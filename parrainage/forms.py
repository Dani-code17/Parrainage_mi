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


class QuestionnaireForm(VerrouillageMixin, forms.Form):
    """Questionnaire de 25 questions, construit depuis le catalogue.

    Le formulaire s'adapte au niveau de l'étudiant (la Q21 n'a pas la même
    formulation en L1 et en L3) et gère les quatre types de questions :
    choix unique, choix multiples, texte libre et note de 0 à 10.

    Une fois le questionnaire validé, les champs sont désactivés et toute
    tentative d'envoi est refusée côté serveur.
    """

    def __init__(self, *args, instance=None, **kwargs):
        from parrainage.questions import (
            TYPE_CHOIX, TYPE_ECHELLE, TYPE_MULTI, TYPE_TEXTE, questions_pour,
        )

        self.instance = instance
        self.questions = []
        niveau = None
        if instance is not None and instance.etudiant_id:
            niveau = instance.etudiant.niveau
            self.questions = questions_pour(niveau)

        super().__init__(*args, **kwargs)

        deja_repondu = (instance.donnees or {}) if instance is not None else {}

        for q in self.questions:
            obligatoire = not q.facultatif
            initial = deja_repondu.get(q.code)

            if q.type == TYPE_CHOIX:
                self.fields[q.code] = forms.ChoiceField(
                    label=q.texte,
                    choices=list(q.options),
                    required=obligatoire,
                    initial=initial,
                    widget=forms.RadioSelect(attrs={'class': 'choix-radio'}),
                )
            elif q.type == TYPE_MULTI:
                self.fields[q.code] = forms.MultipleChoiceField(
                    label=q.texte,
                    choices=list(q.options),
                    required=obligatoire,
                    initial=initial or [],
                    widget=forms.CheckboxSelectMultiple(attrs={'class': 'choix-case'}),
                )
            elif q.type == TYPE_ECHELLE:
                self.fields[q.code] = forms.IntegerField(
                    label=q.texte,
                    min_value=0, max_value=10,
                    required=obligatoire,
                    initial=initial if initial is not None else 5,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-range note-echelle',
                        'type': 'range', 'min': 0, 'max': 10, 'step': 1,
                    }),
                )
            else:  # TYPE_TEXTE
                self.fields[q.code] = forms.CharField(
                    label=q.texte,
                    required=obligatoire,
                    initial=initial or '',
                    widget=forms.Textarea(attrs={
                        'class': 'form-control',
                        'rows': 3,
                        'placeholder': 'Écris librement…',
                    }),
                )

        self.champs_par_code = {q.code: self.fields[q.code]
                                for q in self.questions if q.code in self.fields}

        for champ in self.fields.values():
            if not champ.widget.attrs.get('class'):
                champ.widget.attrs['class'] = 'form-control'

        if self.deja_valide():
            self.desactiver()

    # ---------------------------------------------------------- Validation
    def clean(self):
        from parrainage.questions import TYPE_MULTI

        cleaned = super().clean()

        # Respect du nombre maximal de choix (ex. « 3 valeurs max »).
        for q in self.questions:
            if q.type != TYPE_MULTI or not q.max_choix:
                continue
            choisis = cleaned.get(q.code) or []
            if len(choisis) > q.max_choix:
                self.add_error(
                    q.code,
                    f"Choisis au maximum {q.max_choix} réponses "
                    f"({len(choisis)} sélectionnées).",
                )
        return cleaned

    # -------------------------------------------------------------- Save
    def save(self, commit=True):
        """Écrit les réponses dans ``donnees`` (code -> valeur)."""
        donnees = dict(self.cleaned_data)
        self.instance.donnees = donnees
        if commit:
            self.instance.save()
        return self.instance

    @property
    def verrouille(self):
        """Indique au template que le questionnaire n'est plus modifiable."""
        return self.deja_valide()

    def questions_par_section(self):
        """Regroupe les questions dans l'ordre des sections (pour l'affichage)."""
        sections = []
        index = {}
        for q in self.questions:
            if q.section not in index:
                index[q.section] = {'section': q.section, 'questions': []}
                sections.append(index[q.section])
            index[q.section]['questions'].append(q)
        return sections

    def options_du_champ(self, code):
        """Options d'une question à choix, pour un rendu personnalisé."""
        champ = self.fields.get(code)
        return list(champ.choices) if champ else []

    def paires(self):
        """Liste ``(question, champ)`` dans l'ordre du questionnaire.

        Permet au template de parcourir les questions et leurs champs sans
        connaître les codes à l'avance.
        """
        return [(q, self[q.code]) for q in self.questions if q.code in self.fields]


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
