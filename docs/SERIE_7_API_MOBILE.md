# Série 7 — API mobile Django REST Framework

- Statut : **implémentée et validée localement sur SPA-2**
- Socle : JWT, contexte multi-dépôts, endpoints P0, OpenAPI, throttling,
  idempotence, audit et pagination SQL livrés
- Branche d'intégration : `feature/SPA-2`

Ce document conserve le contrat fonctionnel de l'API et sert désormais de
référence de validation et de non-régression.

## 1. Mission à donner à Codex

```text
Implémente la Série 7 décrite dans docs/SERIE_7_API_MOBILE.md.

Commence par lire complètement ce document, README.md,
docs/MULTI_TENANT_ARCHITECTURE.md, backend/api, backend/accounts,
backend/companies, backend/operations, backend/decisions et
backend/forecasting.

Travaille sur une branche feature/api-mobile-v1 à jour avec main. Préserve
l’interface Django et le laboratoire Streamlit. Réutilise les services métier
existants : ne recopie pas les règles de stock, de vente, de réception, de
prévision ou d’audit dans les vues API.

Chaque lecture et écriture métier doit être limitée au dépôt explicitement
autorisé. Ajoute les tests de permissions, de cloisonnement multi-dépôts et de
non-régression. N’effectue aucun déploiement et ne pousse pas sur main sans
autorisation explicite.
```

## 2. Objectif fonctionnel

Fournir une API `/api/v1/` stable pour une future application Flutter. Elle
doit permettre :

- la connexion par adresse e-mail **ou** numéro de téléphone ;
- la sélection sécurisée d’un dépôt accessible ;
- la consultation du tableau de bord, des produits, clients, fournisseurs,
  stocks, ventes, commandes et prévisions ;
- la saisie d’une vente et d’un mouvement de stock ;
- la création et la réception d’une commande fournisseur ;
- le lancement d’une prévision et la consultation asynchrone de son résultat ;
- l’application des mêmes rôles, transactions et journaux d’audit que le web.

L’API ne remplace ni Django HTML ni Streamlit. Elle devient un troisième client
des mêmes services métier.

## 3. État implémenté

Le projet possède désormais :

- Django REST Framework dans `backend/api/` ;
- des endpoints de lecture pour l’utilisateur, les dépôts, le tableau de bord,
  les produits, les stocks et les ventes ;
- une authentification JWT avec refresh rotatif, en complément de la session Django ;
- une authentification web par e-mail ou téléphone dans
  `accounts.backends.EmailOrPhoneBackend` ;
- un dépôt explicite via `X-Company-ID`, contrôlé contre l'adhésion active ;
- les rôles `OWNER`, `ADMIN`, `ANALYST` et `VIEWER` ;
- les règles métier de ventes et stocks dans `operations` ;
- les commandes fournisseur dans `decisions` ;
- les prévisions asynchrones dans `forecasting` et Celery ;
- la piste d’audit dans `audit`, y compris les transitions de commande ;
- les écritures produits, clients, fournisseurs, ventes, réceptions et commandes ;
- l'idempotence persistée des mutations mobiles sensibles ;
- la pagination exécutée en base pour produits, stocks et ventes ;
- le throttling du login et des écritures sensibles ;
- un schéma OpenAPI documentant les en-têtes métier.
- PostgreSQL RLS et les services SQLAlchemy limités par dépôt.

Travaux de validation restant avant un pilote mobile :

- maintenir un test d'intégration API → Celery → résultat de prévision ;
- exécuter les parcours mobiles sur un client Flutter réel lorsqu'il existera ;
- surveiller les seuils de throttling à partir de l'usage de production.

## 4. Dépendance avec la Série 3

La Série 3 centralise désormais le contexte multi-dépôts dans
`companies.tenancy`, `companies.db` et `api.tenant`. La Série 7 doit utiliser ce
socle partagé et ne doit pas créer une seconde logique divergente.

Si les deux séries sont développées en parallèle :

1. le collègue peut commencer l’authentification, les serializers, OpenAPI et
   les tests API globaux ;
2. il ne doit pas modifier le middleware web de sélection du dépôt sans
   coordination ;
3. avant d’implémenter les endpoints métier, il doit rebaser sa branche sur la
   version de `main` contenant la Série 3 ;
