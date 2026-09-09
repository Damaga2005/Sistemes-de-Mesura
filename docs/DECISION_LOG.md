# DECISION_LOG — Fase 0

| # | Decisión | Motivo | Alternativas descartadas | Confianza |
|---|---|---|---|---|
| D1 | HTML teoría = fuente primaria; PDF = corroboración | HTML tiene LaTeX canónico en comentarios + jerarquía semántica; PDF tiene más texto pero sin estructura explotable | PDF primario (pierde LaTeX exacto) / solo-HTML (pierde corroboración y parte visual) | alta |
| D2 | Extracción de fórmulas vía comentarios `<!-- $…$ -->` (Temas 2–10) | Ratio 1:1 comentario↔SVG verificado en 2.858 casos; determinista, sin OCR | MathJax/KaTeX (inexistente), OCR sobre SVG (pérdida de subíndices), texto del PDF (no canónico) | alta |
| D3 | Parser específico para Tema 1 (`<sub>/<sup>` Unicode) | Tema 1 no tiene SVG ni LaTeX; fidelidad menor pero medible con tests | Forzar el parser general (0 fórmulas en T1) / OCR (sobrecoste, peor) | media-alta |
| D4 | Ponderar doble fuente (infraponderar PDF) | PDF↔HTML solapan materia con distinta redacción (T2 medido); indexar plano duplicaría recuperación | Índice único sin `source_type` (sobrepondera) / excluir PDF (pierde 1,5× texto y 347 imgs) | media-alta |
| D5 | Chunking semántico por bloques tipados, nunca tokens fijos | La jerarquía h1/h2 + cajas existe y es uniforme; tokens fijos romperían definiciones/fórmulas | 500-token chunks (rápido pero destruye trazabilidad semántica) | alta |
| D6 | SQLite + índice vectorial local embebido (Fase 2) | Volumen real pequeño (~miles de chunks); portabilidad y coste 0 | Vector DB servida / cloud (sobreingeniería para 122 MB) | media |
| D7 | Banco V/F de entrenament → `evaluation/`, jamás al índice | Son ~500 preguntas con justificación y origen: gold para eval; indexarlas filtraría respuestas | Indexar todo (fuga train-test, respuestas memorizadas) | alta |
| D8 | `LLMProvider`/`EmbeddingProvider` abstractos desde el día 1 | El modelo disponible puede ser temporal; el conocimiento persiste fuera del LLM | Acoplar a Muse Spark (deuda de migración) | alta |
| D9 | Topic derivado de la carpeta, nunca del nombre | Nomenclatura inconsistente (`SM_U1_*`, `2_*`, `01_doc`…); la carpeta es la única señal estable | Regex sobre nombres (frágil, test 10 lo prohíbe) | alta |
| D10 | Abstención explícita como comportamiento de primera clase | Asignatura técnica con pares confusos; preferible abstención correcta a invención | Responder siempre (alucinación) | alta |
| D11 | Imágenes deduplicadas por hash de bytes + `image_context` | Tema 5 repite 39 base64/página; sin dedup el índice visual miente sobre cobertura | Indexar cada `<img>` tal cual (ruido ×8) / ignorar visual (pierde teoría esencial) | media-alta |
| D12 | No crear `app/` completa ni agentes especializados en Fase 0 | La auditoría manda: solo esqueleto determinista `app/phase0_spec.py` + tests; agentes cuando aporten valor medido | Implementar pipeline/RAG ya (codificar antes de comprender) | alta |

## Fase 1 (pipeline `fase1-1.0`)

| # | Decisión | Motivo | Alternativas descartadas | Confianza |
|---|---|---|---|---|
| D13 | Parser HTML con stdlib (`html.parser`), sin dependencias | Portabilidad y determinismo; la estructura es regular | BeautifulSoup/lxml (dependencia innecesaria para 81 docs) | alta |
| D14 | Figuras desde mapas JS (`IMGDATA`/`FIGS`/`window.__IMG__`) + `alt` como caption | Los `<img>` son referencias `data-fig` vacías; los bytes y el contexto catalán viven en JS+`alt` | Contar solo `<img>` (265 filas sin bytes) / OCR (innecesario) | alta |
| D15 | 1 fila por asset visual único + `occurrences` | Tema 5 comparte pool de 39 assets entre páginas; filas por ocurrencia violan PK y mienten cobertura | Fila por ocurrencia (duplicados) / ignorar repetidos (pierde trazabilidad) | alta |
| D16 | Tail-match único para `doc_ref` DOCS (T6–T10), resto NEEDS_REVIEW | Los DOCS omiten el prefijo numérico del nombre real; match único determinista, ambigüedad nunca resuelta en silencio | Resolver por similitud difusa (no determinista) / dejar todo en NULL (pierde 250 trazabilidades válidas) | alta |
| D17 | Preguntas DATA (T3–T5) con `expected_source` NULL por diseño | Sus blocs son temáticos, no archivos; consta en `origin` | Forzar un archivo (trazabilidad falsa) | alta |
| D18 | Sin tabla `Relationship`: aplazada a Fase 3 con verificación | Ningún patrón determinista extrae relaciones académicas con evidencia; la jerarquía ya vive en `sections`/`parent_context` | Heurísticas de co-ocurrencia (relaciones inventadas) | alta |
| D19 | Variables de fórmula solo con evidencia local (`on X és…`) | Regla 4: sin evidencia → `[]`, nunca inventar significado/unidad | Rellenar con conocimiento externo (contaminación) | alta |
| D20 | `data/processed/` y `data/evaluation/` versionados en git | Son el entregable verificable de la fase (~9,7 MB); re-ejecución bit-idéntica demostrada | Ignorarlos (Fase 2 sin entrada comprometida) | media-alta |

