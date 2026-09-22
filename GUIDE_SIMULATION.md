# Guide de simulation — Parrainage MIAGE

Ce guide sert à **tester l'événement de bout en bout** avec des membres du
bureau avant le jour J.

---

## 1. Préparer la simulation

### Lancer le serveur

```bash
run.bat
```

Puis ouvrir **http://127.0.0.1:8000/** dans un navigateur.

### Remettre la base à zéro

À faire **avant chaque simulation**, pour repartir d'une base propre :

```bash
venv\Scripts\python.exe manage.py remettre_a_zero
```

Cela efface les réponses et les associations, sans toucher aux comptes :
les 127 étudiants gardent leurs identifiants.

### Récupérer les identifiants des testeurs

Ouvre `identifiants.csv` et note les identifiants de 2–3 personnes du bureau.
Tu en donnes un à chacun :

| Rôle | Identifiant | Mot de passe |
|---|---|---|
| Testeur L1 | `e.achoumou` | *(voir le fichier)* |
| Testeuse L3 | `k.aka` | *(voir le fichier)* |

> 💡 **Astuce simulation** : pour aller plus vite, tu peux définir des mots de
> passe simples sur ces comptes de test seulement — voir l'annexe en bas.

---

## 2. Dérouler les 4 phases

### Phase 1 — Inscription (les étudiants répondent)

**Ce que tu fais :**

1. Vérifie que la phase est bien **Inscription** : admin → *Paramètre de
   l'événement*. Si besoin, remets `phase_actuelle = inscription`.
2. Ouvre http://127.0.0.1:8000/ : la page d'accueil affiche le compte à rebours.

**Ce que font les testeurs :**

3. Chaque testeur ouvre **http://127.0.0.1:8000/** et clique **Se connecter**.
4. Il saisit son **identifiant** et son **mot de passe**.
5. Il arrive sur **Mon espace**, puis clique **Remplir le questionnaire**.
6. Il répond aux 25 questions, **une par écran**. La barre de progression se
   remplit ; les questions à choix avancent automatiquement.
7. Il clique **Valider mes réponses** et confirme.

**À vérifier :**

- [ ] Une seule question s'affiche à la fois, avec sa section
- [ ] Les options se surlignent au clic, et la question suivante arrive seule
- [ ] La barre de progression avance à chaque réponse
- [ ] **Toutes les questions sont obligatoires** : impossible de valider sans
      avoir tout rempli
- [ ] La question 21 ne s'affiche **pas** dans la même version pour un L1 et un L3
- [ ] Impossible d'avancer sur une question obligatoire laissée vide
- [ ] Le raccourci clavier `1`…`6` sélectionne une option
- [ ] Après validation, un message vert confirme l'enregistrement
- [ ] **Le testeur ne peut plus modifier ses réponses** : le questionnaire est
      en lecture seule
- [ ] Dans l'admin → *Réponses aux questionnaires*, tu vois ses 25 réponses

> 📌 **Point clé** : c'est ici que se joue le verrouillage. Demande à un testeur
> d'essayer de recharger `/quiz/` : il doit tomber sur le message de
> confirmation, sans pouvoir rien changer.

---

### Phase 2 — Verrouillage (on ferme les réponses)

**Ce que tu fais :**

1. Admin → *Paramètre de l'événement*
2. Coche la ligne, puis action **« Passer en phase Verrouillage »**
3. Enregistre

**À vérifier :**

- [ ] Sur **Mon espace**, les testeurs voient « Les inscriptions sont closes »
- [ ] Un testeur qui n'a pas répondu ne peut plus répondre

> ⚠️ En phase verrouillée, le matching n'est pas encore visible. C'est normal.

---

### Phase 3 — Teasing (le jour J, les indices)

**Ce que tu fais :**

1. Admin → action **« Passer en phase Teasing »**

**Ce que voient les testeurs :**

2. Sur **Mon espace**, chaque étudiant découvre **un indice** :
   une question sur laquelle il a un point commun avec son binôme.
3. **Les noms sont masqués.**
4. Une personne L3 avec 2 filleuls voit **2 indices numérotés**
   (« Personne 1 sur 2 », « Personne 2 sur 2 »).
5. Le mini-jeu est accessible : **Le dé de la rencontre** (animation, messages).

