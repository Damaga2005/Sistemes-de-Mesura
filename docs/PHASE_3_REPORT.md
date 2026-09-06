# PHASE_3_REPORT — Reasoning Engine + Tutor verificable

## Resumen

Tubo completo KB→retrieval→pack→LLM→claims→verificación→respuesta/abstención
(`app/reasoning/`, `app/llm/`, `app/answer.py`). Proveedor real (Gemini
3.5-flash-lite, t=0, JSON) + fallback extractivo determinista. Sin memoria,
sin exámenes, sin UI (§90).

## Arquitectura / LLM / Retrieval / Verification

Ver `REASONING_ARCHITECTURE.md`, `LLM_PROVIDER.md`, `VERIFICATION_ARCHITECTURE.md`.
Retrieval se consume solo vía `EvidencePack` (presupuesto §21); el razonador
no toca SQLite. Rondas máx 2 + timeout implícito (sin loops).

## Fórmulas: 2896 / 2896 = 100 % (gate §86 en verde)

Cobertura por canales generales (lookup exacto, secciones, substring latex,
normalización ca). Exactitud: registros canónicos siempre; validador
exact/equivalent/mismatch (`U=k·u_c == U=u_c·k`, `U=uc/k` no). Variables:
205/2896 con evidencia local; resto `[]` → Fase 4 (limitación explícita,
no invención).

## Cálculos

AST validado (10/10 determinista incl. `4kTR` y `20·log(100)=40 dB`) +
dimensional (`V/Ω=A`) + tolerancias documentadas + 2/2 live VERIFIED.

## Abstention

10/10 benchmark + Tema 20 + override adversarial (`CONFLICTING_EVIDENCE`).
Tipos §33 implementados; frase ES/CA.

## Benchmark / Tests

72 casos (extractive 70/72, gaps acotados) + 16 live (16/16).
`pytest tests/`: **231 passed** (132 F0-2 + 99 F3: cobertura, provider,
verificación, integración). Regresión F0→F2 intacta (retrieval 100 % ambos
splits, KB inmutable tras responder, sin memoria, sin contaminación).

## Fallos / Limitaciones

Ver `REASONING_FAILURE_ANALYSIS.md`. Clave: extractive infrarresponde 2/72;
live varía entre ejecuciones (verificador lo contiene); variables/unidades
por fórmula parciales; semántico no-neuronal (heredado F2).

## Recomendación: GO a Fase 4 (con alcance)

¿Razonar sin inventar? **SÍ** (0 unsupported críticos, 0 fugas, citas 100 %).
¿100 % fórmulas? **SÍ**. Fase 4 natural: examiner con rúbricas + variables/
unidades por fórmula + memoria (diseño ya previsto, sin implementar).
