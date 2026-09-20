from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from parrainage import demo_data
from parrainage.models import (
    Etudiant, ReponseQuestionnaire, DemandeForcage, ParametreEvenement
)
from parrainage.matching import calculer_matchs, SCORE_FORCE_INTERNE, score_affichable


def creer_etudiant(**kwargs):
    """Helper pour créer un étudiant + user."""

    defaults = {
        'nom': 'Doe', 'prenom': 'John', 'sexe': 'G', 'niveau': 'L1',
    }
    defaults.update(kwargs)
    email = defaults.pop('email', 'test@example.com')
    user = User.objects.create_user(
        username=email, email=email, password='testpass123'
    )
    return Etudiant.objects.create(user=user, email=email, **defaults)


def creer_quiz(etudiant, reponses):
    """Helper pour créer un questionnaire complet et marquer l'étudiant éligible."""
    if len(reponses) != 15:
        raise ValueError("Il faut 15 réponses")
    data = {
        f"q{i+1}": val for i, val in enumerate(reponses)
    }
    questionnaire = ReponseQuestionnaire.objects.create(etudiant=etudiant, **data)
    etudiant.a_valide_questionnaire = True
    etudiant.save(update_fields=['a_valide_questionnaire'])
    return questionnaire


class MatchingTests(TestCase):

    def setUp(self):
        # Parametres par défaut
        ParametreEvenement.obtenir()

        # 2 L1 et 2 L3
        self.l1_a = creer_etudiant(
            nom='Alpha', prenom='Élise', email='elise@fac.fr', sexe='F', niveau='L1'
        )
        self.l1_b = creer_etudiant(
            nom='Beta', prenom='Marc', email='marc@fac.fr', sexe='G', niveau='L1'
        )
        self.l3_a = creer_etudiant(
            nom='Gamma', prenom='Alice', email='alice@fac.fr', sexe='F', niveau='L3'
        )
        self.l3_b = creer_etudiant(
            nom='Delta', prenom='Paul', email='paul@fac.fr', sexe='G', niveau='L3'
        )

        # Questionnaires identiques pour les L1 afin que le bonus mixte départage.
        reponses_a = [5, 3, 2, 4, 5, 3, 4, 2, 5, 4, 3, 5, 4, 2, 5]
        reponses_b = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        creer_quiz(self.l1_a, reponses_a)
        creer_quiz(self.l1_b, reponses_b)
        # L3 : l'une matche parfaitement les reponses_a mais même sexe (F),
        #      l'autre est G et proche des reponses_a.
        reponses_l3a = list(reponses_a)  # score quiz = 70, bonus 0
        reponses_l3b = [5, 3, 2, 4, 5, 3, 4, 2, 5, 4, 3, 5, 4, 2, 4]  # proche, G -> bonus 30
        creer_quiz(self.l3_a, reponses_l3a)
        creer_quiz(self.l3_b, reponses_l3b)

    def test_bonus_mixte_applique(self):
        """Le L1 féminin A doit matcher avec le L3 masculin B (bonus mixte)."""
        matchs = calculer_matchs()
        match_l1a = next(m for m in matchs if m['l1'] == self.l1_a)
        self.assertEqual(match_l1a['l3'], self.l3_b)
        # score quiz ~70 + 30 bonus = plus proche de 100
        self.assertGreater(match_l1a['score'], 70)

    def test_score_affiche_entre_0_et_100(self):
        matchs = calculer_matchs()
        for m in matchs:
            self.assertGreaterEqual(m['score_affichage'], 0)
            self.assertLessEqual(m['score_affichage'], 100)

    def test_forcage_ecrase_score_normal(self):
        """Une demande acceptée donne un score interne 9999 affiché comme 100."""
        DemandeForcage.objects.create(
            demandeur=self.l3_a, cible=self.l1_b, statut=DemandeForcage.Statut.ACCEPTE
        )
        matchs = calculer_matchs()
        match_b = next(m for m in matchs if m['l1'] == self.l1_b)
        self.assertEqual(match_b['l3'], self.l3_a)
        self.assertEqual(match_b['score'], SCORE_FORCE_INTERNE)
        self.assertEqual(match_b['score_affichage'], 100)

    def test_score_affichable_convertit_9999(self):
        self.assertEqual(score_affichable(SCORE_FORCE_INTERNE), 100)
        self.assertEqual(score_affichable(75), 75)
        self.assertEqual(score_affichable(101), 100)
        self.assertEqual(score_affichable(-3), 0)


