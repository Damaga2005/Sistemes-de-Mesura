"""DifficultySelector: prioridad != dificultad (§10 Bloque A).

Conservador: nunca salta mas de un nivel; sin evidencia suficiente no sube;
AT_RISK o evidencia LOW siempre devuelven EASY. Solo niveles del Examiner.
Toda constante vive en difficulty-policy-v1.
"""
from __future__ import annotations

from app.student.policy import DIFFICULTY_POLICY, Policy


class DifficultySelector:
    def __init__(self, policy: Policy | None = None) -> None:
        self.policy = policy or DIFFICULTY_POLICY

    def select(self, *, mastery: float, confidence: float, attempt_count: int,
               history: list[dict] | None = None,
               current_difficulty: str = "",
               recommended_action: str = "PRACTICE",
               status: str = "") -> dict:
        """history: [{difficulty, signal}]. Devuelve {difficulty, reasons, policy}."""
        p = self.policy.parameters
        levels: list[str] = list(p["levels"])
        reasons: list[str] = []
        if status == "AT_RISK":
            return self._out("EASY", reasons + ["at_risk_consolida"])
        if attempt_count < 2:
            return self._out("EASY", reasons + ["baja_evidencia(n=%d)" % attempt_count])
        recent = (history or [])[-4:]
        cur_idx = levels.index(current_difficulty) if current_difficulty in levels else 0
        if recommended_action == "MAINTAIN":
            return self._out(levels[min(cur_idx + 1, len(levels) - 1)]
                             if cur_idx < len(levels) - 1 else levels[-1],
                             reasons + ["mantenimiento"])
        n = len(recent)
        ok = sum(1 for h in recent if (h.get("signal", 0) or 0) >= 0.5)
        rate = (ok / n) if n else 0.0
        conf_ok = confidence >= p["min_confidence_to_step_up"]
        can_step = (n >= p["min_attempts_to_step_up"]
                    and rate >= p["min_recent_success_to_step_up"] and conf_ok)
        if not can_step:
            reasons.append("sin_evidencia_para_subir(rate=%.2f,conf=%.2f,n=%d)"
                           % (rate, confidence, n))
            target = levels[cur_idx] if cur_idx else "EASY"
            if recommended_action in ("PRACTICE", "REINFORCE") and cur_idx > 0:
                target = levels[max(0, cur_idx - 1)]
                reasons.append("consolidar_fundamentos")
            return self._out(target, reasons)
        target_idx = min(cur_idx + p["max_step_up"], len(levels) - 1)
        if levels[target_idx] == "EXPERT":
            hard_ok = any(h.get("difficulty") == "HARD" and (h.get("signal", 0) or 0) >= 0.5
                          for h in recent)
            mastered_cap = p["mastered_max_without_hard_history"]
            if not hard_ok and mastered_cap == "HARD":
                target_idx = levels.index("HARD")
                reasons.append("tope_conservador_sin_historial_HARD")
        return self._out(levels[target_idx],
                         reasons + ["progresion_conservadora(+%d)" %
                                    (target_idx - cur_idx)])

    def _out(self, difficulty: str, reasons: list[str]) -> dict:
        return {"difficulty": difficulty, "reasons": list(reasons),
                "policy_id": self.policy.policy_id,
                "policy_version": self.policy.version}
