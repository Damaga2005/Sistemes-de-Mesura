# F17 — Implementation

Redisseny de producte de la UI web. Branca `feature/f17-product-ui`, BASE
`340400a`. 14 tasques (Tasks 1–13 = disseny + implementació; Task 14 =
verificació + pressupostos + docs).

## Fitxers

### Creats

**HTML** — `web/temari.html`, `web/tutor.html`, `web/progres.html`
**CSS** — `web/static/css/shell.css` (estructura de shell), `web/static/css/pages.css` (layout per pàgina)
**JS** — `web/static/js/shell.js` (injecció de header + sidebar), `web/static/js/ui.js` (helpers de presentació compartits), `web/static/js/i18n.js` (diccionari CA/ES de chrome + `sm-lang` a `localStorage`), `web/static/js/dashboard.js`, `web/static/js/temari.js`, `web/static/js/tutor.js`, `web/static/js/progres.js`
**Assets** — `web/static/fonts/InterVariable.woff2` (SIL OFL 1.1), `web/static/fonts/OFL.txt`, `web/static/icons.svg` (sprite de símbols, path data adaptat de Lucide, ISC)
**Tests** — `tests/web/test_shell.py`, `tests/web/test_ui_helpers.py`, `tests/web/test_i18n.py`, `tests/web/test_dashboard.py`, `tests/web/test_api_contract_f17.py`, `tests/web/test_static_assets.py`
**Docs** — `docs/F17_UI_AUDIT.md`, `docs/F17_UI_DESIGN.md`, `docs/F17_BEFORE_AFTER.md`, `docs/F17_IMPLEMENTATION.md`

### Modificats

**HTML** — `web/index.html`, `web/design-system.html`, `web/content.html`, `web/topic.html`, `web/practice.html`, `web/exams.html`, `web/exam.html`, `web/results.html`, `web/review.html`, `web/calendar.html`, `web/documents.html`, `web/history.html`, `web/learning.html`, `web/study.html` (reshell + stubs de redirecció on escau)
**CSS** — `web/static/css/tokens.css` (tokens dark-first, escala tipogràfica ampliada), `web/static/css/base.css` (fixups de rename de tokens), `web/static/css/components.css` (sistema de components ampliat)
**JS** — `web/static/js/app.js`, `web/static/js/topic.js`, `web/static/js/practice.js`, `web/static/js/exams.js`, `web/static/js/exam.js`, `web/static/js/results.js`, `web/static/js/review.js`
**Backend** — `web/server.py`: **1 línia** (`".woff2": "font/woff2"` al dict `_MIME`). Res més.
**Tests** — `tests/web/test_design_system.py`, `tests/web/test_study_ux.py`, `tests/web/test_learn_ux.py`, `tests/web/test_b6_certification.py`, `tests/web/test_exam_ux_contract.py`
**Docs** — `docs/DECISION_LOG.md` (D183–D187)

### Eliminats

`web/static/css/layout.css` (substituït per `shell.css` + `pages.css`)
`web/static/js/study.js` (→ `temari.js` + `tutor.js`)
`web/static/js/learning.js` (→ `progres.js`)
`web/static/js/history.js` (Historial plegat dins Exàmens)

## Components creats (`components.css` / `ui.js`)

