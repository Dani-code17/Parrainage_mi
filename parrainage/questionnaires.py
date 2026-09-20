"""Génération de questionnaires de démonstration cohérents.

Répondre au hasard produit des profils incohérents (quelqu'un qui répond 1 à
« je préfère un parrain strict » et 1 à « je veux de l'aide »). Ici, chaque
étudiant se voit attribuer un **profil de personnalité** parmi quelques
archétypes plausibles, puis on ajoute une légère variation individuelle.

Cela permet de tester le matching avec des données réalistes : les affinités
entre profils produisent de vrais écarts de score.

⚠️ Ces réponses sont des données de DÉMONSTRATION : elles ne remplacent pas
les vraies réponses des étudiants.
"""

import random

# Ordre des 15 questions (voir ReponseQuestionnaire) :
#  1 modèle de réussite   2 avouer ses lacunes    3 parrain strict
#  4 aider sur ses points forts                    5 bons plans de la fac
#  6 révisions en binôme                           7 café/discussion
#  8 activités de groupe                           9 maturité des L3
# 10 âge = atout                                  11 parler orientation
# 12 sorties (5) / jeux tranquilles (1)           13 défi farfelu
# 14 bibliothèque (1) / foyer (5)                 15 entraide = amitié

PROFILS = {
    # Studieux et scolaire : veut un cadre, travaille en bibliothèque.
    'studieux': [5, 4, 4, 5, 2, 5, 3, 2, 4, 3, 3, 2, 2, 1, 5],
    # Sociable et festif : la relation humaine avant les révisions.
    'sociable': [3, 3, 2, 4, 5, 4, 5, 5, 4, 5, 4, 5, 5, 5, 4],
    # Équilibré : un peu de tout, sans extrême.
    'equilibre': [4, 3, 3, 4, 4, 4, 4, 3, 4, 4, 4, 3, 4, 3, 4],
    # Autonome : cherche un appui ponctuel, pas un mentor strict.
    'autonome': [2, 3, 1, 4, 3, 3, 4, 3, 4, 4, 4, 4, 3, 3, 3],
    # Aventurier : ouvert à tout, aime les défis.
    'aventurier': [3, 4, 2, 5, 5, 4, 5, 4, 5, 5, 5, 5, 5, 4, 4],
    # Réservé : préfère un cadre calme et des échanges en petit comité.
    'reserve': [4, 2, 3, 3, 2, 3, 4, 2, 3, 2, 2, 1, 2, 2, 4],
    # Mentor dans l'âme : veut transmettre et accompagner.
    'mentor': [5, 5, 4, 5, 4, 5, 5, 3, 5, 4, 5, 3, 4, 3, 5],
    # Pragmatique : l'efficacité avant le relationnel.
    'pragmatique': [3, 4, 3, 4, 2, 5, 3, 2, 4, 3, 4, 3, 3, 2, 3],
}

# Répartition visée des profils (somme = 1.0).
_REPARTITION = {
    'studieux': 0.14, 'sociable': 0.15, 'equilibre': 0.20, 'autonome': 0.13,
    'aventurier': 0.11, 'reserve': 0.09, 'mentor': 0.10, 'pragmatique': 0.08,
}


def _choisir_profil(hasard):
    """Tire un profil selon la répartition visée."""
    seuil = hasard.random()
    cumul = 0.0
    for profil, poids in _REPARTITION.items():
        cumul += poids
        if seuil <= cumul:
            return profil
    return 'equilibre'


def generer_reponses(graine=None, profil=None):
    """Retourne une liste de 15 réponses (1-5) cohérentes.

    - `graine` : graine aléatoire (pour obtenir des réponses reproductibles).
    - `profil` : force un profil précis au lieu d'en tirer un.
    """
    hasard = random.Random(graine)
    nom_profil = profil if profil in PROFILS else _choisir_profil(hasard)
    base = PROFILS[nom_profil]

    reponses = []
    for valeur in base:
        # Bruit léger : -1, 0 ou +1, borné à [1, 5].
        bruit = hasard.choice((-1, 0, 0, 0, 1))
        reponses.append(max(1, min(5, valeur + bruit)))
    return reponses


def profil_de(reponses):
    """Retrouve le profil le plus proche d'un jeu de réponses (indicatif)."""
    if not reponses:
        return None
    meilleur, meilleure_distance = None, None
    for nom, base in PROFILS.items():
        distance = sum(abs(a - b) for a, b in zip(reponses, base))
        if meilleure_distance is None or distance < meilleure_distance:
            meilleur, meilleure_distance = nom, distance
    return meilleur
