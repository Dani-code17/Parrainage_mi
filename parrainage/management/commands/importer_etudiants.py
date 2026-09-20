"""Import des listes d'étudiants et génération des identifiants d'accès.

Usage ::

    python manage.py importer_etudiants                 # importe puis génère les comptes
    python manage.py importer_etudiants --reset         # repart de zéro
    python manage.py importer_etudiants --sans-comptes  # importe seulement
    python manage.py importer_etudiants --mot-de-passe  # régénère les mots de passe
    python manage.py importer_etudiants --export identifiants.csv
"""

import csv
import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from parrainage.identifiants import creer_comptes, exporter_csv
from parrainage.models import Etudiant
from parrainage.prenoms import deduire_sexe

# ::: Hachage rapide
# Django hache les mots de passe volontairement lentement (~0,3 s avec PBKDF2
# à 1 000 000 d'itérations). Sur 122 comptes, cela dépasse les deux minutes.
# Pour ces comptes créés en masse par l'équipe, on utilise MD5, nettement plus
# rapide et suffisant ici : les mots de passe sont distribués en clair sur
# papier et changés au premier usage. Django sait vérifier ce format.
HACHAGE_RAPIDE = 'django.contrib.auth.hashers.MD5PasswordHasher'

# Fichiers de listes attendus (chemin relatif au dossier fourni).
FICHIERS = [
    ('L1.csv', 'L1'),
    ('L3A.csv', 'L3'),
    ('L3B.csv', 'L3'),
]

# Domaine utilisé pour forger l'adresse e-mail des étudiants.
DOMAINE = 'miage.ci'


def _forcer_utf8():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def _email_de(nom, prenom, domaine=DOMAINE):
    """Adresse e-mail de service : prenom.nom@domaine (normalisée)."""
    import unicodedata

    def net(texte):
        texte = unicodedata.normalize('NFD', str(texte or ''))
        texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
        return ''.join(c for c in texte.lower() if c.isalnum())

    p = net(prenom.split()[0] if prenom.split() else prenom)
    n = net(nom)
    return f"{p}.{n}@{domaine}" if p and n else ''


