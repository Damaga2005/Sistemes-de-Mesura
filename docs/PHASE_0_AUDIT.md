# PHASE_0_AUDIT — Sistemes de Mesura

Fecha: 2026-09-03 · Método: inspección determinista (stdlib + PyMuPDF + pypdf), clon de solo lectura en TEMP.
Originales: **no modificados** (verificado: solo lectura; git status del origen: clean).

## 1. Repositorio (medido)

- Origen: `Damaga2005/Sistemes-de-Mesura` — 10 carpetas `Tema 1..10`, sin README ni estructura `app/`/`data/`/`tests/`/`docs/`.
- **91 archivos**: 81 HTML + 10 PDF. **~122,7 MB** totales.
- Por tema: 1 PDF (`Apunts SM Tema N.pdf`) + HTML de teoría (4–8) + 1 `index` + 1 `entrenament`.
- Nomenclatura inconsistente entre temas (`SM_U1_*`, `2_*`, `01_doc`, `00_Unitat*_Index`): el topic se derivará **siempre de la carpeta**, nunca del nombre (test 10).
- Historial git: subidas manuales web (`Add files via upload`, `Mover archivos a la carpeta Tema 5`). Sin tags ni versiones; el hash SHA-256 por archivo es por tanto el único versionado fiable (ver §9).

## 2. HTML como documento estructurado (confirmado)

Jerarquía semántica aprovechable y **uniforme en Temas 2–10**, distinta en Tema 1:

| Elemento | Temas 2–10 | Tema 1 |
|---|---|---|
| `lang` | `ca` siempre | `ca` siempre |
| hero (`breadcrumb` + `kicker` + `h1` + `p.lead` con dedicación) | sí | variante propia (`SM · Unitat 1`) |
| `h1` = título del apartado | 1 por página | 1 por página |
| `h2` = secciones numeradas | 2–8 por página | 5–7 por página |
| `h3` | escasos (casi todo es h2) | presentes (Tema 1 más profundo) |
| `.box.objectius` (objetivos) / `.box.resum` (síntesis) | siempre, 1 de cada | equivalentes (`box objectius`, `box resum`, `box clau`, `box atencio`, `box dada`, `box llegir`) |
| `.box.nota` / `.box.atencio` (avisos) | sí | sí (`box atencio`) |
| `table.data` | 0–7 por página | 0–4 por página |
| listas / `figure`+`figcaption` / `pre.code` | sí | listas sí; código no observado |
| enlaces externos | ~0 (corpus autocontenido) | ~0 |

Conclusión: existe una jerarquía **Tema → Documento (h1) → Sección (h2) → [bloques tipados]** directamente convertible en chunking semántico padre-hijo. Los `index` declaran además orden de lectura y dedicación (p. ej. U2: 50 min, U4: 62 min).

## 3. Fórmulas (hallazgo central, confirmado)

- **Temas 2–10 (61 páginas de teoría): 2.858 fórmulas**, cada una = 1 SVG matplotlib **con su fuente LaTeX preservada en comentario** `<!-- $...$ -->` (ratio 1:1 verificado exhaustivamente, p. ej. `<!-- $U=k\,u_c$ -->`, `<!-- $Z=R+jX$ -->`).
  Consecuencia: extracción determinista de LaTeX con un parser (regex sobre comentarios + asociación al SVG hermano). **Sin OCR, sin MathJax/KaTeX** (0 ocurrencias en todo el corpus), **sin riesgo `u_c(y)`→`uc(y)`** si se extrae el comentario y no el render.
- **Tema 1 (6 páginas): 0 SVG, 0 comentarios LaTeX.** Fórmulas como HTML Unicode (`<sub>`/`<sup>`: 61 `<sup>` en U1_02, 22 `<sub>` en U1_05, símbolos `Ω`, `±`). Fidelidad aceptable pero menor; requiere extractor específico con tests de preservación (riesgo R2).
- PDFs: texto seleccionable con fórmulas en línea; la extracción PyMuPDF/pypdf conserva letras griegas en las muestras (ver §4). El LaTeX canónico, no obstante, debe venir de los comentarios HTML donde existan.

