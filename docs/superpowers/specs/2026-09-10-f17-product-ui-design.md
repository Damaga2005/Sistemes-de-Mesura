# F17 — Product UI / UX Redesign — Design Spec

**Date:** 2026-09-10 · **Branch:** `feature/f17-product-ui` · **Base:** `v1.0.0` (`a9c153e`)
**Status:** design approved (Sections 1–4), pending user review of this spec before `writing-plans`.

Companion docs: [`docs/F17_UI_AUDIT.md`](../../F17_UI_AUDIT.md) (frontend audit),
[`docs/F17_UI_DESIGN.md`](../../F17_UI_DESIGN.md) (concrete visual language / tokens).

---

## 1. Goal & constraints

Turn the study app's frontend from a "local technical / admin-dashboard / document-viewer"
feel into a **modern, premium, professional educational application**, dark-first with a
violet accent, keeping its own identity (the reference dashboard informs the language, is
not copied).

**Hard constraints (from the F17 brief):**

- No functional backend changes. The **only** backend edit in all of F17 is one line:
  `".woff2": "font/woff2"` added to `_MIME` in `web/server.py` (required to serve the
  self-hosted font).
- No API contract changes, no new endpoints. Everything the new UI needs already exists
  (see audit §5).
- No invented data. Every rendered value comes from a real API field. Sections without
  data are hidden or show an honest empty state.
- Frontend stays vanilla: no framework, no build step, no npm, no new runtime dependency.
- CSRF, focus-visible ring, reduced-motion handling, formula rendering, the
  "presentation layer only — no domain logic in the frontend" invariant: all preserved.
- No commits/merge/tag/release automatically. Branch left ready for review.
- Catalan UI throughout; academic content stays verbatim from the KB.

**Test baseline (F17 §Fase 0):** `889 passed, 1 skipped, 0 failed` (473.99 s). The skip is
`test_home_defaults_under_xdg_on_posix` (POSIX companion, correctly skipped on Windows).
Any post-baseline failure is attributable to F17.

---

## 2. Architecture — Approach A (approved)

**Token re-skin + JS-rendered shell partial.**

- Rewrite `web/static/css/tokens.css` to the dark-first violet system (values in
  `F17_UI_DESIGN.md §1–§3`). `:root` = dark; `@media (prefers-color-scheme: light)` +
  `:root[data-theme="light"]` = light overrides. **No theme toggle ships** (following
  `prefers-color-scheme` only); the `[data-theme]` hook exists for future parity.