class AdminImportCsvTests(TestCase):

    def setUp(self):
        # un superuser pour accéder à l'admin
        self.superuser = User.objects.create_superuser(
            username='admin', email='admin@x.fr', password='pass12345'
        )
        ParametreEvenement.obtenir()
        self.client.force_login(self.superuser)

    def test_import_liste_blanche(self):
        """L'import CSV crée les étudiants et déduit le sexe du prénom."""
        csv_content = (
            "nom,prenom,niveau,groupe\n"
            "DUPONT,Marie,L1,L1\n"
            "MARTIN,Jules,L3,L3A\n"
        )
        upload = SimpleUploadedFile('liste.csv', csv_content.encode('utf-8'),
                                    content_type='text/csv')

        url = reverse('admin:parrainage_etudiant_changelist')
        response = self.client.post(url, {
            'action': 'importer_liste_blanche',
            '_selected_action': '0',
            'csv_liste_blanche': upload,
        })
        self.assertEqual(response.status_code, 302)

        self.assertEqual(Etudiant.objects.count(), 2)
        marie = Etudiant.objects.get(nom='DUPONT')
        jules = Etudiant.objects.get(nom='MARTIN')
        # Le sexe est déduit du prénom.
        self.assertEqual(marie.sexe, 'F')
        self.assertEqual(jules.sexe, 'G')
        self.assertTrue(marie.sexe_deduit)
        # Les niveaux et groupes sont conservés.
        self.assertEqual(jules.niveau, 'L3')
        self.assertEqual(jules.groupe, 'L3A')
        # Aucun compte n'est créé à l'import : l'équipe les génère ensuite.
        self.assertIsNone(marie.user)
        self.assertIsNone(marie.identifiant)

    def test_declencher_revelation(self):
        """L'action admin 'FORCER LA RÉVÉLATION' met phase=revelation et le flag à True."""
        url = reverse('admin:parrainage_parametreevenement_changelist')
        response = self.client.post(url, {
            'action': 'declencher_revelation',
            '_selected_action': '1',
        })
        self.assertEqual(response.status_code, 302)
        p = ParametreEvenement.obtenir()
        self.assertEqual(p.phase_actuelle, ParametreEvenement.Phase.REVELATION)
        self.assertTrue(p.revelation_declenchee_manuellement)


