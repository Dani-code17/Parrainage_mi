"""Jeu de données fictif pour tester la logique du parrainage L1 x L3.

Rien ici n'est utilisé en production : ces profils servent uniquement à
alimenter l'application (via ``python manage.py demo``) afin d'exercer
réellement l'algorithme de matching : écarts de quiz, bonus mixte et
préférence de binôme.

Les réponses vont de 1 (« Pas du tout ») à 5 (« Totalement »), dans
l'ordre des 15 questions du questionnaire.
"""

# Mot de passe commun à tous les comptes fictifs (démo uniquement).
MOT_DE_PASSE = "demo12345"

_DOMAIN = "ecole.fr"

_ACCENTS = str.maketrans({
    'à': 'a', 'â': 'a', 'ä': 'a', 'á': 'a',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'î': 'i', 'ï': 'i', 'í': 'i',
    'ô': 'o', 'ö': 'o', 'ó': 'o',
    'ù': 'u', 'û': 'u', 'ü': 'u',
    'ç': 'c', 'œ': 'oe', 'æ': 'ae',
})


def slug(texte):
    """Minuscule sans accent ni espace, pour construire une adresse e-mail."""
    return (
        texte.lower()
        .translate(_ACCENTS)
        .replace(' ', '-')
        .replace("'", '')
    )


def email_de(prenom, nom):
    """Adresse e-mail fictive de la forme prenom.nom@ecole.fr."""
    return f"{slug(prenom)}.{slug(nom)}@{_DOMAIN}"


# (nom, prenom, sexe, niveau, [15 réponses])
#
# Les profils sont volontairement contrastés :
#   - des binômes naturellement très proches (score élevé sans intervention) ;
#   - des binômes éloignés sur le quiz ;
#   - des sexes identiques / différents pour activer ou non le bonus mixte.
ETUDIANTS = [
    # ---- L1 (parrainé·e·s) ----------------------------------------------
    ("Dubois",  "Léa",    "F", "L1", [5, 4, 3, 5, 4, 5, 5, 3, 5, 4, 5, 4, 4, 2, 5]),
    ("Benali",  "Karim",  "G", "L1", [3, 2, 2, 4, 5, 4, 5, 5, 4, 5, 3, 5, 5, 5, 4]),
    ("Martin",  "Chloé",  "F", "L1", [5, 5, 4, 4, 3, 5, 3, 2, 5, 3, 4, 2, 2, 1, 5]),
    ("Petit",   "Nathan", "G", "L1", [2, 3, 2, 3, 4, 3, 4, 4, 3, 5, 4, 5, 5, 4, 3]),
    ("Diallo",  "Aïcha",  "F", "L1", [4, 4, 3, 5, 4, 5, 4, 3, 5, 4, 5, 3, 3, 2, 5]),
    ("Roux",    "Lucas",  "G", "L1", [3, 4, 3, 3, 4, 3, 4, 4, 4, 4, 3, 4, 4, 3, 3]),

    # ---- L3 (parrain·e·s / marrain·e·s) ---------------------------------
    ("Girard",  "Thomas", "G", "L3", [5, 3, 3, 5, 4, 5, 4, 3, 5, 4, 4, 4, 4, 2, 5]),
    ("Fontaine", "Inès",  "F", "L3", [3, 2, 2, 4, 5, 4, 5, 5, 4, 5, 3, 5, 5, 5, 3]),
    ("Lemoine", "Sarah",  "F", "L3", [5, 5, 4, 4, 3, 5, 3, 3, 5, 3, 4, 2, 2, 1, 5]),
    ("Moreau",  "Hugo",   "G", "L3", [3, 3, 2, 4, 3, 3, 5, 5, 4, 4, 3, 5, 5, 4, 3]),
    ("Blanc",   "Emma",   "F", "L3", [4, 4, 3, 5, 4, 5, 4, 3, 5, 4, 5, 3, 3, 2, 4]),
]

# Étudiant suivi dans le tracé par défaut.
L1_TRACE = email_de("Léa", "Dubois")
L3_TRACE = email_de("Hugo", "Moreau")

# Préférence de binôme exprimée par un L3 vers un L1 (démo).
# Elle est créée « en attente » : seul le panneau d'administration peut
# l'accepter. Une fois acceptée, le binôme est prioritaire.
PREFERENCE_L3 = email_de("Hugo", "Moreau")
PREFERENCE_L1 = email_de("Léa", "Dubois")
