# F17 — UI Design System (visual language)

**Fase:** F17 §Fase 3 deliverable · **Branch:** `feature/f17-product-ui` · **Base:** `v1.0.0`
**Estil:** dark‑first, accent violeta. Adapta el llenguatge d'un dashboard educatiu fosc —
**no el copia**. Vanilla CSS, sense framework ni build. Re‑skin de
`web/static/css/tokens.css` + `components.css` + `shell.css` (era `layout.css`).

Aquest document fixa els **valors concrets**. La resta de F17 (shell, pàgines) s'hi
refereix; els tokens no es tornen a decidir durant la implementació.

---

## 1. Color

### 1.1 Tema fosc (primari — `:root`)

| Token | Valor | Ús |
|---|---|---|
| `--bg` | `#131118` | llenç de la pàgina (negre càlid violaci, **mai `#000`**) |
| `--surface` | `#1a1822` | targetes, sidebar |
| `--surface-elevated` | `#221f2e` | hover, dropdown, drawer, modal |
| `--surface-sunken` | `#0e0d13` | fons d'inputs, pista de progress |
| `--overlay` | `rgb(10 8 16 / 0.60)` | backdrop de modal/drawer |
| `--border` | `#2a2735` | filet hairline |
| `--border-strong` | `#3b3750` | vora d'input, vora de targeta interactiva |
| `--text-primary` | `#f3f1f9` | text principal |
| `--text-secondary` | `#a7a3b8` | text secundari (AA normal sobre `--surface`) |
| `--text-tertiary` | `#726e85` | metadades no essencials (**només ≥h3‑bold o UI**, mai body) |
| `--text-on-accent` | `#ffffff` | text sobre `--accent` |
| `--accent` | `#6f4bff` | acció primària, estat actiu (ratio 4.7:1 vs blanc → AA normal) |
| `--accent-hover` | `#825fff` | hover d'acció primària |
| `--accent-pressed` | `#5d3ae6` | active/pressed |
| `--accent-soft` | `rgb(111 75 255 / 0.16)` | pill de nav actiu, fons de xip, bombolla d'usuari |
| `--accent-border` | `rgb(111 75 255 / 0.38)` | vora de HeroCard/RecommendationCard |
| `--accent-contrast-text` | `#c9bbff` | text/enllaç violaci sobre fosc (8:1 vs `--surface`) |
| `--success` / `--success-soft` / `--success-text` | `#3ddc97` / `rgb(61 220 151 / 0.15)` / `#5fe3ab` | correcte, Domini alt |
| `--warning` / `--warning-soft` / `--warning-text` | `#f2b53c` / `rgb(242 181 60 / 0.15)` / `#f5c463` | Reforçar, fallback del tutor |
| `--danger` / `--danger-soft` / `--danger-text` | `#fb6f6f` / `rgb(251 111 111 / 0.15)` / `#fd8a8a` | incorrecte, error |
| `--info` / `--info-soft` / `--info-text` | `#5ca8ff` / `rgb(92 168 255 / 0.15)` / `#82bcff` | En progrés, avisos neutres |
| `--focus` | `#9b83ff` | anell de focus (3px solid, offset 2px — **sense canvis respecte v1.0.0**) |

**Gradients** (ús mesurat):
- `--gradient-accent: linear-gradient(135deg, #6f4bff 0%, #9d7bff 100%)` — vora de HeroCard, traç de ProgressRing, marca `Σ`.
- `--gradient-surface: linear-gradient(180deg, #1e1b28 0%, #1a1822 100%)` — farciment subtil de HeroCard.

**Ombres** (fosc: l'elevació la fan `surface` + `border`; l'ombra només per a capes flotants):
- `--shadow-sm: 0 1px 2px rgb(0 0 0 / 0.40)`
- `--shadow-md: 0 10px 30px -8px rgb(0 0 0 / 0.50)` — dropdown, popover
- `--shadow-lg: 0 24px 60px -12px rgb(0 0 0 / 0.60)` — modal, drawer
- `--shadow-accent-glow: 0 0 0 1px var(--accent-border), 0 8px 32px -8px rgb(111 75 255 / 0.35)` — HeroCard, hover de CTA primari

### 1.2 Tema clar (secundari)

Overrides sota `@media (prefers-color-scheme: light) { :root { … } }` **i** `:root[data-theme="light"]`
(paritat per si més endavant s'afegeix un toggle; F17 **no** n'inclou cap).

