/* Study (B2.3, B2.7): temes, tutor i accés a pràctica. Sense lògica. */
(function () {
  "use strict";

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

  function setState(regionId, state, message, code) {
    var region = document.getElementById(regionId);
    if (!region) return;
    region.innerHTML = "";
    if (state === "loading") {
      var sp = el("span", "spinner");
      sp.setAttribute("role", "status");
      sp.setAttribute("aria-label", "Carregant");
      region.appendChild(sp);
      return;
    }
    var box = el("div", "state-block");
    var icon = el("div", "state-icon", state === "empty" ? "○" : "△");
    icon.setAttribute("aria-hidden", "true");
    box.appendChild(icon);
    box.appendChild(el("h2", null, state === "empty" ? "Buit" : "Error"));
    box.appendChild(el("p", null, message || ""));
    if (code) {
      var c = el("span", "state-code", code);
      box.appendChild(c);
    }
    region.appendChild(box);
  }

  /* Temes + mastery. */
  function loadTopics() {
    var grid = document.getElementById("topics-grid");
    if (!grid) return;
    setState("topics-grid", "loading");
    api("/api/study/topics").then(function (res) {
      grid.innerHTML = "";
      if (res.status !== 200 || !res.data.topics) {
        setState("topics-grid", "error",
          (res.data && res.data.message) || "No s'han pogut carregar.",
          "topics");
        return;
      }
      res.data.topics.forEach(function (t) {
        var card = el("section", "card");
        var h = el("h2", "h3", "Tema " + t.topic);
        card.appendChild(h);
        var meta = el("p", null,
          t.documents + " documents · " + t.sections + " seccions · " +
          t.formulas + " fórmules");
        card.appendChild(meta);
        if (t.mastery && t.mastery.attempts > 0) {
          var lab = el("label", "label", "Mastery (backend)");
          var bar = document.createElement("progress");
          bar.className = "progress";
          bar.max = 1;
          bar.value = t.mastery.score || 0;
          bar.textContent = Math.round((t.mastery.score || 0) * 100) + "%";
          card.appendChild(lab);
          card.appendChild(bar);
        }
        var link = el("a", "button button--secondary",
          "Obrir tema " + t.topic);
        link.href = "topic.html?topic=" + encodeURIComponent(t.topic);
        var p = el("p");
        p.appendChild(link);
        card.appendChild(p);
        grid.appendChild(card);
      });
    }).catch(function () {
      setState("topics-grid", "error", "Error de xarxa.", "topics");
    });
  }

  /* Següent pas (F6 real o buit honest). */
  function loadNext() {
    var box = document.getElementById("next-action");
    if (!box) return;
    api("/api/study/next").then(function (res) {
      box.innerHTML = "";
      var rec = res.data && res.data.recommendation;
      if (res.status === 200 && rec) {
        box.appendChild(el("p", null,
          "Suggeriment: " + (rec.knowledge_unit_id || "") +
          " (" + (rec.action || "") + ")"));
        var a = el("a", "button", "Practicar");
        a.href = "practice.html";
        box.appendChild(a);
      } else {
        box.appendChild(el("p", null,
          "Comença preguntant al tutor o fent una pràctica."));
      }
    }).catch(function () {
      box.innerHTML = "";
      box.appendChild(el("p", null, "Comença per Estudi o Pràctica."));
    });
  }

  /* Tutor. */
  function bindTutor() {
    var form = document.getElementById("tutor-form");
    if (!form) return;
    var out = document.getElementById("tutor-out");
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var input = document.getElementById("tutor-q");
      var btn = document.getElementById("tutor-send");
      var q = input.value.trim();
      if (!q) return;
      btn.disabled = true;
      btn.textContent = "Pensant…";
      out.innerHTML = "";
      var live = el("div", null, "");
      live.setAttribute("role", "status");
      live.textContent = "Carregant resposta…";
      out.appendChild(live);
      api("/api/tutor/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, top_k: 5 })
      }).then(function (res) {
        btn.disabled = false;
        btn.textContent = "Pregunta";
        out.innerHTML = "";
        if (res.status !== 200) {
          var al = el("div", "alert alert--danger");
          al.setAttribute("role", "alert");
          var code = res.data && res.data.code;
          al.appendChild(el("strong", null,
            code === "USER_ERROR" ? "Pregunta buida" : "Error"));
          al.appendChild(el("p", null,
            (res.data && res.data.message) || "Torna-ho a provar."));
          if (code) al.appendChild(el("span", "state-code", code));
          out.appendChild(al);
          var retry = el("button", "button button--secondary",
            "Reintenta");
          retry.type = "button";
          retry.addEventListener("click", function () { input.focus(); });
          out.appendChild(retry);
          return;
        }
        var d = res.data;
        if (d.abstain) {
          var box = el("div", "state-block");
          var ic = el("div", "state-icon", "∅");
          ic.setAttribute("aria-hidden", "true");
          box.appendChild(ic);
          box.appendChild(el("h2", null,
            "Sense evidència suficient"));
          box.appendChild(el("p", null,
            (d.answer || "") +
            " Pots reformular la pregunta o revisar el contingut."));
          box.appendChild(el("span", "badge badge--info", "ABSTAIN"));
          out.appendChild(box);
          return;
        }
        var ans = el("div", "card");
        ans.appendChild(el("h2", "h3", "Resposta"));
        ans.appendChild(el("p", null, d.answer || ""));
        if (d.status) {
          ans.appendChild(el("p", null, "Estat: " + d.status));
        }
        out.appendChild(ans);
        if (d.formulas && d.formulas.length) {
          var fc = el("div", "card");
          fc.appendChild(el("h2", "h3", "Fórmules citades"));
          var ul = el("ul");
          d.formulas.forEach(function (f) {
            ul.appendChild(el("li", "mono", f.equation_id || ""));
          });
          fc.appendChild(ul);
          out.appendChild(fc);
        }
        if (d.provenance && d.provenance.length) {
          var pc = el("div", "card");
          pc.appendChild(el("h2", "h3", "Evidència"));
          var ol = el("ol");
          d.provenance.slice(0, 5).forEach(function (p) {
            ol.appendChild(el("li", null,
              "Tema " + (p.topic === null || p.topic === undefined
                ? "?" : p.topic)));
          });
          pc.appendChild(ol);
          out.appendChild(pc);
        }
      }).catch(function () {
        btn.disabled = false;
        btn.textContent = "Pregunta";
        setState("tutor-out", "error", "Error de xarxa.", "tutor");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadTopics(); loadNext(); bindTutor();
    });
  } else {
    loadTopics(); loadNext(); bindTutor();
  }
})();
