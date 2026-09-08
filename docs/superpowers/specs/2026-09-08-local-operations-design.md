# Operación local — packaging, configuración y seguridad de datos (design)

Fecha: 2026-09-08
Estado: aprobado, pendiente de plan de implementación.
Sustituye a: `2026-09-08-f12-production-foundations-design.md` (perfiles / aislamiento
multi-estudiante descartados: el objetivo es una sola persona en una sola máquina).

## 1. Objetivo y alcance

Una sola spec, un solo usuario, local. Consolida lo que quedaba con valor
real de las fases F12/F14/F15/F16 del roadmap original una vez fijado el
objetivo "local, solo para mí":

- configuración por `.env` y directorios configurables;
- identidad única (`SM_STUDENT`), sin perfiles ni autenticación;
- migraciones de esquema SQLite (versionado forward-only);
- copia de seguridad y restauración de SQLite (CLI);
- CSRF (localhost sigue siendo alcanzable por cualquier página del navegador);
- CLI única `sistemes` (`init` / `ingest` / `serve` / `check` / `backup` / `restore`);
- verificación de integridad de artefactos empaquetados;
- logs estructurados, health check, límites de tamaño y timeout;
- instalación reproducible (venv + `pip install .`), `CHANGELOG`, checklist de release,
  versión oficial `1.0.0`.

**Fuera de alcance (roadmap original, descartado para uso local mono-usuario):**
perfiles y aislamiento entre estudiantes, autenticación con contraseña,
servidor WSGI/ASGI, reverse proxy, HTTPS gestionado, entornos
`staging`/`producción`, test multiusuario, test de carga, revisión de
secretos como fase (no hay secretos más allá de `GEMINI_API_KEY`
opcional), auditoría de dependencias como fase (`dependencies = []`).

**Charter respetado:** stdlib pura, cero dependencias runtime, determinismo,
sin red silenciosa. `pytest tests/` en verde antes de certificar.

## 2. Configuración por `.env` e identidad

### 2.1 `app/env.py` (~15 líneas, stdlib)

`load_env(path: str | Path) -> dict[str, str]`:
- líneas `KEY=VALUE`; `#` comentario; líneas en blanco ignoradas;
- comillas simples o dobles envolventes opcionales, se retiran;
- sin interpolación de variables, sin `export`;
- fija cada clave en `os.environ` **solo si no está ya presente** (el
  entorno real gana);
- fichero ausente → no es error (todas las claves tienen default).

Orden de búsqueda del `.env`: `--env PATH` → `./.env` → `<SM_CONFIG_DIR>/.env`.
El primero que exista se carga; los defaults incorporados cubren el resto.

`web/server.py main()` y `app/cli.py` llaman a `load_env` antes de
resolver argumentos.

### 2.2 Identidad única

- Se **elimina** la constante `DEMO_STUDENT = "demo"` de `web/server.py`.
- Los ~30 puntos de uso toman `self.student`, fijado al construir el
  `Bridge` desde `SM_STUDENT` (default `"me"`).
- Sin tabla de perfiles, sin selector, sin `profile.html`, sin `Bridge`
  por perfil. El `Bridge` sigue siendo por hilo (conexiones SQLite no
  compartidas entre hilos, invariante P2-3/B6 existente).

## 3. Directorios configurables — `app/paths.py`

Raíz `SM_HOME`:
- Windows: `%LOCALAPPDATA%\SistemesDeMesura`
- POSIX: `$XDG_DATA_HOME/sistemes-de-mesura` o `~/.local/share/sistemes-de-mesura`

Subdirectorios derivados, cada uno con override independiente:

| Rol | Default | Override |
|---|---|---|
| datos (escribible) | `SM_HOME/data` | `SM_DATA_DIR` |
| índices | `SM_HOME/index` | `SM_INDEX_DIR` |
| logs | `SM_HOME/logs` | `SM_LOG_DIR` |
| config | `SM_HOME/config` | `SM_CONFIG_DIR` |
| backups | `SM_HOME/backups` | `SM_BACKUP_DIR` |

