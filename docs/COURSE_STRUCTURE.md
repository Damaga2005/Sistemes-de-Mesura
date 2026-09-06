# COURSE_STRUCTURE — Mapa académico real (Fase 0)

> Nombres extraídos literalmente de `<title>`/`<h1>`/`<h2>` del material. Nada inventado.
> Etiquetas: **[confirmed]** = leído del HTML · **[inferred]** = deducido con evidencia citada · **[unknown]** = pendiente Fase 1.

## Tema 1 — Introducció als sistemes de mesura [confirmed]
- 1. Concepte de mesura: definició · mesurar és comparar · atributs d'objectes i esdeveniments · resultat i unitat · directa/indirecta
- 2. El Sistema Internacional d'Unitats: de l'artefacte a la constant · 7 unitats base · derivades i coherència · 7 constants · prefixos · cas Mars Climate Orbiter · annex
- 3. Estructura dels sistemes de mesura: mesurand→resultat · adquisició i càrrega · condicionament · conversió A/D · processament · presentació
- 4. Sensors: definició i classificació: sensor/transductor/actuador · classificacions · principis de transducció · model elèctric · sensibilitat creuada · selecció
- 5. Característiques estàtiques: funció de resposta · sensibilitat i error de zero · linealitat · exactitud/veracitat/fidelitat · errors sistemàtics/aleatoris · histèresi, zona morta, resolució
- 6. Característiques dinàmiques: mesurand variable · tres models · resposta de primer ordre · estimació de constant de temps · excepció

## Tema 2 — Estimació de la incertesa a la mesura [confirmed]
1. Concepte d'incertesa, GUM, error vs incertesa · 2. Marc teòric (variable aleatòria, valor veritable, paràmetres estadístics, típica/expandida/k) · 3. Model matemàtic (funció de mesura, directa/indirecta, tipus A/B, hipòtesis) · 4. Tipus A (requisits, aberrants, dispersions, arrel de N) · 5. Tipus B (fonts, màxima entropia, 4 distribucions) · 6. Combinació (linealització, sensibilitats, covariància, Monte Carlo) · 7. Expandida (U=k·u_c, k=2/3, t-Student, Welch-Satterthwaite) · 8. Expressió final (balanç, dominància, format)

## Tema 3 — Interferències en Sistemes de Mesura [confirmed]
1. Fonaments i classificació (soroll vs interferència, font–canal–receptor, EMC, Directiva 2014/30/UE, IEC 61000) · 2. Mode diferencial/comú, conduïdes (CMRR, externes/internes, mitigació) · 3. Capacitives i blindatge (acoblament, cable coaxial, sondes atenuadores) · 4. Inductives (acoblament, mitigació, efecte sobre el resultat, diagnosi)

## Tema 4 — Soroll en sistemes de mesura [confirmed]
1. Introducció i caracterització estadística (procés estocàstic) · 2. Soroll tèrmic (origen, expressions, xarxes passives) · 3. Amplada de banda equivalent (definició, càlcul, exemple resolt) · 4. Shot i 1/f (Schottky, contacte, excés) · 5. Dispositius actius (model, exemple operacional) · 6. Amplificadors i disseny de baix soroll (inversor, guia de disseny)

## Tema 5 — Sensors resistius [confirmed]
Panorama (generadors vs moduladors, fonaments físics, model general, excitació) · RTD (principi, model R-T, nominals, construcció) · Autoescalfament/excitació/dinàmica · NTC (exponencial, linealització) · Construcció/PTC/aplicacions · Piezoresistius i galgues (tensió/deformació, factor de galga, rosetes) · Magnetoresistències (AMR, GMR) · LDR, higròmetres, selecció

## Tema 6 — Condicionament de sensors en contínua [confirmed]
Cadena (sortida contínua, adequació a ADC, blocs, AFE, compromisos) · R→V (2/3/4 fils, font de corrent, divisor, Wheatstone) · I→V y diferencials (càrrega, transimpedància, impedàncies) · Instrumentació (3 operacionals, INA317) · Interruptors/multiplexors/PGA (MOSFET→CMOS, errores) · Referències y ratiomètriques (sèrie/shunt, especificacions)

