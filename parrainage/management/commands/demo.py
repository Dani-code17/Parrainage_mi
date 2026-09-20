"""Commande de démonstration : étudiants fictifs + tracé de la logique L1 / L3.

Usage ::

    python manage.py demo --reset          # recrée les données puis trace
    python manage.py demo                  # alimente/trace sans tout effacer
    python manage.py demo --accepter-preference
    python manage.py demo --sans-trace

La commande est idempotente : relancée sans ``--reset``, elle met à jour les
mêmes profils au lieu d'en créer des doublons.
"""

import sys
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from parrainage import demo_data
from parrainage.matching import (
    SCORE_FORCE_INTERNE,
    _bonus_mixte,
    _reponses_questionnaire,
    _score_quiz,
    calculer_matchs,
    question_commune,
    score_affichable,
)
from parrainage.models import (
    DemandeForcage,
    Etudiant,
    ParametreEvenement,
    ReponseQuestionnaire,
)

LARGEUR = 76


def _forcer_utf8():
    """Évite les plantages d'encodage sur la console Windows (cp1252)."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


class Command(BaseCommand):
    help = (
        "Crée des étudiants fictifs et trace le parcours d'un L1 et d'un L3 "
        "à travers les 4 phases de l'événement (test de la logique)."
    )

    # ------------------------------------------------------------------ CLI

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help="Supprime les données de démo existantes avant de les recréer.",
        )
        parser.add_argument(
            '--accepter-preference', action='store_true',
            help="Passe la préférence de démo au statut « acceptée ».",
        )
        parser.add_argument(
            '--sans-trace', action='store_true',
            help="Alimente la base et configure l'événement, sans afficher le tracé.",
        )
        parser.add_argument(
            '--l1', default=demo_data.L1_TRACE,
            help="E-mail du L1 à suivre dans le tracé.",
        )
        parser.add_argument(
            '--l3', default=demo_data.L3_TRACE,
            help="E-mail du L3 à suivre dans le tracé.",
        )

    # -------------------------------------------------------------- Entrée

    def handle(self, *args, **options):
        _forcer_utf8()

        self._titre("DÉMO — PARRAINAGE L1 x L3 : étudiants fictifs + tracé de la logique")

        etudiants = self._semer(reset=options['reset'])
        self._afficher_semis(etudiants, reset=options['reset'])

        self._configurer_evenement()
        demande = self._preparer_preference(
            etudiants, accepter=options['accepter_preference'])
        self._afficher_preference(demande)

        if options['sans_trace']:
            self._afficher_aide(etudiants)
            return

        l1 = self._recuperer(options['l1'], Etudiant.Niveau.L1)
        l3 = self._recuperer(options['l3'], Etudiant.Niveau.L3)
        if l1 is None or l3 is None:
            return

        self._tracer_parcours_l1(l1)
        self._tracer_parcours_l3(l3)
        self._afficher_recapitulatif()
        self._afficher_observations()
        self._afficher_aide(etudiants)

    # ------------------------------------------------------------- Helpers

    def _ecrire(self, texte=''):
        self.stdout.write(texte)

    def _titre(self, texte):
        self._ecrire()
        self._ecrire('=' * LARGEUR)
        self._ecrire(f'  {texte}')
        self._ecrire('=' * LARGEUR)

    def _sous_titre(self, texte):
        self._ecrire()
        self._ecrire('-' * LARGEUR)
        self._ecrire(f'  {texte}')
        self._ecrire('-' * LARGEUR)

    def _recuperer(self, email, niveau):
        try:
            return Etudiant.objects.get(email=email)
        except Etudiant.DoesNotExist:
            self._ecrire()
            self._ecrire(f"  /!\\ Aucun étudiant {niveau} avec l'e-mail « {email} ».")
            self._ecrire("      Lancez d'abord :  python manage.py demo")
            return None

    # ---------------------------------------------------------------- Semis

    @transaction.atomic
    def _semer(self, reset=False):
        if reset:
            emails = [
                demo_data.email_de(prenom, nom)
                for (nom, prenom, _, _, _) in demo_data.ETUDIANTS
            ]
            DemandeForcage.objects.filter(demandeur__email__in=emails).delete()
            DemandeForcage.objects.filter(cible__email__in=emails).delete()
            ReponseQuestionnaire.objects.filter(etudiant__email__in=emails).delete()
            Etudiant.objects.filter(email__in=emails).delete()
            User.objects.filter(username__in=emails).delete()

        etudiants = {}
        for nom, prenom, sexe, niveau, reponses in demo_data.ETUDIANTS:
            etudiants[demo_data.email_de(prenom, nom)] = self._creer_etudiant(
                nom, prenom, sexe, niveau, reponses)
        return etudiants

    def _creer_etudiant(self, nom, prenom, sexe, niveau, reponses):
        """Crée (ou met à jour) un étudiant, son compte et son questionnaire."""
        email = demo_data.email_de(prenom, nom)

        etudiant, _ = Etudiant.objects.update_or_create(
            email=email,
            defaults={
                'nom': nom,
                'prenom': prenom,
                'sexe': sexe,
                'niveau': niveau,
                'a_valide_questionnaire': True,
                'est_eligible': True,
            },
        )

        user, _ = User.objects.get_or_create(username=email, defaults={'email': email})
        user.email = email
        user.first_name = prenom
        user.last_name = nom
        user.set_password(demo_data.MOT_DE_PASSE)
        user.save()
        etudiant.user = user
        etudiant.save(update_fields=['user'])

        ReponseQuestionnaire.objects.update_or_create(
            etudiant=etudiant,
            defaults={f'q{i + 1}': valeur for i, valeur in enumerate(reponses)},
        )
        return etudiant

    def _configurer_evenement(self):
        """Place l'événement en phase « inscription » avec des dates cohérentes."""
        maintenant = timezone.now()
        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.INSCRIPTION
        p.date_fermeture_inscriptions = maintenant + timedelta(days=2)
        p.date_heure_teasing = maintenant + timedelta(days=2, hours=8)
        p.date_heure_revelation = maintenant + timedelta(days=2, hours=18)
        p.revelation_declenchee_manuellement = False
        p.save()

    def _preparer_preference(self, etudiants, accepter=False):
        l3 = etudiants[demo_data.PREFERENCE_L3]
        l1 = etudiants[demo_data.PREFERENCE_L1]
        statut = (DemandeForcage.Statut.ACCEPTE if accepter
                  else DemandeForcage.Statut.EN_ATTENTE)
        demande, _ = DemandeForcage.objects.update_or_create(
            demandeur=l3, cible=l1, defaults={'statut': statut})
        return demande

    # -------------------------------------------------------------- Journal

    def _afficher_semis(self, etudiants, reset=False):
        self._sous_titre("1. DONNÉES FICTIVES")
        if reset:
            self._ecrire("  (option --reset : les données de démo précédentes ont été supprimées)")
        l1s = [e for e in etudiants.values() if e.est_L1]
        l3s = [e for e in etudiants.values() if e.est_L3]
        self._ecrire(f"  {len(l1s)} L1 et {len(l3s)} L3 créés/mis à jour, "
                     f"chacun avec un questionnaire complet (15/15).")
        self._ecrire("  Phase de l'événement : inscription "
                     "(fermeture dans 2 jours, teasing puis révélation).")

    def _afficher_preference(self, demande):
        self._sous_titre("2. PRÉFÉRENCE DE BINÔME (exprimée par un L3)")
        self._ecrire(f"  {demande.demandeur.nom_complet} (L3)  ->  "
                     f"{demande.cible.nom_complet} (L1)")
        self._ecrire(f"  Statut : {demande.get_statut_display()}")
        if demande.statut == DemandeForcage.Statut.EN_ATTENTE:
            self._ecrire("  Elle n'influence PAS le matching tant qu'elle n'est pas acceptée.")
            self._ecrire("  Pour l'accepter : onglet admin « Demandes », action, "
                         "ou relancer avec --accepter-preference.")

    # ---------------------------------------------------- Tracé parcours L1

    def _tracer_parcours_l1(self, l1):
        reponses = _reponses_questionnaire(l1)
        self._sous_titre(
            f"3. PARCOURS D'UN L1 : {l1.nom_complet} "
            f"({l1.niveau}, {l1.get_sexe_display()}) — {l1.email}")

        self._ecrire()
        self._ecrire("  [1] INSCRIPTION")
        self._ecrire(f"      - Présent dans la liste blanche (import CSV) : oui")
        self._ecrire(f"      - Compte d'accès créé                         : "
                     f"{'oui' if l1.user_id else 'non'}")
        self._ecrire(f"      - Questionnaire                              : "
                     f"{'complet (15/15)' if reponses else 'incomplet'}")

        self._ecrire()
        self._ecrire("  [2] VERROUILLAGE")
        self._ecrire("      - Réponses figées, inscriptions closes.")
        self._ecrire("      - Page de préférences : réservée aux L3 -> un L1 y est renvoyé.")

        self._ecrire()
        self._ecrire("  [3] TEASING (jour J) — indice affiché, noms masqués")
        match = self._match_de(l1)
        if not match:
            self._ecrire("      Aucun match calculé (questionnaire incomplet ?).")
            return
        indice = question_commune(match['l1'], match['l3'])
        if indice:
            numero, reponse, texte = indice
            self._ecrire(f"      Indice : « Q{numero} — {texte} »")
            self._ecrire(f"      (les deux y ont répondu {reponse}/5 ; nom du match non révélé)")

        self._ecrire()
        self._ecrire("  [4] RÉVÉLATION — détail du calcul")
        details = self._details_scores(l1)
        self._ecrire("      Score face à chaque L3  (quiz 70% + bonus mixte 30%) :")
        self._ecrire()
        self._ecrire(f"      {'L3':<22}{'quiz':>7}{'bonus':>8}{'final':>8}")
        for d in details:
            self._ecrire(
                f"      {d['l3'].nom_complet:<22}{d['quiz']:>7.1f}"
                f"{d['bonus']:>8.1f}{d['final']:>8.1f}")
        self._ecrire()
        meilleur = details[0]
        self._ecrire(f"      Meilleur score naturel : {meilleur['l3'].nom_complet} "
                     f"({meilleur['final']:.1f}/100)")

        demande = DemandeForcage.objects.filter(
            cible=l1, statut=DemandeForcage.Statut.ACCEPTE).first()
        if demande:
            paire = next((d for d in details if d['l3'].id == demande.demandeur_id), None)
            self._ecrire(f"      Préférence ACCEPTÉE pour ce L1 : {demande.demandeur.nom_complet}")
            if paire:
                self._ecrire(f"      -> score naturel de cette paire : {paire['final']:.1f}/100, "
                             f"porté au score prioritaire interne ({SCORE_FORCE_INTERNE}).")
            self._ecrire(f"      -> affichage public : 100/100 (aucune mention de priorité).")
        else:
            en_attente = DemandeForcage.objects.filter(
                cible=l1, statut=DemandeForcage.Statut.EN_ATTENTE).first()
            if en_attente:
                paire = next(
                    (d for d in details if d['l3'].id == en_attente.demandeur_id), None)
                score_paire = f"{paire['final']:.1f}/100" if paire else "n/a"
                self._ecrire(
                    f"      Note : une préférence NON acceptée existe "
                    f"({en_attente.demandeur.nom_complet}).")
                self._ecrire(
                    f"      -> si l'équipe l'accepte, ce binôme passe à 100/100 "
                    f"(score naturel actuel : {score_paire}).")

        self._ecrire()
        self._ecrire(f"      MATCH RETENU : {match['l1'].nom_complet}  x  {match['l3'].nom_complet}")
        self._ecrire(f"      Affichage public : « Score de compatibilité : "
                     f"{score_affichable(match['score'])}/100 »")

    # ---------------------------------------------------- Tracé parcours L3

    def _tracer_parcours_l3(self, l3):
        reponses = _reponses_questionnaire(l3)
        self._sous_titre(
            f"4. PARCOURS D'UN L3 : {l3.nom_complet} "
            f"({l3.niveau}, {l3.get_sexe_display()}) — {l3.email}")

        self._ecrire()
        self._ecrire("  [1] INSCRIPTION")
        self._ecrire(f"      - Questionnaire : "
                     f"{'complet (15/15)' if reponses else 'incomplet'}")

        self._ecrire()
        self._ecrire("  [2] VERROUILLAGE")
        self._ecrire("      - Plus aucune nouvelle préférence possible après cette phase.")

        self._ecrire()
        self._ecrire("  [3] PRÉFÉRENCE DE BINÔME (réservée aux L3)")
        demandes = DemandeForcage.objects.filter(demandeur=l3).select_related('cible')
        if not demandes:
            self._ecrire("      Aucune préférence exprimée.")
        for d in demandes:
            self._ecrire(f"      -> {d.cible.nom_complet} (L1) : {d.get_statut_display()}")

        self._ecrire()
        self._ecrire("  [4] RÉVÉLATION — L1 accompagnés par ce L3")
        matchs = [m for m in calculer_matchs() if m['l3'].id == l3.id]
        if not matchs:
            self._ecrire("      Ce L3 n'est le meilleur choix d'aucun L1.")
        for m in matchs:
            self._ecrire(f"      - {m['l1'].nom_complet:<22} "
                         f"score {score_affichable(m['score'])}/100")

    # ------------------------------------------------------------ Annexes

    def _details_scores(self, l1):
        """Détail des scores d'un L1 face à chaque L3 (tri décroissant)."""
        rep_l1 = _reponses_questionnaire(l1)
        lignes = []
        for l3 in Etudiant.objects.filter(niveau=Etudiant.Niveau.L3).order_by('nom'):
            rep_l3 = _reponses_questionnaire(l3)
            quiz = _score_quiz(rep_l1, rep_l3)
            bonus = _bonus_mixte(l1, l3)
            lignes.append({'l3': l3, 'quiz': quiz, 'bonus': bonus,
                           'final': quiz + bonus})
        lignes.sort(key=lambda x: -x['final'])
        return lignes

    def _match_de(self, etudiant):
        """Match retenu pour un étudiant (L1 ou L3), ou None."""
        for m in calculer_matchs():
            if m['l1'].id == etudiant.id or m['l3'].id == etudiant.id:
                return m
        return None

    def _afficher_recapitulatif(self):
        self._sous_titre("5. RÉCAPITULATIF DES BINÔMES (tel qu'affiché publiquement)")
        matchs = sorted(calculer_matchs(),
                        key=lambda m: -score_affichable(m['score']))
        if not matchs:
            self._ecrire("  Aucun binôme calculé.")
            return
        self._ecrire(f"  {'L1':<22}{'L3':<22}{'Score':>8}")
        for m in matchs:
            self._ecrire(f"  {m['l1'].nom_complet:<22}{m['l3'].nom_complet:<22}"
                         f"{score_affichable(m['score']):>6}/100")

    def _afficher_observations(self):
        self._sous_titre("6. OBSERVATIONS SUR LA LOGIQUE")
        matchs = calculer_matchs()
        # Combien de L1 chaque L3 accompagne-t-il ?
        par_l3 = {}
        for m in matchs:
            par_l3.setdefault(m['l3'].id, []).append(m['l1'])
        multiples = {k: v for k, v in par_l3.items() if len(v) > 1}
        if multiples:
            self._ecrire("  - Un même L3 peut être le meilleur choix de plusieurs L1 :")
            for l3_id, l1s in multiples.items():
                l3 = Etudiant.objects.get(id=l3_id)
                noms = ', '.join(l1.nom_complet for l1 in l1s)
                self._ecrire(f"      {l3.nom_complet} <- {noms}")
            self._ecrire("    (l'algorithme ne rend pas les binômes exclusifs)")
        else:
            self._ecrire("  - Chaque L3 est associé à un seul L1 dans ce jeu de données.")

        forces = DemandeForcage.objects.filter(statut=DemandeForcage.Statut.ACCEPTE).count()
        self._ecrire(f"  - Préférences acceptées prises en compte : {forces}.")
        self._ecrire("    Elles portent le binôme à un score interne prioritaire, "
                     "affiché 100/100 sans autre explication.")

    def _afficher_aide(self, etudiants):
        self._titre("POUR TESTER DANS LE NAVIGATEUR")
        self._ecrire(f"  Identifiants : <email affiché ci-dessus> / mot de passe "
                     f"« {demo_data.MOT_DE_PASSE} »")
        self._ecrire()
        self._ecrire("  Démarrez le serveur :  python manage.py runserver")
        self._ecrire("  Puis ouvrez http://127.0.0.1:8000/ et connectez-vous en tant que :")
        l1 = etudiants.get(demo_data.L1_TRACE)
        l3 = etudiants.get(demo_data.L3_TRACE)
        if l1:
            self._ecrire(f"      L1 : {l1.email}")
        if l3:
            self._ecrire(f"      L3 : {l3.email}")
        self._ecrire()
        self._ecrire("  Parcours conseillé :")
        self._ecrire("      1. Connectez-vous en L3  -> page « Mes souhaits » -> choisissez un L1.")
        self._ecrire("      2. Admin (/admin/)       -> onglet « Demandes » -> acceptez la demande.")
        self._ecrire("      3. Admin                 -> onglet « Paramètre » -> action « FORCER LA RÉVÉLATION ».")
        self._ecrire("      4. Reconnectez-vous      -> /revelation/ affiche tous les binômes.")
        self._ecrire()