## Fase 2 (`retrieval-2.0` / `index-2.0`)

| # | Decisión | Motivo | Alternativas descartadas | Confianza |
|---|---|---|---|---|
| D21 | Semántico TF-IDF local real, no neural | Sin torch/sklearn/modelo offline en el entorno; §19 permite estrategia local honesta + limitación documentada | Fingir semántica / descargar modelo sin verificar licencia-offline | alta |
| D22 | Fusión RRF (k=60) + ranking lineal explicado | RRF no calibra escalas dispares (BM25 vs coseno); pesos solo donde son interpretables | 0.5/0.5 sin justificar | alta |
| D23 | Expansión es→ca (diccionario + morfología validada + fuzzy 1ed) | Benchmark exige ES; cada mecanismo con guardarraíl medido (`president→precedent` bloqueado) | Traductor externo (red) / nada (ES falla) | media-alta |
| D24 | Plegado `uc↔u_c` con caso + universo matemático sin prosa | Fidelidad de variables (Fase 0); routing solo con señal simbólica real (B06) | Keyword plano (pierde `u_c`) / routing ciego (castiga texto) | alta |
| D25 | Matching con límite de palabra + stems conservadores + prefijo ≥6 | `units⊂unitats` era FP; `distribucions↔distribució` y `compensar↔compensació` son FN sin esto | Substring (FP) / exacto puro (FN) | media-alta |
| D26 | Abstención por OOV + masa IDF absoluta (no minmax) | Minmax oculta debilidad (Champions puntuaba 1.15); lo desconocido debe restar | Threshold sobre score relativo (no abstiene nunca) | alta |
| D27 | Tokens directivos (`Tema N`) filtran, no puntúan | Envenenaban masa y provocaban abstención indebida (I06) | Tratarlos como contenido | alta |
| D28 | Degradación PDF x0.5 por near-dup, sin fusión | Fase 0/D4: la corroboración no suma confianza 2X | Duplicar evidencia / excluir PDF | alta |
| D29 | Benchmark 58 golds con grounding verificado + split dev/test | §69: el benchmark mide, no justifica; test intacto hasta el final | Golds inventados / tuning sobre test | alta |

## Fase 3 (`reasoning-3.0`, prompts v1→v2, Gemini 3.5-flash-lite)

| # | Decisión | Motivo | Alternativas descartadas | Confianza |
|---|---|---|---|---|
| D30 | Gemini real por REST-stdlib + fallback extractivo declarado | Había clave e internet; sin clave el sistema sigue útil sin fingir (select_provider) | Solo-mocks (prohibido §74) / acoplar SDK | alta |
| D31 | Cobertura por canales generales (lookup/sección/substring), nunca por query | §2 prohíbe excepciones; 52,5 %→100 % sin un solo `if query==` | Hardcodear fórmulas (prohibido) / bajar el gate | alta |
| D32 | Validador estricto (reescritura = MISMATCH) + prompt v2 versionado | RF03-live reescribió coeficientes; la laxitud aquí es alucinación | Aceptar equivalencias laxas | alta |
| D33 | Degradación a extractivo verificado (JSON roto / 2 rondas) con aviso | Tutor útil > error seco; procedencia declara el fallback | Abstenerse teniéndo evidencia / reintentar infinito | media-alta |
| D34 | Overrides adversariales → ABSTAIN antes del retrieval | §53-54 exigen rechazo; patrones generales ES/CA, no queries | Dejarlo al prompt (frágil) | alta |
| D35 | RU01/RP01-extractive como gaps documentados, no como tuning | El fallback copia chunks; componer es tarea generativa (16/16 live lo prueba) | Forzar gold / inflar extractive | alta |
| D36 | Variables/unidades por fórmula parciales y declaradas (205/2896) | Sin evidencia local no se inventan (regla 4); Fase 4 las completa | Rellenar con conocimiento externo | alta |

## Fase 4 (`examiner-4.0`)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D37 | Determinista primero, LLM solo abiertos con `--llm` | Reproducibilidad + coste 0 + verificación idéntica; el LLM no aporta seguridad extra | Todo-LLM (coste, varianza) | Benchmark 38/38 determinista |
| D38 | Topic-filter en toda evidencia del examiner | Preguntas single-topic; el caso T9-para-T2 es inválido | Evidencia global (fugas temáticas) | Coherencia exigible por test |
| D39 | Cita de formula_id no basta: el latex debe coincidir | `$U=u_c/k$` citando `eq-02-0034` debe ser CONTRADICTED | Confiar en la cita (falso soporte) | Validador más estricto (F3 intacta) |
| D40 | Fórmulas degeneradas (`_{}`, `$)$`) bloqueadas con motivo | No son evaluables; ocultarlas sería peor | Forzar cobertura o borrarlas de KB | 99.69 % examable, 100 % recuperable |
| D41 | Metadata ausente = UNKNOWN/`UNIT_VALIDATION_UNAVAILABLE`, nunca PASSED | §16/§20: no inventar variables/unidades | Rellenar con LLM | Deuda medida (Fase 5) |
| D42 | `eval.sqlite` ciego por construcción + doble test | §42-43/§77: el banco V/F no debe filtrarse a preguntas | Confiar en no usarlo | Test de cadena + funcional |
| D43 | Live informativo, determinista como gate | El modelo varía entre ejecuciones; el invariante es 0 fugas | Gate sobre live (frágil) | 38/38 + live auditado |
| D44 | Rechazar es correcto ( blueprint/validator rechazan, no degradan) | §66: mejor NO_GENERATION que pregunta débil | Generar siempre algo | 10/10 adversarial rechazado |

