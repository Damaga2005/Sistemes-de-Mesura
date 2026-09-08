# PHASE_11_B0_PREAUDIT — Preauditoría UI/UX (B0, sin implementar)

## B0.1 Inventario actual

**Frontend: NO EXISTE.** 0 ficheros HTML/CSS/JS/templates/assets;
0 frameworks (sin Flask/FastAPI/routes/controllers); 0 dependencias
declaradas (sin requirements/pyproject/package.json; stdlib+sqlite).
**Presentación existente: 3 CLIs** (`app/answer.py`, `app/correct.py`,
`app/retrieve.py`: argparse + salida JSON) y runners de benchmark.
`html_extract.py`/`jsdata.py`/`questions.py` son parsers de ingesta
(solo lectura), no UI. **Backend listo: `app/application/`**
(Tutor/Practice/Adaptive/Exam/Review) + dominios F0–F9.

## B0.2 Capability inventory

| Capacidad | Backend | Façade | UI exist. | UI necesaria |
|---|---|---|---|---|
| Tutor | sí (F3) | sí | CLI | pantalla Q/A + evidencia |
| Practice | sí (F4+F5) | sí | CLI | jugador de preguntas |
| Adaptive | sí (F6) | sí | no | recomendaciones + prior. |
| Exam | sí (F7) | sí 1:1 | no | flujo CREATED→GRADED |
| Review | sí (F7+policy) | sí | no | vistas por policy |
| Mastery/progress | sí (F5) | parcial (`get_result/units`) | no | panel/detalle |
| Documents | **parcial**: chunks con `source_path`, sin endpoint de listado | no | no | lector teórico |
| Subjects | **no**: un solo curso (230920); sin API | no | no | selector si hay N cursos |
| Calendar | **no**: sin tablas ni servicio | no | no | C (capability missing) |

## B0.3–B0.4 Journeys e IA

Journeys 1–5 según prompt, todos resolubles con façades existentes
salvo Documents (sin listado) y Calendar (inexistente). La hipótesis
HOME/STUDY/LEARNING/EXAMS/DOCUMENTS/CALENDAR **no valida tal cual**:
DOCUMENTS exige endpoint de listado (B) y CALENDAR es capacidad C.
Propuesta B1+: arrancar con STUDY/LEARNING/EXAMS; DOCUMENTS y
CALENDAR quedan para B7 tras decidir B/C/D.

## B0.5 State×View

| Estado × Vista | STEM | RESULT | REVIEW | MASTERY |
|---|---|---|---|---|
| CREATED/READY | preparar | prohibido | prohibido | — |
| IN_PROGRESS | pregunta+controles | prohibido | prohibido | — |
| SUBMITTED/EXPIRED | solo lectura | parcial* | prohibido | — |
| GRADED | lectura | score | según policy | vista |
| CANCELLED | bloqueado | prohibido | prohibido | — |
| REAL_EXAM×REVIEW | — | score ciego | blind certificado | sin claves |

*`get_result` admite SUBMITTED (contrato). Timer/expiración los
impone F7; la UI solo los muestra.

## B0.6–B0.7 Seguridad y ownership

Sin UI no hay fuga; al construirla: consumir **solo** `stem_view`,
`VerifiedAnswer` proyectada y feedbacks por policy (claves sensibles
ya ausentes: answer keys, rubrics —`reveal_rubric: False`—, prompts,
CoT, SQL, paths). REAL_EXAM ciego verificado en 2 rutas. Ownership lo
valida Application/Domain (`_own`, NOT_FOUND anti-enumeración); la UI
**no es frontera** y no debe reimplementar checks como única defensa.
`list_sessions` ya es por-estudiante.

## B0.8–B0.9 Responsive y accesibilidad

Sin UI que auditar: requisitos para B8. Exam: fórmulas/tablas/
imágenes (base64+caption en KB), opciones, timer, navegación.
Tutor/review: contenido largo + evidencia. Fórmulas necesitan
render LaTeX con alternativa textual (lectura). Feedback nunca solo
color; timer con texto; targets táctiles; foco visible y teclado
completo; katakana n/a — contenido catalán.

## B0.10 Sistema visual

