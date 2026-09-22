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
    """Réponses d'un étudiant au questionnaire de compatibilité (25 questions).

    Les réponses sont stockées dans un dictionnaire ``code -> valeur`` :

    - ``choix``   : la valeur de l'option (chaîne)
    - ``multi``   : la liste des valeurs cochées
    - ``texte``   : la chaîne saisie
    - ``echelle`` : un entier de 0 à 10

    Ce format souple permet d'ajouter ou de modifier des questions sans
    migration. Le catalogue fait foi : voir ``parrainage.questions``.
    """

    etudiant = models.OneToOneField(
        Etudiant, on_delete=models.CASCADE, related_name='questionnaire'
    )
    donnees = models.JSONField(default=dict, blank=True)
    date_soumission = models.DateTimeField(auto_now=True)
    # Une fois figé, le questionnaire n'est plus modifiable (verrouillage).
    verrouille = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Réponse au questionnaire'
        verbose_name_plural = 'Réponses aux questionnaires'

    def __str__(self):
        return f"Questionnaire de {self.etudiant.nom_complet}"

    # ------------------------------------------------------- Lecture
    def valeur(self, code):
        """Valeur brute d'une réponse, ou None si non répondue."""
        return (self.donnees or {}).get(code)

    def choix(self, code):
        """Valeur d'une question à choix unique."""
        v = self.valeur(code)
        return v if isinstance(v, str) and v != '' else None

    def multi(self, code):
        """Liste des valeurs cochées pour une question à choix multiples."""
        v = self.valeur(code)
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    def texte(self, code):
        """Texte saisi, ou chaîne vide."""
        v = self.valeur(code)
        return v.strip() if isinstance(v, str) else ''

    def nombre(self, code):
        """Note entière, ou None."""
        v = self.valeur(code)
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------ Complétude
    def reponses_manquantes(self):
        """Codes des questions obligatoires non répondues pour ce niveau."""
        from parrainage.questions import questions_pour

        manquantes = []
        for q in questions_pour(self.etudiant.niveau):
            if q.facultatif:
                continue
            v = self.valeur(q.code)
            vide = v in (None, '', [])
            if vide:
                manquantes.append(q.code)
        return manquantes

    @property
    def est_complete(self):
        return not self.reponses_manquantes()

    # ----------------------------------------------- Lecture « humaine »
    def reponses_lisibles(self):
        """Liste (question, libellé de la réponse) pour l'affichage.

        Sert à l'admin et aux fiches profil : on montre le texte de la
        question et un rendu lisible de la réponse.
        """
        from parrainage.questions import libelle_option, questions_pour

        lignes = []
        for q in questions_pour(self.etudiant.niveau):
            v = self.valeur(q.code)
            if v in (None, '', []):
                rendu = '—'
            elif q.type == 'multi':
                rendu = ', '.join(
                    libelle_option(q.code, x, self.etudiant.niveau)
                    for x in self.multi(q.code)
                )
            elif q.type == 'choix':
                rendu = libelle_option(q.code, v, self.etudiant.niveau)
            elif q.type == 'echelle':
                rendu = f"{v}/10"
            else:
                rendu = str(v)
            lignes.append((q, rendu))
        return lignes


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
