"""
Exemple de branchement Django pour les nouvelles pages.
À adapter à ton projet : garde tes propres vues si tu en as déjà.

1. Copie le dossier  templates/parrainage/  dans le dossier templates de ton app.
2. Copie  ../assets/css  et  ../assets/js  dans  <ton_app>/static/parrainage/
   (pour obtenir static/parrainage/css/style.css, static/parrainage/js/*.js).
3. Branche les URLs comme ci-dessous.
"""

from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    # Page d'accueil (landing)
    path("", TemplateView.as_view(template_name="parrainage/accueil.html"), name="accueil"),

    # Page de connexion : la vue LoginView fournit `form` (avec form.errors) et `next`
    path(
        "connexion/",
        auth_views.LoginView.as_view(
            template_name="parrainage/connexion.html",
            redirect_authenticated_user=True,
        ),
        name="connexion",
    ),
]

# Dans settings.py, indique où aller après la connexion, par exemple :
# LOGIN_URL = "connexion"
# LOGIN_REDIRECT_URL = "questionnaire"   # nom de l'URL de ton questionnaire
