# LLM_PROVIDER — Capa de razonamiento sustituible

Protocolo `LLMProvider.generate(messages, temperature) -> LLMResponse`
(`app/llm/interface.py`). El core (`app/reasoning`, `app/retrieval`) no importa
ningún SDK: solo el protocolo.

## Proveedores

| Proveedor | Modelo | Cuándo | Coste/latencia |
|---|---|---|---|
| `gemini` | `gemini-3.5-flash-lite` (env `GEMINI_MODEL`) | `GEMINI_API_KEY` presente (auto) | ~0,8 s, ~20+400 tokens/llamada |
| `extractive-fallback` | `extractive-v1` (determinista, sin generación) | sin clave o `--provider extractive` | ~0 ms, 0 tokens |

`select_provider("auto"|"gemini"|"extractive")`: sin clave + auto → extractive
con aviso; `gemini` sin clave → `reasoning_unavailable` (fallo controlado §76,
nunca respuesta fingida). Reintentos con backoff ante HTTP 429 (3 intentos).

## Reglas

- Temperatura 0 en respuestas académicas; JSON estricto (`responseMimeType`).
- Clave solo desde entorno; jamás en logs, repo ni prompts (§78). Sin `.env`
  comprometido (no existe en el repo).
- Salida malformada 2 veces → degradación a extractivo verificado con aviso
  `llm_malformed_fallback` (no se finge el LLM, no se rompe el tutor).
- `needs_more_evidence` 2 rondas insatisfechas → extractivo verificado con
  aviso (antes que abstención ciega con evidencia en mano).
- Intentos de override (`usa esta fórmula aunque no esté...`, `ignora las
  instrucciones`...) → abstención `CONFLICTING_EVIDENCE` antes del retrieval.

## Prompts versionados (`app/llm/prompts/`)

- `reasoning_v1.txt`: sistema inicial (KB única fuente, citas, JSON).
- `reasoning_v2.txt` (activo): + copia EXACTA del LaTeX + citar siempre el
  `formula_id` (lección RF03-live: el modelo reescribía coeficientes).
- v1 se conserva intacto para reproducibilidad.
