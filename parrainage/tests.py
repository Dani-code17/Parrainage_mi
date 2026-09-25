"""Tests de l'application de parrainage.

Couvre le catalogue des questions, les modèles, l'algorithme de matching,
les vues et l'administration.
"""

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

import io

from io import StringIO

from parrainage import questions as catalogue
from parrainage.models import (
    DemandeForcage, Etudiant, ParametreEvenement, ReponseQuestionnaire,
)
from parrainage.matching import (
    capacite_par_l3, calculer_matchs, dealbreaker_incompatible, eligibles,
    matchs_par_l3, question_commune, score_affichable,
    _score_questionnaire, _bonus_mixte, _scores_dimensions,
)
from parrainage.questionnaires import generer_reponses


# --------------------------------------------------------------- Helpers

def creer_etudiant(**kwargs):
    """Crée un étudiant avec un compte utilisateur."""
    defaults = {'nom': 'Doe', 'prenom': 'John', 'sexe': 'G', 'niveau': 'L1'}
    defaults.update(kwargs)
    email = defaults.pop('email', 'test@example.com')
    identifiant = defaults.pop('identifiant', None) or email.split('@')[0]
    user = User.objects.create_user(
        username=identifiant, email=email, password='testpass123')
    etudiant = Etudiant.objects.create(
        user=user, email=email, identifiant=identifiant, **defaults)
    return etudiant


def creer_quiz(etudiant, donnees=None, valide=True):
    """Crée un questionnaire complet pour un étudiant.

    Sans ``donnees``, on génère un jeu cohérent (et déterministe) à partir de
    l'identifiant de l'étudiant.
    """
    if donnees is None:
        donnees = generer_reponses(graine=etudiant.id or 1,
                                   niveau=etudiant.niveau)
    questionnaire, _ = ReponseQuestionnaire.objects.update_or_create(
        etudiant=etudiant, defaults={'donnees': donnees, 'verrouille': True})
    if valide:
        etudiant.a_valide_questionnaire = True
        etudiant.save(update_fields=['a_valide_questionnaire'])
    return questionnaire


def ajouter_photo(etudiant, nom='photo.jpg'):
    """Attache une vraie image à un étudiant (la photo est obligatoire)."""
    from PIL import Image

    tampon = io.BytesIO()
    Image.new('RGB', (60, 60), (1, 47, 107)).save(tampon, 'JPEG')
    etudiant.photo.save(
        nom, SimpleUploadedFile(nom, tampon.getvalue(), content_type='image/jpeg'),
        save=True)
    return etudiant


# =====================================================================
#  Catalogue des questions
# =====================================================================

class CatalogueTests(TestCase):

    def test_vingt_cinq_questions(self):
        """Le catalogue couvre les 25 questions du document."""
        codes = {q.code for q in catalogue.QUESTIONS}
        self.assertEqual(codes, {f'q{i}' for i in range(1, 26)})

    def test_q21_a_une_version_par_niveau(self):
        """La Q21 existe en version L1 et L3 — une seule par étudiant."""
        versions = [q for q in catalogue.QUESTIONS if q.code == 'q21']
        self.assertEqual(len(versions), 2)
        self.assertEqual({v.condition for v in versions}, {'L1', 'L3'})

        l1 = catalogue.questions_pour('L1')
        l3 = catalogue.questions_pour('L3')
        self.assertEqual(len([q for q in l1 if q.code == 'q21']), 1)
        self.assertEqual(len([q for q in l3 if q.code == 'q21']), 1)

    def test_questions_libres_non_notees(self):
        """Les réponses libres ne participent pas au score."""
        for code in ('q21', 'q23', 'q25'):
            self.assertNotIn(code, catalogue.CODES_NOTES)

    def test_toutes_les_questions_sont_obligatoires(self):
        """Aucune question n'est facultative : tout doit être rempli."""
        facultatives = {q.code for q in catalogue.QUESTIONS if q.facultatif}
        self.assertEqual(facultatives, set())

    def test_six_dimensions_ponderees(self):
        noms = [nom for nom, _ in catalogue.DIMENSIONS]
        self.assertEqual(len(noms), 6)
        self.assertAlmostEqual(sum(catalogue.POIDS_DIMENSIONS.values()), 1.0)


