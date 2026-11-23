/* =========================================================
   Parrainage MIAGE — Landing (intro, hero 3D, mini-jeu)
   Vanilla JS, aucune dépendance.
   ========================================================= */
(function () {
  'use strict';

  var PM = window.PM;
  var reduce = PM.reduceMotion;
  var $ = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };

  /* ---------------------------------------------------------
     1. CONTENU DU MINI-JEU — modifie librement ces textes
     --------------------------------------------------------- */
  var QUESTIONS = [
    {
      label: 'Ton réflexe quand un devoir tombe demain ?',
      options: [
        'MIAGE C’EST FAMILLE (donc je compte sur ma famille)',
        'Chacun pour soi Dieu pour tous',
        'C’est dernier étudiant qui fait minute'
      ]
    },
    {
      label: 'Ton coin préféré pour graille ?',
      options: [
        'Chez Edmond',
        'Chez Adjara panini',
        'Autres'
      ]
    },
    {
      label: 'Tu as cours à 8h, tu quittes la maison il est 7h30, tu fais quoi ?',
      options: [
        'Le retard c’est mon champ',
        'WOUUU attends je vais aller vite faut pas ils vont fermer portail sur moi',
        'C’est quoi qui est cours là ???'
      ]
    }
  ];
  // Archétype = PROFIL[réponse Q1] + STYLE[réponse Q3]
  var PROFIL = ['Solidaire', 'Franc-tireur', 'Dernière minute'];
  var STYLE = ['toujours en retard', 'toujours pressé·e', 'toujours à l’ouest'];
  var DESCRIPTIONS = [
    'Tu comptes sur les autres, et les autres comptent sur toi. Ton QG : ',
    'Tu avances seul·e, à ta façon. Ton QG : ',
    'Tu repousses tout au dernier moment… et ça passe quand même. Ton QG : '
  ];
  var L3_IDEAL = [
    'un·e L3 qui te présente la promo et te file un coup de main.',
    'un·e L3 qui te laisse ton espace, mais répond quand tu bloques.',
    'un·e L3 qui t’aide à anticiper… au moins un peu.'
  ];
  var VERDICTS = ['DUO EXPLOSIF', 'BINÔME DE LÉGENDE', 'COMPATIBILITÉ REDOUTABLE'];
  var SCAN_TEXTS = ['Lecture de tes réponses…', 'Recherche des affinités L1 × L3…', 'Calcul de la compatibilité…', 'Impression de ta carte…'];

  /* ---------------------------------------------------------
     2. INTRO CINÉMATIQUE (≈ 3 s, passable)
     --------------------------------------------------------- */
  var intro = $('#intro');
  if (intro) {
    // L'intro ne se joue qu'une fois par session et jamais en mouvement réduit
    var seen = false;
    try { seen = sessionStorage.getItem('pm-intro') === '1'; } catch (e) {}
    if (!reduce && !seen) {
      intro.style.display = 'flex';
      var closeIntro = function () { intro.style.display = 'none'; clearTimeout(introTimer); };
      var introTimer = setTimeout(closeIntro, 3400);
      $('#skip-intro').addEventListener('click', closeIntro);
      document.addEventListener('keydown', function onEsc(e) {
        if (e.key === 'Escape') { closeIntro(); document.removeEventListener('keydown', onEsc); }
      });
      try { sessionStorage.setItem('pm-intro', '1'); } catch (e) {}
    }
  }

  /* ---------------------------------------------------------
     3. COMPTE À REBOURS
     --------------------------------------------------------- */
  PM.countdown($('#countdown'));

  /* ---------------------------------------------------------
     4. HERO RÉACTIF À LA SOURIS (halo + carte 3D)
     --------------------------------------------------------- */
  var hero = $('#hero');
  if (hero && !reduce) {
    var raf = null;
    hero.addEventListener('pointermove', function (e) {
      var r = hero.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () {
        hero.style.setProperty('--sx', (x * 100).toFixed(1) + '%');
        hero.style.setProperty('--sy', (y * 100).toFixed(1) + '%');
        hero.style.setProperty('--tx', ((0.5 - y) * 18).toFixed(2) + 'deg');
        hero.style.setProperty('--ty', ((x - 0.5) * 22).toFixed(2) + 'deg');
      });
    });
    hero.addEventListener('pointerleave', function () {
      hero.style.setProperty('--sx', '50%'); hero.style.setProperty('--sy', '40%');
      hero.style.setProperty('--tx', '0deg'); hero.style.setProperty('--ty', '0deg');
    });
  }

  /* ---------------------------------------------------------
     5. MINI-JEU DU MATCH
     --------------------------------------------------------- */
  var answers = [null, null, null];
  var phases = { quiz: $('#phase-quiz'), scan: $('#phase-scan'), done: $('#phase-done') };
  var qWrap = $('#quiz-questions');
  var goBtn = $('#go-btn'), goHint = $('#go-hint');
  var scanTick = null, scanEnd = null, copyT = null;

  function setPhase(name) {
    Object.keys(phases).forEach(function (k) { phases[k].hidden = k !== name; });
  }

  // Construction des questions
  QUESTIONS.forEach(function (q, qi) {
    var fs = document.createElement('fieldset');
    fs.style.cssText = 'margin:0;padding:0;border:0;display:flex;flex-direction:column;gap:14px';
    var lg = document.createElement('legend');
    lg.style.cssText = 'padding:0;margin-bottom:14px;font-family:var(--font-display);font-weight:700;font-size:clamp(18px,2vw,22px)';
    lg.innerHTML = '<span style="color:#5B9BFF;font-family:var(--font-mono);font-size:15px;margin-right:10px">0' + (qi + 1) + '</span>';
    lg.appendChild(document.createTextNode(q.label));
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px';
    q.options.forEach(function (opt, oi) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'px-chip';
      b.textContent = opt;
      b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', function () {
        answers[qi] = oi;
        $$('.px-chip', row).forEach(function (c, ci) { c.setAttribute('aria-pressed', ci === oi ? 'true' : 'false'); });
        updateProgress();
      });
      row.appendChild(b);
    });
    fs.appendChild(lg); fs.appendChild(row);
    qWrap.appendChild(fs);
  });

  function answeredCount() { return answers.filter(function (a) { return a !== null; }).length; }

  function updateProgress() {
    var n = answeredCount();
    $('#quiz-progress').setAttribute('aria-valuenow', n);
    $('#quiz-progress-bar').style.width = Math.round(n / 3 * 100) + '%';
    $('#quiz-count').textContent = n + '/3';
    goBtn.disabled = n < 3;
    goHint.textContent = n < 3 ? 'Réponds aux 3 questions pour lancer le match.' : 'Prêt·e ? C’est parti.';
  }

  function computeResult() {
    var a0 = answers[0], a1 = answers[1], a2 = answers[2];
    var sum = a0 + a1 + a2;
    return {
      score: 86 + ((sum * 5 + a0 * 3 + 7) % 13),
      verdict: VERDICTS[sum % 3],
      archetype: PROFIL[a0] + ' ' + STYLE[a2],
      desc: DESCRIPTIONS[a0] + QUESTIONS[1].options[a1].toLowerCase() + '.',
      ideal: L3_IDEAL[a0],
      cardNo: String(1000 + ((a0 * 9 + a1 * 3 + a2) * 37 + 211) % 9000).slice(-4),
      tags: answers.map(function (a, i) { return QUESTIONS[i].options[a]; })
    };
  }

  var result = null;

  function showResult() {
    result = computeResult();
    $$('[data-r="archetype"]').forEach(function (el) { el.textContent = result.archetype; });
    $('[data-r="score"]').textContent = result.score;
    $('[data-r="verdict"]').textContent = result.verdict;
    $('[data-r="desc"]').textContent = result.desc;
    $('[data-r="ideal"]').textContent = result.ideal;
    $('#card-no').textContent = result.cardNo;
    var tags = $('#card-tags'); tags.innerHTML = '';
    result.tags.forEach(function (t) {
      var s = document.createElement('span');
      s.style.cssText = 'padding:2px 10px;border-radius:999px;background:rgba(255,255,255,0.12);font-size:12px;font-weight:700;white-space:nowrap';
      s.textContent = t; tags.appendChild(s);
    });
    // relance l'animation d'apparition de la carte
    var card = $('#holo-wrap');
    card.classList.remove('a-pop'); void card.offsetWidth; card.classList.add('a-pop');
    setPhase('done');
    launchConfetti();
  }

  function launchConfetti() {
    var box = $('#confetti'); box.innerHTML = '';
    if (reduce) return;
    var colors = ['#FFB547', '#5B9BFF', '#FFFFFF', '#FFCF85', '#9CC2FF'];
    for (var i = 0; i < 36; i++) {
      var w = 6 + Math.round(Math.random() * 8);
      var c = document.createElement('span');
      c.className = 'cf';
      c.style.left = (Math.random() * 100).toFixed(1) + '%';
      c.style.width = w + 'px';
      c.style.height = (Math.random() > 0.5 ? w : Math.round(w * 2.2)) + 'px';
      c.style.borderRadius = Math.random() > 0.6 ? '50%' : '2px';
      c.style.background = colors[i % colors.length];
      c.style.animationDelay = (Math.random() * 0.6).toFixed(2) + 's';
      c.style.animationDuration = (1.8 + Math.random() * 1.6).toFixed(2) + 's';
      box.appendChild(c);
    }
  }

  goBtn.addEventListener('click', function () {
    if (answeredCount() < 3) return;
    var step = 0;
    $('#scan-text').textContent = SCAN_TEXTS[0];
    var bar = $('#scan-bar'); bar.classList.remove('a-bar'); void bar.offsetWidth; bar.classList.add('a-bar');
    setPhase('scan');
    clearInterval(scanTick);
    scanTick = setInterval(function () {
      step = Math.min(step + 1, SCAN_TEXTS.length - 1);
      var msg = $('#scan-msg');
      $('#scan-text').textContent = SCAN_TEXTS[step];
      msg.classList.remove('scan-txt'); void msg.offsetWidth; msg.classList.add('scan-txt');
    }, 650);
    scanEnd = setTimeout(function () { clearInterval(scanTick); showResult(); }, reduce ? 300 : 2700);
  });

  $('#reset-btn').addEventListener('click', function () {
    clearTimeout(scanEnd); clearInterval(scanTick);
    answers = [null, null, null];
    $$('.px-chip', qWrap).forEach(function (c) { c.setAttribute('aria-pressed', 'false'); });
    updateProgress();
    $('#share-label').textContent = 'Copier mon résultat';
    setPhase('quiz');
    var first = $('.px-chip', qWrap); if (first) first.focus();
  });

  // Carte holographique qui suit la souris
  var holo = $('#holo-card');
  if (holo && !reduce) {
    var hraf = null;
    holo.addEventListener('pointermove', function (e) {
      var r = holo.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      cancelAnimationFrame(hraf);
      hraf = requestAnimationFrame(function () {
        holo.style.setProperty('--ha', Math.round(x * 360) + 'deg');
        holo.style.setProperty('--ctx', ((0.5 - y) * 22).toFixed(2) + 'deg');
        holo.style.setProperty('--cty', ((x - 0.5) * 26).toFixed(2) + 'deg');
      });
    });
    holo.addEventListener('pointerleave', function () {
      holo.style.setProperty('--ha', '180deg');
      holo.style.setProperty('--ctx', '0deg');
      holo.style.setProperty('--cty', '0deg');
    });
  }

  // Partage du résultat
  $('#share-btn').addEventListener('click', function () {
    if (!result) return;
    var txt = 'Je suis ' + result.archetype + ' (' + result.score + '% de compatibilité) au jeu du Parrainage MIAGE L1 × L3 ! Et toi ?';
    var label = $('#share-label');
    var done = function (msg) {
      label.textContent = msg;
      clearTimeout(copyT);
      copyT = setTimeout(function () { label.textContent = 'Copier mon résultat'; }, 2500);
    };
    if (navigator.share && /Mobi|Android/i.test(navigator.userAgent)) {
      navigator.share({ text: txt, url: location.href }).catch(function () {});
      return;
    }
    try {
      navigator.clipboard.writeText(txt).then(function () { done('Copié !'); }, function () { done('Copie impossible'); });
    } catch (e) { done('Copie impossible'); }
  });

  updateProgress();
})();
