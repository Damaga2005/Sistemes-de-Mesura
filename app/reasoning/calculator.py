"""Calculadora determinista (§26-28, §50-51). Sin eval(): AST validado.

Soporta +-*/%**() y sqrt/log/ln/exp/abs + constantes pi/e. Conversiones SI
por prefijo + unidades del temario. Chequeo dimensional basico (V/Ω=A).
Tolerancias documentadas: relativa 1e-6 o absoluta 1e-9 (la mayor).
"""
from __future__ import annotations

import ast
import math
import re

REL_TOL = 1e-6
ABS_TOL = 1e-9

_FUNCS = {"sqrt": math.sqrt, "log": math.log10, "ln": math.log, "exp": math.exp,
          "abs": abs, "sin": math.sin, "cos": math.cos, "tan": math.tan}
_CONSTS = {"pi": math.pi, "e": math.e}

_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
            ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
            ast.UAdd, ast.USub)


def safe_eval(expression: str) -> float:
    """Evalua una expresion matematica cerrada. Rechaza nombres raros y sintaxis."""
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError("operacion no permitida: %s" % type(node).__name__)
        if isinstance(node, ast.Call) and (
                not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS):
            raise ValueError("funcion no permitida")
        if isinstance(node, ast.Name) and node.id not in _FUNCS and node.id not in _CONSTS:
            raise ValueError("nombre no permitido: %s" % node.id)
    code = compile(tree, "<calc>", "eval")
    return float(eval(code, {"__builtins__": {}}, {**_FUNCS, **_CONSTS}))


PREFIX = {"p": 1e-12, "n": 1e-9, "µ": 1e-6, "u": 1e-6, "m": 1e-3, "": 1.0,
          "k": 1e3, "M": 1e6, "G": 1e9}
BASE_UNITS = {"V", "A", "Ω", "Ohm", "W", "J", "C", "F", "H", "S", "T", "Hz", "m", "s", "g",
              "kg", "rad", "%", "°C", "K", "dB", "Pa", "N", "Ω·m"}

# Dimensiones SI [kg, m, s, A, K, mol, cd] para chequeo dimensional.
DIM = {
    "V": (1, 2, -3, -1, 0, 0, 0), "A": (0, 0, 0, 1, 0, 0, 0),
    "Ω": (1, 2, -3, -2, 0, 0, 0), "W": (1, 2, -3, 0, 0, 0, 0),
    "J": (1, 2, -2, 0, 0, 0, 0), "C": (0, 0, 1, 1, 0, 0, 0),
    "F": (-1, -2, 4, 2, 0, 0, 0), "H": (1, 2, -2, -2, 0, 0, 0),
    "S": (-1, -2, 3, 2, 0, 0, 0), "T": (1, 0, -2, -1, 0, 0, 0),
    "Hz": (0, 0, -1, 0, 0, 0, 0), "m": (0, 1, 0, 0, 0, 0, 0),
    "s": (0, 0, 1, 0, 0, 0, 0), "g": (1, 0, 0, 0, 0, 0, 0),
    "kg": (1, 0, 0, 0, 0, 0, 0), "K": (0, 0, 0, 0, 1, 0, 0),
    "Pa": (1, -1, -2, 0, 0, 0, 0), "N": (1, 1, -2, 0, 0, 0, 0),
}


def split_unit(unit: str) -> tuple[float, str]:
    """'mV' -> (1e-3, 'V'); 'Ω' -> (1.0, 'Ω'). Error si unidad desconocida."""
    u = (unit or "").strip()
    if u in BASE_UNITS:
        return 1.0, u
    if u in ("°C",):
        return 1.0, u
    m = re.fullmatch(r"([pnumkMGµ%]?)([A-Za-zΩ°]+.*)", u)
    if m and m.group(2) in BASE_UNITS and m.group(1) in PREFIX:
        if m.group(1) == "%":
            return 0.01, ""
        return PREFIX[m.group(1)], m.group(2)
    if u.endswith("%"):
        return 0.01, ""
    raise ValueError("unidad desconocida: %r" % unit)


def to_base(value: float, unit: str) -> tuple[float, str]:
    factor, base = split_unit(unit)
    if base == "°C":
        raise ValueError("°C absoluto requiere contexto (diferencias: 1°C = 1K)")
    return value * factor, base


def close_enough(claimed: float, computed: float) -> bool:
    return abs(claimed - computed) <= max(REL_TOL * max(abs(claimed), abs(computed)), ABS_TOL)


def dimension_of(unit: str) -> tuple | None:
    try:
        _, base = split_unit(unit)
    except ValueError:
        return None
    if base in ("", "%"):
        return (0, 0, 0, 0, 0, 0, 0)
    return DIM.get(base)


def check_dimensions(result_unit: str, operand_units: list[str], op: str = "") -> bool | None:
    """Chequeo basico: V/Ω=A, V*A=W, etc. Devuelve None si no hay datos."""
    if not result_unit or not operand_units or any(not u for u in operand_units):
        return None
    rd = dimension_of(result_unit)
    ods = [dimension_of(u) for u in operand_units]
    if rd is None or any(d is None for d in ods):
        return None
    if op == "/" and len(ods) == 2:
        expect = tuple(a - b for a, b in zip(ods[0], ods[1]))
    elif op == "*" :
        expect = [0] * 7
        for d in ods:
            expect = [a + b for a, b in zip(expect, d)]
        expect = tuple(expect)
    else:
        if any(d != ods[0] for d in ods):
            return None
        expect = ods[0]
    return tuple(expect) == tuple(rd)
