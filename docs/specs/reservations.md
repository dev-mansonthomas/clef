# Spec — Réservations de véhicules

Reconstruit depuis le code (aucune doc préexistante trouvée). Toute affirmation non
directement lisible dans le code est taguée `(inferred — verify)`.

## Objet

Permettre à un utilisateur authentifié de réserver un véhicule (chauffeur + créneau +
mission) au sein d'une DT (Délégation Territoriale), avec détection de chevauchement,
et d'exposer ces réservations sous forme de flux iCal pour import dans un calendrier
externe.

Il existe **deux implémentations parallèles** (voir `## Écarts connus`) :
- legacy, adossée à Google Calendar : `backend/app/routers/reservations.py`,
  modèle `ReservationCreate`/`ReservationResponse` (`backend/app/models/reservation.py:8-27`).
- courante, adossée à Redis : `backend/app/routers/reservations_store.py`, modèle
  `RedisReservationCreate`/`RedisReservation` (`backend/app/models/reservation.py:31-69`).

Ce spec documente principalement l'implémentation Redis (source de vérité actuelle),
plus le flux iCal legacy qui reste actif.

## Modèle de données

### `RedisReservation` (`backend/app/models/reservation.py:31-49`)
Champs : `id` (UUID), `vehicule_immat`, `chauffeur_nivol`, `chauffeur_nom`, `mission`,
`debut`/`fin` (datetime), `lieu_depart` (opt.), `commentaire` (opt.), `created_by`
(email), `created_at`, `google_event_id`/`google_event_link` (opt., sync Google Calendar
best-effort — `backend/app/services/redis_service.py:799-833`).

### Clés Redis (préfixe DT via `_key`, `backend/app/services/redis_service.py:54-64` →
`f"{dt}:{':'.join(parts)}"`)
- `{dt}:reservations:{id}` — document JSON de la réservation (`redis_service.py:836-837`).
- `{dt}:reservations:index` — SET de tous les IDs de réservation (`redis_service.py:840`).
- `{dt}:reservations:by_date:{YYYY-MM-DD}` — SET d'IDs, un membre par jour couvert par
  `[debut.date(), fin.date()]` inclus (fan-out un ajout par jour, `redis_service.py:842-848`).
- `{dt}:reservations:by_vehicle:{immat}` — SET d'IDs pour un véhicule (`redis_service.py:851-852`).

Le fan-out `by_date` est linéaire au nombre de jours couverts — une réservation de N
jours écrit N clés `sadd` (`redis_service.py:845-848`). `(inferred — verify)` : pas de
borne sur N, un `fin` très éloigné de `debut` peut générer un grand nombre d'écritures.

## Entrées / sorties

Préfixe Redis : `/api/calendar/{dt}/reservations` (`reservations_store.py:19-22`).
Toutes les routes ci-dessous imposent `require_authenticated_user`
(`backend/app/auth/dependencies.py:64`), sauf le flux iCal.

| Méthode | Route | Auth | Description |
|---|---|---|---|
| GET | `/api/calendar/{dt}/reservations` | utilisateur authentifié | Liste filtrable par `from`, `to`, `vehicule_immat` (`reservations_store.py:25-64`) |
| POST | `/api/calendar/{dt}/reservations` | utilisateur authentifié | Création (`reservations_store.py:67-130`) |
| GET | `/api/calendar/{dt}/reservations/{id}` | utilisateur authentifié | Détail (`reservations_store.py:133-161`) |
| PUT | `/api/calendar/{dt}/reservations/{id}` | créateur OU rôle `Gestionnaire DT` | Modification (`reservations_store.py:164-250`) |
| DELETE | `/api/calendar/{dt}/reservations/{id}` | créateur OU rôle `Gestionnaire DT` | Annulation (`reservations_store.py:253-300`) |
| POST | `/api/reservations` (legacy) | utilisateur authentifié + accès véhicule | Création via Google Calendar (`reservations.py:25-110`) |
| GET | `/api/calendar/{dt}/reservations.ics` | **aucune** | Flux iCal de toutes les réservations (`ical.py:101-159`) |
| GET | `/api/calendar/{dt}/vehicle/{immat}.ics` | **aucune** | Flux iCal filtré véhicule (`ical.py:162-239`) |

