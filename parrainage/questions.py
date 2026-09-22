"""Catalogue du questionnaire de parrainage (25 questions).

Source : « Questionnaire Parrainage — Version Chill (courte) ».

Chaque question porte un code stable (``q1``…``q25``) utilisé pour stocker les
réponses. Les codes ne doivent JAMAIS être réordonnés : les réponses déjà
enregistrées y sont rattachées.

Types de question
-----------------
- ``choix``   : une seule option parmi ``options``
- ``multi``   : plusieurs options (``max_choix`` limite éventuellement)
- ``texte``   : réponse libre
- ``echelle`` : note entière de 0 à 10

**Toutes les questions sont obligatoires** : il faut y répondre pour pouvoir
valider le questionnaire. Le champ ``facultatif`` reste disponible dans le
catalogue si l'équipe souhaite en rendre une passable plus tard.
"""

from dataclasses import dataclass, field


# ----------------------------------------------------------------- Types
TYPE_CHOIX = 'choix'
TYPE_MULTI = 'multi'
TYPE_TEXTE = 'texte'
TYPE_ECHELLE = 'echelle'


@dataclass(frozen=True)
class Question:
    code: str
    section: str
    texte: str
    type: str
    options: tuple = ()
    facultatif: bool = False
    # Niveau concerné : None = tout le monde, 'L1' / 'L3' = une seule version.
    condition: str = None
    max_choix: int = None
    aide: str = ''

    @property
    def est_note(self):
        """La question entre-t-elle dans le calcul du score ?

        Les réponses libres (Q21, Q23, Q25) servent au contexte, au filtrage
        d'exclusion ou à l'expérience — jamais à la note.
        """
        return self.type in (TYPE_CHOIX, TYPE_MULTI, TYPE_ECHELLE)

    @property
    def est_numerique(self):
        """Question à choix ordonné : l'écart entre les rangs a un sens."""
        return self.type == TYPE_CHOIX and self.code in ORDONNEES


# Questions dont les options forment une échelle ordonnée (introversion,
# organisation, rythme de réponse…). Pour celles-ci, deux réponses proches
# valent mieux que deux réponses opposées.
ORDONNEES = {
    'q1',   # introverti → extraverti
    'q4',   # très carré → on verra la veille
    'q6',   # répond tout de suite → rarement
    'q9',   # sort presque jamais → dès qu'il y a un truc
    'q10',  # alcool : jamais → régulièrement
    'q11',  # tabac : jamais → régulièrement
    'q20',  # matin → nuit
    'q24',  # envie de créer un lien (0-10)
}


def _options(*libelles):
    """Construit des options (valeur, libellé) à partir des libellés."""
    return tuple((str(i), libelle) for i, libelle in enumerate(libelles))


# =====================================================================
#  Les 25 questions
# =====================================================================

_SECTION_1 = "Toi, en vrai"
_SECTION_2 = "Études & ambition"
_SECTION_3 = "Communication"
_SECTION_4 = "Sorties & vie sociale"
_SECTION_5 = "Religion & valeurs"
_SECTION_6 = "Un peu de piment"
_SECTION_7 = "Questions qui révèlent tout"
_SECTION_8 = "Lifestyle"
_SECTION_9 = "Pour le matching final"