4. les endpoints API doivent appeler le résolveur de tenant partagé livré par
   la Série 3 ;
5. aucun `set_config('app.current_company_id', ...)` supplémentaire ne doit
   être copié dans les vues API.

La session web doit continuer à fonctionner. L’ajout des jetons mobiles ne doit
pas casser l’authentification actuelle de Django.

## 5. Décisions d’architecture obligatoires

### 5.1 Authentification

Utiliser des jetons JWT courts avec rotation des refresh tokens. La solution
recommandée est `djangorestframework-simplejwt` avec son mécanisme de blacklist.

Conserver temporairement `SessionAuthentication` pour les tests et clients web
existants, mais le client Flutter utilisera :

```http
Authorization: Bearer <access_token>
```

Le login reçoit un champ unique `identifier`, contenant soit un e-mail, soit un
téléphone. Il doit réutiliser `EmailOrPhoneBackend` et `normalize_phone`.

Ne jamais retourner le hash du mot de passe, les permissions Django internes,
les erreurs SMTP, les traces Python ou les secrets de configuration.

### 5.2 Contexte du dépôt

Les endpoints globaux suivants ne nécessitent pas de dépôt :

- authentification ;
- profil courant ;
- liste des dépôts accessibles.

Tous les endpoints métier exigent :

```http
X-Company-ID: <uuid-du-depot>
```

Après authentification DRF, le serveur doit :

1. valider le format UUID ;
2. retrouver un dépôt actif ;
3. vérifier une adhésion active de l’utilisateur ;
4. attacher `request.company` et `request.membership` ;
5. refuser toute donnée d’un autre dépôt.

Le super administrateur de la plateforme peut conserver son accès explicite,
mais aucun utilisateur normal ne doit le recevoir indirectement.

`company_id` ne doit jamais être accepté dans le JSON d’une vente, d’un stock,
d’une commande, d’une réception ou d’une prévision. Il vient uniquement du
contexte vérifié.

Réponses attendues :

- en-tête manquant ou UUID invalide : `400 company_context_required` ;
- dépôt non autorisé : `403 company_access_denied` ;
- ressource absente du dépôt actif : `404 not_found` ;
- rôle insuffisant : `403 permission_denied`.

### 5.3 Services et transactions

Une vue API valide et sérialise les données, puis appelle un service existant.
Elle ne réimplémente pas directement :

- la diminution ou l’augmentation du stock ;
- la génération des numéros métier ;
- l’annulation logique ;
- la réception partielle d’une commande ;
- le choix d’un modèle prédictif ;
- l’écriture du journal d’audit.

Les écritures qui modifient plusieurs tables doivent rester atomiques. Toute
mutation réussie doit produire une entrée d’audit avec l’acteur et le dépôt.

### 5.4 Compatibilité

- Ne pas modifier les routes HTML existantes.
- Ne pas supprimer les endpoints API de lecture existants.
- Ne pas modifier Streamlit.
- Ne pas casser les formats Excel.
- Ne pas changer les règles de rôles sans décision produit.
- Toute migration doit être additive, réversible et sans réinitialisation de la
  base de production.

## 6. Contrat JSON commun

### Succès sur une ressource

```json
{
  "data": {
    "id": "uuid",
    "code": "PRD-000001"
  }
}
```

### Liste paginée

```json
{
  "results": [],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "count": 0,
    "pages": 0,
    "next": null,
    "previous": null
  }
}
```

La pagination doit être effectuée côté base, pas après chargement de toutes les
lignes en mémoire. Limiter `page_size` à 100.

### Erreur

```json
{
  "code": "validation_error",
  "message": "Certaines informations sont incorrectes.",
  "errors": {
    "items.0.quantity": ["La quantité doit être supérieure à zéro."]
  }
}
```

Les montants et quantités décimales sont transmis sous forme de chaînes pour
éviter les erreurs de virgule flottante. Les dates utilisent `YYYY-MM-DD` et les
dates/heures ISO 8601 avec fuseau.

## 7. Endpoints à livrer