## Fase 5 (`grader-5.0`, `rubric-5.0`, `mastery-policy-v1`, prompts assist v1)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D45 | CORRECT alcanzable (required 1.0 + resto ≥0.5) en vez de exigir todo 1.0 | 0.5 significa "sin contraevidencia"; si no, nada determinista llega a CORRECT | Todo-1.0 (CORRECT imposible) / todo-vale | Perfectas llegan a 9.0 |
| D46 | Cita de fórmula no basta: latex debe coincidir | `$U=u_c/k$` citando el id correcto debe ser CONTRADICTED | Confiar en la cita | Validador más estricto (F3 compatible) |
| D47 | Patrón `amb X` eliminado de curación | Falsos positivos masivos (conjunción catalana) | Mantenerlo (468 CONFIRMED falsos) | 83 CONFIRMED reales |
| D48 | LLM assist solo confirma o pide REVIEW (nunca decide nota) | §19/§74: la nota sale de rúbrica+verificación | LLM puntúa (prohibido) | 0 overrides medidos |
| D49 | Benchmarks con nonce por ejecución; idempotencia en test aparte | IDs fijos rejuegan historia tras un fix | Rejugar (falsos fallos) / borrar historia | Métricas limpias + invariante probado |
| D50 | Perfil cuenta TODO; raíces solo causales | §58 pide perfil completo, §59 causalidad | Solo raíces (perfil vacío) | AT_RISK + error_profile coherentes |
| D51 | UNKNOWN ≠ WRONG en variables/unidades/metadata | §21/§33/§35: sin evidencia no se penaliza | Penalizar (injusto) / inventar (prohibido) | NEEDS_REVIEW y UNAVAILABLE honestos |
| D52 | Recencia ponderada sin borrar historial | §54: documentada, eventos intactos, replay exacto | Decay destructivo / sin recencia | Trazabilidad total |

## Fase 6 PASO 2 (contratos pre-adaptativos, sin motor)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D53 | `origin` en Question (default GENERATED) + columnas por migración | Trazar procedencia sin reescribir filas existentes | Nueva tabla (duplica) | REAL_EXAM importable a futuro |
| D54 | Fingerprint sin `origin` (identidad de contenido) | Un duplicado exacto no aporta dos veces; evita reinsertar el pool | Incluir origin (reinserta todo) | Dedupe estable |
| D55 | `exams.kind/source` con validación estricta | Contrato REAL_EXAM sin importador todavía | Esperar al importador (bloquea diseño) | Roundtrip probado |
| D56 | `Policy` frozen + registro; mastery lee sus parámetros | Una sola fuente de verdad sin cambiar comportamiento | Duplicar constantes (deriva) | Mismo comportamiento, testeado |
| D57 | Políticas difficulty/spacing `reserved` sin algoritmo | §GAP2 pide contrato, no motor; parámetros vacíos honestos | Inventar parámetros (falso) | registry + serialización probadas |
| D58 | Desempate `(score, -attempt_count, knowledge_unit_id)` | Orden total sin tocar la lógica de debilidad | Cambiar pesos (prohibido) | Empate exacto determinista (test) |
| D59 | `skill` fuera del contrato efectivo (opción B) | Ningún productor lo emite; sin taxonomía no hay grafo | Inventar skills (prohibido) | `Skill graph → FUTURO` documentado |
| D60 | Loop futuro sobre corrección determinista (`llm_assist=False`) | El assist solo confirma/pide review; la nota es reproducible | LLM en el loop (varianza en mastery) | Test con provider que falla incluido |

## Fase 6 Bloque A (adaptive core determinista, sin LLM)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D61 | `difficulty-policy-v1` `reserved`→`active` + `test_09` al nuevo contrato | El selector la consume de verdad; `reserved` mentiría el estado | Mantener `reserved` (contrato falso) / revertir policy (romper Bloque A) | Suite en verde con el contrato real |
| D62 | Supresión de padres independiente del orden (hoja siempre gana el pick) | §10: mismos intentos → una carencia; el padre viaja en `reasons`, no como pick | Solo-suprimir-hacia-adelante (duplicaba padre-antes-que-hoja) | Ruta sin doble-conteo, orden global preservado |
| D63 | Exploración v1 solo fórmulas | `equation_id` estable y reencontrable por el loop de mastery; términos libres de concepto no lo garantizan | Explorar conceptos KB (IDs que el loop quizá nunca actualiza) | 1 slot honesto con score real del calculador |
| D64 | `to_spec()` abstiene sin tema en vez de inferirlo | Concepto sin eventos no tiene tema trazable; inferirlo sería invención | Heurística de texto (falso soporte) | `ValueError` explícito, testeado |
| D65 | Benchmark como jsonl ejecutable (runner + pytest, una fuente) | Expectativas calculadas a mano y confirmadas (40.0/53.0/41.5…); el gold no puede mentir | Runner solo-imprime / tests solo-estructurales | 20/20 + 14 invariantes, artefacto comprometido |
| D66 | TUNABLEs sin calibrar (`unknown`), sin auto-tuning | Sin datos docentes, cualquier ajuste sería deriva silenciosa (R6) | Calibrar a ojo (falsa precisión) | Deuda declarada en PHASE_6_ADAPTIVE_CORE |

