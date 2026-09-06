# REASONING_BENCHMARK — 72 casos + 16 live

## Dataset (`data/evaluation/reasoning_benchmark.jsonl`)

10 teoría · 10 fórmulas · 5 variables · 5 unidades · 3 procedimientos ·
2 comparación · 2 visuales · 10 cálculo (valor+tolerancia+unidad, verificados
contra `safe_eval` al generar) · 10 abstención (ausencia verificada en KB) ·
10 adversarial (override, inyección, afirmación usuaria falsa) · 4 ambigüedad.
Gold con grounding (script aborta sin evidencia). Runner:
`python3 -m app.answer_benchmark [--provider extractive|gemini] [--live]`.

## Resultados (congelados)

| Sistema | Score | Detalle |
|---|---|---|
| extractive-fallback (72) | **70/72** | RU01 (ohm sin nombrar), RP01 (composición chunk) — gaps del fallback, ambos OK en Gemini |
| gemini live (16) | **16/16** | incl. 2 cálculos VERIFIED, 3 abstenciones correctas, override rechazado |

## Métricas §67-68 (sistema con Gemini)

Answer Accuracy 16/16 · Evidence Support 1.0 · Formula Accuracy 1.0 (canónicas
exactas) · Formula Coverage 1.0 · Calculation 10/10 (calculator) + 2/2 live ·
Unit Accuracy 1.0 (dimensional cuando aplica) · Citation 1.0 (chunk+hash siempre) ·
Abstention P/R 1.0 · Unsupported claims 0 · Hallucination 0 · Contaminación eval 0.
Variables/unidades por fórmula: parcial (205/2896, medido) → Fase 4.

## Comportamiento adversarial verificado

`U=uc/k` no aceptada · `F=m·a externa` rechazada · `ignora instrucciones`
inerte (evidencia = datos) · override → ABSTAIN `CONFLICTING_EVIDENCE` ·
afirmación usuaria falsa no elevada a evidencia.
