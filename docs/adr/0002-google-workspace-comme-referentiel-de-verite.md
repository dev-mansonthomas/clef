# ADR 0002 — Redis est la source de vérité applicative, Google Sheets est l'amont

> Note : les intitulés de Wave cités ci-dessous mentionnent « Valkey », nom du
> datastore de mars à août 2026. Ce sont des **citations** du tracker d'origine et
> sont conservées telles quelles. Le datastore est aujourd'hui Redis 8.10 —
> voir [ADR 0006](0006-redis-8-10-remplace-valkey.md).

**Statut :** accepté, en production, **migration inachevée** — rationale **confirmée**
par `debug/specs-intent.md` et par le propriétaire du projet le 2026-08-13
**Date :** conception initiale 2026-03-10 ; bascule en Wave 11, achevée Waves 15-16

> **Cet ADR a été réécrit le 2026-08-13.** Ma première version, reconstruite du code
> seul, affirmait que « Google Workspace reste le référentiel de vérité ». C'est
> **faux** en tant que description de l'intention. Les documents de reprise récupérés
> et le propriétaire du projet l'ont corrigé. Ce qui suit est la version exacte.

## Contexte

**Conception initiale (Waves 1-10).** Google Sheets était la source de vérité et
MemoryStore un simple cache. C'est écrit noir sur blanc dans les specs récupérées :
« Détermination UL d'un bénévole : consultation du référentiel bénévoles (Google
Sheets, **caché dans MemoryStore**) » et « Référentiel Bénévoles | Export SI
Croix-Rouge | **Cache MemoryStore (TTL 1 an)** ».

**Bascule (Wave 11 « Architecture Multi-Tenant & Valkey Primaire », achevée Waves
15-16).** L'hypothèse a été explicitement révisée : « Valkey 8 avec module JSON natif
comme **base de données primaire** (✅ migré Wave 15-16) ».

**Modèle cible, confirmé par le propriétaire :** Google Sheets reste la source de
vérité **hors** de CLEF (c'est l'export du SI Croix-Rouge, tenu par les équipes) ;
**dans** CLEF, Redis est la source de vérité. Le pont est un Apps Script qui appelle
l'API avec authentification par jeton, en synchronisation périodique.

Ce modèle est **effectivement en place** — et une exception a été oubliée :

| Donnée | Système de vérité | Preuve |
|---|---|---|
| Véhicules | Google Sheets | `sheets_real.py` lit `VEHICULES_SPREADSHEET_ID` ; sync Apps Script chaque minute |
| Bénévoles, rôles, UL | Google Sheets | `auth/service.py` résout le rôle à chaque requête via `sheets_service.get_benevole_by_email` |
| Documents, photos véhicule | Google Drive | `vehicle_document_service.py` crée une arborescence par véhicule |
| Carnet de bord | Google Sheets | `carnet_bord_service.py` ajoute une ligne dans un Sheet par périmètre |
| Notifications | Gmail | alertes CT/antipollution, demandes d'approbation |

## ⚠️ L'exception : l'authentification n'a jamais été migrée

Vérifié par lecture du code le 2026-08-13. Les bénévoles existent **en double** :

| Chemin | Source réelle | Preuve |
|---|---|---|
| Écriture par la sync Apps Script | **Redis** ✅ | `routers/sync.py:244` `redis_store.set_benevole(...)` |
| Lecture par l'app (bénévoles, réservations) | **Redis** ✅ | `routers/benevoles.py:70,74,167,169` ; `reservations_store.py:106,221` |
| **Résolution du rôle, à chaque requête** | **Google Sheets** ❌ | `auth/service.py:47` → `:104` `sheets_service.get_benevole_by_email` |
| Les 3 routes PII non authentifiées | **Google Sheets** ❌ | `main.py:112,201,213` |

La synchronisation fonctionne donc bien, comme prévu — mais **le contrôle d'accès ne
s'en sert pas.** `auth/service.py` et les routes héritées de `main.py` sont restées
sur le modèle pré-Wave-11.

Conséquences concrètes de cet oubli :

1. **Le contrôle d'accès dépend d'un tableur en direct.** Modifier une ligne d'un
   Sheet change les droits dans CLEF immédiatement, sans audit ni validation — alors
   que le modèle cible ferait passer ce changement par une synchronisation traçable.
2. **La latence d'authentification dépend de l'API Google Sheets**, sur le chemin
   critique de *chaque* requête.
3. **La sync est inutile pour ce qui compte le plus.** Le travail de Wave 11 n'a pas
   atteint le chemin le plus sensible.

**Action :** migrer `auth/service.py` pour lire les bénévoles depuis Redis
(`redis_store.get_benevole`), comme le fait déjà `routers/benevoles.py`. C'est le geste
qui termine Wave 11. Voir `docs/TODO.md`.

## Décision

Google Sheets reste la source de vérité **en amont** (export du SI Croix-Rouge,
tenu hors de CLEF). **Redis est la source de vérité applicative.** Le pont est un
Apps Script authentifié par jeton, en synchronisation périodique. Drive et Gmail
restent utilisés pour ce qu'ils sont : stockage de documents et envoi d'emails.

## Conséquences

**Assumées**
- Adoption facilitée : les équipes gardent leurs tableurs en amont.
- Pas de synchronisation bidirectionnelle à concevoir (explicitement hors périmètre
  dans les specs d'origine : « Synchronisation bi-directionnelle avec SI
  Croix-Rouge » figure dans les *Non-Goals*).
- Lectures applicatives rapides et locales, sans quota Google.

**Subies**
- **La migration est inachevée** — voir l'exception ci-dessus, qui annule une partie
  du bénéfice attendu.
- **Aucune table utilisateurs dans CLEF** : le rôle n'est pas stocké, il est recalculé
  à chaque requête.
- **Quatre APIs Google en dépendance** (Sheets, Drive, Gmail, Calendar), avec
  quotas et pannes non maîtrisés.
- **Deux familles de clients Google coexistent** : l'une par service account, l'autre
  par OAuth délégué du gestionnaire DT. Voir [ADR 0003](0003-session-sans-etat-token-google.md).
- Le développement exige des doubles complets : c'est l'origine de `USE_MOCKS`,
  voir [ADR 0006](0006-strategie-de-mocks-integrale.md).
- **Écart de configuration constaté** : la documentation et `.env.example` décrivent
  des variables `SHEETS_URL_{VEHICULES,BENEVOLES,RESPONSABLES}` alors que le code lit
  `{VEHICULES,BENEVOLES,RESPONSABLES}_SPREADSHEET_ID`. Suivre la documentation n'a
  donc **aucun effet**. Voir `docs/TODO.md`.