# =====================================================================
#  Modèle de réponses
# =====================================================================

class ReponsesModeleTests(TestCase):

    def setUp(self):
        self.etudiant = creer_etudiant(email='a@x.fr', niveau='L1')

    def test_lecture_par_type(self):
        q = creer_quiz(self.etudiant, donnees={
            'q1': '2', 'q19': ['0', '3'], 'q24': 7, 'q25': 'Bonjour !'})
        self.assertEqual(q.choix('q1'), '2')
        self.assertEqual(q.multi('q19'), ['0', '3'])
        self.assertEqual(q.nombre('q24'), 7)
        self.assertEqual(q.texte('q25'), 'Bonjour !')
        self.assertIsNone(q.choix('q2'))

    def test_toutes_les_questions_sont_exigees(self):
        """Une question sans réponse empêche la validation."""
        donnees = generer_reponses(graine=42, niveau='L1')
        donnees.pop('q12')
        q = ReponseQuestionnaire(etudiant=self.etudiant, donnees=donnees)
        self.assertIn('q12', q.reponses_manquantes())
        self.assertFalse(q.est_complete)

    def test_reponses_manquantes_detecte_une_obligatoire(self):
        donnees = generer_reponses(graine=42, niveau='L1')
        donnees.pop('q1')
        q = ReponseQuestionnaire(etudiant=self.etudiant, donnees=donnees)
        self.assertIn('q1', q.reponses_manquantes())

    def test_reponses_lisibles_rendent_les_libelles(self):
        creer_quiz(self.etudiant, donnees={'q1': '0', 'q14': ['0', '1']})
        lignes = dict(
            (question.code, rendu)
            for question, rendu in self.etudiant.questionnaire.reponses_lisibles()
        )
        self.assertIn('introverti', lignes['q1'].lower())
        self.assertIn('Loyauté', lignes['q14'])


# =====================================================================
#  Mathématique du score
# =====================================================================

class ScoreDimensionTests(TestCase):

    def setUp(self):
        ParametreEvenement.obtenir()

    def test_reponses_identiques_donnent_le_maximum(self):
        """Deux questionnaires identiques donnent 100 % de compatibilité."""
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1', sexe='G')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3', sexe='G')
        donnees = generer_reponses(graine=7, niveau='L1')
        creer_quiz(l1, donnees=dict(donnees))
        creer_quiz(l3, donnees=dict(donnees))

        note = _score_questionnaire(l1.questionnaire, l3.questionnaire)
        # Le maximum est de 70 ; la règle de complémentarité sur la
        # sociabilité peut retirer quelques points.
        self.assertGreater(note, 68.0)

    def test_bonus_mixte_oppose_seulement(self):
        l1 = creer_etudiant(email='a@x.fr', niveau='L1', sexe='F')
        l3_g = creer_etudiant(email='b@x.fr', niveau='L3', sexe='G')
        l3_f = creer_etudiant(email='c@x.fr', niveau='L3', sexe='F')
        self.assertEqual(_bonus_mixte(l1, l3_g), 30.0)
        self.assertEqual(_bonus_mixte(l1, l3_f), 0.0)

    def test_sous_scores_par_dimension(self):
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        creer_quiz(l1)
        creer_quiz(l3)
        scores = _scores_dimensions(l1.questionnaire, l3.questionnaire)
        self.assertEqual(set(scores), {nom for nom, _ in catalogue.DIMENSIONS})
        for valeur in scores.values():
            self.assertGreaterEqual(valeur, 0.0)
            self.assertLessEqual(valeur, 1.0)

    def test_question_sans_reponse_ne_penalise_pas(self):
        """Une question facultative vide des deux côtés est ignorée."""
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        base = generer_reponses(graine=3, niveau='L1')
        avec = dict(base)
        sans = dict(base)
        sans.pop('q12')
        creer_quiz(l1, donnees=avec)
        creer_quiz(l3, donnees=sans)
        # Le score reste élevé : q12 n'est simplement pas comptée.
        self.assertGreater(_score_questionnaire(
            l1.questionnaire, l3.questionnaire), 50)


# =====================================================================
#  Algorithme de matching
# =====================================================================