### 7.1 Authentification et identité — P0

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/api/v1/auth/login/` | Public |
| `POST` | `/api/v1/auth/refresh/` | Refresh valide |
| `POST` | `/api/v1/auth/logout/` | Authentifié |
| `GET` | `/api/v1/me/` | Authentifié |
| `GET` | `/api/v1/companies/` | Authentifié |

Login :

```json
{
  "identifier": "+22370000000",
  "password": "mot-de-passe"
}
```

Réponse minimale : access token, refresh token, durée de vie, utilisateur et
liste compacte des dépôts accessibles. Le logout place le refresh token en
blacklist. Les comptes inactifs et adhésions suspendues doivent être refusés.

### 7.2 Tableau de bord et référentiels — P0

| Méthode | Route | Autorisation |
|---|---|---|
| `GET` | `/api/v1/dashboard/summary/` | Tous les rôles |
| `GET` | `/api/v1/products/` | Tous les rôles |
| `POST` | `/api/v1/products/` | OWNER, ADMIN |
| `GET/PATCH/DELETE` | `/api/v1/products/{id}/` | Lecture tous, mutation OWNER/ADMIN |
| `GET/POST` | `/api/v1/customers/` | Lecture tous, création OWNER/ADMIN |
| `GET/PATCH/DELETE` | `/api/v1/customers/{id}/` | Lecture tous, mutation OWNER/ADMIN |
| `GET/POST` | `/api/v1/suppliers/` | Lecture tous, création OWNER/ADMIN |
| `GET/PATCH/DELETE` | `/api/v1/suppliers/{id}/` | Lecture tous, mutation OWNER/ADMIN |

`DELETE` réalise un archivage logique. Prévoir `status`, `q`, `ordering`,
`page` et `page_size`. Les codes métier sont générés côté serveur et ne sont pas
modifiables.

### 7.3 Stocks et mouvements — P0

| Méthode | Route | Autorisation |
|---|---|---|
| `GET` | `/api/v1/stocks/` | Tous les rôles |
| `GET` | `/api/v1/stocks/{product_id}/` | Tous les rôles |
| `GET` | `/api/v1/stock-movements/` | Tous les rôles |
| `POST` | `/api/v1/stock-movements/` | OWNER, ADMIN |

Une correction manuelle doit exiger un type autorisé, une quantité positive et
un motif. Le client ne fournit jamais le stock final : le serveur le calcule
transactionnellement et refuse un stock négatif selon les règles existantes.

### 7.4 Ventes — P0

| Méthode | Route | Autorisation |
|---|---|---|
| `GET/POST` | `/api/v1/sales/` | Lecture tous, création OWNER/ADMIN |
| `GET/PATCH/DELETE` | `/api/v1/sales/{id}/` | Lecture tous, mutation OWNER/ADMIN |

Création indicative :

```json
{
  "sale_date": "2026-08-12",
  "sale_time": "14:30:00",
  "customer_id": "uuid-ou-null",
  "payment_method": "CASH",
  "payment_status": "PAID",
  "items": [
    {
      "product_id": "uuid",
      "quantity_packages": "3",
      "unit_price": "8500"
    }
  ]
}
```

Le serveur vérifie les produits, calcule les totaux, crée les lignes et
mouvements de stock dans une transaction. `DELETE` annule logiquement la vente
et produit les mouvements compensatoires existants. Une modification ne doit
pas permettre de changer silencieusement les quantités si le workflow web ne le
permet pas.

### 7.5 Commandes et réceptions fournisseur — P0

| Méthode | Route | Autorisation |
|---|---|---|
| `GET/POST` | `/api/v1/purchase-orders/` | Lecture tous, création OWNER/ADMIN |
| `GET` | `/api/v1/purchase-orders/{id}/` | Tous les rôles |
| `POST` | `/api/v1/purchase-orders/{id}/send/` | OWNER, ADMIN |
| `POST` | `/api/v1/purchase-orders/{id}/cancel/` | OWNER, ADMIN |
| `POST` | `/api/v1/purchase-orders/{id}/receive/` | OWNER, ADMIN |
| `GET` | `/api/v1/receipts/` | Tous les rôles |
| `GET` | `/api/v1/receipts/{id}/` | Tous les rôles |

Respecter la machine d’état existante :

```text
DRAFT → SENT → PARTIALLY_RECEIVED → RECEIVED
   └──────────────→ CANCELLED
