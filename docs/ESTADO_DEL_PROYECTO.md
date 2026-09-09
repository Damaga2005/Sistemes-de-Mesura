# Estado del proyecto — Sistemes de Mesura

> Documento vivo. Refleja el estado real a fecha **2026-09-09**: árbol de
> trabajo sobre `bc4692f` (`origin/main`) más el cierre v1.0.0 sin commitear
> (Test 2 de F0, determinismo de mastery, poda de `__pycache__` en el
> packaging; ver DECISION_LOG D179–D180 y §5). Sustituye a cualquier lectura
> de roadmap anterior que asuma multiusuario.

## 1. Qué es este producto (y qué no es)

**Es:** un tutor verificable y entorno de estudio **local, para un solo
usuario**, de la asignatura Sistemes de Mesura (ETSETB-UPC, 230920). Se
ejecuta en la máquina del estudiante, liga a `127.0.0.1`, y toda
afirmación académica es trazable al material del curso; sin respaldo →
abstención.

**No es:** una aplicación multiusuario. **No hay** autenticación, login,
contraseñas, base de datos de usuarios, ni aislamiento entre estudiantes.
La identidad (`SM_STUDENT`, por defecto `me`) es un valor de
configuración, no un sujeto autenticado.

### La sustitución de F12

El diseño original de F12 ("Fundaciones para producción": autenticación
real, dos perfiles, aislamiento, sesiones persistentes) fue
**descartado explícitamente** y sustituido por
`docs/superpowers/specs/2026-09-08-local-operations-design.md` con el
objetivo **"local, un solo usuario, una sola máquina"**. El documento
antiguo está marcado `SUPERSEDED`. Lo que sobrevivió de F12 se
implementó: `.env`, directorios configurables, `SM_STUDENT`, migraciones,
backup/restore, CSRF. Lo que se descartó: perfiles, autenticación,
WSGI/ASGI, reverse proxy, HTTPS gestionado, staging, producción,
multiusuario, load testing.

## 2. Estado por fases

| Fase | Alcance | Estado |
|---|---|---|
| **F0–F7** | Ingesta, KB, retrieval, reasoning, examiner, correction, mastery, exam/review | 🟢 Certificadas (histórico del proyecto) |
| **F8** | Auditoría y certificación final | 🟢 CERTIFIED |
| **F9** | Operational readiness | 🟢 Operationally Ready |
| **F10** | Application layer | 🟢 CERTIFIED |
| **F11** | Experiencia de producto / UI | 🟢 Product Certified |
| **F12 (original)** | Auth + multiusuario + aislamiento | 🔴 **NO implementada — SUPERSEDED** |
| **F12 (operación local)** | `.env`, paths, `SM_STUDENT`, migraciones, backup, CSRF, health, límites, logs, CLI, integridad | 🟢 **Implementada** |
| **Integración Gemini** | Tutor con `GeminiProvider` real (selección `auto\|gemini\|extractive`) + fallback extractivo ante fallo del proveedor | 🟢 **Implementada y validada end-to-end** (`a3e5d5e`) |
| **F13** | Vertical Documents + contrato Calendar | 🟡 **Parcial** (ver §4) |
| **F14** | Packaging local `1.0.0` | 🟢 **Verificada end-to-end** (2026-09-09): `package.ps1` → carpeta nueva → `install.ps1` → `init`/`check`/`serve` → `/api/health` `ok` → smoke tutor/practice + persistencia tras reinicio. Ver `docs/PHASE_14_PACKAGING.md`. Sin instalador MSI (fuera de alcance). |
| **F15** | Despliegue (staging → producción, proxy, HTTPS) | 🔴 No iniciada (fuera de alcance por decisión) |
| **F16** | Certificación operativa (smoke post-deploy, load test, dependency audit, release) | 🔴 No iniciada |

Los `docs/PHASE_0..11_*.md` son los registros históricos de certificación
de F0–F11 y no se modifican.

## 3. Estado por funcionalidad

### 🟢 Sólido

