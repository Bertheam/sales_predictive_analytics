# Journal d’audit

La table `audit_logs` constitue la piste d’audit fonctionnelle de NexaStock. Elle
répond aux questions : qui a réalisé l’action, dans quel dépôt, sur quelle
ressource, à quel moment et depuis quelle origine.

## Événements actuellement tracés

- connexion réussie, tentative refusée et déconnexion ;
- création et sélection d’un dépôt ;
- modification du profil ;
- création, modification, archivage et restauration d’un produit ;
- création, modification, archivage et restauration d’un client ;
- création, modification, archivage et restauration d’un fournisseur ;
- création, modification administrative et annulation logique d’une vente ;
- création, modification administrative et annulation logique d’une réception ;
- création d’un mouvement manuel de stock.
- création et révocation d’une invitation d’équipe ;
- acceptation d’une invitation, changement de rôle, suspension et réactivation
  d’un accès au dépôt.

Les futurs services d'imports et de prévisions doivent appeler
`audit.services.record_audit` après la réussite de leur transaction métier.

## Données enregistrées

- utilisateur et copie de son adresse e-mail au moment de l’action ;
- dépôt concerné ;
- type d’action ;
- type et identifiant de la ressource ;
- description lisible ;
- métadonnées métier minimales ;
- adresse IP, user-agent, identifiant de requête et horodatage.

Les mots de passe, jetons, cookies, contenus de fichiers importés et autres
secrets ne doivent jamais être placés dans `metadata`.

## Immutabilité et accès

Les entrées ne sont ni modifiables ni supprimables depuis le modèle ou
l’administration Django. PostgreSQL applique également un trigger append-only
qui refuse les `UPDATE` et `DELETE`. Une maintenance de conservation explicitement
autorisée devra activer temporairement `app.audit_maintenance` dans sa transaction.
Un superutilisateur PostgreSQL est également autorisé explicitement, afin que
les opérations de maintenance exécutées dans pgAdmin Query Tool restent
possibles. Cette exception ne s’applique pas aux rôles applicatifs ordinaires.
Un utilisateur ou un dépôt référencé par l’audit doit être archivé plutôt que
supprimé, afin de conserver l’identité de l’auteur et le contexte de l’action.
Le journal web `/administration/audit/` est réservé aux
super administrateurs de la plateforme. Les administrateurs d’un dépôt n’y ont
pas accès.

La RLS des tables métier n'empêche pas un superutilisateur PostgreSQL d'exécuter
des scripts dans pgAdmin. Avec un rôle SQL non-superutilisateur, définissez le
dépôt dans la transaction avant la requête :

```sql
BEGIN;
SELECT set_config('app.current_company_id', '<uuid-du-depot>', TRUE);
-- requêtes de maintenance contrôlées
COMMIT;
```

Le rôle PostgreSQL utilisé par le laboratoire Streamlit n’a aucun privilège sur
`audit_logs`. Le journal ne doit être exposé ni dans les repositories analytiques
ni dans l’API destinée aux dépôts.

Une politique de conservation devra être fixée avant la production commerciale,
par exemple 24 mois, avec archivage sécurisé. L’adresse IP et le user-agent sont
des données techniques potentiellement personnelles et doivent être mentionnés
dans la politique de confidentialité.

En production derrière un proxy de confiance, définissez
`AUDIT_TRUST_X_FORWARDED_FOR=true` pour enregistrer l’adresse transmise par le
proxy. Cette option doit rester à `false` lorsque l’application est directement
accessible, afin qu’un client ne puisse pas falsifier cet en-tête.
