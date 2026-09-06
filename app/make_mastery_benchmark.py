"""Benchmark de mastery (§84): historiales sinteticos con estados esperados
derivados a mano de la politica v1 (media ponderada w=1+0.1i, confianza
min(1,n/8), estados por umbrales). Estudiantes sinteticos, jamas reales (§85).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
WORKSPACE = Path(__file__).resolve().parent.parent
DEST = WORKSPACE / "data" / "evaluation" / "mastery_benchmark.jsonl"

# (id, signals, expected_status, expected_score, split)
# scores a mano: w=[1,1.1,...]; ej [1,0,1,0] -> (1+1.2)/4.6 = 0.4783
CASES = [
    ("M01", [1, 1, 1, 1], "MASTERED", 1.0, "dev"),
    ("M02", [0, 0, 0], "AT_RISK", 0.0, "dev"),
    ("M03", [1, 0, 1, 0], "DEVELOPING", 0.4783, "dev"),
    ("M04", [1], "EMERGING", 1.0, "dev"),
    ("M05", [1, 1, 1, 1, 1, 1, 1, 1], "MASTERED", 1.0, "dev"),
    ("M06", [0, 0, 0, 0, 0], "AT_RISK", 0.0, "dev"),
    ("M07", [1, 1, 0, 1, 1], "PROFICIENT", 0.8, "dev"),
    ("M08", [0, 1, 1, 1], "PROFICIENT", 0.7826, "dev"),
    ("M09", [1, 1, 1, 0, 0, 0], "AT_RISK", 0.44, "test"),
    ("M10", [0, 0, 1, 1, 1, 1], "PROFICIENT", 0.72, "test"),
    ("M11", [1, 1], "DEVELOPING", 1.0, "test"),
    ("M12", [0, 1], "DEVELOPING", 0.5238, "test"),
]


def main() -> None:
    from app.student import policy
    with DEST.open("w", encoding="utf-8") as fh:
        for cid, signals, status, score, split in CASES:
            got_score = policy.update_score([float(s) for s in signals])
            assert abs(got_score - score) < 0.001, (cid, got_score, score)
            n_correct = sum(1 for s in signals if s >= 0.5)
            got_status = policy.status_for(got_score, len(signals), n_correct,
                                           [float(s) for s in signals][-3:])
            assert got_status == status, (cid, got_status, status)
            conf = policy.update_confidence(len(signals), [float(s) for s in signals][-7:])
            fh.write(json.dumps({"id": cid, "signals": signals, "expected_status": status,
                                 "expected_score": score, "expected_confidence": conf,
                                 "split": split}, ensure_ascii=False, sort_keys=True) + "\n")
    print("mastery benchmark: %d casos verificados contra la politica" % len(CASES))


if __name__ == "__main__":
    main()
