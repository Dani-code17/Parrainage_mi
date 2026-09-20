"""Algorithme de matching L1-L3 pour l'événement de parrainage.

Règles
------
1. **Éligibilité** : seuls les étudiants ayant rempli leur questionnaire
   participent. Un L1 sans questionnaire n'a pas de parrain ; un L3 sans
   questionnaire n'a pas de filleul.
2. **Priorité** : un binôme décidé par l'équipe est servi en premier et
   reçoit un score légèrement supérieur à son score naturel (voir
   ``_score_prioritaire``), de façon à rester crédible à l'affichage.
3. **Score** : ``score_quiz`` (70 %) + ``bonus_mixte`` (30 %).
4. **Capacité** : chaque L3 encadre entre 1 et 3 filleuls. Le nombre maximal
   est calculé pour que tous les L1 éligibles puissent être placés.

⚠️ Le score interne n'est jamais montré tel quel : il est converti en 100/100
à l'affichage, sans aucune mention de priorité.
"""

import math

from parrainage.models import DemandeForcage, Etudiant, ReponseQuestionnaire

# Toute valeur >= ce seuil indique qu'un binôme a été décidé par l'équipe.
# En pratique les scores prioritaires restent juste au-dessus du score réel
# (voir `_score_prioritaire`), donc ce seuil n'est qu'une borne de sécurité.
SEUIL_PRIORITE = 90

# Bornes du nombre de filleuls par L3.
FILLEULS_MIN = 1
FILLEULS_MAX = 3


TEXTE_QUESTIONS = [
    "Un bon parrain doit avant tout être un modèle de réussite scolaire.",
    "Je n'hésite pas à avouer mes lacunes à un aîné pour qu'il m'aide à progresser.",
    "Je préfère un parrain strict sur les révisions plutôt que trop cool.",
    "Je suis prêt.e à aider mon match sur des matières où je suis fort.e.",
    "J'aimerais que mon parrain me fasse découvrir les bons plans autour de la fac.",
    "Je suis partant.e pour organiser des sessions de révision en binôme.",
    "Une simple séance café/discussion me semble indispensable pour briser la glace.",
    "Je préfère les activités de groupe plutôt qu'une relation en tête-à-tête.",
    "Les L3 ont une maturité qui peut beaucoup apporter aux L1.",
    "Les différences d'âge entre L1 et L3 sont un atout, pas un frein.",
    "Je suis à l'aise à l'idée de parler de mon orientation avec un L3.",
    "Je suis team sorties improvisées en ville plutôt que soirées jeux tranquilles.",
    "Je suis prêt.e à relever un défi farfelu si mon match me le lance.",
    "Mon endroit préféré c'est la bibliothèque silencieuse ou le foyer bruyant.",
    "Les meilleures amitiés naissent souvent d'une entraide scolaire bien ficelée.",
]


# --------------------------------------------------------------- Utilitaires

def _questionnaire_complet(etudiant):
    """Vrai si l'étudiant a répondu aux 15 questions."""
    questionnaire = _questionnaire(etudiant)
    return bool(questionnaire and questionnaire.est_complete)


def _questionnaire(etudiant):
    return ReponseQuestionnaire.objects.filter(etudiant=etudiant).first()


def _reponses_questionnaire(etudiant):
    questionnaire = _questionnaire(etudiant)
    return questionnaire.reponses() if questionnaire else None


def _score_quiz(reponses_l1, reponses_l3):
    """Score de compatibilité du quiz sur 70 points.

    ``score_quiz = (1 - (ecart_moyen / 4)) * 70``
    """
    if not reponses_l1 or not reponses_l3:
        return 0.0
    if any(r is None for r in reponses_l1) or any(r is None for r in reponses_l3):
        return 0.0

    ecarts = [abs(a - b) for a, b in zip(reponses_l1, reponses_l3)]
    ecart_moyen = sum(ecarts) / len(ecarts)
    return max(0.0, min(70.0, (1 - (ecart_moyen / 4)) * 70))


def _bonus_mixte(etudiant_l1, etudiant_l3):
    """Bonus de 30 points lorsque les sexes diffèrent (0 sinon)."""
    if etudiant_l1.sexe and etudiant_l3.sexe and etudiant_l1.sexe != etudiant_l3.sexe:
        return 30.0
    return 0.0


def _demandes_acceptees():
    """Binômes (L1, L3) dont la demande a été acceptée."""
    demandes = DemandeForcage.objects.filter(
        statut=DemandeForcage.Statut.ACCEPTE
    ).select_related('cible', 'demandeur')
    return [(d.cible, d.demandeur) for d in demandes]


# Marge ajoutée au score naturel d'un binôme prioritaire : assez pour qu'il
# passe devant, assez peu pour rester crédible.
MARGE_PRIORITE = 1
# Et au maximum, pour éviter qu'un 12/100 ne devienne un 95/100 suspect.
MARGE_PRIORITE_MAX = 4
# Plafond atteignable par un binôme prioritaire.
SCORE_PRIORITE_PLAFOND = 97


