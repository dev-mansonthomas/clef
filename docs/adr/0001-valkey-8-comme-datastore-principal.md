# ADR 0001 — Valkey 8 (bundle JSON) comme datastore principal

**Statut :** accepté, en production — **(reconstructed — verify)**
**Date de la décision :** entre le 2026-03-10 et le 2026-03-13 (observée dans l'historique)

## Contexte

Reconstruit depuis le code : le projet démarre le 2026-03-10 avec **Redis** utilisé
comme *cache* de référentiels (`app/cache/`). Le 2026-03-13, en une journée de 48
commits, Redis est remplacé par **Valkey 8** et promu **base de données
principale** : `ValkeyService` (aujourd'hui 1849 lignes) devient la couche d'accès
à toutes les entités du domaine. Aucune base relationnelle n'a jamais existé dans
le dépôt — aucun ORM, aucune migration de schéma, aucun `CREATE TABLE`.

Le choix porte spécifiquement sur l'image **`valkey/valkey-bundle:8`**, qui embarque
les modules **JSON** et **Search**, et non sur `valkey:8` nu. Les documents sont
manipulés via `JSON.SET` / `JSON.GET`.

Le *pourquoi* n'est consigné nulle part. `(inferred — verify)` Hypothèses
plausibles, par ordre de vraisemblance décroissante :
1. Les données arrivent déjà sous forme de documents depuis Google Sheets, sans
   besoin de jointures — un magasin de documents suffit.
2. GCP propose **Memorystore for Valkey** en service managé, donc pas d'opération
   de base à assurer.
3. Le cache Redis existait déjà : promouvoir l'existant coûtait moins que d'ajouter
   un second système.

## Décision

Utiliser Valkey 8 avec le module JSON comme unique magasin de données persistant.
Aucune base relationnelle. Aucun ORM. Les modèles Pydantic tiennent le rôle de
schéma, validé côté application.

## Conséquences

**Assumées**
- Pas de migration de schéma à gérer ; ajouter un champ Pydantic suffit.
- Latence très faible en lecture, adaptée aux écrans de liste.
- Service managé sur GCP.

**Subies**
- **Le module JSON est une dépendance dure.** Sans lui, le code échoue sur
  `unknown command 'json.set'`. C'est ce qui a imposé l'extra `fakeredis[json]`
  dans `requirements.txt` : sans lui, 56 tests échouaient.
- **Aucune intégrité référentielle.** Les index (`:index`, `:by_ul:`, `:by_date:`)
  sont maintenus **à la main** dans `ValkeyService`. Une écriture partielle peut
  laisser un index désynchronisé ; rien ne le détecte.
- **Aucune transaction multi-clés.** Créer un dossier de réparation écrit un
  compteur, un document et un index sans atomicité.
- **Pas d'agrégation serveur.** `stats_service.py` recharge les documents et calcule
  en Python — coût linéaire en nombre d'entités.
- **L'isolation multi-tenant devient une convention de nommage** plutôt qu'une
  contrainte du moteur. Voir [ADR 0004](0004-multitenance-par-prefixe-de-cle.md).
- Le module **Search** est présent dans l'image mais **aucun index `FT.CREATE`
  n'existe dans le code** : capacité payée et non utilisée. `(inferred — verify)`
  probablement anticipée puis jamais mise en œuvre.

## Alternatives non retenues (et non documentées)

Aucune trace d'évaluation de PostgreSQL, Firestore ou BigQuery. `(inferred — verify)`

## Note d'instabilité

Le mode de stockage a **oscillé deux fois** entre l'API JSON native de Valkey et
un stockage de chaînes JSON (`0067e99` ↔ `2c02fec` ↔ `99b9762`, les 14 et 15 mars)
avant de se stabiliser. La raison de ces allers-retours n'est consignée nulle part
— c'est un signal qu'un piège existe dans ce domaine et qu'il n'est pas documenté.