QUESTIONS = [
    # ---------------------------------------------- 1. Toi, en vrai
    Question(
        'q1', _SECTION_1, "Tu te décrirais comme…", TYPE_CHOIX,
        _options(
            "Très introverti(e), je recharge seul(e)",
            "Plutôt discret(e)",
            "Un mix des deux",
            "Plutôt à l'aise partout",
            "Extraverti(e) à fond, je parle à tout le monde",
        ),
    ),
    Question(
        'q2', _SECTION_1, "Quand ça va pas, tu préfères quelqu'un qui…",
        TYPE_CHOIX,
        _options(
            "M'écoute, sans me juger",
            "Me conseille direct",
            "Me change les idées",
            "Me dit franchement ce qu'il/elle pense",
        ),
    ),
    Question(
        'q3', _SECTION_1, "Ton humour, c'est quel style ?", TYPE_CHOIX,
        _options(
            "Innocent", "Sarcastique", "Noir", "Absurde", "Taquin",
            "Un mélange de tout",
        ),
    ),

    # ------------------------------------- 2. Études & ambition
    Question(
        'q4', _SECTION_2, "Côté organisation pour les cours, t'es…",
        TYPE_CHOIX,
        _options(
            "Très carré(e)",
            "Organisé(e) quand il faut",
            "Je bosse surtout sous pression",
            "« On verra la veille » 💀",
        ),
    ),
    Question(
        'q5', _SECTION_2, "Niveau ambition pro, tu vises quoi ?", TYPE_CHOIX,
        _options(
            "Être épanoui(e), avant tout",
            "Une carrière stable",
            "Gagner beaucoup d'argent",
            "Entreprendre",
            "Aller très loin, point final",
            "Je sais pas encore et c'est ok",
        ),
    ),

    # --------------------------------------- 3. Communication
    Question(
        'q6', _SECTION_3, "Tu réponds aux messages…", TYPE_CHOIX,
        _options(
            "Immédiatement",
            "Dans l'heure",
            "Dans la journée",
            "Quand Dieu me rappelle que WhatsApp existe 😭",
        ),
    ),
    Question(
        'q7', _SECTION_3, "Un truc te gêne chez quelqu'un. Tu fais quoi ?",
        TYPE_CHOIX,
        _options(
            "Je le dis direct",
            "J'attends le bon moment",
            "Je prends mes distances, sans rien dire",
            "Je garde tout jusqu'à exploser",
        ),
    ),

    # --------------------------------- 4. Sorties & vie sociale
    Question(
        'q8', _SECTION_4, "Ta soirée idéale ressemble à…", TYPE_CHOIX,
        _options(
            "Netflix/jeu/lecture chez moi",
            "Petit resto tranquille",
            "Sortie entre potes",
            "Bar / lounge",
            "Grosse soirée",
            "Ça dépend total de mon humeur",
        ),
    ),
    Question(
        'q9', _SECTION_4, "Tu sors à quel rythme ?", TYPE_CHOIX,
        _options(
            "Presque jamais",
            "Quelques fois par mois",
            "Toutes les semaines",
            "Dès qu'il y a un truc 😭",
        ),
    ),
    Question(
        'q10', _SECTION_4, "Ton rapport à l'alcool ?", TYPE_CHOIX,
        _options(
            "Jamais", "Rarement", "Occasionnellement", "Régulièrement",
            "Je préfère ne pas répondre",
        ),
    ),
    Question(
        'q11', _SECTION_4,
        "Et à la cigarette / chicha / autre ?", TYPE_CHOIX,
        _options(
            "Jamais", "Rarement", "Occasionnellement", "Régulièrement",
            "Je préfère ne pas répondre",
        ),
    ),

    # ---------------------------------------- 5. Religion & valeurs
    Question(
        'q12', _SECTION_5, "Tu te définirais comme…", TYPE_CHOIX,
        _options(
            "Chrétien(ne)",
            "Musulman(e)",
            "D'une autre religion",
            "Spirituel(le) sans religion",
            "Agnostique",
            "Athée",
            "Je préfère ne pas répondre",
        ),
    ),
    Question(
        'q13', _SECTION_5,
        "Important que ton binôme partage ta religion ?", TYPE_CHOIX,
        _options(
            "Oui, absolument",
            "Ce serait un plus",
            "Pas du tout",
            "Peu importe tant qu'il/elle respecte mes convictions",
        ),
    ),
    Question(
        'q14', _SECTION_5, "Tes 3 valeurs les plus importantes ?",
        TYPE_MULTI,
        _options(
            "Loyauté", "Honnêteté", "Ambition", "Foi", "Famille",
            "Liberté", "Respect", "Solidarité", "Discipline", "Tolérance",
            "Humour",
        ),
        max_choix=3,
    ),

    # ---------------------------------------- 6. Un peu de piment
    Question(
        'q15', _SECTION_6, "Ton plus gros red flag chez quelqu'un ?",
        TYPE_CHOIX,
        _options(
            "Mensonge", "Jalousie", "Infidélité", "Manque d'ambition",
            "Irrespect", "Mauvaise communication", "Égocentrisme",
            "Dépendance affective",
        ),
    ),
    Question(
        'q16', _SECTION_6,
        "Ton parrain/marraine ou filleul(e) devient ton crush. Réaction ?",
        TYPE_CHOIX,
        _options(
            "Pourquoi pas 👀",
            "Ça dépend",
            "Mauvaise idée",
            "INTERDIT, c'est la famille maintenant 😭",
        ),
    ),

    # ------------------------ 7. Questions qui révèlent tout
    Question(
        'q17', _SECTION_7,
        "Ton pote a clairement tort dans une embrouille. Tu fais quoi ?",
        TYPE_CHOIX,
        _options(
            "Je le/la défends devant les autres, je lui parle en privé après",
            "Je lui dis direct qu'il/elle a tort",
            "Je prends pas parti",
            "Je défends mon gars/ma go même devant la Cour pénale 😭",
        ),
    ),
    Question(
        'q18', _SECTION_7,
        "Dans une amitié, ce que tu supportes le moins ?", TYPE_CHOIX,
        _options(
            "Être ignoré(e)",
            "Le manque de loyauté",
            "Les mensonges",
            "Les personnes trop possessives",
            "Les critiques constantes",
            "Les relations à sens unique",
        ),
    ),

    # ------------------------------------------- 8. Lifestyle
    Question(
        'q19', _SECTION_8,
        "Tes centres d'intérêt (coche tout ce qui te parle) :", TYPE_MULTI,
        _options(
            "Sport", "Musique", "Cinéma/séries", "Jeux vidéo", "Anime/manga",
            "Lecture", "Mode", "Technologie", "Entrepreneuriat", "Voyage",
            "Cuisine", "Politique/actualité", "Religion/spiritualité", "Art",
            "Réseaux sociaux", "Danse",
        ),
        aide="Tu peux en cocher autant que tu veux.",
    ),
    Question(
        'q20', _SECTION_8, "Tu es plutôt…", TYPE_CHOIX,
        _options("Matin", "Soir", "Nuit", "Fatigué(e) 24/7"),
    ),

    # ---------------------------------- 9. Pour le matching final
    Question(
        'q21', _SECTION_9,
        "Qu'est-ce que t'attends le plus de ton parrain / ta marraine ?",
        TYPE_TEXTE,
        condition='L1',
        aide="Deux ou trois phrases suffisent.",
    ),
    Question(
        'q21', _SECTION_9,
        "Qu'est-ce que tu peux apporter à ton / ta filleul(e) ?",
        TYPE_TEXTE,
        condition='L3',
        aide="Deux ou trois phrases suffisent.",
    ),
    Question(
        'q22', _SECTION_9,
        "Qu'est-ce que t'attends vraiment de ton binôme, en général ?",
        TYPE_CHOIX,
        _options(
            "Une connaissance sympa",
            "Un guide pour les études",
            "Un(e) partenaire de sorties",
            "Une vraie amitié",
            "Quelqu'un à qui parler",
            "Un peu de tout ça",
        ),
    ),
    Question(
        'q23', _SECTION_9,
        "En une phrase : ton binôme idéal, c'est qui — et ton deal-breaker "
        "absolu ?", TYPE_TEXTE,
        aide="Ton binôme idéal (le genre de personne avec qui tu t'entendrais) "
             "et ton deal-breaker : le défaut que tu ne pourrais PAS supporter "
             "chez quelqu'un (ex. la malhonnêteté, le manque de respect…). "
             "Cette réponse sert à éviter les binômes qui te correspondent mal.",
    ),
    Question(
        'q24', _SECTION_9,
        "Sur 10, t'as vraiment envie de créer un lien avec ton binôme ?",
        TYPE_ECHELLE,
    ),
    Question(
        'q25', _SECTION_9,
        "Pour finir : un message anonyme à ton futur parrain / ta future "
        "filleule 👀", TYPE_TEXTE,
        aide="Il sera transmis à ton binôme le jour de la révélation.",
    ),
]


