# Spec : Carnet de Bord (prise / retour de véhicule)

Reconstruite depuis le code par lecture directe des fichiers listés ci-dessous. Toute affirmation non
directement lisible dans le code est taguée `(inferred — verify)`.

## Objet

Permettre à un bénévole, via la PWA `form`, d'enregistrer la **prise** puis le **retour** d'un véhicule :
kilométrage, niveau de carburant, état général, jusqu'à 5 photos, signature manuscrite. Backend
`app/routers/carnet_bord.py` (`file:routers/carnet_bord.py:17-20`, préfixe `/api/carnet-de-bord`).

## Modèle de données

Pydantic (`backend/app/models/carnet_bord.py`) :

- `PriseVehicule` (`:7-17`) : `vehicule_id`, `benevole_email`, `benevole_nom`, `benevole_prenom`,
  `kilometrage` (`ge=0`), `niveau_carburant`, `etat_general`, `observations?`, `timestamp?`. **Aucun
  champ `signature` ni `commentaires`.**
- `RetourVehicule` (`:35-46`) : idem + `problemes_signales?`. Champs identiques (snake_case) à ceux
  envoyés par `retour-form.component.ts:148-159`.
- `CarnetBordResponse` (`:65-71`) : `success`, `message`, `spreadsheet_id` (toujours `None`, voir
  Écarts), `perimetre`.
- `DernierePrise` (`:83-92`) : reflet de la dernière prise pour un véhicule.

Persistance réelle : `ValkeyService` (via `get_valkey_service`), pas Google Sheets. Le service
`backend/app/services/carnet_bord_service.py` (Google Sheets `append_prise`/`append_retour`, Drive
`_find_existing_sheet`/`_create_new_sheet`, cache Redis du `spreadsheet_id`) **n'est importé nulle part
dans `routers/carnet_bord.py`** — les commentaires `# No longer using Google Sheets` (`routers/carnet_bord.py:78,148`)
et `spreadsheet_id=None` le confirment. `CarnetBordService` est du code mort par rapport au flux HTTP actuel
`(inferred — verify: rechercher d'autres appelants dans le repo)`.

## Parcours utilisateur

**Prise** (`prise-form.component.ts`) :
1. Formulaire réactif `kmDepart`, `niveauCarburant`, `etatGeneral` (slider 1–5), `commentaires` (`:79-84`).
2. Signature obligatoire via `signature_pad` (`SignaturePad`, `:87-107`, `:161-164`).
3. Jusqu'à 5 photos, aperçu par `FileReader` (`:53`, `:113-152`).
4. Soumission : `carnetBordService.submitPrise(request)` puis, si photos, `uploadPhotosPrise` (`:183-218`).

**Retour** (`retour-form.component.ts`) :
1. Chargement de la dernière prise via `getRecentPrise(immat)` pour calculer `kmParcourus` (`:52-60`, `:107-125`).
2. Formulaire `kmArrivee`, `niveauCarburant`, `etatGeneral`, `problemeASignaler` + `descriptionProbleme`
   conditionnel (`Validators.required, minLength(10)` si coché, `:85-104`).
3. Pas de signature ni de capture photo envoyées dans la requête (`selectedPhotos` collectées, `:127-137`,
   mais jamais uploadées dans `onSubmit`) `(inferred — verify)`.
4. Soumission : `carnetBordService.submitRetour(request)` (`:139-185`).

## Entrées / sorties

| Méthode | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| POST | `/api/carnet-de-bord/prise` | `require_authenticated_user` (`routers/carnet_bord.py:26`) | `PriseVehicule` | `CarnetBordResponse` (201) | 404 véhicule inconnu (`:48-52`), 400 déjà pris (`:56-60`), 500 (`:81-85`) |
| POST | `/api/carnet-de-bord/retour` | `require_authenticated_user` (`:91`) | `RetourVehicule` | `CarnetBordResponse` (201) | 404 (`:113-117`), 400 non pris (`:121-125`), 500 (`:151-155`) |
| GET | `/api/carnet-de-bord/{vehicule_id}/derniere-prise` | `require_authenticated_user` (`:161`) | path param | `DernierePrise \| null` (200) | 404 véhicule inconnu (`:181-185`) |