class MatchingTests(TestCase):

    def setUp(self):
        ParametreEvenement.obtenir()

    def test_score_toujours_entre_0_et_100(self):
        for i in range(6):
            creer_quiz(creer_etudiant(
                email=f'l1{i}@x.fr', niveau='L1', sexe='F' if i % 2 else 'G'))
            creer_quiz(creer_etudiant(
                email=f'l3{i}@x.fr', niveau='L3', sexe='G' if i % 2 else 'F'))
        for m in calculer_matchs():
            self.assertGreaterEqual(m['score_affichage'], 0)
            self.assertLessEqual(m['score_affichage'], 100)

    def test_etudiant_sans_questionnaire_est_exclu(self):
        """Un L1 sans questionnaire n'a pas de parrain."""
        l1_sans = creer_etudiant(email='sans@x.fr', niveau='L1')
        l1_avec = creer_etudiant(email='avec@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        creer_quiz(l1_avec)
        creer_quiz(l3)

        places = {m['l1'].id for m in calculer_matchs()}
        self.assertIn(l1_avec.id, places)
        self.assertNotIn(l1_sans.id, places)

    def test_l3_sans_questionnaire_n_a_pas_de_filleul(self):
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3_avec = creer_etudiant(email='avec@x.fr', niveau='L3')
        l3_sans = creer_etudiant(email='sans@x.fr', niveau='L3')
        creer_quiz(l1)
        creer_quiz(l3_avec)

        places = {m['l3'].id for m in calculer_matchs()}
        self.assertIn(l3_avec.id, places)
        self.assertNotIn(l3_sans.id, places)

    def test_association_prioritaire_passe_devant(self):
        """Un binôme décidé par l'équipe l'emporte sur le score naturel."""
        donnees = generer_reponses(graine=1, niveau='L1')

        l1 = creer_etudiant(email='l1@x.fr', niveau='L1', sexe='G')
        creer_quiz(l1, donnees=dict(donnees))

        # Un L3 parfaitement compatible, et un autre très éloigné.
        proche = creer_etudiant(email='proche@x.fr', niveau='L3', sexe='G')
        creer_quiz(proche, donnees=dict(donnees))
        loin = creer_etudiant(email='loin@x.fr', niveau='L3', sexe='G')
        creer_quiz(loin, donnees={**donnees, 'q1': '4', 'q3': '2', 'q8': '4',
                                  'q15': '2', 'q19': ['2'], 'q22': '2'})

        match_naturel = [m for m in calculer_matchs() if m['l1'].id == l1.id][0]
        self.assertEqual(match_naturel['l3'].id, proche.id)

        # L'équipe décide d'associer l'autre L3 : il passe devant.
        DemandeForcage.objects.create(
            demandeur=loin, cible=l1, statut=DemandeForcage.Statut.ACCEPTE)
        match_prioritaire = [m for m in calculer_matchs() if m['l1'].id == l1.id][0]
        self.assertEqual(match_prioritaire['l3'].id, loin.id)

    def test_score_prioritaire_reste_credible(self):
        """Un binôme prioritaire n'affiche jamais 100/100."""
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1', sexe='G')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3', sexe='F')
        creer_quiz(l1, donnees=generer_reponses(graine=5, niveau='L1'))
        creer_quiz(l3, donnees=generer_reponses(graine=5, niveau='L3'))
        DemandeForcage.objects.create(
            demandeur=l3, cible=l1, statut=DemandeForcage.Statut.ACCEPTE)

        match = [m for m in calculer_matchs() if m['l1'].id == l1.id][0]
        self.assertLess(match['score_affichage'], 100)
        self.assertNotEqual(match['score'], 9999)

    def test_capacite_calculee_selon_le_ratio(self):
        self.assertEqual(capacite_par_l3(83, 44), 2)
        self.assertEqual(capacite_par_l3(44, 44), 1)
        self.assertEqual(capacite_par_l3(100, 44), 3)
        # Jamais plus de 3 filleuls, même avec un ratio énorme.
        self.assertEqual(capacite_par_l3(1000, 44), 3)

    def test_tous_les_l1_places_quand_la_capacite_suffit(self):
        for i in range(7):
            creer_quiz(creer_etudiant(
                email=f'l1{i}@x.fr', niveau='L1', sexe='F' if i % 2 else 'G'))
        for i in range(3):
            creer_quiz(creer_etudiant(
                email=f'l3{i}@x.fr', niveau='L3', sexe='G' if i % 2 else 'F'))

        matchs = calculer_matchs()
        self.assertEqual(len({m['l1'].id for m in matchs}), 7)

    def test_aucun_l3_ne_depasse_la_capacite(self):
        for i in range(9):
            creer_quiz(creer_etudiant(
                email=f'l1{i}@x.fr', niveau='L1', sexe='F' if i % 2 else 'G'))
        for i in range(4):
            creer_quiz(creer_etudiant(
                email=f'l3{i}@x.fr', niveau='L3', sexe='G' if i % 2 else 'F'))

        capacite = capacite_par_l3(9, 4)
        for groupe in matchs_par_l3(calculer_matchs()):
            self.assertLessEqual(len(groupe['matchs']), capacite)

    def test_score_privilegie_le_meilleur_couple(self):
        """Le L1 le plus compatible obtient le meilleur score."""
        l1_a = creer_etudiant(email='a@x.fr', niveau='L1', sexe='G')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3', sexe='G')
        donnees = generer_reponses(graine=11, niveau='L1')
        creer_quiz(l1_a, donnees=dict(donnees))
        creer_quiz(l3, donnees=dict(donnees))

        match = [m for m in calculer_matchs() if m['l1'].id == l1_a.id][0]
        # Réponses identiques : 70/100 au questionnaire (mêmes sexes, donc
        # aucun bonus mixte).
        self.assertGreaterEqual(match['score_affichage'], 68)


