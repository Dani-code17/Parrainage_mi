# Parrainage MIAGE — L1 × L3 · Landing + Connexion

Nouveau design du site https://parrainage-mi.abrdns.com/ (édition 2026-2027).

## Contenu du dossier

```
parrainage-miage/
├── index.html                  ← Landing page (version HTML autonome)
├── connexion.html              ← Page de connexion (version HTML autonome)
├── assets/
│   ├── css/style.css           ← Styles communs aux deux pages
│   └── js/
│       ├── common.js           ← Compte à rebours + détection « mouvement réduit »
│       ├── landing.js          ← Intro cinématique, hero 3D, mini-jeu du match
│       └── connexion.js        ← Validation, œil mot de passe, Verr. Maj, chargement
├── django/
│   ├── templates/parrainage/
│   │   ├── accueil.html        ← Landing en template Django ({% static %})
│   │   └── connexion.html      ← Connexion en template Django ({% csrf_token %}, form.errors)
│   └── exemple_urls.py         ← Exemple de branchement des URLs (LoginView)
└── sources-canvas/             ← Fichiers sources du canvas Claude (.dc.html)
```

## Tester en local

Ouvre `index.html` dans ton navigateur (double-clic), ou lance un petit serveur :

```bash
cd parrainage-miage
python3 -m http.server 8000
# puis http://localhost:8000
```

Sur `connexion.html`, ajoute `?erreur=1` à l'URL pour voir le bandeau d'erreur.

## Ce qu'il faut personnaliser

| Quoi | Où |
|---|---|
| **Date de clôture** (compte à rebours) | attribut `data-deadline="2026-10-31T23:59:00"` dans `index.html` **et** `connexion.html` (et les templates Django) |
| **Date de la révélation** | texte `[DATE DE LA RÉVÉLATION]` dans la FAQ de `index.html` |
| **Questions du mini-jeu, archétypes, textes** | tout en haut de `assets/js/landing.js` (`QUESTIONS`, `PROFIL`, `STYLE`, `DESCRIPTIONS`, `L3_IDEAL`) |
| **Logo** | le symbole SVG à deux cercles dans la barre de navigation : remplace-le par `<img src="…/logo.png">` si tu veux ton logo |
| **Couleurs** | variables en haut de `assets/css/style.css` (`--amber`, `--blue`, `--navy`, …) |

## Intégration dans le vrai site (Django)

Ton site actuel semble tourner sous Django (`/connexion/`). Pour brancher le nouveau design :

1. Copie `django/templates/parrainage/` dans le dossier `templates` de ton app.
2. Copie `assets/css` et `assets/js` dans `<ton_app>/static/parrainage/`.
3. Branche les URLs comme dans `django/exemple_urls.py`, ou garde tes vues et change juste leur `template_name`.

Points à vérifier :

- Les champs du formulaire s'appellent **`username`** et **`password`**, les noms attendus par la `LoginView` de Django. Si ta vue utilise d'autres noms, renomme les attributs `name="…"`.
- Le `{% csrf_token %}` est déjà dans le template de connexion : ne le retire pas.
- Le bandeau rouge « Identifiant ou mot de passe incorrect » s'affiche quand `form.errors` existe.
- Les liens pointent vers `/` et `/connexion/`. Adapte-les si tes URLs sont différentes.

Si ton site n'est pas en Django, utilise `index.html` et `connexion.html` directement. Il suffit de régler l'attribut `action` du formulaire vers l'URL qui traite la connexion, et d'afficher `#server-error` (en retirant l'attribut `hidden`) en cas d'échec.

## Accessibilité & performances

- Aucun framework, aucune bibliothèque : seulement les polices Google Fonts (Unbounded, Manrope, JetBrains Mono).
- Contraste de 4,5:1 minimum, zones cliquables d'au moins 44 px, focus clavier visible, libellés de formulaire toujours visibles.
- Si l'appareil demande « moins d'animations », l'intro, les confettis, l'inclinaison 3D et les animations sont désactivés.
- L'intro ne se joue qu'une fois par session et peut être passée (bouton ou touche Échap).
- Le mini-jeu est **purement ludique** : le % de compatibilité ne mesure rien et n'influence pas le vrai match (c'est indiqué sur la page et dans la FAQ).

## Dossier `sources-canvas/`

Ce sont les fichiers du canvas de design dans Claude (format `.dc.html`). Ils ne fonctionnent pas seuls sur un serveur : ils servent de référence ou pour continuer à modifier le design dans le canvas. Pour le site, utilise les versions HTML ou Django ci-dessus.
