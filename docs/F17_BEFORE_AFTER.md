# F17 — Before / After

Redisseny de producte de la UI web (`web/`). Branca `feature/f17-product-ui`,
BASE `340400a`. Sense canvis de backend (excepció: 1 línia `_MIME`).

## Taula comparativa

| Dimensió | Abans (B1–B6) | Després (F17) |
|---|---|---|
| **Layout** | `layout.css` genèric, contenidor ample sense límit de lectura, xrome inline repetit a cada HTML | Shell injectat per `shell.js` al voltant de `<main id="main">`; `--content-max` / `--reading-max` limiten l'amplada; `shell.css` + `pages.css` separen estructura de pàgina | 
| **Navegació** | Sidebar inline a cada fitxer amb enllaços a pàgines no implementades (`study`, `learning`, `documents`, `calendar`, `history` com a entrada pròpia) | Config única a `shell.js` NAV: `Inici · Temari · Pràctica · Tutor IA · Progrés · Exàmens`. `study.html` / `learning.html` / `history.html` són stubs `location.replace`. Documents/Calendari fora de la nav. `aria-current="page"` derivat de `data-route` |
| **Densitat** | Cards planes, espaiat irregular, poca jerarquia entre seccions | Escala d'espaiat per tokens (`--sp-*`), `.card` amb elevació i `--surface-elevated`, grups de nav amb overline (`ESTUDI` / `APRENDRE` / `AVALUACIÓ`) |
| **Tipografia** | Stack de sistema, escala plana (`--fs-caption`, `--fs-button`) | Inter variable self-hosted (`InterVariable.woff2`, SIL OFL); escala semàntica ampliada (`--fs-display`, `--fs-h1..h3`, `--fs-stat`, `--fs-overline`, `--fs-meta`); pesos dedicats (`--fw-h1`, `--fw-bold`) |
| **Jerarquia** | Un sol nivell de títol visible; CTA barrejat amb text | `breadcrumbs` a cada pàgina de producte, H1 + subtítol descriptiu, blocs d'acció separats (p. ex. Tema: `Estudiar` / `Practicar` / `Preguntar al Tutor`) |
| **Experiència (estats)** | Errors i buits inconsistents; `aria-busy` no sempre netejat | `ui.js#setState(el, kind)` unificat: `loading` (spinner), `error` (bloc + reintent), `empty` (missatge + CTA), `ready` (neteja `aria-busy`). Dashboard, Temari, Progrés, Exàmens, Tutor el fan servir |
| **Accions** | Botons genèrics, poca diferència primària/secundària | `.button` primari (gradient d'accent) vs secundari; `.icon-button` amb `aria-label` obligatori; CTA sempre visible sense scroll a les pàgines revisades |
| **Visualització de progrés** | `<progress>` cru amb `%` numèric | `ui.js#statusFromMastery()` deriva etiqueta d'estat (`No iniciat` / `Reforçar` / `En progrés` / `Domini alt` / `Completat`) de `mastery.score` real amb llindars congelats (`<0.40`, `<0.75`, `<0.95`; només si `attempts>0`); `.progress-ring` i `role="progressbar"` amb `aria-valuenow` |

## Visual QA

**Mètode:** servidor local real (`python -m web.server --host 127.0.0.1 --port 8912`)
+ eina de navegador (Chrome headless via MCP). Revisió a 1366×768 de les 7
pàgines i comprovació addicional a 1440×900 i 1920×1080 de les pàgines més
denses (Inici, Temari, Pràctica, Exàmens). El servidor va servir les pàgines i
els seus assets (incloent `InterVariable.woff2` → 200 `font/woff2`) sense error.
Les captures es van fer amb la suite `pytest` executant-se en paral·lel; alguns
primers fotogrames mostraven l'estat `loading` (skeletons) que es resolia en el
següent fotograma — comportament esperat, no defecte.

### Pàgines revisades (1366×768)

| Pàgina | URL | Resultat |
|---|---|---|
| Inici | `/index.html` | Hero "Comença a estudiar" + CTA; secció "El teu progrés" (3 stat-cards); "Necessites reforçar"; "Activitat recent" amb estat buit honest. Sidebar íntegra, footer amb indicador de proveïdor ("● Tutor: preparat"). Sense scroll horitzontal. |
| Temari | `/temari.html` | Graella de `topic-card` a 2 columnes, badge d'estat "No iniciat", recompte `N seccions · M fórmules`, CTA "Obrir tema →". Sense scroll horitzontal, cards no deformades. |
| Tema | `/topic.html?topic=2` | Breadcrumb `Inici / Temari / Tema`, H1 "Tema 2", accions `Estudiar` / `Practicar` / `Preguntar al Tutor`, llista "Continguts" (U2-01…U2-08). Correcte. |
| Pràctica | `/practice.html` | Card "Configuració" amb graella de 2 columnes (Tema / Tipus / Dificultat / Seed) i CTA "Genera pregunta" visible. Correcte. |
| Tutor IA | `/tutor.html` | Breadcrumb `Inici / Tutor IA`, H1 + subtítol, camp "Escriu la teva pregunta…" + botó "Pregunta". Fil de conversa buit fins a la primera consulta. Correcte. |
| Progrés | `/progres.html` | Seccions "Resum" / "Domini per tema" / "Recomanat per a tu" / "Detall d'unitat"; amb DB d'alumne nova mostra estat buit "Encara no hi ha res" + CTA "Comença una pràctica". Correcte. |
| Exàmens | `/exams.html` | "Els meus exàmens" (buit), "Historial" plegat dins la pàgina (buit), formulari "Nou examen" amb selector de tipus i caselles Tema 1–10. Sense scroll horitzontal. |

### Amplades addicionals

- **1440×900** (Pràctica, Exàmens): graelles de camps i caselles de tema
  reflueixen correctament; CTA visible; sense clipping.
- **1920×1080** (Inici, Temari): el contingut queda limitat per `--content-max`
  i no s'estira a tota l'amplada; la sidebar manté amplada fixa; només apareix
  la barra de scroll vertical, mai horitzontal.

### Observacions

- Cap scroll horitzontal a cap pàgina/amplada revisada.
- Cap text retallat ni card deformada.
- Sidebar i header injectats presents i coherents a totes les pàgines.
- CTA principal visible sense scroll a totes les pàgines revisades.
- Estats `loading` / `empty` es rendereixen amb el component compartit; els
  estats buits porten CTA o missatge honest (sense dades inventades).
- No s'ha exercit el drawer d'evidència de Tutor (requereix una consulta amb
  proveïdor Gemini; l'entorn usa el proveïdor extractiu determinista). Resta com
  a P2 documentat (vegeu `F17_IMPLEMENTATION.md` §Residual P2s núm. 5).

### Revisió estàtica de CSS responsive (complement)

Regles a `shell.css` / `pages.css`: breakpoints `@media (width >= 48rem / 64rem
/ 80rem)`, `overflow-x` controlat al contenidor de `<main>`, `--sidebar-w` i
`--header-h` fixos, `--content-max` / `--reading-max` per limitar longitud de
línia. La graella de `topic-card` i les stat-cards passen d'1 a 2–3 columnes
segons breakpoint. Coincideix amb el comportament observat en viu.
