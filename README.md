# Pilotage prédictif des ventes

Plateforme de gestion et de prévision des ventes pour les dépôts de boissons.
Elle transforme les ventes, les stocks et les données calendaires en prévisions
à court terme, recommandations de réapprovisionnement et alertes métier.

Le projet couvre toute la chaîne :

```text
Données PostgreSQL / imports Excel
              ↓
Préparation et contrôle des données
              ↓
Backtesting de plusieurs modèles
              ↓
Sélection automatique du meilleur modèle
              ↓
Prévision future J+1 à J+7
              ↓
Recommandations de stock et alertes
              ↓
Suivi de la qualité prédictive
```

## Fonctionnalités

- Tableau de bord descriptif avec filtres par période.
- Comparaison automatique de plusieurs modèles prédictifs.
- Prévisions futures de 1 à 7 jours avec intervalle de confiance.
- Historique et évaluation des prévisions après leur échéance.
- Recommandations de stock, risques de rupture et priorités de commande.
- Réceptions fournisseurs et mouvements de stock transactionnels.
- Import Excel natif dans Django, guidé pour les ventes, stocks, produits et clients.
- Validation des références, doublons, champs obligatoires et règles métier.
- Génération automatique des codes internes et numéros de mouvements.
- Tableau de bord de qualité ML et détection de dérive.
- Journal d’activité du dépôt pour les propriétaires et administrateurs, avec
  une vue globale réservée au super administrateur de la plateforme.
- E-mails transactionnels Brevo avec templates HTML responsive et fallback texte.

## Technologies

- Python et Django 5.2
- Django REST Framework
- Streamlit, conservé comme laboratoire analytique expert
- PostgreSQL
- SQLAlchemy et Psycopg
- Alembic
- Pandas et NumPy
- Plotly
- scikit-learn
- XGBoost
- OpenPyXL
- SweetAlert2 pour les confirmations et notifications flash
- Select2 pour les listes longues, avec repli sur les champs HTML natifs
- Tailwind CSS 4 compilé pour le design system responsive Django

## Organisation du projet

```text
sales_predictive_analytics/
├── backend/                    # Produit web Django et API
│   ├── accounts/               # Comptes et authentification par e-mail
│   ├── companies/              # Dépôts, appartenances et rôles
│   ├── dashboard/              # Interface métier principale
│   ├── operations/             # Catalogue, stocks et consultation des ventes
│   ├── audit/                  # Piste d’audit fonctionnelle immutable
│   ├── api/                    # API versionnée /api/v1
│   ├── templates/              # Interfaces web responsive
│   └── static/                 # Design system NexaStock
├── .streamlit/                 # Thème et configuration Streamlit
├── alembic/                    # Migrations de la base
│   └── versions/
├── app/
│   ├── main.py                 # Point d'entrée Streamlit
│   ├── config/                 # Configuration par variables d'environnement
│   ├── database/               # Connexion SQLAlchemy
│   ├── imports/                # Définition des formats Excel
│   ├── ml/                     # Dataset, features, modèles et évaluation
│   ├── pages/                  # Pages de l'application
│   ├── repositories/           # Accès aux données PostgreSQL
│   ├── services/               # Règles métier et orchestration
│   └── utils/                  # Composants d'interface partagés
├── database_setup/
│   ├── database/               # Création du schéma et référentiels
│   └── scripts/                # Générateur de données de démonstration
├── docker/
│   └── entrypoint.sh           # Initialisation DB et démarrage du conteneur
├── .dockerignore
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

La plateforme utilise deux interfaces complémentaires :

```text
Django           → produit métier quotidien, comptes, rôles et API
Streamlit        → laboratoire expert pour le ML et le diagnostic
                             ↓
               Services métier et modules ML partagés
                             ↓
                         PostgreSQL
```

Le web Django est la porte d'entrée destinée aux propriétaires et gestionnaires.
Streamlit n'est pas supprimé : il reste disponible séparément pour les analyses
techniques avancées.

Les pages ne portent pas directement les requêtes SQL. Les services valident et
orchestrent les opérations, tandis que les repositories gèrent la persistance.

La conception de l'évolution multi-entreprises est détaillée dans
[`docs/MULTI_TENANT_ARCHITECTURE.md`](docs/MULTI_TENANT_ARCHITECTURE.md).

## Prérequis

- Git.
- Docker Desktop, ou Docker Engine avec le plugin Compose.

Pour une installation sans Docker, il faut aussi Python 3.11 ou une version
ultérieure, PostgreSQL, le client `psql` et Node.js 20 ou supérieur pour modifier
les styles Tailwind.

## Installation avec Docker — recommandée

Docker fournit Python 3.12, PostgreSQL 17, Django, Streamlit et toutes les
dépendances nécessaires.
Il n'est donc pas nécessaire d'installer Python ou PostgreSQL directement sur la
nouvelle machine.

### 1. Récupérer le projet

```bash
git clone <URL_DU_DEPOT>
cd sales_predictive_analytics
```

Remplacez `<URL_DU_DEPOT>` par l'URL Git réelle du projet.

Si le projet est déjà cloné et que `main` vient d'être récupérée, le démarrage
complet tient à ces commandes :

```bash
git pull origin main
cp -n .env.example .env
docker compose up --build
```

`cp -n` crée `.env` uniquement s'il n'existe pas et préserve donc la
configuration locale d'un développeur déjà installé.

### 2. Préparer la configuration

Copiez le fichier d'exemple :

```bash
cp .env.example .env
```

Sous Windows PowerShell :

```powershell
Copy-Item .env.example .env
```

La configuration proposée est :

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sales_predictions
DB_USER=postgres
DB_PASSWORD=postgres
POSTGRES_HOST_PORT=5434
STREAMLIT_PORT=8501
DJANGO_PORT=8001
STREAMLIT_COMPANY_ID=00000000-0000-4000-8000-000000000001
```

Le `DB_HOST=localhost` sert aux commandes exécutées directement sur la machine.
Dans le conteneur, `docker-compose.yml` le remplace automatiquement par :

```text
DB_HOST=db
DB_PORT=5432
```

La communication est donc organisée ainsi :

