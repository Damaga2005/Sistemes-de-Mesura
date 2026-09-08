"""Configuracion global de la pipeline Fase 1. Sin secretos, sin red, determinista."""
from __future__ import annotations

PIPELINE_VERSION = "fase1-1.0"
COURSE = "Sistemes de Mesura (230920)"
LANGUAGE = "ca"

# Fuente inmutable: clon de solo lectura (nunca escribir aqui).
DEFAULT_SOURCE_DIR = r"C:\Users\dmart\AppData\Local\Temp\opencode\Sistemes-de-Mesura"

# Destinos derivados (aislados del original).
DEFAULT_PROCESSED_DIR = "data/processed"
DEFAULT_EVAL_DIR = "data/evaluation"

KNOWLEDGE_DB = "knowledge.sqlite"
EVAL_DB = "eval.sqlite"
REPORT_JSON = "ingestion_report.json"

# Chunking semantico: fusionar parrafos consecutivos hasta este tope, cortando en fin de frase.
PARAGRAPH_MERGE_LIMIT = 1500

# Reconciliacion PDF<->HTML: ratio de vocabulario compartido bajo el cual se marca NEEDS_REVIEW.
RECONCILE_MIN_SHARED_VOCAB = 0.40

# Near-duplicados: Jaccard sobre conjuntos de tokens; solo se registran, nunca se fusionan.
NEARDUP_JACCARD = 0.85

ABSTAIN_PHRASE = "No trobo suport suficient en el material de l'assignatura."

# Stopwords catalanas minimas para metricas de vocabulario (no para indexar).
CA_STOPWORDS = frozenset(
    "el la els les un una uns unes de del al als i o en amb per que qué com més molt tot tota "
    "tots totes aquest aquesta aquests aquestes això son és están esta entre sobre "
    "se es no si també però perquè quan on qual quina".lower().split()
)

# --- F14: rutas efectivas (delegan en app.paths; los DEFAULT_* se conservan
#     como fallback para imports antiguos y ejecucion desde el checkout). ---
from app import paths as _paths  # noqa: E402


def processed_dir():
    return _paths.package_dir() / DEFAULT_PROCESSED_DIR


def eval_dir():
    return _paths.package_dir() / DEFAULT_EVAL_DIR