## 4. PDF (medido con PyMuPDF 1.28 + pypdf 6.14)

| PDF | Páginas | Caracteres | Páginas con texto | Imágenes | Título |
|---|---|---|---|---|---|
| Tema 1 | 56 | 130.007 | 56 | 18 | Capítol 1: Introducció als Sistemes de Mesura |
| Tema 2 | 44 | 88.776 | 44 | 20 | Capítol 2: Estimació de la Incertesa a la Mesura |
| Tema 3 | 51 | 114.062 | 51 | 27 | Capítol 3: Interferències en Sistemes de Mesura |
| Tema 4 | 45 | 97.579 | 45 | 16 | Capítol 4: Soroll en Sistemes de Mesura |
| Tema 5 | 58 | 128.929 | 58 | 48 | Capítol 5: Sensors Resistius |
| Tema 6 | 59 | 127.930 | 59 | 51 | Capítol 6: Condicionament de Sensors en Continua |
| Tema 7 | 57 | 130.604 | 57 | 54 | Capítol 7: Sensors reactius i electromagnètics |
| Tema 8 | 68 | 144.178 | 68 | 53 | Capítol 8: Condicionament de Sensors en Alterna |
| Tema 9 | 54 | 129.670 | 54 | 38 | Capítol 9: Sensors Generadors… |
| Tema 10 | 31 | 72.044 | 31 | 22 | Capítol 10: Condicionament Singular de Senyals |
| **Total** | **523** | **~1,16 M** | **523 (100 %)** | **347** | — |

Sin OCR (todo texto nativo), 0 páginas con glifos corruptos (`\ufffd`/`(cid:`), sin caracteres científicos dañados en las muestras. Calidad de extracción: **alta**.

## 5. Relación PDF ↔ HTML (respuestas A–H, Tema 2 medido + resto inferido)

- A–D. **No es transcripción literal.** Tema 2: PDF ~88,8k chars / 13,9k palabras vs HTML teoría ~57,6k chars / 9,1k palabras visibles. Los `index` declaran que los HTML *sustituyen a los apunts para la lectura previa* (aula inversa). Cobertura terminológica coincidente (`incertesa expandida` pdf=20/html=19, `factor de cobertura` 20/18, `combinada` 10/14) → **misma materia, distinta redacción/granularidad**. [confirmed parcial Tema 2; inferred resto]
- E. Fórmulas: misma física, distinta codificación (LaTeX en HTML vs texto PDF). Comparación símbolo a símbolo pendiente en Fase 1 (muestreo obligatorio). [unknown]
- F. Visual: PDF 347 imágenes vs HTML 723 base64 + 265 `<img>` + 2.858 SVG. Conjuntos parcialmente disjuntos con seguridad (órdenes de magnitud distintos). [confirmed]
- G. Derivación: nomenclatura distinta (`Capítol N` en PDF vs `Unitat N` en HTML) y los HTML enlazan cuestionarios de Atenea y dedicaciones → **dos líneas de material del mismo curso, no una derivada mecánica de la otra**. [inferred, confianza media-alta]
- H. **Riesgo de recuperación duplicada: SÍ.** Indexar PDF+HTML sin `source_type` ponderaría doble casi todo el temario. Decisión D4: HTML = fuente primaria de chunks; PDF = corroboración + fallback visual (ver KNOWLEDGE_ARCHITECTURE).

## 6. Información visual (confirmado)

Teoría fuertemente visual: circuitos, diagramas de bloques, curvas de respuesta, fotos de sensores, tablas de tipos. Conteo: 723 base64 + 265 `<img>` + 347 PDF + 2.858 SVG-fórmula. Patrón anómalo: **Tema 5 repite 39 base64 en cada uno de sus 8 HTML** (plantilla con assets duplicados probable) y Tema 4/6 repiten 11/26 por página → deduplicar por hash de bytes en Fase 1 (riesgo R4). Toda imagen indexada llevará `image_reference` + `image_context` (caption/texto vecino); las esenciales sin correlato textual se marcan `NEEDS_REVIEW`.

