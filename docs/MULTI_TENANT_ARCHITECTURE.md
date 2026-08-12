# Architecture multi-entreprises

Statut : socle d'isolation implémenté le 02/08/2026
Périmètre : authentification, entreprises, rôles, isolation des données et
migration du schéma mono-entreprise existant.

Mise à jour du 12/08/2026 : la résolution des accès est centralisée dans
`companies.tenancy`, les transactions Django protégées dans `companies.db` et
les sessions SQLAlchemy dans `app.database.session`. L’adaptateur `api.tenant`
accepte un dépôt explicite vérifié via `X-Company-ID` tout en conservant la
session du produit web. Les références principales des tables métier disposent
également de clés étrangères composites `(company_id, id)`.

## 1. Objectif et invariant de sécurité

La plateforme doit héberger plusieurs entreprises dans une seule base
PostgreSQL, sans qu'une entreprise puisse lire, modifier ou référencer les
données d'une autre.

L'invariant central est :

```text
Toute donnée métier appartient à exactement une entreprise.
Toute requête métier est exécutée dans un contexte d'entreprise vérifié.
```

Un UUID difficile à deviner n'est pas une protection. Un accès par identifiant
doit toujours prendre cette forme :

```sql
SELECT *
FROM products
WHERE id = :product_id
  AND company_id = :current_company_id;
```

Le `company_id` ne doit jamais être accepté directement depuis une URL, un
fichier Excel ou un champ de formulaire. Il provient uniquement de la session
authentifiée et d'une adhésion active vérifiée.

## 2. Décisions structurantes

### Modèle de stockage

- Une seule base PostgreSQL.
- Un schéma `public` partagé.
- Une clé `company_id` obligatoire sur chaque table métier.
- `users` reste globale : un utilisateur peut appartenir à plusieurs espaces.
- `calendar_features` reste globale dans la première version.
- Les tables enfants portent également `company_id` pour simplifier les index,
  les politiques RLS et les contrôles d'intégrité.

### Défense en profondeur

L'isolation repose sur trois niveaux complémentaires :

1. Contexte d'entreprise vérifié après authentification.
2. Filtrage obligatoire dans les repositories.
3. Row-Level Security PostgreSQL après migration complète de l'application.

Les contraintes composites empêchent aussi une ligne de l'entreprise A de
référencer un produit, un client ou une prévision de l'entreprise B.

## 3. Modèle de contrôle

### `companies`

```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(180) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(50),
    city VARCHAR(120),
    timezone VARCHAR(80) NOT NULL DEFAULT 'Africa/Bamako',
    currency_code VARCHAR(3) NOT NULL DEFAULT 'XOF',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Le `code` est un identifiant technique global stable. Le nom peut évoluer.

### `users`

`users` représente une identité globale. Les changements requis sont :

- rendre `email` obligatoire et unique sans tenir compte de la casse ;
- conserver `password_hash`, sans jamais stocker un mot de passe brut ;
- supprimer à terme `users.role`, car le rôle dépend de l'entreprise ;
- ajouter éventuellement `last_login_at` et `email_verified_at`.

Contrainte recommandée :

```sql
CREATE UNIQUE INDEX uq_users_normalized_email
ON users (LOWER(TRIM(email)));
```

### `company_memberships`

```sql
CREATE TABLE company_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL
        CHECK (role IN ('OWNER', 'ADMIN', 'ANALYST', 'VIEWER')),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('INVITED', 'ACTIVE', 'SUSPENDED', 'REVOKED')),
    joined_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, user_id)
);

