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
- Instalacion reproducible: `scripts/install.ps1` (venv + `pip install .`).

### Changed
- Identidad de estudiante desde `SM_STUDENT` (default `me`); se elimina `DEMO_STUDENT`.
- Version oficial `1.0.0`, leida de `pyproject.toml` por el packaging (`scripts/package.ps1`).

### Notes
- Alcance: uso local mono-usuario. Sin autenticacion, sin despliegue multiusuario.
- Requiere Python 3.11+ en la maquina destino; no incluye runtime de Python ni instalador MSI.
