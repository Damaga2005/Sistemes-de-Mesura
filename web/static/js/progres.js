/* Progrés (F17 Task 9, §4.6): learning dashboard. Presentation only.
   Renders real API data (/api/learn/progress, /api/study/mastery,
   /api/learn/priorities, /api/learn/unit); the adaptive [Començar] handoff
   (POST /api/learn/start -> sessionStorage -> practice.html?from=adaptive)
   is the unchanged adaptive handoff mechanism.
   No domain logic, no client sort, no persistence. Consumes smUI + smI18n. */
(function () {
  "use strict";

  var ui = window.smUI;
  var i18n = window.smI18n;
  if (!ui) return;

  function t(key) { return i18n && i18n.t ? i18n.t(key) : key; }
  function byId(id) { return document.getElementById(id); }

  var DASH = "—";
  var restLoaded = false;

  function sectionOf(region) {
    var n = region;
    while (n && n.tagName !== "SECTION") n = n.parentNode;
    return n;
  }

  function showSection(region, visible) {
    var s = sectionOf(region);
    if (s) s.hidden = !visible;
  }

  /* ---------- Resum: StatCards from /api/learn/progress ---------- */
  function statCard(value, label) {
    var card = ui.el("div", "stat-card card");
    card.appendChild(ui.el("div", "stat-card__value", value));
    card.appendChild(ui.el("div", "stat-card__label", label));
    return card;
  }

  function accuracy(correct, attempts) {
    if (!attempts) return DASH;
    return Math.round((correct / attempts) * 100) + "%";
  }

  function loadSummary() {
    var region = byId("prog-summary");
    if (!region) return;
    ui.setState(region, "loading", { kind: "stat" });
    ui.api("/api/learn/progress").then(function (res) {
      if (res.status !== 200) {
        ui.setState(region, "error", { retry: loadSummary, code: res.status });
        loadRest();
        return;
      }
      var d = res.data || {};
      if (!(d.attempts || 0)) {
        ui.setState(region, "empty",
          { ctaText: t("prog.startPractice"), ctaHref: "practice.html" });
        showSection(byId("prog-mastery"), false);
        showSection(byId("prog-recommend"), false);
        showSection(byId("prog-unit"), false);
        return;
      }
      renderSummary(region, d);
      loadRest();
    }, function () {
      ui.setState(region, "error", { retry: loadSummary });
      loadRest();
    });
  }

  function renderSummary(region, d) {
    ui.setState(region, "ready");
    region.setAttribute("role", "status");
    region.appendChild(statCard(String(d.attempts || 0), t("prog.attempts")));
    region.appendChild(statCard(accuracy(d.correct || 0, d.attempts || 0),
      t("prog.accuracy")));
    region.appendChild(statCard(d.units == null ? DASH : String(d.units),
      t("prog.units")));
    var last = d.last_activity ? (ui.relativeTime(d.last_activity) || DASH) : DASH;
    region.appendChild(statCard(last, t("prog.lastActivity")));
  }

  function loadRest() {
    if (restLoaded) return;
    restLoaded = true;
    loadMastery();
    loadRecommend();
    loadUnit();
  }

  /* ---------- Domini per tema: 10 rows from /api/study/mastery ---------- */
  /* ponytail: client-side reconstruction of a backend-owned unit-id format
     (carried over from the deleted learning.js); a miss degrades to the honest
     empty state. Proper fix is /api/study/mastery returning the unit id — out
     of scope for F17 (no backend change). */
  function topicUnit(n) { return n < 10 ? "topic:T0" + n : "topic:T" + n; }

  function masteryRow(n, rec) {
    var row = ui.el("div", "prog-row card");
    row.appendChild(ui.el("span", "prog-row__label", t("prog.topic") + " " + n));
    var body = ui.el("div", "prog-row__body");
    if (rec && rec.attempts > 0) {
      body.appendChild(ui.progressBar(rec.score, t("prog.domain")));
    }
    var st = ui.statusFromMastery(rec);
    body.appendChild(ui.badge(t(st.labelKey), st.key));
    row.appendChild(body);
    var more = ui.el("button", "button button--secondary prog-row__detail",
      t("prog.detail"));
    more.type = "button";
    more.addEventListener("click", function () { showUnit(topicUnit(n)); });
    row.appendChild(more);
    return row;
  }

  function loadMastery() {
    var region = byId("prog-mastery");
    if (!region) return;
    showSection(region, true);
    ui.setState(region, "loading", { kind: "list" });
    ui.api("/api/study/mastery").then(function (res) {
      if (res.status !== 200) {
        ui.setState(region, "error", { retry: loadMastery, code: res.status });
        return;
      }
      ui.setState(region, "ready");
      var map = (res.data && res.data.mastery) || {};
      for (var n = 1; n <= 10; n++) {
        region.appendChild(masteryRow(n, map[String(n)]));
      }
    }, function () {
      ui.setState(region, "error", { retry: loadMastery });
    });
  }

  /* ---------- Recomanat per a tu: /api/learn/priorities?limit=3 ---------- */
  function startError(res) {
    var al = ui.el("div", "alert alert--danger");
    al.setAttribute("role", "alert");
    al.appendChild(ui.el("p", null,
      (res && res.data && res.data.message) || t("prog.startError")));
    return al;
  }

  function startAdaptive(rec, btn, card) {
    btn.disabled = true;
    btn.textContent = t("prog.preparing");
    ui.api("/api/learn/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item: {
        knowledge_unit_id: rec.unit,
        unit_kind: rec.kind,
        action: rec.action || "PRACTICE",
        difficulty: rec.difficulty || "",
        target_topic: (rec.targets || {}).topic == null
          ? null : rec.targets.topic,
        target_section: (rec.targets || {}).section || null,
        target_concepts: (rec.targets || {}).concepts || [],
        target_formulas: (rec.targets || {}).formulas || [],
        reasons: rec.reasons || []
      } })
    }).then(function (res) {
      btn.disabled = false;
      btn.textContent = t("prog.start");
      if (res.status !== 200) {
        card.appendChild(startError(res));
        return;
      }
      try {
        window.sessionStorage.setItem("sm-adaptive-q",
          JSON.stringify(res.data.question || {}));
      } catch (e) { /* sense sessionStorage: navega igual */ }
      window.location.href = "practice.html?from=adaptive";
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = t("prog.start");
      card.appendChild(startError({ data: {} }));
    });
  }

  function recCard(rec) {
    var card = ui.el("article", "rec-card card");
    card.appendChild(ui.el("p", "rec-card__eyebrow", t("prog.recommended")));
    card.appendChild(ui.el("h3", "rec-card__title", rec.unit || ""));
    if (rec.action_label) {
      card.appendChild(ui.el("p", "rec-card__action", rec.action_label));
    }
    var reasons = rec.reasons_display || [];
    for (var i = 0; i < reasons.length; i++) {
      var r = reasons[i];
      card.appendChild(ui.el("p", "rec-card__reason",
        r.label + ": " + (r.value_label || r.value || "")));
    }
    if (rec.difficulty) {
      var meta = ui.el("div", "rec-card__meta");
      meta.appendChild(ui.badge(rec.difficulty, "neutral"));
      card.appendChild(meta);
    }
    var btn = ui.el("button", "button", t("prog.start"));
    btn.type = "button";
    btn.addEventListener("click", function () { startAdaptive(rec, btn, card); });
    card.appendChild(btn);
    return card;
  }

  function loadRecommend() {
    var region = byId("prog-recommend");
    if (!region) return;
    showSection(region, true);
    ui.setState(region, "loading", { kind: "list" });
    ui.api("/api/learn/priorities?limit=3").then(function (res) {
      if (res.status !== 200) {
        ui.setState(region, "error", { retry: loadRecommend, code: res.status });
        return;
      }
      var list = (res.data && res.data.priorities) || [];
      if (!list.length) {
        ui.setState(region, "empty",
          { ctaText: t("prog.startPractice"), ctaHref: "practice.html" });
        return;
      }
      ui.setState(region, "ready");
      list.forEach(function (rec) { region.appendChild(recCard(rec)); });
    }, function () {
      ui.setState(region, "error", { retry: loadRecommend });
    });
  }

  /* ---------- Detall d'unitat: /api/learn/unit?unit= (expandable) ---------- */
  function renderUnit(region, unit, d) {
    ui.setState(region, "ready");
    var panel = ui.el("div", "prog-unit__panel");
    panel.appendChild(ui.el("h3", "prog-unit__title", unit));
    var st = d.state || {};
    var m = { attempts: st.attempt_count, score: st.score };
    if (m.attempts > 0) {
      panel.appendChild(ui.progressBar(st.score, t("prog.domain")));
    }
    var stat = ui.statusFromMastery(m);
    panel.appendChild(ui.badge(t(stat.labelKey), stat.key));
    panel.appendChild(ui.el("p", "prog-unit__counts",
      t("prog.correct") + ": " + (st.correct_count || 0) + " · " +
      t("prog.incorrect") + ": " + (st.incorrect_count || 0)));
    var errors = d.errors || [];
    if (errors.length) {
      var ul = ui.el("ul", "prog-unit__errors");
      errors.forEach(function (e) {
        ul.appendChild(ui.el("li", null,
          (e.label || e.type || "") + " ×" + e.count));
      });
      panel.appendChild(ul);
    }
    var events = d.events || [];
    if (events.length) {
      var ol = ui.el("ol", "prog-unit__timeline");
      events.forEach(function (ev) {
        var li = ui.el("li", "prog-unit__event");
        li.appendChild(ui.el("span", "prog-unit__event-time",
          ui.relativeTime(ev.created_at || ev.at || "") || (ev.created_at || "")));
        li.appendChild(ui.el("span", "prog-unit__event-label",
          ev.label || ev.kind || ev.question_id || ""));
        ol.appendChild(li);
      });
      panel.appendChild(ol);
    }
    var loc = d.locate;
    if (loc && loc.url) {
      var a = ui.el("a", "button button--secondary", t("prog.viewContent"));
      a.href = loc.url;
      panel.appendChild(a);
    }
    region.appendChild(panel);
  }

  function showUnit(unit) {
    var region = byId("prog-unit");
    if (!region) return;
    showSection(region, true);
    ui.setState(region, "loading", { kind: "card" });
    region.scrollIntoView({ block: "nearest" });
    ui.api("/api/learn/unit?unit=" + encodeURIComponent(unit)).then(function (res) {
      if (res.status !== 200 || !res.data || !res.data.state) {
        ui.setState(region, "empty", {});
        return;
      }
      renderUnit(region, unit, res.data);
    }, function () {
      ui.setState(region, "error", { retry: function () { showUnit(unit); } });
    });
  }

  function loadUnit() {
    var region = byId("prog-unit");
    if (!region) return;
    var m = /[?&]unit=([^&]*)/.exec(window.location.search);
    if (m) {
      showUnit(decodeURIComponent(m[1]));
    } else {
      showSection(region, false);
    }
  }

  function init() { loadSummary(); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