`.hero-card`, `.topic-card`, `.stat-card`, `.rec-card`, `.progress__fill`,
`.progress-ring`, `.chat__msg`, `.drawer` (drawer d'evidència compartit),
`.chip-num`, `.state-block` (loading/error/empty), `.formula`. Helpers de
`ui.js`: `setState(el, kind, opts)`, `statusFromMastery(m)`, `relativeTime(iso)`,
`progressBar` / `progressRing`, `openEvidence(...)`, `setProvider(...)`.
`shell.js`: injecció de header + sidebar amb `NAV` únic i `aria-current` derivat
de `data-route`.

## APIs usades

Totes **preexistents** (F10 / bridge B2). Cap endpoint nou, cap canvi de forma
de resposta. Consumides:

- `GET /api/study/topics`, `/api/study/documents`, `/api/study/sections`, `/api/study/content`, `/api/study/next`, `/api/study/mastery`
- `GET /api/learn/priorities`, `/api/learn/progress`, `/api/learn/unit`, `/api/learn/locate`
- `POST /api/tutor/ask`
- `POST /api/practice/start`, `/api/practice/submit`, `GET /api/practice/question`
- `POST /api/exam/create|start|save|submit|grade`, `GET /api/exam/state|question|result|review|mine|history`
- `GET /api/session`, `/api/health`

Contracte verificat per `tests/web/test_api_contract_f17.py` (formes que la UI
assumeix: `topics[]` amb `mastery{score,attempts}|null`; `learn/priorities`
sense interns `priority_score`/`policy_id`/`seed` i amb `reasons_display`;
`learn/progress` amb `{attempts,correct,units,last_activity,recent}`;
`tutor/ask` amb `versions.provider`).

## Dependències noves

**Cap.** Vanilla ES5, `http.server` stdlib, zero dependències runtime (charter).
Inter és self-hosted (no CDN). Icones són un sprite SVG local.

## Impacte al backend

**0 canvis funcionals.** **+1 línia** a `web/server.py` `_MIME`:
`".woff2": "font/woff2"` (D184 — imprescindible per servir la font
self-hosted). Verificat:

```
$ git diff a9c153e..HEAD -- web/server.py app/
--- a/web/server.py
+++ b/web/server.py
@@ -1034,7 +1034,8 @@ _MIME = {".html": "text/html; charset=utf-8",
          ".css": "text/css; charset=utf-8",
          ".js": "text/javascript; charset=utf-8",
          ".json": "application/json",
-         ".svg": "image/svg+xml", ".png": "image/png"}
+         ".svg": "image/svg+xml", ".png": "image/png",
+         ".woff2": "font/woff2"}
```

`app/` sense cap canvi.

## Decisions d'UX

- **Dark-first amb acent violeta** (D183). Tema clar com a override
  `prefers-color-scheme`, sense toggle. `--bg #131118` (negre càlid violaci, no
  `#000` — la Fase 4 prohibeix "excés de negre").
- **Nav reduïda a funcionalitat real** (D186): `Inici · Temari · Pràctica ·
  Tutor IA · Progrés · Exàmens`. Documents/Calendari fora de la nav; Historial
  plegat dins Exàmens; `study/learning/history.html` → stubs `location.replace`
  (preserven bookmarks).
- **Etiqueta d'estat en lloc de `%` cru** (D185): `statusFromMastery()` deriva
  `No iniciat` / `Reforçar` / `En progrés` / `Domini alt` / `Completat` de
  `mastery.score` real amb llindars congelats (`<0.40`, `<0.75`, `<0.95`;
  només si `attempts>0`). Regla 100% derivada de números del backend.
- **Estats unificats** (`setState`): tota càrrega asíncrona té `loading` /
  `error` (amb reintent) / `empty` (amb CTA o missatge honest). Res d'inventat
  als estats buits.
- **Pressupostos de rendiment com a sostres, no objectius** (D187): cap asset
  s'infla per omplir marge.
- **i18n de chrome CA/ES** (D-T13-b): diccionari data-only en un sol fitxer;
  `documents.js`/`calendar.js` queden CA-only (fora de nav — P2 acceptat).

## Reconciliació de tests (Step 3)

Dues execucions netes consecutives de `python -m pytest tests/ -q`:

```
Run 1: 925 passed, 1 skipped in 552.80s   (0 failed, 0 errored)
Run 2: 925 passed, 1 skipped in 521.75s   (0 failed, 0 errored)
```

Recompte idèntic i estable. L'únic skip és
`test_home_defaults_under_xdg_on_posix` (porta POSIX; salta a Windows).

### Aritmètica

```
Baseline pre-F17 (referència del pla)      889 passed + 1 skipped = 890 recollits
+ fitxers de test nous (6)                 +32
+ delta net en fitxers de test modificats  +4
------------------------------------------------------------
Final                                      926 recollits = 925 passed + 1 skipped + 0 failed
```

**Fitxers de test nous (+32 recollits):**

| Fitxer | Recollits | Origen (ledger / step) |
|---|---:|---|
| `test_shell.py` | 5 | R7, R8 (nou domicili de "exactament una ruta activa" + nav honesta contra `shell.js`) |
| `test_ui_helpers.py` | 5 | R14, R15 (equivalents de fitxer nou: no-random/no-sort, no-domain-logic, localStorage només a i18n, llindars congelats) |
| `test_static_assets.py` | 12 | Task 2 en va crear 4 (`_MIME` woff2, font vàlida, OFL, sprite d'icones); **Task 14 Step 2** n'afegeix 8 (serving HTTP real de woff2 → `font/woff2`, icons.svg → `image/svg+xml`, `temari/tutor/progres.html` → `text/html`, stubs `study/learning/history.html` → `text/html`) |
| `test_i18n.py` | 4 | R15 (`sm-lang` a localStorage) + cobertura del diccionari CA/ES (Task 13) |
| `test_dashboard.py` | 2 | Task 4 (estructura del dashboard d'Inici) |
| `test_api_contract_f17.py` | 4 | Spec §7 (Task 5): formes de `study/topics`, `learn/priorities`, `learn/progress`, `tutor/ask` |

**Fitxers de test modificats (+4 recollits net):**

| Fitxer | Δ funcions | Detall |
|---|---:|---|
| `test_study_ux.py` | +2 | R12: `test_study_hub_structure` (sobre `study.html`) → `test_temari_structure` (`#topic-cards` a `temari.html`) + `test_tutor_structure` (`#tutor-thread`/`#tutor-input` a `tutor.html`). R13: wiring de `tutor.js` (`/api/tutor/ask`, `abstain`, `ABSTAIN`) |
| `test_b6_certification.py` | +1 | R17: assercions d'stub de redirecció (`study/learning/history.html` contenen `location.replace` al target correcte) es divideixen en test propi. R18: `history.js` surt de la tupla de fitxers auditats (eliminat) |
| `test_exam_ux_contract.py` | +1 | Contracte de reshell d'exam/results/review (Task 10/11/12): `id="main"` + shell injectat + enllaços de nav de pàgina amb `?xsid=` |
| `test_design_system.py` | 0 net | R1–R11 reescriuen assercions **in situ** sense afegir/treure funcions: `PAGES` (product pages amb shell), bundle `css()` (`shell.css`+`pages.css` en lloc de `layout.css`), llista `TOKENS` (noms nous, compte ≥ antic), `COMPONENTS` (+9 classes noves), `test_perf_budgets` (sostres nous + línia `ui.js`), blob de `test_no_domain_logic_in_frontend` (+7 fitxers JS nous). Força d'asserció igual o superior en tots els casos |
| `test_learn_ux.py` | 0 net | R16: `learning.html`/`learning.js` → `progres.html`/`progres.js` amb els mateixos checks (ids presents / wiring d'endpoints / `reasons_display` / `aria-live ≥ 3`) |

Cap test reconciliat es va afeblir; els nous només reforcen (confirmat a la
revisió de cada tasca). `test_design_system.py::test_perf_budgets` i
`test_ui_helpers.py::test_status_thresholds_frozen` van rebre assercions
addicionals a Task 14 (línia de sostre `ui.js < 14 KiB`; operadors exactes
`v < 0.40` / `v < 0.75` / `v < 0.95` + guarda d'`attempts`) — només enfortiment.

## Pressupostos de rendiment (mesures finals)

| Fitxer | Mida | Sostre |
|---|---:|---:|
| `tokens.css` | 6413 B | 14 KiB |
| `app.js` | 4872 B | 8 KiB |
| `shell.js` | 3599 B | 10 KiB |
| `ui.js` | 10864 B | 14 KiB |
| `i18n.js` | 14723 B | 16 KiB (D-T13-b) |
| css-total | 39495 B | — |
| total pressupost (`test_perf_budgets`) | 66598 B | 220 KiB (225280) |

Tot còmodament per sota. Cap asset s'ha inflat ni retallat per encaixar un
número (D187).

## Integritat (Step 4)

```
$ python -m app.cli check            → "check OK"        (exit 0)
$ python -m app.cli check --status   → knowledge/questions/student 1->1 (exit 0)
$ git diff --stat a9c153e..HEAD -- data/   → (buit)
$ git status --porcelain -- data/    → (buit, després de checkout del .sqlite mutat per pytest)
```

## Residual P2s

Còpia literal (context de controlador, Task 14):

1. `app/final_certification_benchmark.py:25` + `app/review_results_history_benchmark.py:15` still read the deleted `web/static/js/history.js` → `FileNotFoundError` if either standalone script is run directly. NO pytest module imports them. Out of F17 scope (backend/app freeze is a Global Constraint). Follow-up: a non-F17 cleanup that owns `app/`. (Ruling T11-b)
2. `documents.js` / `calendar.js` chrome left CA-only — not in the redesigned nav, no i18n namespace allotted; ES is an optional secondary language. An ES user opening those pages by direct URL sees Catalan chrome. Follow-up: add `doc.*`/`cal.*` key buckets if these pages are ever promoted. (Ruling T13-a)
3. Dead `else` fallback arms (`if (smUI && smUI.setState) {...} else {...CA...}`) in `exam.js` / `results.js` / `review.js` — unreachable (`ui.js` always loaded before page scripts). Hold untranslated CA strings. Safe to delete in a separate cleanup.
4. `exam.js` GRADED-result-fetch-failure text reuses `exam.reasonUnknown` ("Resultat no disponible", no full stop) — minor semantic/punctuation drift; identical in both languages.
5. Practice explanation / evidence drawer for practice submissions is DORMANT: `/api/practice/submit` has no `explanation` / `provenance` / `formulas` fields, so `practice.js` renders no evidence affordance there (only `tutor.js` does). Honest per "no invented data" — documented limitation, not a bug.
6. `dashboard.js` issues two independent `/api/study/mastery` + `/api/learn/progress` fetches (one per card) for independent retry isolation — a deliberate duplicate-fetch tradeoff.
7. `smUI.progressRing` has no `.skeleton--card` class of its own (composed inline by `ui.js`).
8. `test_status_thresholds_frozen` in `test_ui_helpers.py` (or wherever it lives) is substring-only. **Task 14 Step 1 optional hardening (do it if quick):** add operator-level asserts that call `smUI.statusFromMastery` conceptually — i.e. assert the source contains the exact comparisons `v < 0.40`, `v < 0.75`, `v < 0.95` and the `attempts` guard. Only if it does not already; do not weaken what's there. — **DONE a Task 14** (assercions afegides a `test_status_thresholds_frozen`).

## Rulings recollits

- **P1** — index.html head links added only in the task that creates the target file.
- **P2** — R10 perf-budget reconciliation moved Task 14 → Task 2.
- **P3 → P3-REVISED** — `test_design_system` PAGES grows incrementally as pages migrate, not all-at-once.
- **T2-a** — base.css token-rename fixups in scope.
- **T4-a** — HeroCard "Tema N" — no invented topic names, KB has none.
- **T4-b** — dashboard HeroCard defensively correct on `rec.target_topic`.
- **T5-a** — fix `aria-busy` at shared-helper level (added `setState` "ready" kind).
- **T8-a** — fix `openEvidence` object-rendering at `ui.js` shared-helper level (provText/formulaText).
- **T10-a** — exams.js page-nav links use `?xsid=` to match exam/results/review; API param `exam_session_id` stays separate.
- **T11-a** — controller applied `#exam-timer` restore directly (mechanical regression, no test).
- **T11-b** — `app/*_benchmark.py` history.js staleness = documented follow-up, not F17 scope.
- **T13-a** — documents.js/calendar.js CA-only accepted out of scope.
- **T13-b** — i18n.js perf ceiling 12→16 KiB accepted (data-only, 14723 B measured).
