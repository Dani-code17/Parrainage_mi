"""Remplit les questionnaires des étudiants (données de démonstration).

Usage ::

    python manage.py remplir_questionnaires              # tous les étudiants sans réponses
    python manage.py remplir_questionnaires --reset      # réécrit tout le monde
    python manage.py remplir_questionnaires --niveau L1  # seulement les L1
    python manage.py remplir_questionnaires --apercu     # ne rien écrire, juste montrer

Les réponses sont **déterministes** : la graine dérive de l'e-mail de
l'étudiant, donc relancer la commande redonne exactement les mêmes réponses.

⚠️ Données de DÉMONSTRATION : à ne pas confondre avec de vraies réponses.
"""

import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from parrainage.models import Etudiant, ReponseQuestionnaire
from parrainage.questionnaires import generer_avec_profil


def _forcer_utf8():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def _graine(etudiant):
    """Graine stable et propre à chaque étudiant.

    On n'utilise pas `hash()` : Python randomise le hachage des chaînes à
    chaque exécution, ce qui rendrait les réponses différentes d'un lancement
    à l'autre. Un condensat MD5 garantit la reproductibilité.
    """
    import hashlib
    empreinte = hashlib.md5(etudiant.email.encode('utf-8')).hexdigest()
    return int(empreinte[:8], 16)


class Command(BaseCommand):
    help = "Remplit les questionnaires des étudiants avec des réponses cohérentes (démo)."

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help="Réécrit aussi les questionnaires déjà remplis.")
        parser.add_argument('--niveau', choices=['L1', 'L3'], default=None,
                            help="Ne traiter qu'un niveau.")
        parser.add_argument('--apercu', action='store_true',
                            help="Affiche le résultat sans rien enregistrer.")
        parser.add_argument('--exemple', default=None,
                            help="E-mail d'un étudiant dont on affiche le détail.")

    def handle(self, *args, **options):
        _forcer_utf8()

        etudiants = Etudiant.objects.all().order_by('niveau', 'nom', 'prenom')
        if options['niveau']:
            etudiants = etudiants.filter(niveau=options['niveau'])
        etudiants = list(etudiants)

        if not options['reset']:
            deja = set(
                ReponseQuestionnaire.objects
                .filter(etudiant__in=etudiants)
                .values_list('etudiant_id', flat=True)
            )
            etudiants = [e for e in etudiants if e.id not in deja]

        if not etudiants:
            self.stdout.write(self.style.WARNING(
                "Aucun étudiant à traiter (utilisez --reset pour réécrire)."))
            return

        if options['apercu']:
            self._apercu(etudiants)
            return

        compteur = self._remplir(etudiants)
        self._resume(compteur, options['exemple'])

    # ------------------------------------------------------------- Étapes

    @transaction.atomic
    def _remplir(self, etudiants):
        compteur = {}
        for etudiant in etudiants:
            reponses, profil = generer_avec_profil(
                _graine(etudiant), etudiant.niveau)
            ReponseQuestionnaire.objects.update_or_create(
                etudiant=etudiant,
                defaults={'donnees': reponses, 'verrouille': True},
            )
            if not etudiant.a_valide_questionnaire:
                etudiant.a_valide_questionnaire = True
                etudiant.save(update_fields=['a_valide_questionnaire'])

            compteur[profil] = compteur.get(profil, 0) + 1
        return compteur

    def _apercu(self, etudiants):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nAPERÇU ({len(etudiants)} étudiant(s), rien n'a été enregistré)"))
        for e in etudiants[:8]:
            r, profil = generer_avec_profil(_graine(e), e.niveau)
            self.stdout.write(f"   {e.niveau} {e.nom[:18]:<18} "
                              f"{profil:<12} {len(r)} réponses")
        if len(etudiants) > 8:
            self.stdout.write(f"   … et {len(etudiants) - 8} autres.")

    def _resume(self, compteur, exemple=None):
        total = sum(compteur.values())
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{total} questionnaire(s) rempli(s)"))
        self.stdout.write("   Répartition des profils :")
        for profil, nombre in sorted(compteur.items(), key=lambda x: -x[1]):
            self.stdout.write(f"      {profil:<14} {nombre:>4}")

        if exemple:
            e = Etudiant.objects.filter(email=exemple).first()
            if not e:
                self.stdout.write(self.style.WARNING(
                    f"   Étudiant introuvable : {exemple}"))
            else:
                q = getattr(e, 'questionnaire', None)
                if q:
                    self.stdout.write(f"\n   Détail de {e.nom} {e.prenom} :")
                    for question, rendu in q.reponses_lisibles()[:6]:
                        self.stdout.write(f"      {question.code.upper()} : {rendu}")

        self.stdout.write(
            "\n   Ces réponses sont des données de démonstration, "
            "à remplacer par les vraies réponses des étudiants.")
