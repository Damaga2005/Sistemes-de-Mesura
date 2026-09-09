/* Exams overview + creació (B4). Estats del backend, res més. */
(function () {
  "use strict";

  var TYPES = ["", "TRUE_FALSE", "MULTIPLE_CHOICE", "FORMULA",
    "NUMERICAL", "SHORT_ANSWER", "CONCEPTUAL", "OPEN", "MULTI_STEP",
    "THEORY"];
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

  var CTA = { CREATED: "Preparar examen", READY: "Començar examen",
    IN_PROGRESS: "Continuar examen", SUBMITTED: "Veure estat",
    GRADED: "Veure resultats", EXPIRED: "Tancat (caducat)",
    CANCELLED: "Tancat (cancel·lat)" };
  var BADGE = { CREATED: "neutral", READY: "info",
    IN_PROGRESS: "warning", SUBMITTED: "info", GRADED: "success",
    EXPIRED: "neutral", CANCELLED: "neutral" };

  function loadMine() {
    var box = document.getElementById("exam-list");
    if (!box) return;
    api("/api/exam/mine").then(function (res) {
      box.innerHTML = "";
      if (res.status !== 200) {
        box.appendChild(el("p", null, "No s'ha pogut carregar."));
        return;
      }
      var list = res.data.sessions || [];
      if (!list.length) {
        var b = el("div", "state-block");
        var ic = el("div", "state-icon", "○");
        ic.setAttribute("aria-hidden", "true");
        b.appendChild(ic);
        b.appendChild(el("h2", null, "Cap examen"));
        b.appendChild(el("p", null, "Crea'n un amb el formulari."));
        b.appendChild(el("span", "badge badge--info", "EMPTY"));
        box.appendChild(b);
        return;
      }
      list.forEach(function (s) {
        var card = el("div", "card");
        card.appendChild(el("h2", "h3",
          s.title || ("Examen " + String(s.session_id).slice(0, 12))));
        var meta = el("p", null, (s.exam_kind || "?"));
        card.appendChild(meta);
        var details = el("p", "hint",
          String(s.question_count === undefined ? "?" : s.question_count) +
          " preguntes" + (s.duration_seconds === null ||
          s.duration_seconds === undefined ? "" :
          " · " + Math.round(s.duration_seconds / 60) + " min"));
        card.appendChild(details);
        var row = el("p");
        var badge = el("span",
          "badge badge--" + (BADGE[s.status] || "neutral"),
          s.status);
        row.appendChild(badge);
        row.appendChild(document.createTextNode(" "));
        var a = el("a", "button button--secondary",
          CTA[s.status] || "Obrir");
        a.href = "exam.html?xsid=" + encodeURIComponent(s.session_id);
        if (s.status === "EXPIRED" || s.status === "CANCELLED") {
          a.setAttribute("aria-disabled", "true");
        }
        row.appendChild(a);
        card.appendChild(row);
        box.appendChild(card);
      });
    }).catch(function () {
      box.innerHTML = "";
      box.appendChild(el("p", null, "Error de xarxa."));
    });
  }

  function bindCreate() {
    var tbox = document.getElementById("cfg-topics");
    if (tbox) {
      for (var t = 1; t <= 10; t++) {
        (function (n) {
          var lab = el("label", "check");
          var inp = document.createElement("input");
          inp.type = "checkbox";
          inp.value = String(n);
          inp.checked = (n === 2);
          lab.appendChild(inp);
          lab.appendChild(document.createTextNode(" Tema " + n));
          tbox.appendChild(lab);
        })(t);
      }
    }
    function fill(id, vals, labels) {
      var s = document.getElementById(id);
      if (!s || s.options.length) return;
      vals.forEach(function (v, i) {
        var o = document.createElement("option");
        o.value = v;
        o.textContent = (labels || vals)[i];
        s.appendChild(o);
      });
    }
    fill("cfg-type", TYPES,
      ["Automàtic"].concat(TYPES.slice(1)));
    fill("cfg-diff", DIFFS, ["Automàtica"].concat(DIFFS.slice(1)));
    var go = document.getElementById("cfg-go");
    var out = document.getElementById("cfg-out");
    if (!go) return;
    go.addEventListener("click", function () {
      var topics = [];
      document.querySelectorAll("#cfg-topics input:checked")
        .forEach(function (c) { topics.push(parseInt(c.value, 10)); });
      var durRaw = document.getElementById("cfg-dur").value;
      var body = {
        exam_kind: document.getElementById("cfg-kind").value,
        topics: topics,
        question_count: parseInt(
          document.getElementById("cfg-count").value, 10) || 2,
        question_type: document.getElementById("cfg-type").value,
        difficulty: document.getElementById("cfg-diff").value,
        seed: parseInt(
          document.getElementById("cfg-seed").value, 10) || 0
      };
      if (durRaw) body.duration_seconds = parseInt(durRaw, 10);
      go.disabled = true;
      go.textContent = "Creant…";
      out.innerHTML = "";
      api("/api/exam/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function (res) {
        go.disabled = false;
        go.textContent = "Crea i prepara";
        if (res.status !== 200) {
          var al = el("div", "alert alert--danger");
          al.setAttribute("role", "alert");
          al.appendChild(el("strong", null, "No s'ha pogut crear"));
          al.appendChild(el("p", null,
            (res.data && res.data.message) || ""));
          out.appendChild(al);
          return;
        }
        window.location.href = "exam.html?xsid=" + encodeURIComponent(
          res.data.exam_session.session_id);
      }).catch(function () {
        go.disabled = false;
        go.textContent = "Crea i prepara";
        out.appendChild(el("p", null, "Error de xarxa."));
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadMine(); bindCreate();
    });
  } else {
    loadMine(); bindCreate();
  }
})();