## Fase 6 Bloque B (loop cerrado determinista, sin LLM)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D67 | `spacing-policy-v1` `reserved`→`active` + `test_10` al nuevo contrato | Buckets + criticidad + umbral categoría implementados de verdad | Mantener `reserved` (contrato falso) | Suite en verde, parámetros versionados |
| D68 | Spacing derivado, cero persistencia nueva | §3: todo lo exigible ya existe en mastery+eventos | Nueva tabla spacing (duplicación) | Sin migraciones, veredicto auditable |
| D69 | DEFER solo correcto-reciente-no-crítico; fallo fresco siempre ALLOW | §9: 3×0 nunca desaparece; el fallo de hoy manda sobre el acierto de ayer | Diferir por recencia bruta (oculta debilidades) | L04/L08/L18 lo prueban |
| D70 | Backfill unificado (críticas + ALLOW hasta `limit`, padres cubiertos no) | Path truncado no debe amputar debilidades; §11 intacto | Solo-path (amputa) / resucitar padres (duplica) | L12 lo prueba |
| D71 | Fallback `inclusion_sin_alternativa` si todo es DEFER | El tutor recomienda algo siempre, y lo declara en reasons | Lista vacía (tutor mudo) / reordenar en silencio | Trazabilidad total |
| D72 | `last_correct` F5 documentado, no reparado | Congelado y testeado; el efecto en spacing es seguro (ALLOW) | Tocar `_update_mastery` (riesgo F5) | Límite en PHASE_6_ADAPTIVE_LOOP |
| D73 | Submits del benchmark sobre copia de GENDB + guardia anti-escritura | Una ejecución contaminó GENDB con 3 filas (revertido y verificado) | Escribir directo (reincidencia) | Test de aislamiento + guardia en runner |
| D74 | Cross-process byte-idéntico (detalles sin timestamps) | §25 si viable: lo es excluyendo `now` crudos de los detalles | Solo in-process (débil) | Test con `--out` doble |

## Auditoría de cierre Fase 6 (2026-09-05, 14/14)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D75 | Fallbacks silenciosos → indexación directa (KeyError ruidoso) | `.get(exploration_epsilon, 0.125)`, `.get(sev, 0.6)` y `.get(err, MODERATE)` duplicaban constantes fuera de policy | Mantener defaults (constantes ocultas) | Entrada corrupta falla en voz alta; 114 en verde |
| D76 | Guardia anti-escritura GENDB + 2 tests permanentes | Un benchmark escribió 3 filas `qm-*` en la DB real (revertido) | Confiar en la disciplina (reincidencia) | `RuntimeError` + test de filas sintéticas |
| D77 | Límites de `replay`/`last_correct` documentados, F5 intacto | `replay` no devuelve `last_correct`/`error_counts`; submit no-correct vacía `last_correct` | Tocar `_update_mastery`/`replay` (riesgo F5) | PHASE_6_AUDIT los declara; spacing robusto a ambos |

## Fase 7 Bloque 1 (preauditoría y diseño, sin código)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D78 | Snapshot por referencia (ids+fingerprint re-verificado) | `put()` nunca sobrescribe: las preguntas ya son content-addressed | Duplicar bodies (deriva) | `READY` congela sin copiar |
| D79 | `PAUSED` fuera de v1; `duration` null=sin límite, 0=inválido; restante 0→`EXPIRED` | El dominio no exige pausa; timer por timestamps de servidor | Pausa con ajuste silencioso (irreproducible) | Máquina de estados mínima |
| D80 | Nota final half-up sobre milésimas enteras | `round` flotante es ambiguo entre plataformas | Float directo (deriva) / banker's implícito | `scoring-policy-v1` reproducible |
| D81 | `Correction.exam_id/session_id` aditivo (default `""`) | Provenance respondible sin joins en caliente | Solo-join (frágil) / reescribir F5 (riesgo) | Compatible con F5 |
| D82 | Conceptos solo exigibles en tipos que pueblan `concept_terms` | TF/FORMULA/NUMERICAL llevan `[]`; exigirlo sería blueprint imposible | Inventar cobertura (falso) | Invalidez honesta con shortfall |
| D83 | `NEEDS_REVIEW` → `PENDING_REVIEW` + provisional marcado | 0 silencioso falsearía la nota | Forzar nota (injusto) | `regrade` F5 cierra el ciclo |
| D84 | `REAL_EXAM` alimenta evidencia pero cero señal adaptativa/KB | La señal no existe y la KB es inmutable | Ponderar origen (contaminación) | Aislamiento intacto |
| D85 | `sessions.sqlite` en `data/exams/` separada | Cinco capas, cinco escritores (§2) | Tabla en student DB (mezcla) | Aislamiento por fichero |
| D86 | Orden `seeded_shuffle`\|`blueprint_order` | Mismo patrón `rng` heredado, dos necesidades reales | Orden de pool (filesystem) | Reproducibilidad total |
| D87 | Vistas `STEM_VIEW`/`REVIEW_VIEW` por estado+rol | El body completo contiene soluciones | Una sola vista (fuga) | Anti-fuga por construcción |

