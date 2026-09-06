# PHASE_4_REPORT — Examiner Engine

## Estado

```text
GO (pendiente tu revision; detenida aqui por §93-95)
```

## Tests

```text
pytest: 274 passed / 0 failed (231 F0-3 + 43 F4: 20 obligatorios + 23 extra)
```

## Formula gate (P0 absoluto)

```text
2896 / 2896 = 100.00% (committed + gate test + spot vivo; sin tocar golds/KB)
```

## Formula examability

```text
eligible: 2887  blocked: 9 (degenerate_expression, listados)  coverage: 0.9969
```

## Metadata

```text
variables: 205/2896 (0.0708)  units: 0  conditions: 0  context_section: 2818
(UNKNOWN declarado; UNIT_VALIDATION_UNAVAILABLE, jamas PASSED falso)
```

## Generation (benchmark 38 specs, dev/test disjuntos por temas)

```text
generated: 38/38 deterministic VALID  rejected-adversarial: 10/10
live LLM (tipos abiertos): auditado, 0 fugas (ver FAILURE_ANALYSIS)
```

## Quality

```text
hallucination: 0  unsupported_claims en VALID: 0  formula_accuracy: 1.0
calculation_accuracy: 1.0 (re-chequeo)  unit_accuracy: dimensional donde aplica
provenance: 1.0 (chunk+hash+formula siempre)
```

## Reproducibility

```text
seed triple x3 identico (preguntas y examenes)  idempotencia: put() no-op,
fingerprints estables, exam_id determinista
```

## Contamination

```text
KB: UNCHANGED (sqlite+chunks.jsonl+benchmark hash pre/post)
eval.sqlite: ISOLATED (test de cadena + test funcional)
external knowledge: 0 (unit tests + adversarial)
```

## Limitaciones

Ver FAILURE_ANALYSIS. Clave: metadata incompleta, OPEN sin autocalificacion,
semantica no-neuronal heredada, coste live (~8 llamadas/benchmark).

## Recomendacion

GO a Fase 5 (corrector + memoria): el Examiner entrega preguntas VALID con
trazabilidad total y el gate 2896/2896 intacto.
