# PHASE_11_B3_BASELINE — Contratos F6/F5 auditados (B3.1)

## Público para UI

- `Recommendation`: unit, kind, action ∈ ACTIONS
  (REVIEW/PRACTICE/REINFORCE/CHALLENGE/MAINTAIN), difficulty,
  targets{topic,section,concepts,formulas}, reasons (códigos
  crudos), mastery snapshot vía `get_mastery`.
- `reason_codes` reales: `mastery:`, `evidencia:`,
  `confianza_baja:`, `raiz:<TAXONOMÍA F5>`, `fallo_reciente:`,
  `dificultad:` (+ mecànica interna `spacing:`/`categoria:`/
  `ancestro_*`, NO mostrada).
- Mastery states backend: UNKNOWN/EMERGING/DEVELOPING/PROFICIENT/
  MASTERED/AT_RISK (+score, confidence, attempts, correct,
  incorrect, error_counts, policy_version). MASTERED = score≥0.9
  con min_evidence=4 y min_correct=3 (**nunca en JS**).
- `to_spec` usa `reasons` (routing REINFORCE→NUMERICAL) y
  `priority` NO decide spec; el item viaja íntegro (incl.
  `priority`, no mostrado) para round-trip fiel.
- IDs: `topic:Txx`→tema; `section:Txx:…`→sin match KB directo;
  `concept:<terme>`→`concepts.term_ca`; `formula:eq-`→topic (+
  secció best-effort). Sin match → url null honesto.

## Interno (no UI)

priority_score (no mostrado), spacing buckets/veredictos,
categorías, epsilon/exploration, thresholds, ancestors.
