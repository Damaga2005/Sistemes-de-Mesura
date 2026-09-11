/* Tutor IA (F17 §4.5). Presentation only: answers, formulas, provenance and
   abstain all come from /api/tutor/ask. Conversation is session-local JS
   state — never persisted (no storage, no cookie). */
(function () {
  "use strict";

  var ui = window.smUI || {};
  var i18n = window.smI18n || null;
  var el = ui.el || function (tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  function t(key) { return (i18n && i18n.t) ? i18n.t(key) : key; }

  var history = [];            // in-memory conversation only
  var thread, form, input, btn;
  var pending = false;

  function providerOf(d) {
    return d && d.versions && d.versions.provider && d.versions.provider.provider;
  }

  function scrollToEnd() {
    var last = thread.lastChild;
    if (last && last.scrollIntoView) last.scrollIntoView({ block: "nearest" });
  }

  function userMessage(text) {
    var msg = el("div", "chat__msg chat__msg--user");
    msg.appendChild(el("div", "chat__bubble", text));
    thread.appendChild(msg);
  }

  function tutorShell() {
    var msg = el("div", "chat__msg chat__msg--tutor");
    var avatar = el("div", "chat__avatar", "Σ");
    avatar.setAttribute("aria-hidden", "true");
    var col = el("div", "chat__col");
    msg.appendChild(avatar);
    msg.appendChild(col);
    msg._col = col;
    return msg;
  }

  function loadingMessage() {
    var msg = tutorShell();
    var bubble = el("div", "chat__bubble");
    var typing = el("div", "chat__typing");
    typing.appendChild(el("span"));
    typing.appendChild(el("span"));
    typing.appendChild(el("span"));
    bubble.appendChild(typing);
    msg._col.appendChild(bubble);
    thread.appendChild(msg);
    return msg;
  }

  function resetShell(msg) {
    msg.innerHTML = "";
    var avatar = el("div", "chat__avatar", "Σ");
    avatar.setAttribute("aria-hidden", "true");
    var col = el("div", "chat__col");
    msg.appendChild(avatar);
    msg.appendChild(col);
    msg._col = col;
    return col;
  }

  function actionRow(col, d, query) {
    var row = el("div", "chat__actions");
    var prov = d.provenance || [];
    if (prov[0] && typeof prov[0].topic === "number") {
      var practise = el("a", "button button--secondary", t("tutor.practice"));
      practise.href = "practice.html?topic=" + encodeURIComponent(prov[0].topic);
      row.appendChild(practise);
    }
    var again = el("button", "button button--secondary", t("tutor.rephrase"));
    again.type = "button";
    again.addEventListener("click", function () {
      ask(query + " " + t("tutor.rephraseHint"));
    });
    row.appendChild(again);
    var ev = el("button", "button button--secondary", t("practice.evidence"));
    ev.type = "button";
    ev.addEventListener("click", function () {
      if (ui.openEvidence) {
        ui.openEvidence({ provenance: prov, formulas: d.formulas || [] });
      }
    });
    row.appendChild(ev);
    col.appendChild(row);
  }

  function renderAnswer(msg, d, query) {
    var col = resetShell(msg);
    var bubble = el("div", "chat__bubble", d.answer || "");
    col.appendChild(bubble);
    if (window.smMath) window.smMath.renderMath(bubble);
    var formulas = d.formulas || [];
    if (formulas.length) {
      var chips = el("div", "chat__formulas");
      for (var i = 0; i < formulas.length; i++) {
        chips.appendChild(el("code", "chip-num", formulas[i].equation_id || ""));
      }
      col.appendChild(chips);
    }
    if (d.status) {
      col.appendChild(el("div", "chat__status", t("tutor.status") + ": " + d.status));
    }
    actionRow(col, d, query);
  }

  function renderAbstain(msg, d) {
    var col = resetShell(msg);
    var bubble = el("div", "chat__bubble chat__bubble--abstain");
    bubble.appendChild(ui.badge ? ui.badge(t("tutor.abstain"), "info")
                                : el("span", "badge badge--info", "ABSTAIN"));
    var abstainText = el("p", null, d.answer || "");
    bubble.appendChild(abstainText);
    if (window.smMath) window.smMath.renderMath(abstainText);
    col.appendChild(bubble);
    col.appendChild(el("div", "chat__status", t("tutor.reformulate")));
  }

  function renderError(msg, d, query) {
    var col = resetShell(msg);
    var bubble = el("div", "chat__bubble chat__bubble--error");
    bubble.setAttribute("role", "alert");
    var userError = d && d.code === "USER_ERROR";
    bubble.appendChild(el("strong", null,
      userError ? t("tutor.emptyQuestion") : t("tutor.errorTitle")));
    if (d && d.message) bubble.appendChild(el("p", null, d.message));
    col.appendChild(bubble);
    var retry = el("button", "button button--secondary", t("common.retry"));
    retry.type = "button";
    retry.addEventListener("click", function () { ask(query); });
    col.appendChild(retry);
  }

  function ask(query) {
    if (pending) return;
    query = (query || "").trim();
    if (!query) return;
    history.push({ role: "user", text: query });
    userMessage(query);
    var loadMsg = loadingMessage();
    scrollToEnd();
    var label = btn.textContent;
    btn.disabled = true;
    btn.textContent = t("tutor.pending");
    pending = true;
    ui.api("/api/tutor/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query, top_k: 5 })
    }).then(function (res) {
      pending = false;
      btn.disabled = false;
      btn.textContent = label;
      var d = res.data || {};
      if (res.status !== 200) {
        renderError(loadMsg, d, query);
      } else if (d.abstain) {
        renderAbstain(loadMsg, d);
        history.push({ role: "tutor", text: d.answer || "" });
      } else {
        renderAnswer(loadMsg, d, query);
        history.push({ role: "tutor", text: d.answer || "" });
      }
      if (ui.setProvider) ui.setProvider(providerOf(d));
      scrollToEnd();
    }).catch(function () {
      pending = false;
      btn.disabled = false;
      btn.textContent = label;
      renderError(loadMsg, {}, query);
      scrollToEnd();
    });
  }

  function contextLine() {
    var m = /[?&]topic=(\d+)/.exec(window.location.search);
    if (!m) return;
    thread.appendChild(el("p", "chat__context", t("tutor.context") + " " + m[1]));
  }

  function init() {
    thread = document.getElementById("tutor-thread");
    form = document.getElementById("tutor-form");
    input = document.getElementById("tutor-input");
    if (!thread || !form || !input) return;
    btn = form.querySelector('button[type="submit"]');
    contextLine();
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var q = input.value.trim();
      if (!q) return;
      input.value = "";
      ask(q);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
