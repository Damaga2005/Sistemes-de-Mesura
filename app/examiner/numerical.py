"""Generacion numerica determinista (§17-22): valores con seed, dominios
guardados, calculo con calculator, chequeo dimensional. El LLM jamas calcula.

Clasificacion de valores: SOURCE (del material) / DERIVED (determinista) /
GENERATED_TEST_VALUE (seed, con unidades, sin absurdos, reproducible).
"""
from __future__ import annotations

import ast
import math
import random
import re

from app.reasoning.calculator import safe_eval

SAFE_RANGES = [
    (0.5, 5.0), (1.0, 10.0), (2.0, 20.0), (0.1, 2.0), (10.0, 100.0),
]


def assignable_symbols(expression: str) -> list[str]:
    """Simbolos asignables: letras/giriegas con subindice opcional, sin comandos."""
    syms = re.findall(r"(?:\\(?:alpha|beta|gamma|delta|sigma|mu|omega|theta|lambda|rho|tau|phi)|[A-Za-z](?:_\{[^}]*\}|_[A-Za-z0-9])?)", expression)
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _py_name(sym: str, mapping: dict[str, str]) -> str:
    if sym not in mapping:
        # Identidad preservada: '_' es valido en python; solo se limpian llaves,
        # espacios y comandos. 'R_2'->'R_2' (nunca 'R', que colisionaria con R).
        base = re.sub(r"[\\{}\\s]", "", sym)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", base):
            base = "x"
        name = base
        i = 2
        while name in mapping.values():
            name = "%s%d" % (base, i)
            i += 1
        mapping[sym] = name
    return mapping[sym]


def to_python(expression: str) -> tuple[str, dict[str, str]]:
    """Latex restringido -> expresion python evaluable (para formulas generables).

    Soporta frac, sqrt, cdot/times, subindices. Falla en voz alta si no puede.
    """
    t = expression.strip()
    if t.startswith("$") and t.endswith("$"):
        t = t[1:-1]
    orig = t
    t = t.replace("\\cdot", "*").replace("\\times", "*").replace("\\,", "*")
    t = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", t)
    t = re.sub(r"\\sqrt\[(\d+)\]\{([^{}]+)\}", r"(\2)**(1/\1)", t)
    t = re.sub(r"\\(mathrm|text|mathbf)\{([^{}]+)\}", r"\2", t)
    # Funciones con backslash suelto (\ln 2, \sin x): quitar la barra.
    t = re.sub(r"\\(sqrt|log|ln|exp|sin|cos|tan|abs|pi)\b", r"\1", t)
    # Delimitadores \left \right: pura notacion, se eliminan.
    t = re.sub(r"\\(left|right)\b", "", t)
    # Funcion sin parentesis sobre numero: 'ln 2' -> 'ln(2)'. Solo numeros
    # (con simbolos seria ambiguo y se rechaza honestamente).
    t = re.sub(r"\b(sqrt|log|ln|exp|sin|cos|tan)\s+(\d+(?:\.\d+)?)", r"\1(\2)", t)
    if re.search(r"\\(int|sum|prod|lim|infty|partial|approx|pm|mp|leq|geq|neq|infty)", t):
        raise ValueError("construccion no generable: %s" % orig[:60])
    if "=" in t:
        t = t.split("=", 1)[1].strip()
    mapping: dict[str, str] = {}
    # Subindices primero (mas largos).
    for sym in sorted(set(re.findall(r"[A-Za-z]_\{[^}]*\}|[A-Za-z]_[A-Za-z0-9]", t)),
                      key=len, reverse=True):
        t = t.replace(sym, _py_name(sym, mapping))
    for sym in sorted(set(re.findall(r"[A-Za-z]", t)), key=len, reverse=True):
        if sym in ("e",):
            continue  # se decide abajo: constante o ambiguo
        name = _py_name(sym, mapping)
        t, n = re.subn(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_(])" % sym, name, t)
        if not n:
            del mapping[sym]  # no sustituido (p. ej. dentro de u_c): fuera
    if re.search(r"(?<![A-Za-z0-9_])e(?![A-Za-z0-9_(])", t):
        # 'e' desnuda: Euler o carga elemental segun contexto -> ambiguo, rechazar.
        raise ValueError("simbolo ambiguo 'e' (Euler vs carga elemental)")
    allowed = set(mapping.values()) | {"sqrt", "log", "ln", "exp", "abs", "sin", "cos",
                                       "tan", "pi"}
    rest = set(re.findall(r"[A-Za-z]+(?:_[A-Za-z0-9]+)?", t)) - allowed
    if rest:
        raise ValueError("simbolo no aislado: %s" % sorted(rest)[0])
    # Yuxtaposicion = producto implicito: 2(R1+R2)C -> 2*(R1+R2)*C.
    # El grupo 1 es un solo char (digito o ')'), luego nunca rompe llamadas
    # conocidas (sqrt/log/... empiezan por letra). Regla general documentada.
    t = re.sub(r"(\d|\))([A-Za-z(])", r"\1*\2", t)
    # Notacion funcional f(x): no evaluable como producto; rechazar (honesto).
    # (Despues del chequeo de nombres para no enmascarar otros problemas.)
    for m in re.finditer(r"([A-Za-z][A-Za-z0-9_]*)\(", t):
        if m.group(1) not in ("sqrt", "log", "ln", "exp", "abs", "sin", "cos", "tan"):
            raise ValueError("notacion funcional no soportada: %s(...)" % m.group(1))
    return t, mapping


