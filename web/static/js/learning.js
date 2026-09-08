/* Learning (B3): prioritats, mastery i progrés. Mostra backend, no decideix. */
(function () {
  "use strict";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function api(path, opts) {
    return window.fetch(path, opts).then(function (r) {
      return r.json().then(function (data) {
        return { status: r.status, data: data };
      });
    });
  }

  function errBox(parent, res, what) {
    parent.innerHTML = "";
    var al = el("div", "alert alert--danger");
    al.setAttribute("role", "alert");
    al.appendChild(el("strong", null, "No disponible"));
    al.appendChild(el("p", null,
      (res.data && res.data.message) || ("No s'ha pogut carregar: " + what)));
    parent.appendChild(al);
  }

  function bar(score) {
    var p = document.createElement("progress");
    p.className = "progress";
    p.max = 1;
    p.value = score || 0;
    p.textContent = Math.round((score || 0) * 100) + "%";
    return p;
  }

  function masteryLine(mu) {
    var wrap = el("div");
    if (!mu) {
      wrap.appendChild(el("p", null, "Sense dades de mastery."));
      return wrap;
    }
    wrap.appendChild(bar(mu.score));
    var t = el("p", null,
      "Mastery: " + (mu.status_label || mu.status || "?") +
      " · " + Math.round((mu.score || 0) * 100) + "%" +
      " · intents: " + (mu.attempts === null ||
        mu.attempts === undefined ? "?" : mu.attempts));
    wrap.appendChild(t);
    if (mu.confidence === null || mu.confidence === undefined) {
      wrap.appendChild(el("p", null, "Confiança: sense dades."));
    } else {
      wrap.appendChild(el("p", null,
        "Confiança: " + Math.round(mu.confidence * 100) + "%"));
    }
    return wrap;
  }

  function priCard(rec, first) {
    var card = el("section", "card");
    if (first) {
      card.appendChild(el("p", null, "Acció recomanada"));
    }
    card.appendChild(el("h2", "h3", rec.unit || ""));
    card.appendChild(el("p", null,
      (rec.action_label || rec.action || "") + " · " +
      (rec.action_hint || "")));
    if (rec.difficulty) {
      card.appendChild(el("p", null, "Dificultat: " + rec.difficulty));
    }
    card.appendChild(masteryLine(rec.mastery));
    (rec.reasons_display || []).forEach(function (r) {
      card.appendChild(el("p", null, r.label + ": " +
        (r.value_label || r.value || "")));
    });
    (rec.errors || []).forEach(function (e) {
      card.appendChild(el("p", null,
        "Error: " + (e.label || e.type || "") + " ×" + e.count));
    });
    var row = el("p");
    var go = el("button", "button", "Practicar");
    go.type = "button";
    go.addEventListener("click", function () {
      go.disabled = true;
      go.textContent = "Preparant…";
      api("/api/learn/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item: {
          knowledge_unit_id: rec.raw_unit || rec.unit,
          unit_kind: rec.raw_kind || rec.kind,
          priority: (rec.priority === undefined ? 0 : rec.priority),
          action: rec.action || "PRACTICE",
          difficulty: rec.difficulty || "",
          target_topic: (rec.targets || {}).topic || null,
          target_section: (rec.targets || {}).section || null,
          target_concepts: ((rec.targets || {}).concepts) || [],
          target_formulas: ((rec.targets || {}).formulas) || [],
          reasons: rec.reasons || []
        } })
      }).then(function (res) {
        go.disabled = false;
        go.textContent = "Practicar";
        if (res.status !== 200) {
          errBox(card, res, "generació");
          return;
        }
        try {
          window.sessionStorage.setItem("sm-adaptive-q",
            JSON.stringify(res.data.question || {}));
        } catch (e) { /* sense sessionStorage: navega igual */ }
        window.location.href = "practice.html?from=adaptive";
      }).catch(function () {
        go.disabled = false;
        go.textContent = "Practicar";
        errBox(card, { data: {} }, "generació");
      });
    });
    row.appendChild(go);
    var loc = el("a", "button button--secondary", "Contingut");
    loc.href = "#";
    loc.addEventListener("click", function (ev) {
      ev.preventDefault();
      locate(rec.unit, card);
    });
    row.appendChild(document.createTextNode(" "));
    row.appendChild(loc);
    card.appendChild(row);
    return card;
  }

  function locate(unit, parent) {
    api("/api/learn/locate?unit=" + encodeURIComponent(unit))
      .then(function (res) {
        var l = res.data && res.data.locate;
        if (res.status === 200 && l && l.url) {
          window.location.href = l.url;
        } else {
          var note = el("p", null,
            "Sense contingut enllaçable per a aquesta unitat.");
          parent.appendChild(note);
        }
      });
  }

  function loadPriorities() {
    var box = document.getElementById("pri-list");
    if (!box) return;
    box.innerHTML = "";
    var live = el("p", null, "Carregant prioritats…");
    live.setAttribute("role", "status");
    box.appendChild(live);
    api("/api/learn/priorities?limit=5").then(function (res) {
      box.innerHTML = "";
      if (res.status !== 200) {
        errBox(box, res, "prioritats");
        return;
      }
      var list = res.data.priorities || [];
      window.__priList = list;
      if (!list.length) {
        var b = el("div", "state-block");
        var ic = el("div", "state-icon", "○");
        ic.setAttribute("aria-hidden", "true");
        b.appendChild(ic);
        b.appendChild(el("h2", null, "Sense prioritats"));
        b.appendChild(el("p", null,
          "De moment no hi ha prioritats. Fes una pràctica i torna."));
        b.appendChild(el("span", "badge badge--info", "NO PRIORITIES"));
        box.appendChild(b);
        return;
      }
      list.forEach(function (r, i) {
        var full = {
          unit: r.unit, kind: r.kind, action: r.action,
          action_label: r.action_label, action_hint: r.action_hint,
          difficulty: r.difficulty, targets: r.targets,
          reasons_display: r.reasons_display, mastery: r.mastery,
          errors: r.errors, raw_unit: r.unit, raw_kind: r.kind,
          priority: r.priority, reasons: r.reasons
        };
        box.appendChild(priCard(full, i === 0));
      });
      var next = document.getElementById("next-box");
      if (next && list.length) {
        next.innerHTML = "";
        next.appendChild(el("p", null,
          "Comença per: " + list[0].unit + " — " +
          (list[0].action_label || "")));
      }
    }).catch(function () {
      errBox(box, { data: {} }, "prioritats");
    });
  }

  function loadMastery() {
    var box = document.getElementById("mastery-box");
    if (!box) return;
    api("/api/study/mastery").then(function (res) {
      box.innerHTML = "";
      if (res.status !== 200) {
        errBox(box, res, "mastery");
        return;
      }
      var any = false;
      // Ordre del backend (per tema): no reordenar al frontend (B3.33).
      Object.keys(res.data.mastery || {}).forEach(function (t) {
        var m = res.data.mastery[t];
        var card = el("div", "card");
        card.appendChild(el("h2", "h3", "Tema " + t));
        if (!m || (m.attempts || 0) === 0) {
          card.appendChild(el("p", null, "Sense dades."));
        } else {
          any = true;
          card.appendChild(bar(m.score));
          card.appendChild(el("p", null,
            Math.round((m.score || 0) * 100) + "% · " +
            m.attempts + " intents"));
        }
        var a = el("a", null, "Obrir tema");
        a.href = "topic.html?topic=" + encodeURIComponent(t);
        var p = el("p");
        p.appendChild(a);
        card.appendChild(p);
        box.appendChild(card);
      });
      if (!any) {
        var note = el("p", null,
          "Cap intent registrat: completa una pràctica per construir progrés.");
        box.appendChild(note);
      }
    }).catch(function () {
      errBox(box, { data: {} }, "mastery");
    });
  }

  function loadProgress() {
    var box = document.getElementById("progress-box");
    if (!box) return;
    api("/api/learn/progress").then(function (res) {
      box.innerHTML = "";
      if (res.status !== 200) {
        errBox(box, res, "progrés");
        return;
      }
      var d = res.data;
      if (!d.attempts) {
        var b = el("div", "state-block");
        var ic = el("div", "state-icon", "○");
        ic.setAttribute("aria-hidden", "true");
        b.appendChild(ic);
        b.appendChild(el("h2", null, "Encara no hi ha activitat"));
        b.appendChild(el("p", null,
          "Completa una pràctica per començar a construir el progrés."));
        box.appendChild(b);
        return;
      }
      var ul = el("ul");
      ul.appendChild(el("li", null, "Intents: " + d.attempts));
      ul.appendChild(el("li", null, "Correctes: " + d.correct));
      ul.appendChild(el("li", null, "Unitats: " + d.units));
      ul.appendChild(el("li", null,
        "Última activitat: " + (d.last_activity || "?")));
      box.appendChild(ul);
      if ((d.recent || []).length) {
        box.appendChild(el("h2", "h3", "Recents"));
        var ol = el("ol");
        d.recent.forEach(function (r) {
          ol.appendChild(el("li", "mono",
            (r.created_at || "?") + " · " + (r.question_id || "?")));
        });
        box.appendChild(ol);
      }
    }).catch(function () {
      errBox(box, { data: {} }, "progrés");
    });
  }

  function loadUnit() {
    var root = document.getElementById("unit-root");
    if (!root) return;
    var m = window.location.search.match(/[?&]unit=([^&]*)/);
    var unit = m ? decodeURIComponent(m[1]) : "";
    if (!unit) return;
    api("/api/learn/unit?unit=" + encodeURIComponent(unit))
      .then(function (res) {
        root.innerHTML = "";
        if (res.status !== 200 || !res.data.state) {
          root.appendChild(el("p", null,
            "Sense dades per a aquesta unitat."));
          return;
        }
        var st = res.data.state;
        root.appendChild(el("h2", "h3", unit));
        root.appendChild(masteryLine({
          score: st.score, status: st.status,
          status_label: st.status_label, confidence: st.confidence,
          attempts: st.attempt_count }));
        (res.data.errors || []).forEach(function (e) {
          root.appendChild(el("p", null,
            "Error: " + e.label + " ×" + e.count));
        });
        root.appendChild(el("p", null,
          "Correctes: " + st.correct_count + " · Incorrectes: " +
          st.incorrect_count));
        var l = res.data.locate;
        if (l && l.url) {
          var a = el("a", "button button--secondary",
            "Veure contingut");
          a.href = l.url;
          root.appendChild(a);
        }
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadPriorities(); loadMastery(); loadProgress(); loadUnit();
    });
  } else {
    loadPriorities(); loadMastery(); loadProgress(); loadUnit();
  }
})();
