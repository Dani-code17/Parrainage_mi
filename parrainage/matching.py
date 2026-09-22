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


# --------------------------------------------------------------- Utilitaires

def _questionnaire_complet(etudiant):
    """Vrai si l'étudiant a répondu à toutes les questions obligatoires."""
    questionnaire = _questionnaire(etudiant)
    return bool(questionnaire and questionnaire.est_complete)


def _questionnaire(etudiant):
    return ReponseQuestionnaire.objects.filter(etudiant=etudiant).first()


# =====================================================================
#  Similarité question par question
# =====================================================================

# Deux réponses différentes mais plausibles ne sont pas un désaccord total :
# on leur laisse une part de compatibilité.
ACCORD_CATEGORIEL_DIFFERENT = 0.35


def _accord_question(question, va, vb):
    """Accord entre deux réponses à une même question, entre 0 et 1.

    Retourne None si l'un des deux n'a pas répondu : la question est alors
    simplement ignorée du calcul (elle ne pénalise pas).
    """
    from parrainage.questions import ORDONNEES, TYPE_CHOIX, TYPE_ECHELLE, TYPE_MULTI

    if va in (None, '', []) or vb in (None, '', []):
        return None

    # --- Choix multiples : indice de Jaccard ---------------------------
    if question.type == TYPE_MULTI:
        a = {str(x) for x in (va if isinstance(va, list) else [va])}
        b = {str(x) for x in (vb if isinstance(vb, list) else [vb])}
        if not a and not b:
            return None
        union = a | b
        return len(a & b) / len(union) if union else None

    # --- Note de 0 à 10 ------------------------------------------------
    if question.type == TYPE_ECHELLE:
        try:
            return max(0.0, 1 - abs(int(va) - int(vb)) / 10)
        except (TypeError, ValueError):
            return None

    # --- Choix unique à options ordonnées ------------------------------
    if question.type == TYPE_CHOIX and question.code in ORDONNEES:
        try:
            ia, ib = int(va), int(vb)
        except (TypeError, ValueError):
            return None
        maximum = max(1, len(question.options) - 1)
        ecart = abs(ia - ib)
        accord = 1 - ecart / maximum

        # Complémentarité : sur la sociabilité, deux profils très réservés
        # risquent de ne jamais se relancer, et deux profils très expansifs
        # s'entraident moins sur le travail. Un duo complémentaire est
        # légèrement favorisé.
        if question.code == 'q1':
            if ia <= 1 and ib <= 1:
                accord *= 0.75
            elif ia >= 3 and ib >= 3:
                accord *= 0.9
            else:
                accord = min(1.0, accord + 0.15)
        return max(0.0, accord)

    # --- Choix unique catégoriel ---------------------------------------
    return 1.0 if str(va) == str(vb) else ACCORD_CATEGORIEL_DIFFERENT


def _scores_dimensions(q_l1, q_l3):
    """Accord moyen par dimension, entre 0 et 1.

    Les questions sans réponse d'un côté sont ignorées : un étudiant qui a
    laissé une question facultative vide n'est pas pénalisé.
    """
    from parrainage.questions import DIMENSIONS

    if q_l1 is None or q_l3 is None:
        return {}

    resultats = {}
    for nom, codes in DIMENSIONS:
        accords = []
        for code in codes:
            question = parrainage_questions_par_code(code)
            if question is None:
                continue
            a = _accord_question(question, q_l1.valeur(code), q_l3.valeur(code))
            if a is not None:
                accords.append(a)
        if accords:
            resultats[nom] = sum(accords) / len(accords)
    return resultats


def parrainage_questions_par_code(code):
    """Raccourci d'accès au catalogue (évite un import circulaire)."""
    from parrainage.questions import par_code
    return par_code(code)


