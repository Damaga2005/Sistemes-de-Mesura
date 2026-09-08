/* Exam player (B4). Estats del backend; temporitzador només visual. */
(function () {
  "use strict";

  var XS = null;
  var STATE = null;
  var COUNT = 0;
  var POS = 0;
  var TIMER = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function api(path, opts) {
    return window.fetch(path, opts).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function xsid() {
    var m = window.location.search.match(/[?&]xsid=([^&]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function fmtClock(ms) {
    if (ms < 0) ms = 0;
    var s = Math.floor(ms / 1000);
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var r = s % 60;
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return (h > 0 ? h + ":" : "") + p(m) + ":" + p(r);
  }

  function stopTimer() {
    if (TIMER) { window.clearInterval(TIMER); TIMER = null; }
    var t = document.getElementById("exam-timer");
    if (t) t.textContent = "";
  }

  function startTimer(expiresAt) {
    stopTimer();
    var t = document.getElementById("exam-timer");
    if (!t || !expiresAt) return;
    var end = Date.parse(expiresAt);
    if (isNaN(end)) return;
    function tick() {
      var left = end - Date.now();
      t.textContent = left <= 0
        ? "Temps esgotat (el servidor decideix)"
        : "Temps: " + fmtClock(left);
      if (left <= 0) {
        stopTimer();
        load(true);
      }
    }
    tick();
    TIMER = window.setInterval(tick, 1000);
  }

  function root() {
    return document.getElementById("exam-root");
  }

  function load(silent) {
    var box = root();
    if (!silent) box.innerHTML = "";
    api("/api/exam/state?exam_session_id=" + encodeURIComponent(XS))
      .then(function (res) {
        if (res.status !== 200) {
          box.innerHTML = "";
          var al = el("div", "alert alert--danger");
          al.setAttribute("role", "alert");
          al.appendChild(el("strong", null, "Examen no disponible"));
          al.appendChild(el("p", null,
            (res.data && res.data.message) || ""));
          box.appendChild(al);
          stopTimer();
          return;
        }
        STATE = res.data;
        render();
      }).catch(function () {
        if (!silent) {
          box.innerHTML = "";
          box.appendChild(el("p", null, "Error de xarxa."));
        }
      });
  }

  function render() {
    var box = root();
    box.innerHTML = "";
    var title = document.getElementById("exam-title");
    if (title) title.textContent = STATE.title || "Examen";
    var sub = document.getElementById("exam-sub");
    if (sub) {
      var count = STATE.question_count === undefined ? "?" :
        STATE.question_count;
      sub.textContent = (STATE.exam_kind || "?") + " · " + STATE.status +
        " · " + count + " preguntes";
    }
    var st = STATE.status;
    if (st === "IN_PROGRESS") return renderPlayer(box);
    stopTimer();
    if (st === "READY") {
      box.appendChild(el("p", null,
        "Examen preparat i immutable. Prem per començar."));
      var b = el("button", "button", "Començar examen");
      b.type = "button";
      b.addEventListener("click", function () {
        b.disabled = true;
        api("/api/exam/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ exam_session_id: XS })
        }).then(function () { load(); });
      });
      box.appendChild(b);
      return;
    }
    if (st === "SUBMITTED") return renderSubmitted(box);
    if (st === "GRADED") return renderGraded(box);
    if (st === "GRADING_INCOMPLETE") return renderGradingIncomplete(box);
    var closed = el("div", "state-block");
    var ic = el("div", "state-icon", "■");
    ic.setAttribute("aria-hidden", "true");
    closed.appendChild(ic);
    closed.appendChild(el("h2", null,
      st === "EXPIRED" ? "Temps esgotat" : "Examen tancat"));
    closed.appendChild(el("p", null, "Estat: " + st));
    box.appendChild(closed);
  }

  function renderPlayer(box) {
    startTimer(STATE.expires_at);
    COUNT = Number(STATE.question_count ||
      (STATE.snapshot && STATE.snapshot.instances || []).length);
    box.innerHTML = "";
    var prog = el("p", null, "");
    prog.id = "exam-progress";
    box.appendChild(prog);
    var nav = el("div", null, "");
    nav.setAttribute("role", "navigation");
    nav.setAttribute("aria-label", "Preguntes");
    box.appendChild(nav);
    var qbox = el("div", null, "");
    box.appendChild(qbox);
    var ans = STATE.answers || {};
    var answered = Object.keys(ans).filter(function (key) {
      return ans[key] && String(ans[key].answer || "").trim() !== "";
    }).length;
    prog.textContent = "Respostes: " + answered + " de " + COUNT;
    for (var i = 0; i < COUNT; i++) {
        (function (p) {
          var b = el("button",
            "button button--secondary" +
            (ans[String(p)] ? "" : ""),
            "P" + (p + 1) + (ans[String(p)] ? " ✓" : ""));
          b.type = "button";
          b.style.minWidth = "3rem";
          if (p === POS) b.setAttribute("aria-current", "true");
          b.setAttribute("aria-label",
            "Pregunta " + (p + 1) + (ans[String(p)] ? ", resposta" : ""));
          b.addEventListener("click", function () {
            POS = p;
            render();
          });
          nav.appendChild(b);
          nav.appendChild(document.createTextNode(" "));
        })(i);
      }
    loadQuestion(qbox);
    var sub = el("button", "button", "Entregar examen");
    sub.type = "button";
    sub.style.marginTop = "1rem";
    sub.addEventListener("click", function () { confirmSubmit(box); });
    box.appendChild(sub);
  }

  function loadQuestion(qbox) {
    qbox.innerHTML = "";
    var live = el("p", null, "Carregant pregunta…");
    live.setAttribute("role", "status");
    qbox.appendChild(live);
    api("/api/exam/question?exam_session_id=" + encodeURIComponent(XS) +
      "&position=" + POS).then(function (res) {
      qbox.innerHTML = "";
      if (res.status !== 200) {
        qbox.appendChild(el("p", null, "No disponible."));
        return;
      }
      var q = res.data.question || {};
      var card = el("div", "card");
      card.appendChild(el("h2", "h3",
        "Pregunta " + (POS + 1) + " · " + (q.type || "")));
      card.appendChild(el("p", null, q.prompt || ""));
      if (q.variables && Object.keys(q.variables).length) {
        card.appendChild(el("p", "hint", "Dades: " +
          JSON.stringify(q.variables)));
      }
      (q.options || []).forEach(function (o, i) {
        card.appendChild(el("p", null,
          String.fromCharCode(65 + i) + ") " + (o.text || "")));
      });
      qbox.appendChild(card);
      var form = document.createElement("form");
      var saved = (STATE.answers || {})[String(POS)];
      var get = buildInput(q, form, saved ? saved.answer : "");
      var row = el("p");
      var save = el("button", "button button--secondary", "Desa");
      save.type = "submit";
      row.appendChild(save);
      form.appendChild(row);
      qbox.appendChild(form);
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var answer = get();
        save.disabled = true;
        api("/api/exam/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ exam_session_id: XS, position: POS,
                                 answer: answer })
        }).then(function (r2) {
          save.disabled = false;
          if (r2.status !== 200) {
            if (r2.data && r2.data.code) load(true);
            return;
          }
          load(true);
        }).catch(function () { save.disabled = false; });
      });
    });
  }

  function buildInput(q, form, saved) {
    var t = q.type || "";
    if (t === "TRUE_FALSE") {
      var fs = el("fieldset");
      fs.appendChild(el("legend", "label", "Vertader o fals"));
      [["V", "Vertader"], ["F", "Fals"]].forEach(function (opt) {
        var lab = el("label", "radio");
        var inp = document.createElement("input");
        inp.type = "radio"; inp.name = "xanswer"; inp.value = opt[0];
        inp.required = true;
        if (saved === opt[0]) inp.checked = true;
        lab.appendChild(inp);
        lab.appendChild(document.createTextNode(" " + opt[1]));
        fs.appendChild(lab);
      });
      form.appendChild(fs);
      return function () {
        var c = form.querySelector('input[name="xanswer"]:checked');
        return c ? c.value : "";
      };
    }
    if (t === "MULTIPLE_CHOICE" && q.options && q.options.length) {
      var fs2 = el("fieldset");
      fs2.appendChild(el("legend", "label", "Tria una opció"));
      q.options.forEach(function (o, i) {
        var lab = el("label", "radio");
        var inp = document.createElement("input");
        inp.type = "radio"; inp.name = "xanswer";
        inp.value = String.fromCharCode(65 + i);
        inp.required = true;
        if (saved === inp.value) inp.checked = true;
        lab.appendChild(inp);
        lab.appendChild(document.createTextNode(
          " " + inp.value + ") " + (o.text || "")));
        fs2.appendChild(lab);
      });
      form.appendChild(fs2);
      return function () {
        var c = form.querySelector('input[name="xanswer"]:checked');
        return c ? c.value : "";
      };
    }
    var label = el("label", "label", "La teva resposta");
    var inp;
    if (t === "SHORT_ANSWER" || t === "OPEN" || t === "MULTI_STEP" ||
        t === "CONCEPTUAL" || t === "THEORY") {
      inp = document.createElement("textarea");
      inp.className = "textarea";
      inp.rows = 5;
    } else {
      inp = document.createElement("input");
      inp.className = "input";
      inp.type = "text";
      inp.setAttribute("inputmode", "decimal");
    }
    inp.id = "x-answer";
    inp.value = saved || "";
    label.setAttribute("for", "x-answer");
    form.appendChild(label);
    form.appendChild(inp);
    return function () { return inp.value; };
  }

  function confirmSubmit(box) {
    var ans = STATE.answers || {};
    var missing = [];
    for (var i = 0; i < COUNT; i++) {
      if (!ans[String(i)]) missing.push(i + 1);
    }
    box.innerHTML = "";
    var card = el("div", "card");
    card.appendChild(el("h2", "h3", "Entregar examen?"));
    card.appendChild(el("p", null,
      "Respostes: " + Object.keys(ans).length + " de " + COUNT + "." +
      (missing.length ? " Falten: " + missing.join(", ") + "." : "") +
      " L'entrega és irreversible."));
    var row = el("p");
    var back = el("button", "button button--secondary", "Tornar");
    back.type = "button";
    back.addEventListener("click", function () { render(); });
    var go = el("button", "button", "Confirmar entrega");
    go.type = "button";
    go.addEventListener("click", function () {
      go.disabled = true;
      api("/api/exam/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exam_session_id: XS })
      }).then(function () { load(); });
    });
    row.appendChild(back);
    row.appendChild(document.createTextNode(" "));
    row.appendChild(go);
    card.appendChild(row);
    box.appendChild(card);
  }

  function renderSubmitted(box) {
    box.appendChild(el("p", null,
      "Examen entregat. El backend el qualifica."));
    var b = el("button", "button", "Qualifica");
    b.type = "button";
    b.addEventListener("click", function () {
      b.disabled = true;
      b.textContent = "Qualificant…";
      api("/api/exam/grade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ exam_session_id: XS })
      }).then(function () { load(); });
    });
    box.appendChild(b);
  }

  function renderGradingIncomplete(box) {
    box.appendChild(el("div", "state-block",
      "La correcció encara no està disponible. Torna a consultar més tard."));
  }

  function renderGraded(box) {
    api("/api/exam/result?exam_session_id=" +
      encodeURIComponent(XS)).then(function (res) {
      if (res.status !== 200) {
        box.appendChild(el("p", null, "Resultat no disponible."));
        return;
      }
      var r = res.data;
      var card = el("div", "card");
      card.appendChild(el("h2", "h3", "Resultat"));
      card.appendChild(el("p", null,
        "Nota: " + (r.percentage || "?") + "% · " +
        "Correctes: " + (r.correct_count === undefined ? "?" :
          r.correct_count) + " de " + (r.question_count || "?")));
      box.appendChild(card);
      api("/api/exam/review?exam_session_id=" +
        encodeURIComponent(XS)).then(function (rv) {
        if (rv.status !== 200) {
          box.appendChild(el("p", null, "Revisió no disponible."));
          return;
        }
        box.appendChild(el("h2", null, "Revisió"));
        (rv.data.questions || []).forEach(function (q, i) {
          var fb = q.feedback || {};
          var qc = el("div", "card");
          qc.appendChild(el("h2", "h3", "Pregunta " + (i + 1)));
          qc.appendChild(el("p", null,
            "Estat: " + (fb.status || "?") +
            (fb.score === null || fb.score === undefined ? "" :
              " · " + fb.score)));
          if (fb.student_answer !== null &&
              fb.student_answer !== undefined) {
            qc.appendChild(el("p", null,
              "La teva resposta: " + fb.student_answer));
          }
          (fb.errors || []).forEach(function (e) {
            qc.appendChild(el("p", null,
              "Error: " + (e.human || e.type || "")));
          });
          (fb.guidance || []).forEach(function (g) {
            qc.appendChild(el("p", null, g.hint || ""));
          });
          box.appendChild(qc);
        });
        var more = el("p");
        var a = el("a", "button button--secondary",
          "Veure mastery");
        a.href = "#";
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadMastery(box);
        });
        more.appendChild(a);
        more.appendChild(document.createTextNode(" "));
        var pr = el("a", "button", "Practicar");
        pr.href = "practice.html";
        more.appendChild(pr);
        box.appendChild(more);
      });
    });
  }

  function loadMastery(box) {
    api("/api/exam/mastery?exam_session_id=" +
      encodeURIComponent(XS)).then(function (res) {
      if (res.status !== 200) return;
      var card = el("div", "card");
      card.id = "mastery";
      card.appendChild(el("h2", "h3", "Mastery (backend)"));
      var ul = el("ul");
      (res.data.units || []).forEach(function (u) {
        ul.appendChild(el("li", null,
          (u.knowledge_unit_id || "") + ": " +
          (u.mastery_status || "?")));
      });
      if (!(res.data.units || []).length) {
        ul.appendChild(el("li", null, "Sense unitats."));
      }
      card.appendChild(ul);
      box.appendChild(card);
    });
  }

  XS = xsid();
  if (!XS) {
    root().innerHTML = "";
    root().appendChild(el("p", null, "Falta l'identificador d'examen."));
  } else {
    load();
  }
})();
