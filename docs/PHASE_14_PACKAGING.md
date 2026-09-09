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
  `>=3.11,<3.15`, crea `.venv`, `pip install --no-input .` (con `-Dev`:
  extra `[dev]` editable + `pytest` + `sistemes check`), imprime la ruta de
  `sistemes.exe`.
- **`scripts/package.ps1`**: lee la versión de `pyproject.toml` (sin
  cablearla), copia `CHANGELOG.md`, incluye `scripts/install.ps1` y
  regenera `data/ARTIFACT-MANIFEST.json` contra el árbol staged antes de
  comprimir el zip portable. Artefactos `data/` viajan en el zip, no en el
  wheel.
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

### Dry run del criterio de salida (best effort)

Entorno: Windows 11, Python 3.14.6. No se dispone de una máquina
verdaderamente limpia; se usó un `venv` de scratch y, para los checks
funcionales que dependen de `data/`, `python -m app.cli` desde el repo
(fallback previsto en el brief).

```
# venv aislado + instalación
python -m venv dryrun-venv
dryrun-venv\Scripts\python.exe -m pip install --no-input .
  -> Successfully built sistemes-de-mesura
  -> Successfully installed sistemes-de-mesura-1.0.0
  -> wheel = sistemes_de_mesura-1.0.0-py3-none-any.whl (336 KB, sin data/)

# la consola instalada, ejecutada fuera del árbol portable, no ve data/:
dryrun-venv\Scripts\sistemes.exe --version
  -> FileNotFoundError: .../site-packages/pyproject.toml
dryrun-venv\Scripts\sistemes.exe check
  -> check FALLO: BD ausente: data/processed/knowledge.sqlite ... (exit 1)
  (esperado: los artefactos viajan en el zip portable, no en el wheel)

# checks funcionales vía python -m app.cli desde el repo:
python -m app.cli --version              -> 1.0.0
python -m app.cli check                  -> check OK          (exit 0)
python -m app.cli check --status         -> knowledge 1 -> 1
python -m app.cli backup                 -> backup OK: ...\backups\20260909T103226Z
python -m app.cli backup --list          -> 20260909T103226Z  (0 ficheros)
python -m app.cli restore --from 20260909T103226Z
  -> restore OK (estado previo en ...\20260909T103229Z-pre-restore)  (exit 0)

# corrupción de un byte de una copia verificada de knowledge.sqlite:
(byte 4096 XOR 0x01)
python -m app.cli check
  -> check FALLO:
       - sha256 no coincide: data/processed/knowledge.sqlite   (exit 1)
git checkout -- data/processed/knowledge.sqlite
python -m app.cli check                  -> check OK           (exit 0)
```

**Verificado**: `pip install .` construye el wheel `1.0.0` sin `data/`;
`--version` = `1.0.0`; `check` OK / exit 0 en árbol sano; `check` exit 1 con
un byte corrupto; `backup` y `restore` con snapshot pre-restore; `check
--status` sin desajustes de migración.

**No verificable en este entorno**:
- `scripts/install.ps1` / `scripts/package.ps1` de extremo a extremo
  (requieren PowerShell interactivo y una máquina limpia; validados por
  lectura y por los asserts de `tests/test_packaging.py`).
- `sistemes serve` en una máquina limpia respondiendo en `127.0.0.1:PORT`
  (el gate `check --fast` sí se ejerció por la vía `python -m app.cli`).
- Arranque desde el zip portable extraído (no se generó el zip aquí).
