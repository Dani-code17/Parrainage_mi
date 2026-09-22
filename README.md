# Parrainage MIAGE — L1 × L3

Application Django qui met en relation les étudiants de **L1** (filleuls) avec
leurs aînés de **L3** (parrains / marraines), à partir d'un questionnaire de
compatibilité.

## Fonctionnement en bref

1. **L'équipe importe les listes** d'étudiants et **génère les identifiants**.
2. Les étudiants **se connectent avec leur identifiant** et répondent au
   questionnaire — **une seule fois**.
3. Le **matching** apparie chacun : 1 à 3 filleuls par L3.
4. Le jour J : **indices** de teasing, puis **révélation** publique.

## Installation

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
venv\Scripts\python.exe manage.py migrate
```

Pour lancer le serveur, utilisez le lanceur (il pointe toujours vers le bon
Python) :

```bash
run.bat        # Windows
./run.sh       # Git Bash / Linux / macOS
```

> ⚠️ `python manage.py runserver` utilise le Python global, qui n'a pas
> forcément `crispy_forms` : l'application planterait au démarrage.

## Mise en route de l'événement

```bash
# 1. Importer les listes (donnees/L1.csv, L3A.csv, L3B.csv)
venv\Scripts\python.exe manage.py importer_etudiants

# 2. Récupérer les identifiants à distribuer
venv\Scripts\python.exe manage.py importer_etudiants --export identifiants.csv
```

Le fichier `identifiants.csv` contient **nom, prénom, niveau, groupe, identifiant
et mot de passe** — c'est la liste à imprimer et distribuer.

### Commandes disponibles

| Commande | Rôle |
|---|---|
| `importer_etudiants` | Importe les listes et crée les comptes |
| `importer_etudiants --reset` | Repart de zéro |
| `importer_etudiants --export f.csv` | Exporte les identifiants |
| `importer_etudiants --mot-de-passe` | Régénère les mots de passe |
| `remplir_questionnaires` | Remplit les quiz (données de démonstration) |
| `demo` | Jeu de données fictif + tracé de la logique |

## Côté administration

Dans `/admin/` :

- **Étudiants** — liste, sexe à vérifier, actions :
  *Générer les identifiants manquants*, *Régénérer les mots de passe*,
  *Exporter les identifiants (CSV)*, *Importer une liste d'étudiants (CSV)*.
- **Réponses aux questionnaires** — voir les 25 réponses de chacun,
  rechercher par identifiant, **exporter en CSV** (une colonne par question)
  ou en **fiches profil détaillées** (question + réponse en clair, idéal pour
  arbitrer à la main).
- **Demandes** — accepter ou refuser les souhaits de binôme.
  La colonne « Forcé » n'existe **que** dans cet écran.
- **Paramètre de l'événement** — changer de phase :
  *Verrouillage*, *Teasing*, **FORCER LA RÉVÉLATION**.

## Le questionnaire

**25 questions** réparties en 9 sections (toi en vrai, études, communication,
sorties, valeurs, piment, questions qui révèlent, lifestyle, matching final),
avec quatre types de réponse :

| Type | Exemple | Compte dans le score |
|---|---|---|
| Choix unique | « Tu te décrirais comme… » | oui |
| Choix multiples | « Tes centres d'intérêt » | oui |
| Note de 0 à 10 | « Envie de créer un lien » | oui |
| Texte libre | Q21, Q23, Q25 | **non** |

- **Toutes les questions sont obligatoires** : il faut répondre aux 25 pour
  pouvoir valider. Le catalogue prévoit un champ `facultatif` si l'équipe
  souhaite en rendre une passable plus tard.
- **La question 21 s'adapte au niveau** : un L1 lit « ce que tu attends de ton
  parrain », un L3 lit « ce que tu peux apporter à ton filleul ». Chacun ne
  voit qu'une seule version.
- Le catalogue fait foi dans `parrainage/questions.py`. Les codes (`q1`…`q25`)
  sont **stables** : ne jamais les réordonner, les réponses y sont rattachées.

## Le matching

- **Éligibilité** : seuls les étudiants ayant répondu au questionnaire
  participent. Pas de réponse, pas de binôme.
- **Score** : `questionnaire (70 %)` + `bonus mixte (30 %)`.
  - Le questionnaire est noté par **six sous-scores** : Personnalité, Études,
    Social, Communication, Valeurs, Centres d'intérêt. Chaque dimension est
    pondérée (les Valeurs pèsent le plus).
  - Selon la question, on cherche la **similarité** (valeurs, centres
    d'intérêt, rythme) ou la **complémentarité** (deux profils très réservés
    se relancent difficilement).
  - Une question sans réponse des deux côtés est **ignorée** : laisser une
    question facultative vide ne pénalise pas.
  - Le bonus mixte s'applique quand les sexes diffèrent.
- **Réponses libres** : elles ne sont jamais notées.
  - **Q21** (attentes / apport) et **Q23** (binôme idéal + deal-breaker)
    servent de contexte à l'équipe, affiché dans l'admin.
  - **Q25** est remise au binôme à la révélation, comme message de bienvenue.
- **Capacité** : chaque L3 encadre **de 1 à 3 filleuls**. Le plafond est
  calculé automatiquement d'après le nombre d'étudiants, et l'algorithme
  garantit qu'aucun L3 actif ne reste sans filleul.
- **Souhaits** : un souhait accepté par l'équipe rend le binôme prioritaire.
  Il reçoit alors **son score naturel +1 à +4** (plafonné à 97), pour passer
  devant sans afficher un 100/100 qui trahirait une intervention.

> ⚙️ **Filtre deal-breaker** : désactivé par défaut
> (`EXCLUSION_DEALBREAKER` dans `matching.py`). La Q15 demande ce que la
> personne **déteste**, pas ce qu'elle **est** : exclure sur cette base
> écarterait des gens qui sont d'accord entre eux.

## Anonymat

Le mot « forcé » (et ses variantes) **n'apparaît dans aucun template
utilisateur**. Un binôme prioritaire est indistinguable d'un excellent match
naturel : il affiche simplement `100/100`.

## Charte graphique

Toutes les couleurs sont centralisées en haut de `templates/base.html` :

```css
:root {
    --marine: #12305c;   /* bleu marine */
    --jaune:  #ffc72c;   /* jaune */
    --blanc:  #ffffff;
}
```

Modifier ces trois valeurs suffit à rechanger toute l'interface.

## Tests

```bash
venv\Scripts\python.exe manage.py test parrainage
```


## 🎬 Simuler l'événement

Un guide pas-à-pas complet est disponible dans **[GUIDE_SIMULATION.md](GUIDE_SIMULATION.md)** :
déroulé des 4 phases, points à vérifier, et commandes pour enchaîner les tests.

```bash
run.bat                                        # démarrer
venv\Scripts\python.exe manage.py remettre_a_zero   # base propre entre deux simulations
```

## 🚀 Mettre en ligne

Le guide **[GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md)** couvre l'installation
sur un serveur (école, VPS, Oracle Cloud), PostgreSQL, Nginx, HTTPS, ainsi
que **la remise à zéro de la base à distance**.

L'essentiel :

```bash
cp .env.example .env      # puis renseigner la clé, le domaine et DATABASE_URL
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --config gunicorn.conf.py
```

En ligne, la remise à zéro se fait par la même commande, via SSH :

```bash
python manage.py remettre_a_zero          # garde les étudiants et leurs identifiants
python manage.py remettre_a_zero --tout   # supprime aussi les étudiants
```
