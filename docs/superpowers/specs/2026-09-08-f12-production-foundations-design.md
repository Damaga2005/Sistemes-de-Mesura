# F12 — Fundaciones para producción (design)

Fecha: 2026-09-08
Estado: aprobado, pendiente de plan de implementación.

## 1. Objetivo y criterio de salida

F12 convierte la aplicación web de un tutor mono-usuario cableado
(`DEMO_STUDENT = "demo"`) en una base apta para producción local:
identidad por estudiante, aislamiento de datos, endurecimiento HTTP,
configuración por `.env`, copias de seguridad y versionado de esquema.

**Criterio de salida:** un único servidor localhost, dos perfiles locales
conmutables, aislados end-to-end — sin acceso cruzado a exámenes,
intentos, mastery ni historial; el estado de cada perfil sobrevive a la
conmutación al otro y de vuelta.

## 2. Modelo de identidad y de confianza

- **Sin contraseñas.** Cada estudiante ejecuta / comparte un servidor
  localhost y reclama un *perfil* con nombre. Conmutar de perfil es
  elegir un nombre.
- **Modelo de amenaza explícito:** los perfiles protegen contra
  contaminación *accidental* de datos entre estudiantes y dan a cada uno
  un espacio de trabajo limpio. **No** son una defensa frente a un
  usuario local malicioso (que puede leer los ficheros SQLite del disco
  o seleccionar el perfil ajeno). Para multi-usuario real con
  autenticación se requiere una fase posterior; queda **fuera de alcance
  de F12**.
- El servidor liga solo a `SM_HOST` (default `127.0.0.1`).

## 3. Enfoque de aislamiento (Approach A — directorios por perfil)

El aislamiento es **estructural, por sistema de ficheros**: las filas de
un perfil no existen físicamente en los ficheros del otro, de modo que la
lectura cruzada es imposible por construcción, no por disciplina de
`WHERE`. **No** se añaden columnas `profile_id` en ninguna tabla de
dominio.

```
data/
  processed/knowledge.sqlite   # COMPARTIDO, solo lectura (material inmutable)
  profiles.sqlite              # COMPARTIDO, solo metadatos (perfiles + sesiones)
  profiles/
    <slug>/
      student.sqlite
      questions.sqlite          # copia de trabajo por perfil (intentos + exámenes generados)
      exam_sessions.sqlite
      backups/<UTC-ISO>/…
```

Descartados (registro): **B — row-scoping** por `profile_id` en ficheros
compartidos (superficie de auditoría permanente, un `WHERE` ausente = fuga;
justamente lo que vigilan los tests IDOR de F7/F10, multiplicado).
**C — mínimo** sin sesiones persistentes ni migraciones formales
(incumple la intención de "fundaciones para producción").

## 4. Perfiles

### 4.1 Datos

`data/profiles.sqlite`, fichero compartido, **solo metadatos** (ningún
dato de estudio) — por eso es seguro leerlo sin contexto de perfil.

```sql
CREATE TABLE profiles(
  slug            TEXT PRIMARY KEY,   -- [a-z0-9-]{1,32}, derivado del display_name
  display_name    TEXT NOT NULL,
  created_utc     TEXT NOT NULL,      -- ISO-8601 UTC
  last_active_utc TEXT NOT NULL
);
```

`slug`: `display_name` en minúsculas, no alfanumérico → `-`, colapsar
`-` repetidos, recortar extremos, 1–32 chars. Cadena vacía tras
normalizar → `VALIDATION_ERROR`.

### 4.2 Endpoints

| Método | Ruta | Efecto |
|---|---|---|
| `GET`  | `/api/profiles` | lista `[{slug, display_name, last_active_utc}]` |
| `POST` | `/api/profiles/create` | `{display_name}` → inserta + selecciona; slug en colisión → `409 SLUG_TAKEN` |
| `POST` | `/api/profiles/select` | `{slug}` → fija el perfil de la sesión y **rota la sesión** (nuevo `sm_session`, nuevo `csrf`); slug inexistente → `404 NOT_FOUND` |

- El primer arranque sin perfiles sirve `web/profile.html` (pantalla de
  reclamo: display name → slug). Sin campo de contraseña.
- La app **nunca borra** un perfil ni su directorio (eso es tarea de la
  CLI de backup/restore, §8).
- Rutas exentas de `NO_PROFILE` (§5.4): estáticos, `/api/profiles*`,
  `/api/session`.

### 4.3 `web/profile.html`

Página estática mínima, mismo design system que el resto (`tokens.css`
etc.). Lista perfiles existentes (botón "entrar") + formulario "crear
perfil". Un JS nuevo `web/static/js/profile.js`. Sin dependencias.

## 5. Sesiones, expiración, CSRF, validación de permisos HTTP

