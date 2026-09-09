# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).

## [1.0.0] - 2026-09-09

### Added
- CLI unica `sistemes` (`init`, `serve`, `ingest`, `check`, `backup`, `restore`).
- Cargador `.env` y directorios configurables (`SM_HOME` + datos/index/logs/config/backups).
- Identidad de estudiante por `SM_STUDENT`.
- Migraciones de esquema SQLite forward-only (`PRAGMA user_version`).
- Copia de seguridad y restauracion online de las SQLite escribibles.
- Verificacion de integridad de artefactos (`sistemes check`) y gate de arranque en `serve`.
- Logs estructurados rotados (`serve.log`, `error.log`).
- Health check `GET /api/health`, limites de tamano de cuerpo y timeout de peticion.
- Proteccion CSRF (double-submit cookie) en la API.
- Instalacion reproducible: `scripts/install.ps1` (venv + `pip install -e .`).
- Integracion de Gemini como proveedor del tutor: `sistemes serve --provider auto|gemini|extractive` (o env `SM_PROVIDER`, defecto `auto`). `auto` sin `GEMINI_API_KEY` usa el proveedor extractivo determinista. Validado end-to-end contra el servidor local (respuesta real de `gemini-3.5-flash-lite`, `status=VERIFIED`).

### Changed
- Identidad de estudiante desde `SM_STUDENT` (default `me`); se elimina `DEMO_STUDENT`.
- Version oficial `1.0.0`, leida de `pyproject.toml` por el packaging (`scripts/package.ps1`).
- El tutor deja de tener `ExtractiveProvider` cableado: usa `select_provider(...)`.

### Fixed
- `ReasoningEngine._reason`: un `RuntimeError` del proveedor LLM (red, 5xx/4xx, clave invalida) degrada a extractivo verificado (`versions.provider.provider = "extractive-fallback"`, `fallback_reason`) en vez de propagar como `GENERATION_ERROR`/HTTP 502. Los errores de programacion siguen propagando.
- `mastery._now()` usa resolucion de microsegundos: con resolucion de segundo, varios `submit()` del mismo segundo colisionaban y el desempate por hash barajaba el orden de las senales recency-weighted, dando un score no determinista (DECISION_LOG D180).
- `scripts/package.ps1` poda `__pycache__` del stage antes de comprimir: el zip portable ya no incluye bytecode compilado.
- `tests/test_phase0.py` Test 2: verifica integridad de las fuentes `Tema */` contra `data/source_manifest.json` (existencia + sha256) en vez de asumir que no estan en el repo (contrato cambiado por el merge `a790afa`; DECISION_LOG D179).
- `.gitattributes`: fija el EOL de checkout del material del curso (`"Tema */*.html" text eol=crlf`) para que `source_manifest.json` coincida en Windows y en CI Linux (DECISION_LOG D181).

### Governance
- CI minima en `.github/workflows/ci.yml`: push/PR a `main`, Python 3.12, `pip install -e ".[dev]"`, `pytest tests/ -q`, `python -m app.cli check`. Sin `GEMINI_API_KEY` (comportamiento extractivo), sin secretos (DECISION_LOG D182).

### Notes
- Alcance: uso local mono-usuario. Sin autenticacion, sin despliegue multiusuario.
- Requiere Python 3.11+ en la maquina destino; no incluye runtime de Python ni instalador MSI.
- Cierre v1.0.0 verificado el 2026-09-09: suite en verde (local 889 x2; CI Linux 884 + 6 skips), `sistemes check` OK en local y en CI, packaging + instalacion limpia end-to-end, CI de GitHub Actions en verde.
- Portabilidad Linux/CI: `.gitattributes` fija a CRLF el EOL de checkout de los ficheros hasheados por los manifiestos; `test_home_defaults_..._on_windows` se salta en POSIX (+ companion XDG); CI corre en Python 3.14 (base64 de 3.12 rompia un fixture).
