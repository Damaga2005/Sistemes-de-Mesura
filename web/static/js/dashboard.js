/* Dashboard (F17 Task 4): Inici learning dashboard. Presentation only.
   Renders real API data; every region has skeleton/error/empty states.
   Consumes window.smUI + window.smI18n. No domain logic, no client sort. */
(function () {
  "use strict";

  var ui = window.smUI;
  var i18n = window.smI18n;
  if (!ui) return;

  function t(key) { return i18n && i18n.t ? i18n.t(key) : key; }
  function byId(id) { return document.getElementById(id); }
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }
  function hasScore(m) {
    if (!m || !(m.attempts > 0)) return false;
    var sc = m.score;
    return typeof sc === "number" && isFinite(sc);
  }

  var DASH = "—";        /* em dash for "no value" */
  var WAVE = " 👋"; /* waving hand */

  function cta(text, href) {
    var a = ui.el("a", "button", text);
    a.href = href;
    return a;
  }

  /* ---- greeting: time-of-day only, never data ---- */
  function greeting() {
    var g = byId("greeting");
    if (!g) return;
    var h = new Date().getHours();
    var key = h < 12 ? "dash.morning" : (h < 20 ? "dash.afternoon" : "dash.evening");
    g.textContent = t(key) + WAVE;
  }

  /* ---- HeroCard: /api/study/next (+ mastery for the bar) ---- */
  function loadHero() {
    var region = byId("hero-continue");
    if (!region) return;
    ui.setState(region, "loading", { kind: "card" });
    Promise.all([ui.api("/api/study/next"), ui.api("/api/study/mastery")]).then(
      function (res) {
        var nextRes = res[0], mastRes = res[1];
        if (nextRes.status !== 200) {
          ui.setState(region, "error", { retry: loadHero, code: nextRes.status });
          return;
        }
        var rec = nextRes.data && nextRes.data.recommendation;
        var mastMap = (mastRes.status === 200 && mastRes.data && mastRes.data.mastery) || {};
        renderHero(region, rec, mastMap);
      },
      function () { ui.setState(region, "error", { retry: loadHero }); }
    );
  }

  function renderHero(region, rec, mastMap) {
    ui.setState(region, "ready");
    var card = ui.el("section", "hero-card");
    card.appendChild(ui.el("p", "hero-card__eyebrow", t("dash.hero.eyebrow")));
    var topicNo = rec && rec.target_topic != null ? rec.target_topic : null;
    if (topicNo == null) {
      card.appendChild(ui.el("h2", "hero-card__title", t("dash.hero.startTitle")));
      card.appendChild(ui.el("p", null, t("dash.hero.startBody")));
      card.appendChild(cta(t("dash.hero.ctaStart"), "temari.html"));
      region.appendChild(card);
      return;
    }
    card.appendChild(ui.el("h2", "hero-card__title", t("dash.topic") + " " + topicNo));
    var entry = mastMap[String(topicNo)];
    if (hasScore(entry)) {
      card.appendChild(ui.progressBar(entry.score, t("dash.domini")));
    }
    card.appendChild(ui.el("p", null, t("dash.hero.body")));
    var isPractice = rec.action === "PRACTICE";
    card.appendChild(cta(t("dash.hero.cta"),
      isPractice ? "practice.html" : ("topic.html?topic=" + topicNo)));
    region.appendChild(card);
  }

  /* ---- 3 StatCards: /api/learn/progress (+ mastery for Domini ring) ---- */
  function loadStats() {
    var dom = byId("stat-domini"), pre = byId("stat-precisio"), preg = byId("stat-preguntes");
    if (!dom || !pre || !preg) return;
    var all = [dom, pre, preg];
    all.forEach(function (n) { ui.setState(n, "loading", { kind: "stat" }); });
    Promise.all([ui.api("/api/learn/progress"), ui.api("/api/study/mastery")]).then(
      function (res) {
        var progRes = res[0], mastRes = res[1];
        if (progRes.status !== 200 || mastRes.status !== 200) {
          var code = progRes.status !== 200 ? progRes.status : mastRes.status;
          all.forEach(function (n) {
            ui.setState(n, "error", { kind: "stat", retry: loadStats, code: code });
          });
          return;
        }
        renderStats(dom, pre, preg, progRes.data || {},
          (mastRes.data && mastRes.data.mastery) || {});
      },
      function () {
        all.forEach(function (n) {
          ui.setState(n, "error", { kind: "stat", retry: loadStats });
        });
      }
    );
  }

  function statCard(region, value, label, context) {
    clear(region);
    region.appendChild(ui.el("div", "stat-card__value", value));
    region.appendChild(ui.el("div", "stat-card__label", label));
    if (context) region.appendChild(ui.el("div", "stat-card__context", context));
  }

  function renderStats(dom, pre, preg, progress, mastMap) {
    var attempts = progress.attempts || 0;
    if (!attempts) {
      statCard(dom, DASH, t("dash.domini"), t("dash.noData"));
      statCard(pre, DASH, t("dash.precisio"), t("dash.noData"));
      statCard(preg, DASH, t("dash.preguntes"), t("dash.noData"));
      return;
    }
    var total = 0, seen = 0, entry;
    for (var n = 1; n <= 10; n++) {
      entry = mastMap[String(n)];
      if (hasScore(entry)) {
        total += entry.score;
        seen += 1;
      }
    }
    if (seen) {
      ui.setState(dom, "ready");
      dom.appendChild(ui.progressRing(total / seen));
      dom.appendChild(ui.el("div", "stat-card__label", t("dash.domini")));
    } else {
      statCard(dom, DASH, t("dash.domini"), t("dash.noData"));
    }
    var correct = progress.correct || 0;
    ui.setState(pre, "ready");
    pre.appendChild(ui.el("div", "stat-card__value", Math.round((correct / attempts) * 100) + "%"));
    pre.appendChild(ui.el("div", "stat-card__label", t("dash.precisio")));
    ui.setState(preg, "ready");
    preg.appendChild(ui.el("div", "stat-card__value", String(attempts)));
    preg.appendChild(ui.el("div", "stat-card__label", t("dash.preguntes")));
  }

  /* ---- Necessites reforçar: /api/learn/priorities (+ topics for card meta) ---- */
  function loadReinforce() {
    var region = byId("reinforce-cards");
    var section = byId("reinforce-section");
    if (!region) return;
    ui.setState(region, "loading", { kind: "list" });
    Promise.all([ui.api("/api/learn/priorities?limit=6"), ui.api("/api/study/topics")]).then(
      function (res) {
        var priRes = res[0], topRes = res[1];
        if (priRes.status !== 200) {
          ui.setState(region, "error", { retry: loadReinforce, code: priRes.status });
          return;
        }
        var list = (priRes.data && priRes.data.priorities) || [];
        var topicsOk = topRes.status === 200;
        var topics = (topicsOk && topRes.data && topRes.data.topics) || [];
        renderReinforce(region, section, list, topics, topicsOk);
      },
      function () { ui.setState(region, "error", { retry: loadReinforce }); }
    );
  }

  function findTopic(topics, no) {
    for (var i = 0; i < topics.length; i++) {
      if (Number(topics[i].topic) === Number(no)) return topics[i];
    }
    return null;
  }

  function topicCard(no, info, topicsOk) {
    var card = ui.el("article", "topic-card card");
    var head = ui.el("div", "topic-card__head");
    head.appendChild(ui.el("span", "pill", t("dash.topic") + " " + no));
    var mInfo = info && info.mastery ? info.mastery : null;
    /* topics/mastery fetch failed -> status unknown, show no badge (not a false "No iniciat") */
    if (topicsOk) {
      var state = ui.statusFromMastery(mInfo);
      head.appendChild(ui.badge(t(state.labelKey), state.key));
    }
    card.appendChild(head);
    if (hasScore(mInfo)) {
      card.appendChild(ui.progressBar(mInfo.score, t("dash.domini")));
    }
    if (info) {
      card.appendChild(ui.el("p", "topic-card__meta",
        info.sections + " " + t("dash.sections") + " · " +
        info.formulas + " " + t("dash.formulas")));
    }
    var link = ui.el("a", "topic-card__cta", t("dash.reinforceCta"));
    link.href = "topic.html?topic=" + no;
    card.appendChild(link);
    return card;
  }

  function renderReinforce(region, section, list, topics, topicsOk) {
    var picked = [], byTopic = {}, i, tp;
    for (i = 0; i < list.length && picked.length < 3; i++) {
      tp = list[i] && list[i].targets ? list[i].targets.topic : null;
      if (tp == null || byTopic[tp]) continue;
      byTopic[tp] = 1;
      picked.push(tp);
    }
    if (!picked.length) {
      if (section) section.hidden = true;
      return;
    }
    if (section) section.hidden = false;
    ui.setState(region, "ready");
    for (i = 0; i < picked.length; i++) {
      region.appendChild(topicCard(picked[i], findTopic(topics, picked[i]), topicsOk));
    }
  }

  /* ---- Activitat recent: /api/learn/progress recent[] ---- */
  function loadRecent() {
    var region = byId("recent-activity");
    if (!region) return;
    ui.setState(region, "loading", { kind: "list" });
    ui.api("/api/learn/progress").then(
      function (res) {
        if (res.status !== 200) {
          ui.setState(region, "error", { retry: loadRecent, code: res.status });
          return;
        }
        renderRecent(region, (res.data && res.data.recent) || []);
      },
      function () { ui.setState(region, "error", { retry: loadRecent }); }
    );
  }

  function renderRecent(region, recent) {
    if (!recent.length) {
      ui.setState(region, "empty",
        { ctaText: t("dash.startPractice"), ctaHref: "practice.html" });
      return;
    }
    ui.setState(region, "ready");
    var list = ui.el("ul", "dash-recent");
    for (var i = 0; i < recent.length && i < 5; i++) {
      var it = recent[i] || {};
      var row = ui.el("li");
      row.appendChild(ui.el("span", "dash-recent__unit", it.question_id || DASH));
      row.appendChild(ui.el("span", "dash-recent__time", ui.relativeTime(it.created_at)));
      list.appendChild(row);
    }
    region.appendChild(list);
  }

  function init() {
    greeting();
    loadHero();
    loadStats();
    loadReinforce();
    loadRecent();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
