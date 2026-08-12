# Backlogs techniques NexaStock

Dernière mise à jour : 12 août 2026

Ce document centralise les chantiers de code restant après les lots fonctionnels
déjà réalisés. Les tâches doivent être exécutées par séries, avec tests de
non-régression et sans réinitialiser une base existante.

## Ordre retenu

| Ordre | Série | Statut | Remarque |
|---:|---|---|---|
| 1 | Série 3 — Sécurisation multi-dépôts | **En cours** | Socle requis par l’API livré, audit étendu restant |
| 2 | Série 1 — Socle de tests | En cours | Runner PostgreSQL livré, couverture restante, CI reportée |
| 3 | Série 4 — Fiabilisation Celery | Planifiée | Après le socle tenant et les tests |
| 4 | Série 5 — Automatisation ML | Planifiée | Après Celery |
| 5 | Série 6 — Sécurité et supervision | Planifiée | Par incréments |
| 6 | Série 2 — Découpage des gros fichiers | Planifiée | Refactoring guidé par les tests |
| 7 | Série 8 — Tests d’interface | Planifiée | Après stabilisation des parcours |
| — | Série 7 — API mobile | **Déléguée** | Voir `SERIE_7_API_MOBILE.md` |

La CI distante n’est pas incluse dans le périmètre immédiat. Les tests locaux et
Docker restent obligatoires. GitHub Actions pourra être ajouté plus tard.

## Série 1 — Socle de tests fiable

### Objectif

Pouvoir valider le projet complet avec une base PostgreSQL de test contenant à
la fois les modèles Django et le schéma métier historique géré par SQL/Alembic.

### Tâches

- [x] Documenter la stratégie de base de tests PostgreSQL.
- [x] Initialiser automatiquement les tables métier SQL dans la base de test.
- [x] Appliquer les migrations Django et Alembic dans le bon ordre.
- [x] Fournir une commande unique de tests locaux.
- [x] Faire passer la suite complète sans utiliser la base de développement.
- [x] Ajouter des données de test minimales pour deux dépôts.
- [x] Ajouter les premiers tests d’intégration RLS et d’intégrité composite.
- [ ] Étendre les tests transactionnels métier à tous les parcours critiques.
- [ ] Mesurer la couverture et identifier les zones critiques non couvertes.
- [ ] Documenter les commandes de test dans README.
- [ ] Reporter la création de GitHub Actions/CI à une décision ultérieure.

### Critères de fin

- La base de test est créée et détruite automatiquement.
- Aucun test ne dépend de données locales existantes.
- Les tests opérationnels, prévisionnels et multi-dépôts passent ensemble.
- La production et sa base ne sont jamais contactées par la suite de tests.

## Série 2 — Découpage des gros fichiers

### Objectif

Réduire la dette de maintenance sans introduire de sur-ingénierie ni modifier le
comportement utilisateur.

### Tâches

- [ ] Séparer `operations/data.py` par domaine : catalogue, tiers, ventes,
  stocks et réceptions.
- [ ] Séparer `operations/views.py` selon les mêmes domaines.
- [ ] Séparer `decisions/views.py` entre recommandations, commandes et
  réceptions.
- [ ] Découper `DataImportService` en analyse, validation et persistance.
- [ ] Découper `static/js/app.js` en modules réellement indépendants.
- [ ] Réduire les dépendances croisées entre vues et SQL brut.
- [ ] Garder les composants de formulaire et d’interface existants.
- [ ] Réaliser le refactoring par petits commits protégés par les tests.

### Critères de fin

- Les responsabilités de chaque module sont explicites.
- Aucun comportement fonctionnel ou visuel n’est perdu.
- Les imports circulaires et duplications de règles métier sont absents.

## Série 3 — Sécurisation multi-dépôts

Statut : **en cours — socle requis par la Série 7 livré**.

### Objectif

Garantir qu’une requête web, API, Celery, Streamlit, script ou commande de
gestion ne peut lire ou modifier que le dépôt explicitement autorisé.

### Sous-lot 3.1 — Inventaire et invariant

- [x] Recenser toutes les entrées de contexte : session Django, API, Streamlit,
  Celery, commandes et scripts.
- [x] Recenser les repositories et requêtes SQL recevant `company_id`.
- [x] Lister les tables globales et les tables tenant-scoped.
- [x] Vérifier les contraintes composites et policies RLS existantes.
- [x] Écrire le premier invariant tenant sous forme de tests.

### Sous-lot 3.2 — Contexte partagé

- [x] Créer un composant unique de validation du dépôt et de l’adhésion.
- [x] Conserver la sélection par session pour Django HTML.
- [x] Prévoir un adaptateur explicite pour l’API mobile de Série 7.
- [x] Centraliser l’activation PostgreSQL RLS dans les connexions Django et
  SQLAlchemy.
- [x] Refuser un contexte absent, invalide, archivé ou non autorisé.
- [x] Définir explicitement le comportement du super administrateur plateforme.

### Sous-lot 3.3 — Repositories et écritures

- [ ] Supprimer les requêtes métier non filtrées par dépôt.
- [ ] Exiger `company_id` dans chaque service/repository tenant-scoped.
- [x] Filtrer simultanément la ressource et le dépôt lors d’un accès par UUID
  dans les repositories opérationnels actuels.
- [ ] Vérifier les relations produit, client, fournisseur, vente, réception,
  commande et prévision.
- [x] Garantir la restauration du rôle et du contexte RLS après chaque scope.
- [ ] Vérifier les imports Excel et générations automatiques de codes.

### Sous-lot 3.4 — Tâches et outils techniques