| Área | Detalle |
|---|---|
| Knowledge base | `data/processed/knowledge.sqlite`, sello `user_version = 1`. **2896/2896 fórmulas**, 1903 chunks, 71 documentos. |
| Retrieval / Reasoning / Examiner / Correction / Mastery / Adaptive / Exam / Review | Módulos F0–F11, suite completa en verde x2 (889/889, ver §5). Mastery: determinismo del score reforzado (timestamps de microsegundos, D180). |
| Proveedor de razonamiento | `select_provider(auto\|gemini\|extractive)`. `GeminiProvider` REST stdlib (`gemini-3.5-flash-lite`, env `GEMINI_MODEL`), clave sólo de entorno, nunca en logs/repo. `auto` sin `GEMINI_API_KEY` → `ExtractiveProvider` determinista (verificado por construcción). El tutor web usa esta selección vía `sistemes serve --provider …` / env `SM_PROVIDER` (defecto `auto`) → `Bridge` → `ReasoningEngine`. `versions.provider = {provider, model}` en la respuesta de `/api/tutor/ask`. **Validado end-to-end contra la instancia viva: llamada real a Gemini, `status: VERIFIED`, sin fallback** (`a3e5d5e`). |
| Fallback del razonador | `RuntimeError` del proveedor LLM en `_reason()` (red, 5xx/4xx incl. 401, clave inválida, respuesta vacía) → degradación a extractivo verificado, HTTP 200, `versions.provider.provider = "extractive-fallback"` + `fallback_reason`, aviso `llm_provider_error_fallback`. Ya no hay `GENERATION_ERROR`/502 con evidencia en mano. Bugs de programación (`TypeError`…) **no se capturan** y propagan. |
| Application layer | `app/application/` — fachada F10 sobre los servicios de dominio. |
| Web UI | 14 páginas (study, practice, exam, exams, review, results, history, learning, documents, calendar, topic, content…). Renderer LaTeX con lista blanca. |
| Configuración | `app/env.py` (`.env`, precedencia del entorno real, fichero ausente tolerado) + `app/paths.py` (`SM_HOME` + 5 directorios con override). |
| Migraciones de esquema | `app/migrate.py`, forward-only, `PRAGMA user_version`, atómicas (`BEGIN … PRAGMA user_version … COMMIT` + rollback). Baseline `1` por BD. |
| Backup / restore | `app/backup.py`, `.backup()` online, manifiesto con sha256 + `user_version` + versión de app, snapshot pre-restore, rechazo de versión más nueva, `--list`. |
| Verificación de integridad | `app/artifacts.py` + `sistemes check`: hashes vs `data/ARTIFACT-MANIFEST.json`, esquema, centinelas de conteo, config, fuente opcional. `serve` corre `check --fast` al arrancar y aborta si falla. |
| CSRF | Double-submit cookie (`sm_session` HttpOnly + `sm_csrf`), `X-CSRF-Token` case-insensitive, `SameSite=Strict`, `Secure` con `SM_TLS`. GET exento. Test sobre socket HTTP real. |
| Límites HTTP | `SM_MAX_BODY_BYTES` → 413 antes de leer el cuerpo; `SM_REQUEST_TIMEOUT` como `Handler.timeout`. |
| Health check | `GET /api/health` → 200/503, sin auth ni CSRF. |
| Logs | `app/logsetup.py`: `serve.log` + `error.log` rotados (5 MiB × 5), sin contenido de estudiante, línea por petición (método/ruta/status/ms). |
| CLI | `sistemes init | serve | ingest | check | backup | restore` (+ alias `sistemes-web`). |
| Packaging | `pyproject.toml` `1.0.0`, `requires-python >=3.11,<3.15`, `dependencies = []`. `scripts/install.ps1`, `scripts/package.ps1`, `scripts/abrir-app.cmd`. `CHANGELOG.md`, `docs/RELEASE_CHECKLIST.md`. |

### 🟡 Parcial / con matices

