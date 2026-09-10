# F17 — Auditoria del frontend

**Fase:** F17 §Fase 1 · **Branch:** `feature/f17-product-ui` · **Base:** `v1.0.0` (`a9c153e`)
**Baseline de tests:** `889 passed, 1 skipped, 0 failed` (473,99 s) — l'skip és
`test_home_defaults_under_xdg_on_posix` (companion POSIX, correctament saltat a Windows).

---

## 1. Arquitectura actual

- **Servei:** `web/server.py` (`ThreadingHTTPServer` a `127.0.0.1`). `Handler._static()` serveix
  fitxers de `web/` amb allowlist d'extensions (`_MIME`: `.html .css .js .json .svg .png`).
  `Handler._api()` → `Bridge.route()` despatxa `/api/*`.
- **Frontend:** pàgines HTML estàtiques independents. Cap build, cap npm, cap framework.
  4 fulls CSS + `app.js`/`csrf.js` compartits + un JS per pàgina.
- **Capa de presentació estricta:** el frontend no conté lògica de domini; tota decisió
  (correcció, mastery, temporitzador, recomanacions) és al backend. Aquesta invariant es manté a F17.
- **CSRF:** double‑submit cookie (`sm_session` HttpOnly + `sm_csrf`), header `X-CSRF-Token` via
  `window.smFetch` (`csrf.js`). Intacte a F17.

## 2. Tecnologies

| Capa | Actual | F17 |
|---|---|---|
| Markup | HTML5 estàtic, 1 fitxer/pàgina, shell duplicat 11× | shell injectat per `shell.js` (1 sola font de nav) |
| CSS | `tokens.css` (tokens semàntics, dark via `prefers-color-scheme`), `base.css`, `layout.css`, `components.css` | re‑skin dark‑first violeta; `layout.css`→`shell.css`; +`pages.css` |
| JS | vanilla ES5‑ish, `defer`, sense mòduls | igual; +`shell.js`, +`ui.js` (helpers compartits) |
| Fonts | stack de sistema | Inter self‑hosted (`.woff2`, +1 línia a `_MIME`) |
| Icones | SVG inline ad‑hoc (només hamburger) | sprite `icons.svg` (~16, Lucide ISC) |
| Build | cap | cap (es manté) |

## 3. Pàgines (estat actual)

| Fitxer | Rol actual | Problema principal |
|---|---|---|
| `index.html` | hub d'enllaços (3 targetes → study/learning/exams) | no respon "què faig ara?"; zero dades |
| `study.html` | graella de temes + "següent pas" + formulari de tutor barrejats | tres funcions en una pàgina; el tutor hi està amagat |
| `learning.html` | prioritats + mastery + progrés (4 seccions numerades) | llenguatge d'informe intern ("1. Què faig ara?"), dens |
| `practice.html` | config + pregunta + correcció | formulari administratiu; la pregunta no té focus visual |
| `topic.html` | documents + seccions d'un tema | llistat tècnic d'arxius, no unitat d'aprenentatge |
| `content.html` | lector de secció (text literal KB) | correcte de base; només re‑skin |
| `exams.html` | els meus exàmens + creació | formulari llarg; historial en pàgina separada |
| `exam.html` | runner d'examen (timer, desa, envia) | només re‑shell/re‑token |
| `results.html` / `review.html` | 4 línies + JS que injecta | stubs; només re‑shell |
| `history.html` | historial d'exàmens | entrada de nav separada innecessària |
| `documents.html` / `calendar.html` | stubs "properament" | a la nav principal sense implementació real |
| `design-system.html` | galeria de components | es manté com a referència de dev |

## 4. Components (inventari actual `components.css`)

Presents: `.button` (+`--secondary/--danger/--ghost`), `.icon-button`, `.field/.label/.hint`,
`.input/.select/.textarea`, `.check/.radio/.toggle`, `.card`, `.grid-cards`, `.badge/.pill`
(+`--success/--warning/--danger/--info/--neutral`), `.avatar`, `<progress>.progress`, `.spinner`,
`.skeleton`, `.alert` (+4 variants), `.toast`, `.modal-backdrop/.modal`, `.dropdown`, `.tabs/.tab`,
`.tooltip`, `.state-block`.

Absents (els crea F17): HeroCard, TopicCard, StatCard, RecommendationCard, ProgressBar de `<div>`,
ProgressRing, ChatMessage, EvidenceDrawer, xip de número de tema, skeleton compostos, badges d'estat.

## 5. APIs (contracte, ja existent — F17 no el toca)

| Endpoint | Retorn rellevant per a la UI |
|---|---|
| `GET /api/session` | `{csrf, student}` |
| `GET /api/health` | `{status, version, checks}` |
| `GET /api/study/topics` | `topics[]`: `{topic, documents, sections, formulas, concepts, mastery:{score,attempts}|null}` |
| `GET /api/study/mastery` | `{mastery:{"1":{score,attempts}|null, … "10"}}` |
| `GET /api/study/next` | `{recommendation:{knowledge_unit_id,action,…}|null}` |
| `GET /api/study/documents|sections|content` | documents/seccions/text literal d'un tema |
| `GET /api/learn/priorities?limit=` | `[]` de `project_rec`: `{unit,action,action_label,action_hint,difficulty,mastery:{score,status,status_label,confidence,attempts},reasons_display[],errors[],targets}` — **sense `priority`/`policy_id`/`seed`/weights** |
| `GET /api/learn/progress` | `{attempts,correct,units,last_activity,recent[]}` |
| `GET /api/learn/unit?unit=` | estat + events + errors + locate d'una unitat |
| `POST /api/learn/start` | genera pregunta adaptativa → sessió PRACTICE |
| `POST /api/tutor/ask` | `{answer,status,abstain,formulas[],provenance[],versions:{provider:{provider,model}}}` |
| `POST /api/practice/start|submit`, `GET question`, `POST result|complete` | flux de pràctica amb correcció de backend |
| `POST /api/exam/create|start|save|submit|grade`, `GET state|question|result|review|mastery|mine|history` | màquina d'estats d'examen |

