"""Déduction du sexe à partir d'un prénom.

Les listes fournies (L1 / L3) ne comportent pas de colonne « sexe », alors que
le bonus mixte de l'algorithme en dépend. On déduit donc une valeur probable
depuis le prénom, valeur que l'équipe confirme ensuite dans l'admin.

La fonction ne devine jamais au hasard plus loin qu'une heuristique de suffixe :
si rien n'est reconnu, elle retourne une chaîne vide (sexe à renseigner).
"""

from unicodedata import normalize

FEMININS = {
    'ama', 'akissi', 'adjoua', 'amenan', 'ahou', 'aya', 'affoua', 'ablan',
    'aude', 'esther', 'gore', 'arielle', 'scherina', 'rebecca', 'nadege',
    'jocelyne', 'ghislaine', 'sylvie', 'christelle', 'prisca', 'grace',
    'ornella', 'prunelle', 'ruth', 'rihanna', 'noura', 'zeinab', 'chimelle',
    'angellica', 'shirley', 'alexandra', 'colombe', 'emmanuella', 'noralinn',
    'taly', 'katr', 'carmel', 'hope', 'lilia', 'orilia', 'michelle', 'aimee',
    'sarah', 'marie', 'fatou', 'awa', 'mariam', 'aminata', 'larissa',
    'sandra', 'juliette', 'celine', 'sandrine', 'viviane', 'yvette',
    'sylvain', 'brigitte', 'casimir', 'germaine', 'therese', 'pauline',
    'angelique', 'benedicte', 'carine', 'clarisse', 'constance', 'delphine',
    'diane', 'elisabeth', 'fabiola', 'falonne', 'florence', 'genevieve',
    'germaine', 'hannah', 'helene', 'ines', 'isabelle', 'jacqueline',
    'jeanne', 'josephine', 'josiane', 'laure', 'lea', 'louise', 'marguerite',
    'marthe', 'mireille', 'monique', 'nadine', 'noelle', 'odette', 'olivia',
    'patricia', 'philippine', 'rachel', 'raissa', 'regine', 'rose', 'solange',
    'stephanie', 'suzanne', 'tatiana', 'valentine', 'vanessa', 'veronique',
    'victoire', 'virginie', 'yolande', 'zoe', 'emilie', 'amelie', 'aurelie',
    'claire', 'eleonore', 'eloise', 'eugenie', 'melanie', 'ophelie',
    'aicha', 'aida', 'akoua', 'aminata', 'anoue', 'assana', 'awa', 'bintou',
    'djeneba', 'fanta', 'hawa', 'kadiatou', 'kadi', 'mariame', 'massandje',
    'nene', 'oumu', 'safiatou', 'salimata', 'tenin', 'yasmine', 'zahra',
    'nandy', 'naomie', 'ndanane', 'muriel', 'myriam', 'maelle', 'maeva',
    'elodie', 'estelle', 'eunice', 'bianca', 'cassandra', 'debora', 'divine',
    'dominique', 'edwige', 'erika', 'esperance', 'firmine', 'giselle',
    'gloria', 'grace', 'hadja', 'hortense', 'ida', 'innocente', 'irene',
    'jasmine', 'jeannette', 'judith', 'karen', 'kelly', 'leontine', 'linda',
    'lucie', 'madeleine', 'mado', 'maelle', 'manuella', 'marcelle',
    'melissa', 'micheline', 'mireille', 'nadia', 'natacha', 'nathalie',
    'noemie', 'princesse', 'prudence', 'rebecca', 'rosalie', 'sabine',
    'samira', 'sarah', 'seraphine', 'simone', 'sonia', 'sophie', 'sylvia',
    'thecle', 'valerie', 'venance', 'victorine', 'viviane', 'wilfrieda',
    'yannicka', 'yvonne', 'zenab', 'zita',
    # Compléments issus des listes réelles.
    'nelly', 'roxane', 'priscille', 'arlene', 'raihanat', 'karidjatou',
    'folashade', 'oyolola', 'arike', 'awanat', 'nathanaelle', 'sania',
    'raniah', 'madogne', 'fougnegue', 'tabitha', 'rebekah', 'amlan',
    'djenabou', 'hajatou', 'kadidja', 'kadijatou', 'lamine', 'mariama',
    'minata', 'nagnouma', 'ramatoulaye', 'rokia', 'sita', 'sitan',
    'tenin', 'tiemoko', 'yeguessa', 'zoumana', 'aissata', 'bintou',
    'coumba', 'djenaba', 'fadima', 'gnalen', 'hadja', 'hawa', 'kaoula',
    'kassamba', 'lalla', 'madina', 'marietou', 'maymouna', 'nabou',
    'neneh', 'nialen', 'oummou', 'safiatou', 'seydina', 'sonia', 'yacine',
}

