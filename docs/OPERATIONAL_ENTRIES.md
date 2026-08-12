# Saisie opérationnelle Django

## Parcours disponibles

Les propriétaires et administrateurs d'un dépôt peuvent :

- créer, modifier, archiver et restaurer les clients ;
- créer, modifier, archiver et restaurer les fournisseurs ;
- créer une vente contenant jusqu'à 20 produits, avec une seule ligne affichée
  au départ puis un bouton d'ajout ;
- enregistrer une réception fournisseur contenant jusqu'à 20 produits ;
- créer un ajustement, une casse, une perte ou un retour de stock ;
- modifier les informations administratives d'une vente ou d'une réception ;
- annuler logiquement une vente ou une réception.

Les autres rôles conservent un accès en lecture selon leur matrice de droits.
Tous les identifiants sont contrôlés avec le `company_id` du dépôt actif.

Les codes clients et fournisseurs sont générés côté PostgreSQL. Ils ne sont
jamais demandés dans les formulaires. Un client archivé disparaît des nouvelles
ventes sans perdre son historique ; un fournisseur archivé disparaît des
nouvelles réceptions selon le même principe.

## Intégrité du stock

La création de l'entête, des lignes, des mouvements et du stock journalier est
atomique. En cas d'erreur, toute la transaction est annulée. Une sortie est
refusée lorsque le stock disponible est insuffisant.

Les quantités d'une opération validée ne sont jamais modifiées en place. Une
annulation de vente crée un `SALE_RETURN`; une annulation de réception crée un
`PURCHASE_RETURN`. L'entête est ensuite marqué avec `deleted_at` et
`deleted_by_user_id`, mais son historique demeure en base.

Les mouvements de stock ne sont ni modifiables ni supprimables dans l'interface.
Une correction est un nouveau mouvement inverse, accompagné d'un motif. Cette
règle permet de reconstituer le stock et de savoir qui a réalisé chaque action.

## Champs de traçabilité

Les tables `products`, `customers`, `suppliers`, `sales` et
`purchase_receipts` contiennent :

```text
created_at / created_by_user_id
updated_at / updated_by_user_id
deleted_at / deleted_by_user_id
```

`stock_movements` contient les champs de création et de mise à jour, mais aucun
champ de suppression logique puisqu'il constitue un registre append-only.

## Scripts directs dans pgAdmin

Les règles d'intégrité applicatives ne cherchent pas à interdire la maintenance
directe. La connexion Docker `postgres` est superutilisatrice : elle contourne
la RLS et peut exécuter des scripts dans Query Tool. Le trigger append-only de
`audit_logs` autorise lui aussi explicitement ce superutilisateur.

Pour tester avec un rôle PostgreSQL non-superutilisateur, fournissez le contexte
du dépôt dans la même transaction :

```sql
BEGIN;
SELECT set_config('app.current_company_id', '<uuid-du-depot>', TRUE);
SELECT * FROM sales ORDER BY created_at DESC LIMIT 20;
COMMIT;
```

L'accès direct reste une opération d'administration : faites un backup et
préférez des transactions explicites avant toute modification de production.