class Command(BaseCommand):
    help = "Importe les listes d'étudiants et génère leurs identifiants de connexion."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help="Supprime les étudiants importés avant de recommencer.")
        parser.add_argument('--sans-comptes', action='store_true',
                            help="Importe les profils sans créer les comptes d'accès.")
        parser.add_argument('--mot-de-passe', action='store_true',
                            help="Régénère un mot de passe pour les comptes existants.")
        parser.add_argument('--export', default=None,
                            help="Chemin du fichier CSV où écrire les identifiants.")
        parser.add_argument('--dossier', default='donnees',
                            help="Dossier contenant les listes (défaut : donnees).")

    def handle(self, *args, **options):
        _forcer_utf8()
        dossier = options['dossier']

        if options['reset']:
            self._reinitialiser()

        importes = self._importer(dossier)
        self._resume_import(importes)

        if options['sans_comptes']:
            self.stdout.write(self.style.WARNING(
                "\n--sans-comptes : aucun identifiant n'a été généré."))
            return

        resultats = self._generer_comptes(reinitialiser=options['mot_de_passe'])
        self._resume_comptes(resultats)

        chemin = options['export']
        if chemin:
            self._exporter(resultats, chemin)
        else:
            self._afficher_apercu(resultats)

    # ------------------------------------------------------------- Étapes

    def _reinitialiser(self):
        """Retire les étudiants, leurs comptes et leurs questionnaires."""
        from django.contrib.auth.models import User
        from parrainage.models import DemandeForcage, ReponseQuestionnaire

        emails = list(Etudiant.objects.values_list('email', flat=True))
        DemandeForcage.objects.filter(demandeur__email__in=emails).delete()
        DemandeForcage.objects.filter(cible__email__in=emails).delete()
        ReponseQuestionnaire.objects.filter(etudiant__email__in=emails).delete()
        Etudiant.objects.filter(email__in=emails).delete()
        # Les comptes créés pour ces étudiants sont supprimés aussi.
        User.objects.filter(username__in=list(
            Etudiant.objects.filter(user__isnull=False).values_list('identifiant', flat=True)
        )).delete()
        for u in User.objects.filter(etudiant__isnull=True).exclude(is_superuser=True):
            u.delete()
        self.stdout.write(self.style.WARNING("Données précédentes supprimées.\n"))

    @transaction.atomic
    def _importer(self, dossier):
        """Lit les CSV et crée les étudiants manquants."""
        compteur = {}
        for nom_fichier, niveau in FICHIERS:
            chemin = os.path.join(dossier, nom_fichier)
            if not os.path.exists(chemin):
                raise CommandError(f"Fichier introuvable : {chemin}")

            crees = 0
            ignores = 0
            with open(chemin, encoding='utf-8-sig') as flux:
                for ligne in csv.DictReader(flux):
                    nom = (ligne.get('nom') or '').strip().upper()
                    prenom = (ligne.get('prenom') or '').strip()
                    groupe = (ligne.get('groupe') or niveau).strip()
                    if not nom or not prenom:
                        continue

                    email = _email_de(nom, prenom)
                    if not email:
                        continue

                    if Etudiant.objects.filter(email=email).exists():
                        ignores += 1
                        continue

                    sexe = deduire_sexe(prenom)
                    Etudiant.objects.create(
                        nom=nom, prenom=prenom, email=email, niveau=niveau,
                        groupe=groupe, sexe=sexe, sexe_deduit=True,
                    )
                    crees += 1

            compteur[nom_fichier] = (crees, ignores)
        return compteur

    def _resume_import(self, importes):
        self.stdout.write(self.style.MIGRATE_HEADING("\n1. IMPORT DES LISTES"))
        total = 0
        for fichier, (crees, ignores) in importes.items():
            total += crees
            detail = f"{crees} créés"
            if ignores:
                detail += f", {ignores} déjà présents"
            self.stdout.write(f"   {fichier:<16} {detail}")
        self.stdout.write(f"   {'TOTAL':<16} {total} nouveaux étudiants")

        l1 = Etudiant.objects.filter(niveau='L1').count()
        l3 = Etudiant.objects.filter(niveau='L3').count()
        sans_sexe = Etudiant.objects.filter(sexe='').count()
        self.stdout.write(f"   En base : {l1} L1, {l3} L3"
                          + (f", {sans_sexe} sexe(s) à renseigner" if sans_sexe else ""))

    def _generer_comptes(self, reinitialiser=False):
        etudiants = list(Etudiant.objects.order_by('niveau', 'nom', 'prenom'))
        # Hachage rapide le temps de la génération en masse.
        anciens = settings.PASSWORD_HASHERS
        settings.PASSWORD_HASHERS = [HACHAGE_RAPIDE]
        try:
            return creer_comptes(etudiants, reinitialiser=reinitialiser)
        finally:
            settings.PASSWORD_HASHERS = anciens

    def _resume_comptes(self, resultats):
        crees = [r for r in resultats if r['cree']]
        self.stdout.write(self.style.MIGRATE_HEADING("\n2. COMPTES D'ACCÈS"))
        self.stdout.write(f"   {len(crees)} compte(s) créé(s) / mis à jour")
        self.stdout.write(f"   {len(resultats) - len(crees)} compte(s) déjà en place")

    def _exporter(self, resultats, chemin):
        with open(chemin, 'w', newline='', encoding='utf-8-sig') as flux:
            flux.write(exporter_csv(resultats))
        self.stdout.write(self.style.SUCCESS(f"\nIdentifiants exportés : {chemin}"))

    def _afficher_apercu(self, resultats):
        self.stdout.write(self.style.MIGRATE_HEADING("\n3. APERÇU DES IDENTIFIANTS"))
        self.stdout.write(f"   {'Nom':<28}{'Niveau':<8}{'Identifiant':<20}{'Mot de passe'}")
        for r in resultats[:12]:
            e = r['etudiant']
            nom = f"{e.nom} {e.prenom_usuel}"[:26]
            self.stdout.write(f"   {nom:<28}{e.niveau:<8}"
                              f"{r['identifiant'] or '-':<20}{r['mot_de_passe'] or '(inchangé)'}")
        if len(resultats) > 12:
            self.stdout.write(f"   … et {len(resultats) - 12} autres.")
        self.stdout.write(
            "\n   Pour obtenir la liste complète :\n"
            "       python manage.py importer_etudiants --export identifiants.csv\n"
            "   Ou depuis l'admin : Étudiants → action « Exporter les identifiants »."
        )
