# Sistemes de Mesura

Tutor verificable y entorno de estudio **local, para un solo usuario**, de
la asignatura Sistemes de Mesura (ETSETB-UPC, 230920).

El LLM es capa de razonamiento; la verdad es el material del curso. Toda
respuesta académica se ancla a un fragmento del material con su fuente;
sin respaldo suficiente, el sistema se abstiene
(`No trobo suport suficient en el material de l'assignatura.`).

> **No es multiusuario.** No hay autenticación ni aislamiento entre
> estudiantes. La identidad (`SM_STUDENT`) es configuración, no un usuario
> autenticado. Ver [`docs/ESTADO_DEL_PROYECTO.md`](docs/ESTADO_DEL_PROYECTO.md)
> para el estado real de cada funcionalidad.

## Contenido del repositorio

| Ruta | Qué es |
|---|---|
| `Tema 1/` … `Tema 10/` | **Material del curso** (HTML de teoría + PDF de apunts, en catalán). Fuente inmutable, solo lectura. |
| `app/` | Pipeline y dominio: ingesta, retrieval, reasoning, examiner, correction, mastery, adaptive, exam, review, application layer, CLI, migraciones, backup, integridad, logs. |
| `web/` | Servidor HTTP stdlib + UI (HTML/CSS/JS vanilla, sin frameworks). |
| `data/processed/`, `data/index/`, `data/generated/` | Artefactos derivados del material (SQLite + índice). Versionados. |
| `docs/` | Documentación del proyecto (español). Empieza por `ESTADO_DEL_PROYECTO.md`. |
| `tests/` | `pytest`, stdlib. |
| `scripts/` | `abrir-app.cmd` (lanzador Windows), `install.ps1`, `package.ps1`. |

## Requisitos

Python **3.11–3.14**. Sin dependencias de runtime (`pytest` solo para
tests).

## Arrancar la app

**Windows (doble clic):** `scripts/abrir-app.cmd` — hace `init`, abre el
navegador y arranca el servidor en `http://127.0.0.1:8901`.

**Cualquier plataforma:**

```bash
python -m app.cli init      # crea data/config/logs/backups bajo SM_HOME
python -m app.cli serve     # verifica integridad y arranca en 127.0.0.1:8901
```

## CLI

```
sistemes init       crea los directorios y un .env inicial
sistemes serve      arranca el servidor web (corre `check --fast` primero)
sistemes check      verifica la integridad de los artefactos empaquetados
sistemes backup     copia online de las SQLite escribibles
sistemes restore    restaura desde un snapshot (con snapshot previo de seguridad)
sistemes ingest     [mantenedor] regenera artefactos desde el material fuente
```

`python -m app.cli <cmd>` funciona sin instalar. `pip install .` expone
`sistemes` y `sistemes-web`.

## Configuración

`.env` (ver `.env.example`). Claves principales: `SM_HOME`, `SM_HOST`,
`SM_PORT`, `SM_STUDENT`, `SM_DATA_DIR` / `SM_INDEX_DIR` / `SM_LOG_DIR` /
`SM_CONFIG_DIR` / `SM_BACKUP_DIR`, `SM_MAX_BODY_BYTES`,
`SM_REQUEST_TIMEOUT`, `SM_TLS`, `SM_LOG_LEVEL`, `GEMINI_API_KEY`,
`GEMINI_MODEL`. El entorno real tiene precedencia sobre el `.env`.

Por defecto todo vive bajo `SM_HOME` (`%LOCALAPPDATA%\SistemesDeMesura` en
Windows, `~/.local/share/sistemes-de-mesura` en POSIX).

## Estado

`v1.0.0`. F0–F11 certificadas; operación local (F12 redefinida)
implementada; F13 parcial; F14 avanzada sin certificar; F15/F16 no
iniciadas. Detalle completo en
[`docs/ESTADO_DEL_PROYECTO.md`](docs/ESTADO_DEL_PROYECTO.md).

Pruebas: `python -m pytest tests/ -q` → `2 failed, 872 passed`. Los 2
fallos son tests live de Gemini que requieren `GEMINI_API_KEY` válida.
