# Pilotage prédictif des ventes

Application web de suivi et de prévision des ventes pour un dépôt de boissons.
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
- Import Excel guidé des ventes, stocks, produits et clients.
- Validation des références, doublons, champs obligatoires et règles métier.
- Génération automatique des codes internes et numéros de mouvements.
- Tableau de bord de qualité ML et détection de dérive.

## Technologies

- Python
- Streamlit
- PostgreSQL
- SQLAlchemy et Psycopg
- Alembic
- Pandas et NumPy
- Plotly
- scikit-learn
- XGBoost
- OpenPyXL

## Organisation du projet

```text
sales_predictive_analytics/
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

L'application suit une séparation simple :

```text
Pages Streamlit → Services métier → Repositories → PostgreSQL
                           ↓
                     Modules ML
```

Les pages ne portent pas directement les requêtes SQL. Les services valident et
orchestrent les opérations, tandis que les repositories gèrent la persistance.

## Prérequis

- Git.
- Docker Desktop, ou Docker Engine avec le plugin Compose.

Pour une installation sans Docker, il faut aussi Python 3.11 ou une version
ultérieure, PostgreSQL et le client `psql`.

## Installation avec Docker — recommandée

Docker fournit Python 3.12, PostgreSQL 17 et toutes les dépendances nécessaires.
Il n'est donc pas nécessaire d'installer Python ou PostgreSQL directement sur la
nouvelle machine.

### 1. Récupérer le projet

```bash
git clone <URL_DU_DEPOT>
cd sales_predictive_analytics
```

Remplacez `<URL_DU_DEPOT>` par l'URL Git réelle du projet.

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
```

Le `DB_HOST=localhost` sert aux commandes exécutées directement sur la machine.
Dans le conteneur, `docker-compose.yml` le remplace automatiquement par :

```text
DB_HOST=db
DB_PORT=5432
```

La communication est donc organisée ainsi :

```text
Navigateur                 → localhost:8501
pgAdmin / machine hôte     → localhost:5434
Application dans Docker    → db:5432
PostgreSQL local éventuel  → localhost:5432
```

Dans Docker Desktop, les ressources apparaissent avec des noms cohérents :

```text
Projet       : sales_predictive_analytics
Application  : app
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
Création du schéma et des référentiels
             ↓
Application des migrations Alembic
             ↓
Démarrage de Streamlit
```

