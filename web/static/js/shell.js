/* Shell (F17): renders header + sidebar chrome around <main id="main"> from NAV. */
(function () {
  "use strict";
  var t = (window.smI18n && window.smI18n.t) || function (k) { return k; };
  var NAV = [
    { group: null, items: [
      { key: "nav.inici", href: "index.html", icon: "home" } ] },
    { group: "nav.g.estudi", items: [
      { key: "nav.temari", href: "temari.html", icon: "book" },
      { key: "nav.practica", href: "practice.html", icon: "target" } ] },
    { group: "nav.g.aprendre", items: [
      { key: "nav.tutor", href: "tutor.html", icon: "sparkles" },
      { key: "nav.progres", href: "progres.html", icon: "chart" } ] },
    { group: "nav.g.avaluacio", items: [
      { key: "nav.examens", href: "exams.html", icon: "clipboard-check" } ] }
  ];
  /* Sub-pages that belong to a nav section but are not themselves nav targets.
     Their route resolves to the parent section so the sidebar still shows one
     active item. Pages outside every section (documents/calendar) map nowhere. */
  var SECTION_OF = {
    "topic.html": "temari.html", "content.html": "temari.html",
    "exam.html": "exams.html", "results.html": "exams.html",
    "review.html": "exams.html"
  };
  function icon(name) {
    return '<svg class="icon" aria-hidden="true"><use href="static/icons.svg#' + name + '"></use></svg>';
  }
  function renderHeader(header, nav) {
    header.innerHTML =
      '<button class="icon-button menu-toggle" type="button" data-menu-toggle ' +
      'aria-controls="site-nav" aria-expanded="false" aria-label="' + t("nav.menu") + '">' +
      icon("menu") + '</button>' +
      '<a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">Σ</span>' +
      'Sistemes de Mesura</a><span class="header-spacer"></span>' +
      '<label class="lang-switch"><span class="visually-hidden">' + t("common.language") + '</span>' +
      '<select id="lang-select"><option value="ca">CA</option><option value="es">ES</option></select></label>';
    var sel = header.querySelector("#lang-select");
    sel.value = (window.smI18n && window.smI18n.lang) || "ca";
    sel.addEventListener("change", function () { window.smI18n.setLang(sel.value); });
    var mt = header.querySelector("[data-menu-toggle]");
    mt.addEventListener("click", function () {
      var c = nav.getAttribute("data-collapsed") === "true";
      nav.setAttribute("data-collapsed", c ? "false" : "true");
      mt.setAttribute("aria-expanded", c ? "true" : "false");
    });
  }

  function renderNav(nav, route) {
    var section = SECTION_OF[route] || route;
    var html = '<a class="brand brand--rail" href="index.html">' +
      '<span class="brand-mark" aria-hidden="true">Σ</span>Sistemes de Mesura</a><ul class="nav-list">';
    NAV.forEach(function (sec) {
      if (sec.group) html += '<li class="nav-group" aria-hidden="true">' + t(sec.group) + '</li>';
      sec.items.forEach(function (it) {
        var active = it.href === route || it.href === section;
        html += '<li><a class="nav-link" href="' + it.href + '"' +
          (active ? ' aria-current="page"' : '') + '>' + icon(it.icon) +
          '<span>' + t(it.key) + '</span></a></li>';
      });
    });
    html += '</ul><div class="nav-footer"><span class="provider-dot" id="provider-dot"></span>' +
      '<span id="provider-label">' + t("provider.ready") + '</span></div>';
    nav.innerHTML = html;
  }

  function build() {
    var route = document.body.getAttribute("data-route") || "";
    var main = document.getElementById("main");
    if (!main) return;
    var grid = document.createElement("div"); grid.className = "body-grid";
    var header = document.createElement("header"); header.className = "header";
    var nav = document.createElement("nav");
    nav.className = "sidebar"; nav.id = "site-nav";
    nav.setAttribute("aria-label", "Principal");
    nav.setAttribute("data-collapsed", "true");
    renderNav(nav, route);
    main.parentNode.insertBefore(grid, main);
    grid.appendChild(nav); grid.appendChild(main);
    document.body.insertBefore(header, grid);
    renderHeader(header, nav);
    if (window.smI18n && window.smI18n.onChange) {
      window.smI18n.onChange(function () {
        renderHeader(header, nav);
        renderNav(nav, route);
      });
    }
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", build);
  else build();
})();