Frontend : `CarnetBordService` (`frontend/.../services/carnet-bord.service.ts:23-41`) appelle ces 3 routes,
plus `POST /api/upload/photos` pour les photos (`:46-77`, backend non lu — hors périmètre de cette spec).

## Règles métier

1. Une prise ne peut être enregistrée que si le véhicule existe (`get_vehicle_by_nom_synthetique`) —
   sinon 404 (`routers/carnet_bord.py:46-52`).
2. Une prise est refusée (400) si une prise est déjà active pour ce véhicule (`get_derniere_prise` non
   vide) (`:54-60`).
3. Un retour ne peut être enregistré que si le véhicule existe (`:111-117`) et qu'une prise est active
   (`:119-125`) — sinon 400.
4. `kilometrage` doit être `>= 0` (validation Pydantic `Field(..., ge=0)`, `models/carnet_bord.py:13,41`).
5. Le retour calcule `km_parcourus = retour.kilometrage - derniere_prise.kilometrage` (`:142-143`) et
   l'inclut dans le message de succès — **aucune vérification que ce delta soit positif** (voir Cas limites).
6. Un retour réussi efface la dernière prise active (`enregistrer_retour` côté Valkey — comportement
   déduit des tests, `test_enregistrer_retour_clears_derniere_prise`).
7. `perimetre` retourné = `current_user.dt` de l'utilisateur authentifié (`:79`, `:149`), **pas** le
   périmètre du véhicule lui-même.

## Mode hors ligne

`OfflineSyncService` (`frontend/.../services/offline-sync.service.ts`) : file `localStorage` sous la clé
`offline-form-queue` (`:14`), `queueSubmission()` empile `{data, timestamp, id}` (`:48-56`), `online$`
déclenche `syncQueuedSubmissions()` au retour réseau (`:19-31`, `:76-99`), qui rejoue chaque entrée via
`submitToServer` — **POST générique `/api/submissions`** (`:107-111`), pas `/api/carnet-de-bord/prise|retour`.

**Constat vérifié** : ni `prise-form.component.ts` ni `retour-form.component.ts` n'importent ou n'appellent
`OfflineSyncService` — `onSubmit()` appelle directement `carnetBordService.submitPrise/submitRetour` sans
détection d'état hors ligne ni fallback vers la file. Le mécanisme de file d'attente existe mais **n'est
pas branché** sur le carnet de bord.

## Cas limites

- Retour avec `kilometrage` < km de la prise : accepté, `km_parcourus` négatif affiché sans blocage
  (`routers/carnet_bord.py:142-143`, pas de règle métier contraire).
- Limite de 5 photos appliquée uniquement côté client (`prise-form.component.ts:53,119-126`) — aucune
  validation équivalente vue côté backend dans les fichiers lus.
- Échec de l'upload photo après une prise réussie : le formulaire est quand même considéré validé,
  message d'avertissement puis navigation (`prise-form.component.ts:208-217`).
- Signature vide bloquée côté client (`signaturePad.isEmpty()`, `:161-164`) — mais le champ `signature`
  n'existe pas dans `PriseVehicule` : **il n'y a nulle part où le tracé serait persisté côté backend**
  d'après le modèle lu.
- `kilometrage` négatif rejeté en 422 (`test_prise_validation_negative_kilometrage`).

## Critères d'acceptation