`app/paths.py` expone `data_dir()`, `index_dir()`, `log_dir()`,
`config_dir()`, `backup_dir()`, `package_dir()` (raíz de artefactos
empaquetados, in situ). Sustituye rutas cableadas:
`app/config.py` `DEFAULT_*`, `web/server.py` `KB`/`INDEX`/`GENDB`,
`app/build_index.py` `WORKSPACE`/`KB`/`INDEX_DIR`.

### 3.1 Artefactos empaquetados (solo lectura, in situ)

`knowledge.sqlite`, `data/index/`, `eval.sqlite`, `questions.sqlite`
canónico, `source_manifest.json`, `ARTIFACT-MANIFEST.json`. Viajan en el
zip portable (§9) y se leen desde `package_dir()` sin copiarse.

### 3.2 Estado escribible (bajo los dirs de usuario)

`student.sqlite`, copia de trabajo de `questions.sqlite`,
`exam_sessions.sqlite` (en `data_dir()`); logs (`log_dir()`); snapshots
(`backup_dir()`); `.env` activo (`config_dir()`). La copia de trabajo de
`questions.sqlite` se siembra por `shutil.copyfile` desde el canónico
**solo si no existe** (idempotente, lógica ya presente en `Bridge`).

## 4. Migraciones de esquema — `app/migrate.py`

`PRAGMA user_version` por fichero SQLite, **forward-only**.

- `migrate(conn, db_name, target)`: lee `user_version`, aplica cada
  migración `NNN` > actual en una transacción por migración, sube
  `user_version`. Se ejecuta automáticamente al abrir la conexión en
  cada store.
- `app/migrations/<db_name>/NNN_descripcion.sql`, o `.py` con
  `def up(conn)` para movimientos de datos. `<db_name>` ∈ `student`,
  `questions`, `exam_sessions`, `knowledge`.
- **Baseline:** el esquema vivo actual se captura como `001_baseline.sql`
  por BD; todo `CREATE TABLE IF NOT EXISTS` inline de los stores se
  traslada ahí. No-op sobre BD poblada, real sobre BD nueva. El store
  pasa a llamar solo a `migrate()`.
- `knowledge.sqlite` recibe sello de versión (solo lectura; sus
  migraciones son re-ingesta manual, pero el sello permite a `restore` y
  al arranque **rechazar** ante desajuste en vez de corromper).
- Sin down-migrations. Rollback = restaurar desde backup (§5).
- Errores: `NNN` duplicado o hueco en la secuencia → fallo ruidoso.

## 5. Backup y restauración — `app/backup.py`

Subcomandos de `sistemes` (destructivo → nunca endpoint web):

- `sistemes backup [--out DIR]` → `.backup()` online de `sqlite3` para
  `student.sqlite`, copia de trabajo de `questions.sqlite` y
  `exam_sessions.sqlite` hacia `<SM_BACKUP_DIR>/<UTC-ISO>/`. Consistente
  bajo escritura concurrente. Escribe `manifest.json` (ficheros,
  tamaños, sha256, `user_version` por fichero, versión de app).
- `sistemes restore --from <timestamp>` → pre-backup del estado actual a
  `<UTC>-pre-restore/`, luego copia los ficheros del snapshot de vuelta.
  **Rechaza** si el `user_version` de un fichero del snapshot es más
  nuevo que el objetivo del código.
- `sistemes backup --list` → tabla de snapshots desde los manifests.
- KB y artefactos empaquetados excluidos (regenerables/inmutables).
- `SM_BACKUP_DIR` reubica la raíz (p. ej. disco externo).

## 6. CSRF

Double-submit cookie. Se mantiene aunque sea mono-usuario: `localhost:PORT`
es alcanzable por `POST` desde cualquier página que el navegador visite.

- Cookie `sm_session`: `HttpOnly; SameSite=Strict; Path=/`
  (`+ Secure` cuando `SM_TLS=1`).
- Cookie `sm_csrf`: legible por JS, `SameSite=Strict; Path=/`, valor =
  token de sesión.
