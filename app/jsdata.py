"""Extraccion de literales JS balanceados (objetos/arrays) con strings. Determinista."""
from __future__ import annotations

import base64
import hashlib
import json
import re


def extract_js_value(js: str, start: int) -> str:
    """Dado el índice de un `{` o `[`, devuelve el literal completo balanceado."""
    opener = js[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    instr = False
    esc = False
    quote = ""
    for j in range(start, len(js)):
        c = js[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                instr = False
        elif c in "\"'":
            instr, quote = True, c
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return js[start : j + 1]
    raise ValueError("literal JS sin cierre")


def find_js_object(js: str, name: str) -> dict:
    m = re.search(r"(?:var|const)\s+" + re.escape(name) + r"\s*=\s*\{", js)
    if not m:
        return {}
    return json.loads(extract_js_value(js, m.end() - 1))


def scripts_of(html: str) -> str:
    return "\n".join(re.findall(r"<script.*?>(.*?)</script>", html, flags=re.S | re.I))


_B64ISH = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def find_image_maps(html: str) -> tuple[dict[str, tuple[str, int]], list[str]]:
    """Mapas figura->bytes en cualquier variable JS ({IMGDATA, FIGS, __IMG__, ...}).

    Devuelve ({fig_key: (sha256, bytes)}, [warnings]). Solo acepta valores que
    decodifican como base64 (con o sin prefijo data:image); el resto se ignora.
    """
    warnings: list[str] = []
    found: dict[str, tuple[str, int]] = {}
    js = scripts_of(html)
    for m in re.finditer(r"(?:(?:var|const)\s+([A-Za-z_$][\w$]*)\s*=\s*\{|window\.(__[A-Za-z]+__)\s*=\s*\{)", js):
        try:
            obj = json.loads(extract_js_value(js, m.end() - 1))
        except ValueError as e:
            warnings.append("mapa JS ilegible (%s)" % e)
            continue
        if not isinstance(obj, dict):
            continue
        hits = 0
        for key, val in obj.items():
            if not isinstance(val, str) or len(val) < 500:
                continue
            uri = val.strip()
            if uri.startswith("data:image"):
                if "," not in uri:
                    continue
                uri = uri.split(",", 1)[1]
            if not _B64ISH.match(uri):
                continue
            try:
                raw = base64.b64decode(uri, validate=False)
            except Exception:
                continue
            if len(raw) < 100:
                continue
            digest = hashlib.sha256(raw).hexdigest()
            if key in found and found[key][0] != digest:
                warnings.append("fig_key duplicada con bytes distintos: %s" % key)
                continue
            found[key] = (digest, len(raw))
            hits += 1
        _ = hits
    return found, warnings