def _score_questionnaire(q_l1, q_l3):
    """Note du questionnaire sur 70 points.

    Chaque dimension est pondérée (voir ``POIDS_DIMENSIONS``). Les
    dimensions entièrement sans réponse sont retirées et les poids sont
    renormalisés, pour qu'un questionnaire partiel reste comparable.
    """
    from parrainage.questions import POIDS_DIMENSIONS

    par_dimension = _scores_dimensions(q_l1, q_l3)
    if not par_dimension:
        return 0.0

    poids_total = sum(POIDS_DIMENSIONS[nom] for nom in par_dimension)
    if poids_total <= 0:
        return 0.0

    accord = sum(par_dimension[nom] * POIDS_DIMENSIONS[nom]
                 for nom in par_dimension) / poids_total
    return max(0.0, min(70.0, accord * 70))


def _bonus_mixte(etudiant_l1, etudiant_l3):
    """Bonus de 30 points lorsque les sexes diffèrent (0 sinon)."""
    if etudiant_l1.sexe and etudiant_l3.sexe and etudiant_l1.sexe != etudiant_l3.sexe:
        return 30.0
    return 0.0


# =====================================================================
#  Filtre d'exclusion : deal-breaker (Q23)
# =====================================================================

# ⚠️ Désactivé par défaut, volontairement.
#
# Le questionnaire ne contient PAS de question du type « je suis jaloux ».
# La Q15 demande « ton plus gros red flag chez quelqu'un », c'est-à-dire ce
# que la personne DÉTESTE. Exclure un binôme parce que l'un écrit « pas de
# jaloux » et que l'autre a coché « Jalousie » comme red flag écarterait
# donc deux personnes qui sont… d'accord entre elles.
#
# Tant que ce drapeau reste à False, aucune paire n'est écartée
# automatiquement : le deal-breaker est simplement montré à l'équipe dans
# l'admin, qui tranche à la main. Passer la valeur à True active le filtre
# ci-dessous — à n'utiliser que si une question « je suis… » est ajoutée au
# questionnaire.
EXCLUSION_DEALBREAKER = False

# Mots-clés d'un « deal-breaker » reliés au red flag correspondant (Q15).
# Exemple : écrire « jaloux » comme deal-breaker exclut un binôme qui a
# lui-même coché « Jalousie » dans ses red flags.
DEALBREAKER_VERS_REDFLAG = {
    'jalou': 'Jalousie',
    'possessif': 'Dépendance affective',
    'mensong': 'Mensonge',
    'menteur': 'Mensonge',
    'infidel': 'Infidélité',
    'trompe': 'Infidélité',
    'irrespect': 'Irrespect',
    'impoli': 'Irrespect',
    'manque d\'ambition': "Manque d'ambition",
    'faineant': "Manque d'ambition",
    'paresse': "Manque d'ambition",
    'egois': 'Égocentrisme',
    'egocentri': 'Égocentrisme',
    'centr': 'Égocentrisme',
    'communication': 'Mauvaise communication',
    'silence': 'Mauvaise communication',
    'ghost': 'Mauvaise communication',
    'dependan': 'Dépendance affective',
    'colle': 'Dépendance affective',
}


def _normaliser_texte(texte):
    from unicodedata import normalize
    texte = (texte or '').lower()
    sans_accent = ''.join(
        c for c in normalize('NFD', texte)
        if normalize('NFD', c)[0] not in ('\u0300', '\u0301', '\u0302', '\u0303',
                                          '\u0308', '\u0327')
    )
    return sans_accent


def dealbreaker_incompatible(q_l1, q_l3):
    """Un deal-breaker déclaré exclut-il ce binôme ?

    Signal binaire, sans pondération : si une personne écrit que son
    deal-breaker est « la jalousie » et que l'autre a coché « Jalousie »
    parmi ses red flags, le binôme est écarté.
    """
    if q_l1 is None or q_l3 is None:
        return False

    for source, cible in ((q_l1, q_l3), (q_l3, q_l1)):
        texte = _normaliser_texte(source.texte('q23'))
        if not texte:
            continue
        red_flag = cible.choix('q15')
        for mot, categorie in DEALBREAKER_VERS_REDFLAG.items():
            if mot in texte and red_flag:
                from parrainage.questions import libelle_option
                if libelle_option('q15', red_flag, cible.etudiant.niveau) == categorie:
                    return True
    return False


