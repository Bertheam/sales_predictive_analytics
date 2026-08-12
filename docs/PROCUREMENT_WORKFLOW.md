# Parcours d'approvisionnement

NexaStock expose un seul espace métier **Approvisionnement**. Les trois onglets
représentent trois états différents d'une même décision et ne doivent pas être
confondus.

## 1. Recommandations

Une recommandation répond à la question : **« Que devrais-je commander ? »**

Elle est calculée à partir de la dernière prévision exploitable du produit, du
stock disponible, d'une marge de prudence et du stock minimum. Le gestionnaire
peut ajuster la quantité et choisir un fournisseur. L'enregistrement produit un
`RestockDraft` au statut `DRAFT`.

Aucun mouvement de stock n'est créé à cette étape.

## 2. Commandes

Une commande répond à la question : **« Qu'ai-je demandé au fournisseur ? »**

Les plans préparés sont regroupés par fournisseur. Une commande ne peut donc
jamais mélanger plusieurs fournisseurs. Elle contient une copie du produit, de
la quantité et du coût indicatif afin de conserver un historique fiable même si
le catalogue évolue ensuite.

Le gestionnaire peut aussi créer une **commande libre** depuis tout produit
actif du catalogue, sans prévision ni `RestockDraft`. Cette possibilité couvre
les promotions, événements, opportunités fournisseur et décisions terrain non
détectées par le moteur. Les deux sources utilisent ensuite le même modèle
`PurchaseOrder` et le même cycle de réception.

Cycle de vie :

```text
Brouillon ──→ Envoyée ──→ Partiellement reçue ──→ Réceptionnée
    └──────────────────────────────→ Annulée
```

- **Brouillon** : la commande peut encore être vérifiée.
- **Envoyée** : elle a été communiquée au fournisseur.
- **Partiellement reçue** : une livraison existe, mais il reste un reliquat.
- **Réceptionnée** : toutes les quantités ont été livrées.
- **Annulée** : annulation logique, conservée dans l'historique.

Une commande ayant déjà une réception ne peut pas être annulée.

## 3. Réceptions

Une réception répond à la question : **« Qu'est-ce qui est réellement entré au
dépôt ? »**

C'est la seule étape qui modifie le stock. Sa validation réutilise le mécanisme
transactionnel des réceptions existantes :

1. création de `purchase_receipts` et `purchase_receipt_items` ;
2. création des mouvements d'entrée dans `stock_movements` ;
3. mise à jour du stock journalier dans `daily_stocks` ;
4. mise à jour des quantités reçues et du statut de la commande ;
5. liaison de la réception réelle à la commande Django.

Ces opérations partagent une transaction de base de données. En cas d'erreur,
la réception, le stock et la commande sont annulés ensemble.

Une **réception sans commande** reste disponible pour les livraisons qui n'ont
pas été préparées dans NexaStock. Elle utilise le même moteur de stock et revient
ensuite dans l'historique commun des réceptions.

## Isolation et autorisations

- Toutes les lectures et écritures sont limitées au dépôt actif.
- Seuls le propriétaire et l'administrateur peuvent préparer, commander,
  envoyer, annuler ou réceptionner.
- Le lecteur peut consulter le parcours sans le modifier.
- Les actions importantes sont inscrites dans `audit_logs`.

## Tables Django ajoutées

- `procurement_orders` : en-tête et statut de la commande ;
- `procurement_order_items` : produits commandés et quantités reçues ;
- `procurement_order_receipts` : liaison avec les réceptions PostgreSQL réelles.

Les migrations sont appliquées avec la commande habituelle :

```bash
python backend/manage.py migrate
```

En Docker :

```bash
docker compose exec web python backend/manage.py migrate
```

Le démarrage et les migrations n'effacent ni les commandes ni les données
existantes. Les scripts de démonstration ne doivent pas être lancés sur une base
contenant des données réelles.
