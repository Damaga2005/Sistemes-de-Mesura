"""F18-02: changing CA<->ES must not reload away in-progress exam state.

There is no DOM test runner in this repo (only `node --check`), so behaviour is
proven with small Node harnesses that stub the minimal browser surface and drive
the real `i18n.js` / `exam.js` code paths.
"""
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
JS = ROOT / "web/static/js"
I18N = (JS / "i18n.js").read_text(encoding="utf-8")
SHELL = (JS / "shell.js").read_text(encoding="utf-8")
EXAM = (JS / "exam.js").read_text(encoding="utf-8")


def _run_node(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", "-e", script], capture_output=True, text=True,
                          cwd=str(ROOT))


# ---------------------------------------------------------------- i18n.js core

def test_i18n_setlang_behaviour():
    """Cases A/B (outside exam) + D (live handler) + throwing listener."""
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/i18n.js', 'utf8');
        function fresh() {
          let reloads = 0;
          const store = {};
          const window = {
            localStorage: {
              getItem: k => (k in store ? store[k] : null),
              setItem: (k, v) => { store[k] = String(v); },
            },
            location: { reload: () => { reloads++; } },
          };
          const document = { documentElement: {
            _a: {}, setAttribute(k, v) { this._a[k] = v; }, getAttribute(k) { return this._a[k]; },
          } };
          new Function('window', 'document', src)(window, document);
          return { i: window.smI18n, r: () => reloads, store,
                   html: () => document.documentElement.getAttribute('lang') };
        }
        function ok(c, m) { if (!c) { console.error('FAIL: ' + m); process.exit(1); } }

        // default
        let e = fresh();
        ok(e.i.lang === 'ca', 'default lang ca');
        ok(e.html() === 'ca', 'html lang ca at load');
        ok(typeof e.i.onChange === 'function', 'onChange exported');

        // Case A: CA -> ES, no listener -> reload once, state updated
        e = fresh();
        e.i.setLang('es');
        ok(e.i.lang === 'es', 'A lang es');
        ok(e.store['sm-lang'] === 'es', 'A persisted es');
        ok(e.html() === 'es', 'A html lang es');
        ok(e.r() === 1, 'A reload once when nothing handled it');

        // Case B: ES -> CA
        e.i.setLang('ca');
        ok(e.i.lang === 'ca' && e.store['sm-lang'] === 'ca' && e.r() === 2, 'B es->ca reload');

        // invalid value is a no-op
        e.i.setLang('fr');
        ok(e.i.lang === 'ca' && e.r() === 2, 'invalid lang ignored');

        // Case D: a listener that returns true suppresses the reload, repeatedly
        e = fresh();
        let calls = 0;
        e.i.onChange(() => { calls++; return true; });
        e.i.setLang('es'); e.i.setLang('ca'); e.i.setLang('es');
        ok(calls === 3, 'D listener invoked every switch');
        ok(e.r() === 0, 'D never reloads while a listener handles it');
        ok(e.i.lang === 'es' && e.store['sm-lang'] === 'es' && e.html() === 'es',
           'D state still fully updated live');

        // a throwing listener neither breaks setLang nor suppresses the reload
        e = fresh();
        e.i.onChange(() => { throw new Error('boom'); });
        e.i.setLang('es');
        ok(e.i.lang === 'es' && e.html() === 'es', 'throwing listener: state still updated');
        ok(e.r() === 1, 'throwing listener does not count as handled');

        // mixed: false listener + true listener -> handled, no reload
        e = fresh();
        e.i.onChange(() => false);
        e.i.onChange(() => true);
        e.i.setLang('es');
        ok(e.r() === 0, 'one true listener is enough to skip reload');

        console.log('PASS');
    """)
    r = _run_node(harness)
    assert r.returncode == 0, r.stderr or r.stdout
    assert "PASS" in r.stdout


def test_i18n_localstorage_still_only_sm_lang():
    import re
    hits = re.findall(r'(?:localStorage|sessionStorage)\.\w+\(\s*"([^"]+)"', I18N)
    assert hits and set(hits) == {"sm-lang"}


def test_i18n_default_is_ca_unchanged():
    assert 'var lang = "ca"' in I18N


# ------------------------------------------------------------ exam.js: Case C

def test_exam_language_switch_keeps_unsaved_answer():
    """Case C/E: type an answer, switch language, the draft survives with no
    reload, same position, same session, timer re-armed."""
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/exam.js', 'utf8');
        function ok(c, m) { if (!c) { console.error('FAIL: ' + m); process.exit(1); } }

        const byId = {};
        function elem(tag) {
          const kids = [];
          const e = {
            tagName: tag, style: {}, _attr: {}, _id: '', _value: '', _html: '',
            className: '', rows: 0, type: '', name: '', required: false,
            disabled: false, checked: false, _listeners: {},
            get id() { return this._id; },
            set id(v) { this._id = v; if (v) byId[v] = e; },
            get value() { return this._value; },
            set value(v) { this._value = v; },
            get innerHTML() { return this._html; },
            set innerHTML(v) { this._html = v; if (v === '') kids.length = 0; },
            get textContent() { return this._text || ''; },
            set textContent(v) { this._text = String(v); },
            appendChild(c) { kids.push(c); c.parentNode = e; return c; },
            insertBefore(c) { kids.unshift(c); c.parentNode = e; return c; },
            setAttribute(k, v) { this._attr[k] = String(v); },
            getAttribute(k) { return this._attr[k]; },
            removeAttribute(k) { delete this._attr[k]; },
            addEventListener(ev, fn) { (this._listeners[ev] = this._listeners[ev] || []).push(fn); },
            fire(ev, arg) { (this._listeners[ev] || []).forEach(fn => fn(arg || { preventDefault() {} })); },
            querySelector() { return null; },
            querySelectorAll() { return []; },
            get children() { return kids; },
            get firstChild() { return kids[0] || null; },
          };
          return e;
        }
        const examRoot = elem('div'); examRoot.id = 'exam-root';
        const examTitle = elem('h1'); examTitle.id = 'exam-title';
        const examSub = elem('p'); examSub.id = 'exam-sub';
        const examTimer = elem('p'); examTimer.id = 'exam-timer';

        let intervals = 0;
        const calls = [];
        const FUTURE = new Date(Date.now() + 3600000).toISOString();
        function reply(path) {
          calls.push(path);
          if (path.indexOf('/api/exam/state') === 0) {
            return { status: 200, data: { status: 'IN_PROGRESS', title: 'T',
              question_count: 1, expires_at: FUTURE, answers: {} } };
          }
          if (path.indexOf('/api/exam/question') === 0) {
            return { status: 200, data: { question: { type: 'SHORT_ANSWER',
              prompt: 'p', options: [] } } };
          }
          return { status: 200, data: {} };
        }
        const window = {
          location: { search: '?xsid=SESS123', reload() { ok(false, 'exam page reloaded'); } },
          setInterval() { intervals++; return 1; },
          clearInterval() {},
          smFetch(path) {
            return Promise.resolve({ status: reply(path).status,
              json: () => Promise.resolve(reply(path).data) });
          },
          smI18n: {
            _l: [], lang: 'ca',
            t: k => k,
            onChange(fn) { this._l.push(fn); },
            switch() { this.lang = this.lang === 'ca' ? 'es' : 'ca';
                       return this._l.map(fn => fn()); },
          },
        };
        const document = {
          body: elem('body'),
          createElement: elem,
          createTextNode: v => ({ nodeValue: v }),
          getElementById: id => byId[id] || null,
        };
        window.document = document;

        new Function('window', 'document', src)(window, document);

        setTimeout(() => {
          // exam.js has loaded state + question 0; grab the answer field
          const input = byId['x-answer'];
          ok(input, 'question 0 rendered an input');
          ok(input.value === '', 'input starts empty (no saved answer)');
          const intervalsBefore = intervals;

          // user types a draft answer, does NOT press "Desa"
          input.value = 'my draft answer';

          // user switches CA -> ES
          const results = window.smI18n.switch();
          ok(results.indexOf(true) !== -1, 'relang() returned true (suppresses reload)');

          setTimeout(() => {
            const input2 = byId['x-answer'];
            ok(input2, 'question re-rendered an input after language switch');
            ok(input2.value === 'my draft answer',
               'unsaved draft survived the language switch');
            ok(calls.filter(c => c.indexOf('position=0') !== -1).length >= 2,
               'still on the same question position (0)');
            ok(calls.every(c => c.indexOf('/api/exam/') !== 0 ||
               c.indexOf('SESS123') !== -1), 'same exam session throughout');
            ok(intervals > intervalsBefore, 'visual timer re-armed after switch');
            console.log('PASS');
          }, 20);
        }, 20);
    """)
    r = _run_node(harness)
    assert r.returncode == 0, r.stderr or r.stdout
    assert "PASS" in r.stdout


# ---------------------------------------------------- static wiring assertions

def test_shell_registers_live_relabel():
    assert "smI18n.onChange" in SHELL
    assert "function renderNav(" in SHELL and "function renderHeader(" in SHELL
    # active-route detection unchanged for F18-02
    assert "it.href === route" in SHELL
    assert SHELL.count('aria-current="page"') == 1


def test_exam_registers_relang_that_preserves_draft():
    assert "smI18n.onChange" in EXAM
    assert "function relang(" in EXAM
    assert "PENDING_SEED" in EXAM and "CURRENT_GET" in EXAM
    # relang returns true so i18n.js skips the reload
    assert "return true;" in EXAM.split("function relang(")[1].split("}")[0] + "}"
    # the draft is only carried when it is a non-empty string
    assert 'typeof v === "string" && v !== ""' in EXAM
