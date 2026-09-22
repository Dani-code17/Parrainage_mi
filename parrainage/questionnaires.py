"""Génération de questionnaires de démonstration cohérents (25 questions).

Répondre au hasard produit des profils incohérents (quelqu'un qui se dit
« très introverti » et qui sort « dès qu'il y a un truc »). Ici, chaque
étudiant reçoit un **archétype** plausible, puis une légère variation
individuelle est appliquée.

⚠️ Ces réponses sont des données de DÉMONSTRATION : elles ne remplacent pas
les vraies réponses des étudiants.
"""

import random

# ---------------------------------------------------------------------
#  Archétypes
#
#  Pour chaque code de question :
#    - question à choix unique  -> l'indice de l'option (0 = première)
#    - question à choix multiple -> la liste des indices cochés
#    - note 0-10                -> la valeur
#    - question libre           -> un texte d'exemple
# ---------------------------------------------------------------------

_ARCHETYPES = {
    # Étudie sérieusement, structuré, plutôt réservé.
    'studieux': {
        'q1': 1, 'q2': 1, 'q3': 0, 'q4': 0, 'q5': 1, 'q6': 1, 'q7': 0,
        'q8': 0, 'q9': 1, 'q10': 0, 'q11': 0, 'q12': 0, 'q13': 2,
        'q14': [0, 1, 8], 'q15': 0, 'q16': 2, 'q17': 1, 'q18': 4,
        'q19': [1, 4, 5, 12], 'q20': 0, 'q22': 1, 'q24': 8,
        'q21': "J'aimerais être guidé sur la méthode de travail et la "
               "préparation des partiels.",
        'q23': "Quelqu'un de sérieux et fiable. Mon deal-breaker : le "
               "mensonge.",
        'q25': "Hâte de te rencontrer, j'ai plein de questions sur la L3 !",
    },
    # Très sociable, sort beaucoup, énergie communicative.
    'sociable': {
        'q1': 4, 'q2': 2, 'q3': 5, 'q4': 3, 'q5': 0, 'q6': 0, 'q7': 0,
        'q8': 4, 'q9': 3, 'q10': 2, 'q11': 2, 'q12': 0, 'q13': 2,
        'q14': [0, 10, 6], 'q15': 1, 'q16': 0, 'q17': 0, 'q18': 0,
        'q19': [0, 1, 7, 14, 15], 'q20': 2, 'q22': 3, 'q24': 10,
        'q21': "Je veux quelqu'un avec qui sortir et rigoler, mais aussi "
               "qui me tire vers le haut.",
        'q23': "Quelqu'un de vivant et ouvert. Deal-breaker : les gens "
               "possessifs.",
        'q25': "On va bien s'entendre, je le sens déjà 😄",
    },
    # Équilibré, s'adapte à tout.
    'equilibre': {
        'q1': 2, 'q2': 0, 'q3': 5, 'q4': 1, 'q5': 5, 'q6': 1, 'q7': 1,
        'q8': 1, 'q9': 2, 'q10': 1, 'q11': 0, 'q12': 3, 'q13': 3,
        'q14': [1, 6, 8], 'q15': 5, 'q16': 1, 'q17': 0, 'q18': 2,
        'q19': [1, 2, 5, 9], 'q20': 3, 'q22': 5, 'q24': 7,
        'q21': "Un peu de tout : des conseils, de la bonne humeur et des "
               "moments simples.",
        'q23': "Quelqu'un de respectueux et drôle. Deal-breaker : "
               "l'irrespect.",
        'q25': "À très vite, on va bien s'entendre !",
    },
    # Réservé, préfère les échanges en petit comité.
    'reserve': {
        'q1': 0, 'q2': 0, 'q3': 4, 'q4': 1, 'q5': 0, 'q6': 3, 'q7': 3,
        'q8': 0, 'q9': 0, 'q10': 0, 'q11': 0, 'q12': 0, 'q13': 3,
        'q14': [0, 3, 8], 'q15': 1, 'q16': 3, 'q17': 2, 'q18': 5,
        'q19': [4, 5, 13], 'q20': 1, 'q22': 4, 'q24': 5,
        'q21': "J'espère surtout une présence bienveillante et de la "
               "patience, sans pression.",
        'q23': "Quelqu'un de calme et sincère. Deal-breaker : les critiques "
               "constantes.",
        'q25': "Je suis timide, mais j'ai vraiment envie que ça marche.",
    },
    # Aventurier, ouvert à tout, aime les défis.
    'aventurier': {
        'q1': 3, 'q2': 2, 'q3': 3, 'q4': 2, 'q5': 3, 'q6': 1, 'q7': 0,
        'q8': 2, 'q9': 3, 'q10': 2, 'q11': 1, 'q12': 3, 'q13': 2,
        'q14': [2, 5, 9], 'q15': 3, 'q16': 0, 'q17': 3, 'q18': 1,
        'q19': [0, 7, 9, 15], 'q20': 2, 'q22': 2, 'q24': 9,
        'q21': "Quelqu'un qui me fasse découvrir des choses et me pousse "
               "hors de ma zone de confort.",
        'q23': "Quelqu'un d'ambitieux et libre. Deal-breaker : le manque "
               "d'ambition.",
        'q25': "Prêt(e) pour l'aventure, let's go 🚀",
    },
    # Mentor dans l'âme (surtout côté L3).
    'mentor': {
        'q1': 3, 'q2': 1, 'q3': 5, 'q4': 1, 'q5': 0, 'q6': 1, 'q7': 0,
        'q8': 1, 'q9': 2, 'q10': 0, 'q11': 0, 'q12': 0, 'q13': 2,
        'q14': [0, 1, 6], 'q15': 0, 'q16': 2, 'q17': 0, 'q18': 1,
        'q19': [1, 5, 8, 11], 'q20': 0, 'q22': 1, 'q24': 9,
        'q21': "Je veux transmettre ce que j'ai appris et éviter à mon "
               "filleul les erreurs que j'ai faites.",
        'q23': "Quelqu'un de curieux et respectueux. Deal-breaker : le "
               "manque de loyauté.",
        'q25': "Compte sur moi, je serai là quand ça comptera.",
    },
}