## Fase 7 Bloque 2 (session core persistente, sin grading)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D88 | Sesiones en student.sqlite canónica (D85 superada) | El brief B2 prohíbe tercera DB y fija la canónica | `sessions.sqlite` separada (B1) | 6 tablas aditivas, cero migraciones |
| D89 | `assemble_exam` extendido aditivamente, no duplicado | Filtros nuevos con defaults que preservan comportamiento | Selector paralelo (duplicación) | 43 tests examiner intactos |
| D90 | Claves `sections` a int en `from_dict` | JSON entrega claves str y vaciaba el pool en silencio | Confiar en el llamante (shortfall falso) | Bug real cazado por E19 |
| D91 | Expiry con commit antes de rechazar | Sin commit, el EXPIRED se perdía en rollback | Rechazar sin persistir (inconsistencia) | E08 lo prueba |
| D92 | `sum(types)==count` exigido en validación | Capado silencioso falsearía cuotas | Aceptar y capar (ambiguo) | Blueprint contradictorio inválido |
| D93 | Sin corrección ni attempts en este bloque | Guardar ≠ corregir (§34); F5 intacto | Tocar F5 ya (innecesario) | `Correction.exam_id` queda para grading |
| D94 | `prepare_session` idempotente, `start` no | Re-preparar es inocuo; re-iniciar movería el reloj | Todo-estricto (frágil) | Semántica documentada |
| D95 | GENDB: gate de aislamiento a nivel contenido, no byte-hash | `put_exam` (F4, `INSERT OR REPLACE`) reescribe bytes idénticos en cada suite; el hash cambia sin cambio lógico (demostrado con `test_exam_roundtrip_store`) | Fijar bytes (tocar F4, fuera de alcance) | 76 preguntas/6 exams/0 sintéticas; tests de contenido vigentes |

## Fase 7 Bloque 3 (grading + scoring + resultado)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D96 | `attempt_id = attex-sha(sesion\|pos\|qid\|answer)` (no F5) | Re-grade rejuega, otra sesión no colisiona; misma forma `att-`+12 | Derivación F5 (colisión entre sesiones) | Idempotencia triple probada |
| D97 | Fallo inesperado → `GRADING_INCOMPLETE` + limpieza + reintento | Sin artefactos parciales; la evidencia F5 válida persiste y se deduplica | Estado intermedio persistido (ambiguo) | Test con inyección + resume |
| D98 | `GRADED` exige `COMPLETE`; `INCOMPLETE` queda `SUBMITTED` | §34: GRADED no puede significar dos cosas | Graduar igual (falso completo) | `PENDING` honesto vía `INCOMPLETE` |
| D99 | Grade desde `EXPIRED` → `GRADED` con `origin_status` | Calificar no es continuar; el origen preserva la distinción | Congelar en EXPIRED (resultado huérfano) | Trazabilidad completa |
| D100 | `required=False` sin regla = blueprint inválido | §16 prohíbe inventar penalizaciones | Regla inventada (falsa) | Porcentaje siempre sobre required |
| D101 | `Decimal` + HALF_UP entero; `round()` prohibido en scoring | `round(2.675,2)==2.67` flotante | Float (deriva de plataforma) | Test 2.675 + empates G19 |
| D102 | `test_21` flake temporal preexistente: NO se toca | Misma secuencia con `attempt_id` distintos + empates de segundo + desempate por hash de `event_id` = scores distintos según carga (0.697 vs 0.6667); 10/10 aislado, mecanismo caracterizado | Tocar F5/test (fuera de alcance, semántica de replay intacta) | Registrado; B3 no afecta la ruta |

## Fase 7 Bloque 4 (preaudit review, sin código)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D103 | `prompt` DENY pre-`IN_PROGRESS`, ALLOW solo vía `get_question` | §5 lo lista en denegados pero es el cuerpo de STEM | ALLOW siempre (fuga pre-start) / DENY siempre (examen vacío) | Matriz §8 explícita |
| D104 | `REVIEW` solo `GRADED`+`COMPLETE`; `INCOMPLETE`→`REVIEW_NOT_AVAILABLE` | Lo correcto se desconoce en items NEEDS_REVIEW | Mostrar parcial (falsedad) | Sin revisión engañosa |
| D105 | Presentación raíz+consecuencias vía `PROPAGATION` | Lista plana de 5 errores miente causalidad | Todo visible (ruido) / solo raíz (pierde info) | Feedback honesto |
| D106 | Severidad como banda humana; `CRITICAL`/código internos | `CRITICAL` sin asignación real; el código asusta sin enseñar | Raw visible (ruido) | Informativa, no decide |
| D107 | `review-policy-v1` futura con 8 flags + defaults | Solución/respuesta/fuente dependen de contexto (REAL_EXAM ciego) | Todo visible (fuga) / todo oculto (inútil) | Versionada desde el día 1 |
| D108 | Sin store de review (derivada, policy citada por llamante) | Todo es computable de correction+KB+policies | Cache propia (invalidez) | Cero surface de mutación |
| D109 | Origen EXAM derivado (`attex-`+body), sin campo nuevo | No tocar F5/F6 por un label | `origin` en evento (migración) | Provenance suficiente |
| D110 | Multilingüe por diccionarios fijos, invariantes byte | MT/LLM traduciría fórmulas y números | Traductor externo (riesgo) | Test ca/es de literales |
| D111 | `MASTERY_VIEW` pedagógica sí necesaria (cuarta vista) | Estado crudo expone confianza e ids internos | Reutilizar estado (fuga) | Banda+motivo+exámenes |
| D112 | LLM explicador OFF por defecto, jamás decide/persiste | Determinista cubre el base; el resto es riesgo | LLM primero (T14) | Boundary con 8 reglas |

