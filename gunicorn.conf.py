# =====================================================================
#  Serveur de production — Gunicorn
#
#  Lancement :
#     gunicorn config.wsgi:application \
#         --bind 0.0.0.0:8000 --workers 3 --timeout 60
#
#  3 ouvriers suffisent largement pour 127 étudiants. Le délai de 60 s
#  évite qu'une requête lente soit coupée pendant la révélation.
# =====================================================================

bind = "0.0.0.0:8000"
workers = 3
threads = 2
timeout = 60
graceful_timeout = 30
keepalive = 5

# Journalisation vers la sortie standard : lisible dans les journaux de
# l'hébergeur.
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Redémarre les ouvriers régulièrement (fuites mémoire éventuelles).
max_requests = 1000
max_requests_jitter = 100
