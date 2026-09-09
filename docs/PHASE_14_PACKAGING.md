# Fase 14 — Packaging local y operación reproducible

Estado: **entregado**. Versión oficial `1.0.0` (punto único en `pyproject.toml`).

## Entregado

- **CLI única `sistemes`** (`app.cli:main`): `init`, `serve`, `ingest`
  (mantenedor), `check`, `backup`, `restore`. Se conserva el alias
  `sistemes-web` (`web.server:main`) y `python -m app.cli` / `python -m
  web.server` para desarrollo sin instalación.
- **Configuración `.env`** (`app/env.py`): lookup en el directorio de trabajo
  y en el config dir; el entorno real tiene precedencia. `.env.example` sin
  secretos; `.env` sigue en `.gitignore`.
- **Cinco directorios configurables** (`app/paths.py`): datos, index, logs,
  config y backups bajo `SM_HOME`, cada uno con override
  (`SM_DATA_DIR`, `SM_INDEX_DIR`, `SM_LOG_DIR`, `SM_CONFIG_DIR`,
  `SM_BACKUP_DIR`). `sistemes init` los crea y siembra `.env`.
- **Identidad de estudiante** por `SM_STUDENT` (default `me`); se eliminó
  `DEMO_STUDENT`.
- **Migraciones de esquema** forward-only con `PRAGMA user_version`
  (`app/migrate.py`), baseline `1` para cada BD escribible; sin
  down-migrations (rollback = restore desde backup).
- **Backup / restore online** (`app/backup.py`): `.backup()` de SQLite en
  caliente, snapshot con manifiesto y timestamp, snapshot pre-restore
  automático, rechazo de restaurar una versión más nueva, `backup --list`.
  El KB de solo lectura queda excluido.
- **Verificación de integridad** (`app/artifacts.py` + `sistemes check`):
  hashes de artefactos contra `data/ARTIFACT-MANIFEST.json`, esquema,
  centinelas, config y (opcional) fuente; `--fast`, `--status`,
  `--write-manifest`. `serve` ejecuta `check --fast` al arrancar y aborta si
  falla.
- **Logs estructurados rotados** (`app/logsetup.py`): `serve.log` y
  `error.log` en el log dir, rotación por tamaño, nivel desde
  `SM_LOG_LEVEL`, sin contenido de estudiante.
- **Health check** `GET /api/health` (200 / 503, sin auth ni CSRF).
- **Límites de petición**: `SM_MAX_BODY_BYTES` → 413, `SM_REQUEST_TIMEOUT`
  como timeout de socket.
- **CSRF** double-submit cookie en la API (`SameSite=Strict`, `Secure` con
  `SM_TLS`); GET exento.
- **Instalación reproducible** `scripts/install.ps1`: valida Python
  `>=3.11,<3.15`, crea `.venv`, `pip install --no-input -e .` (editable; con
  `-Dev`: extra `[dev]` + `pytest` + `sistemes check`), imprime la ruta de
  `sistemes.exe`.
- **`scripts/package.ps1`**: lee la versión de `pyproject.toml` (sin
  cablearla), copia `CHANGELOG.md`, incluye `scripts/install.ps1` y
  `run-web.ps1`, regenera `data/ARTIFACT-MANIFEST.json` contra el árbol
  staged y **poda `__pycache__`** antes de comprimir el zip portable.
  Artefactos `data/` viajan en el zip, no en el wheel.
- `CHANGELOG.md` (Keep a Changelog) y `docs/RELEASE_CHECKLIST.md`.

## Límites

- **No incluye runtime de Python**: la máquina destino necesita Python
  3.11–3.14 ya instalado y en el `PATH`.
- **No hay instalador MSI ni contenedor**: la distribución es el zip
  portable + `install.ps1`, o `pip install .` desde el repo.
- Uso local mono-usuario: sin autenticación ni despliegue multiusuario
  (deuda de F12).
- La consola instalada (`sistemes.exe`) resuelve `data/` y `pyproject.toml`
  vía `app/paths.package_dir()` = raíz del paquete importado. Funciona
  cuando se ejecuta desde el árbol portable extraído (que lleva `app/`,
  `data/`, `pyproject.toml`); un `pip install` del wheel aislado, sin ese
  árbol, no trae artefactos y `check` reporta "BD ausente" — comportamiento
  esperado, los artefactos se distribuyen en el zip.
- Sin afirmaciones académicas nuevas.

## Verificación

### Suite completa

```
python -m pytest tests/ -q
2 failed, 872 passed in 468.43s
```

Los dos fallos son preexistentes y ajenos a F14:
`tests/reasoning/test_provider.py::test_live_theory_answer_verified` y
`::test_live_calculation_verified`, ambos `RuntimeError: HTTPError 401`
(Gemini sin credenciales en el entorno de CI). Segunda pasada: recuentos
idénticos.

`python -m pytest tests/test_packaging.py -q` → `5 passed`.

### Verificación end-to-end (auditoría de cierre v1.0.0, 2026-09-09)

Entorno: Windows 11, Python 3.14.6. Carpeta temporal nueva, fuera del
workspace; `SM_HOME` aislado a un directorio temporal.

```
pwsh scripts/package.ps1
  -> ARTIFACT: dist/sistemes-de-mesura-1.0.0-portable.zip   (exit 0)
  -> 340 entradas, ~5,5 MB. Sin .env, sin __pycache__/.pyc, sin
     .pytest_cache, sin .git, sin secretos. Con .env.example,
     data/ARTIFACT-MANIFEST.json, PACKAGE-MANIFEST.json, install.ps1.

# extraer el zip en carpeta nueva + instalar
scripts/install.ps1
  -> pip install -e .  ->  Successfully installed sistemes-de-mesura-1.0.0
  -> CLI: <clean>/.venv/Scripts/sistemes.exe                (exit 0)

sistemes init          -> init OK (data/index/logs/config/backups en SM_HOME)  (exit 0)
sistemes check         -> check OK                                             (exit 0)
sistemes check --status-> knowledge 1 -> 1                                     (exit 0)
sistemes check --json  -> {"ok": true, "problems": []}

sistemes serve --port 8913
GET /api/health        -> 200 {"status":"ok","version":"1.0.0",
                               "checks":{"kb":true,"index":true,"student_db":true}}
GET /api/session       -> 200 {"csrf":"…","student":"me"}
GET /api/study/topics  -> 200  10 temas (retrieval/KB vivos)
POST /api/tutor/ask    -> 200  status=VERIFIED, abstain=false, provenance=3
                               (--provider extractive: provider=extractive-fallback)
POST /api/tutor/ask sin X-CSRF-Token -> 403 CSRF
POST /api/practice/start -> 200  question_id determinista q-93f3e2c4c7fd

# persistencia: student.sqlite + questions.sqlite creados en SM_HOME/data/;
# reinicio del servidor -> /api/study/mastery devuelve 10 filas (estado persiste).
```

**Verificado end-to-end**: `package.ps1` genera el zip portable limpio;
`install.ps1` instala en carpeta nueva; `init`/`check`/`check --status` en
verde; `serve` responde en `127.0.0.1:PORT`; `health` `ok`; tutor, retrieval
y practice funcionales; CSRF activo (403 sin token); persistencia del estado
del estudiante tras reinicio del servidor.

**No cubierto** (fuera de alcance por decisión): instalador MSI, arranque sin
Python preinstalado, `serve` bajo WSGI/reverse-proxy/HTTPS.