## Fase 7 Bloque 5 (review implementada, sin LLM)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D113 | Policy en código frozen, cero tablas | Un solo objeto + registro bastan para v1 | Tabla policies (innecesaria) | §67 cumplido |
| D114 | Legacy B2/B3 intacto + test de consistencia con la tabla | Mensajes congelados por tests; refactor = riesgo | Reescribir puertas (churn) | Autoridad única verificada |
| D115 | `provider/model` solo si el assist actúa (`""` = determinista) | Registrar siempre mentiría; raw jamás persiste | Siempre registrar (falso) / nunca (gap P0) | P0 provenance cerrado |
| D116 | Prompt+opciones texto en review post-`GRADED` | Sin enunciado la review descontextualiza; ya visto en examen | Sin prompt (inútil) | Pedagógico y seguro |
| D117 | Raíces huerfanas como principales, derivados colapsados | TF/numéricos reales no tienen raíz y son la evidencia | Ocultar derivados (pérdida) | Presentación honesta |
| D118 | `INCOMPLETE`/sin-fila → `REVIEW_NOT_AVAILABLE`, nunca parcial | Lo correcto se desconoce | Mostrar parcial (falsedad) | D104 implementada |
| D119 | i18n: solo literales cambian; latex/números/refs byte-idénticos | Traducir lo demás corrompe | MT (riesgo) | Test ca/es |
| D120 | Origen EXAM = `attex-`+body, sin campo/migración | Suficiente y determinista | `origin` en evento (F5 touch) | D109 implementada |
| D121 | `MASTERY_VIEW` exige sesión `GRADED`; lecturas F5 intactas | Resumen con contexto, no estado suelto | Vista global (fuga) | Read-only probado |
| D122 | `REAL_EXAM` ciega correct/solution/latex, resto visible | Score/errores no comprometen futuros reales | Todo ciego (inútil) / todo visible (fuga) | Defaults versionados |

## Fase 7 Bloque 6 (preaudit final, sin código)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D123 | GO con 0 P0 / 0 P1 / 9 P2 | Todo P0 verificado contra código; P2 sin efecto en gates | Exigir P2 cero (cosmético) | F7 cerrada |
| D124 | Suite ×2 con 0 diffs como evidencia §49 | 36 claves (hashes, censos, artefactos) idénticas | Una pasada (débil) | Contaminación descartada |
| D125 | `_is_orphan` duplicada idéntica: documentar, no tocar | B6 no implementa; inocua (última gana, mismo cuerpo) | Fix furtivo (viola regla) | P2 registrada |
| D126 | Deuda doc B1/B2/B3 registrada aquí, no editada | Solo 2 ficheros editables en B6 | Tocar 3 docs (viola §54) | P2 trazable |
| D127 | Concurrencia RISK/P2 sin llamantes concurrentes | Sin capa web no hay carreras reales | Locks (innecesario) | Supuesto single-writer explícito |
| D128 | Naive→UTC y exam_id-F4-ciego-a-quotas como P2 | Sin llamantes afectados hoy | Cambiarlo (churn) | Asunciones documentadas |

## Fase 8 (auditoría final y certificación)

Hallazgos transversales de la auditoría B1–B19 (previos al veredicto):

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D129 | P1 I03: re-baseline del artefacto, no del código | Conducta actual correcta+determinista; artefacto stale F3; revertir sería tunear al artefacto | Revertir ranking (tuneo) / dejar stale (falso fallo) | `formula_recall@5` 0.857 honesto |
| D130 | `correction_results` 11->24 y examiner live aceptados como baseline | Bancos/specs crecieron; 24/24 + live informativo con rechazos por diseño | Congelar artefactos viejos (falso) | Baselines reales |
| D131 | LIVE Gemini ejecutable de nuevo: set 20 adversarial | Red disponible + key válida; gate exigía evidencia, no suposición | Declarar sin evidencia (prohibido §110) | 0 alucinaciones medidas |
| D132 | GENDB 76->89 por vías validadas = diseñado, no contaminación | Solo VALID+GENERATED con fingerprint (live-audit F4) | Congelar conteo (falso gate) | Censo de contenido vigente |
| D133 | Sin fixes de código en F8 salvo re-baselines justificados | Cero P0; único P1 era artefacto | Refactor (prohibido §2) | `git diff` funcional vacío |
| D134 | CERTIFIED con 0 P0 / 0 P1 pendientes / P2 acotados | Todos los gates §106 en verde simultáneo | CONDITIONAL (innecesario) | Fin de certificación |
| D135 | `correction_benchmark` escribe `bench-*` en student DB canónica: P2 higiene, sin fix | Namespaced por alumno, sin efecto en corrección; solo el benchmark lo hace | Migrar a tmp (cambia comportamiento medido) | Documentado, fuera de P0/P1 |
| D136 | Veredicto final CERTIFIED (B20) | Ver `docs/PHASE_8_FINAL_CERTIFICATION.md` §28 | — | DETENTE |

## Fase 9 (operational readiness)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D137 | P0=0/P1=0 en preaudit: cero implementación | Nada bloquea ni degrada; observabilidad solo diseñada | Implementar por Completitud (riesgo) | Diff funcional vacío |
| D138 | Concurrencia P2 con evidencia empírica | Threads: 8/8, 1+5 replayed, doble todo consistente | Subir a P1 sin llamantes (ruido) | Supuesto documentado |
| D139 | Re-baselines F9 (5 artefactos + GENDB + student) aceptados | Causas identificadas una a una, contenido verificado | Congelar (falso) | Trazabilidad total |
| D140 | OPERATIONALLY READY (20 gates) | P0/P1 cero + evidencia simultánea | CONDITIONAL (innecesario) | Fin de fase |

