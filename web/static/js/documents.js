(function () {
  "use strict";
  var root = document.getElementById("documents-root");
  var select = document.getElementById("documents-topic");
  var status = document.getElementById("documents-status");

  function el(tag, cls, value) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (value !== undefined) node.textContent = value;
    return node;
  }

  function load() {
    root.innerHTML = "";
    status.textContent = "Carregant documents…";
    var suffix = select.value ? "?topic=" + encodeURIComponent(select.value) : "";
    fetch("/api/documents" + suffix)
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.message || "Error");
        var docs = result.data.documents || [];
        status.textContent = docs.length + " documents · font: " + result.data.source;
        docs.forEach(function (doc) {
          var card = el("article", "card document-card");
          card.appendChild(el("h2", "h3", doc.title));
          card.appendChild(el("p", "hint", "Tema " + doc.topic + " · " +
            (doc.kind || "document") + " · " + doc.sections + " seccions"));
          var link = el("a", "button button--secondary", "Obrir document");
          link.href = "topic.html?topic=" + encodeURIComponent(doc.topic) +
            "&doc_id=" + encodeURIComponent(doc.id);
          card.appendChild(link);
          root.appendChild(card);
        });
        if (!docs.length) root.appendChild(el("p", "state-block", "No hi ha documents per a aquest filtre."));
      })
      .catch(function () {
        status.textContent = "No s'han pogut carregar els documents.";
      });
  }

  fetch("/api/study/topics").then(function (response) { return response.json(); })
    .then(function (data) {
      (data.topics || []).forEach(function (topic) {
        var option = document.createElement("option");
        option.value = topic.topic;
        option.textContent = "Tema " + topic.topic;
        select.appendChild(option);
      });
    }).then(load).catch(load);
  select.addEventListener("change", load);
}());