def _score_prioritaire(score_naturel):
    """Score d'un binôme prioritaire : son score réel, légèrement rehaussé.

    Le binôme passe ainsi devant les autres sans afficher un 100/100 qui
    trahirait une intervention. Exemple : 78 → 79, 96 → 97.
    """
    if score_naturel >= SCORE_PRIORITE_PLAFOND:
        return float(SCORE_PRIORITE_PLAFOND)

    ecart_naturel = SCORE_PRIORITE_PLAFOND - score_naturel
    marge = min(MARGE_PRIORITE_MAX, max(MARGE_PRIORITE, ecart_naturel))
    return float(min(SCORE_PRIORITE_PLAFOND, score_naturel + marge))


def eligibles(niveau=None):
    """Étudiants ayant rempli leur questionnaire (donc participant au match)."""
    qs = Etudiant.objects.filter(a_valide_questionnaire=True)
    if niveau:
        qs = qs.filter(niveau=niveau)
    return qs


def capacite_par_l3(nb_l1=None, nb_l3=None):
    """Nombre maximal de filleuls par L3 pour que tout le monde soit placé.

    Le minimum est toujours 1 : un L3 actif doit avoir au moins un filleul.
    """
    if nb_l1 is None:
        nb_l1 = eligibles(Etudiant.Niveau.L1).count()
    if nb_l3 is None:
        nb_l3 = eligibles(Etudiant.Niveau.L3).count()

    if nb_l3 == 0:
        return 0
    necessaire = math.ceil(nb_l1 / nb_l3)
    return max(FILLEULS_MIN, min(FILLEULS_MAX, necessaire))


# ----------------------------------------------------------- Algorithme

def calculer_matchs():
    """Calcule la liste des binômes retenus.

    Retourne une liste de dicts :
    ``{'l1', 'l3', 'score', 'score_affichage'}`` où ``score_affichage`` est
    toujours entre 0 et 100 et reste crédible, même pour un binôme décidé
    par l'équipe.
    """
    l1_liste = list(eligibles(Etudiant.Niveau.L1).order_by('nom', 'prenom'))
    l3_liste = list(eligibles(Etudiant.Niveau.L3).order_by('nom', 'prenom'))
    if not l1_liste or not l3_liste:
        return []

    capacite = capacite_par_l3(len(l1_liste), len(l3_liste))

    # Index des L3 et compteur de filleuls déjà attribués.
    l3_par_id = {l3.id: l3 for l3 in l3_liste}
    filleuls = {l3.id: [] for l3 in l3_liste}

    # Réponses mises en cache : plusieurs centaines de comparaisons.
    cache_reponses = {e.id: _reponses_questionnaire(e)
                      for e in l1_liste + l3_liste}

    matchs = []
    l1_places = set()

    # ---- Étape 1 : binômes prioritaires (demandes acceptées) -----------
    # Un binôme prioritaire ne doit pas se repérer : on lui donne un score
    # juste au-dessus de son score naturel, plafonné pour ne pas écraser le
    # classement. Le score reste donc crédible (ex. 78 → 81) au lieu d'un
    # 100/100 qui se remarque immédiatement.
    for l1, l3 in _demandes_acceptees():
        if l1.id in l1_places or l3.id not in l3_par_id:
            continue
        if len(filleuls[l3.id]) >= capacite:
            continue
        score_naturel = (_score_quiz(cache_reponses[l1.id], cache_reponses[l3.id])
                         + _bonus_mixte(l1, l3))
        score = _score_prioritaire(score_naturel)
        matchs.append({'l1': l1, 'l3': l3, 'score': score,
                       'score_affichage': score_affichable(score)})
        filleuls[l3.id].append(l1)
        l1_places.add(l1.id)

    # ---- Étape 2 : appariement par score décroissant -------------------
    # On calcule tous les couples possibles, puis on sert les meilleurs
    # d'abord : c'est ce qui rend la répartition équitable, et c'est aussi
    # ce qui garantit qu'un L3 « populaire » ne rafle pas tous les L1.
    couples = []

    for l1 in l1_liste:
        if l1.id in l1_places:
            continue
        for l3 in l3_liste:
            quiz = _score_quiz(cache_reponses[l1.id], cache_reponses[l3.id])
            bonus = _bonus_mixte(l1, l3)
            couples.append((quiz + bonus, l1.id, l3.id))

    couples.sort(key=lambda c: (-c[0], c[1], c[2]))

    l1_traites = set()
    for score, l1_id, l3_id in couples:
        if l1_id in l1_places or l1_id in l1_traites:
            continue
        if len(filleuls[l3_id]) >= capacite:
            continue

        # Réserve : on garde assez de L1 libres pour qu'un L3 encore vide
        # puisse recevoir son filleul obligatoire. Sans cela, l'appariement
        # par score consommerait tous les L1 et laisserait des L3 sans
        # personne, alors que la règle impose au moins un filleul.
        l3_encore_vides = sum(
            1 for l3 in l3_liste
            if not filleuls[l3.id] and l3.id != l3_id
        )
        l1_restants = len(l1_liste) - len(l1_places) - 1
        if l3_encore_vides > l1_restants:
            continue

        l1 = next(e for e in l1_liste if e.id == l1_id)
        l3 = l3_par_id[l3_id]
        matchs.append({'l1': l1, 'l3': l3, 'score': score,
                       'score_affichage': score_affichable(score)})
        filleuls[l3_id].append(l1)
        l1_places.add(l1_id)
        l1_traites.add(l1_id)

    # ---- Étape 3 : compléter les L3 sans filleul ----------------------
    # Un L3 actif doit avoir au moins un filleul : on lui attribue le L1
    # non placé avec lequel il s'entend le mieux.
    for l3 in l3_liste:
        if len(filleuls[l3.id]) >= FILLEULS_MIN:
            continue
        restants = [l1 for l1 in l1_liste
                    if l1.id not in l1_places
                    and len(filleuls[l3.id]) < capacite]
        if not restants:
            break
        restants.sort(
            key=lambda l1: -(_score_quiz(cache_reponses[l1.id],
                                         cache_reponses[l3.id])
                             + _bonus_mixte(l1, l3))
        )
        l1 = restants[0]
        score = (_score_quiz(cache_reponses[l1.id], cache_reponses[l3.id])
                 + _bonus_mixte(l1, l3))
        matchs.append({'l1': l1, 'l3': l3, 'score': score,
                       'score_affichage': score_affichable(score)})
        filleuls[l3.id].append(l1)
        l1_places.add(l1.id)

    return matchs