## 7. Entrenament (confirmado, importante)

10 archivos, uno por tema. Son apps JS autocontenidas (cálculo local en navegador) con **banco embebido de ~50 afirmaciones V/F por unidad** (`var BANC` / `var DOCS` / `const DATA`, campos `q`=afirmación, `a`=V/F, `j`=justificación, `d`=documento origen; modalidades simulacro 30 s/afirmación y libre; opción `No ho sé` porque adivinar penaliza en Atenea).
**~500 preguntas V/F con justificación y trazabilidad a documento: el dataset de evaluación inicial ya existe.** No indexar como teoría (contaminación); usar como `evaluation/` con script extractor en Fase 1.

## 8. Duplicados, boilerplate, conflictos

- Duplicados exactos de contenido académico: **0 colisiones** (hash de prefijo visible normalizado). Pendiente: near-dup PDF↔HTML a nivel de fragmento (Fase 1, shingles).
- Boilerplate identificado y excluible por selector: `<style>` (1,5–17 kB/página), 1 `<script>`/página (lógica entrenament/imágenes), `breadcrumb`/`hero`, instrucciones de edición **solo en Tema 1** (`COM EDITAR AQUEST FITXER`, con lista de etiquetas y cajas de colores — útil como taxonomía emergente, ver §10), pies `Sistemes de Mesura · ETSETB-UPC`.
- Conflictos académicos reales: **0 detectados en Fase 0** (no se comparó semántica fina; el pipeline Fase 1 debe registrar `CONFLICT` con la taxonomía del §15 del brief, nunca resolver en silencio).

## 9. Versionado e integridad

SHA-256 completo por archivo en `data/source_manifest.json` (91 entradas, IDs `sm-<tema>-<hash10>` deterministas). Git origen sin tags: el `source_hash` es la única señal de cambio. Reproducibilidad: material + versión pipeline + config = mismo dataset (tests 2, 3, 4, 9).

## 10. Taxonomía emergente (del propio material, no inventada)

Tema 1 documenta sus cajas: `box clau` (idea clau, verde), `box atencio` (parany/avís, ámbar), `box dada` (dato/contexto, gris), `box llegir`, `box objectius`/`box resum` (azul); Temas 2–10 usan `objectius/nota/resum/exemple`. Base suficiente para mapear a la taxonomía de contenido de la Fase 1 (ver KNOWLEDGE_ARCHITECTURE).

## 11. Matriz de cobertura

| Tema | Docs teoría | Fórmulas HTML | Imágenes b64 | Tablas | PDF págs | Entrenament V/F | Estado |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 0 (sub/sup) | 13 | 8 | 56 | ~50 | WARNING (R2) |
| 2 | 8 | 281 | 10 | 4 | 44 | ~50 | OK |
| 3 | 4 | 264 | 22 | 1 | 51 | ~50 | OK |
| 4 | 6 | 365 | 66 | 1 | 45 | ~50 | OK (dedup R4) |
| 5 | 8 | 259 | 312 | 4 | 58 | ~50 | OK (dedup R4) |
| 6 | 6 | 293 | 156 | 4 | 59 | ~50 | OK (dedup R4) |
| 7 | 6 | 319 | 48 | 16 | 57 | ~50 | OK |
| 8 | 6 | 445 | 45 | 11 | 68 | ~50 | OK |
| 9 | 6 | 253 | 32 | 27 | 54 | ~50 | OK |
| 10 | 5 | 379 | 19 | 14 | 31 | ~50 | OK |

## 12. Métricas del ingestor (línea base Fase 0 → objetivo Fase 1)

Cobertura 91/91 inventariados (100 %); extracción texto HTML 81/81, PDF 523/523 páginas con texto; metadatos completos 91/91 en manifest; fórmulas 2.858 (Temas 2–10) + sub/sup Tema 1; visual ~1.335 elementos raster + 2.858 SVG; duplicados exactos 0; conflictos 0 (pendiente semántica); trazabilidad: todo fragmento futuro enlazará a `manifest.id` + sección + hash.
