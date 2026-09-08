# PHASE_11_B1_BASELINE — Punto de partida (sin tocar F0–F10)

## Stack elegido (B1.1)

**Opción A: HTML estático + CSS + JS vanilla, 0 dependencias.**
Descartadas: B (Flask/Jinja: servidor innecesario para B1; añade
despliegue sin valor) y C (framework: peso y complejidad injustificados
para app personal). Puente futuro B2+: `stdlib http.server` en proceso
contra `app/application/` (sin Flask). Python 3.14, `http.server` OK.

## Alcance creado (solo `web/` + `tests/web/`, nuevos)

7 páginas (index, study, learning, exams, documents, calendar,
design-system), 4 CSS, 1 JS (52 KB totales). 0 ficheros F0–F10
tocados; 0 tablas; 0 KB/eval/manifest.
