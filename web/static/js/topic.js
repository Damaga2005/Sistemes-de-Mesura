/* Tema + Contingut (F17 Task 6). Presentation only, no domain logic.
   Tema = learning unit: title, optional progress bar, "Continguts" list.
   Content = prose reader; formula HTML comes from the whitelisted renderer
   (B2.28) and is the only innerHTML assignment in this file. */
(function () {
  "use strict";

  var ui = window.smUI;
  var i18n = window.smI18n;
  if (!ui) return;

  var el = ui.el;
  function t(key) { return i18n && i18n.t ? i18n.t(key) : key; }
  function byId(id) { return document.getElementById(id); }
  function enc(v) { return encodeURIComponent(v); }

  function params() {
    var q = {};
    window.location.search.replace(/^\?/, "").split("&").forEach(
      function (kv) {
        var p = kv.split("=");
        if (p[0]) q[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || "");
      });
    return q;
  }

  /* ---------- Tema ---------- */
  function loadMastery(topicNo) {
    var slot = byId("topic-progress");
    if (!slot || !topicNo) return;
    ui.api("/api/study/mastery").then(function (res) {
      if (res.status !== 200) return;
      var table = (res.data && res.data.mastery) || {};
      var mrec = table[String(topicNo)];
      if (mrec && mrec.attempts > 0) {
        slot.appendChild(ui.progressBar(mrec.score, t("topic.progress")));
      }
    });
  }

  function loadSections(doc, list, topicNo) {
    ui.api("/api/study/sections?doc_id=" + enc(doc.id)).then(function (res) {
      if (res.status !== 200) return;
      (res.data.sections || []).forEach(function (s) {
        var li = el("li");
        var a = el("a", null, s.h2 || ("Secció " + s.id));
        a.href = "content.html?section_id=" + enc(s.id) + "&topic=" + enc(topicNo);
        li.appendChild(a);
        list.appendChild(li);
      });
    });
  }

  function renderContents(root, docs, topicNo) {
    ui.setState(root, "ready");
    root.appendChild(el("h2", "contents__title", t("topic.contents")));
    docs.forEach(function (d) {
      var group = el("section", "contents-group");
      group.appendChild(el("h3", "contents-group__title", d.title || ("Document " + d.id)));
      var list = el("ul", "contents-list");
      group.appendChild(list);
      root.appendChild(group);
      loadSections(d, list, topicNo);
    });
  }

  function loadTopic() {
    var root = byId("topic-root");
    if (!root) return;
    var query = params();
    var topicNo = query.topic || "";
    var docId = query.doc_id || "";

    var title = byId("topic-title");
    if (title) title.textContent = "Tema " + topicNo;

    var practice = byId("act-practice");
    if (practice) practice.href = "practice.html?topic=" + topicNo;
    var tutor = byId("act-tutor");
    if (tutor) tutor.href = "tutor.html?topic=" + topicNo;

    loadMastery(topicNo);

    ui.setState(root, "loading", { kind: "list" });
    var path = "/api/study/documents?topic=" + enc(topicNo);
    if (docId) path += "&doc_id=" + enc(docId);
    ui.api(path).then(
      function (res) {
        if (res.status !== 200) {
          ui.setState(root, "error", { retry: loadTopic, code: res.status });
          return;
        }
        var docs = (res.data && res.data.documents) || [];
        if (!docs.length) {
          ui.setState(root, "empty", { ctaText: t("topic.backTemari"), ctaHref: "temari.html" });
          return;
        }
        renderContents(root, docs, topicNo);
      },
      function () { ui.setState(root, "error", { retry: loadTopic }); }
    );
  }

  /* ---------- Contingut ---------- */
  function renderBlock(parent, b) {
    if (b.kind === "formula") {
      var f = el("p", "formula", "");
      if (b.html) {
        f.innerHTML = b.html; /* B2.28: només renderer llista-blanca */
      } else {
        f.textContent = b.expression || "";
      }
      var cap = el("p", null, "");
      var code = el("code", "mono", b.equation_id || "");
      cap.appendChild(code);
      parent.appendChild(f);
      parent.appendChild(cap);
      return;
    }
    if (b.kind === "table") {
      var wrap = el("div", "table-wrap");
      var pre = el("pre", "mono", b.text || "");
      if (b.caption) {
        wrap.appendChild(el("p", null, b.caption));
      }
      wrap.appendChild(pre);
      parent.appendChild(wrap);
      return;
    }
    (b.text || "").split("\n").forEach(function (para) {
      if (para.trim()) parent.appendChild(el("p", null, para));
    });
  }

  function loadContent() {
    var root = byId("content-root");
    if (!root) return;
    var sid = params().section_id || "";
    var backTopic = params().topic || "";
    var back = document.getElementById("content-back");
    if (back) back.href = backTopic ? ("topic.html?topic=" + enc(backTopic)) : "temari.html";
    ui.setState(root, "loading");
    ui.api("/api/study/content?section_id=" + enc(sid)).then(
      function (res) {
        if (res.status !== 200) {
          ui.setState(root, "error", { retry: loadContent, code: res.status });
          return;
        }
        var title = byId("content-title");
        if (title) title.textContent = res.data.h2 || t("topic.contentFallback");
        var blocks = (res.data && res.data.blocks) || [];
        if (!blocks.length) {
          ui.setState(root, "empty", { ctaText: t("topic.backTema"), ctaHref: "topic.html" });
          return;
        }
        ui.setState(root, "ready");
        blocks.forEach(function (b) { renderBlock(root, b); });
      },
      function () { ui.setState(root, "error", { retry: loadContent }); }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadTopic(); loadContent();
    });
  } else {
    loadTopic(); loadContent();
  }
})();
