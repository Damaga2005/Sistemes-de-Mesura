"""Genera data/evaluation/retrieval_benchmark.jsonl con gold verificado.

Cada restriccion gold se comprueba por busqueda directa en chunks.jsonl
(si falla, el script aborta): el gold esta anclado al contenido real,
no a la salida del retriever. Split dev/test estratificado por categoria.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))
P = WORKSPACE / 'data' / 'processed'
CHUNKS = [json.loads(l) for l in (P / 'chunks.jsonl').read_text(encoding='utf-8').splitlines()]

# (id, query, lang, category, topics, text_contains, formula_contains, source_contains, abstain)
ITEMS = [
    # A. Conceptos
    ('A01', 'què és la incertesa expandida?', 'ca', 'concept', [2], ['incertesa expandida'], [], [], False),
    ('A02', 'qué es la GUM?', 'es', 'concept', [2], ['GUM'], [], [], False),
    ('A03', 'què és el pont de Wheatstone?', 'ca', 'concept', [6], ['Wheatstone'], [], [], False),
    ('A04', 'què és una LVDT?', 'ca', 'concept', [7], ['LVDT'], [], [], False),
    ('A05', 'qué es un termopar?', 'es', 'concept', [9], ['termoparell'], [], [], False),
    ('A06', 'què és el soroll tèrmic?', 'ca', 'concept', [4], ['Soroll tèrmic', 'soroll tèrmic'], [], [], False),
    # B. Fórmulas
    ('B01', 'fórmula de la incertesa expandida', 'ca', 'formula', [2], [], ['U=k'], [], False),
    ('B02', 'como se calcula uc', 'es', 'formula', [2], [], ['u_c'], [], False),
    ('B03', 'fórmula de U amb k=2', 'ca', 'formula', [2], [], ['U=k'], [], False),
    ('B04', 'expresión del termistor NTC', 'es', 'formula', [5], [], ['R_{NTC}'], [], False),
    ('B05', 'fórmula del soroll shot', 'ca', 'formula', [4], [], ['2qI'], [], False),
    ('B06', 'equació de l amplada de banda equivalent de soroll', 'ca', 'formula', [4], [], ['B_{eq}'], [], False),
    ('B07', 'fórmula de l efecte Hall', 'ca', 'formula', [7], [], ['V_H'], [], False),
    ('B08', 'tensió del termoparell en funció de la temperatura', 'ca', 'formula', [9], [], ['alpha'], [], False),
    # C. Variables
    ('C01', 'què significa uc?', 'ca', 'variable', [2], ['típica', 'tipica'], ['u_c'], [], False),
    ('C02', 'qué significa k en la incertesa expandida?', 'es', 'variable', [2], ['cobertura'], ['k'], [], False),
    ('C03', 'què és Z en un sensor reactiu?', 'ca', 'variable', [7, 8], ['impedància'], ['Z'], [], False),
    ('C04', 'què representa beta en una NTC?', 'ca', 'variable', [5], [], ['beta'], [], False),
    ('C05', 'què és la constant de temps d un primer ordre?', 'ca', 'variable', [1], ['constant de temps'], [], [], False),
    # D. Unidades
    ('D01', 'en quina unitat s expressa la resistència?', 'ca', 'unit', [1, 5], ['ohm'], [], [], False),
    ('D02', 'unidades del soroll tèrmic en un amplificador', 'es', 'unit', [4], [], [], [], False),
    ('D03', 'què mesura un sensor en Hz?', 'ca', 'unit', [4, 8], ['freqüència'], [], [], False),
    ('D04', 'unitats de la sensibilitat d un sensor', 'ca', 'unit', [1], ['sensibilitat'], [], [], False),
    # E. Procedimientos
    ('E01', 'com es calcula la incertesa expandida pas a pas?', 'ca', 'procedure', [2], ['factor de cobertura'], ['U=k'], [], False),
    ('E02', 'cómo se compensan los corrientes de polarización?', 'es', 'procedure', [10], ['polarització'], [], [], False),
    ('E03', 'mesura de resistència a 3 fils', 'ca', 'procedure', [6], ['3 fils'], [], [], False),
    ('E04', 'compensació de la unió freda del termoparell', 'ca', 'procedure', [9], ['unió freda'], [], [], False),
    ('E05', 'com es tria la freqüència de treball d un sensor capacitiu?', 'ca', 'procedure', [7], ['freqüència de treball'], [], [], False),
    # F. Comparaciones
    ('F01', 'diferencia entre incertesa de tipus A i tipus B', 'ca', 'comparison', [2], ['tipus A', 'tipus B'], [], [], False),
    ('F02', 'diferencia entre sensibilitat i resolució', 'ca', 'comparison', [1], ['sensibilitat', 'resolució'], [], [], False),
    ('F03', 'detecció coherent enfront de no coherent', 'ca', 'comparison', [8], ['coherent'], [], [], False),
    ('F04', 'chopper contra autozero', 'ca', 'comparison', [10], ['chopper', 'autozero'], [], [], False),
    ('F05', 'diferencia entre error e incertidumbre', 'es', 'comparison', [2], ['Error', 'error'], [], [], False),
    # G. Ambigüedad (varios temas aceptables)
    ('G01', 'sensibilitat', 'ca', 'ambiguity', [1, 2, 6, 7], ['sensibilitat'], [], [], False),
    ('G02', 'resolució', 'ca', 'ambiguity', [1, 4, 10], ['resolució'], [], [], False),
    ('G03', 'error', 'ca', 'ambiguity', [1, 2, 3], ['error'], [], [], False),
    ('G04', 'incertesa', 'ca', 'ambiguity', [2, 4], ['incertesa'], [], [], False),
    ('G05', 'transimpedància', 'ca', 'ambiguity', [6, 10], ['transimped'], [], [], False),
    ('G06', 'soroll', 'ca', 'ambiguity', [2, 3, 4, 10], ['soroll'], [], [], False),
    # H. Visuales
    ('H01', 'figura del model elèctric de la LVDT', 'ca', 'visual', [7], ['LVDT'], [], [], False),
    ('H02', 'corbes de les distribucions de probabilitat uniforme i triangular', 'ca', 'visual', [2], ['uniforme', 'triangular'], [], [], False),
    ('H03', 'esquema del pont de Wheatstone', 'ca', 'visual', [6], ['Wheatstone'], [], [], False),
    ('H04', 'fotografia d una galga extensiomètrica', 'ca', 'visual', [5], ['galga'], [], [], False),
    # I. Topic isolation
    ('I01', 'Tema 3 interferències conduïdes', 'ca', 'topic', [3], ['conduïdes'], [], ['Tema 3/'], False),
    ('I02', 'Tema 2 factor de cobertura', 'ca', 'topic', [2], ['cobertura'], [], ['Tema 2/'], False),
    ('I03', 'Tema 9 efecte Seebeck', 'ca', 'topic', [9], ['Seebeck'], [], ['Tema 9/'], False),
    ('I04', 'Tema 5 termistors NTC', 'ca', 'topic', [5], ['NTC'], [], ['Tema 5/'], False),
    ('I05', 'Tema 3 sensibilitat', 'ca', 'topic', [3], [], [], ['Tema 3/'], False),
    ('I06', 'Tema 2 incertesa', 'ca', 'topic', [2], ['incertesa'], [], ['Tema 2/'], False),
    # Tolerancia a errores / ES ya incluidos arriba; typos:
    ('T01', 'incerteza expandida', 'es-typo', 'concept', [2], ['incertesa expandida'], [], [], False),
    ('T02', 'que es el puente de Wheatston', 'es-typo', 'concept', [6], ['Wheatstone'], [], [], False),
    ('T03', 'sensibilidad y resolucion de un sensor', 'es', 'comparison', [1], ['sensibilitat', 'resolució'], [], [], False),
]


def check(item):
    _id, _q, _lang, _cat, topics, texts, forms, srcs, abst = item
    if abst:
        return
    ok = False
    for c in CHUNKS:
        if c['topic'] not in topics:
            continue
        if texts and not any(t in c['text'] for t in texts):
            continue
        if srcs and not any(s in c['source_path'] for s in srcs):
            continue
        if forms:
            ftexts = ' '.join(f for f in [c['text']] )
            if not any(f in c['text'] for f in forms):
                # buscar en formulas.jsonl del chunk
                continue
        ok = True
        break
    return ok


def main():
    # Verificar grounding de text_contains y source_contains en chunks del topic.
    bad = []
    for item in ITEMS:
        _id, _q, _lang, _cat, topics, texts, forms, srcs, abst = item
        if abst:
            continue
        found = False
        for c in CHUNKS:
            if c['topic'] not in topics:
                continue
            if texts and not any(t in c['text'] for t in texts):
                continue
            if srcs and not any(s in c['source_path'] for s in srcs):
                continue
            found = True
            break
        if not found:
            bad.append(_id)
    # Verificar formula_contains en formulas.jsonl del topic.
    forms = {}
    for line in (P / 'formulas.jsonl').read_text(encoding='utf-8').splitlines():
        import json as j
        f = j.loads(line)
        forms.setdefault(f['topic'], []).append(f['expression'])
    for item in ITEMS:
        _id, _q, _lang, _cat, topics, texts, fcs, srcs, abst = item
        if abst or not fcs:
            continue
        if not any(any(fc in e for e in forms.get(t, [])) for fc in fcs for t in topics):
            bad.append(_id + ':formula')
    if bad:
        raise SystemExit('gold sin grounding: %s' % bad)
    # Verificar ausencia para abstención.
    abst_items = [
        ('J01', 'Què diu el Tema 20 sobre la incertesa?', 'ca', 'abstention', 'Tema 20'),
        ('J02', 'Qui va guanyar la Champions el 2026?', 'ca', 'abstention', 'Champions'),
        ('J03', 'Quina és la recepta de la paella?', 'ca', 'abstention', 'paella'),
        ('J04', 'Qui és el president dels Estats Units?', 'ca', 'abstention', 'president'),
        ('J05', 'Com funciona la fotosíntesi?', 'ca', 'abstention', 'fotosíntesi'),
        ('J06', 'Qui va escriure Don Quixot de la Manxa?', 'ca', 'abstention', 'Quixot'),
    ]
    for _id, _q, _lang, _cat, probe in abst_items:
        hits = [c['id'] for c in CHUNKS if probe.lower() in c['text'].lower()]
        if hits:
            raise SystemExit('abstención contaminada %s: %s' % (_id, hits[:3]))
    # Split estratificado por categoría: 1 de cada 3 a test.
    out = []
    counters = {}
    for item in ITEMS:
        cat = item[3]
        counters[cat] = counters.get(cat, 0) + 1
        split = 'test' if counters[cat] % 3 == 0 else 'dev'
        _id, q, lang, _c, topics, texts, fcs, srcs, abst = item
        out.append({'id': _id, 'query': q, 'lang': lang, 'category': _c,
                    'expected_topics': topics, 'text_contains': texts,
                    'formula_contains': fcs, 'source_contains': srcs,
                    'abstain_expected': abst, 'split': split})
    for _id, q, lang, cat, _probe in abst_items:
        counters[cat] = counters.get(cat, 0) + 1
        split = 'test' if counters[cat] % 3 == 0 else 'dev'
        out.append({'id': _id, 'query': q, 'lang': lang, 'category': cat,
                    'expected_topics': [], 'text_contains': [], 'formula_contains': [],
                    'source_contains': [], 'abstain_expected': True, 'split': split})
    dest = WORKSPACE / 'data' / 'evaluation' / 'retrieval_benchmark.jsonl'
    with dest.open('w', encoding='utf-8') as fh:
        for o in out:
            fh.write(json.dumps(o, ensure_ascii=False, sort_keys=True) + '\n')
    import collections
    print('items:', len(out), dict(collections.Counter(o['split'] for o in out)))
    print('cats:', dict(collections.Counter(o['category'] for o in out)))


if __name__ == '__main__':
    main()
