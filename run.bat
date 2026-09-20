@echo off
REM ============================================================
REM  Lancement du serveur de développement avec le Python DU VENV
REM  (n'utilise jamais le Python global : celui-ci n'a pas crispy_forms)
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERREUR] Environnement virtuel introuvable : venv\Scripts\python.exe
    echo          Creez-le avec :
    echo              python -m venv venv
    echo              venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Preparation de la base de donnees...
"venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 (
    echo [ERREUR] La migration a echoue.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Serveur : http://127.0.0.1:8000/
echo   Admin   : http://127.0.0.1:8000/admin/
echo   (Ctrl+C pour arreter)
echo ============================================================
echo.

"venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
endlocal
