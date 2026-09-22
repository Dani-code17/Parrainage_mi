# Guide de déploiement — Parrainage MIAGE

Ce guide couvre la mise en ligne sur **un serveur (école / Oracle Cloud)** et
la **remise à zéro de la base à distance**.

---

## 1. Ce dont vous avez besoin

| Élément | Détail |
|---|---|
| Un serveur | VPS, serveur de l'école, ou instance Oracle Cloud |
| PostgreSQL | Sur le même serveur (recommandé) ou une base fournie |
| Python 3.10+ | `sudo apt install python3 python3-pip python3-venv` |
| Un nom de domaine | Ex. `parrainage.mon-ecole.ci` (facultatif mais conseillé) |

> ⚠️ **Pourquoi pas SQLite en ligne ?** Il ne gère pas les écritures
> simultanées. Avec 127 étudiants qui répondent en même temps, des erreurs
> « database is locked » sont probables. PostgreSQL évite ce problème.

---

## 2. Créer la base PostgreSQL

Sur le serveur :

```bash
sudo -u postgres psql
```

Puis, dans l'invite PostgreSQL :

```sql
CREATE DATABASE parrainage;
CREATE USER parrainage WITH PASSWORD 'un-mot-de-passe-solide';
GRANT ALL PRIVILEGES ON DATABASE parrainage TO parrainage;
ALTER DATABASE parrainage OWNER TO parrainage;
\q
```

---

## 3. Installer l'application

```bash
cd /var/www
git clone https://github.com/Dani-code17/Parrainage_mi.git parrainage
cd parrainage

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Configurer l'environnement

```bash
cp .env.example .env
nano .env
```

Remplissez au minimum :

```ini
DJANGO_SECRET_KEY=<clé générée ci-dessous>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=parrainage.mon-ecole.ci
DJANGO_CSRF_TRUSTED_ORIGINS=https://parrainage.mon-ecole.ci
DATABASE_URL=postgres://parrainage:un-mot-de-passe-solide@localhost:5432/parrainage
```

Pour générer la clé secrète :

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

> 🔐 Le fichier `.env` ne doit **jamais** être publié sur GitHub (il est déjà
> exclu par `.gitignore`).

---

## 5. Préparer la base et les comptes

```bash
python manage.py migrate
python manage.py collectstatic --noinput

# Le compte de l'équipe
python manage.py createsuperuser
```

**Importer les étudiants et générer leurs identifiants :**

```bash
# Les listes doivent être présentes dans donnees/
python manage.py importer_etudiants --export identifiants.csv
```

Récupérez `identifiants.csv` sur votre machine :

```bash
# Depuis votre poste local
scp utilisateur@serveur:/var/www/parrainage/identifiants.csv .
```

> 🔐 Ce fichier contient **tous les mots de passe en clair**. Transmettez-le
> par un canal privé, et supprimez-le du serveur ensuite :
> `rm identifiants.csv`

---

## 6. Lancer le serveur

```bash
gunicorn config.wsgi:application --config gunicorn.conf.py
```

Pour qu'il tourne en permanence, créez un service systemd
(`/etc/systemd/system/parrainage.service`) :

```ini
[Unit]
Description=Parrainage MIAGE
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/parrainage
EnvironmentFile=/var/www/parrainage/.env
ExecStart=/var/www/parrainage/venv/bin/gunicorn config.wsgi:application --config gunicorn.conf.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now parrainage
```

Placez ensuite **Nginx** devant, pour le domaine et le HTTPS :

```nginx
server {
    listen 80;
    server_name parrainage.mon-ecole.ci;

    location /static/ { alias /var/www/parrainage/staticfiles/; }
    location /media/  { alias /var/www/parrainage/media/; }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 10M;   # photos de profil
    }
}
```

Puis HTTPS gratuit :

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d parrainage.mon-ecole.ci
```

---

## 7. ⭐ Remettre la base à zéro EN LIGNE

C'est la question centrale : **comment repartir de zéro quand le site est en
ligne ?**

Il suffit de se connecter au serveur et de lancer la commande :

```bash
ssh utilisateur@serveur
cd /var/www/parrainage
source venv/bin/activate

python manage.py remettre_a_zero
```

La commande affiche ce qu'elle va supprimer et demande confirmation :