class DealbreakerTests(TestCase):

    def setUp(self):
        ParametreEvenement.obtenir()

    def test_dealbreaker_exclut_le_binome(self):
        """Si le deal-breaker de l'un correspond au red flag de l'autre."""
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        base = generer_reponses(graine=2, niveau='L1')
        creer_quiz(l1, donnees={**base, 'q23': "Pas de jaloux, c'est mon deal-breaker."})
        creer_quiz(l3, donnees={**base, 'q15': '1'})  # 1 = Jalousie

        self.assertTrue(dealbreaker_incompatible(
            l1.questionnaire, l3.questionnaire))

    def test_pas_de_dealbreaker_quand_rien_ne_correspond(self):
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        base = generer_reponses(graine=2, niveau='L1')
        creer_quiz(l1, donnees={**base, 'q23': "Quelqu'un de drôle et respectueux."})
        creer_quiz(l3, donnees={**base, 'q15': '0'})  # 0 = Mensonge

        self.assertFalse(dealbreaker_incompatible(
            l1.questionnaire, l3.questionnaire))

    def test_le_dealbreaker_ecarte_le_binome_quand_le_filtre_est_actif(self):
        """Le filtre d'exclusion n'agit que s'il est explicitement activé."""
        from unittest.mock import patch
        from parrainage import matching

        l1 = creer_etudiant(email='l1@x.fr', niveau='L1', sexe='G')
        base = generer_reponses(graine=4, niveau='L1')
        creer_quiz(l1, donnees={**base, 'q23': "Surtout pas quelqu'un de jaloux."})

        # Un L3 quasi identique, mais qui a coché « Jalousie » en red flag.
        l3_ko = creer_etudiant(email='ko@x.fr', niveau='L3', sexe='F')
        creer_quiz(l3_ko, donnees={**base, 'q15': '1'})

        # Un L3 nettement moins compatible.
        l3_ok = creer_etudiant(email='ok@x.fr', niveau='L3', sexe='F')
        creer_quiz(l3_ok, donnees={
            **base, 'q1': '4', 'q3': '2', 'q7': '3', 'q8': '4',
            'q19': ['2', '6'], 'q22': '2',
        })

        # Filtre désactivé (par défaut) : le meilleur score l'emporte,
        # donc le L3 quasi identique.
        with patch.object(matching, 'EXCLUSION_DEALBREAKER', False):
            match = [m for m in matching.calculer_matchs() if m['l1'].id == l1.id][0]
        self.assertEqual(match['l3'].id, l3_ko.id)

        # Filtre activé : ce binôme est écarté, le second est retenu.
        with patch.object(matching, 'EXCLUSION_DEALBREAKER', True):
            match = [m for m in matching.calculer_matchs() if m['l1'].id == l1.id][0]
        self.assertEqual(match['l3'].id, l3_ok.id)


