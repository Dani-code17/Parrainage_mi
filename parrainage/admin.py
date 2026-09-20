import csv
import io

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils.html import format_html

from .identifiants import creer_comptes, exporter_csv, generer_mot_de_passe
from .models import (
    Etudiant, ReponseQuestionnaire, DemandeForcage, ParametreEvenement
)
from .prenoms import deduire_sexe


class ImporterCsvActionForm(ActionForm):
    """Formulaire d'action contenant le champ pour uploader la liste blanche."""
    csv_liste_blanche = forms.FileField(
        label="Fichier CSV (liste blanche)",
        required=False,
    )


# ============================================================
# Actions personnalisées : import CSV de la liste blanche
# ============================================================

def importer_liste_blanche(modeladmin, request, queryset):
    """Importe un CSV (nom,prenom,niveau,sexe) : la liste des participants.

    Le sexe est déduit du prénom s'il n'est pas fourni. Les adresses e-mail
    ne sont plus utilisées : l'identifiant est la clé de connexion.
    """
    csv_file = request.FILES.get('csv_liste_blanche')
    if not csv_file:
        messages.error(request, "Veuillez choisir un fichier CSV.")
        return

    data = csv_file.read().decode('utf-8-sig')
    lecteur = csv.DictReader(io.StringIO(data), delimiter=choisir_separateur(data))

    crees, ignores, erreurs = 0, 0, []
    for ligne in lecteur:
        ligne = {k.strip().lower(): (v or '').strip()
                 for k, v in ligne.items() if k}
        nom = ligne.get('nom', '').upper()
        prenom = ligne.get('prenom', '')
        niveau = ligne.get('niveau', '').upper()
        sexe = ligne.get('sexe', '').upper()
        groupe = ligne.get('groupe', niveau)

        if not nom or not prenom:
            erreurs.append(f"Ligne incomplète : nom={nom!r}, prenom={prenom!r}")
            continue
        if niveau not in ['L1', 'L3']:
            erreurs.append(f"Niveau invalide pour {nom} {prenom} : {niveau!r}")
            continue

        # Adresse technique interne : l'e-mail n'est plus une clé d'accès.
        email = f"{slug(prenom)}.{slug(nom)}@participants.local"
        if Etudiant.objects.filter(email=email).exists():
            ignores += 1
            continue

        if sexe not in ['F', 'G']:
            sexe = deduire_sexe(prenom)
        Etudiant.objects.create(
            nom=nom, prenom=prenom, email=email, niveau=niveau,
            groupe=groupe, sexe=sexe, sexe_deduit=bool(sexe),
        )
        crees += 1

    msg = f"{crees} étudiant(s) importé(s)"
    if ignores:
        msg += f", {ignores} déjà présent(s)"
    if erreurs:
        msg += f", {len(erreurs)} erreur(s) : {erreurs[:3]}"
    messages.success(request, msg + ".")


def choisir_separateur(texte):
    """Devine le séparateur du CSV (virgule ou point-virgule)."""
    premiere = texte.splitlines()[0] if texte else ''
    return ';' if premiere.count(';') > premiere.count(',') else ','


def slug(texte):
    """Minuscule sans accent ni caractère spécial."""
    import unicodedata
    decompose = unicodedata.normalize('NFD', str(texte or ''))
    sans_accent = ''.join(c for c in decompose if unicodedata.category(c) != 'Mn')
    return ''.join(c for c in sans_accent.lower() if c.isalnum())


importer_liste_blanche.short_description = "Importer une liste d'étudiants (CSV)"


# ============================================================
# Actions : identifiants
# ============================================================

def generer_identifiants(modeladmin, request, queryset):
    """Crée les identifiants et mots de passe des étudiants sélectionnés."""
    resultats = creer_comptes(list(queryset), reinitialiser=False)
    crees = [r for r in resultats if r['cree']]
    messages.success(
        request,
        f"{len(crees)} identifiant(s) généré(s) sur {len(resultats)} étudiant(s). "
        "Utilisez « Exporter les identifiants (CSV) » pour récupérer la liste."
    )


generer_identifiants.short_description = "Générer les identifiants manquants"


def regenerer_mots_de_passe(modeladmin, request, queryset):
    """Attribue un nouveau mot de passe aux étudiants sélectionnés."""
    resultats = creer_comptes(list(queryset), reinitialiser=True)
    messages.success(
        request,
        f"{len(resultats)} mot(s) de passe régénéré(s). "
        "Utilisez « Exporter les identifiants (CSV) » pour récupérer la liste."
    )


regenerer_mots_de_passe.short_description = "Régénérer les mots de passe"


