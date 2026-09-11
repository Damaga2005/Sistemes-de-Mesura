/* Math renderer: single responsibility, LaTeX (already in the DOM as plain
   text) -> rendered math, via MathJax 3 (self-hosted, tex-svg).

   renderMath(root) never touches innerHTML: MathJax's own typesetPromise()
   mutates the DOM internally. Callers keep doing `node.textContent = text`
   (safe, unchanged) and then call renderMath(node) once the text is in
   place. If MathJax hasn't finished booting yet, we wait on its own
   startup promise; if MathJax never loads (offline asset missing, etc.)
   or a formula fails to typeset, we resolve quietly and leave the plain
   text visible -- never throw into the caller, never touch the chat/exam
   flow. */
(function () {
  "use strict";

  function typeset(root) {
    var mj = window.MathJax;
    if (!mj || typeof mj.typesetPromise !== "function") return Promise.resolve();
    return mj.typesetPromise([root]).catch(function () {
      /* malformed LaTeX or a MathJax internal error: leave whatever
         MathJax already put in the DOM (it renders its own inline error
         marker for bad TeX); never propagate to the caller. */
    });
  }

  function renderMath(root) {
    if (!root) return Promise.resolve();
    var mj = window.MathJax;
    if (mj && mj.startup && mj.startup.promise &&
        typeof mj.typesetPromise !== "function") {
      return mj.startup.promise.then(function () { return typeset(root); })
        .catch(function () { return typeset(root); });
    }
    return typeset(root);
  }

  window.smMath = { renderMath: renderMath };
})();