CREATE INDEX ix_company_memberships_user_status
ON company_memberships (user_id, status);
```

Une entreprise doit toujours conserver au moins un `OWNER`. Cette règle est
contrôlée transactionnellement dans le service de gestion des membres.

### Invitations

La table `company_invitations` utilise un jeton aléatoire dont seul le hash est
conservé, une date d'expiration, un e-mail ou un téléphone, un rôle et un
statut. Le lien brut est envoyé par e-mail ou affiché une fois au responsable
pour être partagé par SMS ou WhatsApp. Une invitation ne crée pas de session et
ne donne aucun accès avant acceptation. Le membre se connecte ensuite avec son
e-mail ou son téléphone.

### Compteurs métier

Les séquences PostgreSQL actuelles sont globales. Pour obtenir des numéros
indépendants par entreprise sans collision concurrente, la cible est :

```sql
CREATE TABLE company_counters (
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    counter_type VARCHAR(30) NOT NULL,
    next_value BIGINT NOT NULL DEFAULT 1 CHECK (next_value > 0),
    PRIMARY KEY (company_id, counter_type)
);
```

L'incrémentation utilise un `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`
dans la même transaction que la création de la donnée. Types prévus :
`PRODUCT`, `CUSTOMER`, `SALE`, `RECEIPT`, `MOVEMENT`, `IMPORT`, `MODEL_RUN`,
`FORECAST` et `ANOMALY`.

## 4. Rôles et autorisations

| Capacité | OWNER | ADMIN | ANALYST | VIEWER |
|---|---:|---:|---:|---:|
| Voir dashboards et alertes | Oui | Oui | Oui | Oui |
| Générer des prévisions | Oui | Oui | Oui | Non |
| Réévaluer les modèles | Oui | Oui | Oui | Non |
| Importer des données | Oui | Oui | Non | Non |
| Gérer produits et clients | Oui | Oui | Non | Non |
| Saisir réceptions et mouvements | Oui | Oui | Non | Non |
| Gérer les membres | Oui | Oui | Non | Non |
| Modifier l'entreprise | Oui | Oui | Non | Non |
| Transférer la propriété / archiver | Oui | Non | Non | Non |

Une autorisation est évaluée côté service. Masquer un bouton Streamlit améliore
l'expérience utilisateur, mais ne constitue jamais un contrôle de sécurité.

## 5. Matrice des tables

### Tables globales

| Table | Décision | Justification |
|---|---|---|
| `alembic_version` | Globale | État technique du schéma |
| `users` | Globale | Une identité peut rejoindre plusieurs entreprises |
| `companies` | Globale | Racine des tenants |
| `company_memberships` | Globale contrôlée | Relation utilisateur/entreprise |
| `company_invitations` | Globale contrôlée | Invitation vers une entreprise |
| `calendar_features` | Globale en V1 | Calendrier actuellement commun |

La météo et les événements présents dans `calendar_features` pourront être
séparés plus tard dans une table par localisation si plusieurs zones climatiques
sont prises en charge.

### Tables portant directement `company_id NOT NULL`

| Domaine | Tables |
|---|---|
| Référentiels | `product_categories`, `customer_types`, `products`, `customers`, `suppliers` |
| Imports | `import_batches`, `import_batch_errors` |
| Ventes | `sales`, `sale_items` |
| Approvisionnement | `purchase_receipts`, `purchase_receipt_items` |
| Stocks | `stock_movements`, `daily_stocks` |
| ML | `model_runs`, `forecasts`, `forecast_results` |
| Qualité ML | `forecast_evaluations`, `forecast_result_evaluations`, `model_performance_reviews` |
| Surveillance | `anomalies` |

Ajouter `company_id` aux tables enfants est volontaire. Cela permet une policy
RLS directe, évite un `JOIN` dans chaque contrôle et accélère les recherches.

## 6. Contraintes uniques à transformer

Les contraintes globales suivantes deviennent locales à l'entreprise :

| Table | Contrainte cible |
|---|---|
| `product_categories` | `(company_id, code)` et `(company_id, LOWER(name))` |
| `customer_types` | `(company_id, code)` et `(company_id, LOWER(name))` |
| `products` | `(company_id, code)` |
| `customers` | `(company_id, code)` |
| `suppliers` | `(company_id, code)` |
| `import_batches` | `(company_id, batch_number)` |
| `sales` | `(company_id, sale_number)` |
| `sales` | `(company_id, external_reference)` lorsque non nul |
| `purchase_receipts` | `(company_id, receipt_number)` |
| `stock_movements` | `(company_id, movement_number)` |
| `daily_stocks` | `(company_id, stock_date, product_id)` |
| `model_runs` | `(company_id, run_number)` |
| `forecasts` | `(company_id, forecast_number)` |
| `anomalies` | `(company_id, anomaly_number)` |

Les index métier existants sont préfixés par `company_id`, par exemple :

```sql
CREATE INDEX ix_sales_company_date
ON sales (company_id, sale_date);

CREATE INDEX ix_daily_stocks_company_product_date
ON daily_stocks (company_id, product_id, stock_date DESC);
```

Les index `uq_products_business_identity` et
`uq_customers_normalized_phone` doivent également commencer par `company_id`.

## 7. Intégrité des références entre tenants

Un simple `FOREIGN KEY (product_id) REFERENCES products(id)` prouve que le
produit existe, mais pas qu'il appartient à la même entreprise.

Pour les relations sensibles, la cible utilise des clés composites :

```sql
ALTER TABLE products
ADD CONSTRAINT uq_products_company_id_id UNIQUE (company_id, id);

ALTER TABLE sale_items
ADD CONSTRAINT fk_sale_items_company_product
FOREIGN KEY (company_id, product_id)
REFERENCES products(company_id, id);
```

La même règle s'applique aux relations vers catégories, types de clients,
clients, fournisseurs, ventes, imports, réceptions, prévisions et modèles.

Les anciens foreign keys simples peuvent rester temporairement pendant la
migration, puis être supprimés lorsque toutes les clés composites sont validées.

## 8. Contexte tenant dans l'application

Après authentification :

```text
Utilisateur
  → adhésions ACTIVE
  → sélection d'une entreprise autorisée
  → TenantContext(company_id, user_id, role)
```

Objet cible :

```python
@dataclass(frozen=True)
class TenantContext:
    company_id: UUID
    user_id: UUID
    role: str