| Critère | Test |
|---|---|
| Prise enregistrée avec succès, perimetre = DT | `test_carnet_de_bord.py::test_enregistrer_prise_success` |
| Prise refusée si véhicule inconnu | `::test_enregistrer_prise_vehicule_not_found` |
| Prise refusée si véhicule déjà pris | `::test_enregistrer_prise_vehicule_deja_pris` |
| Retour enregistré, km parcourus dans le message | `::test_enregistrer_retour_success` |
| Retour refusé si véhicule inconnu | `::test_enregistrer_retour_vehicule_not_found` |
| Retour refusé si véhicule non pris | `::test_enregistrer_retour_vehicule_non_pris` |
| Dernière prise : 404 si véhicule inconnu | `::test_get_derniere_prise_vehicule_not_found` |
| Dernière prise : null si aucune donnée | `::test_get_derniere_prise_no_data` |
| Dernière prise : renvoyée si existante | `::test_get_derniere_prise_with_data` |
| Kilométrage négatif rejeté (422) | `::test_prise_validation_negative_kilometrage` |
| Retour efface la dernière prise (Valkey) | `::test_enregistrer_retour_clears_derniere_prise` |
| Historique carnet (prise + retour, plus récent d'abord) | `::test_get_historique_carnet` |
| Soumission formulaire prise (UI, e2e) | `frontend/e2e/form-prise-submission.spec.ts` |
| Soumission formulaire retour (UI) | **NON COUVERT** |
| Upload et association des photos (prise/retour) | **NON COUVERT** |
| Persistance de la signature manuscrite | **NON COUVERT** (champ absent du modèle backend) |
| Rejeu de la file hors ligne vers le carnet de bord | **NON COUVERT** (service non branché) |
| Cohérence des noms de champs prise (camelCase) ↔ modèle backend (snake_case) | **NON COUVERT** |

## Écarts connus

1. **Identité bénévole factice codée en dur** au lieu de l'utilisateur authentifié :
   `prise-form.component.ts:178-179` (`'user@example.com'`, `'User Name'`) et
   `retour-form.component.ts:147-152` (`'user@croix-rouge.fr'`, `'Nom'`, `'Prénom'`). Impact direct : le
   carnet ne permet pas de savoir qui a réellement pris/rendu le véhicule.
2. **Correction — le retour EST couvert côté backend.** Quatre tests existent :
   `test_carnet_de_bord.py::test_enregistrer_retour_success`, `_vehicule_not_found`,
   `_vehicule_non_pris`, `_clears_derniere_prise`. Ce qui manque réellement : tout
   test frontend ou e2e du formulaire de retour. Seule la prise a un e2e
   (`frontend/e2e/form-prise-submission.spec.ts`), et il **mocke le backend** —
   c'est précisément pourquoi il ne détecte pas l'écart de contrat du point 4.
3. `carnet-bord.service.ts:16` code son URL d'API en dur (`/api/carnet-de-bord`) au lieu d'utiliser
   `environment.apiUrl`.
4. 🔴 **VÉRIFIÉ — la soumission de prise est cassée.** L'hypothèse d'un intercepteur
   de conversion de casse est **écartée par lecture** : le seul intercepteur du
   projet (`frontend/projects/form/src/app/core/interceptors/auth.interceptor.ts`)
   ne fait que poser `withCredentials: true`, et `carnet-bord.service.ts:24` poste
   l'objet **tel quel**. Or `prise-form.component.ts:170-180` construit des clés
   camelCase (`nomSynthetique`, `kmDepart`, `niveauCarburant`, `etatGeneral`,
   `commentaires`, `signature`, `emailBenevole`, `nomBenevole`) alors que
   `PriseVehicule` exige `vehicule_id`, `kilometrage`, `niveau_carburant`,
   `etat_general`, `benevole_email`, `benevole_nom`, `benevole_prenom` — **tous
   requis, aucun fourni**. Toute prise échoue donc en **422**. Le formulaire de
   retour, lui, envoie bien les clés snake_case (`retour-form.component.ts:148-159`)
   et fonctionne. Sévérité **critique** : la prise de véhicule est la fonction
   première de l'app `form`.
5. **VÉRIFIÉ — `CarnetBordService` est du code mort.** Recherche repo-wide :
   `grep -rn 'CarnetBordService' backend/app/` ne retourne que sa propre définition
   (`services/carnet_bord_service.py:13`). Le router écrit explicitement
   `spreadsheet_id=None,  # No longer using Google Sheets`
   (`routers/carnet_bord.py:78,148`). Le stockage est **Valkey uniquement** ; le
   chemin Google Sheets par périmètre a été abandonné sans que le service soit retiré.
6. **VÉRIFIÉ — le mode hors ligne n'est pas branché.**
   `grep -rn 'OfflineSyncService' frontend/projects/form/src/app` ne retourne que sa
   propre définition (`services/offline-sync.service.ts:12`). Aucun des deux
   formulaires ne l'appelle, et il cible `/api/submissions`, endpoint qui n'existe
   pas dans le backend. La promesse « mode hors ligne » n'est donc pas tenue.
7. Le champ `signature` capturé par `signature_pad` n'existe dans **aucun** modèle
   backend : la signature manuscrite n'est jamais persistée, même si le formulaire
   refuse de se soumettre sans elle (`prise-form.component.ts:161-164`).
