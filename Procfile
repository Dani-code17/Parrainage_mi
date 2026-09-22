# Démarrage automatique du serveur en production.
#
# Cet ordre est important :
#   1. appliquer les migrations (crée ou met à jour la base)
#   2. rassembler les fichiers statiques (CSS, JS, logo)
#   3. lancer Gunicorn
#
# Les identifiants des étudiants se génèrent avec :
#   python manage.py importer_etudiants
# (à faire une seule fois, depuis le terminal de l'hébergeur)

release: python manage.py migrate --noinput && python manage.py collectstatic --noinput

web: gunicorn config.wsgi:application --config gunicorn.conf.py
