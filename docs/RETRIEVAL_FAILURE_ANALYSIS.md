# RETRIEVAL_FAILURE_ANALYSIS — Taxonomía y casos (Fase 2)

## Conteo en test final (16 items): 0 fallos en todas las clases

`MISS 0 · WRONG_TOPIC 0 · WRONG_CONCEPT 0 · WRONG_FORMULA 0 · WRONG_SOURCE 0 ·
DUPLICATE 0 · INSUFFICIENT_CONTEXT 0 · AMBIGUOUS 0 · FALSE_POSITIVE 0 ·
FAILURE_TO_ABSTAIN 0 · OVER_ABSTENTION 0`

## Near-misses (pasan, vigilados)

- `compensar la tensió d'offset` (paráfrasis verbo→nombre): T10 en #5, T6
  plausible delante. Puente flexivo por prefijo ≥6 lo sostiene; sin él caería.
- `sensibilitat` global: T1 canónico primero, T6/T2 detrás — correcto pero
  denso; Fase 3 deberá citar el tópico adecuado a la pregunta.
- `possible_conflict` salta en queries con top-2 empatado de temas distintos
  (p. ej. B06): es aviso, no error; Fase 3 decide con el pack completo.

## Lecciones de dev (fallos reales encontrados y corregidos con fixes generales)

1. **Contaminación SVG-metadata** (Fase 1): `dc:date/matplotlib` en chunks →
    skip de `<metadata>/<defs>` + test en validación. Hallazgo del primer humo.
2. **`units⊂unitats`**: substring matching → tokens con límite de palabra.
3. **`president→precedent`**: fuzzy agresivo → 1 edición + misma raíz + sin
    empates + reglas morfológicas validadas contra vocabulario.
4. **`uc↔u_c`**: plegado base conservando caso; routing FORMULA/VARIABLE solo
    con señal simbólica real (B06: palabras sin símbolos no castigan texto).
5. **Tema-directivo envenena masa** (`Tema 2 incertesa` abstenía):
    `tema/unitat/capítol+N` filtran, no puntúan.
6. **Minmax oculta debilidad**: masa IDF absoluta + OOV para abstención;
    `guanyar` (vencer/captar) legitima falsos amigos que solo la masa detecta.
7. **Alt de figuras fuera del texto** (H04): `[imatge: alt]` en chunks figura.

## Adversarial manual (§78-80, CLI del 2026-09-03)

- `sensibilitat` → T1+T6 · `Tema 3 sensibilitat` → T3 primero (×0.6 resto) ·
  `Tema 2 incertesa` → T2 · `Tema 20` → abstain `unknown_topic` ·
  Champions/paella/president/fotosíntesi/Quixot → abstain · `uc/U/R/S`
  sueltas → fórmulas/variables sin abstención indebida.