Ouvrez ensuite [http://localhost:8501](http://localhost:8501).

L'initialisation du schéma est idempotente : lors des démarrages suivants, le
conteneur détecte la base existante et applique seulement les migrations Alembic
qui manquent.

### 4. Charger les données synthétiques — facultatif

La génération des données de démonstration n'est jamais automatique. Sur une
base Docker neuve uniquement, exécutez :

```bash
docker compose exec app \
  python database_setup/scripts/generate_sample_data.py
```

Cette commande crée environ deux années de ventes, stocks, clients, réceptions,
météo et anomalies. Ne l'exécutez jamais après avoir restauré ou importé des
données réelles.

### 5. Commandes Docker courantes

Démarrer en arrière-plan :

```bash
docker compose up -d --build
```

Voir les journaux :

```bash
docker compose logs -f app
docker compose logs -f db
```

Vérifier l'état des services :

```bash
docker compose ps
```

Vérifier la migration active :

```bash
docker compose exec app python -m alembic current
```

Arrêter les conteneurs sans supprimer les données :

```bash
docker compose down
```

Reconstruire l'application après une modification des dépendances ou du code :

```bash
docker compose up -d --build app
```

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
   docker compose up -d --build app
   ```

6. Contrôlez la migration :

   ```bash
   docker compose exec app python -m alembic current
   ```

Le démarrage du service `db` seul ne crée pas les tables métier. Cela laisse une
base propre pour la restauration. Au démarrage de `app`, le script détecte le
schéma restauré, ne rejoue pas les scripts initiaux et lance uniquement les
migrations Alembic nécessaires.

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
docker compose up -d --build app
docker compose exec app python -m alembic current
```

Les fichiers `*.backup` et `*.dump` sont exclus de l'image Docker. Conservez-les
dans un emplacement sécurisé et ne les ajoutez jamais au dépôt Git.

## Déploiement sur Railway

Railway détecte automatiquement le `Dockerfile` situé à la racine. Le service
web doit être relié à un PostgreSQL Railway managé ; le service `db` du fichier
Compose est réservé au développement local.

### Variables du service Streamlit

Dans l'onglet **Variables** du service applicatif, configurez :

```dotenv
DATABASE_URL=${{Postgres.DATABASE_URL}}
INITIALIZE_DATABASE=false
```

Adaptez `Postgres` si le service PostgreSQL porte un autre nom dans Railway.
`DATABASE_URL` est prioritaire sur les variables `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER` et `DB_PASSWORD`.

Railway injecte automatiquement `PORT`. Le conteneur démarre Streamlit avec :

```bash
python -m streamlit run app/main.py \
  --server.address=0.0.0.0 \
  --server.port=${PORT:-8501}
```

Dans **Settings → Deploy**, laissez de préférence le champ **Start Command**
vide afin que Railway utilise l'`ENTRYPOINT` et le `CMD` du Dockerfile. Si une
commande personnalisée est indispensable, utilisez explicitement un shell :

```bash
sh -c 'python -m alembic upgrade head && python -m streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT:-8501}'
```

Le démarrage Railway suit uniquement ce cycle :

```text
Connexion au PostgreSQL Railway
              ↓
alembic upgrade head
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
5. Déployez ou redéployez l'application.

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
python -m alembic upgrade head
```

Vérifiez la version appliquée :

```bash
python -m alembic current
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

### 6. Lancer l'application

```bash
python -m streamlit run app/main.py
```

Ouvrez ensuite :

```text
http://localhost:8501
```

## Parcours conseillé dans l'application

### Avec les données de démonstration

1. Ouvrir **Tableau de bord** pour vérifier les ventes disponibles.
2. Ouvrir **Comparaison des modèles** et lancer un backtesting sur un produit.
3. Générer une prévision dans **Prévision future**.
4. Consulter les commandes suggérées dans **Pilotage métier**.
5. Vérifier le cycle de vie des prévisions dans **Qualité ML**.

### Avec des données réelles

1. Aller dans **Import de données**.
2. Choisir le type de données.
3. Télécharger le modèle Excel guidé.
4. Compléter uniquement les champs demandés.
5. Charger le fichier et lancer l'analyse.
6. Corriger les lignes invalides ou importer seulement les lignes valides.
7. Consulter l'historique du lot d'import.

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

Vérifier que les modules Python se compilent :

```bash
python -m compileall -q app alembic
```

Afficher l'état des migrations :

```bash
python -m alembic current
```

Mettre la base à niveau après avoir récupéré de nouvelles modifications :

```bash
git pull
pip install -r requirements.txt
python -m alembic upgrade head
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

### Le port 8501 est déjà utilisé

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
docker compose logs db
```

Les causes les plus fréquentes sont un mot de passe différent dans un ancien
volume PostgreSQL, une restauration incomplète ou une migration en erreur.

### XGBoost est long au premier lancement

L'entraînement de Random Forest et XGBoost est plus coûteux que celui des
baselines. Commencez avec un produit et une période de test limitée pour valider
l'installation.

## Points d'attention avant une mise en production

Cette version est une application métier Streamlit. Avant de l'exposer sur un
réseau public, il faut notamment prévoir :

- une authentification réellement connectée à l'interface ;
- une gestion des rôles et autorisations ;
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
9. Finalisation de l'expérience web.

La prochaine évolution naturelle est l'exposition du moteur via une API, puis la
création éventuelle d'un client mobile.
