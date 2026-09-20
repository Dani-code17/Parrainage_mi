from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class Etudiant(models.Model):
    """Un étudiant participant à l'événement de parrainage (L1 ou L3).

    Lié à un utilisateur Django (User) pour l'authentification.
    """

    class Niveau(models.TextChoices):
        L1 = 'L1', 'L1'
        L3 = 'L3', 'L3'

    class Sexe(models.TextChoices):
        F = 'F', 'Féminin'
        G = 'G', 'Masculin'

    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='etudiant'
    )
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    # Identifiant de connexion court, généré par l'équipe (ex. « k.tanoh »).
    identifiant = models.CharField(
        max_length=32, unique=True, null=True, blank=True,
        verbose_name="Identifiant de connexion",
        help_text="Généré automatiquement pour la connexion des étudiants.",
    )
    niveau = models.CharField(max_length=2, choices=Niveau.choices)
    # Groupe d'origine (L1, L3A, L3B) : purement informatif.
    groupe = models.CharField(max_length=10, blank=True, verbose_name="Groupe / classe")
    # Le sexe peut rester vide si la déduction depuis le prénom a échoué :
    # dans ce cas il est à corriger dans l'admin.
    sexe = models.CharField(max_length=1, choices=Sexe.choices, blank=True)
    # Vrai tant que le sexe n'a pas été confirmé par un humain.
    sexe_deduit = models.BooleanField(
        default=False, verbose_name="Sexe déduit (à vérifier)",
    )
    # Photo de profil : recommandée mais non obligatoire.
    photo = models.ImageField(
        upload_to='photos/', null=True, blank=True,
        verbose_name="Photo de profil",
        help_text="Une photo récente et reconnaissable. Recommandée : elle "
                  "apparaît sur l'écran de révélation.",
    )
    date_inscription = models.DateTimeField(auto_now_add=True)
    a_valide_questionnaire = models.BooleanField(default=False)
    est_eligible = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Étudiant(e)'
        verbose_name_plural = 'Étudiants'
        ordering = ['niveau', 'nom', 'prenom']

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.niveau})"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    @property
    def prenom_usuel(self):
        """Premier prénom, utilisé pour l'affichage court et les identifiants."""
        return (self.prenom or '').split()[0] if self.prenom else ''

    @property
    def initiales(self):
        """Initiales (prénom + nom), affichées à défaut de photo."""
        p = (self.prenom or ' ').strip()[:1].upper()
        n = (self.nom or ' ').strip()[:1].upper()
        return f"{p}{n}".strip() or '?'

    @property
    def a_une_photo(self):
        return bool(self.photo)

    @property
    def a_repondu(self):
        """Le questionnaire a-t-il été validé (donc verrouillé) ?"""
        return self.a_valide_questionnaire

    @property
    def est_L3(self):
        return self.niveau == self.Niveau.L3

    @property
    def est_L1(self):
        return self.niveau == self.Niveau.L1


class ReponseQuestionnaire(models.Model):
    """Réponses d'un étudiant aux 15 questions du quiz de compatibilité."""

    ECHILLE_CHOICES = [(i, str(i)) for i in range(1, 6)]

    etudiant = models.OneToOneField(
        Etudiant, on_delete=models.CASCADE, related_name='questionnaire'
    )
    # 15 questions notées de 1 (Pas du tout) à 5 (Totalement).
    # null=True permet de créer une ébauche avant soumission.
    q1 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Un bon parrain doit être un modèle de réussite scolaire.")
    q2 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="J'avoue mes lacunes à un aîné pour qu'il m'aide.")
    q3 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Je préfère un parrain strict sur les révisions.")
    q4 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Je veux aider mon match sur mes points forts.")
    q5 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Mon parrain me fait découvrir les bons plans autour de la fac.")
    q6 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Je suis partant pour des révisions en binôme.")
    q7 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Une séance café/discussion me semble indispensable.")
    q8 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Je préfère les activités de groupe.")
    q9 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Les L3 apportent une maturité précieuse aux L1.")
    q10 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Les différences d'âge sont un atout.")
    q11 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Je suis à l'aise pour parler de mon orientation avec un L3.")
    q12 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Sorties improvisées (5) ou soirées jeux tranquilles (1).")
    q13 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Prêt à relever un défi farfelu si mon match me le lance.")
    q14 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Bibliothèque silencieuse (1) ou foyer bruyant (5).")
    q15 = models.IntegerField(choices=ECHILLE_CHOICES, null=True, blank=True, verbose_name="Les amitiés naissent d'une entraide scolaire.")

    date_soumission = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réponse au questionnaire'
        verbose_name_plural = 'Réponses aux questionnaires'

    def __str__(self):
        return f"Questionnaire de {self.etudiant.nom_complet}"

    def reponses(self):
        """Retourne la liste ordonnée des 15 réponses."""
        return [getattr(self, f"q{i}") for i in range(1, 16)]

    @property
    def est_complete(self):
        return all(r is not None for r in self.reponses())


class DemandeForcage(models.Model):
    """Association prioritaire entre un L3 et un L1.

    Elle est créée par l'équipe depuis l'administration : le binôme est
    alors formé d'office, quel que soit le score calculé. Le statut
    'accepte' est celui d'une association active.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACCEPTE = 'accepte', 'Acceptée'
        REFUSE = 'refuse', 'Refusée'

    demandeur = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name='demandes_emises',
        limit_choices_to={'niveau': 'L3'}
    )
    cible = models.ForeignKey(
        Etudiant, on_delete=models.CASCADE, related_name='demandes_recues',
        limit_choices_to={'niveau': 'L1'}
    )
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE
    )
    date_demande = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Demande'
        verbose_name_plural = 'Demandes'
        unique_together = ('demandeur', 'cible')
        ordering = ['-date_demande']

    def __str__(self):
        return f"{self.demandeur} -> {self.cible} [{self.statut}]"


class ParametreEvenement(models.Model):
    """Singleton qui gère la phase actuelle de l'événement."""

    class Phase(models.TextChoices):
        INSCRIPTION = 'inscription', 'Inscription'
        VERROUILLE = 'verrouille', 'Verrouillage'
        TEASING = 'teasing', 'Teasing'
        REVELATION = 'revelation', 'Révélation finale'

    phase_actuelle = models.CharField(
        max_length=20, choices=Phase.choices, default=Phase.INSCRIPTION
    )
    date_fermeture_inscriptions = models.DateTimeField(null=True, blank=True)
    date_heure_teasing = models.DateTimeField(null=True, blank=True)
    date_heure_revelation = models.DateTimeField(null=True, blank=True)
    revelation_declenchee_manuellement = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Paramètre de l\'événement'

    def __str__(self):
        return f"Phase actuelle: {self.get_phase_actuelle_display()}"

    def save(self, *args, **kwargs):
        """Assure le singleton: il n'y a qu'une seule ligne dans la table."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def obtenir(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