### 5.1 Almacén de sesiones

Sustituye el `dict` en memoria `Bridge.sessions` por una tabla en
`profiles.sqlite` (compartida, sobrevive a reinicios):

```sql
CREATE TABLE sessions(
  token         TEXT PRIMARY KEY,   -- secrets.token_hex(24)
  profile_slug  TEXT,               -- NULL = cookie reclamada, perfil sin elegir
  csrf          TEXT NOT NULL,      -- secrets.token_hex(24)
  created_utc   TEXT NOT NULL,
  last_seen_utc TEXT NOT NULL
);
```

- El scratch de workflow de práctica (hoy
  `sessions[tok]["practice"]`) pasa a un cache en memoria
  `{token: practice_sess}` por proceso — es estado efímero de workflow,
  no merece persistencia; en fallo de cache el workflow lo re-deriva de
  la BD (ya es como degradan `_get`/`_put`).

### 5.2 Expiración

Dos cotas, desde `.env`, evaluadas en cada petición autenticada:

| Variable | Default | Comprobación |
|---|---|---|
| `SM_SESSION_IDLE_TIMEOUT` | `43200` (12 h) | `now - last_seen_utc` |
| `SM_SESSION_MAX_AGE` | `1209600` (14 d) | `now - created_utc` |

Vencida → fila borrada, `401 {code: "SESSION_EXPIRED"}`; el frontend
vuelve a la pantalla de reclamo/conmutación. `last_seen_utc` se
actualiza en cada petición autenticada válida.

### 5.3 CSRF — double-submit

- Cookie `sm_session`: `HttpOnly; SameSite=Strict; Path=/`
  (`+ Secure` cuando `SM_TLS=1`).
- Cookie `sm_csrf`: legible por JS, `SameSite=Strict; Path=/`, valor =
  `csrf` de la sesión.
- Toda petición mutante (`POST /api/*`) debe enviar cabecera
  `X-CSRF-Token` igual a **la cookie `sm_csrf` y** al `csrf` almacenado
  en la sesión. Ausente / distinto → `403 {code: "CSRF"}`.
- `GET` nunca muta (auditoría B0: todos los `GET /api/*` actuales son
  lecturas — se verifica y se congela con test).
- JS vanilla: un helper lee `sm_csrf` y pone la cabecera; se conecta al
  wrapper `fetch` existente en `web/static/js/app.js`.

### 5.4 `NO_PROFILE`

Petición a `/api/*` (salvo exentas §4.2) con cookie de sesión pero
`profile_slug IS NULL` → `401 {code: "NO_PROFILE"}`; el frontend redirige
a `profile.html`.

### 5.5 Guarda de permisos a nivel bridge

Antes de toda llamada de workflow que reciba un id (`session_id`,
`exam_id`, `attempt_id`, id de corrección): comprobar que el recurso
resuelve dentro de las BDs del perfil actual; si no → `404 {code:
"NOT_FOUND"}` (no `403` — no confirmar existencia).

Con ficheros por perfil esto es casi automático (el examen del otro
perfil no está en tu BD), pero la guarda explícita es el ancla de
regresión y sigue siendo correcta si algún día los perfiles comparten
almacenamiento. Reutiliza las comprobaciones de propiedad ya presentes
en F7/F10; añade la guarda donde el bridge hoy pasa ids sin verificar.

### 5.6 `GET /api/session`

Bootstrap para el frontend: `{profile: slug|null, csrf, expires_in}`.
Exenta de `NO_PROFILE`. Crea la sesión + cookies si no existen.

## 6. `Bridge` por (hilo, perfil)

`Bridge.__init__` ya toma `workdir` y copia `GENDB` dentro. Cambios:

- `Handler.thread_bridge()` → `thread_bridge(profile_slug)`, cache
  `{(thread_id, slug): Bridge}`.
- `workdir = data/profiles/<slug>/`, creado en primer uso; la BD de
  preguntas se siembra por `shutil.copyfile` desde el canónico
  `data/generated/questions.sqlite` **solo si no existe** (idempotente,
  igual que la lógica actual).
- La constante `DEMO_STUDENT` se **elimina**. Cada punto de uso (~30)
  toma `self.profile`, fijado al construir el `Bridge`. Edición
  mecánica.
- El KB sigue `mode=ro` y compartido.

## 7. Study tras la Application Layer

Nuevo `app/application/study.py` — `StudyWorkflow(app)`, misma forma que
`TutorWorkflow` etc. Métodos, todos con `ctx`:

- `topics(ctx)` → conteos doc/sección/fórmula/concepto por tema +
  mastery de **este** perfil (mueve `Bridge.kb_topics`).