FEMININS -= {'lamine', 'tiemoko', 'zoumana', 'seydina'}

MASCULINS = {
    'koffi', 'kouassi', 'kouadio', 'konan', 'yao', 'kouakou', 'kouame',
    'nguessan', 'ndri', 'amani', 'ange', 'emmanuel', 'jean', 'marc', 'david',
    'prince', 'samuel', 'daniel', 'steve', 'junior', 'christian', 'frederic',
    'ariel', 'ismael', 'faissal', 'yannick', 'landry', 'joel', 'evrard',
    'jerome', 'aboubacar', 'sidick', 'cheick', 'issouf', 'mory', 'moussa',
    'adama', 'ibrahim', 'mohamed', 'abdoul', 'kader', 'windemi', 'oswald',
    'michel', 'jacques', 'henoc', 'davy', 'davry', 'elieser', 'angel',
    'youssouf', 'noman', 'morel', 'melvin', 'kouao', 'sidik', 'linares',
    'kagnefolo', 'jorim', 'esli', 'makene', 'assad', 'charles', 'jeruel',
    'johan', 'aboh', 'natanael', 'moktar', 'seydou', 'sekou', 'souleymane',
    'toure', 'traore', 'ouattara', 'bamba', 'coulibaly', 'diarra', 'diomande',
    'dosso', 'yeboue', 'zadi', 'akon', 'kacou', 'kablan', 'kobenan',
    'koffi', 'kokora', 'kossonou', 'kpan', 'kra', 'lago', 'lorougnon',
    'mambe', 'mambo', 'marcel', 'marius', 'mathieu', 'maurice', 'maxime',
    'michael', 'mickael', 'narcisse', 'nicolas', 'noel', 'ogou', 'olivier',
    'pacome', 'pascal', 'patrick', 'paul', 'philippe', 'pierre', 'raoul',
    'raymond', 'regis', 'remi', 'rene', 'robert', 'roger', 'roland',
    'romain', 'ruben', 'sebastien', 'serge', 'simon', 'stanislas', 'stephane',
    'sylvain', 'tanguy', 'thierry', 'thomas', 'timothee', 'valentin',
    'vincent', 'wilfried', 'xavier', 'yann', 'yves', 'zacharie', 'abraham',
    'achille', 'adrien', 'alain', 'albert', 'alexandre', 'alexis', 'alphonse',
    'amaury', 'anastase', 'antoine', 'armand', 'arsene', 'arthur', 'augustin',
    'aurelien', 'barthélémy', 'basile', 'benjamin', 'bernard', 'blaise',
    'boris', 'bruno', 'calixte', 'carmel', 'cedric', 'celestin', 'charles',
    'christophe', 'claude', 'clement', 'cyrille', 'damien', 'denis',
    'didier', 'dieudonne', 'dimitri', 'donald', 'edmond', 'edouard', 'elie',
    'emile', 'eric', 'ernest', 'etienne', 'eugene', 'fabrice', 'felix',
    'fernand', 'firmin', 'florian', 'franck', 'francois', 'gabriel',
    'gaetan', 'georges', 'gerard', 'gilbert', 'gilles', 'gregoire',
    'guillaume', 'guy', 'hassan', 'herve', 'honore', 'hubert', 'hugo',
    'ignac', 'isaac', 'ivan', 'james', 'jason', 'jeanluc', 'jocelyn',
    'jonas', 'jordan', 'joseph', 'josue', 'jules', 'julien', 'justin',
    'kevin', 'laurent', 'lazare', 'leo', 'leon', 'lionel', 'loic', 'lucas',
    'ludovic', 'malick', 'manuel', 'marc', 'martin', 'mathias', 'matthieu',
    'medard', 'mensah', 'mere', 'mohammed', 'morgan', 'napoleon', 'nathan',
    'nestor', 'nolan', 'odilon', 'omar', 'oscar', 'othniel', 'pape',
    'patrice', 'paul', 'raphael', 'rodrigue', 'sacha', 'salomon', 'sam',
    'sami', 'samy', 'saul', 'sedrick', 'souleymane', 'spencer', 'stanley',
    'tresor', 'ulrich', 'valery', 'victor', 'wael', 'william', 'yacouba',
    'yahaya', 'youssouf', 'zachary', 'zephirin',
    # Compléments issus des listes réelles.
    'yvan', 'chris', 'steven', 'howel', 'jonathan', 'habib', 'jedidia',
    'johann', 'oumar', 'eliakim', 'ahmed', 'ndudi', 'wonnan', 'aduko',
    'pontchey', 'gningneri', 'kakou', 'hetobi', 'galla', 'yissoné',
    'batebe', 'ousamne', 'ezekias', 'levy',
}

