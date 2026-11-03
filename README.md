# Parrainage MIAGE — L1 × L3

> Application Django de **matching de parrainage** entre étudiants de **L1** (filleuls) et de
> **L3** (parrains / marraines), fondée sur un questionnaire de compatibilité en 25 questions.
> *Développée pour le comité d'organisation de la Journée d'Intégration MIAGE.*

**🇫🇷 Français** · [🇬🇧 English](#-english)

---

## Le problème

Le parrainage d'une promo se fait d'habitude « au feeling » : listes croisées à la main,
affinités devinées, et des binômes qui ne se parlent jamais. Cette application remplace le
tableur par un **algorithme de compatibilité transparent**, un **parcours étudiant guidé** et
un **scénario de révélation** orchestré pour le jour de l'événement.

## Parcours

1. **L'équipe importe les listes** (`donnees/L1.csv`, `L3A.csv`, `L3B.csv`) et génère les
   identifiants.
2. Les étudiants **se connectent avec leur identifiant** et répondent au questionnaire —
   **une seule fois**, verrouillé à la soumission.
3. Le **matching** apparie chacun : **1 à 3 filleuls par L3**, sans laisser un L3 actif sans filleul.
4. Le jour J : la plateforme passe en **teasing** (indices), puis en **révélation** publique.

L'événement est piloté par une machine à états (`ParametreEvenement.Phase`) : *inscriptions
fermées → teasing → révélation*, avec possibilité de **forcer la révélation** manuellement.

## Fonctionnalités

| Module | Détail |
|---|---|
| **Import & identifiants** | Import CSV des promotions, génération automatique des identifiants et mots de passe, export CSV prêt à imprimer |
| **Questionnaire adaptatif** | 25 questions, 9 sections, 4 types de réponse (choix unique, choix multiple, note 0-10, texte libre). La **Q21 change de formulation selon le niveau** (attentes pour un L1 / apport pour un L3) |
| **Algorithme de matching** | Score `questionnaire (70 %) + bonus mixte (30 %)`, calculé sur **six sous-dimensions pondérées** (Personnalité, Études, Social, Communication, Valeurs, Centres d'intérêt), avec **similarité ou complémentarité** selon la question |
| **Souhaits de binôme** | Demandes étudiante validées par l'équipe, rendant le binôme prioritaire — **sans jamais trahir l'intervention** dans l'interface |
| **Anonymat garanti** | Le mot « forcé » n'apparaît dans aucun template utilisateur : un binôme prioritaire s'affiche simplement `100/100` |
| **Back-office** | Réponses consultables question par question, exports CSV (une colonne par question) ou fiches profil, gestion des demandes et de la phase de l'événement |
| **Mode démo** | Jeu de données fictif + commandes de simulation pour roder l'événement avant le jour J |

## Le questionnaire

| Type | Exemple | Compte dans le score |
|---|---|---|
| Choix unique | « Tu te décrirais comme… » | oui |
| Choix multiples | « Tes centres d'intérêt » | oui |
| Note de 0 à 10 | « Envie de créer un lien » | oui |
| Texte libre | Q21, Q23, Q25 | **non** |

- **Toutes les questions sont obligatoires** (le catalogue prévoit un champ `facultatif`
  pour en rendre une optionnelle plus tard).
- Les codes `q1`…`q25` sont **stables** : les réponses y sont rattachées, ne jamais les réordonner.
- Les réponses libres servent de **contexte humain** à l'équipe (Q21, Q23) ou de **message de
  bienvenue** remis au binôme à la révélation (Q25).

## L'algorithme de matching

- **Éligibilité** : seuls les étudiants ayant répondu au questionnaire participent.
- **Score** : `questionnaire (70 %)` + `bonus mixte (30 %)`, avec six sous-scores pondérés
  (les **Valeurs** pèsent le plus). Selon la question, l'algorithme cherche la **similarité**
  (valeurs, centres d'intérêt, rythme) ou la **complémentarité** (deux profils très réservés
  se relancent difficilement).
- **Robustesse** : une question sans réponse des deux côtés est **ignorée** — laisser une
  question facultative vide ne pénalise pas.
- **Capacité** : 1 à 3 filleuls par L3, plafond recalculé d'après l'effectif.
- **Souhait accepté** : score naturel `+1` à `+4` (plafonné à 97) pour passer devant sans
  afficher un 100/100 suspect.
- **Deal-breaker (Q15)** : filtre **désactivé par défaut**. La question demande ce que la
  personne *déteste*, pas ce qu'elle *est* : exclure sur cette base écarterait des gens qui
  sont en réalité d'accord entre eux.

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Django 5 (Python) |
| Interface | Templates Django + **django-crispy-forms** / crispy-bootstrap5 |
| Base de données | SQLite en local, **PostgreSQL** en production (`psycopg`) |
| Fichiers | Pillow (photos des participants) |
| Production | **Gunicorn** + **WhiteNoise** + `python-dotenv` |

## Installation

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
venv\Scripts\python.exe manage.py migrate
```

```bash
run.bat        # Windows
./run.sh       # Git Bash / Linux / macOS
```

> ⚠️ `python manage.py runserver` utilise le Python global, qui n'a pas forcément
> `crispy_forms` : utilisez les lanceurs `run.bat` / `run.sh`.

## Mise en route de l'événement

```bash
# 1. Importer les listes (donnees/L1.csv, L3A.csv, L3B.csv)
venv\Scripts\python.exe manage.py importer_etudiants

# 2. Récupérer les identifiants à distribuer
venv\Scripts\python.exe manage.py importer_etudiants --export identifiants.csv
```

`identifiants.csv` contient **nom, prénom, niveau, groupe, identifiant et mot de passe** —
c'est la liste à imprimer et distribuer.

| Commande | Rôle |
|---|---|
| `importer_etudiants` | Importe les listes et crée les comptes |
| `importer_etudiants --reset` | Repart de zéro |
| `importer_etudiants --export f.csv` | Exporte les identifiants |
| `importer_etudiants --mot-de-passe` | Régénère les mots de passe |
| `remplir_questionnaires` | Remplit les quiz (données de démonstration) |
| `demo` | Jeu de données fictif + tracé de la logique |
| `remettre_a_zero [--tout]` | Vide la base entre deux simulations / éditions |

## Côté administration (`/admin/`)

- **Étudiants** — liste, sexe à vérifier, actions : *Générer les identifiants manquants*,
  *Régénérer les mots de passe*, *Exporter les identifiants (CSV)*, *Importer une liste (CSV)*.
- **Réponses aux questionnaires** — les 25 réponses de chacun, recherche par identifiant,
  export CSV ou fiches profil détaillées.
- **Demandes** — accepter / refuser les souhaits de binôme.
- **Paramètre de l'événement** — basculer de phase : *Verrouillage*, *Teasing*,
  **FORCER LA RÉVÉLATION**.

## Tests

```bash
venv\Scripts\python.exe manage.py test parrainage
```

## Simuler puis mettre en ligne

- **[GUIDE_SIMULATION.md](GUIDE_SIMULATION.md)** — déroulé complet des 4 phases et points à vérifier.
- **[GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md)** — serveur (école, VPS, Oracle Cloud), PostgreSQL,
  Nginx, HTTPS et remise à zéro de la base à distance.

```bash
cp .env.example .env      # clé, domaine, DATABASE_URL
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --config gunicorn.conf.py
```

## Charte graphique

Toutes les couleurs sont centralisées en haut de `templates/base.html` :

```css
:root {
    --marine: #12305c;   /* bleu marine */
    --jaune:  #ffc72c;   /* jaune */
    --blanc:  #ffffff;
}
```

---

## 🇬🇧 English

**Parrainage MIAGE** is a Django application that **matches first-year students with
third-year mentors** using a 25-question compatibility survey.
*Built for the MIAGE Integration Day organising committee.*

- **CSV roster import** with automatic credential generation and a print-ready export.
- **Adaptive survey**: 25 questions across 9 sections and 4 answer types; one question is
  reworded depending on the student's year.
- **Matching algorithm**: `survey (70 %) + mixed-gender bonus (30 %)`, computed over six
  weighted dimensions (personality, academics, social, communication, values, interests),
  using **similarity or complementarity** per question. Each mentor takes 1–3 mentees, and
  no active mentor is left without one.
- **Pair requests** approved by the team boost a pair's score by +1 to +4 (capped at 97)
  without ever exposing the intervention: the UI only ever shows `100/100`.
- **Event state machine**: open → teasing → reveal, with a manual reveal override.
- **Admin exports** per question, plus detailed profile sheets for human arbitration.

**Stack:** Django 5 · crispy-forms · SQLite (dev) / PostgreSQL (prod) · Gunicorn + WhiteNoise.

```bash
python -m venv venv && venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe manage.py migrate
run.bat                       # or ./run.sh on Linux/macOS
venv\Scripts\python.exe manage.py test parrainage
```

**Author:** Yeo Daniel — [github.com/Dani-code17](https://github.com/Dani-code17)