# --------------------------------------------------------------- Index
def questions_pour(niveau):
    """Questions visibles pour un niveau donné (L1 / L3)."""
    return [q for q in QUESTIONS if q.condition in (None, niveau)]


def par_code(code, niveau=None):
    """Retourne la question correspondant à un code.

    ``q21`` existe en deux versions : on sélectionne celle du niveau.
    """
    candidates = [q for q in QUESTIONS if q.code == code]
    if niveau is not None:
        for q in candidates:
            if q.condition == niveau:
                return q
        for q in candidates:
            if q.condition is None:
                return q
    return candidates[0] if candidates else None


def codes_selectionnables(niveau):
    """Codes attendus pour un niveau (sert à valider une soumission)."""
    return [q.code for q in questions_pour(niveau)]


def libelle_option(code, valeur, niveau=None):
    """Libellé lisible d'une option (pour l'admin et les fiches)."""
    q = par_code(code, niveau)
    if not q:
        return valeur
    for val, lib in q.options:
        if str(val) == str(valeur):
            return lib
    return valeur


def toutes_les_sections():
    """Sections dans l'ordre d'apparition (pour l'affichage groupé)."""
    vues = []
    for q in QUESTIONS:
        if q.section not in vues:
            vues.append(q.section)
    return vues


# --------------------------------------------- Sous-scores du matching
# Chaque dimension rassemble les questions qui mesurent la même chose.
# L'ordre reflète les sous-scores demandés par le document.
DIMENSIONS = [
    ("Personnalité",      {'q1', 'q2', 'q3'}),
    ("Études",            {'q4', 'q5'}),
    ("Communication",     {'q6', 'q7', 'q17', 'q18'}),
    ("Social",            {'q8', 'q9', 'q10', 'q11', 'q16', 'q20', 'q24'}),
    ("Valeurs",           {'q12', 'q13', 'q14', 'q15'}),
    ("Centres d'intérêt", {'q19', 'q22'}),
]

# Poids relatifs des dimensions dans la note du questionnaire (somme = 1).
POIDS_DIMENSIONS = {
    "Personnalité":      0.18,
    "Études":            0.12,
    "Communication":     0.18,
    "Social":            0.16,
    "Valeurs":           0.22,
    "Centres d'intérêt": 0.14,
}

# Questions qui entrent dans le score final.
CODES_NOTES = {q.code for q in QUESTIONS if q.est_note and q.code != 'q21'}
