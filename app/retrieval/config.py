"""Configuracion centralizada del Retrieval (§63). Sin valores magicos repartidos."""
from __future__ import annotations

RETRIEVAL_VERSION = "retrieval-2.0"
INDEX_VERSION = "index-2.0"

# Candidatos por rama antes de fusion.
CANDIDATE_K = 60
DEFAULT_TOP_K = 10

# Pesos de fusion RRF (constante) y combinacion lineal documentada en hybrid.py.
RRF_K = 60

# Pesos del ranking final (justificados en RETRIEVAL_ARCHITECTURE + benchmark dev).
W_LEXICAL = 0.45
W_SEMANTIC = 0.30
W_FORMULA = 0.35  # se suma solo si hay señal de fórmula (no diluye lo demás)
W_PHRASE = 0.25
W_TOPIC = 0.20
W_SECTION = 0.10
W_SOURCE_HTML = 0.10
W_SOURCE_PDF = 0.02
DUP_PENALTY = 0.35  # chunks con dup_of (contenido idéntico ya presente)
PDF_CORROBORATION_CAP = 0.85  # un PDF nunca supera a su evidencia HTML primaria

# Abstencion (calibrados en dev, §32; ver RETRIEVAL_BENCHMARK).
ABSTAIN_MIN_SCORE = 0.12
ABSTAIN_MARGIN = 0.03
AMBIGUITY_MARGIN = 0.06
ABSTAIN_MASS = 0.35  # fraccion minima del peso IDF de la consulta en el top1

# Expansion de consulta: fuzzy de una sola edicion (typos, no palabras distintas).
FUZZY_MIN_LEN = 5
FUZZY_MAX_DIST = 1

# Prior de tipo de contenido para consultas DEFINITION/VARIABLE/CONCEPT.
CONTENT_PRIOR = 0.06
# Tablas en consultas UNIT: los mapeos magnitud<->unidad viven en tablas SI.
TABLE_UNIT_PRIOR = 0.25

# Reranking determinista: top-N a reordenar con señales exactas.
RERANK_DEPTH = 20

# Expansion determinista (cobertura de formulas, §Fase3-2/3).
W_SEC_EXPANSION = 0.30  # chunks de la seccion que la query nombra (>=2 palabras, >=50%)
W_LOOKUP_COVER = 0.50  # chunks con formula que cubre todos los simbolos consultados
