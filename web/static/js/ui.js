/* smUI (F17): shared UI helpers. Presentation only, no domain logic.
   Consumes window.smFetch (csrf.js), window.smI18n (i18n.js), window.smOpenDrawer (app.js). */
(function () {
  "use strict";

  var I18N = window.smI18n || null;
  function t(key) { return I18N && I18N.t ? I18N.t(key) : key; }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function api(path, opts) {
    var fetcher = window.smFetch || window.fetch;
    return fetcher(path, opts || {}).then(function (res) {
      var ct = (res.headers && res.headers.get && res.headers.get("content-type")) || "";
      var body = ct.indexOf("application/json") !== -1 ? res.json() : res.text();
      return body.then(function (data) { return { status: res.status, data: data }; });
    });
  }

  var SKELETONS = {
    text: ["skeleton skeleton--text"],
    title: ["skeleton skeleton--title"],
    stat: ["skeleton skeleton--title", "skeleton skeleton--stat"],
    list: ["skeleton skeleton--text", "skeleton skeleton--text", "skeleton skeleton--text"],
    card: ["skeleton skeleton--title", "skeleton skeleton--text",
           "skeleton skeleton--text", "skeleton skeleton--text"]
  };
  function skeleton(kind) {
    var wrap = el("div", "skeleton-group");
    wrap.setAttribute("aria-hidden", "true");
    var rows = SKELETONS[kind] || SKELETONS.text;
    for (var i = 0; i < rows.length; i++) wrap.appendChild(el("div", rows[i]));
    return wrap;
  }

  function clampPct(v) {
    var n = typeof v === "number" && isFinite(v) ? v : 0;
    if (n < 0) n = 0;
    if (n > 1) n = 1;
    return Math.round(n * 100);
  }

  function progressBar(v, label) {
    var p = clampPct(v);
    var bar = el("div", label ? "progress progress--labeled" : "progress");
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-valuenow", String(p));
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    bar.setAttribute("aria-label", label || (p + "%"));
    var fill = el("span", "progress__fill");
    fill.style.width = p + "%";
    bar.appendChild(fill);
    return bar;
  }

  var SVGNS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVGNS, tag);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) node.setAttribute(k, attrs[k]);
    }
    return node;
  }
  function progressRing(v, label) {
    var p = clampPct(v);
    var radius = 52;
    var circ = 2 * Math.PI * radius;
    var root = svgEl("svg", { "class": "progress-ring", viewBox: "0 0 120 120", role: "img" });
    root.setAttribute("aria-label", (label ? label + " " : "") + p + "%");
    var defs = svgEl("defs", {});
    var grad = svgEl("linearGradient", { id: "sm-ring-grad", x1: "0", y1: "0", x2: "1", y2: "1" });
    grad.appendChild(svgEl("stop", { offset: "0", "stop-color": "var(--accent)" }));
    grad.appendChild(svgEl("stop", { offset: "1", "stop-color": "var(--accent-hover)" }));
    defs.appendChild(grad);
    root.appendChild(defs);
    root.appendChild(svgEl("circle", {
      "class": "progress-ring__track", cx: "60", cy: "60", r: String(radius),
      fill: "none", "stroke-width": "10"
    }));
    root.appendChild(svgEl("circle", {
      "class": "progress-ring__value", cx: "60", cy: "60", r: String(radius),
      fill: "none", "stroke-width": "10", "stroke-linecap": "round",
      stroke: "url(#sm-ring-grad)", transform: "rotate(-90 60 60)",
      "stroke-dasharray": String(circ),
      "stroke-dashoffset": String(circ * (1 - p / 100))
    }));
    return root;
  }

  var STATUS_VARIANTS = { none: 1, reinforce: 1, progress: 1, high: 1, complete: 1 };
  function badge(text, variantKey) {
    var v = variantKey || "neutral";
    var cls = STATUS_VARIANTS[v] ? "badge badge--status-" + v : "badge badge--" + v;
    var b = el("span", cls);
    var dot = el("span", "badge__dot");
    dot.setAttribute("aria-hidden", "true");
    b.appendChild(dot);
    b.appendChild(document.createTextNode(text));
    return b;
  }

  function statusFromMastery(m) {
    if (!m || !m.attempts || m.attempts <= 0) return { key: "none", labelKey: "status.none" };
    var v = m.score;
    if (v < 0.40) return { key: "reinforce", labelKey: "status.reinforce" };
    if (v < 0.75) return { key: "progress",  labelKey: "status.progress" };
    if (v < 0.95) return { key: "high",      labelKey: "status.high" };
    return { key: "complete", labelKey: "status.complete" };
  }

  function relativeTime(iso) {
    var then = Date.parse(iso);
    if (isNaN(then)) return "";
    var secs = Math.round((Date.now() - then) / 1000);
    if (secs < 60) return t("time.now");
    var mins = Math.round(secs / 60);
    if (mins < 60) return t("time.ago") + " " + mins + " " + t("time.min");
    var hrs = Math.round(mins / 60);
    if (hrs < 24) return t("time.ago") + " " + hrs + " " + t("time.hour");
    return t("time.ago") + " " + Math.round(hrs / 24) + " " + t("time.day");
  }

  function stateBlock(kind, opts) {
    var block = el("div", "state-block");
    var mark = kind === "error" ? "△" : "○";
    var iconWrap = el("div", "state-block__icon", mark);
    iconWrap.setAttribute("aria-hidden", "true");
    block.appendChild(iconWrap);
    block.appendChild(el("h2", null,
      t(kind === "error" ? "state.errorTitle" : "state.emptyTitle")));
    block.appendChild(el("p", null, opts.message ||
      t(kind === "error" ? "common.loadError" : "common.empty")));
    if (kind === "error" && opts.code) {
      block.appendChild(el("code", "state-code", String(opts.code)));
    }
    if (kind === "error" && typeof opts.retry === "function") {
      var rb = el("button", "button", opts.ctaText || t("common.retry"));
      rb.type = "button";
      rb.addEventListener("click", opts.retry);
      block.appendChild(rb);
    }
    if (kind === "empty" && opts.ctaHref) {
      var link = el("a", "button", opts.ctaText || t("common.empty"));
      link.href = opts.ctaHref;
      block.appendChild(link);
    }
    return block;
  }

  function setState(region, kind, opts) {
    if (!region) return;
    opts = opts || {};
    region.innerHTML = "";
    if (kind === "loading") {
      region.setAttribute("aria-busy", "true");
      region.appendChild(skeleton(opts.kind || "card"));
      return;
    }
    region.removeAttribute("aria-busy");
    region.appendChild(stateBlock(kind, opts));
  }

  function openEvidence(opts) {
    opts = opts || {};
    var prov = opts.provenance || [];
    var formulas = opts.formulas || [];
    var backdrop = el("div", "drawer__backdrop");
    backdrop.setAttribute("data-drawer-close", "");
    var drawer = el("aside", "drawer");
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.setAttribute("aria-label", t("common.evidence"));

    var head = el("div", "drawer__header");
    head.appendChild(el("h2", null, t("common.evidence")));
    var x = el("button", "icon-button", "×");
    x.type = "button";
    x.setAttribute("aria-label", t("common.close"));
    x.setAttribute("data-drawer-close", "");
    head.appendChild(x);
    drawer.appendChild(head);

    var body = el("div", "drawer__body");
    if (prov.length) {
      var ul = el("ul", "drawer__list");
      for (var i = 0; i < prov.length; i++) ul.appendChild(el("li", null, String(prov[i])));
      body.appendChild(ul);
    }
    if (formulas.length) {
      var chips = el("div", "drawer__formulas");
      for (var j = 0; j < formulas.length; j++) {
        chips.appendChild(el("code", "chip-num", String(formulas[j])));
      }
      body.appendChild(chips);
    }
    body.appendChild(el("p", "drawer__verified", t("common.verified")));
    drawer.appendChild(body);

    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);
    if (window.smOpenDrawer) {
      window.smOpenDrawer(drawer, backdrop);
    } else {
      drawer.setAttribute("data-open", "");
    }
  }

  var PROVIDER_COLOR = {
    gemini: "var(--accent)", fallback: "var(--warning)",
    local: "var(--text-tertiary)", ready: "var(--text-tertiary)"
  };
  function setProvider(providerName) {
    var name = String(providerName || "ready").toLowerCase();
    if (!PROVIDER_COLOR[name]) name = "ready";
    var dot = document.getElementById("provider-dot");
    var label = document.getElementById("provider-label");
    if (dot) dot.style.color = PROVIDER_COLOR[name];
    if (label) {
      label.textContent = t(name === "ready" ? "provider.ready" : "provider." + name);
    }
  }

  window.smUI = {
    el: el, api: api, setState: setState, skeleton: skeleton,
    progressBar: progressBar, progressRing: progressRing, badge: badge,
    statusFromMastery: statusFromMastery, relativeTime: relativeTime,
    openEvidence: openEvidence, setProvider: setProvider
  };
})();
