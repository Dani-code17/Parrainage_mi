from django import forms

from parrainage.models import Etudiant, ReponseQuestionnaire


class InscriptionForm(forms.Form):
    """Première étape : l'étudiant choisit son nom dans la liste fournie.

    La sélection par dropdown + mot de passe évite les usurpations.
    L'étudiant choisit l'entrée qui correspond à son plein nom dans le CSV.
    """

    etudiant_choisi = forms.ModelChoiceField(
        queryset=Etudiant.objects.none(),
        label="Sélectionnez votre nom dans la liste",
        empty_label="— Choisissez votre profil —",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    mot_de_passe = forms.CharField(
        label="Créez votre mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=6,
    )
    confirmation = forms.CharField(
        label="Confirmez le mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, phase='inscription', **kwargs):
        super().__init__(*args, **kwargs)
        # Proposés : les étudiants de la liste blanche qui n'ont pas encore
        # de compte d'accès (user est None).
        if phase == 'inscription':
            self.fields['etudiant_choisi'].queryset = (
                Etudiant.objects.filter(user__isnull=True)
            )

    def clean(self):
        cleaned = super().clean()
        mp = cleaned.get('mot_de_passe')
        conf = cleaned.get('confirmation')
        if mp and conf and mp != conf:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned


class VerrouillageMixin:
    """Empêche la modification d'un questionnaire déjà validé.

    Règle métier : une fois les réponses envoyées, l'étudiant ne peut plus
    les modifier. Le contrôle est fait côté serveur, pas seulement dans le
    template.
    """

    def deja_valide(self):
        return bool(getattr(self.instance, 'etudiant', None)
                    and self.instance.etudiant.a_valide_questionnaire
                    and self.instance.pk
                    and self.instance.est_complete)

    def desactiver(self):
        for champ in self.fields.values():
            champ.disabled = True
            champ.widget.attrs['disabled'] = True
            champ.required = False

    def clean(self):
        cleaned = super().clean()
        if self.deja_valide():
            raise forms.ValidationError(
                "Vos réponses sont déjà enregistrées et ne peuvent plus être modifiées."
            )
        return cleaned


class QuestionnaireForm(VerrouillageMixin, forms.ModelForm):
    """Le quiz de 15 questions, chacune notée de 1 à 5.

    Une fois le questionnaire validé, les champs sont désactivés et toute
    tentative d'envoi est refusée côté serveur.
    """

    class Meta:
        model = ReponseQuestionnaire
        fields = [f'q{i}' for i in range(1, 16)]
        widgets = {
            f'q{i}': forms.Select(choices=[(k, v) for k, v in [(1,'1 - Pas du tout'), (2,'2'), (3,'3 - Neutre'), (4,'4'), (5,'5 - Totalement')]], attrs={'class':'form-select'})
            for i in range(1, 16)
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select quiz-select'
        # Questionnaire déjà validé -> lecture seule.
        if self.deja_valide():
            self.desactiver()

    @property
    def verrouille(self):
        """Indique au template que le questionnaire n'est plus modifiable."""
        return self.deja_valide()


class ConnexionForm(forms.Form):
    """Connexion par identifiant court (« k.tanoh »)."""

    identifiant = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ex. k.tanoh',
            'autofocus': True,
            'autocapitalize': 'none',
            'autocomplete': 'username',
        }),
    )
    mot_de_passe = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'current-password',
        }),
    )

    def clean_identifiant(self):
        return (self.cleaned_data.get('identifiant') or '').strip()


class PhotoForm(forms.ModelForm):
    """Ajout ou remplacement de la photo de profil.

    Modifiable tant que l'on n'est pas entré dans la phase teasing : après,
    les binômes sont calculés et la photo ne doit plus bouger.
    """

    class Meta:
        model = Etudiant
        fields = ['photo']
        widgets = {
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
        }

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            return photo
        # 5 Mo maximum
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La photo ne doit pas dépasser 5 Mo.")
        # Formats d'image acceptés
        import imghdr
        try:
            type_detecte = imghdr.what(photo)
        except Exception:
            type_detecte = None
        if type_detecte not in ('jpeg', 'png', 'gif', 'webp', 'bmp'):
            raise forms.ValidationError(
                "Le fichier doit être une image (JPG, PNG, GIF ou WEBP)."
            )
        return photo
