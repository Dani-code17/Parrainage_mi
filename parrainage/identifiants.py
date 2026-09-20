"""Génération et export des identifiants de connexion des étudiants.

L'équipe crée les comptes elle-même : un identifiant court (ex. « k.tanoh »)
et un mot de passe aléatoire lisible sont générés pour chaque étudiant, puis
distribués via un export CSV/Excel.
"""

import csv
import io
import secrets
import unicodedata

from django.contrib.auth.models import User
from django.db import transaction

from parrainage.models import Etudiant

# Alphabet sans caractères ambigus (pas de O/0, I/l/1).
_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_CHIFFRES = '23456789'


def _sans_accent(texte):
    if not texte:
        return ''
    decompose = unicodedata.normalize('NFD', str(texte))
    return ''.join(
        c for c in decompose
        if unicodedata.category(c) != 'Mn'
    )


def _nettoyer_jeton(texte):
    """Minuscule, sans accent, ne garde que lettres et chiffres."""
    texte = _sans_accent(texte).lower()
    return ''.join(c for c in texte if c.isalnum())


def generer_mot_de_passe(longueur=10):
    """Mot de passe aléatoire lisible : lettres + chiffres, sans ambiguïté."""
    if longueur < 6:
        longueur = 6
    # Au moins un chiffre et une majuscule, pour la robustesse.
    caracteres = [
        secrets.choice(_ALPHABET),
        secrets.choice(_CHIFFRES),
        secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ'),
    ]
    reste = longueur - len(caracteres)
    pool = _ALPHABET + _CHIFFRES
    caracteres += [secrets.choice(pool) for _ in range(reste)]
    # Mélange (Fisher-Yates avec une source cryptographique).
    for i in range(len(caracteres) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        caracteres[i], caracteres[j] = caracteres[j], caracteres[i]
    return ''.join(caracteres)


def construire_identifiant(etudiant, deja_pris=None):
    """Construit un identifiant court unique du type « initiale.prenom_nom ».

    En cas de collision, un suffixe numérique est ajouté (k.tanoh2, k.tanoh3…).
    `deja_pris` est un ensemble d'identifiants déjà attribués (en plus de ceux
    présents en base).
    """
    deja_pris = deja_pris if deja_pris is not None else set()

    nom = _nettoyer_jeton(etudiant.nom)
    prenom = _nettoyer_jeton(etudiant.prenom_usuel or etudiant.prenom)
    initiale = prenom[0] if prenom else (nom[0] if nom else 'x')

    # Identifiant de base : initiale du prénom + nom de famille.
    base = f"{initiale}.{nom}" if nom else f"{initiale}.{prenom}"
    if not base or base == '.':
        base = f"{initiale}." + _nettoyer_jeton(etudiant.email.split('@')[0])
    base = base[:28] or 'etudiant'

    candidat = base
    suffixe = 1
    while (candidat in deja_pris
           or Etudiant.objects.filter(identifiant=candidat).exists()):
        suffixe += 1
        candidat = f"{base}{suffixe}"
    deja_pris.add(candidat)
    return candidat


@transaction.atomic
def creer_comptes(etudiants, reinitialiser=False):
    """Crée (ou met à jour) un compte d'accès pour chaque étudiant fourni.

    Retourne une liste de dicts :
        {'etudiant', 'identifiant', 'mot_de_passe', 'cree'}

    - Si l'étudiant a déjà un compte et que `reinitialiser` est faux, il est
      ignoré (mot_de_passe laissé à None).
    - Si `reinitialiser` est vrai, un nouveau mot de passe est généré.
    """
    resultats = []
    deja_pris = set(
        Etudiant.objects.exclude(identifiant__isnull=True)
        .exclude(identifiant='')
        .values_list('identifiant', flat=True)
    )

    for etudiant in etudiants:
        a_deja_un_compte = bool(etudiant.user_id)

        if a_deja_un_compte and not reinitialiser:
            resultats.append({
                'etudiant': etudiant,
                'identifiant': etudiant.identifiant,
                'mot_de_passe': None,
                'cree': False,
            })
            continue

        # Identifiant : on conserve celui déjà attribué, sinon on en forge un.
        identifiant = etudiant.identifiant
        if not identifiant:
            identifiant = construire_identifiant(etudiant, deja_pris)
        else:
            deja_pris.add(identifiant)

        mot_de_passe = generer_mot_de_passe()

        user = etudiant.user
        if user is None:
            user = User(username=identifiant)
        user.username = identifiant
        user.email = etudiant.email
        user.first_name = etudiant.prenom
        user.last_name = etudiant.nom
        user.set_password(mot_de_passe)
        user.save()

        etudiant.user = user
        etudiant.identifiant = identifiant
        etudiant.save(update_fields=['user', 'identifiant'])

        resultats.append({
            'etudiant': etudiant,
            'identifiant': identifiant,
            'mot_de_passe': mot_de_passe,
            'cree': True,
        })

    return resultats


def exporter_csv(resultats):
    """Retourne le contenu CSV (str) des identifiants générés."""
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=';')
    ecrivain.writerow(['Nom', 'Prenoms', 'Niveau', 'Groupe',
                       'Email', 'Identifiant', 'Mot de passe'])
    for r in resultats:
        e = r['etudiant']
        ecrivain.writerow([
            e.nom, e.prenom, e.niveau, e.groupe or '',
            e.email, r['identifiant'] or '', r['mot_de_passe'] or '(inchangé)',
        ])
    return tampon.getvalue()