| Token | Valor |
|---|---|
| `--bg` | `#f5f4fa` (blanc trencat amb tint lavanda) |
| `--surface` / `--surface-elevated` | `#ffffff` / `#ffffff` |
| `--surface-sunken` | `#efedf6` |
| `--overlay` | `rgb(28 24 44 / 0.40)` |
| `--border` / `--border-strong` | `#e7e4f0` / `#d4cfe3` |
| `--text-primary` / `--text-secondary` / `--text-tertiary` | `#1c1a29` / `#57536b` / `#8b8799` |
| `--accent` / `--accent-hover` / `--accent-pressed` | `#6a45f0` / `#7a58f5` / `#5b39d6` (5.9:1 vs blanc) |
| `--accent-soft` / `--accent-border` / `--accent-contrast-text` | `rgb(106 69 240 / 0.10)` / `rgb(106 69 240 / 0.28)` / `#5b39d6` |
| `--success` / `--warning` / `--danger` / `--info` | `#12996b` / `#b5730a` / `#d64545` / `#2563c9` (base = text; `*-soft` = mateix to a 0.12) |
| `--focus` | `#6a45f0` |
| `--shadow-sm` | `0 1px 2px rgb(60 50 110 / 0.08)` |
| `--shadow-md` | `0 10px 30px -8px rgb(60 50 110 / 0.14)` |
| `--shadow-lg` | `0 24px 60px -12px rgb(60 50 110 / 0.20)` |
| `--shadow-accent-glow` | `0 0 0 1px var(--accent-border), 0 10px 30px -8px rgb(106 69 240 / 0.25)` |

---

## 2. Tipografia — Inter, self‑hosted

```css
@font-face {
  font-family: "Inter";
  src: url("../fonts/InterVariable.woff2") format("woff2");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}
```

