# PHASE_5_FAILURE_ANALYSIS — Fallos encontrados y qué enseñan

1. **`amb`-pattern en curación**: `amb i/a` no son variables (conjunción).
   Eliminado; 468→83 CONFIRMED. Lección: patrones en catalán requieren
   validación por muestreo, no solo intuición.
2. **Cita de fórmula sin comprobar latex**: aceptaba `$U=u_c/k$` citando el
   id correcto. Ahora se compara el latex (CONTRADICTED). Afecta a F3
   (compatible hacia estricticidad).
3. **Prose-records como fórmulas** en claims: el validador los trata igual;
   la cobertura del examiner ya los documenta como degenerados si aplica.
4. **Modelo estricto en abstención de sección**: la masa sobre jerarquía
   (Fase 3) evitó falsos NO_EVIDENCE en blueprints.
5. **Benchmark replay-atrapado**: IDs fijos rejuegan correcciones viejas tras
   fix; nonce por ejecución + test de idempotencia separado.
6. **Live LLM en corrección**: solo hints acotados; 1 llamada de prueba OK.
   Sin degradación determinista medida.

Cero fugas: ningún VALID con claims malos en todo el store (test de barrido),
KB bit-idéntica, eval ciego, sin diagnósticos psicológicos en memorias.
