"""Remet l'événement à zéro sans toucher aux comptes des étudiants.

Usage ::

    python manage.py remettre_a_zero
    python manage.py remettre_a_zero --garder-etudiants

Sert à enchaîner les simulations : on efface les réponses et les
associations, on remet la phase à « inscription », mais les 127 étudiants
gardent leurs identifiants et leurs mots de passe.

⚠️ Sans ``--garder-etudiants``, les étudiants eux-mêmes sont **conservés**
(défaut). L'option existe surtout pour rendre l'intention explicite.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from parrainage.models import (
    DemandeForcage, Etudiant, ParametreEvenement, ReponseQuestionnaire,
)


class Command(BaseCommand):
    help = ("Efface réponses et associations, remet la phase à « inscription », "
            "sans supprimer les comptes étudiants.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--garder-etudiants', action='store_true',
            help="Ne touche pas aux étudiants (comportement par défaut).",
        )
        parser.add_argument(
            '--oui', action='store_true',
            help="Ne demande pas de confirmation.",
        )

    def handle(self, *args, **options):
        # Récapitulatif de ce qui va être effacé.
        nb_reponses = ReponseQuestionnaire.objects.count()
        nb_assoc = DemandeForcage.objects.count()
        nb_ayant_repondu = Etudiant.objects.filter(
            a_valide_questionnaire=True).count()

        if not options['oui'] and (nb_reponses or nb_assoc or nb_ayant_repondu):
            self.stdout.write("Vont être effacés :")
            self.stdout.write(f"   - {nb_reponses} questionnaire(s)")
            self.stdout.write(f"   - {nb_assoc} association(s)")
            self.stdout.write(f"   - {nb_ayant_repondu} étudiant(s) remis à "
                              "« n'a pas répondu »")
            self.stdout.write("")
            reponse = input("Confirmer ? [o/N] ").strip().lower()
            if reponse not in ('o', 'oui', 'y', 'yes'):
                self.stdout.write(self.style.WARNING("Annulé."))
                return

        self._executer()
        self._resume()

    @transaction.atomic
    def _executer(self):
        ReponseQuestionnaire.objects.all().delete()
        DemandeForcage.objects.all().delete()
        Etudiant.objects.filter(a_valide_questionnaire=True).update(
            a_valide_questionnaire=False
        )

        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.INSCRIPTION
        p.revelation_declenchee_manuellement = False
        p.save()

    def _resume(self):
        l1 = Etudiant.objects.filter(niveau='L1').count()
        l3 = Etudiant.objects.filter(niveau='L3').count()
        avec_id = Etudiant.objects.exclude(identifiant__isnull=True).count()

        self.stdout.write(self.style.SUCCESS("\nBase remise à zéro."))
        self.stdout.write(f"   Étudiants conservés : {l1} L1, {l3} L3 "
                          f"({avec_id} avec identifiant)")
        self.stdout.write(f"   Questionnaires      : "
                          f"{ReponseQuestionnaire.objects.count()}")
        self.stdout.write(f"   Associations        : "
                          f"{DemandeForcage.objects.count()}")
        self.stdout.write(f"   Phase               : inscription "
                          "(révélation non déclenchée)")
        self.stdout.write("\nPrêt pour une nouvelle simulation.")
