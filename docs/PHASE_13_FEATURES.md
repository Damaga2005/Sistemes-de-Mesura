# Fase 13 — Nuevas funcionalidades: recursos académicos

Estado: **GO parcial** (primer vertical implementado).

## Entregado

- `GET /api/documents` expone el catálogo real de `data/processed/knowledge.sqlite`.
- El catálogo permite filtrar por tema y devuelve `id`, título, tipo, tema,
  número de secciones y enlace de navegación.
- La respuesta etiqueta la fuente como `COURSE_SOURCE`.
- La pantalla Documents ya no es un placeholder: incluye filtro y carga
  progresiva desde el backend.
- La navegación conserva `doc_id` y permite abrir un documento concreto con
  sus seccions, en vez de obligar a recorrer todo el tema.
- `GET /api/calendar` establece el contrato del calendario. Mientras no exista
  una fuente académica configurada, devuelve una lista vacía explícita y no
  inventa clases, laboratorios ni exámenes.
- `app/calendar.py` permite cargar una fuente JSON versionada (`version: 1`)
  con `source_path` y `source_hash` obligatorios; normaliza y ordena eventos
  de forma determinista.
- La pantalla Calendar muestra ese estado de forma honesta y accesible.

## Límites deliberados

- El catálogo es de solo lectura; la autenticación multiestudiante sigue siendo
  una deuda heredada de F10/F11.
- Calendar no persiste eventos ni importa calendarios todavía. La fuente de
  horarios no está presente en el repositorio, por lo que no se generan datos.
- La lectura de la KB sigue pasando por el acceso directo read-only heredado;
  su extracción a Application Layer permanece como trabajo de F12.

## Verificación

- `pytest -q tests/web/test_f13_features.py tests/web/test_design_system.py`
  → 21 passed.
- El contrato mantiene separación `COURSE_SOURCE`/`EXTERNAL_SOURCE` y no
  expone rutas locales ni secretos.

## Próximo bloque F13

1. Añadir eventos de estudio del estudiante cuando F12 resuelva identidad y
   aislamiento.
