# Déployer gratuitement NexaStock avec Render et Neon

Ce guide décrit l’architecture gratuite utilisée pour le pilote NexaStock.
Le backup PostgreSQL est restauré une seule fois dans Neon. Render ne crée,
ne restaure et ne réinitialise jamais la base au démarrage.

## Architecture

```text
Utilisateurs ──► Django sur Render Free ──► PostgreSQL sur Neon Free
                       │
                       ├──► Brevo API pour les e-mails
                       │
                       └──► Streamlit Community Cloud
```

Les tâches Celery sont exécutées temporairement dans le processus Django avec
`CELERY_TASK_ALWAYS_EAGER=true`. Cette configuration évite un Worker et Redis
payants. Elle convient au pilote, mais les prévisions et les e-mails ne sont
plus traités en arrière-plan.

## 1. Base PostgreSQL Neon

Créez un projet Neon gratuit puis récupérez deux URLs depuis **Connect** :

- l’URL directe, sans `-pooler`, pour `pg_restore` et les migrations ;
- l’URL poolée pour les applications à forte concurrence, si nécessaire.

N’enregistrez jamais ces URLs dans Git. Elles contiennent le mot de passe de la
base.

La restauration initiale utilise uniquement l’URL directe :

```bash
export NEON_DATABASE_URL='postgresql://...url-directe-neon...'
./scripts/restore_neon_backup.sh SPA_DB
unset NEON_DATABASE_URL
```

Le script :

- refuse une URL poolée ;
- refuse toute base contenant déjà des tables publiques ;
- restaure séparément le schéma, les données, puis les contraintes et RLS ;
- n’utilise ni `--clean`, ni propriétaire, ni ACL de l’ancienne plateforme.

`SPA_DB`, `*.dump`, `*.backup` et `backups/` sont ignorés par Git et Docker.
Conservez toujours une autre copie du backup hors du projet.

## 2. Laboratoire Streamlit gratuit

Le laboratoire technique reste séparé de l’application métier Django.

1. Ouvrez [Streamlit Community Cloud](https://share.streamlit.io/).
2. Connectez le dépôt GitHub.
3. Choisissez la branche `main` et le fichier `app/main.py`.
4. Ajoutez les secrets suivants dans les paramètres de l’application :

```toml
DATABASE_URL = "postgresql://...url-neon..."
STREAMLIT_SIGNING_KEY = "une-cle-longue-identique-a-render"
STREAMLIT_REQUIRE_SIGNED_ACCESS = "true"
STREAMLIT_USE_RUNTIME_ROLE = "false"
```

Le fichier `packages.txt` installe uniquement la bibliothèque système requise
par XGBoost sur Streamlit Community Cloud.

Notez l’URL publique obtenue, par exemple
`https://nexastock-lab.streamlit.app`.

## 3. Application Django gratuite sur Render

Le fichier [`render.yaml`](../render.yaml) définit un seul Web Service gratuit
nommé `nexastock-web`.

Depuis Render, choisissez **New → Blueprint**, connectez le dépôt et appliquez
le Blueprint. Saisissez les variables marquées `sync: false` :

```text
DATABASE_URL            URL directe Neon
STREAMLIT_SIGNING_KEY   même secret que Streamlit Community Cloud
STREAMLIT_PUBLIC_URL    URL HTTPS du laboratoire Streamlit
BREVO_API_KEY           clé API transactionnelle Brevo
DEFAULT_FROM_EMAIL      NexaStock <adresse-validée@domaine.tld>
```

Utiliser l’URL directe Neon ici permet aux migrations Django et Alembic de
s’exécuter correctement. Le pilote ne lance qu’un processus Gunicorn, donc le
nombre de connexions reste faible.

## 4. Démarrage sûr et optimisé

Les fichiers statiques Django sont maintenant produits pendant la construction
de l'image Docker. Ils ne sont donc plus recalculés lorsque Render réveille le
service gratuit.

Au démarrage, `docker/render_migrations.py` calcule l'empreinte des migrations
Django et Alembic :

```text
empreinte déjà enregistrée ──► Gunicorn
             │
             └── nouvelle empreinte ──► migrations ──► Gunicorn
```

Une migration réussie est enregistrée dans `nexastock_schema_releases`. Si une
migration échoue, l'empreinte n'est pas enregistrée et le prochain démarrage la
retente. Un verrou PostgreSQL évite aussi que deux instances appliquent le même
schéma simultanément.

Pour forcer exceptionnellement une nouvelle vérification complète, définir
temporairement `RENDER_FORCE_MIGRATIONS=true`, redéployer, puis remettre la
variable à `false`.

Le démarrage n'exécute jamais :

- `02_schema.sql` ;
- `03_reference_data.sql` ;
- `04_indexes.sql` ;
- `generate_sample_data.py` ;
- `SPA_DB`.

Les variables `INITIALIZE_DATABASE=false` et `RUN_ALEMBIC=false` empêchent
l'entrypoint Docker de lancer une initialisation supplémentaire.

L'image Linux utilise la distribution CPU de XGBoost. Elle conserve les mêmes
modèles Python, sans embarquer les bibliothèques GPU inutiles sur Render.

## 5. Limites du pilote gratuit

- Render met Django en veille après 15 minutes sans trafic. La prochaine
  requête le réveille automatiquement avec un délai pouvant approcher une
  minute.
- Neon suspend le calcul après quelques minutes d’inactivité et le réveille
  automatiquement à la prochaine connexion.
- Les prévisions sont synchrones : l’utilisateur doit garder la page ouverte
  pendant le calcul.
- Les tâches planifiées Celery sont désactivées.
- Le cache de limitation de débit est local au processus Django.

Lorsque l’usage augmente, la première évolution recommandée est d’ajouter un
Worker Celery et un Redis/Valkey persistant. Le code repasse alors à
`CELERY_TASK_ALWAYS_EAGER=false` sans changer la logique métier.

## 6. Contrôles après déploiement

1. `/health/` retourne HTTP 200 ;
2. la connexion e-mail ou téléphone fonctionne ;
3. le changement de dépôt conserve une isolation correcte ;
4. les ventes, produits, stocks et historiques correspondent au backup ;
5. une invitation est acceptée par Brevo ;
6. une prévision se termine et son résultat est consultable ;
7. le bouton laboratoire ouvre Streamlit avec un lien signé ;
8. un accès direct à Streamlit sans signature est refusé.

## 7. Passage ultérieur en production payante

Le passage à une architecture asynchrone nécessite :

```text
Render Worker Celery
        +
Redis/Valkey persistant
        +
CELERY_TASK_ALWAYS_EAGER=false
```

Conservez Neon tant que sa capacité convient. Le passage d’un plan Neon Free à
un plan supérieur ne nécessite pas de nouvelle migration de base.