## Fase 10 Bloque B2 (diseño application layer)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D141 | Sin clase base de workflow; convención `(ctx,…)` + `AppError` | Base común añade complejidad sin valor | Jerarquía start/step/complete | Workflows explícitos |
| D142 | `ApplicationSession` efímera, sin tabla | Estado durable ya en F5/F7 | Persistir sesión (duplicación) | Serializa el caller |
| D143 | `attempt_id` derivado `app-<session>-<n>` en Practice | Idempotencia sin colisiones con F5/F7 | Reutilizar attex (mezcla dominios) | Trazabilidad por prefijo |
| D144 | Fachada Exam 1:1 sobre F7, sin lógica | Cualquier desviación rompería máquina/scoring | Envolver con atajos | F7 intacto |
| D145 | Mapeo de errores explícito, resto propaga | `except Exception` como flujo oculta P0 | Normalizar todo | Fail-loud |

## Fase 10 Bloque B4 (NO-GO por P1 verificado)

| # | Decisión | Motivo | Alternativas | Consecuencia |
|---|---|---|---|---|
| D146 | B4 NO-GO: `IndexError` en `generate(NUMERICAL)` sin fórmula (F4) | Ruta certificada concepto+REINFORCE+raíz→NUMERICAL vacío; F6 `step` también expone traceback; viola contrato de rechazo | Degradar a P2 para forzar GO (prohibido) / parchear F4 aquí (viola STOP) | STOP; fix de 3 líneas + test en bloque específico futuro |
| D147 | B4 GO tras FIX: guarda `_gen_numerical` + benchmark 54/54 x2 + regresion 712 | FIX verificado (rechazo limpio + `rejected` en loop); workflows exam/review testeados; benchmark scriptado verde dos pasadas; 0 P0/P1; GENDB/KB/eval intactas (hash verificado) | Reabrir debate TF-8.5/COMPLETE (conducta F certificada, fuera de alcance) | B4 cerrado; ver `docs/PHASE_10_WORKFLOWS.md` |
| D148 | B5 GO: integracion verificada sin tocar codigo certificado | Preaudit P0/P1 cero; benchmark 76/76 x2 (incl. 2 subprocesos reales + proveedor roto + REAL_EXAM ciego); 15 tests nuevos; regresion 727; formula 2896/2896; GENDB/KB/eval intactas | Endurecer F4 (prohibido por regla especial P2) / B6 automatico (prohibido: STOP) | B5 cerrado; ver `docs/PHASE_10_B5.md` |
| D149 | P0 grade concurrente (F7): el perdedor borra filas COMMITTED del ganador | Repro 4/4 (2 y 4 hilos) + CC02 rojo x2; mecanismo en `_cleanup_partial` incondicional; GRADED+0 filas irrecuperable con SUCCESS devuelto | Degradar a P1/P2 (niega state-corruption) / parchear F7 aqui (viola STOP) | NO-GO; fix en bloque F7 + re-gates |
| D150 | F10 NOT CERTIFIED (condicional, solo bloquea P0-1) | Todo F10 en verde: 150 tests, 119/120 x2, 2896/2896, 10/10 IDOR, blind 2 rutas, aislamiento 7/7 | Certificar con P0 abierto (prohibido) | Ver docs/PHASE_10_CERTIFICATION.md; F11 bloqueado; STOP |
| D151 | F7 P0-1 CLOSED: claim serializado + cleanup propio en grading | BEGIN IMMEDIATE + adopcion de ganador + INSERT OR IGNORE + cleanup con guarda; 10 tests (hilos y procesos); 120/120 x2; 738 regression; resto intacto | Lock Python (no sobrevive a procesos) / borrar cleanup (rompe GRADING_INCOMPLETE) | Ver docs/PHASE_7_P0_1_FIX.md; siguiente: F10-B6 RE-GATE; STOP |
| D152 | F10 CERTIFIED tras re-gate (P0-1 F7 cerrado y verificado) | 120/120 x2, 738+156 en verde, 2896/2896, 7/7 aislamiento, P0/P1 cero; 2 live excluidos por politica de entorno | Certificar con P0 abierto (ya no existe) | F11 UNBLOCKED; STOP |
| D153 | F11-B0 GO: preauditoria UI/UX sin implementacion | 0 ficheros HTML/CSS/JS/frameworks: solo 3 CLIs + app/application certificada; journeys/IA/gaps B/C/D separados; F0-F10 intactos (150 tests + hashes) | Implementar UI en B0 (prohibido) | NEXT F11-B1 Design System/App Shell; STOP |
| D154 | F11-B1 GO: Design System + App Shell desde cero | HTML estatico + CSS/JS vanilla, 0 deps; 26 primitivas, dark completo, shell responsive a11y; 17 tests; 52 KB; F0-F10 intactas | Framework/Flask (peso injustificado) | NEXT F11-B2; STOP |
| D155 | F11-B2 GO: Study/Tutor/Practice funcionales | Bridge stdlib (13 endpoints) + renderer LaTeX whitelist + 4 paginas/3 JS; threads por-hilo tras hallar retriever compartido; 48 tests web; 786 regression; F0-F10 intactas | Flask/deps pesadas (injustificadas) | NEXT F11-B3; STOP |
| D156 | F11-B3 GO: Adaptive/Mastery UX | 5 endpoints learn + pagina Learning + loop F6 integro (item round-trip); 59 tests web; 797 regression; F0-F10 intactas | Mostrar priority_score/thresholds (duplicaria dominio) | NEXT F11-B4; STOP |
| D157 | F11-B4 UI consume proyecciones persistentes de F10/F7 | La metadata en memoria por hilo rompía refresh/reentrada y el probing de preguntas divergía del snapshot | Mantener meta efímera / inferir conteo desde errores | Snapshot y metadata seguras; sin lógica de dominio en JS |
| D158 | F11-B4 NO-GO tras benchmark determinista 91/100 x2 | Persisten fallos contractuales de MULTI_STEP, grading/review/blind y un código de error; además 2 live tests tienen 401 | Parchear F7/F10 desde UX (prohibido) | STOP; resolver contratos previos y re-gatear |
| D159 | F11-B4-FIX GO condicionado a regresión completa | La fuga REAL_EXAM era de presentation adapter; los demás fallos eran expectativas stale o abstención contractual de F4/F7 | Modificar scoring/generación (fuera de alcance) | Whitelist HTTP, benchmark 100/100 x2, sin cambios de dominio |
| D160 | F11-B5 History es una proyección read-only de sesiones/resultados F7 | F7 ya persiste fechas, estados y resultados; una tabla nueva duplicaría el dominio y rompería idempotencia | Persistir eventos de UI / ampliar SQLite desde web | DTO de historial en F10, ownership delegado a F7 |
| D161 | Results HTTP usa whitelist y Review/History tienen entradas directas | El navegador necesita navegación reentrable, pero no debe recibir IDs de corrección ni campos internos | Pasar payloads completos / estado JS compartido | Refresh seguro, semántica de errores preservada |
| D162 | B6 conserva 125 casos del benchmark | La distribución explícita del prompt suma 125 aunque el objetivo textual diga 120 | Eliminar cinco casos para forzar 120/120 | `125/125 ×2`; P2 documental trazable |
| D163 | F11 Product Experience CERTIFIED | Todos los checks de integración pasan; los únicos fallos son Gemini 401 externos | Certificar ignorando evidencia / reabrir F0–F10 | STOP; siguiente trabajo fuera de F11 |
| D164 | Fix B6: eliminar `catch` desparejado de Practice | `node --check` demostraba que `practice.js` no podía cargar; el test estático previo no cubría sintaxis | Ignorar porque pytest Python estaba verde | Practice vuelve a cargar; regresión Node añadida |
| D165 | F13 empieza con Documents read-only y contrato Calendar vacío | La KB ya contiene documentos reales; no existe una fuente académica de horarios y fabricar eventos violaría la política de abstención | Crear datos ficticios / introducir persistencia de calendario antes de resolver identidad | Vertical útil y honesto; importador + eventos quedan para el siguiente bloque |
| D166 | CalendarSource acepta solo JSON `version: 1` con trazabilidad obligatoria | Un calendario sin `source_path`/`source_hash` no es auditable; ordenar por inicio+id fija el resultado | Aceptar payload libre / ordenar en frontend | Importación local determinista; eventos inválidos fallan con `VALIDATION_ERROR` |
| D167 | Documents conserva `doc_id` hasta la pantalla de seccions | El catálogo podía abrir solo el tema y perder la intención del usuario | Inferir el documento en frontend / cargar todo el tema | Navegación reentrable documento → secció → contingut |
| D168 | Packaging inicial con setuptools y CLI stdlib | El proyecto no necesita dependencias runtime nuevas; un único entry point cubre desarrollo y distribución local | Framework de despliegue / contenedor prematuro | `pyproject.toml` portable; instalador y despliegue quedan para F14 posterior |