# Répartition visée des archétypes (somme = 1.0).
_REPARTITION = {
    'studieux': 0.18, 'sociable': 0.17, 'equilibre': 0.24,
    'reserve': 0.13, 'aventurier': 0.14, 'mentor': 0.14,
}


def _choisir_profil(hasard):
    seuil = hasard.random()
    cumul = 0.0
    for profil, poids in _REPARTITION.items():
        cumul += poids
        if seuil <= cumul:
            return profil
    return 'equilibre'


def generer_avec_profil(graine, niveau=None):
    """Retourne ``(reponses, profil)`` pour la graine donnée.

    ``reponses`` est un dictionnaire ``code -> valeur`` directement
    compatible avec le champ ``donnees`` de ``ReponseQuestionnaire``.
    """
    from parrainage.questions import QUESTIONS

    hasard = random.Random(graine)
    profil = _choisir_profil(hasard)
    base = _ARCHETYPES[profil]

    reponses = {}
    for question in QUESTIONS:
        if question.condition and niveau and question.condition != niveau:
            continue

        valeur = base.get(question.code)
        if valeur is None:
            continue

        if question.type == 'multi':
            # On garde les choix de l'archétype, avec parfois un léger écart.
            choisis = list(valeur)
            if hasard.random() < 0.35 and len(question.options) > 3:
                ajout = hasard.randrange(len(question.options))
                if str(ajout) not in [str(x) for x in choisis]:
                    choisis.append(ajout)
            if question.max_choix:
                choisis = choisis[:question.max_choix]
            reponses[question.code] = [str(x) for x in sorted(set(choisis))]

        elif question.type == 'echelle':
            ecart = hasard.choice([-1, 0, 0, 0, 1])
            reponses[question.code] = max(0, min(10, int(valeur) + ecart))

        elif question.type == 'choix':
            indice = int(valeur)
            # Variation : deux étudiants du même archétype ne répondent pas
            # exactement pareil.
            if hasard.random() < 0.30:
                indice += hasard.choice([-1, 1])
            indice = max(0, min(len(question.options) - 1, indice))
            reponses[question.code] = str(indice)

        else:  # texte
            reponses[question.code] = valeur

    return reponses, profil


def generer_reponses(graine, niveau=None):
    """Comme :func:`generer_avec_profil`, sans le nom du profil."""
    reponses, _ = generer_avec_profil(graine, niveau)
    return reponses