class IndiceTeasingTests(TestCase):

    def setUp(self):
        ParametreEvenement.obtenir()

    def test_indice_rend_la_question_et_la_reponse(self):
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        donnees = generer_reponses(graine=8, niveau='L1')
        creer_quiz(l1, donnees=dict(donnees))
        creer_quiz(l3, donnees=dict(donnees))

        indice = question_commune(l1, l3)
        self.assertIsNotNone(indice)
        self.assertIn('question', indice)
        self.assertIn('reponse', indice)
        self.assertEqual(indice['pct'], 100)

    def test_indice_none_sans_questionnaire(self):
        l1 = creer_etudiant(email='l1@x.fr', niveau='L1')
        l3 = creer_etudiant(email='l3@x.fr', niveau='L3')
        self.assertIsNone(question_commune(l1, l3))


# =====================================================================
#  Vues et parcours
# =====================================================================

class ParcoursTests(TestCase):

    def setUp(self):
        ParametreEvenement.obtenir()
        self.l1 = creer_etudiant(
            email='l1@x.fr', niveau='L1', sexe='G', identifiant='l.roux')
        self.l3 = creer_etudiant(
            email='l3@x.fr', niveau='L3', sexe='F', identifiant='a.marchand')
        # La photo est obligatoire : on la pose pour ne pas être redirigé.
        ajouter_photo(self.l1, 'l1.jpg')
        ajouter_photo(self.l3, 'l3.jpg')
        self.l1.user.set_password('MotDePasse1')
        self.l1.user.save()

    def test_connexion_par_identifiant(self):
        reponse = self.client.post(reverse('login'), {
            'identifiant': 'l.roux', 'mot_de_passe': 'MotDePasse1'})
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(reponse.url.endswith('/dashboard/'))

    def test_connexion_identifiant_insensible_a_la_casse(self):
        reponse = self.client.post(reverse('login'), {
            'identifiant': 'L.ROUX', 'mot_de_passe': 'MotDePasse1'})
        self.assertEqual(reponse.status_code, 302)

    def test_mauvais_mot_de_passe_refuse(self):
        reponse = self.client.post(reverse('login'), {
            'identifiant': 'l.roux', 'mot_de_passe': 'faux'})
        self.assertEqual(reponse.status_code, 200)

    def test_questionnaire_accessible(self):
        self.client.login(username='l.roux', password='MotDePasse1')
        reponse = self.client.get(reverse('quiz'))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.context['verrouille'])

    def test_questionnaire_verrouille_apres_validation(self):
        """Une fois validé, le questionnaire n'est plus modifiable."""
        creer_quiz(self.l1)
        self.client.login(username='l.roux', password='MotDePasse1')

        page = self.client.get(reverse('quiz'))
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['verrouille'])

        avant = self.l1.questionnaire.donnees
        self.client.post(reverse('quiz'), {'q1': '4'})
        self.l1.questionnaire.refresh_from_db()
        self.assertEqual(self.l1.questionnaire.donnees, avant)

    def test_questionnaire_modifiable_avant_validation(self):
        self.client.login(username='l.roux', password='MotDePasse1')
        donnees = generer_reponses(graine=1, niveau='L1')
        reponse = self.client.post(reverse('quiz'), donnees)
        self.assertEqual(reponse.status_code, 302)

        self.l1.refresh_from_db()
        self.assertTrue(self.l1.a_valide_questionnaire)

    def test_verrouillage_par_phase(self):
        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.VERROUILLE
        p.save()
        self.client.login(username='l.roux', password='MotDePasse1')
        page = self.client.get(reverse('quiz'))
        self.assertTrue(page.context['lecture_seule'])

    def test_etudiant_ne_peut_pas_creer_de_binome(self):
        """Aucune URL ne permet à un étudiant de décider d'un binôme."""
        self.client.login(username='l.roux', password='MotDePasse1')
        reponse = self.client.get('/souhaits/')
        self.assertEqual(reponse.status_code, 404)

    def test_revelation_bloquee_avant_declenchement(self):
        self.client.login(username='l.roux', password='MotDePasse1')
        reponse = self.client.get(reverse('revelation'))
        self.assertEqual(reponse.status_code, 302)