- `documents(ctx, topic)`, `sections(ctx, doc_id)`,
  `content(ctx, section_id)` → lecturas KB solo lectura (mueven
  `kb_documents` / `kb_sections` / `kb_content`).
- `next(ctx)` → passthrough de recomendación (ya delega en
  `app.adaptive`).
- `mastery(ctx, topic?)` → `app.students.get_topic_mastery`.

El handle del KB (`mode=ro`) lo posee `ApplicationService`, se abre una
vez y se pasa al workflow — el bridge deja de abrir SQLite directamente.
Las rutas `/api/study/*` quedan como llamadas finas
`self.flows["study"].<método>(ctx)`, igual que el resto. Neto: `Bridge`
pierde ~120 líneas de SQL inline; los helpers `kb_*` se borran.

## 8. `.env`, backups, migraciones

### 8.1 `.env`

`app/env.py` — ~15 líneas, stdlib: lee líneas `KEY=VALUE` (`#`
comentarios, líneas en blanco, comillas envolventes opcionales, sin
interpolación, sin `export`). `load_env(path)` fija claves en
`os.environ` **solo si no están presentes** (el entorno real gana).

- `web/server.py main()` llama a `load_env` antes de parsear args; ruta
  desde `--env` o `./.env`.
- Claves (superset del `.env.example` actual): `SM_HOST`, `SM_PORT`,
  `SM_DATA_DIR`, `SM_TLS`, `COURSE_CALENDAR_PATH`, `GEMINI_API_KEY`,
  `GEMINI_MODEL`, `SM_SESSION_IDLE_TIMEOUT`, `SM_SESSION_MAX_AGE`,
  `SM_BACKUP_DIR`.
- `.env.example` actualizado con las nuevas claves + comentarios.
  `.env` sigue en `.gitignore`.
- `.env` ausente no es error (todas las claves tienen default).
  `GEMINI_API_KEY` ausente → fallback `ExtractiveProvider` existente,
  sin cambios.

### 8.2 Backup / restore

CLI `python -m app.backup` (nunca endpoint web — destructivo):

- `backup --profile <slug> [--all]` → para cada uno de
  `student.sqlite`, `questions.sqlite`, `exam_sessions.sqlite`: abrir
  origen, `.backup()` online de `sqlite3` hacia
  `data/profiles/<slug>/backups/<UTC-ISO>/`. Consistente bajo escrituras
  concurrentes. Escribe `manifest.json` (ficheros, tamaños, sha256,
  `user_version` por fichero, versión de app).
- `restore --profile <slug> --from <timestamp>` → pre-backup del estado
  actual a `backups/<UTC>-pre-restore/`, luego copia los ficheros del
  snapshot de vuelta. Rechaza si el `user_version` de un fichero del
  snapshot es **más nuevo** que el objetivo del código (necesitaría una
  migración que no puede hacer).
- `list --profile <slug>` → tabla de snapshots desde los manifests.
- KB y `profiles.sqlite` excluidos — el KB es regenerable/inmutable; los
  metadatos de perfil son triviales y compartidos.
- `SM_BACKUP_DIR` reubica la raíz de backups (p. ej. disco externo);
  default bajo cada dir de perfil.

### 8.3 Migraciones / versionado de esquema

`PRAGMA user_version` por fichero, **forward-only**:

- `app/migrations/<db_name>/NNN_descripcion.sql` (o `.py` con
  `def up(conn)` para movimientos de datos). `<db_name>` ∈ `student`,
  `questions`, `exam_sessions`, `profiles`, `knowledge`.
- `app/migrate.py` — `migrate(conn, db_name, target)`: lee
  `user_version`, aplica cada `NNN` > actual en una transacción cada
  una, sube `user_version`. Se ejecuta automáticamente cuando un store
  abre su conexión.
- **Baseline:** el esquema vivo actual se captura como
  `001_baseline.sql` por BD; todo `CREATE TABLE IF NOT EXISTS` inline de
  los stores existentes se mueve ahí. Es no-op sobre BDs pobladas, real
  sobre dirs de perfil nuevos. El store solo llama a `migrate()`.
- `knowledge.sqlite` también recibe sello de versión (solo lectura, sus
  migraciones son re-ingesta manual, pero el sello permite a `restore` y
  al arranque detectar desajuste y **rechazar** en vez de corromper).
- CLI: `python -m app.migrate --status` (actual vs objetivo por BD),
  `--check` (exit != 0 si hay pendientes — gate pre-deploy).
- Sin down-migrations. Rollback = restore desde backup (§8.2).

## 9. Pruebas y criterio de salida

