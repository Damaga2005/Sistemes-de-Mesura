/* Practice player (B2.11–B2.19; F17 Task 7 restyle). Render per tipus; cap càlcul.
   Presentation only: correctesa, errors i evidències venen del backend. */
(function () {
  "use strict";

  var ui = window.smUI || null;
  var i18n = window.smI18n || null;
  var el = (ui && ui.el) ? ui.el : function (tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  function t(key) { return (i18n && i18n.t) ? i18n.t(key) : key; }

  var TYPES = ["TRUE_FALSE", "MULTIPLE_CHOICE", "FORMULA", "NUMERICAL",
    "SHORT_ANSWER", "CONCEPTUAL", "OPEN", "MULTI_STEP", "THEORY"];
  var DIFFS = ["", "EASY", "MEDIUM", "HARD", "EXPERT"];

  function api(path, opts) {
    return window.smFetch(path, opts).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function showError(box, res, retryFn) {
    var opts = { retry: retryFn || undefined };
    if (res && res.data && res.data.message) opts.message = res.data.message;
    if (res && res.data && res.data.code) opts.code = res.data.code;
    if (ui && ui.setState) {
      ui.setState(box, "error", opts);
      return;
    }
    box.innerHTML = "";
    var al = el("div", "alert alert--danger");
    al.setAttribute("role", "alert");
    al.appendChild(el("strong", null, "Error"));
    al.appendChild(el("p", null, opts.message || t("common.retry")));
    box.appendChild(al);
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
    var t2 = q.type || "";
    if (t2 === "TRUE_FALSE") {
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
    if (t2 === "MULTIPLE_CHOICE" && q.options && q.options.length) {
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
    if (t2 === "SHORT_ANSWER" || t2 === "OPEN" || t2 === "MULTI_STEP" ||
        t2 === "CONCEPTUAL" || t2 === "THEORY") {
      inp = document.createElement("textarea");
      inp.className = "textarea";
      inp.rows = t2 === "SHORT_ANSWER" ? 3 : 6;
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
    if (t2 === "NUMERICAL" && q.variables) {
      var vars = Object.keys(q.variables);
      if (vars.length) {
        box.appendChild(el("p", "hint", "Variables: " + vars.join(", ")));
      }
    }
    return function () { return inp.value; };
  }

  function contextStrip(q) {
    var parts = [];
    var topic = (q.topic === undefined || q.topic === null || q.topic === "")
      ? cfgVal("cfg-topic", "") : q.topic;
    if (topic !== "" && topic !== undefined) {
      parts.push(t("practice.topic") + " " + topic);
    }
    if (q.difficulty) parts.push(q.difficulty);
    if (q.type) parts.push(q.type);
    return el("p", "practice-context", parts.join(" · "));
  }

  function bannerVariant(status) {
    if (status === "CORRECT") {
      return { cls: "alert--success", icon: "✓", text: t("practice.correct") };
    }
    if (status === "NO_ANSWER") {
      return { cls: "alert--warning", icon: "○", text: t("practice.noAnswer") };
    }
    return { cls: "alert--danger", icon: "✗", text: t("practice.incorrect") };
  }

  function renderCorrection(box, res) {
    box.innerHTML = "";
    var r = res.result || {};
    var wrap = el("div", "practice-result");

    var v = bannerVariant(r.status);
    var banner = el("div", "alert " + v.cls);
    banner.setAttribute("role", "status");
    var head = el("div", "practice-banner");
    var glyph = el("span", "practice-banner__icon", v.icon);
    glyph.setAttribute("aria-hidden", "true");
    head.appendChild(glyph);
    head.appendChild(el("strong", null, v.text));
    banner.appendChild(head);
    if (r.replayed) {
      banner.appendChild(el("p", null,
        "Ja corregida abans (idempotent, sense duplicar)."));
    }
    wrap.appendChild(banner);

    if (r.explanation) {
      var exp = el("div", "card");
      exp.appendChild(el("h2", "h3", t("practice.explanation")));
      exp.appendChild(el("p", null, r.explanation));
      wrap.appendChild(exp);
    }

    var prov = r.provenance || [];
    var formulas = r.formulas || [];
    if ((prov.length || formulas.length) && ui && ui.openEvidence) {
      var ev = el("button", "button button--secondary", t("practice.evidence"));
      ev.type = "button";
      ev.addEventListener("click", function () {
        ui.openEvidence({ provenance: prov, formulas: formulas });
      });
      wrap.appendChild(ev);
    }

    (r.errors || []).forEach(function (e) {
      var card = el("div", "card");
      card.appendChild(el("h2", "h3", e.label || e.type || "Error"));
      if (e.band) card.appendChild(el("p", "hint", e.band));
      if (e.hint) card.appendChild(el("p", null, e.hint));
      wrap.appendChild(card);
    });

    var actions = el("div", "practice-actions");
    var again = el("button", "button", t("practice.continue"));
    again.type = "button";
    again.addEventListener("click", function () { start(); });
    actions.appendChild(again);
    var done = el("a", "button button--secondary", t("practice.finish"));
    done.href = "index.html";
    actions.appendChild(done);
    wrap.appendChild(actions);

    box.appendChild(wrap);
  }

  function cfgVal(id, dflt) {
    var n = document.getElementById(id);
    return n ? n.value : dflt;
  }

  function currentConfig() {
    return { topic: parseInt(cfgVal("cfg-topic", "2"), 10) || 2,
             question_type: cfgVal("cfg-type", "TRUE_FALSE"),
             difficulty: cfgVal("cfg-diff", ""),
             seed: parseInt(cfgVal("cfg-seed", "0"), 10) || 0 };
  }

  function start() {
    var qbox = document.getElementById("q-box");
    var abox = document.getElementById("a-box");
    var cbox = document.getElementById("c-box");
    cbox.innerHTML = "";
    abox.innerHTML = "";
    if (ui && ui.setState) ui.setState(qbox, "loading", { kind: "card" });
    else qbox.innerHTML = "";
    var cfg = currentConfig();
    api("/api/practice/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg)
    }).then(function (res) {
      if (res.status !== 200) {
        showError(qbox, res, start);
        return;
      }
      if (ui && ui.setState) ui.setState(qbox, "ready");
      playQuestion(res.data.question || {});
    }).catch(function () {
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

    var col = el("div", "practice-q");
    col.appendChild(contextStrip(q));

    var stem = el("div", "card");
    stem.appendChild(el("h2", "h3", t("practice.question")));
    stem.appendChild(el("p", null, q.prompt || q.stem || ""));
    (q.options || []).forEach(function (o, i) {
      stem.appendChild(el("p", null,
        String.fromCharCode(65 + i) + ") " + (o.text || "")));
    });
    if (q.variables && Object.keys(q.variables).length) {
      renderFormulaBox(stem, JSON.stringify(q.variables), null);
    }
    col.appendChild(stem);

    var form = document.createElement("form");
    form.id = "answer-form";
    var get = answerField(q, form);
    var btn = el("button", "button", t("practice.send"));
    btn.type = "submit";
    btn.id = "send-btn";
    form.appendChild(btn);
    col.appendChild(form);
    qbox.appendChild(col);

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var answer = get();
      if (!answer) return;
      btn.disabled = true;
      btn.textContent = t("practice.sending");
      api("/api/practice/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: answer,
                               attempt_id: "web-" + Date.now() })
      }).then(function (r2) {
        btn.disabled = false;
        btn.textContent = t("practice.send");
        if (r2.status !== 200) {
          showError(cbox, r2, null);
          return;
        }
        renderCorrection(cbox, r2.data);
      }).catch(function () {
        btn.disabled = false;
        btn.textContent = t("practice.send");
        showError(cbox, { data: {} }, null);
      });
    });
  }

  function bindConfig() {
    var tsel = document.getElementById("cfg-type");
    if (tsel && !tsel.options.length) {
      TYPES.forEach(function (ty) {
        var o = document.createElement("option");
        o.value = ty;
        o.textContent = ty;
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
