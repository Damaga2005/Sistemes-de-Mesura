/* smFetch: adjunta X-CSRF-Token (cookie sm_csrf) a les peticions mutants. */
(function () {
  "use strict";
  function readCookie(name) {
    var m = document.cookie.match("(?:^|; )" + name + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : "";
  }
  window.smFetch = function (path, opts) {
    opts = opts || {};
    var method = (opts.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
      opts.headers = opts.headers || {};
      opts.headers["X-CSRF-Token"] = readCookie("sm_csrf");
    }
    return window.fetch(path, opts);
  };
})();