| Área | Estado |
|---|---|
| Identidad | Solo `SM_STUDENT` (config). **No es autenticación.** |
| Sesiones | `Bridge.sessions` en memoria. Sin persistencia ni expiración — correcto para mono-usuario, insuficiente para multiusuario. |
| Documents (F13) | Catálogo real read-only: `GET /api/documents` (filtro por tema, título, tipo, nº de secciones, `COURSE_SOURCE`). Pantalla funcional, ya no placeholder. |
| Calendar (F13) | `GET /api/calendar` con contrato; sin fuente académica → `[]` (no inventa eventos). `app/calendar.py` acepta JSON `version: 1` con trazabilidad. |
| F14 packaging | Entregado y probado por partes; **falta** una ejecución real `package → máquina limpia → install → check → serve`. `scripts/*.ps1` validados por lectura + `tests/test_packaging.py`, no ejecutados end-to-end. |
| Metadatos de proveedor en HTTP | `TutorWorkflow._project` reduce `versions.provider` a `{provider, model}`: la respuesta del tutor **no expone `fallback_reason`** (sí queda en logs y en el objeto del engine). El frontend (`study.js`) ni siquiera lee `versions`. |
| `SM_PROVIDER` | Variable nueva **no documentada en `.env.example`** (las reglas prohíben añadir variables nuevas ahí). Documentada en `docs/LLM_PROVIDER.md`. |

### 🔴 No implementado

| Área | Motivo |
|---|---|
| Autenticación / multiusuario / aislamiento entre estudiantes | Descartado por decisión (D169). Reabrir requiere una fase "F12-R". |
| Study tras la Application Layer | El bridge abre SQLite del KB directamente (`web/server.py`: `_kb()`, `kb_topics/kb_documents/kb_sections/kb_content`). Deuda reconocida en F13. |
| Despliegue (F15): WSGI/ASGI, reverse proxy, HTTPS gestionado, staging, producción | Fuera de alcance del producto local (D170). |
| Certificación operativa (F16): smoke post-deploy, test de carga, dependency audit formal, release de producción | Depende de F15. |
| CI (GitHub Actions) | No existe `.github/workflows/`. |
| Branch protection en `main` | `protected = false`, sin required status checks. |
| Firma de commits | Los commits no están firmados. |
| Release `v1.0.0` publicado | Sin tag `v1.0.0` ni release en GitHub; `RELEASE_CHECKLIST.md` es un checklist, no evidencia de ejecución. |

## 4. Deudas técnicas conocidas (ninguna es P0)

1. **Study salta la Application Layer** — `web/server.py` accede al KB por SQLite directo. Migrar a un `StudyWorkflow` si se reactiva F12 o se endurece el boundary.
2. **`migrate.TARGETS` incluye `exam_sessions`** aunque sus tablas viven dentro de `student.sqlite` (D88). `app/exam/store.py` sella `user_version` de `student.sqlite` de forma redundante. `backup.py` ya excluye `exam_sessions.sqlite` de `WRITABLE_DBS`. Consolidar antes de cualquier producción.
3. **`questions.sqlite` fuera de la cobertura SHA-256 del manifiesto** (`UNHASHED_ARTIFACTS`) porque los tests lo ensucian. Es una copia de trabajo generada; su cobertura actual es de esquema + tablas, no criptográfica. Para un release habría que separar limpiamente artefacto canónico inmutable ↔ copia de trabajo mutable.
4. **`/api/health` `checks.student_db` está hardcodeado a `True`** — no consulta la BD del estudiante.
5. **`srv.timeout` / logs — minores diferidos** de la revisión: `srv.timeout` se resolvió como `Handler.timeout`; `logsetup.configure()` puede escribir logs vacíos en `%LOCALAPPDATA%` para algún test de CLI sin `SM_HOME`.
6. **Branch protection / firma de commits / tag de release** — CI mínima
   añadida en `.github/workflows/ci.yml` (D182); el resto de la governance
   (protección de `main`, firma, tag/release) se cierra en la fase de
   release governance.