| Test | Cubre |
|---|---|
| `tests/web/test_profiles.py` | reclamo, conmutación, validación/colisión de slug, gating `NO_PROFILE`, rotación de sesión al conmutar |
| `tests/web/test_session_security.py` | CSRF reject (ausente/distinto), expiración idle + absoluta, `GET` nunca exige CSRF, forma de respuesta de sesión vencida |
| `tests/web/test_permission_guard.py` | perfil A no alcanza `session_id`/`exam_id`/`attempt_id` de B (→ `NOT_FOUND`); patrones IDOR de F7/F10 |
| `tests/application/test_study_workflow.py` | paridad: salida de `StudyWorkflow` == salida de los `kb_*` inline para un fixture KB fijo; KB abierto solo lectura (escritura lanza) |
| `tests/test_env.py` | comillas/comentarios/blancos, precedencia del entorno real, fichero ausente OK |
| `tests/test_backup_restore.py` | backup→mutar→restore round-trip byte-idéntico; hashes de manifest; restore rechaza `user_version` más nuevo |
| `tests/test_migrations.py` | BD nueva alcanza objetivo; baseline no-op sobre BD poblada; exit code de `--check`; `NNN` fuera de orden/duplicado rechazado |
| `tests/web/test_two_profile_isolation.py` | **criterio de salida** (ver abajo) |

**Test de criterio de salida** — un servidor, un cliente de test: crear
perfiles `ada` y `blai`; como `ada` generar + calificar un examen,
ejecutar práctica adaptativa (mueve mastery), leer historial; conmutar a
`blai`; afirmar que `blai` ve cero exámenes / cero intentos / mastery
vacío / historial vacío, y no puede recuperar ninguno de los ids de
`ada`; conmutar de vuelta a `ada`, afirmar su estado intacto. Aserción
de sistema de ficheros: `data/profiles/blai/` no contiene ninguna fila
de las BDs de `ada`.

**Regresión completa** (`pytest tests/`) en verde — las ~30 ediciones de
`DEMO_STUDENT` y el refactor de Study son el riesgo; las suites de
dominio F0–F11 deben quedar intactas y en verde.

## 10. Secuencia de bloques

| Bloque | Contenido |
|---|---|
| **B0** | Preauditoría (doc, sin código): enumerar cada punto `DEMO_STUDENT`, cada punto de SQL directo en `Bridge`, comportamiento actual de sesión/cookie, todas las rutas `/api` × método × mutación. |
| **B1** | Loader `.env` + `app/migrate.py` + `001_baseline` por BD + stores llaman a `migrate()`. Regresión en verde. |
| **B2** | `profiles.sqlite`, endpoints CRUD/select de perfil, `web/profile.html`, `Bridge` por (hilo, perfil), eliminar `DEMO_STUDENT`. Gating `NO_PROFILE`. |
| **B3** | Tabla `sessions` persistente, expiración idle/absoluta, CSRF double-submit, guarda de permisos a nivel bridge. |
| **B4** | `StudyWorkflow`; `/api/study/*` + `kb_*` salen de `Bridge`. |
| **B5** | CLI `app/backup` (backup/restore/list). |
| **B6** | Certificación: test de aislamiento de dos perfiles, regresión completa ×2, `docs/PHASE_12_CERTIFICATION.md`, entradas en `DECISION_LOG`. |

## 11. Decisiones (para `DECISION_LOG` en B6)

| # | Decisión | Motivo | Alternativas |
|---|---|---|---|
| D169 | Perfiles locales sin contraseña, confianza honor-system | Herramienta de estudio local; multi-usuario real con auth es fase posterior | Contraseñas + hash scrypt (provisión + superficie no justificadas hoy) |
| D170 | Aislamiento por directorio por perfil, sin `profile_id` | Aislamiento estructural: fuga imposible por construcción; backup = copiar dir | Row-scoping (un `WHERE` ausente = fuga) |
| D171 | KB y `profiles.sqlite` compartidos y excluidos de backup | KB inmutable/regenerable; metadatos de perfil triviales | Copia por perfil (duplicación inútil) |
| D172 | Sesiones persistidas en `profiles.sqlite` | "Expiración de sesión" es requisito; sobrevive a reinicio | Dict en memoria (se pierde al reiniciar) |
| D173 | CSRF double-submit + `SameSite=Strict` | Stdlib, encaja con el JS vanilla existente | Token en sesión sin cookie espejo (necesita endpoint extra en cada carga) |
| D174 | Migraciones forward-only con `user_version`, sin down | Rollback = restore desde backup; down-migrations son código muerto casi siempre | Herramienta de migración con dependencia externa |
| D175 | Study movido a `StudyWorkflow`, KB solo lectura vía `ApplicationService` | El brief lo pide; homogeneiza con el resto de rutas; -120 líneas de SQL en el bridge | Dejar `kb_*` en el bridge (incoherente, sin `ctx`) |