class IntegrationParcoursTests(TestCase):
    """Parcours complet d'un utilisateur sur l'application."""

    def setUp(self):
        ParametreEvenement.obtenir()
        # Création de la liste blanche (un L1, un L3) SANS compte User,
        # comme produit par l'import CSV.
        self.l1 = Etudiant.objects.create(
            nom='Roux', prenom='Lucas', email='l1@x.fr',
            niveau='L1', sexe='G'
        )
        self.l3 = Etudiant.objects.create(
            nom='Marchand', prenom='Anna', email='l3@x.fr',
            niveau='L3', sexe='F'
        )

    def _set_user_password(self, etudiant, mdp='secret123'):
        """Attache (ou re-attache) un User à l'étudiant avec un mot de passe."""
        if not etudiant.user_id:
            u = User(username=etudiant.email, email=etudiant.email,
                     first_name=etudiant.prenom, last_name=etudiant.nom)
            u.set_password(mdp)
            u.save()
            etudiant.user = u
            etudiant.save(update_fields=['user'])
        else:
            etudiant.user.set_password(mdp)
            etudiant.user.save()

    def test_page_inscription_renvoie_vers_la_connexion(self):
        """L'inscription autonome n'existe plus : les comptes sont créés par l'équipe."""
        self.client.logout()
        resp = self.client.get(reverse('inscription'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Elle invite à se connecter avec l'identifiant remis par l'équipe.
        self.assertIn('identifiant', html.lower())
        self.assertIn(reverse('login'), html)

    def test_parcours_quiz_puis_revelation_avec_compte_fourni(self):
        """Un étudiant à qui l'équipe a donné un identifiant peut répondre puis voir son binôme."""
        # L'équipe a créé le compte : l'étudiant se connecte avec son identifiant.
        self._set_user_password(self.l1, 'MonMdp123')
        self.client.login(username=self.l1.email, password='MonMdp123')

        # 1) Il répond au questionnaire.
        reactions = [5, 4, 3, 2, 1, 5, 4, 3, 2, 1, 5, 4, 3, 2, 1]
        data = {f'q{i+1}': v for i, v in enumerate(reactions)}
        resp = self.client.post(reverse('quiz'), data)
        self.assertEqual(resp.status_code, 302)

        self.l1.refresh_from_db()
        self.assertTrue(self.l1.a_valide_questionnaire)
        self.assertTrue(self.l1.questionnaire.est_complete)

    def test_revelation_publique_ne_contient_pas_force(self):
        """Un binôme 'forcé' affiche 100/100 sans le mot 'Forcé'."""
        # Réponses identiques pour créer un score élevé naturel.
        for etu in (self.l1, self.l3):
            # besoin d'un mot de passe pour se connecter comme L3 pour demander
            pass

        # Créer les questionnaires
        resp_a = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5]
        ReponseQuestionnaire.objects.create(etudiant=self.l1, **{f'q{i+1}': v for i, v in enumerate(resp_a)})
        ReponseQuestionnaire.objects.create(etudiant=self.l3, **{f'q{i+1}': v for i, v in enumerate(resp_a)})
        self.l1.a_valide_questionnaire = True; self.l1.save()
        self.l3.a_valide_questionnaire = True; self.l3.save()

        # Une demande acceptée (donc 'forcée' en interne, score 9999 -> 100).
        DemandeForcage.objects.create(
            demandeur=self.l3, cible=self.l1, statut=DemandeForcage.Statut.ACCEPTE
        )

        # Déclencher la révélation
        p = ParametreEvenement.obtenir()
        p.revelation_declenchee_manuellement = True
        p.save()

        # Un utilisateur authentifié voit la révélation
        self._set_user_password(self.l1)
        self.client.login(username='l1@x.fr', password='secret123')
        resp = self.client.get(reverse('revelation'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        self.assertIn('100/100', html)
        # Le mot interdit ne doit PAS apparaître.
        lower = html.lower()
        self.assertNotIn('forcé', lower)
        self.assertNotIn('forcer', lower)
        self.assertNotIn('impos', lower)

    def test_etudiants_ne_peuvent_pas_creer_de_binome(self):
        """Seul l'admin décide des associations : la page a disparu du site."""
        self._set_user_password(self.l1)
        self.client.login(username='l1@x.fr', password='secret123')
        # L'ancienne page de souhaits n'existe plus.
        for chemin in ['/souhaits/', '/souhaits/annuler/1/']:
            self.assertEqual(self.client.get(chemin).status_code, 404)

        # Un L3 non plus.
        self._set_user_password(self.l3)
        self.client.login(username='l3@x.fr', password='secret123')
        self.assertEqual(self.client.get('/souhaits/').status_code, 404)


class DemoCommandTests(TestCase):
    """La commande de démo doit alimenter la base et rester idempotente."""

    def test_demo_sem_et_trace(self):
        from io import StringIO
        from django.core.management import call_command

        sortie = StringIO()
        call_command('demo', '--reset', stdout=sortie)
        texte = sortie.getvalue()

        # Les profils fictifs sont créés.
        self.assertEqual(Etudiant.objects.count(), 11)
        self.assertEqual(Etudiant.objects.filter(niveau='L1').count(), 6)
        self.assertEqual(Etudiant.objects.filter(niveau='L3').count(), 5)
        # Chaque profil a un questionnaire complet et un compte.
        self.assertEqual(ReponseQuestionnaire.objects.count(), 11)
        self.assertEqual(Etudiant.objects.filter(user__isnull=True).count(), 0)
        # Le tracé mentionne bien le L1 et le L3 suivis.
        self.assertIn('PARCOURS D\'UN L1', texte)
        self.assertIn('PARCOURS D\'UN L3', texte)
        self.assertIn('Score de compatibilité', texte)

    def test_demo_idempotente(self):
        from io import StringIO
        from django.core.management import call_command

        call_command('demo', '--reset', '--sans-trace', stdout=StringIO())
        call_command('demo', '--reset', '--sans-trace', stdout=StringIO())
        # Deux exécutions ne créent pas de doublons.
        self.assertEqual(Etudiant.objects.count(), 11)
        self.assertEqual(ReponseQuestionnaire.objects.count(), 11)

    def test_demo_preference_acceptee_change_le_match(self):
        from io import StringIO
        from django.core.management import call_command
        from parrainage.matching import calculer_matchs, SCORE_FORCE_INTERNE

        call_command('demo', '--reset', '--sans-trace', stdout=StringIO())
        l1 = Etudiant.objects.get(email=demo_data.L1_TRACE)

        # Sans préférence acceptée : match naturel.
        match_naturel = next(m for m in calculer_matchs() if m['l1'].id == l1.id)
        self.assertNotEqual(match_naturel['score'], SCORE_FORCE_INTERNE)

        # Après acceptation : le binôme est prioritaire et affiché 100/100.
        call_command('demo', '--accepter-preference', '--sans-trace', stdout=StringIO())
        match_prioritaire = next(m for m in calculer_matchs() if m['l1'].id == l1.id)
        self.assertEqual(match_prioritaire['score'], SCORE_FORCE_INTERNE)
        self.assertEqual(match_prioritaire['score_affichage'], 100)


class CapaciteMatchingTests(TestCase):
    """Le matching doit respecter : 1 à 3 filleuls par L3, tous les éligibles placés."""

    def setUp(self):
        ParametreEvenement.obtenir()
        self.reponses = [
            [5, 4, 3, 5, 2, 5, 3, 2, 5, 4, 4, 3, 3, 2, 5],
            [3, 3, 2, 4, 5, 4, 5, 5, 4, 5, 4, 5, 5, 5, 4],
            [4, 3, 3, 4, 4, 4, 4, 3, 4, 4, 4, 3, 4, 3, 4],
            [2, 3, 1, 4, 3, 3, 4, 3, 4, 4, 4, 4, 3, 3, 3],
        ]

    def _creer(self, nb_l1, nb_l3, niveaux_sexes=None):
        """Crée nb_l1 L1 et nb_l3 L3 éligibles, sexes alternés."""
        for i in range(nb_l1):
            e = creer_etudiant(nom=f'L1{i}', prenom=f'Filleul{i}',
                               email=f'l1.{i}@t.fr', niveau='L1',
                               sexe='F' if i % 2 == 0 else 'G')
            creer_quiz(e, self.reponses[i % len(self.reponses)])
        for i in range(nb_l3):
            e = creer_etudiant(nom=f'L3{i}', prenom=f'Parrain{i}',
                               email=f'l3.{i}@t.fr', niveau='L3',
                               sexe='G' if i % 2 == 0 else 'F')
            creer_quiz(e, self.reponses[i % len(self.reponses)])

    def _verifier_contraintes(self, nb_l1, nb_l3):
        from collections import Counter
        from parrainage.matching import calculer_matchs, capacite_par_l3

        matchs = calculer_matchs()
        par_l3 = Counter(m['l3'].id for m in matchs)
        capacite = capacite_par_l3(nb_l1, nb_l3)

        # 1) Tous les L1 éligibles sont placés (quand c'est possible).
        self.assertEqual(len({m['l1'].id for m in matchs}), nb_l1)
        # 2) Chaque L3 a au moins 1 filleul.
        self.assertEqual(len(par_l3), nb_l3)
        # 3) Aucun L3 ne dépasse la capacité.
        if par_l3:
            self.assertLessEqual(max(par_l3.values()), capacite)
            self.assertGreaterEqual(min(par_l3.values()), 1)
        return matchs

    def test_ratio_deux_pour_un(self):
        """83 L1 pour 44 L3 : tout le monde est placé, 1 à 2 filleuls par L3."""
        self._creer(20, 11)
        self._verifier_contraintes(20, 11)

    def test_moins_de_l1_que_de_l3(self):
        """S'il y a plus de L3 que de L1, chacun a au plus 1 filleul."""
        from collections import Counter
        from parrainage.matching import calculer_matchs

        self._creer(5, 8)
        matchs = calculer_matchs()
        par_l3 = Counter(m['l3'].id for m in matchs)
        # Tous les L1 sont placés, chacun chez un L3 différent.
        self.assertEqual(len({m['l1'].id for m in matchs}), 5)
        self.assertEqual(len(par_l3), 5)
        self.assertEqual(max(par_l3.values()), 1)

    def test_un_seul_l3_n_a_pas_plus_de_trois_filleuls(self):
        """Avec beaucoup de L1 pour peu de L3, la capacité plafonne à 3."""
        from collections import Counter
        self._creer(12, 4)
        from parrainage.matching import calculer_matchs
        matchs = calculer_matchs()
        par_l3 = Counter(m['l3'].id for m in matchs)
        self.assertLessEqual(max(par_l3.values()), 3)

    def test_l3_sans_questionnaire_na_pas_de_filleul(self):
        """Un L3 qui n'a pas répondu au questionnaire est exclu."""
        from collections import Counter
        from parrainage.matching import calculer_matchs, eligibles

        self._creer(6, 3)
        l3 = eligibles('L3').first()
        l3.a_valide_questionnaire = False
        l3.save(update_fields=['a_valide_questionnaire'])

        matchs = calculer_matchs()
        par_l3 = Counter(m['l3'].id for m in matchs)
        self.assertNotIn(l3.id, par_l3)
        # Les L1 restent tous placés grâce aux autres L3.
        self.assertEqual(len({m['l1'].id for m in matchs}),
                         eligibles('L1').count())

    def test_l1_sans_questionnaire_nest_pas_place(self):
        """Un L1 qui n'a pas répondu au questionnaire n'a pas de parrain."""
        from parrainage.matching import calculer_matchs, eligibles

        self._creer(6, 3)
        l1 = eligibles('L1').first()
        l1.a_valide_questionnaire = False
        l1.save(update_fields=['a_valide_questionnaire'])

        matchs = calculer_matchs()
        self.assertNotIn(l1.id, {m['l1'].id for m in matchs})
        self.assertEqual(len({m['l1'].id for m in matchs}),
                         eligibles('L1').count())

    def test_preference_acceptee_respecte_la_capacite(self):
        """Une préférence acceptée passe devant, sans casser les contraintes."""
        from collections import Counter
        from parrainage.matching import (calculer_matchs, capacite_par_l3,
                                         eligibles, match_du_l1)

        self._creer(10, 5)
        l1 = eligibles('L1').first()
        l3 = [x for x in eligibles('L3') if x.id != match_du_l1(l1)['l3'].id][0]

        DemandeForcage.objects.create(
            demandeur=l3, cible=l1, statut=DemandeForcage.Statut.ACCEPTE)

        matchs = calculer_matchs()
        match = match_du_l1(l1, matchs)
        self.assertEqual(match['l3'].id, l3.id)
        self.assertEqual(match['score'], SCORE_FORCE_INTERNE)
        self.assertEqual(match['score_affichage'], 100)

        par_l3 = Counter(m['l3'].id for m in matchs)
        capacite = capacite_par_l3(10, 5)
        self.assertLessEqual(max(par_l3.values()), capacite)
        self.assertEqual(len(par_l3), len(eligibles('L3')))

    def test_score_privilegie_le_meilleur_couple(self):
        """Le premier filleul d'un L3 est bien son meilleur score."""
        from parrainage.matching import calculer_matchs, eligibles
        self._creer(8, 4)
        matchs = calculer_matchs()
        for l3 in eligibles('L3'):
            siens = [m for m in matchs if m['l3'].id == l3.id]
            if len(siens) > 1:
                scores = [m['score'] for m in siens]
                self.assertEqual(scores, sorted(scores, reverse=True))


class ConnexionEtVerrouTests(TestCase):
    """Connexion par identifiant et verrouillage des réponses."""

    def setUp(self):
        ParametreEvenement.obtenir()
        self.reponses = [5, 4, 3, 5, 2, 5, 3, 2, 5, 4, 4, 3, 3, 2, 5]
        self.etudiant = creer_etudiant(
            nom='Tanoh', prenom='Koffi Roche', email='koffi.tanoh@miage.ci',
            niveau='L1', sexe='G')
        # L'identifiant est la seule clé de connexion : il sert aussi de
        # username au compte Django.
        self.etudiant.identifiant = 'k.tanoh'
        self.etudiant.save(update_fields=['identifiant'])
        self.etudiant.user.username = 'k.tanoh'
        self.etudiant.user.set_password('MotDePasse1')
        self.etudiant.user.save()

    def test_connexion_par_identifiant(self):
        ok = self.client.login(username='k.tanoh', password='MotDePasse1')
        self.assertTrue(ok)

    def test_connexion_par_identifiant_via_vue(self):
        reponse = self.client.post(reverse('login'), {
            'identifiant': 'k.tanoh', 'mot_de_passe': 'MotDePasse1'})
        self.assertEqual(reponse.status_code, 302)
        self.assertIn('dashboard', reponse.url)

    def test_identifiant_insensible_a_la_casse(self):
        """« K.TANOH » doit fonctionner comme « k.tanoh »."""
        reponse = self.client.post(reverse('login'), {
            'identifiant': 'K.TANOH', 'mot_de_passe': 'MotDePasse1'})
        self.assertEqual(reponse.status_code, 302)

    def test_mauvais_mot_de_passe_refuse(self):
        reponse = self.client.post(reverse('login'), {
            'identifiant': 'k.tanoh', 'mot_de_passe': 'faux'})
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_questionnaire_verrouille_apres_validation(self):
        """Une fois validé, le questionnaire ne peut plus être modifié."""
        creer_quiz(self.etudiant, self.reponses)  # marque a_valide_questionnaire
        self.client.login(username='k.tanoh', password='MotDePasse1')

        # La page indique le verrouillage et les champs sont désactivés.
        page = self.client.get(reverse('quiz'))
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['verrouille'])

        # Une tentative d'écriture est refusée et ne change rien.
        avant = self.etudiant.questionnaire.reponses()
        self.client.post(reverse('quiz'), {f'q{i}': 1 for i in range(1, 16)})
        self.etudiant.questionnaire.refresh_from_db()
        self.assertEqual(self.etudiant.questionnaire.reponses(), avant)

    def test_questionnaire_modifiable_avant_validation(self):
        """Tant que rien n'est validé, l'étudiant peut répondre."""
        self.client.login(username='k.tanoh', password='MotDePasse1')
        reponse = self.client.post(
            reverse('quiz'), {f'q{i}': 3 for i in range(1, 16)})
        self.assertEqual(reponse.status_code, 302)
        self.etudiant.refresh_from_db()
        self.assertTrue(self.etudiant.a_valide_questionnaire)

    def test_verrouillage_par_phase(self):
        """En phase verrouillée, même un questionnaire vierge est figé."""
        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.VERROUILLE
        p.save()

        self.client.login(username='k.tanoh', password='MotDePasse1')
        page = self.client.get(reverse('quiz'))
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['phase_fermee'])

        # Aucune réponse n'a été enregistrée.
        self.client.post(reverse('quiz'), {f'q{i}': 3 for i in range(1, 16)})
        self.etudiant.refresh_from_db()
        self.assertFalse(self.etudiant.a_valide_questionnaire)


class AdminReponsesEtIdentifiantsTests(TestCase):
    """L'équipe doit pouvoir voir les réponses et récupérer les identifiants."""

    def setUp(self):
        ParametreEvenement.obtenir()
        self.admin = User.objects.create_superuser(
            username='chef', email='chef@x.fr', password='pass12345')
        self.client.force_login(self.admin)

        self.etudiant = Etudiant.objects.create(
            nom='Tanoh', prenom='Koffi Roche', email='koffi@participants.local',
            niveau='L1', groupe='L1', sexe='G')
        self.reponses = [5, 4, 3, 5, 2, 5, 3, 2, 5, 4, 4, 3, 3, 2, 5]
        creer_quiz(self.etudiant, self.reponses)

    def test_liste_reponses_affiche_les_15_valeurs(self):
        url = reverse('admin:parrainage_reponsequestionnaire_changelist')
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        apercu = ' · '.join(str(v) for v in self.reponses)
        self.assertIn(apercu, html)

    def test_export_reponses_csv(self):
        url = reverse('admin:parrainage_reponsequestionnaire_changelist')
        questionnaire = self.etudiant.questionnaire
        reponse = self.client.post(url, {
            'action': 'exporter_reponses',
            '_selected_action': [str(questionnaire.id)],
        })
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode('utf-8-sig')
        self.assertIn('Nom;Prenoms;Niveau', contenu)
        # Les 15 réponses figurent dans la ligne exportée.
        for valeur in self.reponses:
            self.assertIn(str(valeur), contenu)

    def test_generer_identifiants_puis_export(self):
        url = reverse('admin:parrainage_etudiant_changelist')
        self.assertIsNone(self.etudiant.identifiant)

        # Génération des identifiants
        reponse = self.client.post(url, {
            'action': 'generer_identifiants',
            '_selected_action': [str(self.etudiant.id)],
        })
        self.assertEqual(reponse.status_code, 302)  # action -> redirection

        self.etudiant.refresh_from_db()
        self.assertTrue(self.etudiant.identifiant)
        self.assertTrue(self.etudiant.user_id)

        # Export CSV des identifiants
        reponse = self.client.post(url, {
            'action': 'exporter_identifiants',
            '_selected_action': [str(self.etudiant.id)],
        })
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode('utf-8-sig')
        self.assertIn('Identifiant;Mot de passe', contenu)
        self.assertIn(self.etudiant.identifiant, contenu)

    def test_colonne_sexe_signale_les_deductions(self):
        """Un sexe déduit automatiquement est signalé comme tel."""
        self.etudiant.sexe_deduit = True
        self.etudiant.save(update_fields=['sexe_deduit'])
        url = reverse('admin:parrainage_etudiant_changelist')
        page = self.client.get(url)
        self.assertIn('(déduit)', page.content.decode())

    def test_sexe_confirme_nest_pas_marque_deduit(self):
        """Un sexe vérifié par l'équipe ne porte pas la mention « déduit »."""
        self.etudiant.sexe_deduit = False
        self.etudiant.save(update_fields=['sexe_deduit'])
        url = reverse('admin:parrainage_etudiant_changelist')
        page = self.client.get(url)
        self.assertNotIn('(déduit)', page.content.decode())

    def test_etudiant_sans_sexe_est_signale(self):
        self.etudiant.sexe = ''
        self.etudiant.save(update_fields=['sexe'])
        url = reverse('admin:parrainage_etudiant_changelist')
        page = self.client.get(url)
        self.assertIn('à renseigner', page.content.decode())