- Fitxer: `web/static/fonts/InterVariable.woff2` (variable, roman; ~350 KB). Llicència **SIL OFL 1.1**
  → s'inclou `web/static/fonts/OFL.txt`. Cal afegir `".woff2": "font/woff2"` a `_MIME` de `web/server.py`
  (**l'única línia de backend de tot F17**).
- `--font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;`
- `--font-mono`: **sense canvis** (`ui-monospace, "SF Mono", Menlo, Consolas, monospace`) — el renderitzat de fórmules a `base.css` no es toca.
- `body { font-feature-settings: "cv05" 1, "cv11" 1, "ss01" 1; }` — `l` inequívoca, `a` d'un pis.

### Escala (root 16px)

| Token | Mida | Line‑height | Pes | Tracking | Ús |
|---|---|---|---|---|---|
| `--fs-display` | 1.75rem | 1.2 | 700 | −0.02em | salutació del dashboard, títol de HeroCard |
| `--fs-h1` | 1.375rem | 1.25 | 640 | −0.015em | títol de pàgina |
| `--fs-h2` | 1.0625rem | 1.3 | 600 | −0.01em | títol de secció |
| `--fs-h3` | 0.9375rem | 1.35 | 600 | 0 | títol de targeta |
| `--fs-body` | 0.9375rem | 1.6 | 400 | 0 | text |
| `--fs-body-lg` | 1rem | 1.6 | 400 | 0 | respostes del tutor, prosa acadèmica |
| `--fs-meta` | 0.8125rem | 1.45 | 500 | 0 | metadades, captions |
| `--fs-overline` | 0.6875rem | 1.4 | 600 | 0.08em | etiquetes de grup de nav (uppercase) |
| `--fs-stat` | 2rem | 1.1 | 700 | −0.02em | xifres de StatCard (`tabular-nums`) |

Pesos: `--fw-regular 400 · --fw-medium 500 · --fw-semibold 600 · --fw-h1 640 · --fw-bold 700`.
`font-variant-numeric: tabular-nums` a tota xifra de mètrica/estadística.

---

## 3. Espaiat · radi · layout · moviment

**Espaiat** (escala 4px existent + `2xs`):
`--sp-2xs .125 · --sp-xs .25 · --sp-sm .5 · --sp-md 1 · --sp-lg 1.5 · --sp-xl 2 · --sp-2xl 3 · --sp-3xl 4` (rem)

**Layout:**
`--sidebar-w 16rem · --sidebar-w-wide 17rem · --header-h 3.5rem · --content-max 72rem · --reading-max 46rem`

**Radi:** `--radius-xs 6px · --radius-sm 8px · --radius-md 12px · --radius-lg 16px · --radius-xl 22px · --radius-full 999px`
- inputs/botons → `md` · targetes → `lg` · hero/modal/drawer → `xl` · badges → `full` · xip de número de tema → `sm`

**Moviment** (sense canvis respecte v1.0.0):
`--duration-fast 120ms · --duration-normal 200ms · --duration-slow 320ms`
`--ease-standard cubic-bezier(.2,0,0,1) · --ease-emphasized cubic-bezier(.05,.7,.1,1)`
- pill de nav: bg/color `fast` · hover de targeta (`translateY(-2px)` + border + shadow) `normal` · slide de drawer `slow`/`emphasized` · shimmer de skeleton `1.4s linear infinite`
- `@media (prefers-reduced-motion: reduce)` ja neutralitza animacions/transicions globalment a `base.css` — **es manté**. Skeleton i indicador d'escriptura tenen fallback estàtic.

---

## 4. Iconografia — una família, sprite SVG

`web/static/icons.svg` (símbols, viewBox 24×24, `stroke="currentColor"` 1.5px, `fill="none"`, `stroke-linecap/linejoin="round"`).
Ús: `<svg class="icon"><use href="static/icons.svg#home"></use></svg>`. `.svg` ja és a `_MIME`.

Set (~16): `home · book · target · sparkles · chart · clipboard-check · chevron-right · menu · close · check · x · alert-triangle · info · external-link · arrow-right · dot`.
Path data adaptat de **Lucide** (llicència ISC — strings copiats, sense dependència de runtime; nota al capçal del fitxer).

---

## 5. Components

Notació: **N** = nou · **R** = re‑estilitzat (classe existent). Tots amb tokens; cap estat només‑color.

### 5.1 Sidebar (R)
`position:sticky; top:0; height:100dvh; width:var(--sidebar-w)` (17rem ≥80rem); `background:var(--surface); border-right:1px solid var(--border); display:flex; flex-direction:column`.
- **Marca:** padding `--sp-lg var(--sp-md)`; `Σ` 1.75rem quadrat, `--radius-sm`, `background:var(--gradient-accent); color:#fff; font-weight:700` + wordmark `--fs-h3`/600.
- **Nav:** `flex:1; overflow-y:auto; padding:var(--sp-sm)`.
- **Etiqueta de grup:** `--fs-overline`, uppercase, `--text-tertiary`, padding `--sp-md var(--sp-sm) var(--sp-2xs)`.
- **Ítem** (`a.nav-link`): `display:flex; align-items:center; gap:var(--sp-sm); min-height:44px; padding:var(--sp-sm) var(--sp-md); border-radius:var(--radius-md); color:var(--text-secondary); font-weight:500`. Icona 20px, `opacity:.85`.
  - hover: `background:var(--surface-elevated); color:var(--text-primary)`.
  - `[aria-current="page"]`: `background:var(--accent-soft); color:var(--accent-contrast-text); font-weight:600; box-shadow:inset 3px 0 0 var(--accent)`; icona `opacity:1; color:var(--accent)`.
- **Peu (indicador de proveïdor):** fixat a baix, `border-top:1px solid var(--border); padding:var(--sp-md); font-size:var(--fs-meta); color:var(--text-tertiary)`. Punt = cercle 8px `background:currentColor`, color segons estat (`--accent` Gemini / `--warning` fallback / `--text-tertiary` local o preparat). Substitueix el peu "capa de presentació BX".

### 5.2 Header (R)
`position:sticky; top:0; z-index:50; height:var(--header-h); display:flex; align-items:center; gap:var(--sp-md); padding:0 var(--sp-lg); background:color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter:blur(8px); border-bottom:1px solid var(--border)`. Fallback sense `backdrop-filter`: `background:var(--bg)`.
- **Hamburger** (`.icon-button`, <48rem): 44px, `--radius-md` (quadrat‑arrodonit, més "app"), `border:1px solid var(--border)`, hover `--surface-elevated`. Ocult ≥48rem.
- **Breadcrumbs:** `--fs-meta`, `--text-tertiary`; separador `/` via `::before`; actual `--text-secondary`.
- **Slot dret:** xip de curs — `.pill` neutre, `--fs-meta`, `--text-tertiary`. **Sense `localhost` enlloc.**

### 5.3 PageHeader (R)
`margin-bottom:var(--sp-xl)`. h1 `--fs-h1`. Subtítol `--fs-body`, `--text-secondary`, `max-width:var(--reading-max)`. `.page-actions`: flex, gap `--sp-sm`, `margin-top:var(--sp-md)`.

### 5.4 Card (R)
`background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-lg); padding:var(--sp-lg); transition:border-color,transform,box-shadow var(--duration-normal) var(--ease-standard)`.
- Sense ombra per defecte en fosc; en clar, `--shadow-sm`.
- **Interactiva** (`a.card`, `.card--link`): hover `transform:translateY(-2px); border-color:var(--border-strong); box-shadow:var(--shadow-md)`.
- `.card__title` = `--fs-h3` · `.card__meta` = `--fs-meta`/`--text-tertiary`.

### 5.5 HeroCard (N)
`position:relative; border-radius:var(--radius-xl); padding:var(--sp-xl); background:var(--gradient-surface); border:1px solid var(--accent-border); overflow:hidden`.
- Vora en gradient via `::before` amb `mask-composite:exclude` (filet `--gradient-accent`, `opacity:.5`). Fallback: `--accent-border` pla.
- Decoració opcional: `radial-gradient(600px circle at 100% 0%, rgb(111 75 255 / 0.12), transparent 60%)`.
- Eyebrow `--fs-overline` uppercase `--accent-contrast-text` · títol `--fs-display` · ProgressBar + etiqueta · CTA `.button` (primari) `.button--lg`.

### 5.6 TopicCard (N)
`.card--link`; `display:flex; flex-direction:column; gap:var(--sp-sm)`.
- Fila superior: **xip de número** (`.chip-num`: `min-width:1.75rem; height:1.75rem; display:inline-flex; align-items:center; justify-content:center; border-radius:var(--radius-sm); background:var(--accent-soft); color:var(--accent-contrast-text); font-weight:700; font-size:var(--fs-meta)`) + **status badge** (`margin-left:auto`).
- Títol `--fs-h3` (clamp 2 línies) · ProgressBar (**només si `attempts>0`**) · meta "X seccions · Y fórmules" `--fs-meta`/`--text-tertiary` · afordança "Obrir tema →" `--accent-contrast-text` `--fs-meta`/600 (o tota la targeta és l'enllaç).

### 5.7 StatCard (N)
`.card; padding:var(--sp-lg); display:flex; flex-direction:column; gap:var(--sp-2xs)`.
- Icona opcional en quadrat `--accent-soft` 28px, `--radius-sm`.
- Valor `--fs-stat` `tabular-nums` `--text-primary` · etiqueta `--fs-meta` `--text-secondary` · línia de context opcional `--fs-meta` `--text-tertiary` ("—" quan no hi ha dades; **mai un delta inventat**).

### 5.8 RecommendationCard (N)
`.card` amb tint: `border-color:var(--accent-border); background:linear-gradient(180deg, var(--accent-soft), transparent 40%), var(--surface)`.
- Eyebrow "Recomanat per a tu" `--fs-overline` `--accent-contrast-text` · títol (`unit`) `--fs-h3` · línies de motiu (`reasons_display` → `label: value_label`) `--fs-body` `--text-secondary` amb `•`/check al davant · badge de dificultat (`.badge--neutral`) · CTA `[Començar]` primari.

### 5.9 Button (R)
Base: `display:inline-flex; align-items:center; justify-content:center; gap:var(--sp-sm); min-height:44px; padding:var(--sp-sm) var(--sp-lg); font:600 var(--fs-body)/1 var(--font-sans); border-radius:var(--radius-md); border:1px solid transparent; cursor:pointer; transition:background var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast)`.

| Variant | Estil |
|---|---|
| `--primary` (defecte) | `background:var(--accent); color:var(--text-on-accent)` · hover `background:var(--accent-hover); box-shadow:var(--shadow-accent-glow)` · active `background:var(--accent-pressed); transform:translateY(1px)` |
| `--secondary` | `background:var(--surface-elevated); color:var(--text-primary); border-color:var(--border-strong)` · hover `border-color:var(--accent-border); background:var(--surface)` |
| `--ghost` | `background:transparent; color:var(--accent-contrast-text)` · hover `background:var(--accent-soft)` |
| `--danger` | `background:var(--danger); color:#fff` |
| `--lg` | `min-height:52px; padding:var(--sp-md) var(--sp-xl); font-size:var(--fs-body-lg)` |

disabled `opacity:.45; cursor:not-allowed` · `[data-loading]` `cursor:progress; opacity:.75` · focus‑visible: anell global 3px.

### 5.10 Badge (R + status variants)
Base: `display:inline-flex; align-items:center; gap:var(--sp-xs); font:600 var(--fs-meta)/1 var(--font-sans); padding:.2rem .6rem; border-radius:var(--radius-full); border:1px solid transparent`. Punt capçalera 6px `background:currentColor`.

| Classe | Etiqueta | bg | text | border |
|---|---|---|---|---|
| `.badge--status-none` | No iniciat | `--surface-elevated` | `--text-tertiary` | `--border` |
| `.badge--status-reinforce` | Reforçar | `--warning-soft` | `--warning-text` | transparent |
| `.badge--status-progress` | En progrés | `--info-soft` | `--info-text` | transparent |
| `.badge--status-high` | Domini alt | `--success-soft` | `--success-text` | transparent |
| `.badge--status-complete` | Completat | `--accent-soft` | `--accent-contrast-text` | transparent |

Sempre punt + etiqueta de text → **mai només color**.

### 5.11 ProgressBar (N — substitueix `<progress>`)
```html
<div class="progress" role="progressbar" aria-valuenow="X" aria-valuemin="0"
     aria-valuemax="100" aria-label="…"><span class="progress__fill" style="width:X%"></span></div>
```
- Pista: `height:.5rem; background:var(--surface-sunken); border-radius:var(--radius-full); overflow:hidden`.
- Farciment: `height:100%; border-radius:inherit; background:var(--gradient-accent); transition:width var(--duration-slow) var(--ease-emphasized)`.
- Modificadors: `.progress--sm` (`.375rem`), `.progress--labeled` (valor `--fs-meta` al costat).

### 5.12 ProgressRing (N)
SVG ~120px. 2 `<circle>` (pista + valor), `stroke-width:10`, `stroke-linecap:round`, `transform:rotate(-90deg)`.
Pista `stroke:var(--surface-sunken)`; valor `stroke:url(#ringGradient)` (`<linearGradient>` accent→`#9d7bff`).
`stroke-dasharray = C`; `stroke-dashoffset = C·(1−pct)`; transició a `stroke-dashoffset` `--duration-slow`.
Centre: valor `--fs-h1` + etiqueta `--fs-meta`. `role="img"` + `aria-label`. Reduced‑motion: sense transició.

### 5.13 ChatMessage (N)
`.chat`: `display:flex; flex-direction:column; gap:var(--sp-md); max-width:var(--reading-max); margin-inline:auto`.
`.chat__msg`: `display:flex; gap:var(--sp-sm); align-items:flex-start`.
- `--user`: `flex-direction:row-reverse`; bombolla `background:var(--accent-soft); color:var(--text-primary); border:1px solid var(--accent-border)`.
- `--tutor`: avatar `Σ` 1.75rem `--radius-sm` `--gradient-accent`; bombolla `background:var(--surface); border:1px solid var(--border); border-top-left-radius:var(--radius-xs)`.
- Bombolla: `padding:var(--sp-md); border-radius:var(--radius-lg); font-size:var(--fs-body-lg); line-height:1.6; max-width:85%`.
- Sota la bombolla del tutor: xips de fórmula (mono) + línia d'estat `--fs-meta`.
- Indicador d'escriptura: 3 punts amb pulse d'opacitat; reduced‑motion → "…" estàtic.
- Fila d'accions: `.button--ghost`/`--secondary`, `--fs-meta`, `flex-wrap`.

### 5.14 EvidenceDrawer (N)
`.drawer`: `position:fixed; inset:0 0 0 auto; width:min(28rem,100vw); height:100dvh; background:var(--surface-elevated); border-left:1px solid var(--border); box-shadow:var(--shadow-lg); transform:translateX(100%); transition:transform var(--duration-slow) var(--ease-emphasized); z-index:80; display:flex; flex-direction:column`.
- `.drawer:not([hidden])` / `[data-open]` → `transform:translateX(0)`.
- `.drawer__backdrop`: `position:fixed; inset:0; background:var(--overlay); z-index:79`.
- Capçalera: títol "Evidència" `--fs-h2` + tancar `.icon-button`. Cos: `overflow-y:auto; padding:var(--sp-lg)` — llista de proveninstància (Tema N · secció), xips de fórmula, línia "Contingut verificat" amb check `--success-text`.
- Focus‑trap + Esc + restauració de focus **compartits amb el modal** (`app.js`). Reduced‑motion: sense slide.

### 5.15 Modal (R)
`.modal`: `background:var(--surface-elevated); border:1px solid var(--border); border-radius:var(--radius-xl); box-shadow:var(--shadow-lg); max-width:32rem; padding:var(--sp-xl)`. Backdrop `var(--overlay)`.

### 5.16 Skeleton (R)
`.skeleton`: `background:linear-gradient(90deg, var(--surface) 0%, var(--surface-elevated) 50%, var(--surface) 100%); background-size:200% 100%; animation:shimmer 1.4s linear infinite; border-radius:var(--radius-sm)`.
Composicions: `.skeleton--text` (.8rem, últim fill 60%), `.skeleton--title` (1.25rem, 40%), `.skeleton--card` (títol + 3 línies + barra), `.skeleton--stat`.
Reduced‑motion: `--surface-elevated` estàtic, sense animació.

### 5.17 Alert (R)
`.alert`: `border:1px solid var(--border); border-left-width:3px; border-radius:var(--radius-md); padding:var(--sp-md); background:var(--surface)`.
Variants → `border-left-color` + icona: `--success` / `--warning` / `--danger` / `--info` (`background:var(--*-soft)` opcional).
`.alert strong` = `--fs-h3` · `.alert p` = `--text-secondary`.

### 5.18 state-block — loading / error / empty (R)
`.state-block`: `text-align:center; padding:var(--sp-2xl) var(--sp-md); max-width:28rem; margin-inline:auto`.
- Icona 2.5rem dins d'un quadrat `--surface-elevated` `--radius-lg` 3.5rem — `○` buit · `△` error · spinner loading.
- Títol `--fs-h2` · text `--fs-body` `--text-secondary` · CTA primari (`[Reintenta]` / `[Comença a estudiar]`).
- Error: `.state-code` opcional `--fs-meta` `--font-mono` `--text-tertiary`. **Mai stack traces.**

### 5.19 Formula (sense canvis)
`.formula` i familia romanen a `base.css` tal qual (ja usen tokens). Verificar contrast del mono sobre el nou `--surface` fosc (OK, ~14:1).

---

## 6. Accessibilitat (contrast AA)

- **Fosc:** `--text-primary` sobre `--surface` ≈ 14:1 · `--text-secondary` ≈ 6.5:1 (AA normal) · `--text-tertiary` ≈ 3.4:1 → **només UI/large o meta no essencial** · `--accent-contrast-text` ≈ 8:1 · text blanc sobre `--accent` `#6f4bff` ≈ 4.7:1 (AA normal).
- **Clar:** `--accent` `#6a45f0` vs blanc ≈ 5.9:1 · `--text-secondary` vs blanc ≈ 7:1 · `--text-tertiary` ≈ 3.5:1 (mateixa regla).
- Anell de focus: 3px solid `--focus` + offset 2px — **sense canvis respecte v1.0.0**.
- Status: sempre punt + etiqueta, mai només color. Resultats de pràctica: icona ✓/✗ + color + text.
- Tot element interactiu ≥ 44px (`--touch-min: 44px` es manté).
- `prefers-reduced-motion`: neutralització global existent + fallbacks estàtics (skeleton, ring, typing).

---

## 7. Fitxers afectats

```
web/static/css/tokens.css       reescrit (§1–§3)
web/static/css/base.css         només: var de font + feature-settings; .formula intacte
web/static/css/shell.css        NOU (era layout.css) — sidebar/header/content/responsive
web/static/css/components.css   reescrit/ampliat (§5)
web/static/css/pages.css        NOU — composicions per pàgina
web/static/fonts/InterVariable.woff2   NOU  + OFL.txt
web/static/icons.svg            NOU (§4)
web/server.py                   + 1 línia: ".woff2": "font/woff2" a _MIME
```

**Impacte de backend: 1 línia.** Cap canvi de contracte d'API.