- [ ] Vérifier chaque tâche Celery avec un `company_id` explicite et validé.
- [ ] Tester la maintenance ML sur plusieurs dépôts.
- [ ] Sécuriser les commandes Django et scripts de seed.
- [x] Vérifier l’accès signé vers Streamlit et revalider l’adhésion active.
- [x] Empêcher une session ou un worker de réutiliser accidentellement le
  contexte précédent.

### Sous-lot 3.5 — Tests d’isolation

- [x] Créer deux dépôts A et B dans les tests tenant.
- [ ] Tester toutes les lectures A contre des UUID appartenant à B.
- [ ] Tester les créations avec des références appartenant à B.
- [ ] Tester OWNER, ADMIN, ANALYST, VIEWER et super administrateur.
- [x] Tester l’adhésion suspendue et le dépôt archivé.
- [x] Tester RLS directement via le rôle PostgreSQL restreint.
- [ ] Vérifier qu’une erreur ne révèle pas l’existence d’une donnée étrangère.

### Critères de fin

- Toutes les entrées applicatives utilisent le même invariant tenant.
- Aucun UUID étranger n’est lisible ou référençable.
- Les tests multi-dépôts couvrent web, services, Celery et PostgreSQL RLS.
- Les parcours existants d’un utilisateur à plusieurs dépôts restent valides.

## Série 4 — Fiabilisation Celery

### Tâches

- [ ] Rendre les tâches de prévision idempotentes.
- [ ] Classer les erreurs temporaires et définitives.
- [ ] Ajouter des retries avec backoff uniquement lorsque pertinent.
- [ ] Détecter et récupérer les jobs bloqués en attente ou en cours.
- [ ] Enregistrer tentatives, dernière erreur et dates d’exécution utiles.
- [ ] Ajouter un contrôle de santé Worker/Beat exploitable en production.
- [ ] Ajouter une politique de rétention des résultats Celery.
- [ ] Tester Redis indisponible, worker redémarré et tâche rejouée.

### Critères de fin

- Une tâche rejouée ne crée pas de doublon métier.
- Un job bloqué est détectable et récupérable.
- Une panne temporaire produit un état compréhensible et traçable.

## Série 5 — Automatisation et qualité ML

### Tâches

- [ ] Évaluer automatiquement les prévisions après leur échéance.
- [ ] Déclencher la réévaluation des modèles en baisse.
- [ ] Versionner dataset, features, paramètres et modèle retenu.
- [ ] Enregistrer les graines aléatoires et versions des bibliothèques.
- [ ] Effectuer des backtests sur plusieurs fenêtres chronologiques.
- [ ] Renforcer les tests des demandes intermittentes et ruptures de stock.
- [ ] Ajouter une commande Django de recalcul par produit ou dépôt.
- [ ] Produire un résumé métier des changements de modèle.

### Critères de fin

- Une prévision arrivée à échéance obtient une évaluation reproductible.
- Un modèle ne change que si le challenger dépasse le seuil défini.
- Toute décision ML peut être expliquée à partir des données enregistrées.

## Série 6 — Sécurité et supervision

### Tâches

- [ ] Refuser la clé Django de développement lorsque `DEBUG=false`.
- [ ] Conserver `/health/` comme liveness simple.
- [ ] Ajouter un endpoint de readiness vérifiant PostgreSQL et Redis.
- [ ] Exécuter et corriger `manage.py check --deploy`.
- [ ] Structurer les logs avec requête, utilisateur, dépôt et tâche Celery.
- [ ] Ajouter une remontée centralisée des erreurs, par exemple Sentry.
- [ ] Ajouter du throttling sur login, invitations et imports.
- [ ] Vérifier HSTS, cookies sécurisés, proxy SSL et origines CSRF.
- [ ] Documenter la sauvegarde et la restauration PostgreSQL.

### Critères de fin

- Une mauvaise configuration critique empêche un démarrage silencieusement
  vulnérable.
- Les pannes PostgreSQL, Redis, Celery et e-mail sont distinguables.
- Les logs ne contiennent ni mot de passe, ni token, ni secret.

## Série 7 — API mobile

Cette série est confiée à un collègue. Son périmètre, les endpoints, règles de
sécurité, tests et critères de fin sont définis dans
[`SERIE_7_API_MOBILE.md`](SERIE_7_API_MOBILE.md).

La Série 7 doit se rebaser sur le socle de contexte tenant livré par la Série 3.

## Série 8 — Tests d’interface et accessibilité

### Tâches

- [ ] Installer Playwright dans un environnement de test isolé.
- [ ] Automatiser connexion e-mail/téléphone et changement de dépôt.
- [ ] Automatiser produit, client, vente et diminution du stock.
- [ ] Automatiser commande, réception et augmentation du stock.
- [ ] Automatiser import Excel, prévision, invitation et audit.
- [ ] Tester les loaders et la prévention des doubles clics.
- [ ] Tester mobile, tablette et ordinateur.
- [ ] Ajouter des contrôles automatisés clavier, focus, labels et contrastes.
- [ ] Conserver quelques vérifications visuelles manuelles avant livraison.

### Critères de fin

- Les parcours essentiels sont reproductibles sans intervention manuelle.
- Les régressions responsive et les blocages d’actions sont détectés tôt.
- Les écrans essentiels restent utilisables au clavier et sur petit écran.

## Règles de réalisation communes

- Travailler sur une branche dédiée par série.
- Préserver les modifications sans rapport déjà présentes dans le worktree.
- Ne jamais réinitialiser automatiquement une base existante.
- Ajouter une migration uniquement lorsqu’elle est réellement nécessaire.
- Écrire ou adapter les tests avant de déclarer une tâche terminée.
- Vérifier au minimum Django, JavaScript, migrations et Docker selon le périmètre.
- Mettre à jour README et la documentation concernée.
- Ne pousser sur `main` qu’après validation explicite.