```text
Produit web Django         → localhost:8001
Laboratoire Streamlit      → localhost:8501
pgAdmin / machine hôte     → localhost:5434
Application dans Docker    → db:5432
PostgreSQL local éventuel  → localhost:5432
```

Dans Docker Desktop, les ressources apparaissent avec des noms cohérents :

```text
Projet       : sales_predictive_analytics
Produit web  : web
Laboratoire  : app
PostgreSQL   : db
Image app    : sales_predictive_analytics_app:latest
```

Le port hôte `5434` évite les conflits avec PostgreSQL local sur `5432` et avec
le PostgreSQL Docker d'`amsoft_compagnie` exposé sur `5433`.

### 3. Démarrer une installation neuve

```bash
docker compose up --build
```

Au premier démarrage, le projet effectue automatiquement les opérations
suivantes :

```text
Création du conteneur PostgreSQL 17
             ↓
Création du schéma et des référentiels métier
             ↓
Application des migrations Django
             ↓
Application des migrations Alembic et activation de l'isolation RLS
             ↓
Démarrage de Django et de Streamlit
```

Ouvrez ensuite :

- [http://localhost:8001](http://localhost:8001) pour le produit web ;
- [http://localhost:8501](http://localhost:8501) pour le laboratoire Streamlit.

Docker démarre également les services internes suivants :

```text
web     → interface métier Django
app     → laboratoire technique Streamlit
worker  → exécution des prévisions Celery
beat    → planification des maintenances périodiques
redis   → file de messages Celery
db      → PostgreSQL 17
```

`worker`, `beat` et `redis` ne sont pas exposés publiquement. Une prévision
lancée depuis Django est placée dans Redis, calculée par `worker`, puis son
statut et son résultat sont enregistrés dans `forecast_jobs`.

Au premier accès web, créez votre compte puis votre dépôt. Le premier membre est
automatiquement enregistré comme **Propriétaire** du dépôt.

Les données présentes avant l'activation multi-dépôts sont rattachées au
**Dépôt historique**. Après avoir créé votre compte Django, attribuez-vous ce
dépôt avec une commande explicitement administrative :

```bash
docker compose exec web \
  python backend/manage.py claim_legacy_company votre@email.com
```

Reconnectez-vous puis choisissez **Dépôt historique** dans le sélecteur. La
commande refuse par défaut d'ajouter un second propriétaire actif.

Il est préférable d'accorder cet accès plutôt que de remplacer les
`company_id` des ventes historiques : le dépôt de démonstration reste ainsi
séparé du dépôt réel. Un même propriétaire peut naviguer entre les deux depuis
le sélecteur de dépôt.

L'initialisation du schéma est idempotente : lors des démarrages suivants, le
conteneur détecte la base existante et applique seulement les migrations Django
et Alembic qui manquent.

### 4. Charger les données synthétiques — facultatif

La génération des données de démonstration n'est jamais automatique. Sur une
base Docker neuve uniquement, exécutez :

```bash
docker compose exec app \
  python database_setup/scripts/generate_sample_data.py
```

Cette commande crée environ deux années de ventes, stocks, clients, réceptions,
météo et anomalies dans le seul dépôt désigné par `STREAMLIT_COMPANY_ID`. Elle
n'utilise jamais `TRUNCATE`, afin de préserver les autres dépôts. Ne l'exécutez
jamais dans le dépôt contenant vos données métier réelles.

Par défaut, `STREAMLIT_COMPANY_ID=00000000-0000-4000-8000-000000000001` cible
le **Dépôt historique**. Les données synthétiques ne sont donc pas rattachées
automatiquement au dernier dépôt créé dans Django.

Pour préparer localement **DEPOT BERTHE KLB** à partir de ce jeu historique et
prolonger ses ventes jusqu'à la date courante, utilisez plutôt la commande
idempotente suivante :

```bash
docker compose exec web \
  python backend/manage.py seed_recent_berthe_sales --confirm
```

Si le dépôt Berthe KLB ne possède encore aucune vente, la commande copie le
socle analytique du **Dépôt historique** sans déplacer ni modifier la source :
catégories, produits, clients, fournisseurs, ventes, lignes de vente et stocks
journaliers. Elle ajoute ensuite les jours manquants avec des références
déterministes. Une seconde exécution ignore les ventes déjà créées.

Pour figer la date de fin lors d'une démonstration :

```bash
docker compose exec web \
  python backend/manage.py seed_recent_berthe_sales \
  --end-date 2026-08-06 --confirm
```

La commande est bloquée par défaut lorsque `DJANGO_DEBUG=false`. Elle est
destinée à la préparation d'une base locale avant sauvegarde, pas à
l'alimentation automatique d'une base de production.

Pour produire un classeur Excel réimportable depuis ces ventes récentes :

```bash
docker compose exec web python database_setup/scripts/export_recent_sales_excel.py \
  --company-id <UUID_DU_DEPOT> \
  --output outputs/ventes_recentes_berthe_klb.xlsx
```

Le dossier `outputs/` reste local et n'est pas versionné. Le classeur généré
reprend le modèle officiel d'import NexaStock avec ses listes de choix.

### 5. Commandes Docker courantes

Démarrer en arrière-plan :

```bash
docker compose up -d --build
```

Voir les journaux :

```bash
docker compose logs -f app
docker compose logs -f web
docker compose logs -f db
docker compose logs -f worker
docker compose logs -f beat
docker compose logs -f redis
```

Vérifier l'état des services :

```bash
docker compose ps
```

Vérifier la migration active :

```bash
docker compose exec app python -m alembic current
docker compose exec web python backend/manage.py showmigrations
```

Arrêter les conteneurs sans supprimer les données :

```bash
docker compose down
```

Reconstruire l'application après une modification des dépendances ou du code :

```bash
docker compose up -d --build web app worker beat
```

### 6. Développement Docker avec rechargement automatique

Le fichier `docker-compose.yml` reste volontairement proche de la production :
le code est intégré à l'image et doit être reconstruit après une modification.

Pour travailler quotidiennement sans reconstruire les conteneurs, utilisez la
surcharge de développement :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Le premier lancement construit l'image Python et installe les dépendances Node.
Ensuite, les dossiers du projet sont montés directement dans les conteneurs :

```text
Modification Python ou template Django  → rechargement automatique de Django
Modification Streamlit                  → rechargement automatique de Streamlit
Modification des classes Tailwind       → recompilation automatique du CSS
Modification JavaScript ou CSS existant → visible après actualisation du navigateur
```

Il n'est donc plus nécessaire de relancer `docker compose up --build` après
chaque modification d'interface.

Voir les journaux utiles pendant le développement :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f web app tailwind
```

Arrêter le mode développement sans supprimer PostgreSQL ni Redis :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Les processus Celery ne se rechargent pas automatiquement. Après une
modification d'une tâche ou de sa planification, redémarrez uniquement :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker beat
```

Une reconstruction reste nécessaire seulement après une modification de
`Dockerfile`, `requirements.txt`, `package.json` ou `package-lock.json` :

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Cette surcharge est strictement locale. Railway continue d'utiliser le
`Dockerfile` et ne lance ni le serveur Django de développement ni le watcher
Tailwind.

Vérifier que Celery répond :

```bash
docker compose exec worker celery -A config inspect ping
```

La page Django **Prévisions** permet à un propriétaire, un administrateur ou
un analyste de demander un calcul J+1 à J+7. La page peut être actualisée sans
relancer le job : chaque demande passe successivement par les statuts
`En attente`, `En cours`, `Terminée` ou `Échec`.

Une prévision terminée propose le bouton **Voir le résultat**. La page de détail
présente la demande attendue, le scénario prudent P90, le chiffre d'affaires
prévisionnel, le stock supplémentaire estimé et les valeurs de chaque journée.

Les maintenances périodiques sont volontairement désactivées sur une nouvelle
installation. Après validation des calculs manuels, activez-les avec :

```dotenv
CELERY_AUTOMATION_ENABLED=true
```

Puis redémarrez `worker` et `beat`. La tâche quotidienne évalue les prévisions
arrivées à échéance et actualise les indicateurs de qualité ML pour chaque
dépôt actif. Elle ne réinitialise jamais le schéma et ne génère pas les données
de démonstration.

> **Attention :** `docker compose down -v` supprime le volume PostgreSQL et
> toutes les données qu'il contient. N'utilisez cette commande que pour
> réinitialiser volontairement une base de développement sauvegardée.

## Migrer la base PostgreSQL locale vers Docker

Le conteneur utilise PostgreSQL 17 pour rester compatible avec la base locale
actuelle. La méthode recommandée consiste à démarrer uniquement la base Docker,
à restaurer le backup, puis à démarrer l'application.

### Méthode avec pgAdmin

1. Créez un backup de la base locale `sales_predictions` avec pgAdmin.
2. Démarrez uniquement PostgreSQL Docker :

   ```bash
   docker compose up -d db
   ```

3. Ajoutez un serveur pgAdmin avec les paramètres suivants :

   ```text
   Hôte : localhost
   Port : 5434
   Base : sales_predictions
   Utilisateur : postgres
   Mot de passe : valeur DB_PASSWORD du fichier .env
   ```

4. Restaurez le backup dans `sales_predictions`.
5. Démarrez ensuite l'application :

   ```bash
   docker compose up -d --build web app
   ```

6. Contrôlez les migrations :

   ```bash
   docker compose exec web python -m alembic current
   docker compose exec web python backend/manage.py showmigrations
   ```

Le démarrage du service `db` seul ne crée pas les tables métier. Cela laisse une
base propre pour la restauration. Au démarrage de `web`, le script détecte le
schéma restauré, ne rejoue pas les scripts initiaux et lance les migrations
Django puis Alembic nécessaires.

### Méthode en ligne de commande

Créer un backup au format personnalisé depuis PostgreSQL local sur `5432` :

```bash
pg_dump \
  --host=localhost \
  --port=5432 \
  --username=postgres \
  --format=custom \
  --file=sales_predictions.backup \
  sales_predictions
```

Démarrer la base Docker, puis restaurer sur `5434` :

```bash
docker compose up -d db

pg_restore \
  --host=localhost \
  --port=5434 \
  --username=postgres \
  --dbname=sales_predictions \
  --clean \
  --if-exists \
  --no-owner \
  sales_predictions.backup
```

Enfin, démarrez l'application :

```bash
docker compose up -d --build web app
docker compose exec web python -m alembic current
```

Créez ensuite votre compte Django et utilisez `claim_legacy_company` comme
indiqué plus haut pour accéder aux données restaurées.

Les fichiers `*.backup` et `*.dump` sont exclus de l'image Docker. Conservez-les
dans un emplacement sécurisé et ne les ajoutez jamais au dépôt Git.

## Déploiement sur Railway

Railway détecte automatiquement le `Dockerfile` situé à la racine. Le service
PostgreSQL du fichier Compose reste réservé au développement local. En
production, créez idéalement deux services depuis le même dépôt Git :

```text
web         → application Django destinée aux clients
app         → laboratoire Streamlit, accès technique séparé
Postgres    → base managée commune
Redis       → file de messages managée ou service Redis privé
worker      → traitements Celery depuis la même image Docker
beat        → planificateur Celery depuis la même image Docker
```

Sur le plan Railway **Hobby**, limité à cinq services, l'architecture déployée
regroupe provisoirement Worker et Beat dans un même service :

```text
Postgres + Django + Streamlit + Redis + celery-worker
                                      └── Beat intégré
```

Commande de démarrage correspondante :

```bash
celery --workdir=backend -A config worker --beat --loglevel=INFO \
  --concurrency=2 --schedule=/tmp/celerybeat-schedule
```

Cette configuration convient à une charge modérée. Sur un plan autorisant plus
de services, séparez de nouveau `worker` et `beat` afin de pouvoir les superviser
et les redimensionner indépendamment.

### Variables et démarrage du service Django

Configurez au minimum :

```dotenv
DATABASE_URL=${{Postgres.DATABASE_URL}}
INITIALIZE_DATABASE=false
RUN_ALEMBIC=false
DJANGO_SECRET_KEY=<clé-longue-et-aléatoire>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<domaine-du-service>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<domaine-du-service>
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=31536000
AUDIT_TRUST_X_FORWARDED_FOR=true
STREAMLIT_PUBLIC_URL=https://<domaine-du-laboratoire>
STREAMLIT_SIGNING_KEY=<secret-partage-long-et-aleatoire>
STREAMLIT_ACCESS_TOKEN_TTL_SECONDS=300
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=<identifiant-smtp-brevo>
EMAIL_HOST_PASSWORD=<clé-smtp-brevo>
EMAIL_TIMEOUT=15
BREVO_API_KEY=<clé-api-brevo>
BREVO_API_URL=https://api.brevo.com/v3/smtp/email
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=NexaStock <adresse-verifiee@votre-domaine.com>
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
CELERY_AUTOMATION_ENABLED=false
FORECAST_MAX_DATA_AGE_DAYS=3
FORECAST_CHAMPION_MIN_IMPROVEMENT=5
```

Sur Railway, créez `worker` et `beat` depuis le même dépôt et la même image que
Django. Ils partagent `DATABASE_URL`, `CELERY_BROKER_URL` et
`CELERY_RESULT_BACKEND`, mais n'exécutent ni migrations ni initialisation SQL.
Ajoutez donc explicitement `INITIALIZE_DATABASE=false` et `RUN_ALEMBIC=false`
aux variables de ces deux services.

Commande de démarrage du worker :

```bash
celery --workdir=backend -A config worker --loglevel=INFO --concurrency=2
```

Commande de démarrage du planificateur :

```bash
celery --workdir=backend -A config beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule
```

Déployez dans l'ordre `Postgres/Redis`, `web`, puis le service Celery combiné
sur Hobby — ou `worker` et `beat` séparément sur un plan supérieur. N'activez
`CELERY_AUTOMATION_ENABLED=true` qu'après avoir validé une prévision manuelle
en production.

Sur Railway Free, Trial ou Hobby, utilisez `BREVO_API_KEY` : l'envoi passe par
l'API transactionnelle HTTPS, car les connexions SMTP sortantes y sont
bloquées. Le transport SMTP reste disponible comme fallback local ou sur une
offre Railway compatible. Vérifiez l'adresse expéditrice dans Brevo et
authentifiez idéalement son domaine avec DKIM et DMARC.
Les invitations utilisent `backend/templates/emails/company_invitation.html`
avec un fallback texte. Django crée l'invitation immédiatement, puis Celery
effectue l'envoi SMTP avec plusieurs tentatives. La page **Équipe** affiche
`En attente d'envoi`, `Envoi en cours`, `E-mail envoyé` ou `Échec de l'envoi`.
Le libellé métier « E-mail envoyé » signifie techniquement que Brevo a accepté
le message ; la livraison finale dans la boîte du destinataire reste
consultable dans les journaux transactionnels Brevo.

L'action **Renvoyer le lien** invalide l'ancien jeton, prolonge la validité de
trois jours et remet un nouvel e-mail en file. Le worker et le service Django
doivent donc partager les variables SMTP ci-dessus en plus de `DATABASE_URL`
et `CELERY_BROKER_URL`.

### Fraîcheur et sécurité des prévisions

Une prévision n'est acceptée que si la dernière vente du produit est assez
récente. Le seuil est configurable et vaut trois jours par défaut :

```dotenv
FORECAST_MAX_DATA_AGE_DAYS=3
```

Si l'historique est plus ancien, Django affiche la date de dernière vente et
demande d'importer ou de saisir les données manquantes. Une contrainte en base
interdit également plusieurs jobs `QUEUED`/`RUNNING` pour le même produit et le
même dépôt. Les jobs en échec peuvent être relancés depuis la page
**Prévisions** ; les statuts actifs s'actualisent automatiquement toutes les
huit secondes.

### Modèle champion par produit

Django conserve une méthode de prévision de référence pour chaque produit. À
chaque calcul, tous les modèles éligibles sont comparés sur la période de test,
mais le champion actuel n'est remplacé que si le challenger réduit la MAE d'au
moins 5 %. Ce seuil évite les changements de modèle dus à des écarts trop
faibles et peut être configuré ainsi :

```dotenv
FORECAST_CHAMPION_MIN_IMPROVEMENT=5
```

La page métier **Prévisions** présente la décision en langage courant. Les
métriques MAE, RMSE et WAPE restent accessibles dans le volet repliable
**Détails techniques**. Le laboratoire Streamlit conserve les analyses ML plus
détaillées destinées aux profils techniques.

### Modèles de demande et quantiles

Le backtesting classe la série du produit avant d'ajouter ses challengers :

- **Holt-Winters (ETS)** pour les séries journalières régulières avec saisonnalité hebdomadaire ;
- **Croston TSB** lorsque 40 % ou plus des jours ont une demande nulle ;
- **XGBoost quantile** pour apprendre directement P50, P80 et P90 lorsqu'XGBoost est champion.

Pour les autres champions, P50/P80/P90 sont estimés à partir de la dispersion
des résidus du backtesting. Ces trois niveaux sont persistés dans
`forecast_results`. P50 représente les **ventes les plus probables**, tandis que P80 et P90
servent à dimensionner progressivement le risque de stock. Le classement expose
également WAPE et le biais, en complément de MAE, RMSE et MAPE.

Pour Mailtrap Sandbox : ouvrez **Email Testing → Sandboxes → votre inbox →
Integration → SMTP**, puis copiez les variables proposées. Les messages restent
dans Mailtrap et ne sont pas remis aux destinataires réels.

Pour l'envoi réel : ouvrez **Email Sending → Sending Domains**, ajoutez votre
domaine, publiez les enregistrements DNS demandés et attendez sa validation.
Dans **Integrations → Transactional Stream → SMTP**, récupérez ensuite le host,
le port, le username et le mot de passe SMTP. `MAIL_FROM_ADDRESS` doit utiliser
le domaine vérifié. Ne placez jamais ces secrets dans Git.

Utilisez cette **Start Command** pour Django :

```bash
sh -c 'python backend/manage.py migrate --noinput && python -m alembic upgrade head && python backend/manage.py collectstatic --noinput --ignore="src/*" && gunicorn --chdir backend config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120'
```

Son chemin de contrôle de santé est `/health/`.

### Variables du service Streamlit

Dans l'onglet **Variables** du service applicatif, configurez :

```dotenv
DATABASE_URL=${{Postgres.DATABASE_URL}}
INITIALIZE_DATABASE=false
RUN_ALEMBIC=false
STREAMLIT_USE_RUNTIME_ROLE=false
STREAMLIT_SIGNING_KEY=<meme-secret-que-le-service-django>
STREAMLIT_REQUIRE_SIGNED_ACCESS=true
```

Adaptez `Postgres` si le service PostgreSQL porte un autre nom dans Railway.
`DATABASE_URL` est prioritaire sur les variables `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER` et `DB_PASSWORD`.

Le secret de signature doit être identique sur Django et Streamlit. Django crée
un lien valable cinq minutes contenant le dépôt actif ; Streamlit refuse tout
accès direct ou tout jeton altéré avant d'ouvrir une session PostgreSQL.

Railway injecte automatiquement `PORT`. Configurez cette Start Command :

```bash
python -m streamlit run app/main.py \
  --server.address=0.0.0.0 \
  --server.port=${PORT:-8501}
```

```bash
sh -c 'python -m streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true'
```

Le démarrage Railway suit uniquement ce cycle :

```text
Validation du lien signé Django
              ↓
Sélection du dépôt autorisé
              ↓
Connexion au PostgreSQL Railway
              ↓
Streamlit sur le port Railway
```

Il ne lance jamais automatiquement :

- `02_schema.sql` ;
- `03_reference_data.sql` ;
- `04_indexes.sql` ;
- `generate_sample_data.py`.

L'initialisation SQL n'est exécutée que lorsque
`INITIALIZE_DATABASE=true`, valeur utilisée par Docker Compose local pour une
base neuve. Sur Railway, conservez toujours cette variable à `false` après la
restauration du backup.

### Restaurer la base avant le premier déploiement

1. Créez le service PostgreSQL dans Railway.
2. Utilisez les paramètres du **TCP Proxy** Railway pour restaurer le backup
   avec pgAdmin ou `pg_restore`.
3. Vérifiez que le schéma et la table `alembic_version` sont présents.
4. Configurez `DATABASE_URL=${{Postgres.DATABASE_URL}}` sur le service web.
5. Déployez ou redéployez d'abord Django, puis Streamlit.
6. Créez votre compte et exécutez `claim_legacy_company` depuis le service web
   pour réclamer les données restaurées.

Une base Railway totalement vide ne peut pas recevoir directement les migrations
Alembic actuelles, car celles-ci prolongent le schéma initial. Il faut donc soit
restaurer le backup, soit effectuer une initialisation contrôlée avant le premier
démarrage.

### Santé du service

Dans les paramètres Railway, utilisez le chemin de healthcheck Streamlit :

```text
/_stcore/health
```

Le conteneur écoute sur `0.0.0.0` et sur la valeur de `PORT` fournie par
Railway.

## Installation sans Docker

Cette méthode reste disponible pour les contributeurs qui souhaitent exécuter
Python et PostgreSQL directement sur leur machine.

### 1. Créer l'environnement Python

Sous macOS ou Linux :

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Sous Windows PowerShell :

```powershell
py -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configurer PostgreSQL

Copiez le fichier d'exemple :

```bash
cp .env.example .env
```

Sous Windows :

```powershell
Copy-Item .env.example .env
```

Adaptez ensuite `.env` :

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sales_predictions
DB_USER=postgres
DB_PASSWORD=postgres
```

Le fichier `.env` contient des informations locales et ne doit pas être ajouté
à Git.

### 3. Créer la base et le schéma initial

Les commandes suivantes supposent un utilisateur PostgreSQL nommé `postgres`.
Modifiez `-U postgres` si votre utilisateur est différent.

```bash
psql -U postgres -d postgres \
  -f database_setup/database/01_create_database.sql

psql -U postgres -d sales_predictions \
  -f database_setup/database/02_schema.sql

psql -U postgres -d sales_predictions \
  -f database_setup/database/03_reference_data.sql

psql -U postgres -d sales_predictions \
  -f database_setup/database/04_indexes.sql
```

Ces scripts créent notamment :

- le schéma métier ;
- les catégories et types de clients ;
- 30 produits et plusieurs fournisseurs de démonstration ;
- les index utiles aux analyses.

### 4. Appliquer les migrations

```bash
python backend/manage.py migrate
python -m alembic upgrade head
```

Vérifiez la version appliquée :

```bash
python -m alembic current
python backend/manage.py showmigrations
```

La base doit se trouver sur la révision la plus récente affichée comme `head`.

### 5. Ajouter des données de démonstration — facultatif

Sur une base neuve, le générateur crée environ deux années de ventes, clients,
stocks, réceptions, météo et anomalies cohérentes :

```bash
python database_setup/scripts/generate_sample_data.py
```

Cette étape sert à découvrir immédiatement les dashboards et le moteur ML. Ne
relancez pas ce générateur sur une base contenant des données métier réelles.

### 6. Lancer les interfaces

Lancez d'abord le produit web Django :

```bash
python backend/manage.py runserver 0.0.0.0:8001
```

Ouvrez [http://localhost:8001](http://localhost:8001), créez un compte et
configurez votre premier dépôt.

Dans un second terminal, lancez le laboratoire analytique :

```bash
python -m streamlit run app/main.py
```

Ouvrez ensuite :

```text
http://localhost:8501
```

## Comptes, dépôts et rôles

L'authentification Django accepte l'adresse e-mail ou le numéro de téléphone.
Un membre invité par téléphone n'a donc pas besoin d'une fausse adresse e-mail.
Un utilisateur peut appartenir à plusieurs dépôts, mais chaque requête est
rattachée à un dépôt actif contrôlé côté serveur. Les rôles disponibles sont :

- **Propriétaire** : contrôle complet du dépôt ;
- **Administrateur** : gestion opérationnelle du dépôt, des ventes et du stock ;
- **Analyste** : analyses et prévisions ;
- **Consultation** : lecture seule.

Le propriétaire n'est pas un simple administrateur supplémentaire. Il constitue
le responsable ultime du dépôt : lui seul pourra transférer la propriété,
archiver définitivement l'espace et gérer ultérieurement l'abonnement. Un dépôt
doit toujours conserver un propriétaire actif. Les administrateurs assurent la
gestion quotidienne, mais ne peuvent ni retirer le dernier propriétaire ni
s'approprier le dépôt. Cette séparation évite qu'une erreur de gestion des accès
rende l'entreprise orpheline.

Le **super administrateur Django** est un rôle plateforme distinct : il peut
sélectionner tous les dépôts actifs pour l’assistance et l’administration. Il ne
remplace pas le propriétaire métier d’un dépôt. La matrice fonctionnelle est
donc volontairement limitée à `OWNER`, `ADMIN`, `ANALYST` et `VIEWER` ; l’ancien
rôle `MANAGER` est automatiquement converti en `ADMIN` par migration.

L'API initiale est exposée sous `/api/v1/` :

- `GET /api/v1/me/` : utilisateur connecté ;
- `GET /api/v1/companies/` : dépôts accessibles ;
- `GET /api/v1/context/` : utilisateur, dépôt actif et rôle.
- `GET /api/v1/dashboard/summary/` : KPI du seul dépôt actif.
- `GET /api/v1/products/` : catalogue du dépôt actif ; filtres `q` et `status`.
- `GET /api/v1/stocks/` : dernière situation de stock ; filtres `q` et `status`.
- `GET /api/v1/sales/` : ventes récentes et KPI du dépôt actif.

Cette première API utilise la session Django. Une authentification par jeton sera
ajoutée lorsque le client mobile sera développé.

## Espace opérationnel Django

Après connexion et sélection du dépôt, Django expose les écrans métier suivants :

| Adresse | Utilité | Accès |
|---|---|---|
| `/` | Vue d'ensemble du dépôt | Tous les membres actifs |
| `/produits/` | Catalogue, prix, conditionnements et seuils | Lecture pour tous |
| `/produits/nouveau/` | Création d'un produit | Propriétaire, administrateur |
| `/clients/` | Clients, activité commerciale et archivage | Tous les membres actifs |
| `/clients/nouveau/` | Création d'un client | Propriétaire, administrateur |
| `/fournisseurs/` | Fournisseurs et historique d'approvisionnement | Tous les membres actifs |
| `/fournisseurs/nouveau/` | Création d'un fournisseur | Propriétaire, administrateur |
| `/depots/gestion/` | Modification, archivage et restauration des dépôts | Lecture des dépôts accessibles ; actions réservées au propriétaire |
| `/depots/equipe/` | Membres, rôles et invitations par téléphone ou e-mail | Propriétaire, administrateur |
| `/stocks/` | Stocks, réceptions récentes et journal des mouvements | Tous les membres actifs |
| `/stocks/reception/nouvelle/` | Saisie d'une réception fournisseur | Propriétaire, administrateur |
| `/stocks/mouvement/nouveau/` | Saisie d'un mouvement manuel | Propriétaire, administrateur |
| `/ventes/` | Transactions et KPI par période | Tous les membres actifs |
| `/ventes/nouvelle/` | Saisie d'une vente et sortie du stock | Propriétaire, administrateur |
| `/ventes/<id>/` | Détail d'une vente et de ses lignes | Tous les membres actifs |
| `/compte/profil/` | Informations personnelles du compte | Utilisateur connecté |

Le code d'un produit n'est jamais saisi dans le formulaire : PostgreSQL le
génère automatiquement. La catégorie est choisie dans une liste limitée au
dépôt actif. Tous les accès par identifiant combinent systématiquement l'UUID de
la ressource avec le `company_id` issu de la session ; connaître l'identifiant
d'une ressource d'un autre dépôt ne donne donc aucun accès.

Les clients, fournisseurs, ventes, réceptions et mouvements manuels sont
désormais gérés dans Django. Les codes `CLI-*` et `FRS-*` sont générés par
PostgreSQL et ne figurent pas dans les formulaires. Le téléphone d'un client est
unique dans un dépôt lorsqu'il est renseigné ; le nom normalisé d'un fournisseur
actif est également unique dans son dépôt.

La gestion d'équipe permet d'inviter un collaborateur par téléphone ou par
e-mail avec un rôle `ADMIN`, `ANALYST` ou `VIEWER`. Pour un téléphone, NexaStock
affiche un lien à copier et à partager par SMS ou WhatsApp ; pour un e-mail,
l'envoi est confié à Celery. Le lien expire après 3 jours et seul son hash est
conservé en base. Une invitation n'accorde aucun accès avant son acceptation.
Le collaborateur choisit son mot de passe puis se connecte avec le même numéro
ou la même adresse.
Seul le propriétaire peut promouvoir ou gérer un administrateur ; un
administrateur peut gérer les analystes et les comptes en consultation. Le
propriétaire et l'utilisateur courant sont protégés contre une suspension
accidentelle depuis leur propre session.

La nouvelle vente commence avec une seule ligne. Le bouton **Ajouter un
produit** crée uniquement les lignes supplémentaires nécessaires, jusqu'à 20
produits. Les ventes, réceptions et mouvements manuels sont désormais saisis
dans Django.
Chaque écriture métier et sa variation de stock sont enregistrées dans une même
transaction PostgreSQL. Une vente ou une réception validée n'est pas réécrite :
ses informations administratives peuvent être modifiées, tandis qu'une
annulation crée des mouvements compensatoires puis renseigne `deleted_at` et
`deleted_by_user_id`. Le journal des mouvements reste append-only ; une erreur
se corrige avec un nouveau mouvement inverse et motivé.

Les tables opérationnelles disposent de `created_at`, `updated_at`,
`created_by_user_id` et `updated_by_user_id`. Les produits, clients,
fournisseurs, ventes et réceptions possèdent aussi `deleted_at` et
`deleted_by_user_id` pour la suppression logique. Les boutons compacts de vue,
modification et annulation conservent un libellé accessible (`aria-label`) et
une infobulle native.

Les listes de ventes, produits, clients, fournisseurs, stocks, réceptions,
mouvements et événements d’audit sont paginées. Les en-têtes autorisés peuvent
être sélectionnés pour alterner un tri ascendant ou descendant ; la recherche,
la période et les autres filtres sont conservés pendant la navigation. Les
statuts techniques sont présentés avec un libellé métier français, par exemple
`PAID` sous la forme **Payée**.

Les règles complètes sont décrites dans
[`docs/OPERATIONAL_ENTRIES.md`](docs/OPERATIONAL_ENTRIES.md).

Les composants communs se trouvent dans `backend/templates/components/`. Les
pages doivent réutiliser en priorité `button.html`, `page_header.html`,
`form_field.html` et `empty_state.html`. Les conventions et limites de ce petit
design system sont décrites dans
[`docs/UI_CONVENTIONS.md`](docs/UI_CONVENTIONS.md).

La politique et les événements du journal d’audit sont documentés dans
[`docs/AUDIT_LOGS.md`](docs/AUDIT_LOGS.md).

### Approvisionnement prédictif Django

Le menu **Approvisionnement** constitue un parcours unique en trois étapes. Il
évite de disperser les recommandations, les commandes et les entrées de stock
dans plusieurs menus :

```text
1. Recommandations  → ce que NexaStock conseille
2. Commandes        → ce qui est préparé puis envoyé au fournisseur
3. Réceptions       → ce qui a réellement été livré et ajouté au stock
```

L'étape **Recommandations** transforme les dernières prévisions persistées en
décisions métier par dépôt. Pour chaque produit, elle présente le stock actuel,
les ventes probables, la marge de prudence, le risque de rupture et la quantité
conseillée. Le détail technique reste replié pour ne pas surcharger
l'utilisateur :

```text
quantité à préparer = demande prudente P90
                    + stock minimum de sécurité
                    - stock disponible
```

Le propriétaire ou un administrateur peut enregistrer un plan avec un
fournisseur et une quantité ajustable. Les plans d'un même fournisseur peuvent
ensuite être regroupés dans une commande. Une commande suit les statuts
**Brouillon**, **Envoyée**, **Partiellement reçue**, **Réceptionnée** ou
**Annulée**.

Une recommandation n'est jamais obligatoire. Dans l'onglet **Commandes**, le
bouton **Nouvelle commande** permet de choisir librement un fournisseur et
n'importe quel produit actif. Les commandes recommandées et les commandes
libres utilisent ensuite le même suivi et le même parcours de réception.

Une recommandation ou une commande n'augmente jamais le stock. Seule la
validation d'une **réception** crée la réception fournisseur, les mouvements
d'entrée et le nouveau stock journalier. Une livraison partielle conserve le
reliquat dans la commande. Une livraison reçue sans commande préalable peut
aussi être saisie depuis l'onglet Réceptions.

Toutes ces actions sont isolées par dépôt et les créations, envois,
annulations et réceptions sont enregistrés dans le journal d'audit. La
description technique complète est disponible dans
[`docs/PROCUREMENT_WORKFLOW.md`](docs/PROCUREMENT_WORKFLOW.md).

L'archivage d'un dépôt est logique : ses ventes, stocks, prévisions et journaux
sont conservés. Le dépôt reste visible dans **Mes dépôts** pour son propriétaire
et peut y être restauré.

Après une modification des classes Tailwind, reconstruisez le CSS :

```bash
npm install
npm run css:build
```

`backend/static/css/tailwind.css` est un artefact généré et n'est pas versionné.
Il ne doit donc pas être ajouté manuellement à Git. En développement Docker,
le service `tailwind` le régénère dès le démarrage et le maintient à jour. Il
reconstruit également le fichier s'il disparaît pendant un changement de
branche, un rebase ou un nettoyage du répertoire de travail.

En Docker, cette compilation est réalisée automatiquement dans une étape Node
séparée du `Dockerfile`; Node.js n’est pas conservé dans l’image Python finale.

## Parcours conseillé dans l'application

### Avec les données de démonstration

1. Ouvrir **Tableau de bord** pour vérifier les ventes disponibles.
2. Ouvrir **Comparaison des modèles** et lancer un backtesting sur un produit.
3. Générer une prévision dans **Prévision future**.
4. Consulter les commandes suggérées dans **Pilotage métier**.
5. Vérifier le cycle de vie des prévisions dans **Qualité ML**.

### Avec des données réelles

1. Dans l'application Django, ouvrir **Gestion → Import Excel**.
2. Choisir le type de données.
3. Télécharger le modèle Excel guidé.
4. Compléter uniquement les champs demandés.
5. Charger le fichier et cliquer sur **Vérifier le fichier**.
6. Contrôler les lignes valides, les erreurs et les doublons avant de confirmer.
7. Corriger les lignes invalides ou choisir d'importer seulement les lignes valides.
8. Consulter l'historique du lot d'import.

Ce parcours est entièrement intégré à Django : les boutons **Importer Excel**
des pages Ventes, Stocks, Produits et Clients n'ouvrent pas Streamlit. Seuls le
propriétaire et l'administrateur peuvent importer. Le fichier vérifié est gardé
temporairement pendant 30 minutes, isolé par dépôt et par utilisateur, puis
supprimé après confirmation, annulation ou expiration.

L'ordre conseillé pour une première alimentation est :

```text
Produits → Clients → Stocks → Ventes
```

Les codes produit, client et vente sont générés par PostgreSQL. Ils ne doivent
pas être inventés manuellement lors de la création des référentiels. Les ventes
importées utilisent toutefois le `product_code` et, si nécessaire, le
`customer_code` déjà présents dans la base.

## Gestion du stock

La page **Stocks et réceptions** permet :

- d'enregistrer une réception fournisseur contenant plusieurs produits ;
- de saisir une casse, une perte, un retour ou un ajustement ;
- de consulter le stock actuel et le journal des mouvements.

Les écritures sont transactionnelles : une opération incomplète est annulée en
totalité. Une sortie supérieure au stock disponible est refusée. Une opération
antérieure au dernier état de stock du produit est également bloquée afin de ne
pas rendre l'historique incohérent.

Les ventes importées créent leur mouvement et diminuent le stock journalier dans
la même transaction.

## Fonctionnement du moteur prédictif

### Modèles comparés

- Vente observée 7 jours auparavant.
- Moyenne mobile sur 7 jours.
- Régression linéaire.
- Random Forest.
- XGBoost.

### Variables utilisées

- Retards J-1, J-7, J-14, J-21 et J-28.
- Moyennes mobiles de 7, 14 et 28 jours.
- Jour de la semaine, mois, semaine de l'année et week-end.
- Température moyenne et pluie.
- Périodes Ramadan et Tabaski.
- Stock disponible et indicateur de rupture.

Le découpage entraînement/test est chronologique. Les jours de rupture sont
traités avec précaution, car une vente nulle en l'absence de stock ne signifie
pas nécessairement une demande nulle.

### Métriques

- **MAE** : erreur absolue moyenne en colis.
- **RMSE** : erreur donnant plus de poids aux écarts importants.
- **MAPE** : erreur moyenne exprimée en pourcentage.

Le meilleur modèle est sélectionné à partir des résultats de backtesting, puis
réentraîné sur l'historique exploitable. La prévision multi-jours est produite de
manière itérative afin de recalculer les retards à chaque nouvelle journée.

## Contrôles utiles pour le développement

Vérifier rapidement la syntaxe et la cohérence des migrations :

```bash
python -m compileall -q app alembic backend
DJANGO_USE_SQLITE=true DJANGO_DEBUG=true \
  python backend/manage.py makemigrations --check --dry-run
```

Pour valider exactement l'image utilisée en production, privilégiez Docker :

```bash
docker compose build web
docker compose up -d db
docker compose run --rm --no-deps -e INITIALIZE_DATABASE=false \
  web python backend/manage.py check
docker compose run --rm --no-deps -e INITIALIZE_DATABASE=false \
  web python backend/manage.py makemigrations --check --dry-run
docker compose run --rm --no-deps -e INITIALIZE_DATABASE=false \
  web python backend/manage.py test \
  accounts audit forecasting companies.tests.TeamManagementTests \
  operations.tests.DataImportWorkflowTests decisions \
  dashboard.tests.PercentageChangeTests
```

Ces tests sont autonomes. Les vues qui interrogent directement les tables
métier historiques (`sales`, `products`, etc.) se vérifient ensuite avec le
schéma PostgreSQL/Alembic réellement initialisé :

```bash
docker compose up -d web
docker compose exec web python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/').read().decode())"
```

Afficher l'état des migrations :

```bash
python -m alembic current
python backend/manage.py showmigrations
```

Mettre la base à niveau après avoir récupéré de nouvelles modifications :

```bash
git pull
pip install -r requirements.txt
python -m alembic upgrade head
python backend/manage.py migrate
```

Puis redémarrez Streamlit.

Avec Docker, utilisez plutôt :

```bash
git pull
docker compose up -d --build
```

## Problèmes fréquents

### Connexion PostgreSQL impossible

Vérifiez que :

- PostgreSQL est démarré ;
- les valeurs de `.env` sont correctes ;
- le port PostgreSQL est accessible ;
- la base `sales_predictions` existe.

Test rapide :

```bash
psql -U postgres -d sales_predictions -c "SELECT 1;"
```

### Une table ou une colonne est absente

Appliquez les migrations :

```bash
python -m alembic upgrade head
```

### Le port 8001 ou 8501 est déjà utilisé

Pour Django :

```bash
python backend/manage.py runserver 8001
```

Pour Streamlit :

Lancez l'application sur un autre port :

```bash
python -m streamlit run app/main.py --server.port 8502
```

Avec Docker, modifiez `STREAMLIT_PORT` dans `.env`, par exemple :

```dotenv
STREAMLIT_PORT=8502
```

### Le port PostgreSQL 5434 est déjà utilisé

Choisissez un autre port exposé dans `.env` :

```dotenv
POSTGRES_HOST_PORT=5435
```

L'application Docker continuera à joindre la base avec `db:5432`. Seul le port
utilisé depuis pgAdmin ou la machine hôte changera.

### Le conteneur de l'application redémarre en boucle

Consultez les journaux et l'état de santé de PostgreSQL :

```bash
docker compose ps
docker compose logs app
docker compose logs web
docker compose logs db
```

Les causes les plus fréquentes sont un mot de passe différent dans un ancien
volume PostgreSQL, une restauration incomplète ou une migration en erreur.

### XGBoost est long au premier lancement

L'entraînement de Random Forest et XGBoost est plus coûteux que celui des
baselines. Commencez avec un produit et une période de test limitée pour valider
l'installation.

## Points d'attention avant une mise en production

Avant d'exposer la plateforme à des données réelles, il faut notamment prévoir :

- des tests systématiques empêchant toute lecture entre deux dépôts ;
- un utilisateur PostgreSQL de production non-superviseur et sans privilège
  `BYPASSRLS` ; le rôle managé Railway répond normalement à cette exigence ;
- HTTPS et une gestion sécurisée des secrets ;
- des sauvegardes PostgreSQL automatisées ;
- une stratégie de tests automatisés et de déploiement ;
- la supervision du serveur et des tâches de réentraînement.

Ne publiez jamais le fichier `.env` ni une sauvegarde contenant des données
réelles.

## État actuel

Le projet comprend les lots fonctionnels suivants :

1. Initialisation technique et base PostgreSQL.
2. Dashboard descriptif.
3. Préparation des données et baselines.
4. Modèles ML, backtesting et prévision future.
5. Recommandations de stock et alertes décisionnelles.
6. Suivi de performance et dérive des modèles.
7. Import Excel contrôlé.
8. Réceptions et mouvements de stock.
9. Finalisation de l'expérience Streamlit.
10. Socle du produit Django : inscription, connexion, création et sélection du
    dépôt, rôles, contexte multi-dépôts, interface responsive et API initiale.
11. Isolation des données métier : `company_id` obligatoire, contraintes
    uniques par dépôt, RLS PostgreSQL, reprise du dépôt historique et contexte
    Streamlit verrouillé.

La prochaine évolution recommandée consiste à séparer la **Vue d’ensemble**,
orientée actions immédiates, d’un **Tableau de bord analytique** filtrable par
période. Ce dernier présentera les tendances de ventes, les comparaisons avec la
période précédente et les classements métier. Le client mobile viendra ensuite
consommer l’API stabilisée.
