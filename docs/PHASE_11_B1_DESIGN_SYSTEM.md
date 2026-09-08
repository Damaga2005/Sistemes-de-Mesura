# PHASE_11_B1_DESIGN_SYSTEM — Tokens, componentes y decisiones

## Principios (B1.2)

Claridad, jerarquía, contenido primero, espacio, consistencia,
feedback inmediato, baja carga cognitiva, accesibilidad, responsive,
cero decoración. Sin gradients/glass/sombras fuertes/gamificación.

## Tokens (B1.3, `tokens.css`)

13 colores semánticos, 9 tamaños + alturas/pesos, 7 espaciados,
4 radios, 3 sombras, motion (fast/normal/slow + 2 easings),
touch 44px, content 72rem, breakpoints 48/64/80rem. **Dark mode
implementado completo** vía `prefers-color-scheme` (mismo set
semántico, pares de contraste seguros; no parcial).

## Componentes (B1.4–B1.5)

26 primitivas en `components.css`, 0 colores hardcoded (test),
estados default/hover/focus/active/disabled/loading/error/success
donde aplica; error nunca solo-color (texto+vora).

## Shell y navegación (B1.8–B1.11)

Header sticky + sidebar (drawer en móvil, `aria-expanded`) + page
container (breadcrumb/header/actions). Nav: Home/Study/Learning/
Exams/Documents(properament)/Calendar(properament); `aria-current`
en las 6 de producto. Sin auth (D de B0).

## Estados (B1.13–B1.15)

EMPTY vs NOT_IMPLEMENTED vs UNAVAILABLE distinguidos con texto
honesto (documents=B, calendar=C). Errores 400–500 + ABSTAIN +
VALIDATION como presentación de códigos backend existentes (cero
códigos nuevos). Loading: spinner/skeleton/button; skeletons sin
bloqueo global; `aria-live` en toasts.

## Iconos, idioma, fórmulas (B1.16–B1.19)

SVG inline (menú; resto texto+badge, nunca icono solo). Catalán
(`lang="ca"`), español preparado sin framework. Fórmulas: estilos
sub/sup + contenedor con scroll + convención `data-tex`; sin librería
(designa B2; fuente canónica intacta).

## Seguridad y no-duplicación (B1.21/B1.23)

Auditoría por test: 0 `score/mastery/grade/adaptive/correct_answer/
formula_validation`, 0 SQL/sqlite, 0 secretos/paths/traces. CSS no
oculta nada sensible (no hay nada sensible en B1).