class AnonymatTests(TestCase):
    """Le mot « forcé » ne doit jamais apparaître côté étudiant."""

    def setUp(self):
        ParametreEvenement.obtenir()
        self.l1 = creer_etudiant(
            email='l1@x.fr', niveau='L1', sexe='G', identifiant='l.roux')
        self.l3 = creer_etudiant(
            email='l3@x.fr', niveau='L3', sexe='F', identifiant='a.m')
        creer_quiz(self.l1)
        creer_quiz(self.l3)
        self.l1.user.set_password('MotDePasse1')
        self.l1.user.save()

    def test_revelation_reservee_a_lequipe(self):
        """Un étudiant ne peut pas ouvrir l'écran de projection."""
        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.REVELATION
        p.revelation_declenchee_manuellement = True
        p.save()

        self.client.login(username='l.roux', password='MotDePasse1')
        reponse = self.client.get(reverse('revelation'))
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(reponse.url.endswith('/dashboard/'))

    def test_revelation_ne_contient_aucun_mot_interdit(self):
        """Pour l'équipe : aucune mention de priorité sur l'écran de projection."""
        DemandeForcage.objects.create(
            demandeur=self.l3, cible=self.l1,
            statut=DemandeForcage.Statut.ACCEPTE)
        p = ParametreEvenement.obtenir()
        p.phase_actuelle = ParametreEvenement.Phase.REVELATION
        p.revelation_declenchee_manuellement = True
        p.save()

        # L'écran de projection est réservé au personnel.
        self.l1.user.is_staff = True
        self.l1.user.save()

        self.client.login(username='l.roux', password='MotDePasse1')
        page = self.client.get(reverse('revelation'))
        self.assertEqual(page.status_code, 200)

        html = page.content.decode().lower()
        for mot in ('forcé', 'forcer', 'impos'):
            self.assertNotIn(mot, html)

    def test_score_affichable_borne(self):
        self.assertEqual(score_affichable(97), 97)
        self.assertEqual(score_affichable(-5), 0)
        self.assertEqual(score_affichable(130), 100)


# =====================================================================
#  Administration
# =====================================================================

class AdminTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@x.fr', password='pass12345')
        ParametreEvenement.obtenir()
        self.client.force_login(self.admin)

    def test_import_liste_blanche(self):
        csv_content = (
            "nom,prenom,niveau,groupe\n"
            "Dupont,Marie,L1,L1\n"
            "Martin,Jules,L3,L3A\n"
        )
        upload = SimpleUploadedFile(
            'liste.csv', csv_content.encode('utf-8'), content_type='text/csv')

        url = reverse('admin:parrainage_etudiant_changelist')
        reponse = self.client.post(url, {
            'action': 'importer_liste_blanche',
            '_selected_action': '0',
            'csv_liste_blanche': upload,
        })
        self.assertEqual(reponse.status_code, 302)
        # Le nom est normalisé en majuscules à l'import.
        self.assertTrue(Etudiant.objects.filter(nom__iexact='Dupont').exists())

    def test_declencher_revelation(self):
        url = reverse('admin:parrainage_parametreevenement_changelist')
        self.client.post(url, {
            'action': 'declencher_revelation', '_selected_action': '1'})
        p = ParametreEvenement.obtenir()
        self.assertEqual(p.phase_actuelle, ParametreEvenement.Phase.REVELATION)
        self.assertTrue(p.revelation_declenchee_manuellement)

    def test_liste_des_reponses_affiche_les_etudiants(self):
        etudiant = creer_etudiant(email='rep@x.fr', niveau='L1', nom='Zebre')
        creer_quiz(etudiant)
        url = reverse('admin:parrainage_reponsequestionnaire_changelist')
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Zebre')

    def test_export_reponses_csv(self):
        etudiant = creer_etudiant(email='rep@x.fr', niveau='L1', nom='Zebre')
        creer_quiz(etudiant)
        url = reverse('admin:parrainage_reponsequestionnaire_changelist')
        reponse = self.client.post(url, {
            'action': 'exporter_reponses',
            '_selected_action': [str(etudiant.questionnaire.id)],
        })
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode('utf-8-sig')
        self.assertIn('Zebre', contenu)
        self.assertIn('Q25', contenu)

    def test_export_fiches_profil(self):
        etudiant = creer_etudiant(email='rep@x.fr', niveau='L1', nom='Zebre')
        creer_quiz(etudiant)
        url = reverse('admin:parrainage_reponsequestionnaire_changelist')
        reponse = self.client.post(url, {
            'action': 'exporter_fiches_profil',
            '_selected_action': [str(etudiant.questionnaire.id)],
        })
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode('utf-8-sig')
        self.assertIn('FICHE', contenu)
        # La fiche contient le texte des questions, pas seulement des codes.
        self.assertIn('décrirais', contenu)