Vacío actual. Dirección: minimalista limpio moderno (evitar clonar
estética propietaria). Conceptos: tipografía legible con catalán,
espaciado generoso, cards, botones/inputs, badges de estado de
examen, progreso de mastery, empty/error/loading states. Sin valores
CSS todavía (B1).

## B0.11 Fórmulas y contenido

KB preserva LaTeX (`<!-- $...$ -->`), sub/superíndices, variables,
unidades, tablas, imágenes base64, referencias y catalán; review
expone `formula{latex,…}` cuando la policy revela. Regla UI: render
puede transformar visualmente, jamás el significado canónico
(2896/2896 intacto).

## B0.12 Multilingüismo

`ca` por defecto (`config.LANGUAGE`), `es` soportado en contexto,
feedback (`ERROR_HUMAN`, hints, bandas) y review (`feedback_lang`).
Cadenas hardcoded ca/es sin framework i18n; errores AppError en
español. Estado: bilingüe de facto, sin infraestructura (B7/B8).

## B0.13 Performance

Sin assets ni N+1 hoy (todo local SQLite). Riesgos al construir UI:
`get_review` por pregunta (preferir review completo), provenance
extensa, listas largas de mastery, payloads de feedback con fórmulas.
Sin optimizar (medir en B9).

## B0.14 Estados UI

Cubiertos por contratos: LOADING/EMPTY (presentación), NOT_FOUND,
STATE_ERROR→{IN_PROGRESS…}, VALIDATION/USER_ERROR, ABSTAIN,
RETRIEVAL/GENERATION/CORRECTION/PERSISTENCE/POLICY_ERROR,
GRADED/EXPIRED/CANCELLED/SUBMITTED/GRADING_INCOMPLETE. Sin estados
nuevos de dominio.

## B0.15 Product gaps

- **A (UI missing)**: Tutor, Practice, Adaptive, Exam, Review,
  Mastery/progress (façade parcial suficiente para panel).
- **B (integración posterior)**: listado de documentos (chunks con
  `source_path` pero sin endpoint), selector multi-curso.
- **C (capability missing)**: Calendar/clases/labs; CRUD de
  documentos; notificaciones.
- **D (decisión)**: navegación exacta; orden DOCUMENTS/CALENDAR;
  login/identidad de estudiante (hoy `technical_student_id` sin
  auth); multi-curso.

## B0.16 Anti-duplicación

Sin JS/UI: nada que duplicar hoy → todo SAFE por ausencia. Reglas
B1+: scoring/grading/mastery/adaptive/review-policy/fórmulas/estados
solo en backend; UI consume DTOs; validaciones críticas nunca solo
client-side; ningún acceso SQLite desde presentación (CLIs actuales
usan servicios, patrón a mantener). 0 WARNING/P0/P1/P2/P3.

## B0.17 Arquitectura propuesta

```text
Pantallas (presentación pura, sin estado de negocio)
  │ DTOs: stem_view, VerifiedAnswer proyectada, resultados,
  │       recommendations, reviews por policy, mastery states
  ▼
app/application/ (único puerto: workflows + AppError)
  ▼
Dominios F0–F9  ▼  Datos canónicos
```

Pantalla→workflow: Study→Tutor/Practice; Learning→Adaptive/Practice;
Exams→Exam/Review; Progress→Practice.get_result/Review mastery_view.
Sin contratos nuevos en B0.

## B0.18 Roadmap propuesto

B1 Design System + App Shell (incluye navegación base) · B2 Study
(Tutor/Practice) · B3 Adaptive/Mastery · B4 Exam · B5 Review ·
B6 Documents (requiere endpoint B) + Calendar (requiere C) · B7 i18n
y gaps B/D · B8 responsive+accesibilidad · B9 integración/E2E +
perf · B10 certificación UX. Ajusta la hipótesis del prompt
fusionando shell en B1 y condicionando B6 a B/C/D.

## Hallazgos y veredicto

P0: 0 · P1: 0 · P2: 2 (DOCUMENTS sin endpoint; CALENDAR inexistente —
ambos categoría B/C, fuera de UI) · P3: 0.

```text
F11-B0
======

STATUS: GO

P0: 0
P1: 0

UI implementation: NOT STARTED
Domain changes: 0
Application changes: 0
KB changes: 0
Evaluation changes: 0

F0–F10 integrity: PASS

NEXT:
F11-B1 — Design System / App Shell

STOP
```