- Toda petición mutante (`POST /api/*`) debe enviar cabecera
  `X-CSRF-Token` igual a la cookie `sm_csrf`. Ausente/distinto →
  `403 {code: "CSRF"}`.
- `GET` nunca muta (auditoría B6: se verifica y se congela con test).
- JS vanilla: un helper lee `sm_csrf` y pone la cabecera; se engancha al
  wrapper `fetch` de `web/static/js/app.js`.
- El `dict` de sesión en memoria se mantiene: sin expiración, sin
  persistencia (un usuario, localhost).

## 7. CLI única `sistemes` — `app/cli.py`

Entry point `sistemes = "app.cli:main"`. Despachador `argparse`; cada
subcomando delega en código ya probado, no reimplementa.

| Comando | Hace | Delega en |
|---|---|---|
| `sistemes init` | crea los 5 dirs; escribe `<config>/.env` desde `.env.example` si no existe (`--force` lo reescribe); no toca datos; idempotente | `app/paths.py` |
| `sistemes ingest` | regenera `data/processed/` + `data/evaluation/` + índice. **Mantenedor**: exige `--source DIR` y `--out DIR` (default: `data/` del checkout); se niega si el destino no es escribible sin `--out` | `app.ingest.main` + `app.build_index.main` |
| `sistemes serve` | ejecuta `check --fast`; si falla, aborta. Si no, arranca el servidor web | `web.server.main` |
| `sistemes check` | integridad de artefactos (§8). Exit 0 / ≠0. Flags: `--json`, `--fast`, `--status` (versiones de migración), `--write-manifest` (mantenedor) | `app/artifacts.py` |
| `sistemes backup` / `restore` | §5 | `app/backup.py` |
| `sistemes --version` | lee `version` de `pyproject.toml` (metadata instalada) | — |

`sistemes-web` se mantiene un ciclo como **alias deprecado** de
`sistemes serve` (aviso en `--help`).

## 8. Verificación de integridad — `app/artifacts.py`

Tabla de expectativas (sha256 + tablas + recuentos centinela, tomados de
los docs de certificación F8/F10/F11):

1. **Hashes:** cada artefacto empaquetado vs `ARTIFACT-MANIFEST.json`.
2. **Esquema:** `PRAGMA user_version` == objetivo del código; tablas
   esperadas presentes en cada BD.
3. **Centinelas:** recuentos fijos — 2896 fórmulas, y nº de
   chunks / documentos / preguntas V/F.
4. **Config:** `.env` parsea; los 5 dirs existen y son escribibles los
   que deben serlo.
5. **Fuente (opcional):** con `--source DIR`, `source_manifest.json`
   cuadra (reusa `app.ingest.verify_sources`).

`--fast` = (2) + (4); es lo que ejecuta `serve` al arrancar.
`ARTIFACT-MANIFEST.json` lo genera `scripts/package.ps1` y
`sistemes check --write-manifest` (mantenedor, sobre el checkout).

## 9. Logs, health check, límites

### 9.1 Logs — `app/logsetup.py`

`configure(log_dir, level)`. `logging` stdlib + `RotatingFileHandler`
(5 MB × 5 ficheros).
- `serve.log`: una línea por petición — `ts method path status ms`.
  Sustituye el `log_message` silenciado del `Handler`.
- `error.log`: nivel `ERROR`+, con traceback — excepciones no
  controladas del handler y fallos de subcomandos CLI.
- Nivel desde `SM_LOG_LEVEL` (default `INFO`).
- **Nunca** se registran prompts ni respuestas de estudiante.

### 9.2 Health check

`GET /api/health` → `{status, version, checks: {kb, index, student_db}}`.
`200` si todo OK; `503` si algún check falla. Sin auth, sin CSRF.
~10 líneas en el `Bridge`.

### 9.3 Límites de tamaño y timeout

En `Handler`:
- `Content-Length` > `SM_MAX_BODY_BYTES` (default 1 MiB) → `413` sin leer
  el cuerpo.
