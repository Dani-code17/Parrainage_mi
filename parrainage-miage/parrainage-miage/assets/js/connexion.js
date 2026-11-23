/* =========================================================
   Parrainage MIAGE — Page de connexion
   Validation côté client + confort (œil, Verr. Maj, chargement).
   Le formulaire est envoyé normalement au serveur (POST) :
   la vraie vérification des identifiants reste côté serveur.
   ========================================================= */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  window.PM.countdown($('countdown'));

  var form = $('login-form');
  var idInput = $('lx-id'), pwInput = $('lx-pw');
  var idMsg = $('lx-id-msg'), pwMsg = $('lx-pw-msg');
  var idHelp = idMsg.textContent;
  var serverError = $('server-error');
  var touched = false, caps = false;

  // Démo : ?erreur=1 affiche le bandeau d'erreur (dans Django, il est rendu par le template)
  if (serverError && /[?&]erreur=1\b/.test(location.search)) serverError.hidden = false;
  function hideServerError() { if (serverError && !serverError.hasAttribute('data-keep')) serverError.hidden = true; }

  function setMsg(el, text, kind) {
    el.textContent = text;
    el.classList.toggle('is-error', kind === 'error');
    el.classList.toggle('is-warn', kind === 'warn');
  }

  function validate() {
    var idErr = touched && !idInput.value.trim();
    var pwErr = touched && !pwInput.value;
    idInput.setAttribute('aria-invalid', idErr ? 'true' : 'false');
    pwInput.setAttribute('aria-invalid', pwErr ? 'true' : 'false');
    setMsg(idMsg, idErr ? 'Indique ton identifiant.' : idHelp, idErr ? 'error' : null);
    if (pwErr) setMsg(pwMsg, 'Indique ton mot de passe.', 'error');
    else if (caps) setMsg(pwMsg, 'Attention : la touche Verr. Maj est activée.', 'warn');
    else setMsg(pwMsg, '', null);
    return !idErr && !pwErr;
  }

  idInput.addEventListener('input', function () { hideServerError(); validate(); });
  pwInput.addEventListener('input', function () { hideServerError(); validate(); });

  // Détection de la touche Verr. Maj
  ['keyup', 'keydown'].forEach(function (evt) {
    pwInput.addEventListener(evt, function (e) {
      if (typeof e.getModifierState === 'function') { caps = e.getModifierState('CapsLock'); validate(); }
    });
  });

  // Afficher / masquer le mot de passe
  var toggle = $('toggle-pw');
  toggle.addEventListener('click', function () {
    var show = pwInput.type === 'password';
    pwInput.type = show ? 'text' : 'password';
    toggle.setAttribute('aria-pressed', show ? 'true' : 'false');
    toggle.setAttribute('aria-label', show ? 'Masquer le mot de passe' : 'Afficher le mot de passe');
    toggle.querySelector('[data-eye="show"]').hidden = show;
    toggle.querySelector('[data-eye="hide"]').hidden = !show;
    pwInput.focus();
  });

  // Envoi
  form.addEventListener('submit', function (e) {
    touched = true;
    if (!validate()) {
      e.preventDefault();
      (!idInput.value.trim() ? idInput : pwInput).focus();
      return;
    }
    // Indicateur de chargement pendant que le serveur répond
    var btn = $('submit-btn');
    $('submit-loader').hidden = false;
    $('submit-label').textContent = 'Connexion…';
    btn.setAttribute('aria-busy', 'true');
    // On évite le double envoi sans désactiver le bouton avant l'envoi
    setTimeout(function () { btn.disabled = true; }, 0);
  });

  // Si l'utilisateur revient avec le bouton « précédent », on réinitialise le bouton
  window.addEventListener('pageshow', function () {
    $('submit-btn').disabled = false;
    $('submit-loader').hidden = true;
    $('submit-label').textContent = 'Se connecter';
    $('submit-btn').setAttribute('aria-busy', 'false');
  });
})();