## Tema 7 — Sensors reactius i electromagnètics [confirmed]
Fonaments (qué son, por qué, coste alterna, frecuencia como parámetro, 4 mecanismos) · Capacitiu (model, pla, impedància, linealitat, dielèctric) · Capacitiu real (vores, guardes Kelvin, fuita, frecuencia) · Aplicacions + diferencial · Inductius + Foucault · Transformadors variables (LVDT, resolver), Hall, magnetostricció

## Tema 8 — Condicionament de sensors en alterna [confirmed]
Impedància complexa Z(f), frecuencia de trabajo, cadena lineal, modelos canónicos · Z→V (divisores, inversor capacitiu, ponts, pseudoponts) · Amplificadors d'alterna (banda, centrat, instrumentació, limitaciones AO) · No coherents (AM/DSB, RMS, multiplicadors, pic/envolupant) · Coherents (homodina, rectificació síncrona, mostreig) · Oscil·ladors (relaxació, F→V, comptatge)

## Tema 9 — Sensors generadors i unions semiconductores [confirmed]
Generadors vs moduladors, Seebeck/Peltier/Thomson · Termoparell (tipus normalitzats, conversió V–T) · Lleis, unió freda, prestacions · Piezoelèctrics (coeficients, materials, model, resposta) · Piroelèctrics (polarització, dinàmica, PIR) · Unions semiconductores (corrent constant, PTAT, calibratge)

## Tema 10 — Condicionament singular de senyals [confirmed]
Sensors singulars (nivell vs impedància), operacional real (errors estàtics, derives, soroll, tecnologies d'entrada) · Baixes derives (polarització, offset) · Chopper y autozero · Electromètrics y transimpedància (Thevenin/Norton, xarxa en T, node d'alta Z) · Càrrega (model, realimentació, contínua, triboelèctric)

## Conceptos transversales [inferred — evidencia: aparecen en ≥2 temas]
- **sensibilitat** (T1-característiques, T2-coeficients de sensibilitat, T7/T8-cadena): relación salida/mesurando; en T2 es derivada parcial del modelo. Tres acepciones contextualizadas — NO fusionar en un solo nodo (test de confusión).
- **resolució** (T1) vs **soroll** (T4, límite físico de resolución) vs **derives/offset** (T10): cadena causal para preguntas RELATION.
- **incertesa** (T2, GUM) vs **error/interferència** (T3): distinción normativa explícita en el material (T2 §1.3, T3 §1) — caso de test de confusión prioritario.
- **pont de Wheatstone** (T6) reutilizado en alterna (T8 §4): relación `aplicat-a`.
- **transimpedància** (T6 §3, T10 §3): mismo circuito, distinto contexto (corriente continua vs alta impedancia) — desambiguar por topic.
- **model del sensor**: resistivo (T5), reactivo Z(f) (T7/T8), generador Thevenin/Norton (T9/T10) — eje vertebrador del curso.

## Relaciones (solo justificadas por el material) [inferred]
- sensor `és-element-de` sistema de mesura (T1 §3) · sensor `es-classifica-segons` principi de transducció (T1 §4.2–4.3) · sensor `té` sensibilitat/resolució/linealitat/histèresi (T1 §5–6) · mesura `té` incertesa típica/combinada/expandida (T2) · incertesa tipus A `s'avalua-per` estadística / tipus B `s'avalua-per` distribució assumida (T2 §4–5) · soroll tèrmic/shot/1-f `limita` resolució (T4) · RTD/NTC/galga `són` sensors moduladors resistius (T5) · Wheatstone/divisor/font `converteix` R→V (T6) · guarda Kelvin `mitiga` efecte de vores (T7 §3.3) · detecció coherent `millora` estimació d'amplitud vs no coherent (T8 §5 vs §4) · unió freda `requereix` compensació (T9 §2) · chopper/autozero `redueix` offset/deriva (T10 §2).

## Lagunas e incertidumbres [unknown → NEEDS_REVIEW]
- Granularidad exacta PDF↔HTML por sección (solo Tema 2 muestreado a nivel global).
- Contenido de imágenes base64 sin caption completa ( Fase 1: inventario visual con `image_context`).
- Unidades/magnitudes: presentes (SI en T1 §2, especificaciones en T6/T8/T9) pero sin catálogo cerrado — Fase 1 extraerá el glosario desde el texto, no desde conocimiento externo.
