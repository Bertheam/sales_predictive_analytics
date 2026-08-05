# Conventions de l’interface Django

Objectif : conserver une interface cohérente, responsive et facile à maintenir,
sans construire un framework interne.

## Composants disponibles

Les composants sont de simples inclusions Django dans
`backend/templates/components/` :

- `button.html` : boutons et liens d’action, avec variantes `primary`, `dark`,
  `ghost` et `danger` ;
- `page_header.html` : titre, contexte, retour et action principale ;
- `form_field.html` : label, champ, aide et erreurs de validation ;
- `empty_state.html` : absence de résultat ou de donnée.
- `sortable_header.html` : en-tête de colonne triable, avec direction visible et
  attribut `aria-sort` ;
- `pagination.html` : navigation paginée qui conserve les filtres et le tri.

Une table métier reste dans son template tant que ses colonnes et comportements
sont propres à une seule page. Elle ne devient un composant que lorsqu’un second
usage réel apparaît. Cette règle évite les composants génériques difficiles à
comprendre.

## Dépendances frontend

- SweetAlert2 affiche les messages flash Django et les confirmations sensibles.
- Select2 améliore uniquement les listes longues marquées avec
  `data-enhanced-select`.
- Tailwind CSS est le système principal pour les nouveaux layouts, composants
  et règles responsive. Les fichiers historiques `app.css` et `operations.css`
  restent temporairement chargés pendant la migration progressive des vues.

Tailwind est compilé avant le démarrage de l’application :

```bash
npm install
npm run css:build
```

Le navigateur charge uniquement le fichier statique minifié généré ; Tailwind
n’ajoute donc aucun JavaScript d’exécution côté client.

Les versions de Select2 et SweetAlert2 sont épinglées dans `base_app.html`. Si le CDN est
indisponible, les notifications redeviennent des messages HTML, les
confirmations utilisent `window.confirm` et les listes restent des `select`
natifs.

## Listes et filtres

Chaque filtre possède un `label` visible relié au champ par `for` et `id`. Le
placeholder donne un exemple, mais ne remplace jamais le label. Les filtres se
replient verticalement sur mobile et les tables restent défilables
horizontalement.

Les listes métier utilisent `operations.listing.sort_and_paginate`. Chaque vue
déclare explicitement ses colonnes triables dans une liste blanche ; une valeur
transmise dans l’URL ne doit jamais devenir directement un fragment SQL. La
pagination affiche 25 lignes par défaut et conserve la recherche, les dates,
les filtres et la direction du tri.

Les codes techniques ne sont jamais affichés tels quels lorsqu’un libellé métier
existe. Le filtre `status_label` traduit notamment les statuts de paiement et de
sévérité (`PAID` → `Payée`, `CRITICAL` → `Critique`).

## Responsive

Les vues sont conçues en mobile-first avec les variantes Tailwind `md:` et `lg:`.
La navigation latérale devient une barre inférieure mobile. Toute nouvelle page
doit être utilisable à 360 px sans action principale inaccessible.

## JavaScript

Le fichier `backend/static/js/app.js` contient seulement les comportements
transversaux : toasts, confirmations, Select2 et fermeture du menu utilisateur.
Les règles métier restent côté Django. Aucune validation importante ne doit
dépendre du JavaScript.
