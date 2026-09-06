# PHASE_6_ADAPTIVE_CORE — Bloque A (motor determinista, sin LLM)

Implementa `docs/PHASE_6_PRIORITY_DESIGN.md` §§5–16: ranking explicado +
dificultad conservadora + ruta con exploración + `QuestionSpec` consumible
por `ExaminerEngine.generate()`. Sin UI, sin spacing/decay, sin Fase 7,
sin importador REAL_EXAM, sin LLM en ninguna decisión.

## Componentes (`app/adaptive/`)

| Pieza | Contrato |
|---|---|
| `PriorityCalculator` | `P = 100·(wM·need·evW + wE·err + wR·rec)`; pesos y umbrales solo de `priority-policy-v1`; orden total `(score DESC, unit_id ASC)`; `seed` aceptado, no ordena |
| `DifficultySelector` | prioridad ≠ dificultad; nunca +1 nivel; `n<2` o `AT_RISK` → EASY; tope HARD sin historial HARD; niveles solo del Examiner |
| `LearningPathSelector` | hoja manda (§10: padre suprimido → `ancestro_en_contexto`); `floor(limit·ε)` slots UNSEEN (solo fórmulas, ID estable); `to_spec()` abstiene sin tema (`ValueError`, nunca inventa) |
| Tabla acción→tipo | frozen v1 en `path.py` (§10 + error-directed §11: `CALCULATION/UNIT_ERROR` → NUMERICAL); la dificultad la pone el selector, nunca la tabla |

Lecturas: student DB (mastery/attempts), questions generadas, `formulas.topic`
de KB. Escrituras: ninguna. KB/eval/generadas verificadas intactas por test.

## Benchmark (20 casos, una sola fuente de verdad)

`data/evaluation/adaptive_core_benchmark.jsonl` + `app/adaptive_benchmark.py`
+ `data/evaluation/adaptive_core_results.json` (artefacto verificado).

Casos: vacío, P=40.0 canónico (1 fallo MAJOR d=0), raíz×3 (53.0),
sin-raíces (derivados no computan, 38.25), media+UNIT_ERROR (REINFORCE 41.5),
alta (CHALLENGE 11.5), MASTERED (MAINTAIN residual 22.5), empate (desempate
canónico), jerarquía (1 pick + contexto), exploración ε (limit=8 → 1 slot),
recencia (27.5 > 21.5), 61d sin practicar (40.0), multi (orden total),
AT_RISK (REINFORCE+EASY), step-up (MEDIUM→HARD), tope HARD, n=1 (EASY),
REINFORCE+CALCULATION_ERROR (NUMERICAL), spec exacta + origin forjado
rechazado, determinismo (doble ejecución + seed invariante).

```
python3 app/adaptive_benchmark.py [--write]
python3 -m pytest tests/adaptive/ -q   # 34 tests (20 casos + 14 invariantes)
```

## Estado y deuda

- `difficulty-policy-v1`: `reserved` (Paso 2) → `active` (la consume el
  selector); `test_09` actualizado al nuevo contrato. `spacing-policy`
  sigue `reserved`. Calibración de TUNABLEs con datos docentes: pendiente
  (`unknown`, nunca auto-tuning).
- Deuda conocida: conceptos sin eventos no resuelven tema (abstención
  honesta, no fallback); exploración v1 solo fórmulas; `MAINTAIN` sube un
  nivel (política documentada, revisar con docente).
- Gate 2896/2896 intacto (el selector solo lee `formula_id` opacos).
