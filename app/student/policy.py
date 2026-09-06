"""Politica mastery v1 (versionada, determinista, documentada §103).

- Senal por intento: 1.0 CORRECT, 0.5 PARTIALLY_CORRECT, 0.0 INCORRECT.
  NEEDS_REVIEW/UNGRADABLE/NO_ANSWER no actualizan (solo registran intento).
- score = media ponderada con sesgo a recencia suave: w_i = 1 + 0.1*i
  (i = indice cronologico). Historial nunca borrado (§54).
- confidence = min(1, intentos_contados/8) * (1 - varianza_reciente/4).
  1 acierto NO da 100% confianza (§51); el score puede ser alto pero la
  confianza refleja la evidencia.
- status: UNKNOWN (0 intentos) | EMERGING (<0.4 o <2 intentos) |
  DEVELOPING (<0.7) | PROFICIENT (<0.9 y >=4 intentos) | MASTERED (>=0.9 y
  >= minimo_evidencia=4 intentos con >=3 correctos) | AT_RISK (ultimos 3
  incorrectos con >=3 intentos). Sin diagnostico psicologico (§60).
- Agregacion: media ponderada por intentos de unidades hijas (formula/
  concepto -> seccion -> topic). Rollup observacional, sin inventar
  dependencias: hijas = misma seccion/topic o co-ocurrencia en preguntas.
- Recencia documentada, sin borrar historial. Sin decay por defecto.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

MIN_EVIDENCE_MASTERED = 4
MIN_CORRECT_MASTERED = 3
CONFIDENCE_N = 8
POLICY_VERSION = "mastery-policy-v1"

SIGNAL = {"CORRECT": 1.0, "PARTIALLY_CORRECT": 0.5, "INCORRECT": 0.0}
COUNTED = {"CORRECT": "correct", "PARTIALLY_CORRECT": "correct", "INCORRECT": "incorrect"}


@dataclass(frozen=True)
class Policy:
    """Abstraccion minima de politica versionada (Fase 6, GAP 2).

    Identidad inequivoca: policy_id + version (+ parameters opcionales).
    Determinista, serializable (sort_keys), reproducible, compatible con
    replay (los eventos guardan policy_version y nunca se reescriben),
    independiente del LLM. Sin framework: un dataclass congelado + registro.
    """
    policy_id: str
    version: str
    parameters: dict = field(default_factory=dict)
    status: str = "active"  # active | reserved (reservada, sin algoritmo aun)

    def key(self) -> str:
        return "%s@%s" % (self.policy_id, self.version)

    def dumps(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def loads(raw: str) -> "Policy":
        d = json.loads(raw)
        return Policy(policy_id=d["policy_id"], version=d["version"],
                      parameters=d.get("parameters", {}),
                      status=d.get("status", "active"))


MASTERY_POLICY = Policy(
    policy_id="mastery-policy",
    version="v1",
    parameters={"min_evidence_mastered": MIN_EVIDENCE_MASTERED,
                "min_correct_mastered": MIN_CORRECT_MASTERED,
                "confidence_n": CONFIDENCE_N,
                "signal_correct": 1.0, "signal_partial": 0.5, "signal_incorrect": 0.0,
                "recency_alpha": 0.1},
    status="active",
)
PRIORITY_POLICY = Policy(
    policy_id="priority-policy",
    version="v1",
    parameters={"w_mastery": 0.5, "w_error": 0.3, "w_recency": 0.2,
                "evidence_weight": {"LOW": 0.3, "MODERATE": 0.7, "HIGH": 1.0},
                "severity_weight": {"MAJOR": 1.0, "MODERATE": 0.6, "MINOR": 0.2},
                "recency_buckets_days": [7, 30],
                "recency_values": [0.2, 0.6, 1.0],
                "recency_unseen": 1.0,
                "recent_failure_boost": 0.5,
                "recent_failure_window_days": 7,
                "action_mastery_low": 0.4, "action_mastery_high": 0.7,
                "exploration_epsilon": 0.125},
    status="active",
)
DIFFICULTY_POLICY = Policy(
    policy_id="difficulty-policy",
    version="v1",
    parameters={
        # Niveles canónicos del Examiner, orden inmutable.
        "levels": ["EASY", "MEDIUM", "HARD", "EXPERT"],
        # Nunca saltar mas de un nivel por decision.
        "max_step_up": 1,
        # Sin evidencia suficiente no se sube: umbral conservador.
        "min_attempts_to_step_up": 2,
        "min_recent_success_to_step_up": 0.75,
        "min_confidence_to_step_up": 0.5,
        # MASTERED puede aspirar como maximo a HARD salvo historial HARD.
        "mastered_max_without_hard_history": "HARD",
        # AT_RISK o evidencia LOW siempre devuelven EASY.
    },
    status="active",
)
SPACING_POLICY = Policy(
    policy_id="spacing-policy",
    version="v1",
    parameters={
        # Buckets de recencia sobre dias desde last_attempt (n==0: NEVER_SEEN).
        # Sin decay continuo: solo etiquetas discretas (Bloque B, §4).
        "buckets_days": [1, 7, 30],
        "bucket_names": ["VERY_RECENT", "RECENT", "NORMAL", "OLD"],
        # Diferir solo lo correcto-reciente no-critico (debilidad > spacing).
        "defer_correct_within_days": 7,
        # Criticidad (cualquiera basta): AT_RISK, dominio muy bajo con
        # evidencia minima, o raiz causal con dominio <0.7 y >=2 fallos.
        "critical_statuses": ["AT_RISK"],
        "critical_mastery_below": 0.4,
        "critical_min_attempts": 2,
        "critical_root_mastery_below": 0.7,
        "critical_root_min_incorrect": 2,
        # Umbral de categoria 2 (high priority practice) del Builder.
        "high_priority_min_score": 40.0,
    },
    status="active",
)
POLICIES: dict[str, Policy] = {
    MASTERY_POLICY.key(): MASTERY_POLICY,
    PRIORITY_POLICY.key(): PRIORITY_POLICY,
    DIFFICULTY_POLICY.key(): DIFFICULTY_POLICY,
    SPACING_POLICY.key(): SPACING_POLICY,
}


def get_policy(policy_id: str, version: str) -> Policy:
    key = "%s@%s" % (policy_id, version)
    if key not in POLICIES:
        raise KeyError("policy desconocida: %s (no inventar versiones)" % key)
    return POLICIES[key]


def signal_for(status: str) -> float | None:
    return SIGNAL.get(status)


def _params() -> dict:
    return MASTERY_POLICY.parameters


def update_score(signals: list[float]) -> float:
    if not signals:
        return 0.0
    alpha = _params()["recency_alpha"]
    weights = [1.0 + alpha * i for i in range(len(signals))]
    return round(sum(s * w for s, w in zip(signals, weights)) / sum(weights), 4)


def update_confidence(n: int, recent: list[float]) -> float:
    import statistics
    base = min(1.0, n / _params()["confidence_n"])
    if len(recent) >= 2:
        try:
            var = statistics.pvariance(recent)
        except statistics.StatisticsError:
            var = 0.0
        base *= max(0.0, 1.0 - var / 4.0)
    return round(base, 4)


def status_for(score: float, n: int, n_correct: int, last3: list[float]) -> str:
    if n == 0:
        return "UNKNOWN"
    if len(last3) >= 3 and all(s <= 0.0 for s in last3[-3:]) and n >= 3:
        return "AT_RISK"
    if score >= 0.9 and n >= _params()["min_evidence_mastered"] \
            and n_correct >= _params()["min_correct_mastered"]:
        return "MASTERED"
    if score >= 0.7 and n >= 4:
        return "PROFICIENT"
    if score >= 0.4 and n >= 2:
        return "DEVELOPING"
    return "EMERGING"


def aggregate(children: list[tuple[float, int]]) -> tuple[float, int]:
    """Hijas (score, intentos) -> (score, intentos). Media ponderada."""
    total = sum(n for _, n in children)
    if not total:
        return 0.0, 0
    return round(sum(s * n for s, n in children) / total, 4), total