```

Une réception :

- ne dépasse pas la quantité restante ;
- peut être partielle ;
- augmente le stock une seule fois ;
- conserve le lien avec la commande ;
- est protégée contre les doubles soumissions ;
- met à jour le statut de la commande dans la même transaction.

### 7.6 Prévisions asynchrones — P0

| Méthode | Route | Autorisation |
|---|---|---|
| `GET/POST` | `/api/v1/forecast-jobs/` | Lecture tous, création OWNER/ADMIN/ANALYST |
| `GET` | `/api/v1/forecast-jobs/{id}/` | Tous les rôles |
| `POST` | `/api/v1/forecast-jobs/{id}/retry/` | OWNER/ADMIN/ANALYST |
| `GET` | `/api/v1/forecast-jobs/{id}/result/` | Tous les rôles |

Le `POST` reçoit seulement `product_id` et éventuellement `horizon` limité de 1
à 7. Il réutilise le contrôle de fraîcheur par produit et la contrainte empêchant
deux jobs actifs pour le même produit.

Réponse de création : `202 Accepted`, identifiant du job, statut `QUEUED` et URL
de suivi. Le mobile interroge l’URL jusqu’à `SUCCESS` ou `FAILED`. Ne jamais
exposer `error_message` technique brut ; retourner un message utilisateur et un
code d’erreur stable.

Le résultat métier doit contenir au minimum : période, ventes probables,
quantité prudente, stock disponible, quantité recommandée, risque, détail par
jour et date de génération. Les métriques ML avancées peuvent rester dans un
objet optionnel `quality`.

### 7.7 Robustesse mobile — P1 avant pilote réel

Les connexions mobiles peuvent être interrompues après l’envoi d’une requête.
Les créations sensibles doivent accepter :

```http
Idempotency-Key: <uuid-généré-par-le-client>
```

À couvrir au minimum : ventes, mouvements manuels, commandes, réceptions et
jobs de prévision. Une même clé, pour le même utilisateur, dépôt, méthode et
route, retourne la réponse précédente sans répéter l’écriture. Une clé réutilisée
avec un contenu différent retourne `409 idempotency_conflict`.

Cette fonctionnalité peut nécessiter une table Django additive dédiée. Ajouter
une politique d’expiration et une commande de nettoyage, sans stocker de secret.

## 8. Matrice de permissions

| Domaine | OWNER | ADMIN | ANALYST | VIEWER |
|---|---:|---:|---:|---:|
| Consulter les données | Oui | Oui | Oui | Oui |
| Produits, clients, fournisseurs | Écriture | Écriture | Lecture | Lecture |
| Ventes et mouvements | Écriture | Écriture | Lecture | Lecture |
| Commandes et réceptions | Écriture | Écriture | Lecture | Lecture |
| Générer une prévision | Oui | Oui | Oui | Non |
| Consulter une prévision | Oui | Oui | Oui | Oui |

Les permissions sont vérifiées côté API et service. Masquer un bouton Flutter
ne constitue pas un contrôle de sécurité.

## 9. OpenAPI et versionnement

Ajouter `drf-spectacular` ou un équivalent maintenu et exposer :

- `/api/v1/schema/` ;
- `/api/v1/docs/` en environnement autorisé.

Documenter les en-têtes `Authorization`, `X-Company-ID` et `Idempotency-Key`,
les enums, exemples, erreurs et permissions. Le schéma doit être générable sans
accéder aux données de production.

Toute rupture future de contrat utilisera `/api/v2/`. Ne pas renommer ou
supprimer silencieusement un champ publié dans `/api/v1/`.

## 10. Sécurité API

- Access token court, refresh token rotatif et révocable.
- Throttling du login et des écritures sensibles.
- Aucun CORS permissif par défaut ; Flutter natif n’en a pas besoin.
- Si Flutter Web est ajouté, autoriser uniquement les origines configurées.
- Limites de longueur sur recherches, notes et chaînes.
- Validation stricte des UUID, dates, quantités et enums.
- Aucun détail indiquant qu’un UUID existe dans un autre dépôt.
- Utiliser `select_related`, `prefetch_related` et pagination côté base.
- Ne jamais journaliser mot de passe, access token ou refresh token.

## 11. Tests obligatoires

### Authentification

- login e-mail valide ;
- login téléphone valide après normalisation ;
- mot de passe invalide ;
- compte inactif ;
- rotation et révocation du refresh token ;
- endpoint protégé sans Bearer token.

### Multi-dépôts

Créer systématiquement deux dépôts A et B dans les tests :

- un membre de A ne lit aucun objet de B ;
- un UUID de B utilisé sous le contexte A retourne `404` ;
- un `X-Company-ID` sans adhésion retourne `403` ;
- `company_id` injecté dans un body est ignoré ou rejeté ;
- le super administrateur suit une règle explicite et testée ;
- chaque écriture porte le dépôt actif vérifié.

### Rôles

- OWNER et ADMIN réalisent les écritures opérationnelles ;
- ANALYST génère une prévision mais ne modifie pas le stock ;
- VIEWER reste strictement en lecture.

### Transactions

- vente réussie : stock diminué une fois et audit créé ;
- vente invalide : aucune écriture partielle ;
- annulation : compensation unique ;
- réception partielle puis complète : stock et statut exacts ;
- double requête avec la même clé d’idempotence : une seule écriture ;
- job de prévision dupliqué : refus métier stable.

### Contrat

- pagination et limite maximale ;
- filtres et tris autorisés uniquement ;
- format uniforme des erreurs ;
- schéma OpenAPI généré sans avertissement bloquant.

## 12. Organisation recommandée du code

```text
backend/api/
├── urls.py
├── authentication.py
├── permissions.py
├── tenant.py              # adaptateur vers le socle partagé de Série 3
├── pagination.py
├── exceptions.py
├── idempotency.py
├── schema.py
├── serializers/
│   ├── auth.py
│   ├── catalog.py
│   ├── operations.py
│   ├── procurement.py
│   └── forecasting.py
├── views/
│   ├── auth.py
│   ├── catalog.py
│   ├── operations.py
│   ├── procurement.py
│   └── forecasting.py
└── tests/
    ├── factories.py
    ├── test_auth.py
    ├── test_tenant_isolation.py
    ├── test_operations.py
    ├── test_procurement.py
    └── test_forecasting.py