**À vérifier :**

- [ ] Les indices s'affichent avec une jauge circulaire
- [ ] **Aucun nom** n'apparaît (ni L1, ni L3)
- [ ] Le lien « Le dé » apparaît dans la barre de navigation
- [ ] Le dé s'anime quand on clique

---

### Phase 4 — Révélation (le clou du spectacle)

**Ce que tu fais :**

1. Admin → *Paramètre de l'événement* → action **« FORCER LA RÉVÉLATION »**

**Ce que tu projettes :**

2. Ouvre **http://127.0.0.1:8000/revelation/** sur le vidéoprojecteur.

**La séquence :**

- Un **rideau bleu marine** couvre l'écran avec un compte à rebours **3 → 2 → 1**
- Les **cartes des parrains apparaissent une par une**, avec un éclat doré
- Des **confettis** tombent régulièrement
- Les **compteurs s'incrémentent** (binômes, parrains, filleuls)
- Une **pluie de confettis finale** célèbre l'ensemble

**À vérifier :**

- [ ] Le décompte 3-2-1 s'affiche
- [ ] Les cartes apparaissent progressivement
- [ ] Les confettis tombent
- [ ] Le bouton **« Rejouer l'animation »** relance toute la séquence
- [ ] Le bouton **« Passer l'introduction »** affiche tout immédiatement
      (utile si le public est impatient)
- [ ] **Aucune mention** de priorité, de forçage ou d'administration

> 💡 **Conseil projection** : appuie sur **F11** pour le plein écran.
> Le bouton « Rejouer » te permet de refaire l'effet si l'assistance arrive
> en retard.

---

## 3. Tester une association décidée par l'équipe

Pour vérifier le mécanisme des binômes prioritaires :

1. Admin → **Demandes** → **Ajouter une demande**
2. Choisis un **L3** (liste filtrée) puis un **L1** (liste filtrée)
3. Le statut est **déjà sur « Acceptée »** — laisse-le
4. Enregistre
5. Va sur `/revelation/` : ce binôme affiche **100/100**

**À vérifier :**

- [ ] Le binôme apparaît bien ensemble
- [ ] Il affiche `100/100`
- [ ] **Rien ne le distingue** des autres sur la page publique
- [ ] Dans l'admin, la colonne « Forcé » indique « Oui — 100/100 »

---

## 4. Remettre en production

Quand la simulation est finie :

```bash
venv\Scripts\python.exe manage.py remettre_a_zero
```

Puis dans l'admin :

1. *Paramètre de l'événement* → `phase_actuelle = inscription`
2. Vérifie que `revelation_declenchee_manuellement` est **décoché**
3. Supprime les **Demandes** de test (associations prioritaires)

---

## Annexe — Mots de passe simples pour les comptes de test

Pour gagner du temps pendant la simulation, tu peux définir un mot de passe
simple sur quelques comptes, **uniquement pour les tests** :

```bash
venv\Scripts\python.exe manage.py shell -c "from django.contrib.auth.models import User; [User.objects.filter(username=u).update(password=__import__('django.contrib.auth.hashers', fromlist=['make_password']).make_password('test')) for u in ['e.achoumou','k.aka']]"
```

Ensuite, ces comptes se connectent avec le mot de passe `test`.

> ⚠️ **N'oublie pas de regénérer les vrais identifiants avant la production** :
> `venv\Scripts\python.exe manage.py importer_etudiants --mot-de-passe --export identifiants.csv`

---

## Récapitulatif des commandes

| Commande | Utilité |
|---|---|
| `run.bat` | Démarrer le serveur |
| `manage.py remettre_a_zero` | Base propre pour une simulation |
| `manage.py importer_etudiants --export identifiants.csv` | Regénérer les identifiants |
| `manage.py remplir_questionnaires` | Remplir les quiz automatiquement (démo) |

## Récapitulatif des accès

| Qui | URL | Identifiants |
|---|---|---|
| Étudiants | http://127.0.0.1:8000/ | `identifiants.csv` |
| Équipe (admin) | http://127.0.0.1:8000/admin/ | `admin` / `admin123` |

> 🔐 **Change le mot de passe admin** avant la production :
> admin → *Modifier le mot de passe* (en haut à droite).