- The sidebar + header markup is currently copy-pasted into 11 HTML files. Extract it into
  `web/static/js/shell.js`, which builds the chrome from a **single nav-config array** and
  injects it; each page file becomes just its `<main>`. `shell.js` loads in `<head>`
  **without `defer`** so chrome paints with the page. CSS `grid` reserves the sidebar
  column at every breakpoint → **no layout shift**; worst case nav labels paint ~1 frame
  after the canvas (no worse than today's `Carregant…` content).
- `web/static/css/layout.css` → `shell.css`. New `web/static/css/pages.css` for
  page-specific compositions. `components.css` rewritten/extended.
- `web/static/js/ui.js` (new): shared render helpers — `el()`, `api()`, `setState()`,
  `skeleton()`, `progressBar()`, `progressRing()`, `badge()`, `statusFromMastery()`,
  `openEvidence()` — deduping the copy-pasted helpers in every page JS.
- `app.js` keeps tabs/modal/toast/dropdown; the drawer reuses its focus-trap. Mobile menu
  logic moves into `shell.js`.
- Self-hosted **Inter** variable (`web/static/fonts/InterVariable.woff2`, SIL OFL 1.1,
  `OFL.txt` included). Icon **sprite** `web/static/icons.svg` (~16 icons, Lucide ISC —
  path strings copied, no runtime dep).

Rejected: **B** (server-side shell injection — changes how the certified server renders,
more regression risk) and **C** (re-skin duplicated shell in place — nav defined 11×,
the restructure becomes 11 error-prone edits).

---

## 3. Application shell

### 3.1 Navigation (single config array in `shell.js`)

```
INICI            index.html      home
ESTUDI
  Temari         temari.html     book            (NEW file — topic explorer, from study.html)
  Pràctica       practice.html   target
APRENDRE
  Tutor IA       tutor.html      sparkles        (NEW file — extracted from study.html)
  Progrés        progres.html    chart           (replaces learning.html)
AVALUACIÓ
  Exàmens        exams.html      clipboard-check
```

- **Dropped from main nav:** Documents, Calendari (stubs — F17 §Fase 5); `design-system.html`
  kept as a file, linked only from a small dev footer.
- **Historial** folds into the Exàmens page as a section (backed by `/api/exam/history`), not
  a top-level item.
- **Legacy URLs** `study.html`, `learning.html`, `history.html` become 2-line
  `location.replace` redirect stubs (bookmark compatibility).
- Active state: `shell.js` matches `location.pathname` basename → `aria-current="page"` +
  `.is-active`; parent group gets a subtle marker.

### 3.2 Sidebar / Header / Content

Full specs in `F17_UI_DESIGN.md §5.1–§5.3`. Summary:

- **Sidebar** (≥48rem): sticky, `--surface`, 16rem (17rem ≥80rem), own scroll. Brand `Σ` +
  wordmark. Group overlines + nav items (44px, `--radius-md`, active = `--accent-soft` pill +
  3px `--accent` left bar). Pinned footer = **provider indicator** (§6.3).
- **Header** (all sizes): sticky, 3.5rem, blurred `--bg`, hairline border. `<48rem`:
  hamburger + brand. `≥48rem`: breadcrumbs left, course chip right. **No `localhost` anywhere.**
- **Content**: `<main>` `max-width: var(--content-max)` (72rem), centered. Breadcrumbs →
  `.page-header` (h1 + subtitle + optional `.page-actions`).

### 3.3 Responsive

- `≥48rem`: `[16rem sidebar][main]` grid, sidebar always visible.
- `<48rem`: single column; sidebar → off-canvas drawer (slide from left, backdrop,
  focus-trap + Esc via `app.js`), hamburger toggles.
- Verify no overflow at 1366×768 / 1440×900 / 1600×900 / 1920×1080 (F17 §18/22), especially
  practice/exam question blocks and the chat column.

---

## 4. Pages

Data sources are existing endpoints (audit §5). **Nothing fabricated.**

### 4.1 Inici (`index.html`) — learning dashboard

Answers *"què faig ara?"*.

| Block | Source | Behaviour |
|---|---|---|
| Greeting | client `Date` | "Bon dia / Bona tarda / Bona nit 👋" (time-based, not data) |
| **HeroCard "Continua estudiant"** | `/api/study/next` + `/api/study/mastery` | recommended topic name · progress bar · CTA → `topic.html?topic=N` (or `practice.html` if the action is practice). `recommendation == null` → CTA "Comença pel Temari" |
| **El teu progrés** — 3 StatCards | `/api/learn/progress` | Domini (avg mastery of topics with attempts, ProgressRing) · Precisió (`correct/attempts`) · Preguntes (`attempts`). `attempts == 0` → "—" + "Encara sense dades" |
| **Necessites reforçar** — ≤3 TopicCards | `/api/study/mastery` | lowest-score topics with `attempts > 0`. None → section hidden |
| **Activitat recent** | `/api/learn/progress` `recent[]` | last 5 attempts (unit · correct/incorrect · relative time). Empty → EmptyState + CTA |

### 4.2 Temari (`temari.html`, NEW) — topic explorer

- 10 **TopicCards** from `/api/study/topics` (carries `mastery: {score, attempts}`).
- Card: `Tema N` number chip · title · ProgressBar (only if `attempts > 0`) · **status badge** ·
  meta "X seccions · Y fórmules" · `Obrir tema` → `topic.html?topic=N`.

**Status badge rules** — client-side derivation from real backend `mastery`. Applied only
when `attempts > 0`; `score` = `mastery.score` (0–1 float); **half-open intervals, frozen
here**:

| Condition | Badge label |
|---|---|
| `attempts == 0` or `mastery == null` | `No iniciat` |
| `0 < score < 0.40` | `Reforçar` |
| `0.40 ≤ score < 0.75` | `En progrés` |
| `0.75 ≤ score < 0.95` | `Domini alt` |
| `score ≥ 0.95` | `Completat` |

Rationale: a learning UI answers "what should I do?" better with a label than a raw `37%`.
The rule is 100% derived from real backend numbers. Recorded in `docs/DECISION_LOG.md` (F17
section). Implemented once in `ui.js#statusFromMastery(mastery)` and reused by Temari,
Progrés and the dashboard.

### 4.3 Tema (`topic.html`) — restructured to a learning unit

- Source: `/api/study/documents?topic=N` + `/api/study/sections?doc_id=` (unchanged).
- `Tema N — <name>` · progress bar · **Continguts** as a clean sectioned list/accordion
  (section titles → `content.html?section_id=`), grouped by document but presented as
  contents, not files.
- `.page-actions`: `[Estudiar]` · `[Practicar]` → `practice.html?topic=N` ·
  `[Preguntar al Tutor]` → `tutor.html?topic=N`.
- `content.html` stays the section reader — restyled prose card, **formula rendering
  untouched**, back-to-tema link.

### 4.4 Pràctica (`practice.html`) — restyle, flow unchanged

- Two modes on one page: configured (form) and adaptive (`?from=adaptive`,
  reads `sessionStorage`) — both existing.
- **Config** → compact card (Tema · Tipus · Dificultat · Seed · `[Genera pregunta]`).
- **Question** → single centered column: context strip (`Tema N · Dificultat`) · question
  body (formulas intact) · answer input · `[Enviar]`.
- **Result** → `Correcte ✓` / `Incorrecte ✗` banner (icon + colour, never colour alone) ·
  Explicació · `[Veure evidències]` (drawer) · errors from `enrich_errors` (label + hint +
  band) · `[Continuar]` / `[Acabar]`.
- Endpoints `/api/practice/start|submit|question|result|complete` unchanged.

### 4.5 Tutor IA (`tutor.html`, NEW) — extracted from `study.html`

- Source: `/api/tutor/ask` (`{query, top_k}`).
- Centered conversation column (`--reading-max`) + sticky composer (auto-grow textarea +
  `[Pregunta]`).
- **ChatMessages**: user (right, `--accent-soft`) / tutor (left, `--surface`, `Σ` avatar).
  Formula chips + status line under the tutor message.
- **Loading** = tutor bubble with 3-dot pulse. **Abstain** = distinct bubble + `ABSTAIN`
  badge + reformulate hint. **Error** = alert-style bubble + `[Reintenta]`.
- Post-answer action row: `[Practicar]` (topic from provenance) ·
  `[Explica-ho d'una altra manera]` (re-ask with a rephrase hint) · `[Veure evidències]`
  (drawer).
- `?topic=N` prefills a context line. Conversation is **session-local JS state** — not
  persisted (no backend for it; not faked).

### 4.6 Progrés (`progres.html`, NEW) — replaces `learning.html`

| Block | Source | Notes |
|---|---|---|
| **Resum** — StatCards | `/api/learn/progress` | Preguntes · Precisió · Unitats treballades · Última activitat. `attempts == 0` → whole-page empty state + "[Comença una pràctica]" |
| **Domini per tema** | `/api/study/mastery` | 10 rows: name + ProgressBar + status badge (same `statusFromMastery`). `attempts == 0` → "No iniciat", not 0% |
| **Recomanat per a tu** — RecommendationCards | `/api/learn/priorities?limit=3` | `unit` · `action_label` · **human `reasons_display`** (label + value_label — already provided by `project_rec`) · `difficulty` badge · `[Començar]` → `/api/learn/start` (existing). Projection already omits `priority`/`policy_id`/`seed`/weights — UI shows labels only |
| **Errors freqüents** | priorities `errors[]` | `label ×count`. Only if present |
| **Detall d'unitat** | `/api/learn/unit` | existing drill-down as an expandable panel (events timeline restyled), not front-and-center |

### 4.7 Exàmens (`exams.html`) — restyle + absorb Historial

- **Els meus exàmens** — cards from `/api/exam/mine`: title · kind badge · state (READY /
  IN_PROGRESS / SUBMITTED / GRADED) · contextual action → `exam.html` / `results.html` /
  `review.html`.
- **Historial** — folded in from `history.html` via `/api/exam/history` (exam · result ·
  date · `[Revisar]`), as a section/tab.
- **Nou examen** — config card restyled (Tipus · Temes · Nº · Tipus pregunta · Dificultat ·
  Durada · Seed · `[Crea i prepara]`), immutability hint kept.
- `exam.html` / `results.html` / `review.html` — reshell + retoken only; **timer &
  blind-review contract untouched**. Lower priority (F17 §Fase 14).

---

## 5. Cross-cutting

### 5.1 Loading / Error / Empty (F17 §15)

- **Loading**: `ui.js` `skeleton(kind)` — `--card` / `--text` / `--list` silhouettes on
  every async region (no "Carregant…" text). Inline spinner only for buttons (`[Pensant…]`).
- **Error**: `.state-block` — `△`, "No hem pogut carregar les dades.", `[Reintenta]` wired
  to re-run the fetch, optional muted error code. **No stack traces.**
- **Empty**: `.state-block` — `○`, context copy, primary CTA.

### 5.2 Evidence drawer (F17 §12)

`ui.js#openEvidence({provenance, formulas})` → right-side `.drawer` reusing `app.js`
focus-trap + Esc + backdrop + focus restore. Shows provenance (Tema N · section title),
cited formulas (`equation_id`), a "Contingut verificat" trust line. Only via
`[Veure evidències]` — never inline-permanent. Data already in `/api/tutor/ask` + practice
result; no backend change.

### 5.3 Gemini UX (F17 §16)

Provider indicator = dot + label, **sidebar footer**, from `versions.provider`
(`{provider, model}`) cached from the last `/api/tutor/ask`:

| `provider` | Label | Dot |
|---|---|---|
| `gemini` | `Tutor: Gemini` | `--accent` |
| `extractive-fallback` | `Tutor: local (fallback)` + tooltip "Resposta verificada del contingut local" | `--warning` |
| `extractive` | `Tutor: local` | `--text-tertiary` |
| (before any call) | `Tutor: preparat` | `--text-tertiary` |

Never shows API key / endpoint / params beyond model name. Never claims Gemini when the
response says otherwise. Tutor error bubble = "El tutor no està disponible ara mateix." +
retry, no technical detail.

### 5.4 Català glossary (F17 §17)

*Inici · Estudi · Temari · Pràctica · Tutor IA · Progrés · Exàmens · Continuar estudiant ·
Començar pràctica · Veure evidències · Necessites reforçar · En progrés · Domini alt ·
No iniciat · Completat · Reforçar · Recomanat per a tu · Reintenta.* Chrome + nav all `ca`;
academic content verbatim from the KB.

### 5.5 Accessibility (F17 §19)

Skip-link, `nav`/`main`/`header` landmarks, `aria-current`, **3px focus-visible ring
unchanged**, 44px targets, drawer/modal focus-trap + restore, `aria-expanded` toggles,
result/status by icon+text not colour alone, `aria-live` on async regions, global
`prefers-reduced-motion`. Violet accent + text tokens verified WCAG AA both themes
(`F17_UI_DESIGN.md §6`).

### 5.6 `<progress>` → `role="progressbar"`

`<div class="progress" role="progressbar" aria-valuenow aria-valuemin aria-valuemax
aria-label>` with a styled fill span. Cross-browser styleable, rounded gradient fill,
optional label.

---

## 6. Backend / API impact

- **One line**: `".woff2": "font/woff2"` in `web/server.py` `_MIME`.
- Zero API contract changes, zero new endpoints, zero domain-logic touch.
- `python -m app.cli check` + `check --status` must stay exit 0 (F17 touches only `web/` —
  no artifact / manifest / KB impact).

---

## 7. Testing (F17 §21/26) — priority: 0 regressions

No existing test deleted or weakened. New tests are Python (no JS test tooling added):

1. `tests/web/test_static_assets.py` (NEW) — `.woff2` → `font/woff2` 200; `icons.svg` 200;
   `temari.html` / `tutor.html` / `progres.html` → 200 `text/html`; `study.html` /
   `learning.html` / `history.html` still 200 (redirect stubs).
2. `tests/web/test_api_contract_f17.py` (NEW) — smoke that UI-relied endpoints keep their
   documented keys (`study/topics[].mastery`, `learn/priorities` projected keys,
   `learn/progress` shape, `tutor/ask` → `versions.provider`) **and still omit
   `priority` / `policy_id` / `seed`**.
3. All existing `tests/web/*` green.

Per implementation block: `pytest tests/web/ -q` + touched area. At verification: full suite
vs the 889 / 1-skip baseline; `app check` + `check --status` exit 0.

---

## 8. Deliverable docs

- `docs/F17_UI_AUDIT.md` (§Fase 1) — done.
- `docs/F17_UI_DESIGN.md` (§Fase 3) — done.
- This spec — committed before `writing-plans`.
- `docs/F17_BEFORE_AFTER.md` (§Fase 24) + `docs/F17_IMPLEMENTATION.md` (§Fase 25) — at the end.
- `docs/DECISION_LOG.md` — new "F17" section: dark-first violet theme; self-hosted Inter
  (+ `.woff2` MIME line); frozen status-badge thresholds; nav restructure / dropped stubs.

---

## 9. Implementation order (feeds `writing-plans`)

1. Font + icons + `_MIME` line + `tokens.css` rewrite.
2. `shell.js` + `shell.css` + nav config; migrate one page (`index.html`) to the injected shell.
3. `components.css` rewrite + `ui.js` helpers.
4. Inici dashboard.
5. Temari.
6. Tema + content restyle.
7. Pràctica.
8. Tutor IA.
9. Progrés.
10. Exàmens (+ Historial fold, redirect stubs).
11. exam/results/review reshell.
12. Loading/error/empty pass + evidence drawer + provider indicator.
13. Responsive + a11y + visual QA (screenshots 1366/1440/1920).
14. `F17_BEFORE_AFTER.md` + `F17_IMPLEMENTATION.md`; full suite; code review.

Each block: implement → `pytest tests/web/ -q` + touched area → visual check → fix before next.