**Conclusió:** tot el que la nova UI necessita ja existeix. Zero endpoints nous, zero canvis de forma.

## 6. Estats

- Càrrega: text "Carregant…" inline (inconsistent). `.skeleton` existeix però poc usat.
- Error: `.alert--danger` o `.state-block` amb codi; sense botó de reintent cablejat de manera uniforme.
- Buit: `.state-block` amb `○`. Copy no estandarditzat.
- F17 unifica els tres via `ui.js` (skeleton per regió, `[Reintenta]` cablejat, copy en català).

## 7. Problemes UX

1. `index.html` no orienta: cap "continua per aquí".
2. Navegació barreja implementat i stubs (`properament`) al mateix nivell.
3. `study.html` amaga el tutor sota temes; el tutor mereix pàgina pròpia.
4. `learning.html` parla com un informe intern, no com un entrenador.
5. `practice.html`/`exams.html` són formularis; la pregunta i el resultat no tenen jerarquia.
6. `topic.html` sembla un explorador d'arxius.
7. Historial en entrada de nav separada.
8. Peus "capa de presentació BX" i nota `ETSETB‑UPC 230920` exposen fontaneria.

## 8. Problemes visuals

- Estètica "admin/iOS" genèrica: blau de sistema, targetes totes iguals, `<progress>` cru,
  ombres febles, tipografia de sistema sense jerarquia treballada.
- Densitat plana: h2 + graella de targetes repetida a totes les pàgines.
- Cap identitat pròpia.

## 9. Problemes responsive

- Layout de shell correcte (`grid` 1‑col → 2‑col ≥48rem, sidebar off‑canvas <48rem) — **es conserva**.
- `.grid-cards` a 2/3 columnes ja respon.
- Risc a validar a 1366×768: blocs de pregunta de pràctica/examen i columna de xat.

## 10. Problemes d'accessibilitat

- Base sòlida: skip‑link, landmarks, `aria-current`, focus‑visible 3px, `aria-live` a regions async,
  `prefers-reduced-motion` global, targets 44px.
- A verificar amb la nova paleta: contrast de l'accent violeta i dels tokens de text (AA) en tots dos temes.
- `<progress>` amb `textContent` de % com a fallback — es reemplaça per `role="progressbar"` amb aria‑values.
- Status només per color a alguns badges → F17 hi afegeix punt + etiqueta.

## 11. Codi reutilitzable

- `tokens.css`: estructura semàntica sencera (només canvien valors).
- `base.css`: reset, focus, reduced‑motion, **renderitzat de fórmules** — intacte.
- `app.js`: focus‑trap de modal, tabs, dropdown, toast — es reutilitza (drawer comparteix el focus‑trap).
- `csrf.js` `smFetch` — intacte.
- Patrons `el()` / `api()` / `setState()` repetits a cada JS de pàgina → es consoliden a `ui.js`.
- Flux de pràctica/examen/adaptatiu de `practice.js`/`exam.js`/`learning.js` — es conserva la lògica de crida.

## 12. Codi a redissenyar

- `layout.css` → `shell.css` (sidebar/header amb la nova identitat).
- `components.css` (nous components + re‑estil).
- Shell HTML duplicat a 11 fitxers → `shell.js` + config única.
- `index.html`, `study.html`, `learning.html` → dashboard, `temari.html`, `tutor.html`, `progres.html`.
- `topic.html`, `practice.html`, `exams.html` → re‑estructura de contingut.

## 13. Riscos

| Risc | Mitigació |
|---|---|
| Regressió funcional del backend certificat | F17 toca només `web/` + 1 línia `_MIME`; suite completa vs baseline 889 |
| FOUC del shell injectat per JS | `shell.js` a `<head>` sense `defer`; `grid` reserva la columna → sense layout shift |
| Contrast AA de l'accent violeta | valors fixats i verificats a `F17_UI_DESIGN.md §6` |
| Inventar dades per omplir la UI | regla dura: només render de camps reals d'API; seccions sense dades s'amaguen o mostren buit honest |
| Etiquetes d'estat de tema | derivades de `mastery.score` real amb llindars **fixats al spec**, documentades a DECISION_LOG |
| Bookmarks trencats (`study.html`, `learning.html`, `history.html`) | stubs de redirecció (`location.replace`) |
| Trencar contracte d'API sense adonar‑se'n | `tests/web/test_api_contract_f17.py` (nou) verifica claus + absència de `priority`/`policy_id`/`seed` |

## 14. Proposta

Redisseny dark‑first amb accent violeta i identitat pròpia (no còpia de la referència), en 4 seccions
de disseny aprovades (design system, application shell, IA per pàgina, transversals). Implementació
incremental per blocs: shell → tokens → dashboard → temari → tema → pràctica → tutor → progrés →
exàmens → estats → QA. Zero canvis funcionals de backend (excepció: `".woff2"` a `_MIME`). Nav
reduïda a funcionalitat real: **Inici · Temari · Pràctica · Tutor IA · Progrés · Exàmens**.
Detall a `docs/superpowers/specs/2026-09-10-f17-product-ui-design.md` i `docs/F17_UI_DESIGN.md`.