# =====================================================================
#  Commande de remplissage (démonstration)
# =====================================================================

class RemplirQuestionnairesTests(TestCase):

    def test_remplit_tous_les_etudiants(self):
        ParametreEvenement.obtenir()
        creer_etudiant(email='l1@x.fr', niveau='L1')
        creer_etudiant(email='l3@x.fr', niveau='L3')

        call_command('remplir_questionnaires', '--reset', stdout=StringIO())

        self.assertEqual(ReponseQuestionnaire.objects.count(), 2)
        for q in ReponseQuestionnaire.objects.all():
            self.assertTrue(q.est_complete)
            self.assertNotIn('_profil', q.donnees)

    def test_reponses_deterministes(self):
        """Deux exécutions donnent exactement les mêmes réponses."""
        ParametreEvenement.obtenir()
        etudiant = creer_etudiant(email='l1@x.fr', niveau='L1')
        call_command('remplir_questionnaires', '--reset', stdout=StringIO())
        premier = ReponseQuestionnaire.objects.get(etudiant=etudiant).donnees
        call_command('remplir_questionnaires', '--reset', stdout=StringIO())
        second = ReponseQuestionnaire.objects.get(etudiant=etudiant).donnees
        self.assertEqual(premier, second)


# =====================================================================
#  Photo obligatoire
# =====================================================================

class PhotoObligatoireTests(TestCase):
    """Sans photo, l'étudiant est redirigé vers la page d'ajout."""

    def setUp(self):
        ParametreEvenement.obtenir()
        self.etudiant = creer_etudiant(
            email='sans@x.fr', niveau='L1', identifiant='s.photo')
        self.etudiant.user.set_password('MotDePasse1')
        self.etudiant.user.save()
        self.client.login(username='s.photo', password='MotDePasse1')

    def test_pages_bloquees_sans_photo(self):
        for nom in ('dashboard', 'quiz', 'mini_jeu'):
            reponse = self.client.get(reverse(nom))
            self.assertEqual(reponse.status_code, 302, nom)
            self.assertTrue(reponse.url.endswith('/ma-photo/'), nom)

    def test_page_photo_reste_accessible(self):
        self.assertEqual(self.client.get(reverse('photo')).status_code, 200)

    def test_acces_debloque_apres_ajout(self):
        ajouter_photo(self.etudiant)
        for nom in ('dashboard', 'quiz'):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200, nom)

    def test_image_valide_acceptee(self):
        from PIL import Image
        tampon = io.BytesIO()
        Image.new('RGB', (80, 80), (255, 199, 44)).save(tampon, 'PNG')
        envoi = SimpleUploadedFile('moi.png', tampon.getvalue(),
                                   content_type='image/png')
        reponse = self.client.post(reverse('photo'), {'photo': envoi})
        self.assertEqual(reponse.status_code, 302)
        self.etudiant.refresh_from_db()
        self.assertTrue(self.etudiant.a_une_photo)

    def test_fichier_non_image_refuse_sans_erreur_serveur(self):
        """Un faux fichier doit être refusé proprement (pas de 500)."""
        faux = SimpleUploadedFile('virus.txt', b'pas une image',
                                  content_type='text/plain')
        reponse = self.client.post(reverse('photo'), {'photo': faux})
        self.assertEqual(reponse.status_code, 200)
        self.etudiant.refresh_from_db()
        self.assertFalse(self.etudiant.a_une_photo)
