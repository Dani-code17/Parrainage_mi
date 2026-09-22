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

## 6. Lancer le serveur en permanent (IP, port 80, Nginx)

Objectif : le site répond sur **http://51.222.205.47** (sans `:8000`), tourne
même quand vous fermez la session SSH, et reste rapide.

### a) Gunicorn en service systemd

Le serveur de développement (`runserver`) s'arrête dès que le terminal se
ferme. On le remplace par Gunicorn, lancé par systemd.

Adaptez les chemins (`/home/ubuntu51/parrainage`) et l'utilisateur
(`ubuntu51`) à votre serveur :

```bash
sudo nano /etc/systemd/system/parrainage.service
```

```ini
[Unit]
Description=Parrainage MIAGE
After=network.target

[Service]
User=ubuntu51
Group=www-data
WorkingDirectory=/home/ubuntu51/parrainage
EnvironmentFile=/home/ubuntu51/parrainage/.env
ExecStart=/home/ubuntu51/parrainage/venv/bin/gunicorn config.wsgi:application --config gunicorn.conf.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now parrainage
sudo systemctl status parrainage
```

> Le service doit afficher **`active (running)`**. S'il échoue :
> `sudo journalctl -u parrainage -n 40` montre la cause.

### b) Nginx devant Gunicorn

```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/parrainage
```

```nginx
server {
    listen 80 default_server;
    server_name 51.222.205.47;

    # Taille des photos de profil
    client_max_body_size 10M;

    # Fichiers statiques servis directement par Nginx (rapide)
    location /static/ {
        alias /home/ubuntu51/parrainage/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias /home/ubuntu51/parrainage/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

Activez le site et rechargez :

```bash
sudo ln -sf /etc/nginx/sites-available/parrainage /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t                      # doit dire « syntax is ok »
sudo systemctl reload nginx
```

### c) Ouvrir le port 80

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow OpenSSH

# Le port 8000 n'est plus utile de l'extérieur : Nginx passe par la boucle locale.
sudo ufw delete allow 8000/tcp 2>/dev/null

sudo ufw status
```

### d) Adapter la configuration Django

Nginx sert le site sur le port 80 : la redirection HTTPS doit rester
désactivée (pas encore de certificat).

```bash
cd ~/parrainage && nano .env
```

Vérifiez que ces deux lignes sont présentes :

```ini
DJANGO_HTTPS=0
DJANGO_SSL_REDIRECT=0
```

Puis redémarrez :

```bash
sudo systemctl restart parrainage
```

Le site est maintenant sur **http://51.222.205.47** — sans `:8000`.

### e) Vérifier

```bash
curl -I http://51.222.205.47
```

Doit répondre **`HTTP/1.1 200 OK`**.

Depuis un navigateur : la page d'accueil s'affiche, avec le logo.

### f) Mettre à jour le code ensuite

```bash
cd ~/parrainage
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart parrainage
```

---

## 6 bis. Et le HTTPS ?

Un cadenas **reconnu par les navigateurs** exige un **nom de domaine** :
Let's Encrypt refuse de certifier une adresse IP seule. Aucun contournement
honnête n'existe.

Deux situations :

**Sans domaine** (votre cas actuel) — le site reste en `http://`. Le
navigateur n'affiche **aucun avertissement** en HTTP simple : il montre
juste une icône « information » discrète. Rien d'alarmant pour les
étudiants, contrairement à un certificat auto-signé qui déclencherait un
écran rouge « connexion non privée » — à éviter absolument.

**Avec un domaine** (~10 €/an) — le HTTPS devient gratuit et automatique :

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d votredomaine.com
```

Puis dans `.env` :

```ini
DJANGO_HTTPS=1
DJANGO_SSL_REDIRECT=1
DJANGO_ALLOWED_HOSTS=votredomaine.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://votredomaine.com
```

```bash
sudo systemctl restart parrainage
```

> 💡 **Conseil** : pour un événement avec 127 étudiants, le domaine à 10 €
> vaut largement l'investissement. C'est la seule façon d'avoir le cadenas,
> et ça évite toutes les questions.

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
- [ ] `DJANGO_ALLOWED_HOSTS` : l'adresse du site, pas `*`
- [ ] `DJANGO_HTTPS` et `DJANGO_SSL_REDIRECT` cohérents avec le mode
      (à `0` en HTTP, à `1` une fois le certificat en place)
- [ ] Le service `parrainage` est `active (running)` et démarre au boot
- [ ] Le site répond sur le **port 80**, sans `:8000`
- [ ] `sudo nginx -t` ne signale aucune erreur
- [ ] Mot de passe du superutilisateur changé
- [ ] `identifiants.csv` **supprimé du serveur** après distribution
- [ ] Sauvegarde de la base faite
- [ ] Test : se connecter avec un identifiant, répondre au questionnaire
- [ ] Test : le questionnaire est bien verrouillé après validation
- [ ] Test : passer en phase *Teasing*, vérifier qu'aucun nom n'apparaît
- [ ] Test : les photos des parrains s'affichent à la révélation
- [ ] Sauvegarde de secours avant la révélation

### Commandes utiles le jour J

```bash
sudo systemctl status parrainage     # le site tourne-t-il ?
sudo systemctl restart parrainage    # le redémarrer
sudo journalctl -u parrainage -f     # suivre les erreurs en direct
sudo tail -f /var/log/nginx/error.log
```

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