- Timeout de socket `SM_REQUEST_TIMEOUT` (default 30 s) para que un
  cliente colgado no retenga un hilo.

## 10. Instalación reproducible y packaging

- `pyproject.toml`:
  - `version = "1.0.0"`;
  - `requires-python = ">=3.11,<3.15"`;
  - `[project.scripts] sistemes = "app.cli:main"`;
  - `[project.optional-dependencies] dev = ["pytest"]`;
  - `packages.find` incluye `app*`, `web*`;
  - `package-data` mantiene `web/*`; los artefactos `data/` viajan en el
    zip, no en el wheel.
- `scripts/install.ps1`: comprueba `python` ≥ 3.11 (`< 3.15`); crea
  `.venv` junto al zip desempaquetado; `pip install --no-input .`;
  imprime la ruta de `sistemes.exe`. `-Dev` añade `pip install pytest` y
  corre `sistemes check`.
- `scripts/package.ps1` extendido: bundlea `install.ps1`, emite
  `ARTIFACT-MANIFEST.json`, lee `$version` de `pyproject.toml` (deja de
  estar cableado en `0.13.0`).
- Reproducibilidad: cero dependencias runtime que fijar; `pip install .`
  es determinista dada la versión de Python. Se documenta la versión
  exacta probada.
- `CHANGELOG.md` nuevo (formato Keep a Changelog), entrada `1.0.0`.
- `docs/RELEASE_CHECKLIST.md` nuevo (corto): tests en verde ×2,
  `sistemes check` en verde, `CHANGELOG` actualizado, versión subida en
  `pyproject.toml`, `package.ps1` ejecutado, sha del artefacto anotado.

## 11. Pruebas

| Test | Cubre |
|---|---|
| `tests/test_env.py` | parseo comillas/comentarios/blancos, precedencia del entorno real, fichero ausente OK |
| `tests/test_paths.py` | `SM_HOME` + cada override, Windows vs POSIX, rutas cableadas eliminadas |
| `tests/test_migrations.py` | BD nueva alcanza objetivo; baseline no-op sobre BD poblada; `--status`; `NNN` duplicado/hueco rechazado; **restore rechaza `user_version` más nuevo** |
| `tests/test_backup_restore.py` | backup→mutar→restore byte-idéntico; hashes de manifest; `--list` |
| `tests/test_csrf.py` | `POST` rechazado sin token / con token erróneo; `GET` nunca lo exige; forma de respuesta |
| `tests/test_cli.py` | despacho de subcomandos, `--help`, `--version` desde `pyproject`, `init` idempotente + `--force`, `ingest` se niega sin `--out` en destino no escribible, alias deprecado |
| `tests/test_check.py` | detecta hash alterado, `user_version` desfasado, tabla ausente, centinela roto; exit codes; `--json`; `--fast` ⊂ completo |
| `tests/test_logsetup.py` | rotación, formato de línea de petición, sin contenido de estudiante, nivel desde `.env` |
| `tests/test_health.py` | `200` todo OK, `503` con KB ausente, sin auth/CSRF |
| `tests/test_limits.py` | `413` por encima de `SM_MAX_BODY_BYTES` |
| `tests/test_packaging.py` (ampliado) | `pyproject` válido, entry point resuelve, zip con artefactos + `install.ps1` + `ARTIFACT-MANIFEST.json`, versión coherente |
| `tests/test_serve_gate.py` | `serve` aborta con artefacto corrupto; arranca con artefactos íntegros |

Regresión `pytest tests/` completa en verde — las ~30 ediciones de
`DEMO_STUDENT` y el cambio de rutas son el riesgo; las suites de dominio
F0–F11 quedan intactas.

## 12. Criterio de salida

En una máquina limpia con solo Python 3.11+:

1. `scripts/install.ps1` produce `sistemes.exe`;
2. `sistemes init` crea los 5 directorios y un `.env` inicial;
3. `sistemes check` pasa en verde;
4. `sistemes serve` levanta la web y responde;
5. los 5 directorios se respetan al fijarlos por `.env`;
6. `sistemes backup` seguido de `sistemes restore --from <ts>` deja el
   estado byte-idéntico;