def _incompatibles(l1, l3, cache):
    """Vrai si le binôme doit être écarté d'office.

    Ne s'applique que si ``EXCLUSION_DEALBREAKER`` est activé (voir la note
    ci-dessus : le filtre est désactivé par défaut).
    """
    if not EXCLUSION_DEALBREAKER:
        return False
    return dealbreaker_incompatible(cache.get(l1.id), cache.get(l3.id))


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

    # Questionnaires mis en cache : plusieurs milliers de comparaisons.
    cache = {e.id: _questionnaire(e) for e in l1_liste + l3_liste}

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
        score_naturel = (_score_questionnaire(cache[l1.id], cache[l3.id])
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
            # Filtre binaire : un deal-breaker écarté d'office.
            if _incompatibles(l1, l3, cache):
                continue
            note = _score_questionnaire(cache[l1.id], cache[l3.id])
            bonus = _bonus_mixte(l1, l3)
            couples.append((note + bonus, l1.id, l3.id))

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
                    and len(filleuls[l3.id]) < capacite
                    and not _incompatibles(l1, l3, cache)]
        if not restants:
            break
        restants.sort(
            key=lambda l1: -(_score_questionnaire(cache[l1.id], cache[l3.id])
                             + _bonus_mixte(l1, l3))
        )
        l1 = restants[0]
        score = (_score_questionnaire(cache[l1.id], cache[l3.id])
                 + _bonus_mixte(l1, l3))
        matchs.append({'l1': l1, 'l3': l3, 'score': score,
                       'score_affichage': score_affichable(score)})
        filleuls[l3.id].append(l1)
        l1_places.add(l1.id)

    # ---- Étape 4 : rattrapage -----------------------------------------
    # La réserve de l'étape 2 peut laisser un L1 de côté lorsqu'un L3 encore
    # vide s'avère incompatible avec lui (deal-breaker). On place alors les
    # L1 restants chez le L3 qui leur convient le mieux et qui a encore de
    # la place, même s'il a déjà des filleuls.
    for l1 in l1_liste:
        if l1.id in l1_places:
            continue
        candidats = [
            l3 for l3 in l3_liste
            if len(filleuls[l3.id]) < capacite
            and not _incompatibles(l1, l3, cache)
        ]
        if not candidats:
            continue
        candidats.sort(
            key=lambda l3: -(_score_questionnaire(cache[l1.id], cache[l3.id])
                             + _bonus_mixte(l1, l3))
        )
        l3 = candidats[0]
        score = (_score_questionnaire(cache[l1.id], cache[l3.id])
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
    """Indice de teasing : le point commun le plus fort entre deux étudiants.

    Retourne un dictionnaire ``{'question', 'reponse', 'pct'}`` ou None :

    - ``question`` : le texte de la question où ils se rejoignent le plus
    - ``reponse``  : le libellé de leur réponse commune
    - ``pct``      : cet accord en pourcentage (pour la jauge)
    """
    from parrainage.questions import CODES_NOTES, libelle_option, par_code

    q_l1 = _questionnaire(l1)
    q_l3 = _questionnaire(l3)
    if q_l1 is None or q_l3 is None:
        return None

    meilleur = None
    for code in CODES_NOTES:
        question = par_code(code, l1.niveau)
        if question is None:
            continue
        va, vb = q_l1.valeur(code), q_l3.valeur(code)
        accord = _accord_question(question, va, vb)
        if accord is None:
            continue
        if meilleur is None or accord > meilleur[0]:
            meilleur = (accord, question, va)

    if meilleur is None:
        return None

    accord, question, valeur = meilleur

    # Réponse lisible : on privilégie celle du L1, qui lit l'indice.
    if question.type == 'multi':
        reponse = ', '.join(
            libelle_option(question.code, x, l1.niveau) for x in (valeur or [])
        )
    elif question.type == 'choix':
        reponse = libelle_option(question.code, valeur, l1.niveau)
    elif question.type == 'echelle':
        reponse = f"{valeur}/10"
    else:
        reponse = str(valeur)

    return {
        'question': question.texte,
        'reponse': reponse,
        'pct': round(accord * 100),
    }


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