7. **Gemini: observabilidad y config menores** — la respuesta HTTP del tutor
   no expone `fallback_reason` (`_project` lo recorta); `SM_PROVIDER` no está
   en `.env.example`. Ninguna afecta al funcionamiento; ambas documentadas en
   §3 🟡 y en `docs/LLM_PROVIDER.md`.
8. **Sin cuotas / billing para Gemini** — cada petición del tutor con
   `--provider gemini` (o `auto` con clave) es una llamada de pago sin límite
   ni contador. Aceptable para uso local individual; a vigilar.
9. **Packaging: el zip portable se descomprime "plano"** (`Compress-Archive`
   de `$stage/*`, sin carpeta contenedora). `install.ps1` funciona igual
   porque localiza la raíz relativa a `scripts/`. Cosmético.

## 5. Estado de pruebas

```
python -m pytest tests/ -q      (dos pasadas consecutivas, auditoría de cierre 2026-09-09)
889 passed, 0 failed, 0 skipped     (605 s)
889 passed, 0 failed, 0 skipped     (772 s)
```

**Verde total x2.** Dos defectos, ambos preexistentes y ajenos a la
integración Gemini, resueltos en la auditoría de cierre:

- **`tests/test_phase0.py` Test 2** (`test_2_source_integrity_matches_manifest`,
  antes `..._originals_not_vendored_...`): el contrato cambió con el merge
  `a790afa` — `Tema */` es fuente canónica in-repo. El test viejo lo
  contradecía y fallaba en árbol limpio. Sustituido por una comprobación
  **más estricta**: cada una de las 91 fuentes existe y su sha256 coincide
  con `data/source_manifest.json` (detecta borrado / mutación). DECISION_LOG
  D179.
- **`test_21_mastery_deterministic`** fallaba ~2/15 aislado y 1/1 bajo carga:
  `mastery._now()` usaba resolución de segundo; varios `submit()` del mismo
  segundo colisionaban y el desempate por hash de `event_id` barajaba el
  orden de las señales recency-weighted → score no determinista. Corregido a
  `timespec="microseconds"` (DECISION_LOG D180). Verificado 0/30 tras el fix.

Los tests live de Gemini (`@NEEDS_KEY`) se ejecutan en este entorno (hay
`GEMINI_API_KEY`) y pasan; en este shell la clave da 401, así que lo hacen
por la ruta de fallback extractivo verificado. La validación con **Gemini
real** se hizo por separado contra el servidor local en marcha (§3, provider
de razonamiento).

## 6. Repositorio

- `main` en `github.com/Damaga2005/Sistemes-de-Mesura` contiene **ambos
  árboles** desde el merge `a790afa`: el material del curso (`Tema 1/` …
  `Tema 10/`, HTML + PDF en catalán) **y** la aplicación (`app/`, `web/`,
  `data/` derivados, `docs/`, `tests/`, packaging).
- El material `Tema N/` es **fuente inmutable**: solo lectura, los
  derivados van a `data/processed/` con trazabilidad por hash.
- Sin ramas adicionales. Historia lineal. Último commit relevante:
  `a3e5d5e` (integración Gemini en el tutor), sobre `187610e` (docs).

## 7. Si el objetivo vuelve a ser multiusuario

Habría que abrir **F12-R** (reactivación), en bloques:

1. **B0** — Auditoría de identidad actual (`SM_STUDENT`, sesiones, cookies, ownership, todas las rutas `/api`, todos los IDs, todas las SQLite).
2. **B1** — Autenticación (login + almacén de credenciales).
3. **B2** — Sesión ligada a identidad + autorización.
4. **B3** — Aislamiento de almacenamiento por estudiante.
5. **B4** — Study → Application Layer.
6. **B5** — Backup / migración multiusuario.
7. **B6** — Certificación de seguridad (IDOR, dos estudiantes aislados end-to-end).

Criterio de cierre: estudiante A no puede acceder a exam / session /
attempt / result / review / mastery / history / practice de estudiante B.
