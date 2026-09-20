#!/usr/bin/env bash
# ============================================================
#  Lancement du serveur de développement avec le Python DU VENV
#  (n'utilise jamais le Python global : celui-ci peut ne pas
#   contenir crispy_forms / crispy_bootstrap5)
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

# Chemin du Python du venv, selon l'OS.
if [ -x "venv/Scripts/python.exe" ]; then        # Windows (Git Bash / MSYS)
    PY="venv/Scripts/python.exe"
elif [ -x "venv/bin/python" ]; then              # Linux / macOS
    PY="venv/bin/python"
else
    echo "[ERREUR] Environnement virtuel introuvable (venv/)."
    echo "         Créez-le avec :"
    echo "             python -m venv venv"
    echo "             venv/bin/python -m pip install -r requirements.txt   # ou venv\\Scripts\\python.exe sous Windows"
    exit 1
fi

echo "Préparation de la base de données..."
"$PY" manage.py migrate --noinput

echo
echo "============================================================"
echo "  Serveur : http://127.0.0.1:8000/"
echo "  Admin   : http://127.0.0.1:8000/admin/"
echo "  (Ctrl+C pour arrêter)"
echo "============================================================"
echo

exec "$PY" manage.py runserver 127.0.0.1:8000