7. `sistemes check` detecta un artefacto empaquetado alterado a
   propósito (exit ≠ 0).

Regresión completa en verde.

## 13. Secuencia de bloques (orden de implementación, no fases)

| Bloque | Contenido |
|---|---|
| **B0** | Preauditoría (doc): inventario de rutas absolutas cableadas, entry points y comandos `python -m` actuales, puntos `DEMO_STUDENT`, rutas `/api` × método × mutación, estado de `package.ps1`. |
| **B1** | `app/env.py` + `app/paths.py`; sustituir rutas cableadas por `paths.*`; `SM_STUDENT` sustituye `DEMO_STUDENT`. Regresión verde. |
| **B2** | `app/migrate.py` + `001_baseline.sql` por BD; stores llaman a `migrate()`. |
| **B3** | `app/backup.py` (`backup` / `restore` / `--list`). |
| **B4** | `app/cli.py` con `init` / `serve` / `ingest` + alias deprecado. |
| **B5** | `app/artifacts.py` + `check` + `ARTIFACT-MANIFEST.json` + gate de arranque en `serve`. |
| **B6** | `app/logsetup.py` + `/api/health` + límites tamaño/timeout + CSRF. |
| **B7** | `install.ps1` + `package.ps1` extendido + `pyproject` a `1.0.0` (versión des-duplicada) + `CHANGELOG.md` + `docs/RELEASE_CHECKLIST.md` + certificación (regresión ×2, criterio de salida, `DECISION_LOG`). |

## 14. Decisiones (para `DECISION_LOG` en B7)

| # | Decisión | Motivo | Alternativas descartadas |
|---|---|---|---|
| D169 | Mono-usuario local: `SM_STUDENT` desde `.env`, sin perfiles/auth/aislamiento | El objetivo es una persona en una máquina | Perfiles honor-system (F12 original) / cuentas con contraseña / aislamiento por directorio |
| D170 | `ThreadingHTTPServer` stdlib se mantiene; sin WSGI/ASGI, reverse proxy ni HTTPS gestionado | YAGNI para localhost mono-usuario; charter de cero dependencias | gunicorn/uvicorn/waitress + nginx |
| D171 | Migraciones forward-only con `user_version`; sin down-migrations | Rollback = restore desde backup; las down-migrations son código muerto casi siempre | Herramienta de migración con dependencia externa |
| D172 | Artefactos `data/` en el zip portable, no en el wheel | Un wheel con decenas de MB de SQLite es un antipatrón; el zip ya los lleva | `package-data` en el wheel |
| D173 | La CLI delega; no reimplementa `serve`/`ingest` | Menor superficie; `web.server.main` y `app.ingest.main` ya están probados | Reescribir la lógica en `app/cli.py` |
| D174 | `ingest` es comando de mantenedor (exige `--source`/`--out`) | La fuente vive fuera del paquete y los artefactos empaquetados son inmutables | `ingest` para usuario final (escribiría en `site-packages`) |
| D175 | CSRF se mantiene pese a ser mono-usuario; expiración y persistencia de sesión se descartan | Cualquier página del navegador puede hacer `POST` a `localhost:PORT`; la expiración no aporta con un solo usuario local | Quitar CSRF (deja la web local abierta a CSRF) / sesión persistente con expiración (sin valor aquí) |
| D176 | Versión oficial `1.0.0`, punto único en `pyproject.toml` | F0–F13 certificadas; `package.ps1` duplicaba `0.13.0` | Mantener `0.x` / versión en fichero aparte |
| D177 | Un solo formato de configuración: `.env`, con lookup extra en el config dir | Coherencia; `tomllib` añadiría un segundo formato | `config.toml` |
| D178 | `serve` corre `check --fast` al arrancar y aborta si falla | Un KB corrupto da respuestas silenciosamente malas; mejor fallo ruidoso | Arrancar siempre y confiar en `check` manual |
