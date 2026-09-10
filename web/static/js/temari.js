/* Temari (F17 Task 5): topic explorer. Presentation only.
   Renders /api/study/topics as TopicCards; the status badge is derived by
   the frozen smUI.statusFromMastery helper (never re-implemented here).
   No domain logic, no client sort, no storage. */
(function () {
  "use strict";

  var ui = window.smUI;
  var i18n = window.smI18n;
  if (!ui) return;

  function t(key) { return i18n && i18n.t ? i18n.t(key) : key; }
  function byId(id) { return document.getElementById(id); }
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }

  function hasBar(m) {
    if (!m || !(m.attempts > 0)) return false;
    var sc = m.score;
    return typeof sc === "number" && isFinite(sc);
  }

  function topicCard(tp) {
    var card = ui.el("a", "card card--link topic-card");
    card.href = "topic.html?topic=" + tp.topic;

    var head = ui.el("div", "topic-card__head");
    head.appendChild(ui.el("span", "chip-num", String(tp.topic)));
    var st = ui.statusFromMastery(tp.mastery);
    head.appendChild(ui.badge(t(st.labelKey), st.key));
    card.appendChild(head);

    card.appendChild(ui.el("h3", "topic-card__title", t("dash.topic") + " " + tp.topic));

    if (hasBar(tp.mastery)) {
      card.appendChild(ui.progressBar(tp.mastery.score, t("temari.mastery")));
    }

    card.appendChild(ui.el("p", "topic-card__meta",
      tp.sections + " " + t("temari.sections") + " · " +
      tp.formulas + " " + t("temari.formulas")));

    card.appendChild(ui.el("span", "topic-card__cta", t("temari.open")));
    return card;
  }

  function render(container, topics) {
    if (!topics.length) {
      ui.setState(container, "empty",
        { ctaText: t("temari.emptyCta"), ctaHref: "index.html" });
      return;
    }
    ui.setState(container, "ready");
    for (var i = 0; i < topics.length; i++) {
      container.appendChild(topicCard(topics[i]));
    }
  }

  function load() {
    var container = byId("topic-cards");
    if (!container) return;
    ui.setState(container, "loading", { kind: "card" });
    ui.api("/api/study/topics").then(
      function (res) {
        if (res.status !== 200) {
          ui.setState(container, "error", { retry: load, code: res.status });
          return;
        }
        render(container, (res.data && res.data.topics) || []);
      },
      function () { ui.setState(container, "error", { retry: load }); }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
