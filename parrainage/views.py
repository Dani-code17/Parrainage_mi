from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (
    Etudiant, ReponseQuestionnaire, ParametreEvenement, DemandeForcage
)
from .forms import (
    InscriptionForm, QuestionnaireForm, ConnexionForm
)
from .matching import (
    calculer_matchs, question_commune, score_affichable,
    match_du_l1, matchs_du_l3, statistiques,
)


# ---------------------------------------------------------------- Helpers

def parametres():
    return ParametreEvenement.obtenir()


def get_etudiant(request):
    """Retourne l'étudiant connecté ou None."""
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.etudiant
    except Etudiant.DoesNotExist:
        return None


def verifier_phase(phase_requise):
    """Décorateur: bloque l'accès si la phase de l'événement est différente."""
    def decorator(view_func):
        def _wrapped(request, *args, **kwargs):
            p = parametres()
            if p.phase_actuelle != phase_requise:
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ---------------------------------------------------------------- Pages publiques

def home(request):
    """Page d'accueil avec compte à rebours."""
    p = parametres()
    maintenant = timezone.now()
    contexte = {
        'parametre_evenement': p,
        'maintenant': maintenant,
        'dates': {
            'fermeture_inscriptions': p.date_fermeture_inscriptions,
            'teasing': p.date_heure_teasing,
            'revelation': p.date_heure_revelation,
        },
    }
    # Calcul des délais en secondes
    contexte['secondes_inscription'] = (
        (p.date_fermeture_inscriptions - maintenant).total_seconds()
        if p.date_fermeture_inscriptions else None
    )
    if request.user.is_authenticated:
        etudiant = get_etudiant(request)
        if etudiant:
            return redirect('dashboard')
    return render(request, 'parrainage/home.html', contexte)


def inscription_view(request):
    """Étape 1 : l'étudiant choisit son profil dans la liste et crée son compte."""
    p = parametres()
    if p.phase_actuelle != ParametreEvenement.Phase.INSCRIPTION:
        messages.info(request, "Les inscriptions sont terminées.")
        return redirect('home')

    if request.method == 'POST':
        form = InscriptionForm(request.POST, phase=p.phase_actuelle)
        if form.is_valid():
            etudiant = form.cleaned_data['etudiant_choisi']
            mdp = form.cleaned_data['mot_de_passe']

            # L'étudiant ne doit pas encore avoir de compte
            if hasattr(etudiant, 'user') and etudiant.user_id:
                messages.error(request, "Ce profil possède déjà un compte. Connectez-vous.")
                return redirect('login')

            user = User.objects.create_user(
                username=etudiant.email,
                email=etudiant.email,
                password=mdp,
                first_name=etudiant.prenom,
                last_name=etudiant.nom,
            )
            etudiant.user = user
            etudiant.save()

            # Login automatique
            user = authenticate(username=etudiant.email, password=mdp)
            if user:
                login(request, user)
                messages.success(request, f"Bienvenue {etudiant.prenom} !")
                return redirect('quiz')
    else:
        form = InscriptionForm(phase=p.phase_actuelle)

    return render(request, 'parrainage/inscription.html', {
        'form': form, 'parametre_evenement': p,
    })


@login_required
def quiz_view(request):
    """Le questionnaire de 15 questions.

    Accessible tant que la phase est « inscription », **et** tant que les
    réponses n'ont pas été validées : ensuite le questionnaire est en
    lecture seule (contrôle serveur, pas seulement visuel).
    """
    p = parametres()
    etudiant = get_etudiant(request)
    if not etudiant:
        messages.error(request, "Vous n'êtes pas reconnu comme étudiant.")
        return redirect('home')

    questionnaire, _ = ReponseQuestionnaire.objects.get_or_create(etudiant=etudiant)
    deja_valide = etudiant.a_valide_questionnaire and questionnaire.est_complete

    # Après verrouillage (phase ou validation), on ne modifie plus rien.
    phase_fermee = p.phase_actuelle != ParametreEvenement.Phase.INSCRIPTION
    if deja_valide or phase_fermee:
        return render(request, 'parrainage/quiz.html', {
            'form': QuestionnaireForm(instance=questionnaire),
            'etudiant': etudiant,
            'parametre_evenement': p,
            'verrouille': deja_valide,
            'phase_fermee': phase_fermee and not deja_valide,
            'lecture_seule': True,
        })

    if request.method == 'POST':
        form = QuestionnaireForm(request.POST, instance=questionnaire)
        if form.is_valid():
            q = form.save(commit=False)
            q.etudiant = etudiant
            q.save()
            etudiant.a_valide_questionnaire = True
            etudiant.save(update_fields=['a_valide_questionnaire'])
            messages.success(
                request,
                "Vos réponses sont enregistrées. Elles ne peuvent plus être "
                "modifiées : contactez l'équipe en cas d'erreur."
            )
            return redirect('dashboard')
    else:
        form = QuestionnaireForm(instance=questionnaire)

    return render(request, 'parrainage/quiz.html', {
        'form': form, 'etudiant': etudiant, 'parametre_evenement': p,
        'verrouille': False, 'phase_fermee': False, 'lecture_seule': False,
    })


