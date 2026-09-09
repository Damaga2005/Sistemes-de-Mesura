/* Practice player (B2.11–B2.19). Render per tipus; cap càlcul. */
(function () {
  "use strict";

  var TYPES = ["TRUE_FALSE", "MULTIPLE_CHOICE", "FORMULA", "NUMERICAL",
    "SHORT_ANSWER", "CONCEPTUAL", "OPEN", "MULTI_STEP", "THEORY"];
  var DIFFS = ["", "EASY", "MEDIUM", "HARD", "EXPERT"];

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function api(path, opts) {
    return window.smFetch(path, opts).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function showError(box, res, retryFn) {
    box.innerHTML = "";
    var al = el("div", "alert alert--danger");
    al.setAttribute("role", "alert");
    al.appendChild(el("strong", null, "Error"));
    al.appendChild(el("p", null,
      (res.data && res.data.message) || "Torna-ho a provar."));
    if (res.data && res.data.code) {
      al.appendChild(el("span", "state-code", res.data.code));
    }
    box.appendChild(al);
    if (retryFn) {
      var b = el("button", "button button--secondary", "Reintenta");
      b.type = "button";
      b.addEventListener("click", retryFn);
      box.appendChild(b);
    }
  }

  function renderFormulaBox(parent, expr, fhtml) {
    var box = el("p", "formula", "");
    if (fhtml) {
      box.innerHTML = fhtml; /* B2.28: només HTML del renderer llista-blanca */
    } else {
      box.textContent = expr || "";
    }
    parent.appendChild(box);
  }

  function answerField(q, box) {
    var t = q.type || "";
    if (t === "TRUE_FALSE") {
      var fs = el("fieldset");
      fs.appendChild(el("legend", "label", "Vertader o fals"));
      [["V", "Vertader"], ["F", "Fals"]].forEach(function (opt) {
        var lab = el("label", "radio");
        var inp = document.createElement("input");
        inp.type = "radio"; inp.name = "answer"; inp.value = opt[0];
        inp.required = true;
        lab.appendChild(inp);
        lab.appendChild(document.createTextNode(" " + opt[1]));
        fs.appendChild(lab);
      });
      box.appendChild(fs);
      return function () {
        var c = box.querySelector('input[name="answer"]:checked');
        return c ? c.value : "";
      };
    }
    if (t === "MULTIPLE_CHOICE" && q.options && q.options.length) {
      var fs2 = el("fieldset");
      fs2.appendChild(el("legend", "label", "Tria una opció"));
      q.options.forEach(function (o, i) {
        var lab = el("label", "radio");
        var inp = document.createElement("input");
        inp.type = "radio"; inp.name = "answer";
        inp.value = String.fromCharCode(65 + i);
        inp.required = true;
        lab.appendChild(inp);
        lab.appendChild(document.createTextNode(
          " " + String.fromCharCode(65 + i) + ") " + (o.text || "")));
        fs2.appendChild(lab);
      });
      box.appendChild(fs2);
      return function () {
        var c = box.querySelector('input[name="answer"]:checked');
        return c ? c.value : "";
      };
    }
    var label = el("label", "label", "La teva resposta");
    var inp;
    if (t === "SHORT_ANSWER" || t === "OPEN" || t === "MULTI_STEP" ||
        t === "CONCEPTUAL" || t === "THEORY") {
      inp = document.createElement("textarea");
      inp.className = "textarea";
      inp.rows = t === "SHORT_ANSWER" ? 3 : 6;
    } else {
      inp = document.createElement("input");
      inp.className = "input";
      inp.type = "text";
      inp.setAttribute("inputmode", "decimal");
    }
    inp.id = "answer-input";
    inp.required = true;
    label.setAttribute("for", "answer-input");
    box.appendChild(label);
    box.appendChild(inp);
    if (t === "NUMERICAL" && q.variables) {
      var vars = Object.keys(q.variables);
      if (vars.length) {
        box.appendChild(el("p", "hint",
          "Variables: " + vars.join(", ")));
      }
    }
    return function () { return inp.value; };
  }

  function renderCorrection(box, res) {
    box.innerHTML = "";
    var r = res.result || {};
    var head = el("div", "alert " + (r.status === "CORRECT"
      ? "alert--success" : r.status === "NO_ANSWER"
      ? "alert--warning" : "alert--danger"));
    head.setAttribute("role", "status");
    head.appendChild(el("strong", null,
      r.status === "CORRECT" ? "Correcte" : r.status === "NO_ANSWER"
      ? "Sense resposta" : "A corregir"));
    var sc = (r.score === null || r.score === undefined) ? "" :
      (" — nota: " + r.score);
    head.appendChild(el("p", null, "Estat: " + (r.status || "?") + sc));
    if (r.replayed) {
      head.appendChild(el("p", null,
        "Ja corregida abans (idempotent, sense duplicar)."));
    }
    box.appendChild(head);
    (r.errors || []).forEach(function (e) {
      var card = el("div", "card");
      card.appendChild(el("h2", "h3", e.label || e.type || "Error"));
      if (e.band) card.appendChild(el("p", null, "Severitat: " + e.band));
      if (e.hint) card.appendChild(el("p", null, e.hint));
      box.appendChild(card);
    });
    if ((r.mastery || []).length) {
      var mc = el("div", "card");
      mc.appendChild(el("h2", "h3", "Mastery (backend)"));
      var ul = el("ul");
      r.mastery.forEach(function (m) {
        ul.appendChild(el("li", null,
          (m.unit || "") + ": " + (m.score === null ||
            m.score === undefined ? "?" : m.score) +
          (m.status ? " (" + m.status + ")" : "")));
      });
      mc.appendChild(ul);
      box.appendChild(mc);
    }
    var again = el("button", "button", "Nova pregunta");
    again.type = "button";
    again.addEventListener("click", function () { start(); });
    box.appendChild(again);
    var back = el("a", "button button--secondary",
      "Veure l'actualització a Aprenentatge");
    back.href = "learning.html";
    box.appendChild(document.createTextNode(" "));
    box.appendChild(back);
    box.appendChild(el("span", "state-code",
      "attempt: " + (res.attempt_id || "?")));
  }

  function currentConfig() {
    function val(id, dflt) {
      var n = document.getElementById(id);
      return n ? n.value : dflt;
    }
    return { topic: parseInt(val("cfg-topic", "2"), 10) || 2,
             question_type: val("cfg-type", "TRUE_FALSE"),
             difficulty: val("cfg-diff", ""),
             seed: parseInt(val("cfg-seed", "0"), 10) || 0 };
  }

  function start() {
    var qbox = document.getElementById("q-box");
    var abox = document.getElementById("a-box");
    var cbox = document.getElementById("c-box");
    cbox.innerHTML = "";
    qbox.innerHTML = "";
    abox.innerHTML = "";
    var live = el("div", null, "");
    live.setAttribute("role", "status");
    live.textContent = "Generant pregunta…";
    qbox.appendChild(live);
    var cfg = currentConfig();
    api("/api/practice/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg)
    }).then(function (res) {
      qbox.innerHTML = "";
      if (res.status !== 200) {
        showError(qbox, res, start);
        return;
      }
      var q = res.data.question || {};
      playQuestion(q);
    }).catch(function () {
      qbox.innerHTML = "";
      showError(qbox, { data: {} }, start);
    });
  }

  function playQuestion(q) {
    var qbox = document.getElementById("q-box");
    var abox = document.getElementById("a-box");
    var cbox = document.getElementById("c-box");
    qbox.innerHTML = "";
    abox.innerHTML = "";
    cbox.innerHTML = "";
    var stem = el("div", "card");
    stem.appendChild(el("h2", "h3",
        "Pregunta · " + (q.type || "") + " · Tema " +
        (q.topic === undefined ? "?" : q.topic)));
      stem.appendChild(el("p", null, q.prompt || q.stem || ""));
      (q.options || []).forEach(function (o, i) {
        stem.appendChild(el("p", null,
          String.fromCharCode(65 + i) + ") " + (o.text || "")));
      });
      if (q.variables && Object.keys(q.variables).length) {
        renderFormulaBox(stem, JSON.stringify(q.variables), null);
      }
      qbox.appendChild(stem);
      var form = document.createElement("form");
      form.id = "answer-form";
      var get = answerField(q, form);
      var btn = el("button", "button", "Envia la resposta");
      btn.type = "submit";
      btn.id = "send-btn";
      form.appendChild(btn);
      abox.appendChild(form);
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var answer = get();
        if (!answer) return;
        btn.disabled = true;
        btn.textContent = "Corregint…";
        api("/api/practice/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: answer,
                                 attempt_id: "web-" + Date.now() })
        }).then(function (r2) {
          btn.disabled = false;
          btn.textContent = "Envia la resposta";
          if (r2.status !== 200) {
            showError(cbox, r2, null);
            return;
          }
          renderCorrection(cbox, r2.data);
        }).catch(function () {
          btn.disabled = false;
          btn.textContent = "Envia la resposta";
          showError(cbox, { data: {} }, null);
        });
      });
  }

  function bindConfig() {
    var tsel = document.getElementById("cfg-type");
    if (tsel && !tsel.options.length) {
      TYPES.forEach(function (t) {
        var o = document.createElement("option");
        o.value = t;
        o.textContent = t;
        tsel.appendChild(o);
      });
      tsel.value = "TRUE_FALSE";
    }
    var dsel = document.getElementById("cfg-diff");
    if (dsel && !dsel.options.length) {
      DIFFS.forEach(function (d) {
        var o = document.createElement("option");
        o.value = d;
        o.textContent = d === "" ? "Automàtica" : d;
        dsel.appendChild(o);
      });
    }
    var go = document.getElementById("cfg-go");
    if (go) go.addEventListener("click", start);
    if (window.location.search.indexOf("from=adaptive") !== -1) {
      try {
        var stored = window.sessionStorage.getItem("sm-adaptive-q");
        if (stored) {
          playQuestion(JSON.parse(stored));
          window.sessionStorage.removeItem("sm-adaptive-q");
          return;
        }
      } catch (e) { /* cau al flux normal */ }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindConfig);
  } else {
    bindConfig();
  }
})();
