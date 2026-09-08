# Fase 14 — Packaging local y arranque portable

Estado: **base implementada**.

## Entregado

- `pyproject.toml` con metadatos del proyecto, Python `>=3.11` y build backend
  setuptools.
- Entry point `sistemes-web` para arrancar la aplicación.
- `python -m web.server` sigue disponible para desarrollo sin instalación.
- Configuración portable mediante `.env.example` y variables:
  `SM_HOST`, `SM_PORT`, `SM_DATA_DIR`, `COURSE_CALENDAR_PATH`,
  `GEMINI_API_KEY` y `GEMINI_MODEL`.
- Argumentos explícitos `--host`, `--port`, `--data-dir` y `--calendar`.
- El packaging incluye HTML, CSS y JavaScript de `web/`.

## Límites

- No se ha generado todavía un instalador Windows ni un contenedor.
- El despliegue multiusuario continúa bloqueado por la deuda de autenticación.
- `.env.example` no contiene secretos; los valores reales deben vivir en `.env`,
  excluido por `.gitignore`.

## Verificación

- `pytest -q tests/test_packaging.py` → 3 passed.
- Ayuda CLI verificada con `python -m web.server --help`.
