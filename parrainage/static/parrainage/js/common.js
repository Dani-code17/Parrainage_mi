/* =========================================================
   Parrainage MIAGE — utilitaires communs
   ========================================================= */
(function () {
  'use strict';

  var PM = window.PM = window.PM || {};

  /** true si l'utilisateur a demandé moins d'animations */
  PM.reduceMotion = (function () {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
    catch (e) { return false; }
  })();

  function pad(n) { return n < 10 ? '0' + n : String(n); }

  /**
   * Compte à rebours.
   * Lit la date dans l'attribut data-deadline de l'élément (format ISO, ex. 2026-10-31T23:59:00).
   * Remplit les éléments [data-cd="d|h|m|s|label|compact"] qu'il contient.
   */
  PM.countdown = function (root) {
    if (!root) return;
    var end = new Date(root.getAttribute('data-deadline')).getTime();
    var q = function (k) { return root.querySelector('[data-cd="' + k + '"]'); };
    var label = q('label'), compact = q('compact');
    var openLabel = label ? label.textContent : '';

    function tick() {
      var diff = isNaN(end) ? -1 : end - Date.now();
      var d = '—', h = '—', m = '—', s = '—';
      if (diff > 0) {
        var t = Math.floor(diff / 1000);
        d = pad(Math.floor(t / 86400));
        h = pad(Math.floor((t % 86400) / 3600));
        m = pad(Math.floor((t % 3600) / 60));
        s = pad(t % 60);
        if (label) label.textContent = openLabel;
        if (compact) compact.textContent = Math.floor(t / 86400) + 'j ' + h + 'h ' + m + 'm ' + s + 's';
      } else if (!isNaN(end)) {
        d = '00'; h = '00'; m = '00'; s = '00';
        if (label) label.textContent = root.getAttribute('data-closed-label') || 'Les inscriptions sont closes';
        if (compact) compact.textContent = 'closes';
        clearInterval(timer);
      }
      ['d', 'h', 'm', 's'].forEach(function (k, i) {
        var el = q(k); if (el) el.textContent = [d, h, m, s][i];
      });
    }
    var timer = setInterval(tick, 1000);
    tick();
  };
})();
