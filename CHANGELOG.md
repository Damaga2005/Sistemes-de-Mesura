# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).

## [Unreleased]

### Added
- **Aplicación de escritorio para Windows** (F19): `SistemesDeMesura.exe`,
  ventana `pywebview` / WebView2 sobre el servidor local, empaquetada con
  PyInstaller en un solo fichero. `escritorio.py` lanza `web.server` en un
  hilo daemon con `--port 0` y descubre el puerto efímero vía `$SM_PORT_FILE`;
  sin puente JS↔Python. Se genera con `.\build.ps1`; extras opcionales
  `pip install -e ".[desktop,build]"`. La instalación base y el job Linux de
  CI no cambian; se añade un job `desktop` independiente en `windows-latest`.
  Requiere el WebView2 Runtime (no se empaqueta). Ver `docs/F19_DESKTOP_APP.md`
  y DECISION_LOG D188.

### Changed
- **Rediseño de producto / UI** (F17): sistema de tokens *dark-first* con
  acento violeta, shell (cabecera + navegación) inyectada por JS, i18n CA/ES
  completa del *chrome*, componentes compartidos (`web/static/js/ui.js`),
  todas las páginas re-skinned, navegación reducida a funcionalidad real
  (`Inici · Temari · Pràctica · Tutor IA · Progrés · Exàmens`);
  `study.html` / `learning.html` / `history.html` pasan a *stubs* de
  redirección. Inter *self-hosted*
  (`web/static/fonts/InterVariable.woff2`) + una línea en `_MIME` de
  `web/server.py` (`.woff2`) — único cambio de backend de F17. DECISION_LOG
  D183–D187; `docs/F17_*`.
- `web/server.py::main()`: publicación de puerto **opt-in** (F19) — si
  `$SM_PORT_FILE` está definido, escribe el puerto realmente enlazado tras el
  `bind` del `ThreadingHTTPServer` y antes de `serve_forever()` (sin sonda
  `bind→close→rebind`). Con la variable sin definir, el servidor es idéntico
  al anterior.

### Removed
- Borrador obsoleto de la UI de producto de F17 (F18-05).

### Fixed
- Estado de examen estable al cambiar de idioma en marcha: la respuesta sin
  enviar, la posición/pregunta, el `xsid` de la sesión y el temporizador
  sobreviven CA↔ES sin recarga (F18-02).
- `aria-current="page"` en el elemento de navegación activo (F18-03).
- Compatibilidad de los iconos SVG externos endurecida (F18-04).
- Benchmarks de certificación manuales (`app/*_benchmark.py`) adaptados al
  shell de F17 (F18-01).

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
