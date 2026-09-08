/* Topic i Content (B2.4–B2.5): llistes KB + blocs. Tot textContent
   excepte l'HTML de fórmules servit pel renderer llista-blanca. */
(function () {
  "use strict";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function api(path) {
    return window.fetch(path).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function params() {
    var q = {};
    window.location.search.replace(/^\?/, "").split("&").forEach(
      function (kv) {
        var p = kv.split("=");
        if (p[0]) q[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || "");
      });
    return q;
  }

  function loadTopic() {
    var root = document.getElementById("topic-root");
    if (!root) return;
    var query = params();
    var topic = query.topic || "";
    var docId = query.doc_id || "";
    var path = "/api/study/documents?topic=" + encodeURIComponent(topic);
    if (docId) path += "&doc_id=" + encodeURIComponent(docId);
    api(path)
      .then(function (res) {
        root.innerHTML = "";
        if (res.status !== 200) {
          root.appendChild(el("p", null, "Tema no trobat."));
          return;
        }
        var title = document.getElementById("topic-title");
        if (title) title.textContent = "Tema " + topic;
        (res.data.documents || []).forEach(function (d) {
          var card = el("section", "card");
          card.appendChild(el("h2", "h3", d.title || ("Document " + d.id)));
          card.appendChild(el("p", null, "Tipus: " + (d.kind || "?")));
          var secs = el("div");
          secs.setAttribute("role", "status");
          secs.textContent = "Carregant seccions…";
          card.appendChild(secs);
          root.appendChild(card);
          loadSections(d, secs);
        });
        if (!(res.data.documents || []).length) {
          root.appendChild(el("p", null, "Sense documents."));
        }
      });
  }

  function loadSections(doc, box) {
    api("/api/study/sections?doc_id=" + encodeURIComponent(doc.id))
      .then(function (res) {
        box.innerHTML = "";
        if (res.status !== 200) return;
        var ul = el("ul");
        (res.data.sections || []).forEach(function (s) {
          var li = el("li");
          var a = el("a", null, s.h2 || ("Secció " + s.id));
          a.href = "content.html?section_id=" + encodeURIComponent(s.id);
          li.appendChild(a);
          ul.appendChild(li);
        });
        box.appendChild(ul);
      });
  }

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
    var root = document.getElementById("content-root");
    if (!root) return;
    var sid = params().section_id || "";
    api("/api/study/content?section_id=" + encodeURIComponent(sid))
      .then(function (res) {
        root.innerHTML = "";
        if (res.status !== 200) {
          root.appendChild(el("p", null, "Secció no trobada."));
          return;
        }
        var title = document.getElementById("content-title");
        if (title) title.textContent = res.data.h2 || "Contingut";
        (res.data.blocks || []).forEach(function (b) {
          renderBlock(root, b);
        });
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadTopic(); loadContent();
    });
  } else {
    loadTopic(); loadContent();
  }
})();
