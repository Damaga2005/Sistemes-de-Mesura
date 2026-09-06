"""ExamBlueprint: ensamblado determinista y reproducible de examenes (§39-40, §67-70).

Prioridad: SAFETY > EVIDENCE > CORRECTNESS > BLUEPRINT > DIVERSITY > QUANTITY.
Seleccion determinista por seed desde el pool VALIDADO del store.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from app.examiner.models import EXAMINER_VERSION


def assemble_exam(store, *, topics: list[int], question_count: int,
                   types: dict[str, int] | None = None,
                   difficulty: dict[str, float] | None = None,
                   seed: int = 0, kb_version: str = "",
                   retrieval_version: str = "retrieval-2.0",
                   sections: dict[int, list[str]] | None = None,
                   formula_ids: list[str] | None = None,
                   concept_terms: list[str] | None = None,
                   order: str = "seeded_shuffle") -> dict:
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % store.path, uri=True)
    try:
        pool = con.execute(
            "SELECT question_id, topic, type, difficulty, fingerprint,"
            " section, body_json FROM questions "
            "WHERE status='VALID' AND topic IN (%s) ORDER BY question_id" % ",".join(
                "?" * len(topics)), tuple(topics)).fetchall()
        chosen_topics: set[int] = set()
    finally:
        con.close()
    import json as _json
    pool = [list(r) + [_json.loads(r[6] or "{}")] for r in pool]
    if sections:
        pool = [r for r in pool
                if any(r[5].startswith(p) for p in sections.get(r[1], []))]
    if order not in ("seeded_shuffle", "blueprint_order"):
        raise ValueError("order no válido: %r" % order)
    rng = random.Random(seed)
    # Cuotas por tipo/dificultad (proporcionales, deterministas).
    wanted_types = dict(types or {})
    wanted_diff = dict(difficulty or {})
    wanted_f = sorted(set(formula_ids or []))
    wanted_c = sorted(set(concept_terms or []))
    chosen: list[str] = []
    remaining = [list(r) for r in pool]
    rng.shuffle(remaining)
    type_quota = _quotas(wanted_types, question_count)
    diff_quota = _proportions(wanted_diff, question_count)
    type_used: dict[str, int] = {}
    diff_used: dict[str, int] = {}
    have_f, have_c = set(), set()

    def _take(row) -> None:
        qid, topic, _qt, _qd, _fp = row[0], row[1], row[2], row[3], row[4]
        chosen.append(qid)
        chosen_topics.add(topic)
        type_used[row[2]] = type_used.get(row[2], 0) + 1
        diff_used[row[3]] = diff_used.get(row[3], 0) + 1
        have_f.update(row[7].get("formula_ids", []) or [])
        have_c.update(row[7].get("concept_terms", []) or [])

    # Cobertura dura primero (requisitos del blueprint; cuentan en cuotas).
    if wanted_f or wanted_c:
        for row in remaining:
            if len(chosen) >= question_count:
                break
            body = row[7]
            need = (set(body.get("formula_ids", []) or []) & set(wanted_f)
                    - have_f) or \
                   (set(body.get("concept_terms", []) or []) & set(wanted_c)
                    - have_c)
            if need and row[0] not in chosen:
                _take(row)
    for row in remaining:
        if len(chosen) >= question_count:
            break
        qid, topic, qtype, qdiff = row[0], row[1], row[2], row[3]
        if qid in chosen:
            continue
        if type_quota and type_used.get(qtype, 0) >= type_quota.get(qtype, 0):
            continue
        if diff_quota and diff_used.get(qdiff, 0) >= diff_quota.get(qdiff, 0):
            continue
        _take(row)
    # Completar sin cuotas si faltan, pero NUNCA fuera de los tipos pedidos:
    # mejor shortfall registrado que evidencia fuera de blueprint.
    if len(chosen) < question_count:
        have = set(chosen)
        fids = {r[4] for r in pool if r[0] in have}
        for row in remaining:
            qid, topic, qtype = row[0], row[1], row[2]
            if len(chosen) >= question_count:
                break
            if type_quota and qtype not in type_quota:
                continue
            if qid not in have and row[4] not in fids:
                _take(row)
                have.add(qid)
                fids.add(row[4])
    if order == "blueprint_order":
        slot = {r[0]: (r[1], r[2], r[0]) for r in pool}
        chosen = sorted(chosen, key=lambda q: slot.get(q, (0, "", q)))
    exam_id = "ex-" + hashlib.sha256(
        ("%d|%s|%s|%s|%s" % (seed, sorted(topics), sorted(chosen),
                             EXAMINER_VERSION, kb_version)).encode()).hexdigest()[:12]
    versions = {"examiner": EXAMINER_VERSION, "knowledge": kb_version,
                "retrieval": retrieval_version, "reasoning": "reasoning-3.0"}
    return {"exam_id": exam_id, "seed": seed, "question_ids": chosen,
            "blueprint": {"topics": topics, "question_count": question_count,
                          "types": wanted_types, "difficulty": wanted_diff},
            "versions": versions,
            "coverage": {"topics": sorted(chosen_topics),
                         "shortfall": question_count - len(chosen),
                         "formulas_covered": sorted(have_f & set(wanted_f)),
                         "concepts_covered": sorted(have_c & set(wanted_c))}}


def _quotas(wanted: dict[str, int], total: int) -> dict[str, int]:
    return {k: v for k, v in wanted.items() if v > 0}


def _proportions(wanted: dict[str, float], total: int) -> dict[str, int]:
    if not wanted or abs(sum(wanted.values()) - 1.0) > 0.02:
        return {}
    out, acc = {}, 0
    keys = sorted(wanted)
    for k in keys[:-1]:
        out[k] = round(wanted[k] * total)
        acc += out[k]
    out[keys[-1]] = total - acc
    return out
