"""Remet l'événement à zéro. Fonctionne aussi en ligne.

Usage ::

    python manage.py remettre_a_zero              # demande confirmation
    python manage.py remettre_a_zero --oui        # sans confirmation
    python manage.py remettre_a_zero --tout       # efface AUSSI les comptes

Par défaut, les étudiants et leurs identifiants sont **conservés** : seules
les réponses, les associations et la phase sont remises à zéro. C'est ce
qu'il faut entre deux tests.

``--tout`` va plus loin et supprime les étudiants eux-mêmes (comptes,
identifiants, photos). À n'utiliser que pour repartir d'une page blanche.

⚠️ En ligne, la commande demande une confirmation renforcée : il n'y a pas
de sauvegarde automatique.
"""

import sys

from django.core.management.base import BaseCommand
from django.db import transaction

from parrainage.models import (
    DemandeForcage, Etudiant, ParametreEvenement, ReponseQuestionnaire,
)


def _forcer_utf8():
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


class Command(BaseCommand):
    help = ("Efface réponses, associations et remet la phase à « inscription », "
            "sans supprimer les comptes étudiants.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--oui', action='store_true',
            help="Ne pas demander de confirmation (utile en script).",
        )
        parser.add_argument(
            '--tout', action='store_true',
            help="Supprime AUSSI les étudiants, leurs comptes et leurs photos.",
        )

    def handle(self, *args, **options):
        _forcer_utf8()

        nb_reponses = ReponseQuestionnaire.objects.count()
        nb_assoc = DemandeForcage.objects.count()
        nb_valides = Etudiant.objects.filter(a_valide_questionnaire=True).count()
        nb_etudiants = Etudiant.objects.count()

        self._avertir(nb_reponses, nb_assoc, nb_valides, nb_etudiants,
                      tout=options['tout'])

        if not options['oui'] and not self._confirmer(options['tout']):
            self.stdout.write(self.style.WARNING("Annulé — rien n'a été modifié."))
            return

        self._executer(tout=options['tout'])
        self._resume()

    # ------------------------------------------------------------- Étapes

    def _avertir(self, nb_reponses, nb_assoc, nb_valides, nb_etudiants, tout):
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Vont être supprimés :"))
        self.stdout.write(f"   - {nb_reponses} questionnaire(s) et leurs réponses")
        self.stdout.write(f"   - {nb_assoc} association(s) prioritaire(s)")
        self.stdout.write(f"   - l'état « a répondu » de {nb_valides} étudiant(s)")
        if tout:
            self.stdout.write(self.style.ERROR(
                f"   - LES {nb_etudiants} ÉTUDIANTS, leurs comptes et leurs "
                "identifiants"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"   (les {nb_etudiants} étudiants et leurs identifiants sont "
                "CONSERVÉS)"))
        self.stdout.write("")

    def _confirmer(self, tout):
        attendu = 'SUPPRIMER TOUT' if tout else 'oui'
        question = (f"Tapez « {attendu} » pour confirmer : "
                    if tout else "Confirmer ? [o/N] ")
        try:
            reponse = input(question).strip()
        except EOFError:
            return False
        if tout:
            return reponse == attendu
        return reponse.lower() in ('o', 'oui', 'y', 'yes')

    @transaction.atomic
    def _executer(self, tout=False):
        ReponseQuestionnaire.objects.all().delete()
        DemandeForcage.objects.all().delete()

        if tout:
            # Les comptes utilisateurs liés partent avec les étudiants.
            Etudiant.objects.all().delete()
        else:
            Etudiant.objects.filter(a_valide_questionnaire=True).update(
                a_valide_questionnaire=False)

        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.INSCRIPTION
        p.revelation_declenchee_manuellement = False
        p.save()

    def _resume(self):
        l1 = Etudiant.objects.filter(niveau='L1').count()
        l3 = Etudiant.objects.filter(niveau='L3').count()
        avec_id = Etudiant.objects.exclude(identifiant__isnull=True).count()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Base remise à zéro."))
        self.stdout.write(f"   Étudiants        : {l1} L1, {l3} L3 "
                          f"({avec_id} avec identifiant)")
        self.stdout.write(f"   Questionnaires   : "
                          f"{ReponseQuestionnaire.objects.count()}")
        self.stdout.write(f"   Associations     : "
                          f"{DemandeForcage.objects.count()}")
        self.stdout.write("   Phase            : inscription "
                          "(révélation non déclenchée)")
        self.stdout.write("")
        self.stdout.write("Prêt pour un nouveau test.")