# Suffixes typiquement féminins (français / noms composés).
_SUFFIXES_F = ('ette', 'elle', 'ienne', 'eline', 'ine', 'inne', 'ande',
               'ence', 'ance', 'euse', 'trice', 'ise', 'ize', 'ette',
               'ina', 'yna', 'elle', 'ette')

# Terminaisons typiquement masculines.
_SUFFIXES_M = ('el', 'al', 'er', 'ir', 'ur', 'in', 'on', 'an', 'en',
               'ard', 'ier', 'eur', 'eil', 'ois')


def _normaliser(texte):
    """Minuscule, sans accent ni apostrophe ni tiret."""
    if not texte:
        return ''
    sans_accent = ''.join(
        c for c in normalize('NFD', str(texte))
        if normalize('NFD', c)[0] not in ('\u0300', '\u0301', '\u0302', '\u0303',
                                          '\u0308', '\u030c', '\u0327')
    )
    return sans_accent.lower().replace("'", '').replace('’', '').replace('-', '')


def deduire_sexe(prenom):
    """Retourne 'F', 'G' (masculin) ou '' si le sexe reste indéterminé.

    On teste d'abord chaque prénom dans le dictionnaire, puis on retombe sur
    une heuristique de suffixe appliquée au premier prénom.
    """
    if not prenom:
        return ''

    jetons = [j for j in str(prenom).replace('-', ' ').split() if j]

    # 1) Dictionnaire, du prénom le plus spécifique au plus général.
    for jeton in jetons:
        cle = _normaliser(jeton)
        if not cle:
            continue
        if cle in FEMININS:
            return 'F'
        if cle in MASCULINS:
            return 'G'

    # 2) Heuristique de suffixe sur le premier prénom.
    premier = _normaliser(jetons[0]) if jetons else ''
    if premier:
        for suffixe in _SUFFIXES_F:
            if premier.endswith(suffixe):
                return 'F'
        if premier.endswith('a'):
            return 'F'
        for suffixe in _SUFFIXES_M:
            if premier.endswith(suffixe):
                return 'G'

    return ''


# Normalisation une fois pour toutes : les dictionnaires sont comparés à des
# clés sans accent ni apostrophe, comme celles produites par `_normaliser`.
FEMININS = {cle for cle in (_normaliser(n) for n in FEMININS) if cle}
MASCULINS = {cle for cle in (_normaliser(n) for n in MASCULINS) if cle}