```
Vont être supprimés :
   - 127 questionnaire(s) et leurs réponses
   - 3 association(s) prioritaire(s)
   - l'état « a répondu » de 127 étudiant(s)
   (les 127 étudiants et leurs identifiants sont CONSERVÉS)

Confirmer ? [o/N]
```

### Les deux modes

| Commande | Effet |
|---|---|
| `remettre_a_zero` | Efface réponses + associations, remet la phase à **inscription**. **Garde les étudiants et leurs identifiants.** |
| `remettre_a_zero --tout` | **Supprime aussi les étudiants** et leurs comptes. Demande de taper `SUPPRIMER TOUT`. |

Pour un test grandeur nature, c'est la **première** qu'il faut : les
étudiants gardent leurs identifiants déjà distribués, seules leurs réponses
sont effacées.

### Sans confirmation (script, tâche planifiée)

```bash
python manage.py remettre_a_zero --oui
```

### Vérifier l'état sans rien modifier

```bash
python manage.py shell -c "
from parrainage.models import Etudiant, ReponseQuestionnaire, DemandeForcage, ParametreEvenement
print('Étudiants    :', Etudiant.objects.count())
print('Ont répondu  :', Etudiant.objects.filter(a_valide_questionnaire=True).count())
print('Questionnaires:', ReponseQuestionnaire.objects.count())
print('Associations :', DemandeForcage.objects.count())
print('Phase        :', ParametreEvenement.obtenir().phase_actuelle)
"
```

---

## 8. Autres opérations courantes en ligne

### Changer de phase

```bash
python manage.py shell -c "
from parrainage.models import ParametreEvenement
p = ParametreEvenement.obtenir()
p.phase_actuelle = 'teasing'   # ou verrouille, revelation
p.save()
print('Phase :', p.phase_actuelle)
"
```

Ou depuis l'admin web : *Paramètre de l'événement* → actions.

### Régénérer les identifiants

```bash
python manage.py importer_etudiants --mot-de-passe --export identifiants.csv
```

Puis récupérer le fichier (`scp`), le distribuer, et **le supprimer du
serveur**.

### Mettre à jour le code

```bash
cd /var/www/parrainage
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart parrainage
```

---

## 9. Sauvegarder la base (à faire avant chaque test)

```bash
pg_dump parrainage > sauvegarde_$(date +%F_%H%M).sql
```

Pour restaurer :

```bash
psql parrainage < sauvegarde_2026-09-22_1400.sql
```

> 💡 **Réflexe important** : faites une sauvegarde **avant** chaque
> `remettre_a_zero`. Il n'y a pas d'annulation possible.

---

## 10. Avant le vrai jour J — liste de contrôle

- [ ] `DJANGO_DEBUG=False` dans `.env`
- [ ] `DJANGO_SECRET_KEY` : une vraie clé aléatoire, pas celle par défaut
- [ ] `DJANGO_ALLOWED_HOSTS` : votre domaine, pas `*`
- [ ] HTTPS actif (certbot)
- [ ] Mot de passe du superutilisateur changé
- [ ] `identifiants.csv` **supprimé du serveur**
- [ ] Sauvegarde de la base faite
- [ ] Test : se connecter avec un identifiant, répondre au questionnaire
- [ ] Test : le questionnaire est bien verrouillé après validation
- [ ] Test : passer en phase *Teasing*, vérifier qu'aucun nom n'apparaît
- [ ] Sauvegarde de secours avant la révélation

---

## 11. En cas de problème

**« database is locked »** → vous êtes sur SQLite. Passez à PostgreSQL.

**Les pages s'affichent sans mise en forme** → les fichiers statiques ne sont
pas servis :

```bash
python manage.py collectstatic --noinput
sudo systemctl restart parrainage
```

**« Bad Request (400) »** → le domaine n'est pas dans `ALLOWED_HOSTS`.
Ajoutez-le dans `.env`, puis redémarrez.

**Erreur CSRF au moment de se connecter** → ajoutez votre domaine dans
`DJANGO_CSRF_TRUSTED_ORIGINS`, **avec** `https://`.

**Les photos ne s'affichent pas** → vérifiez la ligne `location /media/` dans
Nginx et que le dossier `media/` existe.
