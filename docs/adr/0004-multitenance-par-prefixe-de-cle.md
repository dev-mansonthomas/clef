# ADR 0004 — Multi-tenance par préfixe de clé, appliquée par l'application

**Statut :** accepté, en production, **incomplet** — **(reconstructed — verify)**
**Date de la décision :** 2026-03-13 (journée de migration vers Valkey)

## Contexte

Reconstruit depuis le code. CLEF est conçu pour plusieurs délégations
territoriales, mais une seule existe (`DT75`). Le mécanisme d'isolation est unique
et tient en une méthode :

```python
# app/services/valkey_service.py:54-64
def _key(self, *parts):
    return f"{self.dt}:{':'.join(parts)}"
```

Le code DT est le **premier segment de chaque clé**. Le `dt` provient de
`current_user.dt`, injecté par `valkey_dependencies.py`, lui-même dépendant de
`require_authenticated_user`.

Valkey n'impose rien : pas d'ACL par préfixe, pas de base séparée par tenant. Toute
l'isolation repose sur le fait que le code passe systématiquement par `_key()`.

## Décision

Isoler les tenants par convention de nommage de clé, appliquée par une méthode
unique et centralisée, sans mécanisme de contrainte côté datastore.

## Conséquences

**Assumées**
- Coût nul : une seule instance Valkey pour toutes les délégations.
- Convention simple, lisible, et facile à vérifier par revue.

**Subies — quatre brèches constatées**

1. **Deux caches ne portent aucun code DT** : `clef:calendar_ids:{nom}` et
   `clef:carnet_bord:sheet_id:{perimetre}:v{N}` vivent dans un espace de noms
   global. Un identifiant Calendar ou Sheet mis en cache est donc partagé entre
   toutes les délégations.
2. **Les clés iCal inversent l'ordre** : `ical:{dt}:all` place le DT en deuxième
   position. Fonctionnel, mais rompt la convention et casse tout raisonnement par
   préfixe (`SCAN MATCH "{dt}:*"` ne les trouve pas).
3. **Le `SCAN` de recherche de token traverse tous les tenants** :
   `app/routers/approbation.py:60` scanne `*:approbation:{token}` sur tout le
   keyspace, après avoir d'abord essayé un préfixe `"DT75"` **codé en dur**. Le DT
   n'étant pas déductible du token, l'isolation est structurellement contournée ici.
4. **Le paramètre de chemin `{dt}` n'est pas systématiquement recoupé** avec le DT
   de l'appelant. Plusieurs routers acceptent `{dt}` dans l'URL et le propagent ; si
   le contrôle croisé manque, un utilisateur authentifié d'une délégation peut
   viser les données d'une autre. Voir `docs/TODO.md`, sévérité élevée.

**Et une incohérence de fond** : côté frontend, **quatre services codent
`dt = 'DT75'` en dur** (`api-keys`, `stats`, `unite-locale`, `vehicle-import`).
L'application est donc **mono-délégation en pratique**, alors que le backend paie le
coût de conception du multi-tenant. La décision est prise mais pas terminée.

## Recommandation

Si le multi-DT doit devenir réel, la protection ne doit pas rester une convention :
un contrôle systématique `path.dt == current_user.dt` dans une dépendance FastAPI
unique serait vérifiable, alors qu'une convention de nommage ne l'est pas. Question
produit préalable : CLEF doit-il rester mono-DT ? Voir `docs/migration-status.md`.
