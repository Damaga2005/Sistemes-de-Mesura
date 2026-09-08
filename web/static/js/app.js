/* App JS (B1): millora progressiva. Sense lògica de domini. */
(function () {
  "use strict";

  /* Navegació mòbil. */
  document.querySelectorAll("[data-menu-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var nav = document.getElementById(btn.getAttribute("aria-controls"));
      if (!nav) return;
      var collapsed = nav.getAttribute("data-collapsed") === "true";
      nav.setAttribute("data-collapsed", collapsed ? "false" : "true");
      btn.setAttribute("aria-expanded", collapsed ? "true" : "false");
    });
  });

  /* Tabs (patró manual: botons reals + aria-selected). */
  document.querySelectorAll("[data-tabs]").forEach(function (group) {
    var tabs = Array.prototype.slice.call(
      group.querySelectorAll('[role="tab"]'));
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { select(i); });
      tab.addEventListener("keydown", function (ev) {
        var j = null;
        if (ev.key === "ArrowRight") j = (i + 1) % tabs.length;
        if (ev.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
        if (j !== null) { ev.preventDefault(); select(j); tabs[j].focus(); }
      });
    });
    function select(i) {
      tabs.forEach(function (tab, j) {
        var on = i === j;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(
          tab.getAttribute("aria-controls"));
        if (panel) panel.hidden = !on;
      });
    }
  });

  /* Modal: focus + Escape. */
  var lastFocus = null;
  document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var modal = document.getElementById(btn.getAttribute("data-modal-open"));
      if (!modal) return;
      lastFocus = document.activeElement;
      modal.hidden = false;
      var first = modal.querySelector("button, [href], input, select, textarea");
      if (first) first.focus();
    });
  });
  document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var modal = btn.closest(".modal-backdrop");
      if (!modal) return;
      modal.hidden = true;
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    });
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    document.querySelectorAll(".modal-backdrop:not([hidden])")
      .forEach(function (modal) {
        modal.hidden = true;
        if (lastFocus && lastFocus.focus) lastFocus.focus();
      });
  });

  /* Toast de demostració (galeria). */
  document.querySelectorAll("[data-toast]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var region = document.getElementById("toast-region");
      if (!region) return;
      var el = document.createElement("div");
      el.className = "toast";
      el.setAttribute("role", "status");
      el.textContent = btn.getAttribute("data-toast");
      region.appendChild(el);
      window.setTimeout(function () { el.remove(); }, 4000);
    });
  });

  /* Dropdown. */
  document.querySelectorAll("[data-dropdown]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var menu = document.getElementById(btn.getAttribute("aria-controls"));
      if (!menu) return;
      var open = menu.hidden === false;
      menu.hidden = open;
      btn.setAttribute("aria-expanded", open ? "false" : "true");
    });
  });
  document.addEventListener("click", function (ev) {
    document.querySelectorAll(".dropdown-menu:not([hidden])")
      .forEach(function (menu) {
        var wrap = menu.closest(".dropdown");
        if (wrap && !wrap.contains(ev.target)) {
          menu.hidden = true;
          var btn = wrap.querySelector("[data-dropdown]");
          if (btn) btn.setAttribute("aria-expanded", "false");
        }
      });
  });
})();
