# RETRIEVAL_ARCHITECTURE — Motor de evidencia académica (Fase 2)

```
query
 ↓ normalization (conservadora: preserva u/uc/σ/Ω/Hz/dB; stopwords funcionales + es→ca)
 ↓ classification (13 tipos deterministas + fallback GENERAL) + topic mention
 ↓ candidate generation: lexical FTS5 (60) + TF-IDF coseno (60) + fórmulas (20)
 ↓ fusion RRF (k=60: sin calibrar escalas dispares)
 ↓ ranking con componentes explicados (sin magic scores)
 ↓ reranking determinista (corroboración PDF x0,5 si near-dup ≥0,8)
 ↓ context expansion (padre + vecinos + fórmulas + visuales + tabla)
 ↓ abstention (unknown_topic/terms, masa IDF, margen, score mínimo)
 ↓ EvidencePack {primary(3) + supporting + formulas + concepts + units + visuals + sources}
```

## Componentes del ranking (`final`, todos en [0,1] salvo penalizaciones)

`0.45·lexical + 0.30·semantic + 0.35·formula + 0.25·phrase + 0.20·topic
+ 0.10·section + source(html 0.10/pdf 0.02) − dup(0.35) [+0.06 definition
en DEFINITION/VARIABLE/CONCEPT] [×0.6 tema mencionado ajeno]
[×0.55 routing FORMULA/VARIABLE sin fórmulas y con símbolos reales y phrase<0.6]`

Justificación de pesos (benchmark dev, congelados antes del test):
lexical manda (terminología normativa exacta), semántico acompaña (paráfrasis),
fórmula solo suma con señal (nunca diluye: sin hits vale 0), frase desempata
colocaciones (`model matemàtic`), topic/section ordenan sin excluir.

## Decisiones clave (detalle en DECISION_LOG D21+)

- **Embeddings**: TF-IDF local (`tfidf-local-1.0`, 11.357 términos). Sin stack
  neural offline en el entorno; interfaz `EmbeddingProvider` lista para swap.
- **Expansión es→ca**: diccionario técnico (~100 entradas) + reglas
  morfológicas validadas contra vocabulario + fuzzy de 1 edición
  (misma raíz de 3 letras, sin empates). `president→precedent` bloqueado.
- **Símbolos**: plegado `uc↔u_c` (conserva caso: `U≠u`); universo matemático
  sin palabras de prosa; routing solo con señal simbólica real.
- **Matching**: tokens con límite de palabra + stems catalanes conservadores
  (`distribucions↔distribució`, nunca `units↔unitats`) + prefijo ≥6
  (`compensar↔compensació`); alineación mejor-variante con masa IDF.
- **Abstención**: tópico desconocido, ≥2 OOV, 1 OOV sin evidencia (masa<0,6),
  masa<0,35, score<0,12, margen estrecho con score débil. Umbrales en
  `app/retrieval/config.py`, calibrados en dev, intactos en test.
- **Límites**: latencia p95 ~130 ms, memoria servicio ~33 MB, índice ~7,9 MB.
  Sin red, sin LLM, determinista (mismos IDs/orden/scores).
