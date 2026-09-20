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
- **Réponses aux questionnaires** — voir les 15 réponses de chacun,
  rechercher par identifiant, **exporter en CSV**.
- **Demandes** — accepter ou refuser les souhaits de binôme.
  La colonne « Forcé » n'existe **que** dans cet écran.
- **Paramètre de l'événement** — changer de phase :
  *Verrouillage*, *Teasing*, **FORCER LA RÉVÉLATION**.

## Le matching

- **Éligibilité** : seuls les étudiants ayant répondu au questionnaire
  participent. Pas de réponse, pas de binôme.
- **Score** : `quiz (70 %)` + `bonus mixte (30 %)`.
  `score_quiz = (1 - écart_moyen / 4) × 70`. Le bonus mixte s'applique quand
  les sexes diffèrent.
- **Capacité** : chaque L3 encadre **de 1 à 3 filleuls**. Le plafond est
  calculé automatiquement d'après le nombre d'étudiants, et l'algorithme
  garantit qu'aucun L3 actif ne reste sans filleul.
- **Souhaits** : un souhait accepté par l'équipe rend le binôme prioritaire.
  Il s'affiche alors **100/100**, sans aucune mention de priorité.

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
