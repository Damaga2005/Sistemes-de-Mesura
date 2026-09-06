"""Cobertura examinadora (§15-16, §37): por formula, elegible/bloqueada + motivo.

Elegible = generable en ALGUN tipo determinista (TF siempre que haya frase;
MCQ si no degenerada; NUMERICAL si to_python pasa). Bloqueada con razon
explicita (jamas oculto). Las variables/unidades/condiciones se miden tal
cual estan en KB (UNKNOWN si ausentes, nunca inventadas).
Uso: python3 -m app.examiner_coverage
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.examiner import numerical as NUM  # noqa: E402
from app.examiner.distractors import _variants  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent
DEST = WORKSPACE / "data" / "evaluation" / "formula_examiner_coverage.json"


def _has_alnum(expr: str) -> bool:
    core = expr.strip()
    if core.startswith("$") and core.endswith("$"):
        core = core[1:-1]
    core = re.sub(r"\\[a-zA-Z]+", "X", core)  # comandos cuentan como contenido
    return any(unicodedata.category(c).startswith("L") or c.isdigit() for c in core)


def assess(form: dict) -> tuple[bool, str]:
    expr, vars_ = form["expression"], form.get("variables", [])
    if not _has_alnum(expr):
        return False, "degenerate_expression"  # p. ej. '$)$', '_{}' vacios
    try:
        py, _ = NUM.to_python(expr)
    except ValueError:
        py = ""
    # NUMERICAL exige computo real (operador); un simbolo solo ($R_3$) no es
    # un ejercicio ("calcula R_3 dado R_3" seria absurdo §18).
    if py and re.search(r"[-+*/%()]|sqrt|log|ln|exp|sin|cos", py):
        return True, "eligible:numerical"
    if _variants(expr):
        return True, "eligible:formula-mcq"
    if form.get("section_h2"):
        return True, "eligible:true-false"
    return False, "no_section_context"


def main() -> None:
    forms = [json.loads(l) for l in
             (WORKSPACE / "data" / "processed" / "formulas.jsonl").read_text(
                 encoding="utf-8").splitlines()]
    eligible: list = []
    blocked: list = []
    reasons: dict = {}
    var_known = units_known = cond_known = ctx_known = 0
    for f in forms:
        ok, why = assess(f)
        if f.get("variables"):
            var_known += 1
        if f.get("section_h2"):
            ctx_known += 1
        # units/conditions: no extraidos en KB -> UNKNOWN honesto.
        if ok:
            eligible.append(f["equation_id"])
        else:
            blocked.append({"formula_id": f["equation_id"], "reason": why})
            reasons[why] = reasons.get(why, 0) + 1
    total = len(forms)
    report = {
        "total_formulas": total, "eligible_formulas": len(eligible),
        "blocked_formulas": len(blocked),
        "coverage": round(len(eligible) / total, 4) if total else 0.0,
        "block_reasons": reasons, "blocked_sample": blocked[:20],
        "metadata_completeness": {
            "variables": var_known, "variables_pct": round(var_known / total, 4),
            "units": units_known, "units_pct": 0.0,
            "conditions": cond_known, "conditions_pct": 0.0,
            "context_section": ctx_known,
            "context_pct": round(ctx_known / total, 4)},
    }
    DEST.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("examability: %d/%d = %.2f%% blocked=%d %s" % (
        len(eligible), total, 100 * len(eligible) / total, len(blocked), reasons))


if __name__ == "__main__":
    main()
