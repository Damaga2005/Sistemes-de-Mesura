/* MathJax 3 config (self-hosted, tex-svg). MUST run before the combined
   component script tag (both non-deferred, in this order) -- MathJax reads
   window.MathJax once at load and boots from it.

   Delimiters: $...$ is the ONLY one that actually appears anywhere in the
   knowledge base or in generated question stems (verified: 505 KB chunks +
   real question prompts use it; zero \( \), \[ \] or $$ occurrences exist
   in the corpus today). \( \) and \[ \] are supported too (a generative
   provider is not constrained to the KB's own convention). $$ is included
   for the same reason, at zero extra cost.

   startup.typeset=false: this app never wants MathJax scanning the whole
   page on load -- content arrives async from the API. Every screen calls
   window.smMath.renderMath(root) (math-renderer.js) explicitly, once, on
   the exact node it just filled with text. */
window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]],
    processEscapes: true
  },
  svg: {
    fontCache: "global"
  },
  options: {
    skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"],
    ignoreHtmlClass: "no-math"
  },
  startup: {
    typeset: false
  }
};