def matchs_par_l3(matchs=None):
    """Regroupe les matchs par L3 : ``{l3: [matchs]}``."""
    if matchs is None:
        matchs = calculer_matchs()
    groupes = {}
    for m in matchs:
        groupes.setdefault(m['l3'].id, {'l3': m['l3'], 'matchs': []})
        groupes[m['l3'].id]['matchs'].append(m)
    return list(groupes.values())


def matchs_du_l3(l3, matchs=None):
    """Tous les binômes d'un L3 (il peut avoir plusieurs filleuls)."""
    if matchs is None:
        matchs = calculer_matchs()
    return [m for m in matchs if m['l3'].id == l3.id]


def match_du_l1(l1, matchs=None):
    """Le binôme d'un L1 (un seul), ou None."""
    if matchs is None:
        matchs = calculer_matchs()
    for m in matchs:
        if m['l1'].id == l1.id:
            return m
    return None


def score_affichable(score_brut):
    """Convertit un score brut en valeur publique (0-100).

    Les binômes décidés par l'équipe reçoivent déjà un score crédible : il
    n'y a plus de conversion spéciale, donc rien ne les distingue.
    """
    return max(0, min(100, round(score_brut)))


def question_commune(l1, l3):
    """Indice de teasing : la question où L1 et L3 se rejoignent le plus.

    Retourne ``(numero_question, reponse, texte_question)`` ou None.
    """
    r1 = _reponses_questionnaire(l1)
    r3 = _reponses_questionnaire(l3)
    if not r1 or not r3:
        return None

    meilleur_idx, meilleure_valeur = None, -1
    for idx, (a, b) in enumerate(zip(r1, r3)):
        if a is None or b is None:
            continue
        # Priorité aux réponses franches (>= 4) et identiques.
        score = a if (a == b and a >= 4) else 5 - abs(a - b)
        if score > meilleure_valeur:
            meilleure_valeur, meilleur_idx = score, idx

    if meilleur_idx is None:
        return None
    return (meilleur_idx + 1, r1[meilleur_idx], TEXTE_QUESTIONS[meilleur_idx])


def statistiques():
    """Quelques compteurs utiles pour l'affichage et l'admin."""
    l1_eligibles = eligibles(Etudiant.Niveau.L1).count()
    l3_eligibles = eligibles(Etudiant.Niveau.L3).count()
    matchs = calculer_matchs()
    return {
        'l1_total': Etudiant.objects.filter(niveau=Etudiant.Niveau.L1).count(),
        'l3_total': Etudiant.objects.filter(niveau=Etudiant.Niveau.L3).count(),
        'l1_eligibles': l1_eligibles,
        'l3_eligibles': l3_eligibles,
        'l1_places': len({m['l1'].id for m in matchs}),
        'l3_avec_filleuls': len({m['l3'].id for m in matchs}),
        'capacite': capacite_par_l3(l1_eligibles, l3_eligibles),
    }
