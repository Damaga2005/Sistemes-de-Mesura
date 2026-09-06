# EXAM_BLUEPRINT — Exámenes reproducibles (§39-40, §67-70)

```json
{"topics": ["Tema 2", "Tema 3"], "question_count": 10,
 "types": {"MULTIPLE_CHOICE": 4, "NUMERICAL": 4, "OPEN": 2},
 "difficulty": {"easy": 0.2, "medium": 0.5, "hard": 0.3}}
```

Selección determinista del pool VALID por seed (cuotas de tipo/dificultad;
si el pool no da, shortfall registrado, nunca relleno fuera de blueprint).
Sin cuotas cruzadas: si pides 8 TRUE_FALSE y hay 5, obtienes 5 + shortfall 3.

Prioridad: SAFETY > EVIDENCE > CORRECTNESS > BLUEPRINT > DIVERSITY > QUANTITY.
Trazabilidad: `exam → questions → evidence → sources` y `exam → formulas`
(`get_exam` + tablas). Versiones {examiner, knowledge, retrieval, reasoning}
en cada examen. Triple seed idéntico (test).

CLI: `app.examiner exam --topics 2,3 --count 8 --seed 42 [--types MCQ=4]`.
