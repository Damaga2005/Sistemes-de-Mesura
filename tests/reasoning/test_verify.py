"""Tests de verificacion determinista: formulas, calculos, claims, unidades.

Sin LLM: Validador + calculadora + verificador sobre la KB real.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.reasoning.calculator import (  # noqa: E402
    check_dimensions, close_enough, safe_eval, split_unit, to_base,
)
from app.reasoning.claims import ClaimVerifier, extract_claims, verify_calculation  # noqa: E402
from app.reasoning.formula_check import FormulaValidator, equivalent  # noqa: E402
from app.reasoning.models import Claim  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")


@pytest.fixture(scope="module")
def validator():
    return FormulaValidator(KB)


# --- FormulaValidator: exact / equivalent / mismatch / missing ---
def test_validator_exact(validator):
    status, rec = validator.check_latex("$U=k\\,u_c$")
    assert status == "EXACT_MATCH" and rec["equation_id"].startswith("eq-02-")


def test_validator_equivalent_commutative():
    assert equivalent("$U=k\\,u_c$", "$U=u_c\\,k$")
    assert equivalent("$U=k\\,u_c(y)$", "$U = u_c(y)\\,k$")


def test_validator_mismatch_division():
    assert not equivalent("$U=k\\,u_c$", "$U=u_c/k$")
    status, _ = FormulaValidator(KB).check_latex("$U=u_c/k$")
    assert status in ("MISSING", "MISMATCH")


def test_validator_missing_id(validator):
    assert validator.check_id("eq-99-9999")[0] == "MISSING"


def test_validator_rejects_external_formula(validator):
    # E=mc^2 no forma parte del temario (F=m*a SI esta en T9: el validador la
    # encuentra correctamente; aqui se prueba el rechazo real).
    status, _ = validator.check_latex("$E=m\\,c^2$")
    assert status == "MISSING"


def test_validator_live_kb_count(validator):
    assert len(validator._by_id) == 2896


# --- Calculator: exacta, segura, dimensional ---
@pytest.mark.parametrize("expr,expected", [
    ("2*0.5", 1.0), ("2*1.3", 2.6), ("sqrt(16)", 4.0), ("2200*0.001", 2.2),
    ("10/4", 2.5), ("0.03*200", 6.0), ("sqrt(2)**2", 2.0), ("10*0.001", 0.01),
    ("20*log(100)", 40.0), ("4*1.38e-23*300*1000*1000", 1.656e-14),
])
def test_calculator_exact(expr, expected):
    assert close_enough(safe_eval(expr), expected)


def test_calculator_rejects_eval_abuse():
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('x')")
    with pytest.raises(ValueError):
        safe_eval("open('f').read()")


def test_calculator_units():
    assert to_base(2200, "mV") == (2.2, "V")
    assert to_base(10, "mA") == (0.01, "A")
    with pytest.raises(ValueError):
        to_base(1.0, "parsecs")


def test_dimensional_check():
    assert check_dimensions("A", ["V", "Ω"], "/") is True
    assert check_dimensions("W", ["V", "A"], "*") is True
    assert check_dimensions("V", ["V", "Ω"], "/") is False
    assert check_dimensions("A", [], "/") is None


def test_verify_calculation_match():
    r = verify_calculation("2*0.5", 1.0, "")
    assert r["match"] and r["computed"] == 1.0


def test_verify_calculation_mismatch():
    r = verify_calculation("2*0.5", 2.0, "")
    assert not r["match"]


def test_verify_calculation_dimension_fail():
    r = verify_calculation("5/2", 2.5, "V", ["V", "Ω"], "/")
    assert not r["match"]


# --- Claims: extraccion y verificacion ---
def test_extract_claims_shape():
    cs = extract_claims({"claims": [{"text": "a", "type": "FORMULA", "evidence_ids": ["x"]},
                                    {"text": "", "type": "FACTUAL"}]})
    assert len(cs) == 1 and cs[0].type == "FORMULA"


def test_claim_formula_supported(validator):
    v = ClaimVerifier(validator)
    c = v.verify(Claim(text="La expandida es $U=k\\,u_c$", type="FORMULA",
                       evidence_ids=["eq-02-0201"]),
                 {}, {"eq-02-0201": {"equation_id": "eq-02-0201"}})
    assert c.status == "SUPPORTED"


def test_claim_formula_contradicted(validator):
    v = ClaimVerifier(validator)
    c = v.verify(Claim(text="La expandida es $U=u_c/k$", type="FORMULA", evidence_ids=[]),
                 {"c1": "texto"}, {})
    assert c.status in ("CONTRADICTED", "UNSUPPORTED")


def test_claim_no_evidence_unsupported(validator):
    v = ClaimVerifier(validator)
    c = v.verify(Claim(text="Algo sin citas", type="FACTUAL", evidence_ids=[]), {}, {})
    assert c.status == "UNSUPPORTED"


def test_claim_variable_partial_without_definition(validator):
    v = ClaimVerifier(validator)
    c = v.verify(Claim(text="uc incertesa típica", type="VARIABLE",
                       evidence_ids=["c1"]), {"c1": "uc es la incertesa típica"}, {})
    assert c.status in ("SUPPORTED", "PARTIALLY_SUPPORTED")


def test_significant_figures_from_kb():
    # T2 §8 fija reglas de formato del resultado (retrieve, no asumir).
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM chunks WHERE text LIKE '%xifra%'"
                        " OR text LIKE '%arrodon%'").fetchone()[0]
        assert n > 0
    finally:
        con.close()
