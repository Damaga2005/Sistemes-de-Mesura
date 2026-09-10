/* App JS (B1 / F17): millora progressiva. Sense lògica de domini. */
(function () {
  "use strict";

  /* Focus-trap compartit: modal + drawer. Retorna una funció close(). */
  function trapFocus(container, onClose) {
    var prev = document.activeElement;
    var SEL = 'a[href],button:not([disabled]),input:not([disabled]),' +
      'select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
    function items() {
      return Array.prototype.slice.call(container.querySelectorAll(SEL))
        .filter(function (n) { return n.offsetParent !== null || n === document.activeElement; });
    }
    function onKey(ev) {
      if (ev.key === "Escape") { ev.preventDefault(); close(); return; }
      if (ev.key !== "Tab") return;
      var f = items();
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
    }
    function close() {
      document.removeEventListener("keydown", onKey, true);
      if (typeof onClose === "function") onClose();
      if (prev && prev.focus) prev.focus();
    }
    document.addEventListener("keydown", onKey, true);
    var f = items();
    if (f.length) f[0].focus();
    return close;
  }
  window.smTrapFocus = trapFocus;

  /* Drawer (creat dinàmicament per ui.js): backdrop-click + [data-drawer-close] + Esc. */
  var drawerClose = null;
  window.smOpenDrawer = function (drawer, backdrop) {
    drawerClose = trapFocus(drawer, function () {
      if (backdrop) backdrop.remove();
      drawer.remove();
      drawerClose = null;
    });
    drawer.setAttribute("data-open", "");
    function bye() { if (drawerClose) drawerClose(); }
    if (backdrop) backdrop.addEventListener("click", bye);
    drawer.querySelectorAll("[data-drawer-close]").forEach(function (b) {
      b.addEventListener("click", bye);
    });
  };

  /* Tabs (patró manual: botons reals + aria-selected). */
  document.querySelectorAll("[data-tabs]").forEach(function (group) {
    var tabs = Array.prototype.slice.call(group.querySelectorAll('[role="tab"]'));
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
        var panel = document.getElementById(tab.getAttribute("aria-controls"));
        if (panel) panel.hidden = !on;
      });
    }
  });

  /* Modal: focus-trap compartit + Escape. */
  var closeModal = null;
  document.querySelectorAll("[data-modal-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var modal = document.getElementById(btn.getAttribute("data-modal-open"));
      if (!modal) return;
      modal.hidden = false;
      closeModal = trapFocus(modal, function () { modal.hidden = true; });
    });
  });
  document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
    btn.addEventListener("click", function () { if (closeModal) closeModal(); });
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
    document.querySelectorAll(".dropdown-menu:not([hidden])").forEach(function (menu) {
      var wrap = menu.closest(".dropdown");
      if (wrap && !wrap.contains(ev.target)) {
        menu.hidden = true;
        var btn = wrap.querySelector("[data-dropdown]");
        if (btn) btn.setAttribute("aria-expanded", "false");
      }
    });
  });
})();