def generate_values(symbols: list[str], seed: int, units: dict) -> dict[str, dict]:
    """Valores GENERATED_TEST_VALUE reproducibles; denominadores != 0 se
    garantizan en la sustitucion (fase de validacion), no aqui.

    Tabla de normalizacion (§87 permitida y documentada): simbolos con dominio
    conocido (k factor de cobertura, N conteos) usan rangos sanos para evitar
    resultados absurdos (§18). Resto: rangos seguros positivos.
    """
    rng = random.Random(seed)
    out = {}
    for i, s in enumerate(symbols):
        base = re.sub(r"[^A-Za-z]", "", s)
        if base == "k":
            val = float(rng.choice([1, 2, 3]))
        elif base in ("N", "n"):
            val = float(rng.randint(3, 30))
        else:
            lo, hi = SAFE_RANGES[(seed + i) % len(SAFE_RANGES)]
            val = round(rng.uniform(lo, hi), 3)
            if abs(val) < 0.05:
                val = 1.5
        out[s] = {"value": val, "unit": units.get(s, ""), "kind": "GENERATED_TEST_VALUE"}
    return out


def solve(py_expr: str, values: dict[str, float]) -> float:
    """Sustituye valores y evalua con safe_eval (mismo validador que Fase 3)."""
    bound = py_expr
    for name in sorted(values, key=len, reverse=True):
        bound = re.sub(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_(])" % re.escape(name),
                       repr(float(values[name])), bound)
    result = safe_eval(bound)
    if not math.isfinite(result):
        raise ValueError("resultado no finito (dominio invalido)")
    return result


def check_denominators(py_expr: str, values: dict[str, float]) -> tuple[bool, str]:
    """Rechaza division por cero con los valores asignados (via safe_eval)."""
    try:
        tree = ast.parse(py_expr, mode="eval")
    except SyntaxError as e:
        return False, "sintaxis: %s" % e
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            den = ast.unparse(node.right) if hasattr(ast, "unparse") else None
            if den is None:
                return False, "denominador no inspeccionable"
            bound = den
            for name in sorted(values, key=len, reverse=True):
                bound = re.sub(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_(])" % re.escape(name),
                               repr(float(values[name])), bound)
            try:
                if abs(safe_eval(bound)) < 1e-12:
                    return False, "denominador cero"
            except ValueError as e:
                return False, str(e)[:100]
    return True, "OK"
