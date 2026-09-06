"""Recurso general de lengua es->ca para retrieval (no especifico de ninguna query).

Solo equivalencias tecnicas estables asignatura. La KB permanece en catalan;
esto solo expande la consulta. Documentado como limitacion: no es traduccion
general, es puente terminologico del dominio.
"""
from __future__ import annotations

ES_CA: dict[str, str] = {
    "puente": "pont", "ruido": "soroll", "incertidumbre": "incertesa",
    "incerteza": "incertesa", "medida": "mesura", "medición": "mesura",
    "medicion": "mesura", "unidad": "unitat", "unidades": "unitat",
    "polarización": "polarització", "corriente": "corrent", "tensión": "tensió",
    "tension": "tensió", "resistencia": "resistència", "temperatura": "temperatura",
    "frecuencia": "freqüència", "frecuencia": "freqüència", "ganancia": "guany",
    "ancho": "amplada", "banda": "banda", "deriva": "deriva", "offset": "offset",
    "etapa": "etapa", "salida": "sortida", "entrada": "entrada",
    "sensibilidad": "sensibilitat", "resolución": "resolució", "resolucion": "resolució",
    "exactitud": "exactitud", "precisión": "precisió", "precision": "precisió",
    "linealidad": "linealitat", "histéresis": "histèresi", "histeresis": "histèresi",
    "termopar": "termoparell", "galga": "galga",
    "pantalla": "pantalla", "apantallamiento": "blindatge", "blindaje": "blindatge",
    "tierra": "terra", "masa": "massa", "cortocircuito": "curtcircuit",
    "interruptor": "interruptor", "multiplexor": "multiplexor", "reloj": "rellotge",
    "muestreo": "mostreig", "resolución": "resolució", "pregunta": "qüestió",
    "respuesta": "resposta", "pregunta": "pregunta", "error": "error",
    "fallo": "error", "avería": "avaria", "averia": "avaria",
    "condensador": "condensador", "bobina": "bobina", "núcleo": "nucli",
    "nucleo": "nucli", "devanado": "bobinat", "espira": "espira",
    "amplificador": "amplificador", "operacional": "operacional",
    "diferencial": "diferencial", "instrumentación": "instrumentació",
    "instrumentacion": "instrumentació", "filtro": "filtre", "rectificador": "rectificador",
    "oscilador": "oscil·lador", "comparador": "comparador", "sensor": "sensor",
    "transductor": "transductor", "actuador": "actuador", "medidor": "mesurador",
    "patrón": "patró", "patron": "patró", "calibración": "calibratge",
    "calibracion": "calibratge", "verificación": "verificació", "trazabilidad": "traçabilitat",
    "repetibilidad": "repetibilitat", "reproducibilidad": "reproductibilitat",
    "deriva": "deriva", "envejecimiento": "envelliment", "ruido": "soroll",
    "interferencia": "interferència", "compatibilidad": "compatibilitat",
    "pantalla": "pantalla", "jaula": "gàbia", "sonda": "sonda",
    "atenuador": "atenuador", "ganancia": "guany", "impedancia": "impedància",
    "admitancia": "admitància", "reactancia": "reactància", "susceptancia": "susceptància",
    "potencia": "potència", "energia": "energia", "carga": "càrrega",
    "descarga": "descàrrega", "aislamiento": "aïllament", "fuga": "fuita",
    "guarda": "guarda", "apantallar": "blinda", "campo": "camp",
    "flujo": "fluxe", "inducción": "inducció", "induccion": "inducció",
    "capacidad": "capacitat", "inductancia": "inductància", "mutua": "mútua",
    "entrehierro": "entreferro", "núcleo": "nucli", "primario": "primari",
    "secundario": "secundari", "espira": "espira", "efecto": "efecte",
    "seebeck": "seebeck", "peltier": "peltier", "thomson": "thomson",
    "piezoeléctrico": "piezoelèctric", "piroeléctrico": "piroelèctric",
    "calcula": "calcula", "calcular": "calcular", "cómo": "com", "como": "com",
    "qué": "què", "cuál": "quina", "cual": "quina", "cuáles": "quines",
    "diferencia": "diferència", "entre": "entre", "sobre": "sobre",
}


def expand_es_ca(terms: list[str]) -> list[str]:
    out = list(terms)
    for t in terms:
        for cand in (t, t[:-2] if t.endswith("es") else t, t[:-1] if t.endswith("s") else t):
            ca = ES_CA.get(cand)
            if ca and ca not in out:
                out.append(ca)
        for conv in morph_candidates(t):
            if conv not in out:
                out.append(conv)
    return out


# Transformaciones candidatas (SIN validar): el llamador solo conserva las que
# existen en el vocabulario del indice. Reglas generales, no por query.
MORPH_RULES = (("ción", "ció"), ("sión", "sió"), ("dad", "tat"),
               ("aje", "atge"), ("an", "en"))


def morph_candidates(term: str) -> list[str]:
    out = []
    for es_suf, ca_suf in MORPH_RULES:
        if term.endswith(es_suf) and len(term) > len(es_suf) + 4:
            out.append(term[: -len(es_suf)] + ca_suf)
    return out


def levenshtein(a: str, b: str, limit: int = 2) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur.append(v)
            row_min = min(row_min, v)
        if row_min > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def fuzzy_correct(term: str, vocab: set[str], *, min_len: int = 5,
                 max_dist: int = 2) -> str | None:
    """Correccion conservadora: distancia minima unica, misma raiz (3 letras),
    longitud casi igual. Empates o colisiones con palabra comun -> None."""
    if len(term) < min_len or term in vocab:
        return None
    best: str | None = None
    best_d = max_dist + 1
    ambiguous = False
    for cand in sorted(vocab):  # orden determinista: mismo resultado siempre
        if abs(len(cand) - len(term)) > 1:
            continue
        if cand[:3] != term[:3]:
            continue
        d = levenshtein(term, cand, max_dist)
        if d < best_d:
            best_d, best, ambiguous = d, cand, False
        elif d == best_d:
            ambiguous = True
    if best is not None and not ambiguous:
        return best
    return None