def exporter_identifiants(modeladmin, request, queryset):
    """Télécharge un CSV avec nom, identifiant et mot de passe.

    ⚠️ Les mots de passe ne sont affichés qu'une fois, à la création : cette
    action exporte les identifiants et, pour les comptes qui viennent d'être
    créés, le mot de passe en clair. Pour un compte existant dont le mot de
    passe a déjà été distribué, la colonne indique « (inchangé) » — utilisez
    « Régénérer les mots de passe » avant d'exporter.
    """
    resultats = creer_comptes(list(queryset), reinitialiser=False)

    contenu = exporter_csv(resultats)
    reponse = HttpResponse(contenu, content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = 'attachment; filename="identifiants.csv"'
    return reponse


exporter_identifiants.short_description = "Exporter les identifiants (CSV)"


# ============================================================
# Actions : changements de phase
# ============================================================

def passer_en_verrouillage(modeladmin, request, queryset):
    for p in queryset:
        p.phase_actuelle = ParametreEvenement.Phase.VERROUILLE
        p.save()
    messages.success(request, "Phase passée en « Verrouillage ».")
passer_en_verrouillage.short_description = "Passer en phase Verrouillage"


def passer_en_teasing(modeladmin, request, queryset):
    for p in queryset:
        p.phase_actuelle = ParametreEvenement.Phase.TEASING
        p.save()
    messages.success(request, "Phase passée en « Teasing ».")
passer_en_teasing.short_description = "Passer en phase Teasing"


def declencher_revelation(modeladmin, request, queryset):
    """Bouton « FORCER LA RÉVÉLATION » : montre tous les binômes."""
    for p in queryset:
        p.phase_actuelle = ParametreEvenement.Phase.REVELATION
        p.revelation_declenchee_manuellement = True
        p.save()
    messages.success(request, "Révélation déclenchée : tous les matchs sont visibles.")
declencher_revelation.short_description = "FORCER LA RÉVÉLATION (affiche les binômes)"


# ============================================================
# Admin Etudiant
# ============================================================

@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    """Gestion des étudiants : liste, sexe à vérifier, identifiants."""

    action_form = ImporterCsvActionForm
    list_display = ('nom', 'prenom', 'identifiant', 'niveau', 'groupe',
                    'sexe_affiche', 'a_valide_questionnaire', 'a_un_compte')
    list_filter = ('niveau', 'groupe', 'sexe', 'sexe_deduit',
                   'a_valide_questionnaire', 'est_eligible')
    search_fields = ('nom', 'prenom', 'identifiant', 'email')
    actions = [importer_liste_blanche, generer_identifiants,
               regenerer_mots_de_passe, exporter_identifiants]
    list_per_page = 50

    fieldsets = (
        ('Identité', {'fields': ('nom', 'prenom', 'niveau', 'groupe')}),
        ('Sexe', {
            'fields': ('sexe', 'sexe_deduit'),
            'description': "Le sexe déduit automatiquement est à confirmer. "
                           "Décochez « Sexe déduit » après vérification.",
        }),
        ('Connexion', {'fields': ('identifiant', 'user', 'email')}),
        ('État', {'fields': ('a_valide_questionnaire', 'est_eligible')}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('date_inscription',)
        return ()

    @admin.display(description="Sexe", ordering='sexe')
    def sexe_affiche(self, obj):
        if not obj.sexe:
            return format_html('<span style="color:#b00;">à renseigner</span>')
        libelle = obj.get_sexe_display()
        if obj.sexe_deduit:
            return format_html('{} <em style="color:#888;">(déduit)</em>', libelle)
        return libelle

    @admin.display(boolean=True, description="Compte créé")
    def a_un_compte(self, obj):
        return bool(obj.user_id and obj.identifiant)


# ============================================================
# Admin des réponses : voir ce que chacun a répondu
# ============================================================

def exporter_reponses(modeladmin, request, queryset):
    """Télécharge les réponses des étudiants sélectionnés (CSV)."""
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=';')
    entete = ['Nom', 'Prenoms', 'Niveau', 'Groupe', 'Identifiant', 'Depot']
    entete += [f'Q{i}' for i in range(1, 16)]
    ecrivain.writerow(entete)

    for questionnaire in queryset.select_related('etudiant'):
        e = questionnaire.etudiant
        ligne = [e.nom, e.prenom, e.niveau, e.groupe or '', e.identifiant or '',
                 questionnaire.date_soumission.strftime('%d/%m/%Y %H:%M')
                 if questionnaire.date_soumission else '']
        ligne += [v if v is not None else '' for v in questionnaire.reponses()]
        ecrivain.writerow(ligne)

    reponse = HttpResponse(tampon.getvalue(), content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = 'attachment; filename="reponses_questionnaires.csv"'
    return reponse


exporter_reponses.short_description = "Exporter les réponses (CSV)"


@admin.register(ReponseQuestionnaire)
class ReponseQuestionnaireAdmin(admin.ModelAdmin):
    """Consultation des réponses de chaque étudiant.

    Les réponses sont en lecture seule : elles appartiennent aux étudiants.
    """

    list_display = ('etudiant_nom', 'niveau_affiche', 'depot', 'apercu_reponses')
    list_filter = ('etudiant__niveau', 'etudiant__groupe')
    search_fields = ('etudiant__nom', 'etudiant__prenom', 'etudiant__identifiant')
    list_select_related = ('etudiant',)
    list_per_page = 50
    actions = [exporter_reponses]

    def get_readonly_fields(self, request, obj=None):
        return ('etudiant',) + tuple(f'q{i}' for i in range(1, 16)) + ('date_soumission',)

    def has_add_permission(self, request):
        # Les réponses sont saisies par les étudiants, pas par l'équipe.
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    @admin.display(description="Étudiant", ordering='etudiant__nom')
    def etudiant_nom(self, obj):
        return f"{obj.etudiant.nom} {obj.etudiant.prenom}"

    @admin.display(description="Niveau", ordering='etudiant__niveau')
    def niveau_affiche(self, obj):
        return obj.etudiant.niveau

    @admin.display(description="Déposé le", ordering='date_soumission')
    def depot(self, obj):
        return obj.date_soumission

    @admin.display(description="Réponses (q1 → q15)")
    def apercu_reponses(self, obj):
        return ' · '.join(str(v) if v is not None else '–' for v in obj.reponses())


# ============================================================
# Admin des associations — l'équipe décide des binômes prioritaires
# ============================================================

@admin.register(DemandeForcage)
class DemandeForcageAdmin(admin.ModelAdmin):
    """Association prioritaire entre un L3 et un L1, décidée par l'équipe.

    C'est le SEUL endroit où l'on décide qu'un binôme doit être formé
    d'office. Le site public n'en montre rien : le binôme s'affiche
    simplement avec un score de 100/100.

    Pour créer une association :
      1. « Ajouter une demande »
      2. choisir le L3 puis le L1
      3. laisser le statut sur « Acceptée »
    """

    list_display = ('demandeur', 'cible', 'statut', 'date_demande',
                    'est_affiche_comme_force')
    list_filter = ('statut', 'demandeur__groupe')
    search_fields = ('demandeur__nom', 'demandeur__prenom',
                     'demandeur__identifiant',
                     'cible__nom', 'cible__prenom', 'cible__identifiant')
    readonly_fields = ('date_demande',)
    list_select_related = ('demandeur', 'cible')
    list_per_page = 50

    fieldsets = (
        ('Binôme', {
            'fields': ('demandeur', 'cible'),
            'description': "Choisissez le parrain/marraine (L3) puis le "
                           "filleul/filleule (L1). Le binôme sera formé "
                           "d'office et affiché 100/100.",
        }),
        ('Décision', {'fields': ('statut', 'date_demande')}),
    )

    def get_changeform_initial_data(self, request):
        # Par défaut on crée une association active.
        return {'statut': DemandeForcage.Statut.ACCEPTE}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # On ne propose que des L3 comme parrains et des L1 comme filleuls.
        if db_field.name == 'demandeur':
            kwargs['queryset'] = Etudiant.objects.filter(
                niveau=Etudiant.Niveau.L3).order_by('nom', 'prenom')
        elif db_field.name == 'cible':
            kwargs['queryset'] = Etudiant.objects.filter(
                niveau=Etudiant.Niveau.L1).order_by('nom', 'prenom')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Forcé", boolean=False)
    def est_affiche_comme_force(self, obj):
        if obj.statut == DemandeForcage.Statut.ACCEPTE:
            return format_html('<b style="color:#0a7f34;">Oui — 100/100</b>')
        if obj.statut == DemandeForcage.Statut.EN_ATTENTE:
            return format_html('<span style="color:#888;">en attente</span>')
        return "—"


# ============================================================
# Admin ParametreEvenement (singleton qui gère les phases)
# ============================================================

@admin.register(ParametreEvenement)
class ParametreEvenementAdmin(admin.ModelAdmin):
    list_display = ('phase_actuelle', 'date_fermeture_inscriptions',
                    'date_heure_teasing', 'date_heure_revelation',
                    'revelation_declenchee_manuellement')
    actions = [passer_en_verrouillage, passer_en_teasing, declencher_revelation]

    fieldsets = (
        ('Phase actuelle', {
            'fields': ('phase_actuelle', 'revelation_declenchee_manuellement'),
        }),
        ('Calendrier', {
            'fields': ('date_fermeture_inscriptions', 'date_heure_teasing',
                       'date_heure_revelation'),
        }),
    )