## Operación local (F14 ampliada)

| # | Decisión | Motivo | Alternativas descartadas |
|---|---|---|---|
| D169 | Mono-usuario local: `SM_STUDENT` desde `.env`, sin perfiles/auth/aislamiento | El objetivo es una persona en una máquina | Perfiles honor-system (F12 original) / cuentas con contraseña / aislamiento por directorio |
| D170 | `ThreadingHTTPServer` stdlib se mantiene; sin WSGI/ASGI, reverse proxy ni HTTPS gestionado | YAGNI para localhost mono-usuario; charter de cero dependencias | gunicorn/uvicorn/waitress + nginx |
| D171 | Migraciones forward-only con `user_version`; sin down-migrations | Rollback = restore desde backup; las down-migrations son código muerto casi siempre | Herramienta de migración con dependencia externa |
| D172 | Artefactos `data/` en el zip portable, no en el wheel | Un wheel con decenas de MB de SQLite es un antipatrón; el zip ya los lleva | `package-data` en el wheel |
| D173 | La CLI delega; no reimplementa `serve`/`ingest` | Menor superficie; `web.server.main` y `app.ingest.main` ya están probados | Reescribir la lógica en `app/cli.py` |
| D174 | `ingest` es comando de mantenedor (exige `--source`/`--out`) | La fuente vive fuera del paquete y los artefactos empaquetados son inmutables | `ingest` para usuario final (escribiría en `site-packages`) |
| D175 | CSRF se mantiene pese a ser mono-usuario; expiración y persistencia de sesión se descartan | Cualquier página del navegador puede hacer `POST` a `localhost:PORT`; la expiración no aporta con un solo usuario local | Quitar CSRF (deja la web local abierta a CSRF) / sesión persistente con expiración (sin valor aquí) |
| D176 | Versión oficial `1.0.0`, punto único en `pyproject.toml` | F0–F13 certificadas; `package.ps1` duplicaba `0.13.0` | Mantener `0.x` / versión en fichero aparte |
| D177 | Un solo formato de configuración: `.env`, con lookup extra en el config dir | Coherencia; `tomllib` añadiría un segundo formato | `config.toml` |
| D178 | `serve` corre `check --fast` al arrancar y aborta si falla | Un KB corrupto da respuestas silenciosamente malas; mejor fallo ruidoso | Arrancar siempre y confiar en `check` manual |
