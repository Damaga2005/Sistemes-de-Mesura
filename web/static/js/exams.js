/* Exàmens (F17 Task 10): els meus exàmens + historial + creació.
   Presentation only — estats, correcció i temporitzador són del backend. */
(function () {
  "use strict";

  var smUI = window.smUI;
  var el = smUI.el;
  var api = smUI.api;
  var I18N = window.smI18n || null;
  function t(key) { return I18N && I18N.t ? I18N.t(key) : key; }

  var TYPES = ["", "TRUE_FALSE", "MULTIPLE_CHOICE", "FORMULA",
    "NUMERICAL", "SHORT_ANSWER", "CONCEPTUAL", "OPEN", "MULTI_STEP",
    "THEORY"];
  var DIFFS = ["", "EASY", "MEDIUM", "HARD", "EXPERT"];

  // state -> badge variant (icon + label, never colour-only via badge__dot).
  var BADGE = { CREATED: "neutral", READY: "info", IN_PROGRESS: "warning",
    SUBMITTED: "neutral", GRADED: "success", EXPIRED: "neutral",
    CANCELLED: "neutral" };
  // state -> { page, ctaKey }. CREATED/READY/IN_PROGRESS resume the runner;
  // SUBMITTED/GRADED go to results.html. EXPIRED/CANCELLED are terminal.
  var ACTION = {
    CREATED: { page: "exam.html", key: "exam.prepare" },
    READY: { page: "exam.html", key: "exam.start" },
    IN_PROGRESS: { page: "exam.html", key: "exam.continue" },
    SUBMITTED: { page: "results.html", key: "exam.view" },
    GRADED: { page: "results.html", key: "exam.viewResult" }
  };

  function link(cls, text, href) {
    var a = el("a", cls, text);
    a.href = href;
    return a;
  }

  function examCard(s) {
    var id = String(s.session_id);
    var card = el("article", "card exam-card");
    card.appendChild(el("h3", "exam-card__title",
      s.title || ("Examen " + id.slice(0, 12))));

    var meta = el("p", "exam-card__meta");
    meta.appendChild(smUI.badge(s.exam_kind || "?", "neutral"));
    if (s.status) meta.appendChild(smUI.badge(s.status, BADGE[s.status] || "neutral"));
    card.appendChild(meta);

    var qc = (s.question_count === undefined || s.question_count === null)
      ? null : String(s.question_count) + " " + t("exam.questions");
    var dur = (s.duration_seconds === undefined || s.duration_seconds === null)
      ? null : Math.round(s.duration_seconds / 60) + " " + t("time.min");
    var bits = [];
    if (qc) bits.push(qc);
    if (dur) bits.push(dur);
    if (bits.length) card.appendChild(el("p", "exam-card__detail", bits.join(" · ")));

    var act = ACTION[s.status];
    if (act) {
      card.appendChild(link("button button--secondary exam-card__cta",
        t(act.key),
        act.page + "?xsid=" + encodeURIComponent(id)));
    } else {
      var closed = el("span", "badge badge--neutral", t("exam.closed"));
      card.appendChild(closed);
    }
    return card;
  }

  function loadMine() {
    var box = document.getElementById("exam-list");
    if (!box) return;
    smUI.setState(box, "loading", { kind: "card" });
    api("/api/exam/mine").then(function (res) {
      if (res.status !== 200) {
        smUI.setState(box, "error", { code: res.status, retry: loadMine });
        return;
      }
      var list = (res.data && res.data.sessions) || [];
      if (!list.length) {
        smUI.setState(box, "empty", { message: t("exam.emptyMine") });
        return;
      }
      box.innerHTML = "";
      box.removeAttribute("aria-busy");
      list.forEach(function (s) { box.appendChild(examCard(s)); });
    }).catch(function () {
      smUI.setState(box, "error", { retry: loadMine });
    });
  }

  function historyRow(item) {
    var id = String(item.session_id);
    var tr = el("tr", "exam-hist__row");
    tr.appendChild(el("td", "exam-hist__title",
      item.title || ("Examen " + id.slice(0, 12))));

    var resCell = el("td", "exam-hist__result");
    var r = item.result || {};
    if (r.available) {
      resCell.appendChild(link("button button--ghost exam-hist__revisar",
        t("exam.review"),
        "review.html?xsid=" + encodeURIComponent(id)));
    } else {
      resCell.appendChild(el("span", "exam-hist__muted",
        r.reason || t("exam.noResult")));
    }
    tr.appendChild(resCell);

    var when = item.submitted_at || item.created_at || "";
    var td = el("td", "exam-hist__date", smUI.relativeTime(when) || when || "—");
    tr.appendChild(td);
    return tr;
  }

  function loadHistory() {
    var box = document.getElementById("exam-historial");
    if (!box) return;
    smUI.setState(box, "loading", { kind: "list" });
    api("/api/exam/history").then(function (res) {
      if (res.status !== 200) {
        smUI.setState(box, "error", { code: res.status, retry: loadHistory });
        return;
      }
      var list = (res.data && res.data.history) || [];
      if (!list.length) {
        smUI.setState(box, "empty", { message: t("exam.emptyHistory") });
        return;
      }
      box.innerHTML = "";
      box.removeAttribute("aria-busy");
      var table = el("table", "exam-hist");
      var head = el("tr");
      head.appendChild(el("th", null, t("exam.examCol")));
      head.appendChild(el("th", null, t("exam.result")));
      head.appendChild(el("th", null, t("exam.date")));
      var thead = el("thead");
      thead.appendChild(head);
      table.appendChild(thead);
      var tbody = el("tbody");
      list.forEach(function (item) { tbody.appendChild(historyRow(item)); });
      table.appendChild(tbody);
      box.appendChild(table);
    }).catch(function () {
      smUI.setState(box, "error", { retry: loadHistory });
    });
  }

  function bindConfig() {
    var tbox = document.getElementById("cfg-topics");
    if (tbox && !tbox.children.length) {
      for (var i = 1; i <= 10; i++) {
        (function (n) {
          var lab = el("label", "check");
          var inp = document.createElement("input");
          inp.type = "checkbox";
          inp.value = String(n);
          inp.checked = (n === 2);
          lab.appendChild(inp);
          lab.appendChild(document.createTextNode(" " + t("exam.topic") + " " + n));
          tbox.appendChild(lab);
        })(i);
      }
    }
    function fill(id, vals, labels) {
      var s = document.getElementById(id);
      if (!s || s.options.length) return;
      vals.forEach(function (v, idx) {
        var o = document.createElement("option");
        o.value = v;
        o.textContent = labels[idx];
        s.appendChild(o);
      });
    }
    fill("cfg-type", TYPES, [t("exam.autoType")].concat(TYPES.slice(1)));
    fill("cfg-diff", DIFFS, [t("exam.autoDiff")].concat(DIFFS.slice(1)));

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
        seed: parseInt(document.getElementById("cfg-seed").value, 10) || 0
      };
      if (durRaw) body.duration_seconds = parseInt(durRaw, 10);
      go.disabled = true;
      go.textContent = t("exam.creating");
      out.innerHTML = "";
      api("/api/exam/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }).then(function (res) {
        go.disabled = false;
        go.textContent = t("exam.create");
        if (res.status !== 200) {
          var al = el("div", "alert alert--danger");
          al.setAttribute("role", "alert");
          al.appendChild(el("strong", null, t("exam.createError")));
          al.appendChild(el("p", null, (res.data && res.data.message) || ""));
          out.appendChild(al);
          return;
        }
        window.location.href = "exam.html?xsid=" +
          encodeURIComponent(res.data.exam_session.session_id);
      }).catch(function () {
        go.disabled = false;
        go.textContent = t("exam.create");
        out.appendChild(el("p", null, t("exam.netError")));
      });
    });
  }

  function init() { loadMine(); loadHistory(); bindConfig(); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