def connexion_view(request):
    """Connexion par identifiant uniquement."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ConnexionForm(request.POST)
        if form.is_valid():
            saisi = form.cleaned_data['identifiant']
            mdp = form.cleaned_data['mot_de_passe']

            # Le username du compte est l'identifiant. On tolère une casse
            # différente en retrouvant l'identifiant exact depuis la base.
            user = authenticate(request, username=saisi, password=mdp)
            if user is None:
                etudiant = Etudiant.objects.filter(
                    identifiant__iexact=saisi).first()
                if etudiant and etudiant.user:
                    user = authenticate(request,
                                        username=etudiant.user.username,
                                        password=mdp)

            if user is not None and user.is_active:
                login(request, user)
                return redirect('dashboard')
            messages.error(request, "Identifiant ou mot de passe incorrect.")
    else:
        form = ConnexionForm()

    return render(request, 'parrainage/connexion.html', {'form': form})


def deconnexion_view(request):
    logout(request)
    return redirect('home')


# ---------------------------------------------------------------- Dashboard (connecté)

@login_required
def dashboard(request):
    """Espace personnel selon la phase et le profil."""
    etudiant = get_etudiant(request)
    if not etudiant:
        return redirect('home')

    p = parametres()
    context = {
        'etudiant': etudiant,
        'parametre_evenement': p,
        'phase': p.phase_actuelle,
        'est_L3': etudiant.est_L3,
        'est_L1': etudiant.est_L1,
    }

    # Les demandes de l'étudiant (L3).
    if etudiant.est_L3:
        context['demandes_l3'] = DemandeForcage.objects.filter(demandeur=etudiant)

    # Les demandes reçues (L1).
    else:
        context['demandes_recues'] = DemandeForcage.objects.filter(cible=etudiant)

    # Phase teasing : afficher l'indice de compatibilité.
    if p.phase_actuelle == ParametreEvenement.Phase.TEASING:
        mes_matchs = matchs_de(etudiant)
        context['mes_matchs'] = mes_matchs
        if mes_matchs:
            # Un indice par personne à découvrir (le L3 en a un par filleul).
            context['indices'] = [
                {'match': m, 'indice': question_commune(m['l1'], m['l3'])}
                for m in mes_matchs
            ]

    # Révélation déclenchée (manuellement) : rendre le match visible.
    if p.revelation_declenchee_manuellement:
        context['revelation_active'] = True
        context['mes_matchs'] = matchs_de(etudiant)

    return render(request, 'parrainage/dashboard.html', context)


def matchs_de(etudiant):
    """Tous les binômes d'un étudiant (plusieurs pour un L3, un seul pour un L1)."""
    if etudiant.est_L1:
        m = match_du_l1(etudiant)
        return [m] if m else []
    return matchs_du_l3(etudiant)


def mon_match(etudiant):
    """Premier binôme d'un étudiant, ou None (compatibilité)."""
    trouves = matchs_de(etudiant)
    return trouves[0] if trouves else None


@login_required
def teasing_view(request):
    """Page teasing : indices sur ses binômes, noms masqués."""
    etudiant = get_etudiant(request)
    if not etudiant:
        return redirect('home')

    p = parametres()
    if p.phase_actuelle not in [ParametreEvenement.Phase.TEASING, ParametreEvenement.Phase.REVELATION]:
        return redirect('dashboard')

    mes_matchs = matchs_de(etudiant)
    indices = [
        {'match': m, 'indice': question_commune(m['l1'], m['l3'])}
        for m in mes_matchs
    ]

    return render(request, 'parrainage/teasing.html', {
        'etudiant': etudiant,
        'mes_matchs': mes_matchs,
        'indices': indices,
        'match': mon_match(etudiant),
        'parametre_evenement': p,
    })


@login_required
def mini_jeu(request):
    """Page du dé virtuel de la compatibilité."""
    etudiant = get_etudiant(request)
    return render(request, 'parrainage/mini_jeu.html', {
        'etudiant': etudiant,
    })


# ---------------------------------------------------------------- Révélation publique

@login_required
def revelation_view(request):
    """Écran de projection : tous les binômes publics avec score 0-100.

    Les binômes sont regroupés par parrain/marraine, puisque chacun peut
    encadrer plusieurs filleuls. Aucune mention de priorité n'apparaît.
    """
    p = parametres()
    if not p.revelation_declenchee_manuellement:
        messages.info(request, "La révélation n'a pas encore été déclenchée par l'équipe.")
        return redirect('dashboard')

    matchs = calculer_matchs()

    # Regroupement par L3 : {l3, filleuls: [{l1, score}], score_moyen}
    groupes = {}
    for m in matchs:
        entree = groupes.setdefault(m['l3'].id, {'l3': m['l3'], 'filleuls': []})
        entree['filleuls'].append({
            'l1': m['l1'],
            'score': score_affichable(m['score']),
        })

    liste = []
    for entree in groupes.values():
        entree['filleuls'].sort(key=lambda f: -f['score'])
        scores = [f['score'] for f in entree['filleuls']]
        entree['score_moyen'] = round(sum(scores) / len(scores)) if scores else 0
        entree['nb_filleuls'] = len(scores)
        liste.append(entree)
    liste.sort(key=lambda e: (-e['score_moyen'], e['l3'].nom))

    return render(request, 'parrainage/revelation.html', {
        'groupes': liste,
        'matchs': matchs,
        'stats': statistiques(),
        'parametre_evenement': p,
    })


# ------------------------------------------------- L'association est décidée par l'admin
#
# Les étudiants ne peuvent pas proposer de binôme. Seule l'équipe, depuis
# l'administration Django, crée une association entre un L3 et un L1 : ce
# binôme devient alors prioritaire et s'affiche 100/100, sans mention
# particulière sur le site public.
