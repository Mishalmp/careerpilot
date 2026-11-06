/* Runs before first paint so the page never flashes the wrong theme.
   Served as a same-origin file (not inline) so a future strict CSP (script-src 'self') still allows it.
   Reads the cp-theme and cp-density cookies written by src/lib/theme.tsx. */
(function () {
  try {
    var cookie = document.cookie;
    var t = (cookie.match(/(?:^|; )cp-theme=(light|dark|system)/) || [])[1] || "system";
    var dark = t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    var root = document.documentElement;
    root.classList.toggle("dark", dark);
    root.style.colorScheme = dark ? "dark" : "light";
    root.dataset.density = (cookie.match(/(?:^|; )cp-density=(compact|comfortable)/) || [])[1] || "comfortable";
  } catch (e) {
    /* cookies blocked: keep the default light theme */
  }
})();