## Règles métier

1. `fin` doit être strictement postérieur à `debut`, sinon `400` — vérifié à la création
   (`reservations_store.py:91-95`) et à la modification (`reservations_store.py:206-210`).
2. Le véhicule (`vehicule_immat`) doit exister (`redis_store.get_vehicle`), sinon `404`
   (`reservations_store.py:97-103`, `212-218`).
3. Le chauffeur (`chauffeur_nivol`) doit exister (`redis_store.get_benevole`), sinon `404`
   (`reservations_store.py:105-111`, `220-226`).
4. **Chevauchement** : deux réservations chevauchent ssi `debut < autre.fin AND fin >
   autre.debut` (`redis_service.py:1172`) — comparaison stricte, donc deux réservations
   *contigües* (`fin1 == debut2`) ne se chevauchent pas.
5. Le chevauchement est vérifié **uniquement pour le même véhicule** — deux réservations
   simultanées sur des véhicules différents sont autorisées
   (`test_reservations_store.py::TestReservationOverlapValidation::test_overlap_different_vehicles`).
6. À la modification, la réservation courante est exclue de la vérification de
   chevauchement via `exclude_id` (`redis_service.py:961-966`, `1167-1168`).
7. Modification/suppression : autorisées seulement si `created_by == current_user.email`
   OU `current_user.role == "Gestionnaire DT"` ; sinon `403`
   (`reservations_store.py:199-203`, `282-286`). Comparaison de rôle en chaîne exacte —
   `(inferred — verify)` : pas de vérification que l'utilisateur appartient à la même DT
   que la réservation (`dt` du path n'est pas comparé à un champ DT de la réservation).
8. La création/modification tente une synchronisation Google Calendar best-effort si une
   `calendar_id` est configurée pour la DT ; un échec de sync n'empêche pas la réservation
   d'être créée/modifiée (`redis_service.py:808-833`, `994-1034`).

## Flux iCal

- Deux endpoints publics (`ical.py:101`, `162`) génèrent un `.ics` à partir des
  événements **Google Calendar** (`calendar_service.get_events`), pas de la source Redis
  `(inferred — verify)` : incohérence probable avec `## Écarts connus` point 1 — le flux
  iCal ne reflète donc que les réservations legacy/synchronisées Calendar, pas forcément
  toutes les réservations Redis natives.
- Cache Redis/Redis clé `ical:{dt}:all` ou `ical:{dt}:vehicle:{immat_normalisé}`, TTL 60s
  (`ical.py:117-129`, `183-196`, `225`). En cas d'échec cache (lecture/écriture), le calcul
  se fait quand même, sans échec de la requête (`ical.py:118-132`, `143-147`).
  `Cache-Control: public, max-age=60` renvoyé au client (`ical.py:128`, `154`).
  `immat` est normalisé (espaces/tirets retirés, upper) avant clé de cache et filtrage
  (`ical.py:180`, `211-212`).
- Filtrage véhicule fait par extraction du préfixe `summary` (format
  `{indicatif} - {chauffeur} - {mission}`, `extract_indicatif_from_summary`,
  `ical.py:35-43`) OU sous-chaîne brute dans `summary` (`ical.py:215`) —
  double critère, risque de faux positifs si l'immat apparaît ailleurs dans le texte
  `(inferred — verify)`.
- UID iCal : `f"{dt}-res-{event_id}@clef.croix-rouge.fr"` (`ical.py:68`).

## Cas limites

- Réservation contigüe (`fin1 == debut2`) : autorisée (comparaison stricte, règle 4).
- Réservation multi-jours : indexée sous une clé `by_date` par jour couvert ; suppression
  symétrique dans `delete_reservation` (`redis_service.py:1126-1133`) et
  `update_reservation` (`redis_service.py:1050-1067`).
- `list_reservations` sans filtre de date utilise des bornes par défaut
  `2020-01-01`–`2030-12-31` lors d'un filtre partiel (`redis_service.py:900-905`) —
  `(inferred — verify)` : réservation hors de cette plage non indexée correctement par date
  (mais reste dans l'index global).
- Sync Google Calendar : configuration absente ou `redis.json()` non supporté (ex.
  fakeredis dans les tests) → capturé silencieusement, pas de sync
  (`redis_service.py:801-806`, `986-992`, `1094-1099`).
- `check_reservation_overlap` recharge toutes les réservations du véhicule via
  `list_reservations` puis filtre en mémoire (`redis_service.py:1162-1175`) —
  pas de requête indexée par plage ; coût O(n) réservations du véhicule à chaque
  création/modification `(inferred — verify, perf)`.

## Critères d'acceptation

| # | Critère | Test |
|---|---|---|
| 1 | Création basique | `test_reservations_store.py::TestReservationCRUD::test_create_reservation` |
| 2 | Lecture par ID | `test_reservations_store.py::TestReservationCRUD::test_get_reservation` |
| 3 | Lecture ID inexistant → `None` | `test_reservations_store.py::TestReservationCRUD::test_get_nonexistent_reservation` |
| 4 | Liste triée par `debut` | `test_reservations_store.py::TestReservationCRUD::test_list_reservations` |
| 5 | Filtre par plage de dates | `test_reservations_store.py::TestReservationCRUD::test_list_reservations_by_date_range` |
| 6 | Filtre par véhicule | `test_reservations_store.py::TestReservationCRUD::test_list_reservations_by_vehicle` |
| 7 | Modification | `test_reservations_store.py::TestReservationCRUD::test_update_reservation` |
| 8 | Suppression + nettoyage index | `test_reservations_store.py::TestReservationCRUD::test_delete_reservation` |
| 9 | Pas de chevauchement si créneaux disjoints | `test_reservations_store.py::TestReservationOverlapValidation::test_no_overlap_different_times` |
| 10 | Rejet si chevauchement total | `test_reservations_store.py::TestReservationOverlapValidation::test_overlap_same_time` |
| 11 | Rejet si chevauchement partiel (début) | `test_reservations_store.py::TestReservationOverlapValidation::test_overlap_partial_start` |
| 12 | Rejet si chevauchement partiel (fin) | `test_reservations_store.py::TestReservationOverlapValidation::test_overlap_partial_end` |
| 13 | Modif n'entre pas en conflit avec soi-même | `test_reservations_store.py::TestReservationOverlapValidation::test_update_no_overlap_with_self` |
| 14 | Chevauchement ignoré si véhicules différents | `test_reservations_store.py::TestReservationOverlapValidation::test_overlap_different_vehicles` |
| 15 | Permissions update/delete (créateur/Gestionnaire DT) | **NON COUVERT** (aucun test HTTP sur `reservations_store.py:199-203`/`282-286`) |
| 16 | Génération iCal correcte (UID, champs) | `test_ical.py::test_create_ical_from_events` |
| 17 | Endpoint iCal global (+ cache miss) | `test_ical.py::test_get_reservations_ical_endpoint` |
| 18 | Endpoint iCal filtré véhicule | `test_ical.py::test_get_vehicle_ical_endpoint` |
| 19 | Extraction indicatif depuis `summary` | `test_ical.py::test_extract_indicatif_from_summary` |
| 20 | Cache hit iCal (TTL 60s) | **NON COUVERT** (tests forcent `cache.get` → `None`) |
| 21 | 404 véhicule/chauffeur inconnu à la création/modif | **NON COUVERT** |

## Écarts connus

1. **Deux modèles de réservation coexistent** : le legacy `Reservation` lié à Google
   Calendar (`backend/app/models/reservation.py:8-27`) et le plus récent
   `RedisReservation` (`reservation.py:31-69`). Le frontend ne possède une interface
   TypeScript que pour le **legacy** ; la forme Redis n'en a aucune. Migration
   inachevée : `f206ac9` (2026-03-15) a remplacé l'intégration Google Calendar par des
   réservations natives Redis sans retirer l'ancien modèle.
2. `GET /api/calendar/{dt}/reservations.ics` et
   `GET /api/calendar/{dt}/vehicle/{immat}.ics` sont servis **sans aucune
   authentification** (`backend/app/routers/ical.py`) : quiconque devine un code DT
   obtient les données de réservation. Sévérité élevée.
3. `frontend/projects/admin/src/app/services/reservation.service.ts:11` code son URL en
   dur au lieu d'utiliser `environment.apiUrl`.
