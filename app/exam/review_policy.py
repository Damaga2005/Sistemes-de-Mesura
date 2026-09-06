"""review-policy-v1: que puede mostrarse en review (frozen, versionada).

Sin tabla (D108): un solo objeto congelado + registro. Flags B4/D107;
REAL_EXAM ciego por defecto (D+ §5). `llm_explainer` solo admite "off"
(D112): cualquier otro valor es policy invalida, no fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import ExamError

REVIEW_POLICY_ID = "review-policy"
REVIEW_POLICY_VERSION = "review-policy-v1"

FLAGS = ("reveal_score", "reveal_student_answer", "reveal_correct_answer",
         "reveal_solution", "reveal_formula", "reveal_source",
         "reveal_errors", "reveal_rubric")

DEFAULTS: dict[str, object] = {
    "reveal_score": True,
    "reveal_student_answer": True,
    "reveal_correct_answer": True,
    "reveal_solution": True,
    "reveal_formula": True,
    "reveal_source": True,
    "reveal_errors": True,
    "reveal_rubric": False,
    "feedback_lang": "ca",
    "llm_explainer": "off",
}

# REAL_EXAM: nada que comprometa examenes reales futuros (B4 §5).
BLIND_DEFAULTS: dict[str, object] = {
    "reveal_correct_answer": False,
    "reveal_solution": False,
    "reveal_formula": False,
}

LANGS = ("ca", "es")


@dataclass(frozen=True)
class ReviewPolicy:
    policy_id: str = REVIEW_POLICY_ID
    version: str = REVIEW_POLICY_VERSION
    parameters: dict = field(default_factory=lambda: dict(DEFAULTS))
    status: str = "active"

    def key(self) -> str:
        return "%s@%s" % (self.policy_id, self.version)


REVIEW_POLICY = ReviewPolicy()


def get_review_policy(version: str) -> ReviewPolicy:
    if version in ("", REVIEW_POLICY_VERSION):
        return REVIEW_POLICY
    raise ExamError("REVIEW_POLICY_NOT_FOUND: %r" % version)


def effective_policy(exam_kind: str, version: str = "") -> dict:
    """Parametros efectivos + provenance. Sin fallback silencioso."""
    pol = get_review_policy(version)
    params = dict(pol.parameters)
    if exam_kind == "REAL_EXAM":
        params.update(BLIND_DEFAULTS)
    lang = params.get("feedback_lang", "ca")
    if lang not in LANGS:
        raise ExamError("feedback_lang no soportado: %r" % lang)
    if params.get("llm_explainer", "off") != "off":
        raise ExamError("llm_explainer debe ser 'off' (D112)")
    for f in FLAGS:
        if not isinstance(params.get(f), bool):
            raise ExamError("flag no booleano: %r" % f)
    return {"policy_id": pol.policy_id, "policy_version": pol.version,
            "exam_kind": exam_kind, "parameters": params}