```

Chaque service et repository métier reçoit ce contexte :

```python
repository = DashboardRepository(db, tenant_context)
```

Règles :

- aucune valeur par défaut de `company_id` dans le code applicatif ;
- aucun repository métier instancié sans contexte ;
- toutes les recherches par UUID incluent l'entreprise ;
- les créations injectent `company_id` depuis le contexte ;
- les caches incluent `company_id` dans leur clé ;
- les tâches ML et imports conservent l'entreprise d'origine ;
- un changement d'espace invalide les résultats et états Streamlit précédents.

## 9. Row-Level Security PostgreSQL

Une fois tous les repositories migrés, chaque transaction positionne :

```sql
SET LOCAL app.current_company_id = 'uuid-de-l-entreprise';
```

Policy type :

```sql
ALTER TABLE sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_sales ON sales
USING (
    company_id = NULLIF(
        current_setting('app.current_company_id', true),
        ''
    )::uuid
)
WITH CHECK (
    company_id = NULLIF(
        current_setting('app.current_company_id', true),
        ''
    )::uuid
);
```

`SET LOCAL` doit être exécuté dans la transaction afin qu'une connexion rendue
au pool ne conserve jamais le tenant précédent. Sans contexte, la policy ne
retourne aucune ligne.

Le rôle de migration Alembic doit être traité séparément du rôle applicatif pour
que les migrations et backfills restent opérables sans désactiver la sécurité du
runtime.

## 10. Migration des données existantes

La révision Alembic `20260802_05` réalise désormais les opérations suivantes
dans une transaction PostgreSQL :

1. création du **Dépôt historique** avec l'UUID stable
   `00000000-0000-4000-8000-000000000001` ;
2. ajout de `company_id` aux 20 tables métier ;
3. rattachement de toutes les lignes existantes au dépôt historique ;
4. passage immédiat des colonnes en `NOT NULL` ;
5. transformation des unicités métier en unicités par dépôt ;
6. création des index préfixés par `company_id` ;
7. activation et forçage des politiques RLS ;
8. reconstruction de `v_sales_analysis` en vue `security_invoker`.

Le compte propriétaire n'est jamais choisi automatiquement. Après création du
compte Django, un administrateur exécute :

```bash
python backend/manage.py claim_legacy_company proprietaire@example.com
```

Cette séparation évite qu'un premier visiteur public puisse réclamer les données
restaurées. Les nouveaux dépôts reçoivent seulement leurs catégories et types de
clients privés ; aucune vente ni aucun produit ne leur est copié.

### Éléments restant à renforcer

- foreign keys composites `(company_id, id)` entre parents et enfants ;
- compteurs métier indépendants par dépôt ;
- transfert explicite de propriété entre deux membres ;
- suppression ou rapprochement de l'ancienne table technique `users` lorsque
  tous les usages de `created_by` auront migré vers les comptes Django.

## 11. Authentification

L'authentification arrive après la phase d'expansion du schéma.

Workflow :

```text
Email + mot de passe
  → identité active
  → adhésions actives
  → choix de l'entreprise
  → création du TenantContext
  → pages autorisées
```

Exigences minimales pour une authentification locale :

- hash Argon2id avec sel automatique ;
- comparaison en temps constant via une bibliothèque éprouvée ;
- limitation des tentatives de connexion ;
- renouvellement de session après authentification ;
- expiration et révocation des sessions ;
- aucun secret dans les logs ou paramètres d'URL.

Django fournit maintenant la session authentifiée durable, renouvelle son
identifiant à la connexion et vérifie l'appartenance au dépôt à chaque requête.
Streamlit reste un laboratoire technique séparé : son dépôt est fixé par une
variable d'environnement serveur et ne provient jamais d'un paramètre d'URL.

## 12. Tests d'isolation obligatoires

Chaque scénario utilise au minimum deux entreprises A et B.

- A ne voit aucun produit, client, vente, stock ou forecast de B.
- A ne peut pas charger un UUID de B par URL ou paramètre.
- A ne peut pas créer une vente avec un produit ou client de B.
- Un import A ne reconnaît pas les doublons et codes de B comme siens.
- Les numéros métier peuvent être identiques entre A et B.
- Les dashboards et métriques A restent inchangés lorsque B importe des ventes.
- Les entraînements et historiques ML sont isolés.
- Les caches ne réutilisent jamais un résultat d'un autre tenant.
- Une connexion SQL sans `app.current_company_id` ne retourne aucune donnée RLS.
- Le changement d'entreprise vide les sélections, uploads et résultats en session.

Ces tests sont bloquants avant l'ouverture à une deuxième entreprise réelle.

## 13. État d'implémentation

```text
TERMINÉ  Comptes Django + entreprises + appartenances + rôles
TERMINÉ  Sélection du dépôt et contexte de session vérifié
TERMINÉ  company_id NOT NULL + unicités locales + index
TERMINÉ  RLS PostgreSQL + contexte SQLAlchemy Streamlit
TERMINÉ  Reprise contrôlée du dépôt historique
TERMINÉ  Invitations temporaires et gestion des rôles de l'équipe
À FAIRE  Foreign keys composites + compteurs par dépôt
EN COURS Écrans métier Django et API opérationnelle complète
```