```

Ce découpage est une cible, pas une obligation de créer des abstractions vides.
Créer seulement les modules réellement utilisés.

## 13. Ordre de réalisation conseillé

1. Rebaser sur `main` après la Série 3.
2. Ajouter JWT, refresh, logout et tests d’authentification.
3. Brancher le contexte API sur le résolveur de dépôt partagé.
4. Uniformiser erreurs et pagination.
5. Compléter les endpoints de lecture.
6. Ajouter produits, clients et fournisseurs.
7. Ajouter stocks et ventes.
8. Ajouter commandes et réceptions.
9. Ajouter jobs et résultats de prévision.
10. Ajouter l’idempotence.
11. Générer OpenAPI et compléter les tests.
12. Mettre à jour README et `.env.example`.

Faire des commits petits et thématiques. Ne pas mélanger un refactoring global
de `operations` avec l’ajout d’un seul endpoint.

## 14. Définition de terminé

La Série 7 est terminée lorsque :

- le mobile peut se connecter par e-mail ou téléphone ;
- tous les endpoints métier exigent un dépôt autorisé ;
- la matrice des rôles est couverte par des tests ;
- aucune lecture ou écriture inter-dépôts n’est possible ;
- ventes et réceptions modifient le stock une seule fois ;
- les prévisions sont réellement asynchrones et consultables ;
- les écritures sensibles sont idempotentes ;
- OpenAPI décrit le contrat public ;
- les tests API passent avec PostgreSQL ;
- les tests Django existants restent verts ;
- aucune migration ne détruit ou ne réinitialise les données existantes ;
- la documentation de démarrage est mise à jour.

## 15. Hors périmètre initial

- création de l’application Flutter ;
- synchronisation complète hors ligne ;
- import Excel depuis le mobile ;
- administration globale de la plateforme ;
- exposition des écrans ML techniques de Streamlit ;
- WebSockets pour le suivi des prévisions ; le polling suffit en V1 ;
- modification des algorithmes de prévision.
