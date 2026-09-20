from parrainage.models import ParametreEvenement


def event_phase(request):
    """Expose la phase actuelle de l'événement à tous les templates."""
    parametres = None
    try:
        parametres = ParametreEvenement.obtenir()
    except Exception:
        parametres = None

    return {
        'parametre_evenement': parametres,
        'phase_actuelle': parametres.phase_actuelle if parametres else 'inscription',
    }
