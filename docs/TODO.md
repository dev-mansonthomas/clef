# TODO — registre des constats

> Établi le 2026-08-13 lors de la reconstruction documentaire. Chaque entrée est
> soit **vérifiée par exécution ou lecture** (citée), soit marquée
> `(inferred — verify)`. **Rien n'a été corrigé** : ce document ne fait que
> constater. Les deux seules corrections appliquées ce jour l'ont été avant cette
> revue et sont committées (`97f5d11`, `4b4d0a0`).
>
> Sévérités : 🔴 critique · 🟠 haute · 🟡 moyenne · ⚪ faible

## 🔴 Critique

### ~~C1~~ — ✅ **RÉSOLU le 2026-08-20** — Données personnelles de bénévoles exposées sans authentification

`backend/app/main.py` ne contient **aucun `Depends`** (vérifié : `grep -c Depends
app/main.py` → `0`) et l'app n'a pas de dépendance globale. Trois routes y exposent
le référentiel :

```
main.py:197  @app.get("/api/benevoles")          async def get_benevoles():
main.py:209  @app.get("/api/benevoles/{email}")  async def get_benevole(email):
main.py:~227 @app.get("/api/responsables")       async def get_responsables():
```

**Vérifié par requête réelle** sur une instance locale :

```
GET /api/benevoles      → HTTP 200, liste de 6 bénévoles
champs exposés : ['dt', 'email', 'nom', 'prenom', 'role', 'statut', 'ul']
GET /api/responsables   → HTTP 200
```

En mode mock les données sont fictives ; **en production ce sont les nom, prénom,
email et unité locale de bénévoles de la Croix-Rouge**. Enjeu RGPD direct.
`GET /api/alerts/status` (`routers/alerts.py:48`) est également non authentifié et
divulgue `service_account_email`. ✅ **Supprimée le 2026-08-28** — voir plus bas.

**Action :** déplacer ces routes dans un router avec `require_authenticated_user`,
ou les supprimer si elles ne servaient qu'au débogage.

> ✅ **Fait, et les deux à la fois.**
>
> - `/api/benevoles` est **conservée** : les formulaires de réservation des deux
>   applications s'en servent pour leur sélecteur de chauffeur
>   (`form/.../reservation-form.component.ts:113`,
>   `admin/.../reservation-form.component.ts:83`). Elle est désormais servie par
>   `routers/benevoles.directory_router` : `require_authenticated_user`, périmètre pris
>   sur `current_user.dt` — **jamais** sur un paramètre d'URL, ce qui la met hors
>   d'atteinte de la classe C3 — et lecture dans Redis, plus dans Sheets.
>   Chemin et forme de réponse inchangés : aucune modification frontend.
> - `/api/benevoles/{email}` et `/api/responsables` sont **supprimées** : aucun
>   appelant, ni frontend ni Apps Script. La surface la plus sûre est celle qui
>   n'existe pas.
>
> Politique d'accès arbitrée par le propriétaire : **tout utilisateur authentifié de la
> délégation**, email inclus. Restreindre aux gestionnaires casserait le parcours de
> réservation du bénévole terrain.
>
> Vérifié en exécution sur la stack locale :
> ```
> GET /api/benevoles           → 401     (sans cookie)
> GET /api/benevoles/{email}   → 404
> GET /api/responsables        → 404
> ```
> `GET /api/alerts/status` était restée **non authentifiée**, hors périmètre de ce
> correctif. ✅ **Supprimée le 2026-08-28**, et supprimée plutôt que gardée :
>
> - aucun appelant — ni `admin`, ni `form`, ni e2e, ni les Apps Script ;
> - `"enabled": True` était **codé en dur** alors que le job dépend de
>   `SCHEDULER_ENABLED` : la route répondait « activé » scheduler éteint, donc elle
>   mentait précisément quand on l'interrogeait ;
> - elle ne disait rien de ce qu'on voudrait savoir : dernière et prochaine exécution,
>   nombre d'alertes envoyées, erreurs ;
> - ses deux seules valeurs exactes (`alert_delay_days`, `use_mocks`) sont désormais
>   servies sous guard par `GET /admin/super/environnement` ;
> - et la fonctionnalité qu'elle décrivait **ne fonctionne pas en production** :
>   `alert_service.py:100` lit le référentiel dans Sheets avec le service account —
>   c'est le constat N13.
>
> `tests/test_probe_publique.py` porte deux gardes : le 404 de la route, et une
> vérification que **toute** route du router des alertes remonte à un `require_*`.
> Le second est une garde de router, pas de route : `POST /trigger` était gardée et
> `GET /status` non, à quinze lignes d'écart, et cela ne se voyait pas à la relecture.
>
> ⚠️ Si superviser ce job redevient un besoin — il est légitime, c'est une tâche
> silencieuse — la route à écrire lit l'état RÉEL du scheduler (`job.next_run_time`)
> sous `require_dt_manager`. C'est une petite fonctionnalité, pas un correctif.

### C4 — 🔴 `/auth/callback-dt` acceptait l'identité d'un paramètre d'URL non signé

> ✅ **Correctif écrit et vérifié** le 2026-08-29 — commit `fix(auth): l'identité du
> consentement DT vient de Google, plus d'un paramètre d'URL`, branche
> `hotfix/callback-dt-identite`, à merger **avant** la tranche 3. 14 tests nouveaux, et
> chaque garde éprouvée par mutation. Ce qui suit décrit l'état d'origine, conservé pour
> mémoire.

Découvert le 2026-08-29 en écrivant la spec de la tranche 3, sur lecture de
`app/auth/routes.py:318-380`. **Déployé en dev.**

La route **n'a aucun guard** — `code` et `state` en paramètres de requête, pas de
`Depends` — et `state`, que `app/auth/google_oauth.py:45` documente pourtant comme
« State parameter for CSRF protection », est utilisé comme **identité** :

```python
state: str = Query(..., description="DT manager email from state")
...
dt_id = "DT75"  # Default          ← ligne 351, en dur
success = await dt_token_service.store_tokens(dt_id=dt_id, email=state, ...)
```

**Enchaînement.** Le `client_id` est public — `01-gcp-deploy.sh` l'imprime, et c'est
normal — et le `redirect_uri` (`https://dev.clef.paquerette.com/auth/callback-dt`) est
déclaré en console. Un tiers construit lui-même l'URL de consentement Google, consent
**avec son propre compte**, et Google le redirige vers
`…/auth/callback-dt?code=<le sien>&state=<email du gestionnaire>`. Le jeton de
rafraîchissement stocké comme identité déléguée de la délégation devient le sien, et
**écrase le légitime**.

**Conséquences.** Les dossiers Drive créés par CLEF et les documents déposés par les
bénévoles — cartes grises, photos, dossiers de réparation — atterrissent dans **son**
Drive ; CLEF envoie des courriels sous **son** compte ; et les fonctions Drive de la
délégation cessent pour tout le monde.

**Deux nuances, par honnêteté :**

- la sévérité dépend du **type d'écran de consentement** OAuth (Interne / Test / Publié),
  non vérifiable depuis la VM. En « Interne », l'attaquant doit être un compte
  `@croix-rouge.fr` — c'est-à-dire l'un des 4546 bénévoles synchronisés. Ça reste une
  prise de contrôle de la délégation Google par n'importe quel bénévole ;
- `dt_id` étant codé en dur, la cible est toujours DT75.

**Correctif** (branche dédiée, avant la tranche 3 — décision du propriétaire du 2026-08-29) :

1. dériver l'email de l'`id_token` du retour Google, **jamais** de `state` ;
2. réduire `state` à un **nonce imprévisible** stocké côté serveur
   (`clef:oauth:nonce:{nonce}`, TTL 600 s) et lié à la session qui a lancé le parcours ;
3. exiger `require_dt_manager` sur le rappel, et refuser si l'email du jeton diffère de
   celui de la session ;
4. contrôler le domaine de l'email — `/auth/callback` le fait, `/auth/callback-dt` non.

Trois tests le fixent : rappel sans session refusé, `state` falsifié refusé, email
divergent refusé.

⚠️ **À faire en même temps** : `revoke_tokens` ne fait qu'un `DELETE` local — l'autorisation
reste vivante chez Google, donc « révoqué » est faux. Voir l'AC-21 de
`docs/specs/administration-globale-delegations.md`.

**Trois défauts trouvés en écrivant le correctif, et corrigés avec lui** — ils touchaient
le même chemin :

1. **`dt_token_service` ne sondait pas sa connexion Redis.** Il testait `_connected`, un
   drapeau qui reste vrai quand la boucle d'événements qui a ouvert le client a disparu
   (bascule Redis, maintenance). Comme ce service **avale ses exceptions**, une connexion
   périmée se traduisait en « le gestionnaire n'a pas autorisé l'accès » : un faux négatif
   silencieux sur le chemin des autorisations Google — famille du constat M2 — qui pousse
   à refaire un consentement, précisément le parcours qu'on venait de durcir. La logique
   de sonde existait, éprouvée, dans `auth/dependencies.py` et **nulle part ailleurs** :
   extraite en `cache.client_utilisable()`, désormais partagée.
2. **`/auth/callback` levait un `UnboundLocalError` au lieu de son 400.** Le chemin super
   admin faisait `status = await dt_token_service.get_authorization_status(...)`, ce qui
   rendait `status` local à toute la fonction ; le gestionnaire d'exception, qui lit
   `status.HTTP_400_BAD_REQUEST`, échouait donc sur un nom non encore assigné.
   ⚠️ **`tests/test_auth.py::test_invalid_authorization_code` figeait ce bug** : il
   attendait l'`UnboundLocalError` et le documentait en commentaire. Un test peut donc
   sanctuariser un défaut au lieu de le révéler — à surveiller ailleurs.
3. **`/auth/dt-authorization-status` et `/auth/revoke-dt-authorization` ciblaient
   « DT75 » en dur.** Les laisser aurait rendu le trio incohérent avec le rappel corrigé :
   révoquer depuis la session d'une autre délégation aurait été une révocation croisée.

### C2 — La prise de véhicule échoue systématiquement en 422

Écart de contrat entre le formulaire `form` et le backend. `prise-form.component.ts:170-180`
envoie `nomSynthetique`, `kmDepart`, `niveauCarburant`, `etatGeneral`, `commentaires`,
`signature`, `emailBenevole`, `nomBenevole` ; `PriseVehicule`
(`backend/app/models/carnet_bord.py:7-32`) exige `vehicule_id`, `kilometrage`,
`niveau_carburant`, `etat_general`, `benevole_email`, `benevole_nom`,
`benevole_prenom` — **tous requis, aucun fourni**.

Hypothèse d'un intercepteur de conversion **écartée par lecture** : le seul
intercepteur (`form/src/app/core/interceptors/auth.interceptor.ts`) ne fait que
poser `withCredentials: true`, et `carnet-bord.service.ts:24` poste l'objet tel quel.

Non détecté parce que l'unique e2e (`frontend/e2e/form-prise-submission.spec.ts`)
**mocke le backend**. Le formulaire de retour, lui, envoie les bonnes clés et
fonctionne.

**Action :** aligner les noms de champs, et ajouter un test d'intégration qui touche
le vrai backend sur ce parcours.

## 🟠 Haute

### ~~H1~~ — ✅ **RÉSOLU le 2026-08-13** — Le job de déploiement n'est gardé par aucun test

`.github/workflows/ci.yml` : `backend-test` et `frontend-build` sont conditionnés
`if: github.event_name == 'pull_request'` ; `deploy-dev` est conditionné
`if: github.event_name == 'push' && github.ref == 'refs/heads/main'` et **n'a pas de
`needs:`**. Sur un push vers `main`, les jobs de test **ne s'exécutent même pas** et
le déploiement part quand même. Seule une protection de branche côté GitHub —
hors de ce fichier — peut l'empêcher.

**Action :** ajouter `needs: [backend-test, frontend-build]` et faire tourner les
tests aussi sur `push`.

> ✅ **Fait.** `deploy-dev` déclare
> `needs: [backend-test, frontend-build, frontend-test, e2e]` et les jobs de test ne
> sont plus conditionnés `pull_request`. `backend/tests/test_ci_workflow.py` (8
> assertions) relit `ci.yml` et fait échouer la suite si le garde-fou disparaît.

### ~~H2~~ — ✅ **RÉSOLU le 2026-08-13** — Fixture de test perdue : 8 tests en échec

`backend/tests/fixtures/vehicles_import_sample.csv` n'existe pas et **n'a jamais été
committé** (0 occurrence dans tout l'historique). La règle `.gitignore:156 *.csv`,
posée pour protéger les données personnelles, l'a avalé. La machine source a été
supprimée. Forme reconstruite et deux options de remédiation dans
`docs/specs/import-vehicules-csv.md`. **Décision produit requise.**

> ✅ **Tranché : les deux options.** Les CSV de test sont désormais **générés** par
> les fixtures `vehicles_import_sample_csv` et `vehicles_no_indicatif_csv`
> (`backend/tests/conftest.py`) — plus aucun `.csv` versionné sous `backend/`, donc
> cette classe de panne a disparu. Un exemple documenté, 100 % fictif, vit sous
> `docs/examples/referentiel-vehicules-exemple.csv`, couvert par l'exception
> `.gitignore` `!docs/examples/*.csv`, **strictement limitée à ce répertoire**.
> La même panne existait côté e2e (`e2e/fixtures/test-vehicles.csv`, jamais
> committé) : réglée de la même façon via `e2e/helpers/vehicles-csv.ts`.

### H3 → requalifié en **C3** après vérification endpoint par endpoint

Ma première formulation (« le `{dt}` n'est pas recoupé ») était trop vague. La
réalité, vérifiée, est plus rassurante sur la majorité des routers et **plus grave**
sur trois d'entre eux. Voir **C3** ci-dessous.

### C3 — 🔴 Trois routers construisent leur accès aux données sur le `{dt}` de l'URL

**Le mécanisme normal est sain.** `get_valkey_service`
(`services/valkey_dependencies.py:34`) fait
`ValkeyService(redis_client=cache.client, dt=current_user.dt)` : pour tout router qui
passe par cette dépendance, le `{dt}` de l'URL est **inerte** — le falsifier ne fuite
rien. Cela couvre `depenses`, `fournisseurs`, `valideurs`, `contacts_cc`,
`reminders`, `import_vehicles`, `stats`, `reservations_valkey`,
`dossiers_reparation`. `benevoles.py` va plus loin et vérifie explicitement
l'égalité (`:63-67`, `:144-148`) — c'est le bon patron.

**Trois routers contournent ce mécanisme :**

| Router | Preuve | Conséquence |
|---|---|---|
| `routers/api_keys.py:36-49` | `async def get_valkey_for_dt(dt: str) -> ValkeyService: return ValkeyService(..., dt=dt)` — construit **sur le paramètre d'URL**, aucun utilisateur impliqué | Un `Gestionnaire DT` de DT-A **liste, crée et supprime les clés API** de DT-B via `/api/DT-B/config/api-keys`. Les clés API sont des credentials : cela ouvre ensuite l'API de sync de l'autre délégation |
| `routers/unites_locales.py` | clés bâties en dur : `f"{dt}:unite_locales:index"` (`:45`), `f"{dt}:unite_locale:{ul_id}"` (`:54,97,130`). **Zéro occurrence de `current_user.dt`** dans tout le fichier | Tout utilisateur authentifié lit l'organisation des UL de n'importe quelle délégation ; tout `Gestionnaire DT` y crée, modifie et supprime des UL |
| `routers/sync.py:47-70` | `verify_api_key` compare à un `SYNC_API_KEY` **global unique**, sans lien avec un DT | Le porteur de cette clé lit et **écrase** bénévoles, responsables et véhicules de **toutes** les délégations. À noter : `/{dt}/vehicules/{ul_id}` (`:130`) valide bien une clé par UL — l'incohérence est interne au fichier |

**Action :** une dépendance FastAPI unique imposant `path.dt == current_user.dt`,
appliquée aux trois routers ; et une clé de sync **par délégation** plutôt qu'une clé
globale.

### H3bis — Aucun filtrage par unité locale hors `vehicles.py`

`vehicles.py` est le **seul** router à appliquer
`get_accessible_vehicle_data` / `filter_by_user_access`
(`services/vehicle_service.py:143-155`) — et ces fonctions ne filtrent de toute façon
pas par UL. Conséquence : un `Bénévole` ou un `Responsable UL` accède aux données de
**tous** les véhicules de la délégation, pas seulement de son UL :

- `dossiers_reparation.py` — dossiers, devis (montants, fournisseurs), factures, uploads
- `depenses.py` — export financier de n'importe quel véhicule
- `carnet_bord.py` — prise et retour sur n'importe quel véhicule ; permet aussi de
  marquer « pris » le véhicule d'une autre UL (déni de service métier)
- `reservations_valkey.py` — créer et consulter des réservations sur tout véhicule
- `stats.py` — agrégats sur toute la flotte de la délégation

Incohérences de garde relevées au passage : `reservations.py:64-70` appelle
`filter_by_user_access` avant de créer une réservation, mais son successeur
`reservations_valkey.py:97-103` — **même opération** — ne le fait pas. Et
`reservations_valkey.py:133-161` (`GET /{id}`) n'a aucun contrôle de propriété, alors
que `PUT` (`:199`) et `DELETE` (`:282`) vérifient créateur-ou-gestionnaire : un id
devinable suffit à lire le NIVOL du chauffeur et la mission.

Enfin, `dossiers_reparation.py` fait confiance au `{dt}` de l'URL **pour ses effets
de bord** tout en utilisant `current_user.dt` pour la lecture :
`ApprovalService(dt=dt)` (`:404,507,768`), `send_*_email(dt_id=dt, …)`
(`:428,544`), `get_or_create_folder(dt_id=dt, …)` (`:666-701,969-989`). Un appelant
peut donc faire créer des tokens ou écrire dans Drive sous l'identité d'une autre
délégation.

### H4 — Flux iCal servis sans authentification

`GET /api/calendar/{dt}/reservations.ics` et
`GET /api/calendar/{dt}/vehicle/{immat}.ics` (`backend/app/routers/ical.py:101,162`)
n'ont **aucune dépendance d'auth** — vérifié : `require_authenticated_user` n'est
même pas importé dans le fichier. Quiconque devine un code DT obtient les noms de
chauffeurs, missions et horaires. `backend/tests/test_ical.py` les appelle avec un
`TestClient` non authentifié et attend `200`, ce qui **fige ce comportement comme
attendu**.

### H5 — Tokens d'approbation renvoyés dans les réponses API

`Devis.token_approbation` (`repair_models.py:125`) n'est pas exclu du
`response_model` de `GET .../dossiers/{numero}` ni de `GET .../devis/{devis_id}`.
Des tokens d'approbation actifs (TTL 7 j) circulent donc dans le JSON servi aux
clients admin.

**Action :** `response_model_exclude` ou un modèle de réponse distinct.

### H6 — Clé de service account à longue durée, exposée en output Terraform

`backend/terraform/service_account.tf` crée un `google_service_account_key` et
`outputs.tf` expose `base64decode(...private_key)`. L'état Terraform est **local**
(aucun bloc `backend`), donc la clé privée réside en clair dans un fichier sur
disque. `infra/README.md` reconnaît le problème.

**Action :** Workload Identity Federation plutôt qu'une clé statique ; état sur GCS
avec verrouillage.

### ~~H7~~ — ✅ **RÉSOLU le 2026-08-26** — Les deux racines Terraform sont cassées

Vérifié par exécution :

```
backend/terraform : outputs.tf:16,21 → google_compute_instance.valkey (ressource inexistante)
infra             : main.tf:167 → google_secret_manager_secret.okta_client_secret (jamais déclarée)
```

Plus : `variables.tf` ne déclare pas `valkey_replica_count`, `valkey_node_type`,
`valkey_version`, `valkey_zone_mode` ; le lock épingle le provider google `6.50.0`
alors que `providers.tf` exige `7.23.0` ; aucun `apply` n'est possible. Voir
`docs/adr/0005-*`.

### H8 — Le formulaire de réservation admin et le calendrier admin ne parlent pas au même backend

`reservation-form.component.ts` poste vers l'API **legacy** Google Calendar
(`POST /api/reservations`), tandis que `calendar-view.component.ts` lit via
`calendar.service.ts` l'API **Valkey** (`GET /api/calendar/{dt}/reservations`). Une
réservation créée depuis l'admin n'apparaît donc pas dans le calendrier admin.
`(inferred — verify : à confirmer en exécutant les deux parcours)`

## 🟡 Moyenne

| # | Constat | Emplacement |
|---|---|---|
| M1 | **Le champ « Montant de la franchise » est décoratif.** Stocké (`valkey_models.py:34`) et consommé (`dossiers_reparation.py:423,540`, `approbation.py:101`), mais absent de `ConfigUpdate` **et** de `ConfigResponse` → ni écrit ni relu, figé à 350 € | `backend/app/models/config.py` |
| M2 | ✅ **Traité 2026-08-20.** L'exception est désormais journalisée (`WARNING`, avec type et message) avant le 401. C'est ce log qui a immédiatement révélé la cause de F20 (`Event loop is closed`) pendant le chantier N2. Le 401 reste muet **côté client**, ce qui est correct : on ne renseigne pas un attaquant | `auth/dependencies.py` |
| M3 | **Identité bénévole factice** dans le carnet de bord : entrées mal attribuées | `prise-form.component.ts:178-179`, `retour-form.component.ts:147-152` |
| ~~M4~~ | ✅ **RÉSOLU 2026-08-13.** Les 2 specs Jasmine portées vers Vitest ; les 2 `app.spec.ts` scaffold (`Hello, admin`/`Hello, form`) réécrits sur le contrat réel. 22 tests passent. ⚠️ La couverture reste mince : 6 fichiers pour ~100 composants | `frontend/projects/**/*.spec.ts` |
| ~~M5~~ | ✅ **RÉSOLU 2026-08-13.** Deux nouveaux jobs : `frontend-test` (matrice admin/form) et `e2e`. Tous deux dans le `needs:` de `deploy-dev` | `.github/workflows/ci.yml` |
| M6 | **`SCAN` cross-tenant de tout le keyspace** pour retrouver un token, après un essai sur un préfixe `"DT75"` codé en dur | `routers/approbation.py:50,60` |
| M7 | **4 services admin codent `dt = 'DT75'` en dur** → application mono-DT en pratique | `api-keys`, `stats`, `unite-locale`, `vehicle-import` services |
| M8 | **Deux caches sans préfixe DT** (`clef:calendar_ids:*`, `clef:carnet_bord:sheet_id:*`) : espace de noms global, isolation plus faible | `valkey_service.py`, `carnet_bord_service.py:16` |
| M9 | **Variables d'environnement documentées inopérantes** : la doc et `.env.example` décrivent `SHEETS_URL_{VEHICULES,BENEVOLES,RESPONSABLES}`, le code lit `{...}_SPREADSHEET_ID` | `services/sheets_real.py:24-26` |
| M10 | **9 variables lues par le code sont absentes de `.env.example`** : `BACKEND_URL`, `ALLOWED_FRONTEND_URLS`, `FRONTEND_URL`, `*_SPREADSHEET_ID` (×3), `GCP_PROJECT_ID`, `ENV` | divers |
| M11 | **`JWT_SECRET_KEY`** est documenté et déclaré en IaC mais **jamais transmis** à Cloud Run (`--set-secrets` ne le liste pas) | `.github/workflows/ci.yml` |
| M12 | **Incohérence de région** : Cloud Run en `europe-west1`, Memorystore et KMS en `europe-west9` | CI vs `backend/terraform` |
| M13 | **Photos de retour capturées mais jamais envoyées** : aucun appel d'upload dans `onSubmit()` | `retour-form.component.ts` |
| M14 | **Signature manuscrite jamais persistée** : aucun champ backend, alors que le formulaire l'exige | `models/carnet_bord.py` |
| M15 | **Mode hors ligne non branché** : `OfflineSyncService` n'est appelé par aucun formulaire et cible `/api/submissions`, endpoint inexistant | `form/services/offline-sync.service.ts` |
| M16 | **`ical.py` et `calendar.py` appellent `calendar_service.get_events()`**, méthode qui n'existe que sur le mock — le vrai `CalendarService` expose `list_events`. Bug latent du chemin production, invisible car les tests tournent en `USE_MOCKS=true` | `routers/ical.py:136,202` |
| M17 | **`ul_config.py` rejette les `Gestionnaire DT`** (rôle exigé exactement `"Responsable UL"`) alors que le backend `is_ul_responsible` les inclut ailleurs — incohérence de droits | `routers/ul_config.py` |
| M18 | **Dossiers de réparation et dépenses n'appliquent pas le filtre UL** que `vehicles.py` applique | `routers/dossiers_reparation.py`, `depenses.py` |
| M19 | **23 `datetime.utcnow()` naïfs** subsistent en production. Comparaisons naïf/naïf donc cohérentes, mais l'API est dépréciée depuis Python 3.12 et c'est la même famille de bug que celle corrigée en `4b4d0a0` | 10 fichiers |
| M20 | **`PATCH .../factures/{facture_id}`** branché de bout en bout, **aucun test backend** | `routers/dossiers_reparation.py` |
| M21 | **`_build_cost_html`** (ventilation sinistre/franchise dans l'email) et le chemin **relance + invalidation de token** : aucun test | `services/email_service.py`, `approval_service.py:82` |
| M22 | **Le spec d'origine est en décalage** : `docs/specs-gestion-factures.md` (2026-03-21) n'anticipait le sinistre que comme une note en prose ; l'implémentation a introduit `est_sinistre`/`franchise_applicable`/`montant_franchise`. **Le spec n'a jamais été mis à jour.** | `docs/specs-gestion-factures.md` §4.2 |
| M23 | **Documentation de déploiement obsolète** : `DEPLOYMENT.md` et `SECRETS_SETUP.md` décrivent `clef-cache` / `redis_7_0` (Memorystore for **Redis**) et des noms de secrets GitHub erronés ; `DOCKER_SETUP.md` parle du service `redis`, ignore le conteneur `frontend-form` (port 4202) et invite à « configurer Okta ». `README.md` omet le segment `{DT}` des endpoints de sync et attribue un rôle IAM (`memorystore.dbConnectionUser`) qui n'est accordé nulle part | racine du dépôt |
| M24 | **Partiellement résolu 2026-08-13.** La cause racine est identifiée : le mock portait l'ancien modèle Google Calendar (`vehicule_id`, `date_debut`) alors que le calendrier lit le modèle Redis (`vehicule_immat`, `debut`) — corrigé, le calendrier affiche désormais l'événement et les 5 tests passent. ⚠️ **Le bloc gardé par `if (await createButton.isVisible())` reste inerte** : le bouton « Nouvelle réservation » n'existe pas, donc la création de réservation n'est toujours pas couverte | `frontend/e2e/` |
| M25 | **Le module Search est disponible mais inutilisé** : aucun `FT.CREATE` dans le code. Fourni sans coût par l'image officielle `redis:8.10` — plus rien à décider côté provisionnement | image `redis:8.10` |

## ⚪ Faible

| # | Constat |
|---|---|
| F1 | `environments/*.tfvars` sont versionnés malgré `.gitignore:102 *.tfvars` (contenu non sensible, mais incohérence de politique) |
| F2 | `*.csv` et `*.json` sont ignorés globalement avec liste blanche : `.claude/settings.json` est ignoré de fait |
| F3 | 3 fichiers `.tf` ne passent pas `tofu fmt -check` : `apis.tf`, `kms.tf`, `providers.tf` |
| F4 | `projects/frontend` est un squelette CLI vide, non déployé, jamais supprimé |
| F5 | `features/retour/` et `features/vehicle-selection/` dans `form` : composants placeholder non routés |
| F6 | `app/dependencies/` est un package vide |
| F7 | `app/cache/cache_service.py` est marqué déprécié mais toujours présent |
| F8 | `valideurs.py`, `contacts_cc.py`, `stats.py` n'ont aucun fichier de test dédié |
| F9 | 3 services frontend codent leur URL d'API en dur au lieu d'`environment.apiUrl` : `qr-code.service.ts:13`, `reservation.service.ts:11` (admin), `carnet-bord.service.ts:16` (form) |
| F10 | `OnPush` n'est utilisé que dans **un** composant sur ~100 |
| F11 | `dossier-detail.component.ts` fait 1028 lignes — candidat au découpage |
| F12 | `redis_service.py` (ex-`valkey_service.py`) fait 1849 lignes et porte tous les domaines |
| ~~F13~~ | ✅ **RÉSOLU 2026-08-13.** `main.py` utilise `lifespan`. Nécessaire : Starlette 1.0 a **supprimé** `on_event()` (encode/starlette#3117) ; seul un shim FastAPI le maintenait en vie |
| F14 | Deux familles Drive/Gmail coexistent (service account vs OAuth délégué), avec deux motifs mock/réel différents — migration inachevée |
| F15 | `calendar-view/README.md` dit que le composant utilise des données mockées : obsolète |

## Commentaires `TODO` dans le code (inventaire exhaustif)

Aucun `FIXME` ni `HACK` dans tout le dépôt. 21 `TODO` :

**Backend (4)**
```
app/auth/routes.py:391          dt_id = "DT75"  # TODO: Get from user context
app/auth/routes.py:414          dt_id = "DT75"  # TODO: Get from user context
app/routers/reservations.py:73  # TODO: Implement metadata retrieval from "Metadata CLEF" sheet tab
app/routers/upload.py:63        # TODO: Get Drive folder ID from vehicle metadata
```

**Frontend (17)** — deux thèmes dominants : l'identité utilisateur non câblée dans
`form` (7 occurrences) et le `dt` codé en dur dans les services `admin`
(4 occurrences). Liste complète :
```
form/prise-form.component.ts:178,179
form/retour-form.component.ts:147,150,151,152
form/vehicle-selector.component.ts:211
admin/vehicle-list.component.ts:156,168,198,229
admin/reservation-form.component.ts:184
admin/services/api-keys.service.ts:13
admin/services/qr-code.service.ts:59
admin/services/stats.service.ts:49
admin/services/vehicle-import.service.ts:96,118
admin/services/unite-locale.service.ts:13
```

## État des tests

### Après le chantier « CI verte » (mesuré le 2026-08-13, seconde passe)

| Suite | Commande | Résultat |
|---|---|---|
| Backend, avec `redis:8.10` | `pytest tests/ -q` + `REDIS_URL` | ✅ **410 passed, 1 skipped** |
| Backend, sans serveur | `pytest tests/ -q` | ✅ **394 passed, 17 skipped** (aucun échec) |
| Frontend unitaire `admin` | `ng test admin --watch=false` | ✅ **19 passed** (6 fichiers) |
| Frontend unitaire `form` | `ng test form --watch=false` | ✅ **3 passed** |
| E2E | `playwright test` | ✅ **30 passed** |
| Builds ×2 | `ng build {admin,form} --configuration production` | ✅ exit 0 |
| Terraform ×2 | `tofu validate` | ❌ **toujours cassé** — hors périmètre (H7) |

### Référence historique (première passe, avant le chantier)

| Suite | Résultat |
|---|---|
| Backend, sans Valkey (= CI de l'époque) | 12 échecs / 356 passés / 1 ignoré |
| Backend, avec Valkey | 8 échecs / 360 passés / 1 ignoré |
| Backend, avant les correctifs du jour | 154 échecs / 214 passés |
| Frontend unitaire | ne compilait pas |
| E2E | 30 échecs (navigateur introuvable), jamais exécutée en CI |

## Branches et travail inachevé

| Branche | État |
|---|---|
| `feat/sinistres-franchise` | **branche de travail**, poussée, PR #6 ouverte, CI rouge à cause de H2 |
| `origin/feat/vehicle-form` | obsolète (`6dba235`), contenu inclus dans la branche courante — supprimable |
| `clef-fleet-management-app` (`3192a5e`) | impasse : arbre **byte-identique** à `df88b0f`, rien d'unique à récupérer |
| `fix/backend-tests` (`df88b0f`) | ancêtre de `origin/main`, intégrée — supprimable |
| tag `backup/vehicle-form-2026-08-13` | filet de sécurité avant la réconciliation ; à conserver jusqu'au merge de PR #6 |

Travail manifestement en cours au moment de l'arrêt (déduit des 17 derniers commits
fonctionnels du 2026-03-23) : l'extension sinistre/franchise, dont le câblage
frontend/backend est complet **sauf** M1, et dont trois chemins neufs (M20, M21)
n'ont aucun test. Puis 4,5 mois sans aucun commit.

---

# Revue de code et revue de sécurité — 2026-08-13

Menées après la rédaction du registre ci-dessus : 5 angles de revue de code sur le
diff `origin/main...HEAD` (31 fichiers) et 3 angles de sécurité sur l'ensemble du
backend. **Tous les constats listés ici ont été revérifiés par inspection directe**
du code par l'agent principal — les numéros de ligne sont cités. Aucune correction
appliquée.

## 🔴 Sécurité — critique

### ~~S1~~ — ✅ **RÉSOLU le 2026-08-13** — `USE_MOCKS=true` en production = contournement total de l'authentification

```
auth/config.py:52   use_mocks: bool = os.getenv("USE_MOCKS", "false").lower() == "true"
okta_mock.py:15     self.mock_secret = "mock-secret-key-for-testing"
okta_mock.py:135    return jwt.encode(payload, self.mock_secret, algorithm="HS256")
```

Le drapeau **n'est gardé par aucun contrôle d'environnement**. S'il vaut `true` sur
Cloud Run, `get_current_user` accepte des JWT HS256 signés avec un secret **présent
en clair dans le dépôt public**. N'importe qui peut alors forger un cookie
`clef_session` pour n'importe quel email, y compris celui du super admin.

Le défaut (`"false"`) est sûr : ce n'est donc **pas exploitable en l'état**, c'est
une absence de défense en profondeur. Mais le risque est réel : `.env.dev` et
`.env.test` existent, `docker-compose.yml` positionne `USE_MOCKS`, et rien
n'empêche un mauvais fichier d'environnement de partir en production.

**Action :** refuser le démarrage si `USE_MOCKS=true` et `ENVIRONMENT` vaut
production. Le même drapeau désactive aussi le chiffrement KMS (voir S2).

> ✅ **Fait.** `assert_mocks_not_in_production()`
> (`app/mocks/service_factory.py`) lève une `RuntimeError` si `USE_MOCKS=true` et que
> `ENVIRONMENT` **ou** `ENV` vaut `production`/`prod`. Appelée **à l'import** de
> `app/main.py`, avant la création de l'app — délibérément pas dans le `lifespan`,
> dont le `except Exception` avalerait l'erreur et laisserait l'app servir.
> 28 tests dans `tests/test_mocks_guard.py`, dont un qui vérifie que la garde n'est
> pas déplacée dans le `lifespan`. Vérifié par exécution :
> `USE_MOCKS=true ENVIRONMENT=production python -c "import app.main"` → `RuntimeError`.
>
> ⚠️ **S2 reste ouvert** : le mode mock réduit toujours le chiffrement KMS à du
> base64. La garde empêche seulement que ce mode atteigne la production.

### S2 — Le même drapeau réduit le chiffrement KMS à du base64

`services/kms_service.py:20,39-56` : en mode mock, `encrypt()`/`decrypt()` ne font
qu'un enrobage base64 préfixé `"MOCK:"`. Or `dt_token_service` s'en sert pour
stocker les **refresh tokens OAuth** des gestionnaires DT. Une mauvaise
configuration transforme « chiffré au repos » en « encodé » : quiconque lit Valkey
récupère les tokens.

### S3 — Cookie de session sans le drapeau `secure`

```
auth/routes.py:178   secure=False,  # Set to True in production with HTTPS
auth/routes.py:194   secure=False,  # Set to True in production with HTTPS
auth/routes.py:224   secure=False,  # Set to True in production with HTTPS
```

Trois sites, valeur **codée en dur**, aucun branchement sur l'environnement : le
commentaire annonce une intention jamais implémentée. Ce n'est donc pas « ça
pourrait manquer en production », c'est **garanti absent**. Combiné au fait que le
cookie porte l'ID token Google brut ([ADR 0003](adr/0003-session-sans-etat-token-google.md)),
tout point du chemin non strictement en TLS expose un jeton d'identité réutilisable.

## 🟠 Sécurité — haute

| # | Constat | Emplacement |
|---|---|---|
| S4 | **XSS stocké dans l'export « PDF » des dépenses.** `_build_pdf_response` renvoie une `HTMLResponse` construite par f-string, avec `fournisseur_nom`, `description` et le paramètre `immat` interpolés **sans échappement**. Un fournisseur nommé `<script>…</script>` exécute du code dans la session de tout gestionnaire qui ouvre l'export | `routers/depenses.py:96-121` |
| S5 | **Injection HTML dans les emails d'approbation.** `fournisseur_nom`, `description`, `description_items`, `commentaire` sont interpolés bruts dans le HTML envoyé aux **valideurs externes** | `services/email_service.py:95-99,164-189,233,258-294` |
| S6 | **Tokens d'approbation écrits en clair dans les logs.** Le token *est* la totalité du moyen d'authentification (TTL 7 j) et le journal a une audience plus large que la base | `services/approval_service.py:53,79,87,132` |
| S7 | **Collision de clés Valkey par identifiant non validé.** `_key()` joint les segments par `:` sans exclure les littéraux réservés (`index`, `counter`, `by_vehicle`…). Un véhicule importé avec `immat="INDEX"` écrit un document JSON sur la clé du SET d'index et casse `list_vehicles()` pour toute la délégation | `services/valkey_service.py:54` |

## 🟡 Sécurité — moyenne

| # | Constat | Emplacement |
|---|---|---|
| S8 | **HMAC du QR comparé sans temps constant** (`expected_encoded == encoded_id` au lieu de `hmac.compare_digest`), signature **tronquée à 64 bits**, endpoint `/decode` **non authentifié** et **aucun rate limiting** dans tout le backend. Oracle de forge illimité. Bon point : le sel est *fail-closed* (`ValueError` si absent ou < 16 caractères) | `services/qr_code_service.py:56-58,99-113` ; `routers/vehicles.py:579` |
| S9 | **`[innerHTML]` alimenté par des données utilisateur** : noms de valideurs et noms de dossiers Drive | `shared/confirm-dialog/confirm-dialog.component.ts:26`, appelé depuis `valideurs-manager.component.ts:190`, `config-page.component.ts:358` |
| S10 | **Upload : validation côté client seulement.** `content_type` de la requête cru sans reniflage d'octets, aucune limite de taille ni de nombre côté serveur, `Image.open()` sans `MAX_IMAGE_PIXELS` → bombe de décompression | `routers/upload.py:47-79`, `services/upload_service.py:47` |
| S11 | **Injection de formule CSV** : l'export dépenses n'échappe pas les valeurs commençant par `=`, `+`, `-`, `@` | `routers/depenses.py:68-84` |
| S12 | **Import CSV sans borne mémoire** : `list(csv_reader)` charge tout le fichier | `routers/import_vehicles.py:182,314` |

**Points propres, vérifiés** : aucun secret réel dans l'historique git ni dans
l'arbre de travail ; CORS sans joker ni réflexion d'origine, défaut *fail-closed* ;
aucun log de cookie, d'access token ou de corps de requête complet ; aucune CVE
confirmable sur les versions épinglées.

## Revue de code — bugs de correctness confirmés

| # | Constat | Emplacement |
|---|---|---|
| R1 | 🟠 **La facture d'un sinistre non pris en charge par la CRF est impossible à enregistrer.** `montant_crf` porte `gt=0` sur `FactureCreate` et `FactureUpdate`, alors que le formulaire calcule automatiquement `0` quand `est_sinistre=true` et `franchise_applicable=false` → **422**. C'est exactement le scénario que la fonctionnalité vise. Noter que `Facture` (l 141) et le modèle d'approbation (l 421) n'ont **pas** cette contrainte : l'incohérence est interne au fichier | `models/repair_models.py:283,296` vs `facture-form.component.ts:246` |
| R2 | 🟡 **Rattacher une facture à un autre devis est un no-op silencieux.** `FactureUpdate` ne déclare pas `devis_id` (contrairement à `FactureCreate`) ; le formulaire envoie le même payload en création et en modification, Pydantic l'ignore, l'UI affiche un succès | `models/repair_models.py:287-296`, `facture-form.component.ts:302` |
| R3 | 🟡 **Montant non formaté sur la page publique d'approbation.** `{{ cond ? montant_franchise : 0 \| number:'1.2-2' }}` : dans la grammaire Angular, `parseConditional` parse chaque branche avec `parsePipe()`, donc le pipe ne s'applique qu'à la branche `0`. Le valideur externe voit `350` au lieu de `350,00` — précisément dans le cas franchise | `approbation-page.component.ts:107` |
| R4 | 🟡 **Modifier une facture dont le fournisseur a été archivé est impossible.** Le sélecteur filtre les fournisseurs archivés avant d'émettre la valeur initiale, `selectedFournisseur` reste `null` et `onSubmit()` sort immédiatement — l'utilisateur ne peut plus corriger le moindre champ | `facture-form.component.ts:278` |
| R5 | ⚪ **La relance groupée n'avertit pas** avant d'invalider les tokens déjà envoyés, alors que la relance d'un devis unique affiche `ConfirmResendDialogComponent`. Un valideur ayant l'ancien email ouvert voit son lien mourir sans préavis | `routers/dossiers_reparation.py:495` |
| R6 | ⚪ **Une seule facture par devis, côté UI seulement.** Le bouton « Ajouter facture » disparaît dès qu'une facture existe (`!getFactureForDevis(d.id)`), alors que le backend n'impose aucune relation 1:1 — facturation en deux fois désormais impossible par l'interface | `dossier-detail.component.ts:246` |
| R7 | ⚪ **Gardes `?.` retirées sur `fournisseur`** en 3 endroits, dont la page publique d'approbation. Risque **faible** : `fournisseur` est déclaré requis des deux côtés (`repair_models.py:117,136` avec `Field(...)`, et non optionnel en TypeScript). Ne devient un problème que sur données héritées — plausible puisque Valkey n'a pas de schéma | `approbation-page.component.ts:65`, `dossier-detail.component.ts:229`, `facture-form.component.ts:123` |

## Revue de code — qualité

| # | Constat | Emplacement |
|---|---|---|
| Q1 | Le littéral `350.0` et l'expression `config.montant_franchise if config else 350.0` sont dupliqués **3 fois** côté backend et **2 fois** côté frontend, redéclarant un défaut déjà porté par le modèle | `dossiers_reparation.py:423,540`, `approbation.py:101`, `dossier-create.component.ts:140`, `dossier-detail.component.ts:516` |
| Q2 | La relance émet **N `DELETE` sur le même token** : les devis d'un dossier partagent un token unique, remplacé juste après la boucle | `routers/dossiers_reparation.py:511` |
| Q3 | La règle métier `cout_crf = montant_franchise if franchise_applicable else 0` vit dans un **constructeur de HTML d'email**, pas dans un service de domaine : inutilisable par l'API, un export ou un rapport sans réimplémentation | `services/email_service.py:270` |
| Q4 | La fusion `fournisseur_id`/`fournisseur_nom` → `FournisseurSnapshot` est réimplémentée en ligne dans `update_facture`, portant à **4** le nombre d'endroits où cette règle existe | `dossiers_reparation.py:1079` vs `:314`, `valkey_service.py:1436,1548` |
| Q5 | `tabNameToIndex` et `tabIndexToName` sont deux tables inverses écrites à la main : réordonner un onglet casse silencieusement les liens profonds `?tab=` | `vehicle-edit.ts:151` |

## Altitude

`(inferred — verify)` La forme retenue — deux booléens sur le dossier plus un
`montant_franchise` **global à la délégation** — ne permet pas de représenter deux
sinistres du même véhicule avec des franchises différentes, ce que le champ
`sinistre_id` (déclaré « futur », jamais utilisé) semblait anticiper.

→ **Tranché le 2026-08-13** : voir D1 ci-dessous. La franchise est **nationale**, donc
la question du « par sinistre » ne se pose pas, et le niveau de stockage actuel est
lui aussi trop bas.

---

# Décisions du propriétaire — 2026-08-13

Réponses aux questions ouvertes, obtenues du propriétaire du projet. Elles
**remplacent** les inférences correspondantes et créent les tâches ci-dessous.

### D1 — La franchise de 350 € est **nationale**, pas par délégation

Contrat d'assurance **national** de la Croix-Rouge : le montant vaut pour **toutes**
les délégations. Conséquences :

- Le stockage actuel sur `DTConfiguration.montant_franchise`
  (`models/valkey_models.py:34`) est **au mauvais niveau** : il invite chaque DT à
  définir une valeur qui n'est pas la sienne à définir.
- Le correctif de **M1** change de nature : il ne s'agit **plus** d'ajouter le champ à
  `ConfigUpdate`/`ConfigResponse` pour le rendre éditable par DT. Il faut au contraire
  le **remonter au niveau national** — configuration globale ou constante applicative
  — et retirer le champ de l'écran de configuration DT, qui devient trompeur.
- La question « franchise par sinistre » est **close** : sans objet.
- ⚠️ Le littéral `350.0` est aujourd'hui dupliqué **5 fois** (voir Q1). Une valeur
  nationale contractuelle ne doit exister qu'à **un** endroit.

### D2 — Le multi-DT est un **objectif**, pas une hypothèse

DT75 est la **première** délégation à utiliser CLEF, pas la seule prévue. « DT75 ne
devrait pas être en dur. » Conséquences directes sur la priorisation :

- **C3 passe de « à durcir » à bloquant.** Les trois routers qui construisent leur
  accès sur le `{dt}` de l'URL (`api_keys.py`, `unites_locales.py`, `sync.py`)
  deviennent des failles d'isolation entre délégations réelles dès la deuxième DT.
  La clé de sync **globale unique** doit devenir une clé **par délégation**.
- **H3bis (absence de filtrage par UL) monte également en priorité.**
- **M7 n'est plus une dette tolérable** : les 4 services frontend codant `dt = 'DT75'`
  en dur (`api-keys`, `stats`, `unite-locale`, `vehicle-import`), plus
  `auth/routes.py:391,414` et les 3 composants de réservation de l'app `form`, doivent
  passer au contexte utilisateur.
- Le `SCAN` cross-tenant de recherche de token (**M6**), avec son préfixe `"DT75"`
  codé en dur en premier essai, devient franchement incorrect.

### D3 — Terraform : à creuser, et un `gcp-deploy.sh` à écrire

Le propriétaire ne tranche pas encore entre `backend/terraform/` et `infra/`.

**Nouvelle tâche N1 :** écrire un `gcp-deploy.sh` **à la racine**, prenant en
paramètre le **nom de l'environnement** (`dev`/`test`/`prod`) et, en option, la
**liste des composants** à déployer. Script **exécuté depuis l'hôte** (jamais depuis
la VM : il porte des actions créditées), à relire avant exécution conformément au
modèle de sécurité. Il devra composer : terraform/tofu → build et push des images →
déploiement Cloud Run → affichage des URLs. Le choix de l'arbre Terraform autoritaire
(**H7**) est un prérequis.

### D4 — Valkey **est** la source de vérité applicative ; l'auth ne l'utilise pas

Confirmé par le propriétaire, et corroboré par les specs récupérées : Sheets est la
source **en amont**, Valkey la source **dans** CLEF, le pont étant un Apps Script
authentifié par jeton en synchronisation périodique. Mon [ADR 0002](adr/0002-google-workspace-comme-referentiel-de-verite.md)
a été **réécrit** en conséquence.

**Nouvelle tâche N2 :** migrer `auth/service.py:47,104,111` pour lire les bénévoles
depuis **Valkey** (`valkey.get_benevole`, comme `routers/benevoles.py:70,74` le fait
déjà) au lieu de Google Sheets. Aujourd'hui, le contrôle d'accès dépend d'un tableur
en direct et la latence d'auth dépend de l'API Sheets **à chaque requête**. C'est le
geste qui termine Wave 11. Les 3 routes PII de `main.py` (**C1**) lisent Sheets pour
la même raison historique : les traiter ensemble.

### D5 — Le tracker est **retrouvé**

`debug/specs-intent.md` (2306 lignes) est le plan Augment Intent d'origine. Il
contient `## Key Decisions`, `## Assumptions`, `## Non-Goals`, et les Waves 1 à 30+
avec leurs identifiants de tâches (`intent://local/task/<uuid>`) — ce sont les
tickets `16.3`, `28.7`… cités dans les messages de commit. **Une grande part du
« pourquoi » que j'avais déclaré irrécupérable est donc récupérée.** Voir
`docs/migration-status.md`, section révisée.

⚠️ Ce fichier est actuellement dans `debug/`, que le commit `2e08454` a **gitignoré**.
Il doit être déplacé sous `docs/` pour ne pas être perdu une seconde fois. Il contient
une donnée personnelle de tiers (un email de contact assurance) : décision de
traitement à prendre avant versionnement.

### Scope : le module factures était **hors périmètre MVP**

Les specs récupérées listent « Gestion du budget/factures des véhicules » dans les
`## Non-Goals (Hors Scope MVP)`. Tout le module Dossiers Réparation / devis /
factures — soit l'essentiel du travail de mars — a donc été construit **après** avoir
été explicitement exclu. Ce n'est pas un défaut, mais cela explique pourquoi ce module
est le moins couvert par les tests et le moins présent dans les specs d'origine.

## Nouvelles tâches issues de la mise à jour de l'environnement

| # | Tâche | Détail |
|---|---|---|
| N1 | **`gcp-deploy.sh` à la racine** | voir D3. Paramètre : nom d'environnement ; option : composants. Exécution **hôte uniquement** |
| N2 | **Auth sur Valkey** | voir D4. Termine Wave 11 |
| N3 | **Python 3.14.x** | La VM va passer en 3.14 et `python3 -m venv` sera réparé. À mettre à jour : `backend/pyproject.toml` (`requires-python`), `backend/Dockerfile` + `Dockerfile.dev` (image de base), `.github/workflows/ci.yml` (`python-version`), et le parcours d'install du `README.md` (le contournement par `uv` restera valide mais ne sera plus nécessaire) |
| N4 | **Node 24** | Aligner sur la VM : `frontend/Dockerfile:4`, `frontend/Dockerfile.dev:1`, `.github/workflows/ci.yml:61`. Les 3 builds passent déjà en 24, donc l'alignement ne devrait rien casser. Vérifier la compatibilité Angular 21 ↔ Node 24 avant de figer |
| N5 | **Remplacer Valkey par Redis 8.10** | Redis **8.10.0** est GA depuis juillet 2026. Motif de fond : Redis 8.0 a ajouté **AGPLv3**, ce qui retire la raison d'être du fork Valkey ici. Points d'attention : (a) le module **JSON** doit rester disponible — vérifier l'image et le déploiement Memorystore ; (b) `docker-compose.yml:4` (`valkey/valkey-bundle:8`) ; (c) le healthcheck utilise `valkey-cli` ; (d) `backend/terraform/memorystore_valkey.tf` provisionne `google_memorystore_instance` en mode Valkey — vérifier l'équivalent Redis 8 sur GCP ; (e) `fakeredis[json]` côté tests ; (f) le module **Search**, provisionné mais inutilisé (M25), peut être abandonné à cette occasion |

---

# Constats nouveaux — chantier « CI verte » du 2026-08-13

Découverts en rendant les quatre suites exécutables. Tous **vérifiés par exécution**.
Aucun n'a été corrigé, sauf mention explicite.

## 🟠 Haute

### H9 — `/super-admin` et `/configuration-ul` n'étaient desservies par aucun lien

Les deux routes existent et sont gardées (`superAdminGuard`, `ulResponsableGuard`),
`AuthService` expose `isSuperAdmin` et `isUlResponsable` — mais `LayoutComponent`
n'appelait ni l'un ni l'autre : **les deux écrans n'étaient atteignables qu'en
saisissant l'URL à la main**. `layout.component.spec.ts` décrivait pourtant la
navigation attendue ; ses assertions échouaient depuis toujours, invisibles parce que
`ng test` ne compilait pas.

> ✅ **Corrigé** : les deux liens sont câblés, conditionnés par les mêmes prédicats de
> rôle. Le contrôle d'accès reste porté par les guards — aucun élargissement de droits.

### H10 — Le bouton d'aide du back-office n'avait pas de nom accessible

`layout.component.html` posait un `matTooltip` mais aucun `aria-label` : le bouton
était muet pour un lecteur d'écran, et introuvable par nom accessible.

> ✅ **Corrigé** : `aria-label="Aide à la configuration"`, aligné sur le texte visible
> du tooltip (WCAG 2.5.3 *Label in Name*).

### ~~H11~~ — ✅ **RÉSOLU le 2026-08-13** — `./run_local.sh` ne peut pas démarrer dans une VM sans credential GCP

`docker-compose.yml` ne positionne pas `USE_MOCKS` : la valeur vient de
`backend/.env`, qui porte `USE_MOCKS=false`. L'app instancie alors le vrai
`GoogleSheetsService`, qui exige `/credentials/clef-backend-dev-key.json` — monté
depuis `~/.cred/CLEF`. Or le modèle de sécurité veut que la VM de développement ne
détienne **aucune credential sortante**. Le healthcheck du backend échoue, et
`depends_on: condition: service_healthy` empêche les deux frontends de démarrer :

```
dependency failed to start: container clef-backend is unhealthy
FileNotFoundError: '/credentials/clef-backend-dev-key.json'   (sheets_real.py:39)
```

**Vérifié : la stack démarre intégralement avec `USE_MOCKS=true`** — `/health` répond
`{"status":"healthy","redis":"connected"}`, `4200` et `4202` renvoient 200. Le seul
obstacle est ce drapeau.

**Décision requise**, car elle touche un drapeau à portée de sécurité (voir **S1** :
`USE_MOCKS=true` en production contourne toute l'authentification) :

- **Option A** — poser `USE_MOCKS=true` dans le `backend/.env` local. Aucun fichier
  versionné ne change ; chaque poste doit le faire.
- **Option B** — déclarer `USE_MOCKS=${USE_MOCKS:-true}` dans le service `backend` de
  `docker-compose.yml`. La stack démarre alors partout sans credential. Contrepartie :
  un fichier versionné porterait la valeur `true` par défaut pour ce drapeau, et
  `environment:` **prime sur** `env_file:` — un `USE_MOCKS=false` délibéré dans
  `.env` serait silencieusement ignoré.
- **Option C** — corriger **S1** d'abord (refuser le démarrage si `USE_MOCKS=true` et
  `ENVIRONMENT` vaut production), ce qui rend l'option B sans danger, puis appliquer B.

> ✅ **Option C retenue et appliquée.** Le garde-fou S1 est posé (voir S1 ci-dessus),
> puis `docker-compose.yml` déclare `USE_MOCKS=${USE_MOCKS:-true}` sur le service
> `backend` — surchargeable depuis le shell (`USE_MOCKS=false docker compose up`,
> vérifié). `./run_local.sh` passe désormais de bout en bout **sans aucune
> credential** :
>
> ```
>   Redis: ✅ Ready     Backend: ✅ Ready     Frontend: ✅ Ready
>   GET localhost:8000/health → {"status":"healthy","redis":"connected"}
>   GET localhost:4200 → 200    GET localhost:4202 → 200    /docs → 200
> ```

## 🟡 Moyenne

| # | Constat | Emplacement |
|---|---|---|
| M26 | **L'autorisation est évaluée *après* l'acquisition du datastore.** Les 8 routes de `config.py` déclarent `Depends(get_config_service)` / `Depends(get_redis_service)` **avant** `Depends(is_dt_manager)`. FastAPI résolvant les dépendances dans l'ordre déclaré, un appelant non autorisé fait ouvrir une connexion Redis avant de recevoir son 403 — et si le datastore est absent, il reçoit un 500 au lieu d'un 403. Défense en profondeur à inverser ; non corrigé, car réordonner une chaîne d'autorisation dépassait le périmètre du chantier | `app/routers/config.py:79-82,103-107,179-182,197-200,377-380,418-422,446-451,595-598,651-654,679-681` |
| M27 | **Flake de tri dans l'historique du carnet de bord.** `get_carnet_entries` trie les entrées sur `timestamp.isoformat()` en ordre lexicographique. `test_get_historique_carnet` a échoué **une fois sur ~10 exécutions** (`Retour` et `Prise` inversés) ; il passe systématiquement isolé. Un tri de dates sur des chaînes n'est pas robuste aux égalités ni aux variations de format (fuseau, microsecondes à zéro). Impact utilisateur : l'historique affiché peut inverser deux entrées proches | `app/services/redis_service.py:568` |
| M28 | **Le wizard d'import ne demande jamais la prévisualisation au backend.** `import-config.component.ts:193` calcule l'aperçu côté client (`.slice(skipLines, skipLines + 5)`), et la valeur par défaut de `skip_lines` vaut **6** côté frontend contre **4** détecté par `POST /preview`. L'endpoint de prévisualisation est donc du code mort du point de vue du wizard, et les deux valeurs divergent silencieusement | `frontend/.../import-config.component.ts` vs `app/routers/import_vehicles.py:196` |
| M29 | **`tests/test_cache.py:9` écrase `REDIS_URL` à l'import**, pour toute la session pytest. Un développeur ou une CI qui pointe un autre serveur voit sa variable ignorée par tous les tests suivants. C'est ce qui a d'abord faussé la mesure « suite sans serveur » | `backend/tests/test_cache.py:9` |
| M30 | **`backend/test_output.txt` est un artefact de run versionné** (sortie pytest de mars 2026, mentionnant Valkey). À supprimer et à gitignorer | racine `backend/` |

## ⚪ Faible

| # | Constat |
|---|---|
| F16 | **`proxy.conf` cible l'hôte `backend`** (nom de service docker compose). Hors compose, chaque requête non interceptée par un mock produit `[WebServer] Error: getaddrinfo ENOTFOUND backend` dans la sortie Playwright. Bruit sans conséquence, mais il masque de vrais problèmes réseau. |
| F17 | **`starlette.testclient` avertit** : `Using httpx with starlette.testclient is deprecated; install httpx2 instead`. Migration à prévoir. |
| F18 | **`backend/scripts/setup_gcp.sh` lit des sorties Terraform nommées `valkey_host` / `valkey_port`.** Ces noms appartiennent à l'arbre Terraform, non touché par le renommage : les changer d'un seul côté casserait le script. À traiter avec H7. |
| F19 | **`PyJWT` avertit** `InsecureKeyLengthWarning: The HMAC key is 27 bytes long` en test — le secret du mock OIDC est sous les 32 octets recommandés pour SHA-256. Sans effet en test ; à ne pas reproduire en production. |


---

# Constats du 2026-08-14 — premier passage réel de la CI sur `main`

Le squash-merge de PR #6 a déclenché le premier run `push` sur `main` avec le
workflow gardé. **Les 6 jobs de test sont passés** ; seul `deploy-dev` a échoué.

## 🟠 Haute

### H12 — Le déploiement automatique n'a jamais pu fonctionner : le secret GitHub est absent

Run `31786247125`, job `Deploy to Dev (Cloud Run)`, échec en 8 s à l'étape
« Authenticate to Google Cloud » :

```
google-github-actions/auth failed with: the GitHub Action workflow must specify
exactly one of "workload_identity_provider" or "credentials_json"!
```

`credentials_json: ${{ secrets.GCP_SERVICE_ACCOUNT_KEY }}` résout à **chaîne vide** :
le secret n'est pas configuré sur le dépôt. Les runs `push` sur `main` d'il y a quatre
mois échouaient déjà en 12 à 15 s — très probablement au même endroit. Le déploiement
automatique n'a donc **jamais fonctionné**, ce que l'absence de `needs:` (H1) rendait
invisible : le job partait, échouait seul, et personne ne regardait.

**Ce n'est pas une régression du chantier CI.** C'est ce chantier qui l'a rendu visible.

**Action, à arbitrer avec H6** : ne pas se contenter d'ajouter le secret. H6 relève déjà
qu'une clé de service account à longue durée exposée en secret GitHub est le mauvais
patron. La **Workload Identity Federation** (`workload_identity_provider`, sans clé) est
la voie recommandée, et l'action `google-github-actions/auth@v2` la prend en charge
directement. À trancher dans le chantier déploiement (N1).

## ⚪ Faible

| # | Constat |
|---|---|
| F20 | **`Event loop is closed` remonte en annotation d'erreur sur `Backend Tests` en CI**, alors que le job passe. **Cause identifiée le 2026-08-26** : le destructeur du client redis-py (`redis/asyncio/connection.py:217 AbstractConnection.__del__`) s'exécute alors que la boucle d'événements qui portait la connexion a disparu. Des dizaines d'occurrences, sur 16 fichiers de tests. Origine : `reset_cache_after_test` met `cache.client = None` **sans le fermer**, et plusieurs fixtures injectent leur propre client dans le singleton de cache.<br><br>⚠️ **Difficile à corriger sur place** : quand la fixture de nettoyage s'exécute, la boucle du `TestClient` est déjà fermée — on ne peut donc pas y fermer proprement un client qui lui est lié. Le correctif de fond est d'arrêter de partager un singleton de cache entre des tests aux boucles différentes (une instance de cache par test), ce qui est un chantier de refonte des fixtures, pas un correctif ponctuel. Non fatal : les jobs passent. À traiter avec M27. |
| F21 | **Toutes les actions du workflow tirent Node 20, déprécié** : `actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`, `google-github-actions/auth@v2`. GitHub les force déjà sur Node 24 et avertit à chaque run. Monter les actions d'un cran (`@v5` / `@v6` selon les cas) supprimera huit avertissements par run. |
| F22 | **`git-pr-merge` ne réécrit pas le titre d'une PR réutilisée** : le commit de squash sur `main` s'appelle « feat: sinistres, franchise et édition de factures (#6) » et ne mentionne pas le chantier CI. Cosmétique, mais à savoir : passer le titre à l'outil ne suffit pas si la PR existe déjà. |


---

# Constats du 2026-08-14 — le mode réel n'est pas praticable en l'état

Relevés en construisant le préflight de `./run_local.sh --real`. Tous **vérifiés par
lecture du code**, avec les lignes citées.

## 🔴 Critique

### ~~M31~~ — ✅ **RÉSOLU le 2026-08-20** — `get_benevole_by_email()` n'existe que sur le mock

Deuxième instance de la famille de bugs relevée en **M16** (`calendar_service.get_events()`),
et celle-ci est sur le **chemin d'authentification**.

```
auth/service.py:104        return self.sheets_service.get_benevole_by_email(email)
mocks/google_sheets_mock.py:290   def get_benevole_by_email(...)     ← existe
services/sheets_real.py           ← N'EXISTE PAS
```

Avec `USE_MOCKS=false`, l'appel lève `AttributeError`. Mais `_get_benevole`
(`auth/service.py:103-106`) l'enveloppe dans `except Exception: return None`, et
`get_current_user` fait de même (`auth/dependencies.py:60-61`, constat **M2**). La
chaîne complète, vérifiée par lecture de `get_user_from_token` :

1. `email == EMAIL_GESTIONNAIRE_DT` → **Gestionnaire DT**. Ce chemin ne touche pas
   Sheets (`auth/service.py:33-43`) : il continue de fonctionner.
2. sinon `_get_benevole()` → `AttributeError` avalée → `None`.
3. sinon `_get_responsable()` → `get_responsables()` existe bien sur le service réel,
   mais avec `spreadsheet_id=None` l'appel Sheets échoue → avalé → `None`.
4. sinon **repli** (`auth/service.py:88-99`) : `role="Bénévole"`, `ul=None`,
   `perimetre=None`, `type_perimetre=None`.

**Conséquence en production ou en intégration réelle :** seul le compte
`EMAIL_GESTIONNAIRE_DT` obtient un rôle correct. **Tous les autres utilisateurs
authentifiés sont silencieusement ramenés à « Bénévole » sans UL ni périmètre**, sans
la moindre trace dans les logs. Les Responsables UL perdent leurs droits, les autres
gestionnaires DT aussi.

Le sens de la dégradation est heureusement *fail-closed* — personne ne gagne de droits.
Mais c'est une panne fonctionnelle totale et muette.

**Action :** c'est exactement la tâche **N2** de la décision **D4** — faire lire les
bénévoles depuis Redis (`redis_store.get_benevole`, comme `routers/benevoles.py:70,74`
le fait déjà) au lieu de Google Sheets. Cela supprime d'un coup : ce bug, la latence
Sheets sur chaque requête d'authentification, et la dépendance du contrôle d'accès à un
tableur en direct. À faire **avant** que le mode réel serve à quoi que ce soit.

> ✅ **Fait — N2 est livrée.** `auth/service.py` ne référence plus le service Sheets
> (test structurel à l'appui). `get_user_from_token` est devenue asynchrone et prend le
> `RedisService` en paramètre : pas d'état caché, et l'appelant contrôle le périmètre.
>
> **Index email → NIVOL.** L'authentification identifie par email, les bénévoles sont
> stockés par NIVOL. Un index `{dt}:benevoles:by_email:{email}` (deux lectures à coût
> constant) évite de parcourir toute la délégation à chaque requête. Il est maintenu par
> `set_benevole`/`delete_benevole`, purge l'entrée obsolète quand une adresse change —
> sans quoi l'ancienne continuerait d'ouvrir une session — et normalise la casse.
>
> **Backfill obligatoire** avant la première connexion :
> `python backend/scripts/backfill_benevole_email_index.py [--dt DT75] [--dry-run]`.
> Les bénévoles écrits avant l'index seraient sinon introuvables — soit le symptôme de
> M31 réintroduit par la porte des données.
>
> **Plus de dégradation silencieuse.** Une panne du datastore **remonte** au lieu de
> produire un utilisateur sans périmètre, et un email absent du référentiel est
> journalisé en `WARNING`. Vérifié : contre une base vide, l'endpoint répond 403 et le
> log dit `Email authentifié absent du référentiel DT75 : aucun périmètre accordé`.
>
> ⚠️ **Conséquence à connaître : l'authentification dépend maintenant de Redis.** Si le
> datastore est injoignable, personne ne se connecte — sauf `EMAIL_GESTIONNAIRE_DT`,
> dont le chemin ne consulte aucun référentiel. C'est un couplage assumé : le contrôle
> d'accès dépendait auparavant de l'API Google Sheets, moins disponible encore.

## 🟠 Haute

### H13 — Les trois URL de feuilles de la configuration DT sont entièrement inertes

`DTConfiguration` (`models/redis_models.py:16-18`) déclare `sheets_url_vehicules`,
`sheets_url_benevoles` et `sheets_url_responsables`. Recherche exhaustive dans tout le
dépôt : **ces noms n'apparaissent nulle part ailleurs** que dans ces trois déclarations
et deux mocks de test.

- Ils ne sont **pas** dans `ConfigUpdate` → `PATCH /api/config` ne peut pas les écrire.
- Ils ne sont **pas** dans `ConfigResponse` → `GET /api/config` ne les relit pas.
- **Aucune ligne de code ne les consomme.**

Le mécanisme réellement utilisé est ailleurs : `sheets_real.py:24-26` lit les variables
d'environnement `VEHICULES_SPREADSHEET_ID`, `BENEVOLES_SPREADSHEET_ID` et
`RESPONSABLES_SPREADSHEET_ID` — qui ne sont définies **ni** dans `backend/.env`, **ni**
dans `.env.example` (constat **M9/M10**).

Même défaut que **M1** (`montant_franchise`), mais en version intégrale : M1 était au
moins consommé en aval, ici rien ne l'est.

**Action :** trancher où vit cette configuration. Deux voies cohérentes :
- **La configuration DT est la source** → ajouter les champs à
  `ConfigUpdate`/`ConfigResponse`, extraire l'identifiant depuis l'URL (le code sait déjà
  le faire pour `drive_folder_url`, `routers/config.py`), et faire lire la config par le
  service Sheets.
- **L'environnement est la source** → retirer les trois champs de `DTConfiguration`,
  qui ne font que suggérer un réglage inexistant, et documenter les variables.

La première voie est plus cohérente avec le multi-DT (**D2**) : chaque délégation a ses
propres feuilles. Mais si **N2** est fait d'abord, l'authentification n'a plus besoin de
Sheets du tout, et la question se réduit à l'import de véhicules.

---

# Constats du 2026-08-20 — audit de parité mock / réel

En corrigeant M31, j'ai cherché ses frères et sœurs de façon systématique : comparer
chaque méthode **appelée** sur un service fourni par `app/mocks/service_factory.py` aux
méthodes réellement **définies** sur l'implémentation réelle. C'est désormais un test —
`tests/test_mock_parity.py` — avec la dette existante en liste explicite : toute
**nouvelle** occurrence fait échouer la suite.

⚠️ Mon premier audit, écrit en shell, n'a rien trouvé — alors que M16 était sous son
nez. Réécrit en Python et confronté à M16 comme témoin, il a remonté 17 signalements,
dont 13 étaient des faux positifs de ma table de correspondance (les trois fichiers
`drive*.py`). **Un audit dont on ne peut pas justifier le silence ne vaut rien.**

## 🟠 Haute

### M32 — Trois appels de plus vers des méthodes inexistantes, tous sur le chemin réel

Même famille que **M16** et **M31**. Chacun lève `AttributeError` en `USE_MOCKS=false`.

| Appel | Emplacement | Réalité |
|---|---|---|
| `sheets_service.get_vehicule_by_indicatif()` | `routers/reservations.py:56` | n'existe **que sur le mock** ; le service réel expose `get_vehicule_by_nom_synthetique` |
| `calendar_service.get_calendar_id()` | `routers/calendar.py:34` | n'existe **nulle part** |
| `calendar_service._get_calendar_name()` | `routers/calendar.py:41` | n'existe **nulle part** |
| `calendar_service.get_events()` | `routers/ical.py:136,202` | n'existe **nulle part** ; le service réel expose `list_events` (= M16) |

Conséquence : en mode réel, la **création et la configuration de calendrier**
(`routers/calendar.py`) et les **flux iCal** (`routers/ical.py`) échouent, et la
création de réservation par l'API legacy (`routers/reservations.py`) aussi. Aucun test
ne pouvait le voir : ils tournent tous en `USE_MOCKS=true`.

**Action :** aligner les appels sur les signatures réelles, puis retirer les entrées
correspondantes de `KNOWN_DEBT` dans `tests/test_mock_parity.py` — le test refuse une
dette obsolète, il échouera donc si on oublie.

⚠️ `routers/calendar.py` appelle **deux** méthodes qui n'existent nulle part : ce
fichier n'a très probablement jamais été exécuté en mode réel. À traiter avec **H8**
(deux modèles de réservation coexistent) plutôt qu'isolément.

## ⚪ Faible

| # | Constat |
|---|---|
| F23 | **L'authentification fait un `PING` Redis par requête authentifiée.** Ajouté avec N2 pour détecter un client lié à une boucle d'événements morte (bascule Redis, maintenance Memorystore, plusieurs `TestClient` dans un même test) — sans quoi l'authentification resterait bloquée définitivement. Un aller-retour local, à comparer à l'appel HTTP complet vers l'API Sheets que ce chemin faisait avant. Mieux à terme : une reconnexion-et-réessai dans `RedisCache` lui-même, sans sonde préalable. |
| F24 | **La suite se replie sur `fakeredis` quand aucun serveur n'est joignable** (`tests/conftest.py`), en remplaçant `cache.connect()`. Nécessaire depuis que l'authentification dépend du datastore : sans repli, 87 tests échouaient faute d'environnement, pas de code. Conséquence à connaître : `pytest` sans serveur n'exerce pas le vrai client Redis — c'est le rôle des 17 tests marqués `integration`. |

---

# Chantier du 2026-08-21 — référentiel bénévoles : identité vs organisation

Les six fragilités relevées le 2026-08-20 sur l'import bénévole sont **traitées**, ainsi
que **C3**. Spécification : `docs/specs/synchronisation-referentiel-benevoles.md`.
Décision de conception : [ADR 0007](adr/0007-partage-de-propriete-feuille-clef.md).

| # | Constat | Traitement |
|---|---|---|
| 1 | Les en-têtes de la feuille étaient un contrat d'API implicite | ✅ Alias explicites sur `Nivol`, `Nom`, `Prénom`, `UL`, `Téléphone`, `Email` ; `Prénom Nom` ignorée ; colonne absente → erreur **qui la nomme** |
| 2 | Contradiction sur `nivol` entre les deux chemins d'écriture | ✅ Tranchée : la feuille porte `Nivol`, clé primaire. Le préchargement Sheets de `main.py` est **retiré** ; la synchronisation est le seul pont (ADR 0002). Reste un amorçage gardé par `use_mocks()` pour le développement local |
| 3 | Tout ou rien : une ligne fautive rejetait le lot en 422 | ✅ Validation **ligne à ligne**, erreurs situées au numéro de ligne de la feuille, réponse 200 même partielle |
| 4 | La synchronisation ne supprimait jamais rien | ✅ Réconciliation : absent du lot → `statut="inactif"`. Jamais de suppression — l'historique référence le bénévole |
| 5 | `statut` était jeté | ✅ `statut` devient un champ de premier plan, **propriété de CLEF**, et l'authentification le respecte (401 si inactif) |
| 6 | La synchronisation écrasait les rôles saisis dans CLEF | ✅ Deux points d'entrée disjoints : `upsert_benevole_identite` n'accepte aucun champ d'organisation, `set_benevole_organisation` aucun champ d'identité |
| C3 | Clé de synchronisation globale unique | ✅ `validate_api_key` sur le `{dt}` de l'URL, sur les **six** endpoints de `sync.py`. `SYNC_API_KEY` n'existe plus |

## Ce que le chantier a corrigé en plus

- **Le modèle de rôles.** `role` à valeur unique → `responsable_ul: bool` +
  `fonctions_dt: list[str]`. Un bénévole peut être responsable de son UL **et** porter
  une fonction DT. Le rôle applicatif n'est plus stocké : il est **dérivé**.
- **Bug préexistant sur `by_ul`.** `set_benevole` ne faisait qu'un `sadd` sur la
  nouvelle UL : un changement d'UL laissait une entrée fantôme dans l'ancienne, et
  `list_benevoles(ul=...)` renvoyait un bénévole qui n'y était plus. Corrigé.
- **Le `PATCH` écrivait l'UL.** Nommer un responsable d'UL déplaçait le bénévole — une
  valeur que la synchronisation suivante rétablissait de toute façon. Retiré.
- **Le `PATCH` parcourait toute la délégation** pour retrouver un bénévole par email.
  Passe par l'index `by_email`, à coût constant.
- **Le téléphone** est importé et exposé dans l'annuaire, sur arbitrage du propriétaire.

## ⚠️ Ordre de déploiement — contraignant

```sh
# 1. AVANT de déployer le nouveau code
python backend/scripts/migrate_benevole_role_to_organisation.py --dry-run
python backend/scripts/migrate_benevole_role_to_organisation.py

# 2. Puis déployer.
```

Le nouveau code lit `responsable_ul` et `fonctions_dt`. Sur un document non migré,
Pydantic leur donne `False` et `[]` : **tous les responsables perdraient leurs droits**
jusqu'au passage de la migration. Le dry-run sur le Redis local rapportait
`1 responsable_ul, 1 responsable_dt, 4 sans rôle`.

Une **clé API de délégation** doit également exister avant la première synchronisation
(écran de configuration, `generate_api_key_dt`) : l'ancienne variable d'environnement
globale n'est plus lue.

## Reste ouvert

| # | Constat |
|---|---|
| N4 | **L'écran d'administration ne permet pas encore de saisir les `fonctions_dt`.** L'API (`PATCH /api/{dt}/benevoles/{email}`) et le stockage existent ; `dt-admin.component.ts` a été adapté au nouveau modèle mais ne gère que `responsable_ul`. Sans cet écran, la moitié CLEF du modèle n'est saisissable qu'à la main. Spec d'UI à écrire |
| N5 | **Pas de référentiel fermé des fonctions DT.** `fonctions_dt` est une liste de chaînes libres. Un référentiel — et une liste déroulante — sont un chantier produit distinct |
| N6 | **Purge RGPD des bénévoles inactifs.** La décision retenue est « désactiver, ne jamais supprimer ». Une purge planifiée après délai de conservation reste à spécifier |
| M33 | **Le référentiel legacy `responsables`** (`set_responsable`, `ResponsableData`, endpoints de `sync.py`) coexiste toujours avec les bénévoles. Son retrait est un chantier de nettoyage à part |


---

# Où on en est — 2026-08-28, fin de séance

## Domaine personnalisé : en attente du certificat

L'infrastructure du load balancer est **appliquée**. `dev.clef.paquerette.com` résout vers
l'IP globale, l'enregistrement `A` est publié, et le certificat managé est en
`PROVISIONING` sur les deux lignes — l'état sain. Rien à faire jusqu'à `ACTIVE`.

```sh
# ⚠️ Le nom du certificat porte désormais une empreinte du domaine
# (« clef-dev-cert-1f2e3d4c ») : sans cela, `create_before_destroy` était inopérant.
# Ne pas le composer à la main.
tofu -chdir=deploy/terraform output -raw certificat_verifier
gcloud compute ssl-certificates list --global --project=rcq-fr-dev
```

⚠️ **Conséquence à connaître avant le prochain `./00-infra.sh dev`** : le certificat
`clef-dev-cert` déjà provisionné sera **remplacé** par `clef-dev-cert-<empreinte>`, et
la fenêtre de provisionnement repart de zéro. Le moment est le bon — l'ancien est encore
en `PROVISIONING`, donc rien n'est servi en HTTPS et il n'y a aucune coupure à subir.
Fait après passage en `ACTIVE`, c'eût été une interruption.

**Reste à faire, dans cet ordre :**

1. Attendre `ACTIVE`. Si ça reste bloqué en `FAILED_NOT_VISIBLE`, c'est le DNS — mais
   il résout déjà, donc ce n'est pas attendu.
2. `PUBLIC_DOMAIN=dev.clef.paquerette.com` dans `deploy/deploy.dev.env`, puis
   `./01-gcp-deploy.sh dev`. **Indépendant du certificat** : peut se faire avant.
   Sans cette étape, la connexion échouera en `redirect_uri_mismatch` même avec un
   certificat actif — le service utiliserait encore son URL `run.app` comme URI de
   redirection.
3. Vérifier — **`01-gcp-deploy.sh` le fait maintenant lui-même** : `/health` par le
   domaine (service par défaut du LB), `/api/test` (règle `/api/*`) et la redirection
   301 depuis `http://`. Si l'une échoue, il le dit et ne conclut plus « ✅ terminé ».
   Reste à l'œil : `https://dev.clef.paquerette.com/`, `/admin/`, `/form/`.
4. Se connecter. L'origine et l'URI de redirection du domaine sont **déjà déclarés**
   côté client OAuth.

## Deux branches à merger

| Branche | Contenu |
|---|---|
| `fix/frontend-base-href` | corrige un bug **en production** : le frontend déployé ne servait aucune ressource. Plus les URL des QR codes et des courriels d'approbation, et la page d'accueil |
| `feat/domaine-personnalise-alb` | le load balancer, déjà appliqué contre GCP mais non mergé |

## Ce qui empêchera l'application de fonctionner, une fois le domaine ouvert

**Constat N13**, connu et non traité : trois routes lisent Google Sheets avec le service
account, ce qui est structurellement impossible dans ce Workspace. `upload.py:54` (envoi
de photos), `reservations.py:55` (création de réservation), `alert_service.py:100`
(alertes CT et pollution). Elles doivent lire Redis.

La connexion et le back-office marcheront ; ces trois fonctions échoueront en 403.

## Ce qui n'a jamais été observé

**Les instantanés RDB** (reliquat de N9). Le montage GCS fonctionne — les journaux du
premier déploiement le prouvent — mais aucune écriture périodique n'a été constatée :

```sh
gcloud storage ls -l gs://rcq-fr-dev-clef-redis-snapshots/
```

# Chantier du 2026-08-26 — déploiement GCP

Décision de conception : [ADR 0008](adr/0008-redis-sidecar-cloud-run-instantanes-gcs.md).

## Ce qui est fait

| Constat | Traitement |
|---|---|
| **H7** — les deux racines Terraform sont cassées | ✅ Racine **unique** `deploy/terraform`, qui valide et est formatée. Les 8 erreurs étaient triviales, et 4 ont disparu avec le retrait de Memorystore. ⚠️ Les deux racines n'étaient pas concurrentes mais **complémentaires**, tout en se disputant le même service account et les mêmes APIs |
| **H6** — clé de service account à longue durée exposée en output | ✅ Plus aucune `google_service_account_key` déclarée. Prérequis livré côté code : `app/services/google_credentials.py` remplace quatre copies du chargement de credentials et se replie sur l'ADC, ce que Cloud Run fournit sans clé. ⚠️ Les deux clés existantes restent à révoquer à la main |
| **M12** — incohérence de région | ✅ Devenue un écart **documenté** : Cloud Run, bucket et registre en `europe-west1` avec le reste du projet ; le keyring KMS reste en `europe-west9`, où il existe et d'où il ne peut être déplacé |
| **M11** — `JWT_SECRET_KEY` jamais transmis à Cloud Run | ✅ Le gabarit l'injecte |
| **N1** — écrire `gcp-deploy.sh` | ✅ Deux scripts : `00-infra.sh` puis `01-gcp-deploy.sh`. Une commande chacun, préflight qui nomme ce qui manque, `shellcheck` muet |

### M11 était un faux constat, et il en cachait deux vrais

Le constat M11 disait « `JWT_SECRET_KEY` est stocké mais jamais transmis au service
Cloud Run ». En vérifiant ce que le code lit réellement, avant de renseigner les
secrets : **aucun code ne lit `JWT_SECRET_KEY`**. `app/auth/config.py` déclare
`session_secret_key` (`SESSION_SECRET_KEY`), qui n'est utilisé nulle part non plus.

La raison est structurelle : le cookie de session porte l'**id_token de Google**,
vérifié contre les clés publiques de Google (`google_oauth.verify_id_token`). Aucun
jeton n'est signé par l'application. Le secret est donc supprimé — en stocker un que
rien ne lit aurait laissé croire au prochain lecteur que les sessions sont signées
côté application.

Le recoupement systématique « variables injectées par le gabarit » contre
« variables lues par le code » a alors sorti **deux défauts bloquants**, qu'aucune
relecture n'avait vus :

| Variable | Effet |
|---|---|
| `ALLOWED_FRONTEND_URLS` | nom inventé ; `app/main.py` lit `CORS_ORIGINS`. Le défaut `localhost:4200,4202,8000` restait en place et **le navigateur bloquait tous les appels du frontend déployé** |
| `GOOGLE_REDIRECT_URI` | absente ; `app/auth/config.py` retombe sur `http://localhost:8000/auth/callback`. Google aurait renvoyé chaque utilisateur **vers sa propre machine** : connexion intégralement cassée |

Les deux sont muets : le déploiement réussit, la révision contient bien ce qu'on lui
a donné, et l'application applique un défaut de développement. Corrigés, et gardés
par deux tests de `test_cloudrun_template.py` — dont un qui compare l'ensemble des
variables injectées à l'ensemble des `getenv` du code, et fait échouer la suite sur
toute variable orpheline.

`01-gcp-deploy.sh` **redéploie une seconde fois** à la création du service :
l'URI de redirection dépend de l'URL du service, qui n'existe pas avant sa création.
Même chose quand le frontend vient d'apparaître, pour que son origine entre dans
`CORS_ORIGINS`.

### Deux défauts attrapés avant le premier apply

**`roles/storage.objectAdmin` était accordé au niveau projet.** Dans `rcq-fr-dev`,
partagé avec une autre application entière, cela donnait au backend CLEF le droit de
lire, écrire et **supprimer** les objets de tous les buckets du projet — dont ceux du
voisin. Vu dans le plan du premier `00-infra.sh`, avant confirmation. La liaison est
désormais portée par le bucket d'instantanés
(`google_storage_bucket_iam_member`), pas par le projet.

`roles/secretmanager.secretAccessor` reste au niveau projet, à dessein : il ne donne
accès qu'aux secrets sur lesquels une liaison existe, et `secrets.tf` en pose une par
secret CLEF. C'est la liaison par secret qui borne la portée.

**Les liaisons IAM renommées auraient pu couper l'accès à KMS.** L'ancienne racine
nommait la ressource `service_account_roles`, la nouvelle `backend_roles` : Terraform
planifiait un destroy **et** un create de la liaison
`roles/cloudkms.cryptoKeyEncrypterDecrypter`, sans dépendance entre les deux nœuds.
Le create passant en premier aurait été un no-op, et le destroy suivant aurait retiré
la liaison — le backend perdant la capacité de déchiffrer les refresh tokens OAuth des
gestionnaires DT, sans erreur. Corrigé par un bloc `moved`, vérifié dans le plan réel
(« has moved to », sans changement).

### Un défaut attrapé avant le premier déploiement

Le gabarit Cloud Run déclarait l'ordre de démarrage par un champ `dependsOn` sur le
conteneur backend. C'est la syntaxe du **provider Terraform** : l'API v1 utilisée par
`gcloud run services replace` l'ignore, **sans erreur**. Le déploiement aurait
« réussi » avec un backend démarrant avant sa base, pour seul symptôme des 500
intermittents au démarrage — et l'authentification lit le référentiel dans Redis dès
la première requête.

La bonne forme est l'annotation
`run.googleapis.com/container-dependencies: '{"backend":["redis"]}'`, **plus** un
`startupProbe` sur le conteneur dont on dépend : sans sonde, l'annotation ne garantit
rien. Les deux sont désormais gardés par `backend/tests/test_cloudrun_template.py`
(14 tests, chacun vérifié par mutation du gabarit).

Leçon générale : les fichiers d'infrastructure ne bénéficient d'aucun typage ni
d'aucun compilateur. Un champ inconnu y est du silence, pas une erreur. Ils méritent
des tests comme le reste.

## Le frontend déployé ne servait rien (2026-08-28)

Symptôme : page sans style, une douzaine de 404 sur `main-*.js`, `chunk-*.js`,
`styles-*.css`, `manifest.json`, `favicon.ico`, et un
« Refused to apply style ... MIME type ('text/html') ».

**Cause unique** : `<base href="/">` est codé en dur dans les deux `index.html` sources,
et `angular.json` ne déclare aucun `baseHref`. Les applications sont pourtant servies
sous `/admin/` et `/form/` : le navigateur résolvait donc toutes les ressources à la
**racine** du domaine, où nginx n'a rien. Le message de MIME type est le même défaut vu
d'un autre angle — le repli renvoyait du HTML là où le navigateur attendait du CSS.

Corrigé par `--base-href=/admin/` et `--base-href=/form/` à la construction. Les
références dans `index.html` étant relatives, poser la bonne base suffit ; il n'y avait
rien d'autre à réécrire. Vérifié par construction et exécution de l'image : `/admin/`,
`main-*.js` (`application/javascript`), `styles-*.css` (`text/css`), `manifest.json`,
`favicon.ico` et le lien profond `/admin/vehicles` répondent tous 200 avec le bon type.

### Deux autres URL cassées, trouvées en cherchant la même famille

| URL fabriquée | Par | Résultat | Corrigé en |
|---|---|---|---|
| `https://{DOMAIN}/vehicle/{id}` | `qr_code_service.py:127` — **QR codes collés sur les véhicules** | 404 | redirection 301 vers `/form/vehicle/{id}` |
| `{FRONTEND_URL}/approbation/{token}` | `dossiers_reparation.py:419,524` — **courriels aux garages** | 404 | redirection 301 vers `/admin/approbation/{token}` |

Ces deux-là **sortent du produit** : un QR code imprimé et un courriel envoyé ne se
corrigent pas par un redéploiement. D'où des redirections dans nginx plutôt qu'un
allongement des URL — un QR code plus court est aussi moins dense, donc plus facile à
scanner. Si une page déménage, seule la configuration nginx change.

Ajouté au passage : **`absolute_redirect off`**. nginx fabriquait ses `Location:` depuis
son propre hôte et son port d'écoute 80, donc `/admin` redirigeait vers **http://**
alors que le client parle HTTPS à Cloud Run.

### Le test qui a de la valeur

`backend/tests/test_frontend_routing.py` (7 tests) ne se contente pas de vérifier la
liste connue : `test_aucune_url_de_produit_non_couverte` **relit le backend** à chaque
exécution et échoue sur toute URL de frontend fabriquée qu'nginx ne connaît pas. Les
trois défauts d'origine ont été trouvés à la main, un par un, après déploiement.

Il porte aussi son propre garde-fou : si ses motifs de détection cessent de trouver les
deux occurrences connues, il échoue — un test qui ne trouve plus rien ne teste plus
rien. Les trois vérifiés par mutation.

⚠️ **La page racine `/` n'est pas un bug** : c'est un `RUN echo '<html>…'` du
`frontend/Dockerfile`, deux liens sans style, écrit comme provisoire. Elle n'a jamais eu
de CSS. À remplacer ou à rediriger — décision produit, laquelle des deux applications
est la porte d'entrée.

## ✅ N7 clos — le premier déploiement a abouti (2026-08-27)

Après le correctif ci-dessous, `./01-gcp-deploy.sh dev` **passe** : les deux images
sont construites par Cloud Build en `europe-west1`, le service à deux conteneurs est
créé, et le sidecar Redis démarre.

⚠️ **Mais l'application ne fonctionne pas encore.** Diagnostic reporté à un chantier
dédié — le déploiement était le périmètre de celui-ci. Pistes déjà connues, par ordre
de probabilité :

1. **N13** — trois routes lisent Google Sheets avec le service account, ce qui est
   structurellement impossible dans ce Workspace : `upload.py:54` (envoi de photos),
   `reservations.py:55` (création de réservation), `alert_service.py:100` (alertes
   CT/pollution). Elles doivent lire Redis.
2. **L'URI de redirection OAuth** doit être déclaré côté client OAuth dans la console
   GCP — et c'est celui du **frontend**, pas celui de l'API. Sans lui, la connexion
   échoue en `redirect_uri_mismatch`.
3. **Le référentiel Redis est vide** au premier démarrage : seul
   `EMAIL_GESTIONNAIRE_DT` peut se connecter, tant que la synchronisation Apps Script
   n'a pas tourné. C'est l'amorçage attendu, pas une panne.
4. **Les instantanés RDB** ne sont pas encore observés (reste de N9).

À reprendre avec `./02-logs.sh dev --what=run`, qui donne maintenant les journaux par
conteneur.

## Premier déploiement réel — pourquoi il a d'abord échoué (2026-08-27)

Le message de Cloud Run était :

    The user-provided container failed the configured startup probe checks.

Il désigne une sonde. La cause est ailleurs — et c'est tout l'intérêt de le consigner.
Les journaux, collectés par `./02-logs.sh dev`, disent :

    STARTUP TCP probe succeeded after 1 attempt for container "redis" on port 6379
    Ready to accept connections tcp
    ERROR json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
    ERROR pydantic_settings.exceptions.SettingsError: error parsing value for field
          "allowed_frontend_urls" from source "EnvSettingsSource"

**Ce qui a bien fonctionné**, et qu'il faut retenir comme acquis : GCSFuse a monté le
bucket (`File system has been successfully mounted`, avec `uid:1000 dir-mode:777` —
donc la crainte d'un montage en root non traversable par l'uid 999 de l'image redis
était **infondée**), Redis 8.10.1 a démarré avec ses modules, et **la sonde du sidecar
est passée du premier coup**. Le constat N9 est donc largement levé sur le montage
lui-même ; reste à observer l'écriture périodique du RDB.

**La cause réelle** : `pydantic-settings` exige du **JSON** pour tout champ de type
complexe lu depuis l'environnement. `ALLOWED_FRONTEND_URLS=https://…run.app` — une URL
nue, ce que le script transmet — lève une exception à l'**import** de
`app/auth/config.py`, donc avant que l'application existe. Cloud Run ne pouvait
rapporter que l'absence de réponse.

Corrigé par `Annotated[list[str], NoDecode]` plus un validateur `mode="before"` qui
accepte le format « a,b,c ». Appliqué aux **trois** champs de type liste, pas au seul
qui a explosé : `google_scopes` et `dt_oauth_scopes` échoueraient identiquement le jour
où quelqu'un les pose dans l'environnement.

### Pourquoi aucun test ne l'avait vu

C'est la leçon, et elle vaut plus que le correctif. **En local, aucune de ces variables
n'est définie** : les valeurs par défaut s'appliquent, rien ne plante, et les 548 tests
étaient verts. Aucun test ne plaçait l'application dans l'environnement où elle allait
réellement tourner.

`backend/tests/test_cloudrun_env_import.py` (9 tests) rend cet environnement **la
condition testée** : il lit les variables depuis le gabarit rendu — donc toute variable
ajoutée y entre automatiquement — les pose dans un environnement **minimal** (rien de
la machine de développement, comme sur Cloud Run) et importe `app.main` dans un
sous-processus. Il couvre aussi les formes dégradées : variables vides, ce que le script
produit au tout premier passage. Les 9 vérifiés par mutation : sans `NoDecode`, les 9
tombent.

Second défaut découvert au passage : `test_toute_variable_injectee_est_lue_par_le_code`
ne voyait plus `ALLOWED_FRONTEND_URLS`, car **`pydantic-settings` lit l'environnement
par nom de champ, sans appel `getenv` visible**. Un grep ne peut pas le savoir. Le test
prend désormais aussi les noms de champs de `AuthSettings.model_fields` comme sources
de lecture — vérifié par mutation qu'il attrape toujours une vraie orpheline.

## Revue de sécurité du 2026-08-27 — 2 constatations, 2 traitées

`/security-review` sur `main...HEAD`. Deux constatations retenues, plus un
durcissement et un bloquant fonctionnel découvert au passage. Toutes vérifiées
indépendamment avant correction.

| # | Défaut | Traitement |
|---|---|---|
| S3 | **Le proxy nginx ne vérifiait pas le certificat de l'amont.** `proxy_ssl_verify` vaut **`off`** par défaut : le SNI était posé délibérément, mais aucune vérification. Or c'est une connexion TLS **nouvelle** — avant cette branche, l'image frontend ne parlait jamais au backend — et tout le parcours authentifié la traverse : cookie de session, en-tête `X-API-Key` de la synchronisation, données personnelles des bénévoles | `proxy_ssl_verify on` + `verify_depth` + bundle CA de l'image + `proxy_ssl_name`. Posées **sans condition** : ces directives ne s'appliquent qu'à un amont `https`, nginx les ignore sur `http://`. Un `if` sur le schéma n'aurait jamais été testé. **Vérifié en exécution** : amont HTTPS à certificat auto-signé ⇒ `502` et `upstream SSL certificate verify error: (18:self-signed certificate)` ; amont HTTP ⇒ le relais fonctionne toujours |
| S4 | **`/docs`, `/redoc` et `/openapi.json` devenaient joignables depuis Internet.** Le constructeur `FastAPI()` est préexistant, mais cette branche est le premier chemin de déploiement qui aboutit, et le service est nécessairement `allUsers` / `run.invoker`. Le schéma décrivait les 86 routes à qui le demande : routes super-admin, gestion des clés d'API, nom de l'en-tête `X-API-Key`, le fait que `/api/approbation/{token}` n'est pas authentifiée, et les modèles du référentiel bénévoles. Aucun accès n'en découlait — les gardes tiennent — mais tout le tâtonnement disparaissait | `ENABLE_API_DOCS`, défaut **`false`**. `docker-compose.yml` pose `true` : la doc reste disponible en local. **Vérifié en conteneur** : par défaut `/docs`, `/redoc`, `/openapi.json` → 404 ; avec le drapeau → 200. Un test interdit au gabarit Cloud Run de l'activer |
| S5 | **Durcissement** : une entrée vide dans `ALLOWED_FRONTEND_URLS` dégénère `validate_redirect_url` en `url.startswith("/")`, qui accepte l'URL protocol-relative `//evil.tld` — un open redirect. Le cas est atteignable : le script rend la variable vide au tout premier déploiement. Il n'était pas exploitable, `GOOGLE_REDIRECT_URI` étant vide dans la même fenêtre — les deux dérivent de la même variable — mais le validateur ne doit pas dépendre de cette coïncidence | Entrées vides filtrées dans `app/auth/config.py` |
| S6 | 🔴 **Bloquant fonctionnel, pas une vulnérabilité : la connexion ne pouvait pas fonctionner.** `GOOGLE_REDIRECT_URI` pointait l'origine de l'**API**. Le backend pose le cookie de session dans la réponse au callback, et le navigateur l'attribue à l'hôte qui lui a répondu : le cookie partait sur `clef-api-*.run.app`, puis le navigateur suivait la redirection vers le frontend, dont les appels ne portaient plus aucun cookie | L'URI pointe désormais l'origine du **frontend**, que nginx relaie déjà. Le cookie est attribué à l'hôte du frontend et tout reste en même origine. ⚠️ Le correctif réflexe — `SameSite=None` sur un domaine partagé — aurait détruit la propriété de même origine sur laquelle repose le reste du raisonnement. C'est aussi l'URI du **frontend** qu'il faut déclarer au client OAuth dans la console GCP |

**Écartés après vérification** : l'open redirect par `startswith` (le validateur exige
l'égalité ou le préfixe `autorisé + "/"`, donc `https://front.run.app.evil.tld` est
rejeté) ; l'héritage des `add_header` nginx (défaut préexistant à l'octet près, et le
bloc **nouveau** hérite bien des trois en-têtes) ; la confusion de chemin dans le
proxy (nginx normalise avant de choisir la location, et l'URL du backend est de toute
façon publique) ; l'injection de gabarit par `envsubst` (le filtre ne porte que sur
les variables définies) ; les en-têtes transmis (le backend n'en lit aucun) ; le
repli ADC de `google_credentials.py` (les credentials du serveur de métadonnées
ignorent les scopes et produisent des 403, pas un accès élargi) ; l'absence de
`requirepass` sur le sidecar Redis (aucun port déclaré, pas de connecteur VPC —
6379 n'est joignable que du conteneur voisin).

## Revue de code du 2026-08-27 — 13 constatations, 13 traitées

`/code-review` sur `main...HEAD`. Toutes vérifiées par lecture du code ou par
exécution avant correction ; aucune n'était un faux positif. Les quatre premières
faisaient que **le déploiement aurait tourné sans que l'application fonctionne**.

| # | Défaut | Traitement |
|---|---|---|
| R1 | **Le frontend déployé n'avait aucune route vers le backend.** `angular.json` ne déclare aucun `fileReplacements` : le build de production utilise `environment.ts`, où `apiUrl` est vide — les appels partent en relatif vers `/api/...`. `nginx.conf` ne définissait que `/health`, `/admin`, `/form` et `/`. Chaque appel du frontend recevait un 404 de nginx. `environment.prod.ts` est du code mort | `frontend/clef.conf.template` relaie `/api` et `/auth` vers le backend, rendu au démarrage par l'entrypoint nginx. **Vérifié en exécution** : `/api/test` renvoie le corps du backend, `/auth/me` un 401, `/health` reste servi par nginx |
| R2 | **`ALLOWED_FRONTEND_URLS` retirée à tort.** Je l'avais crue inventée. `app/auth/config.py:65` la lit, et `app/auth/routes.py` s'en sert pour valider `redirect_to` puis choisir la destination post-connexion. Défaut `localhost:4200` : toute connexion rejetée en 400, et un callback réussi renvoyant sur localhost | Restaurée. Mon recoupement cherchait `getenv("NOM"` sur une seule ligne, et l'appel est écrit sur deux — d'où l'angle mort |
| R3 | **Cookie de session `secure=False` en dur**, aux trois points d'appel dont la déconnexion | Piloté par `SESSION_COOKIE_SECURE`, à `true` dans le gabarit. `SameSite=Lax` reste correct : le proxy nginx fait du frontend et du backend la même origine |
| R4 | **`FRONTEND_URL` et `DOMAIN` non injectées.** La première fabrique les liens d'approbation de devis **envoyés aux garages** ; la seconde l'URL encodée dans les QR codes **imprimés et collés sur les véhicules**, dont le défaut est `clef.example.com` | Injectées. `DOMAIN` retombe sur l'hôte du backend, jamais sur localhost : une valeur fausse ne se corrige pas par un redéploiement, mais au chiffon |
| R5 | **Le job CI `deploy-dev` aurait détruit le datastore.** Inchangé, il tourne sur chaque push vers `main` et fait un `gcloud run deploy` mono-conteneur avec `--max-instances 10` et les anciens noms de secrets : topologie écrasée, volume d'instantanés détaché | Job **retiré**. `test_ci_workflow.py` échoue désormais si un job de déploiement réapparaît — le garde-fou est inversé, plus supprimé |
| R6 | **Mon garde-fou de destruction ignorait les remplacements forcés.** Terraform écrit « must be replaced », qui détruit puis recrée. `google_secret_manager_secret` n'a pas de `prevent_destroy`, et changer `replication` — ce que j'avais fait en 48f7c66 — force un remplacement : le script aurait annoncé « aucune destruction planifiée » | Les deux libellés reconnus. Et l'extraction d'identifiant élargie aux préfixes `~`/`+` des blocs `-/+`, sans quoi un remplacement **légitime** était refusé. Quatre plans de référence vérifiés |
| R7 | `--skip-build` ne résolvait que l'image backend : le frontend gardait un tag horodaté jamais poussé, et échouait **après** le remplacement du service api | Les deux images résolues, chacune sous condition de son composant |
| R8 | `--format="value(package)@value(version)"` : gcloud refuse du texte hors projection, stderr était jeté, la variable sortait vide — `--skip-build` ne fonctionnait **jamais** | `format("{0}@{1}",package,version)` |
| R9 | **`secretmanager.secretAccessor` au niveau projet.** Mon commentaire affirmait qu'il ne portait que sur les secrets liés : c'est faux, une liaison projet porte sur tous les secrets de `rcq-fr-dev`, dont ceux du voisin | Retiré. `secrets.tf` posait déjà une liaison par secret, qui suffit. Même raisonnement que pour `storage.objectAdmin` |
| R10 | `--maxmemory-policy noeviction` **sans `--maxmemory`** : la politique est inerte, et le dépassement se traduit par un OOM-kill de Cloud Run — retour au dernier instantané, sans signal Redis | `--maxmemory` à 65 % de la limite du conteneur, calculé depuis `REDIS_MEMORY`. La marge couvre la duplication de pages du BGSAVE, que `maxmemory` ne compte pas |
| R11 | `timeoutSeconds: 300` documenté comme un délai de grâce à l'arrêt. C'est le délai de **requête** ; Cloud Run n'expose aucun délai de grâce configurable | Commentaire corrigé. Le RPO réel à l'arrêt est la pleine fenêtre de 10 min, comme le dit l'ADR 0008 |
| R12 | `00-infra.sh` réclamait encore `CLEF_JWT_SECRET_KEY`, supprimé de Terraform : il invitait à créer un secret que rien ne lit | Retiré |
| R13 | `envsubst` non vérifié au préflight, alors qu'il est absent de macOS par défaut : l'échec tombait **après** la construction et la poussée des deux images | Contrôlé avec les autres prérequis |

**Ce que la revue apprend sur mes garde-fous.** `test_cloudrun_template.py` vérifiait
que tout ce qui est **injecté** est **lu**. Une inclusion dans un seul sens : elle ne
pouvait structurellement pas voir une variable **manquante**, ce qui est précisément
le défaut R2 — et R4. Le test inverse existe désormais, avec une liste explicite des
variables dont le défaut est faux en production. Un garde-fou qui ne teste qu'une
direction donne une confiance qu'il ne mérite pas.

## Revue de code du 2026-08-28 — 11 constatations, 11 traitées

`/code-review` sur le dernier commit (`c623d80`, PR #11 — domaine personnalisé par
ALB) et la surface de déploiement voisine. **Les deux premières auraient empêché toute
connexion** le jour de l'ouverture du domaine ; trois autres ne se manifestaient qu'au
*second* apply Terraform, donc après la mise en service.

| # | Défaut | Traitement |
|---|---|---|
| V1 | 🔴 **L'URI de redirection OAuth affiché n'était pas celui déployé.** Le script disait « enregistrer `${BACKEND_URL}/auth/callback} » alors que `deploy_api` envoie `${PUBLIC_BASE}/auth/callback` dès qu'un domaine existe. L'opérateur déclarait l'URI `*.run.app`, l'application en annonçait un autre : **toute** connexion échouait en `redirect_uri_mismatch` | Le script affiche `$R_REDIRECT_URI` — la valeur réellement partie dans le service — et l'origine JavaScript correspondante. Un test interdit la recomposition |
| V2 | 🟠 **`ALLOWED_FRONTEND_URLS` réduite à une seule valeur** alors que `validate_redirect_url` la lit comme une **liste**. Dès que le domaine public existait, l'origine `*.run.app` disparaissait des destinations valides — service pourtant toujours publiquement invocable et toujours dans `CORS_ORIGINS` : `400 Invalid redirect URL` | Liste, domaine public en tête, origines run.app conservées derrière, sans doublon |
| V3 | 🟠 **`create_before_destroy` sur un certificat à nom FIXE ne peut pas fonctionner.** Changer `public_domain` force le remplacement ; Terraform crée d'abord, GCP refuse le doublon de nom (`alreadyExists`), l'apply échoue — et la bascule sans coupure n'a jamais lieu | Le nom porte `substr(sha256(public_domain), 0, 8)`. Même effet que le `random_id` + `keepers` de la doc du provider, sans état supplémentaire. La sortie `certificat_verifier` donne le nom réel |
| V4 | 🟠 **`prevent_destroy` rendait inutilisable l'interrupteur documenté.** Il n'est pas conditionnel : vider `public_domain` planifiait la destruction d'une ressource protégée, et Terraform échouait **au plan** — la racine entière devenait inapplicable, y compris pour des changements sans rapport, et `tofu destroy` était bloqué | L'adresse suit sa propre condition (`ip_active`) et **reste réservée** quand le LB s'éteint : le DNS publié reste valide. `keep_public_ip = false` la libère explicitement |
| V5 | 🟠 **Politique TLS et certificat n'attendaient pas l'activation des APIs.** Ne référençant aucune autre ressource, le provider ne leur déduisait aucune dépendance : au premier apply d'un environnement où `compute.googleapis.com` s'active dans la même passe, elles couraient l'activation et échouaient en `SERVICE_DISABLED` | `depends_on` ajouté. Le test écrit pour l'occasion est **générique** — il a trouvé une **troisième** ressource dans le même cas, l'url map de redirection, que la relecture avait manquée |
| V6 | ⚪ **La spec prescrivait encore `timeout_sec` à 300 s**, le champ même que le second commit de la PR avait retiré parce que GCP le REFUSE sur un NEG serverless. Un mainteneur suivant la spec le remettait, et l'apply échouait | Ligne de risque réécrite, avec le message d'erreur exact |
| V7 | ⚪ **`PUBLIC_DOMAIN` utilisé brut.** Collé avec son schéma — la forme affichée partout dans la documentation — il donnait `https://https://clef…` dans `FRONTEND_URL`, `GOOGLE_REDIRECT_URI` et, **irréversiblement**, dans `DOMAIN` : l'hôte encodé dans les QR codes collés sur les véhicules. Rien ne le recoupait non plus avec le `public_domain` du tfvars | Validé comme nom d'hôte seul (ni schéma, ni chemin, ni port), normalisé en minuscules, et comparé au tfvars de l'environnement. Refus **avant** de déployer, comme pour `PROJECT_ID` |
| V8 | ⚪ **nginx ne relayait pas `/admin/super/*`**, que le LB route vers l'API. Par l'URL run.app — encore le seul chemin tant que l'ingress n'est pas verrouillé — ces appels tombaient dans `location /admin` et recevaient l'index.html de l'application admin au lieu du JSON | Les trois préfixes relayés. **Vérifié en exécution** (nginx + backend factice) : `/admin/super/status` va au backend, `/admin/vehicles` sert toujours le SPA. Un test compare les préfixes du relais à ceux du LB : ils ne peuvent plus diverger |
| V9 | ⚪ **`/api/test` divulguait `environment` et `using_mocks` sans authentification**, déclarée en ligne dans `main.py` — donc publique par construction, la famille de C1 — et désormais publiée sur le domaine public de la Croix-Rouge | Scindée : la **sonde** de routage reste publique dans `routers/probe.py` (c'est son rôle : prouver que `/api/*` atteint l'API) mais ne dit plus rien ; le **diagnostic** passe sous guard en `GET /admin/super/environnement`. Garde structurelle : toute nouvelle route en ligne dans `main.py` fait échouer la suite |
| V10 | ⚪ **Aucun `Strict-Transport-Security`.** Le LB ne sert qu'en HTTPS et redirige le port 80, mais un 301 est interceptable : la **première** visite — nom tapé, QR code, lien de courriel — partait en clair, sur une application qui sert les données personnelles des bénévoles | En-tête posé (un an, `includeSubDomains`, sans `preload`). **Vérifié en exécution** sur la navigation admin. ⚠️ nginx n'hérite pas des `add_header` dans les blocs qui en déclarent un : les deux locations d'actifs statiques ne l'ont pas — sans conséquence pour HSTS, mais un scanner le signalera |
| V11 | ⚪ **La vérification finale ne sondait que l'URL `run.app`.** Certificat en `FAILED_NOT_VISIBLE`, enregistrement A absent, NEG visant le mauvais service : tout cela passait, et le script concluait « ✅ Déploiement terminé » | Trois sondes par le domaine public — `/health`, `/api/test`, et le 301 depuis `http://` avec conservation du chemin — et un message final qui ne dit plus « terminé » quand elles échouent. Résultat aussi dans le rapport JSON |

**Un douzième, hors des onze.** `GET /api/alerts/status` — signalée dans V9 comme « de
la même famille, toujours ouverte » — a été **supprimée** dans la même branche, sur
décision de l'utilisateur après examen de son utilité. Elle divulguait
`service_account_email` en plus du mode mock, n'avait aucun appelant, et son champ
`enabled` codé en dur mentait dès que `SCHEDULER_ENABLED=false`. Détail dans la section
C1 ci-dessus.

**Ce que la revue apprend.** Cinq des six constats Terraform partagent une cause :
*une propriété déclarative dont l'effet réel contredit ce qu'en dit le commentaire ou
la documentation* — `create_before_destroy` inopérant sur un nom fixe,
`prevent_destroy` qui bloque son propre interrupteur, un `depends_on` absent là où
aucune référence ne le remplace. Aucune n'est visible d'un `tofu validate` ; toutes le
sont d'un test qui lit le fichier. Le test générique de V5 en a trouvé une de plus que
la relecture : **écrire la règle plutôt que la vérifier cas par cas**.

## Contraintes de l'environnement, découvertes par exécution

Le premier `./00-infra.sh dev` a réellement tourné le 2026-08-27 : **12 ressources sur
16 créées**, les 4 secrets en échec.

**Une policy d'organisation `constraints/gcp.resourceLocations` interdit les
emplacements par défaut de GCP** sur ce projet — `global` comme `us`. Deux
occurrences rencontrées, à deux étapes différentes.

**Première : `global`.** `replication { auto {} }` place un secret
dans `global` : les quatre créations ont été refusées. Corrigé par une réplication
explicite en `europe-west1`, région dont le même apply a prouvé qu'elle est autorisée
— bucket et registre y ont été créés.

Le message d'erreur parle d'emplacement mais **ne nomme jamais `auto`** : rien dans
l'erreur ne mène au champ fautif.

**Seconde : `us`, au premier déploiement.** `gcloud builds submit --region=europe-west1`
place le **build** dans la région, mais dépose l'archive des sources dans un bucket de
staging qu'il crée par défaut en multi-région **US** :

```
ERROR: (gcloud.builds.submit) HTTPError 412: 'us' violates constraint
       'constraints/gcp.resourceLocations'
```

Là encore, le message nomme l'emplacement sans nommer la ressource. Corrigé par
`--default-buckets-behavior=regional-user-owned-bucket`, qui fait créer ce bucket par
Cloud Build dans la région du build — et évite d'avoir à lui accorder des droits sur
un bucket qu'on aurait provisionné soi-même. Le bucket de state, lui, précisait déjà
`--location`, ce qui explique qu'il soit passé.

**Les sessions gcloud expirent, et vite.** Le 2026-08-27, deux réauthentifications
ont été nécessaires dans la même journée, à 4 h 30 d'intervalle, alors que l'habitude
était de ne pas se reconnecter pendant des mois. Symptôme : les contrôles du préflight
échouent tous ensemble, et — avant correction — étaient rapportés comme des
« ressources absentes ».

Ce n'est pas l'outillage : `00-infra.sh` et `01-gcp-deploy.sh` n'exécutent qu'un
`gcloud config get-value account`, en lecture seule, et n'écrivent ni dans
`~/.config/gcloud` ni dans `CLOUDSDK_*` (audité). L'hypothèse la plus probable est une
politique **Google Cloud session control** de Workspace, dont la durée aurait été
raccourcie — cohérent avec une organisation qui vient d'imposer
`constraints/gcp.resourceLocations` sur `global` **et** sur `us`.

À trancher sur le message exact : « Reauthentication required » = durée de session ;
« invalid_grant / Token has been expired or revoked » = révocation par un
administrateur. La valeur se lit dans *Admin console → Sécurité → Contrôle d'accès et
données → Google Cloud session control*.

**Conséquence pratique** : sur un déploiement qui dure, s'attendre à devoir relancer
`gcloud auth login` en cours de route. Le préflight sait désormais le dire au lieu
d'inventer une absence.

**La règle à retenir** : sur ce projet, une commande GCP qui ne précise pas
d'emplacement en choisit un interdit. Vérifier l'emplacement effectif de toute
ressource ajoutée, **y compris celles qu'un outil crée implicitement**. Deux tests de
`test_cloudrun_template.py` tiennent désormais les deux commandes concernées.

## Faits établis sur l'existant

- **De l'infrastructure était déployée** sur `rcq-fr-dev`, contrairement à ce que tout le
  monde croyait : keyring KMS, service account, 11 APIs, rôles IAM — et un Memorystore
  facturé, **détruit le 2026-08-26**.
- **Aucun service Cloud Run `clef-*`** n'a jamais existé : `deploy-dev` échouait toujours
  à l'authentification GCP (H12). Vérifié toutes régions.
- **Le projet `rcq-fr-dev` est partagé** avec une autre application entière (15 services
  Cloud Run : `rcq-api`, `rcq-frontend`, `dev-export-*`, `ul-queteur-*`). D'où : secrets
  préfixés `CLEF_` (Secret Manager est un espace de noms de projet, et un `JWT_SECRET`
  existe déjà chez le voisin), `disable_on_destroy = false` sur les APIs, liaisons IAM
  additives.
- **Le state Terraform était local, non versionné, et contenait une clé privée en clair.**
  `00-infra.sh` le migre vers un bucket GCS versionné.

## Reste ouvert

| # | Constat |
|---|---|
| N7 | **Aucun déploiement n'a encore été exécuté.** Les scripts sont écrits, `shellcheck` est muet et tous les chemins d'argument sont testés — mais **rien n'a tourné contre GCP**. Le premier `00-infra.sh` puis `01-gcp-deploy.sh` sont à faire depuis l'hôte, en relisant les plans. |
| N8 | **Les deux clés de service account utilisateur restent à révoquer** : `745beb6b…` (celle du `/credentials` local, encore utile à `run_local.sh --real`) et `c0b9e001…` (celle de Terraform, sans usage). ⚠️ Révoquer la première casse le mode réel local jusqu'à `gcloud auth application-default login`. |
| **N9** | 🟠 **REQUALIFIÉ le 2026-08-29, et c'est désormais le défaut le plus gênant du déploiement.** L'inquiétude d'origine — `rename` non atomique sur un stockage objet — ne s'est **jamais** manifestée ; les instantanés s'écrivent (`BGSAVE done, 9208 keys saved`, `DB saved on disk`). C'est le **montage** qui échoue : `GetStorageLayout … rpc error: code = Unimplemented`, sur `Attempt: 1`, gcsfuse ne réessayant pas (`EnableMountRetries:false`). **Mesuré : trois échecs pour un succès en 25 minutes**, et deux occurrences de plus le même soir — un 500 rendu à un utilisateur à 21:11, puis l'échec du déploiement de `clef-api-00017-srg` à 21:06. La sonde en cause détecte l'espace de noms hiérarchique et la documentation gcsfuse la dit « integral … cannot be skipped » : **aucune option de montage ne la court-circuite**, et la liste supportée par Cloud Run n'offre ni réessai ni désactivation. Colmatage en place : trois réessais dans `01-gcp-deploy.sh`, et `MIN_INSTANCES=1` pour que le tirage n'ait lieu qu'au déploiement. **Le correctif réel reste le repli déjà prévu ici** : RDB sur disque local, recopié périodiquement vers GCS, restauré au démarrage — le montage quitte alors le chemin critique. Amendement à l'ADR 0008, à chiffrer. |
| **N15** | 🔴 **`npm ci --only=production` rendait l'image frontend inconstructible.** Construire une application Angular exige les devDependencies : le builder `@angular/build:application` déclaré dans `angular.json`, `@angular/compiler-cli` et `typescript` y vivent tous les trois. L'installation réussissait, puis `ng build` échouait faute de builder — un échec tardif, au milieu d'un Cloud Build, dont la cause est deux étapes plus haut. Corrigé en `npm ci` complet (ce sont des dépendances de l'étage de construction : rien n'atteint l'image finale, qui ne contient que nginx et des fichiers statiques) et `npx ng` au lieu d'un CLI installé globalement, pour que la version vienne du `package.json`. **Vérifié par construction réelle** : image de 104 Mo, `/`, `/admin/` et `/form/` servis en 200. |
| **N14** | 🔴 **`backend/.env` serait parti en clair dans l'image de conteneur.** `gcloud builds submit backend` ne lit que `backend/.gcloudignore` — ou à défaut `backend/.gitignore`, qui ne contenait que `test_output.txt` — et **jamais** le `.gitignore` ni le `.gcloudignore` de la racine, où `.env` et `.venv/` sont pourtant bien exclus. Le Dockerfile faisant `COPY . .`, `backend/.env` (GOOGLE_CLIENT_SECRET, QR_CODE_SALT, SYNC_API_KEY, chemin d'une clé de service account) et ses variantes `.dev`/`.test`/`.prod` auraient été livrés dans une image poussée sur Artifact Registry — lisible par quiconque a accès au projet **partagé**. Plus 244 Mo de virtualenv et 362 Mo de `node_modules`. Attrapé le 2026-08-27, pendant le premier déploiement, avant qu'aucune image ne soit servie. Corrigé par `backend/.gcloudignore` et `frontend/.gcloudignore` (0,7 Mo et 4,2 Mo envoyés au lieu de 388 et 406). ⚠️ **Et ce n'était que la moitié du problème** : `.gcloudignore` ne concerne que Cloud Build. `docker build` lit `.dockerignore`, absent — donc `run_local.sh --build` copiait bel et bien `/app/.env` dans l'image, ce qu'une construction locale a confirmé (1,59 Go). `backend/.dockerignore` et `frontend/.dockerignore` ajoutés : image backend à 580 Mo, aucun secret, `/health` 200. `backend/tests/test_gcloudignore.py` (17 tests) exige les deux fichiers et vérifie qu'ils restent cohérents. ⚠️ **Si une image a été construite avant ce correctif, la supprimer du registre** — commandes dans la conversation. |
| **N13** | 🔴 **Trois routes de production lisent Google Sheets avec le service account — impossible dans ce Workspace.** Le domaine `@croix-rouge.fr` interdit le partage d'un document vers une adresse extérieure, et `clef-backend@….gserviceaccount.com` en est une. C'est structurel : il n'existe pas de réglage qui l'autorise, et aucune délégation à l'échelle du domaine n'est configurée dans le dépôt. **C'est toute la raison pour laquelle les données circulent dans l'autre sens** — Apps Script pousse les bénévoles vers l'API, et tire les véhicules depuis l'API. Les trois routes fautives : `routers/upload.py:54` (`get_vehicule_by_nom_synthetique`, à l'envoi de photos), `routers/reservations.py:55` (`get_vehicule_by_indicatif`, à la création d'une réservation) et `services/alert_service.py:100` (`get_vehicles`, pour les alertes CT et pollution du scheduler). Toutes trois doivent lire **Redis** — le référentiel véhicules y est déjà, `redis_service` expose ce qu'il faut. Tant que ce n'est pas fait, le déploiement tourne mais l'envoi de photos, la création de réservations et les alertes échouent en 403. Découvert le 2026-08-27, sur correction de l'utilisateur : la documentation reconstruite décrivait Sheets comme lu par le backend, ce qui n'a jamais pu être vrai en production. |
| N10 | **`backend/scripts/setup_gcp.sh` est périmé** : il lit des sorties Terraform `valkey_host`/`valkey_port` qui n'existent plus. À retirer ou réécrire. |
| ~~N11~~ | ✅ **CLOS le 2026-08-29 — `MIN_INSTANCES = 1`.** Tranché sur un incident, pas en théorie : à 0, un `GET /api/config` a renvoyé 500 parce que le clic est tombé sur un démarrage à froid dont le montage gcsfuse a échoué. ⚠️ La raison n'est **pas** un risque de perte de données — mesuré, Redis écrit son instantané final sur SIGTERM en ~400 ms, donc un arrêt propre ne perd rien : c'est le tirage du montage à chaque réveil. Et ce réglage **déplace** l'échec vers le déploiement plutôt que de le supprimer. Voir les deux sections datées en fin de document. |
| N12 | **L'ancienne racine `backend/terraform` et `infra/` subsistent.** Conservées le temps de valider la nouvelle ; à supprimer ensuite, avec leurs `terraform.tfstate` locaux. |

## Le 500 sur `/api/config` — un démarrage à froid, pas un bug applicatif (2026-08-29)

Symptôme : `https://dev.clef.paquerette.com/api/config` → `500 (Internal Server Error)`
depuis le back-office.

**Ce n'était pas l'application.** Aucune ligne `GET /api/config` n'atteint uvicorn dans
la fenêtre, et aucune trace Python n'est journalisée. La séquence, relevée dans
Cloud Logging sur la révision `clef-api-00016-k9p` (heures de **Paris** — les
horodatages du log sont en `Z`, deux heures de moins, ce qui m'a d'abord égaré) :

| Heure | Événement |
|---|---|
| 20:11:36.508 | `ERROR The request failed because the instance failed the readiness check` |
| 20:11:36.513 | `WARNING The request was aborted because there was no available instance` |
| 20:11:36.543 | `Starting new instance. Reason: AUTOSCALING` |
| 20:11:37.441 | `Error: … storageLayout call failed … code = Unimplemented` |
| 20:11:38.650 | `Container called exit(255)` |
| 20:11:40.575 | `ERROR terminated: … volume (type: gcs, name: snapshots): mount operation failed` |
| **20:11:40.889** | **`GetStorageLayout -> (…) 62 msec`** — le même appel, réussi |
| 20:11:49 | Application démarrée, 9208 clés rechargées depuis le RDB |

Le point décisif est l'avant-dernière ligne : l'appel identique réussit en 62 ms trois
secondes plus tard. `Unimplemented` n'est donc pas une propriété du bucket — c'est un
échec **intermittent** — et non une propriété du bucket. ⚠️ Ma première rédaction le
qualifiait de « transitoire, rattrapé par Cloud Run » : trop optimiste. Le relevé
complet est de **trois échecs pour un succès en 25 minutes**. Cloud Run reprend
l'instance, mais la requête en vol, elle,
était déjà perdue : Cloud Run ne la rejoue pas.

C'est la conjonction de deux constats déjà ouverts. **N9** — « le montage GCS FUSE pour
les instantanés RDB n'est pas éprouvé, c'est le point à vérifier au premier
déploiement » : il est éprouvé, et il est bien le maillon fragile, mais pas pour la
raison prévue (le `rename` non atomique) — c'est le **montage** qui échoue, pas
l'écriture. **N11** — `MIN_INSTANCES = 0` : sans instance tiède, chaque premier clic
après une période d'inactivité déclenche un démarrage à froid, donc une tentative de
montage.

### Ce qui a été corrigé — `MIN_INSTANCES = 1`

Vérifié dans la documentation Cloud Run : les volumes Cloud Storage acceptent bien un
`mountOptions` dans `volumeAttributes`, mais la liste supportée ne contient **pas** de
réessai de montage (`implicit-dirs`, `only-dir`, `rename-dir-limit`, les caches, les
permissions, `client-protocol`, `max-conns-per-host`, les limites de débit — rien de
plus). La configuration imprimée par gcsfuse confirme `EnableMountRetries:false`, et ce
n'est pas modifiable ici. La seule parade est donc de **ne pas démarrer à froid sur un
clic**.

Corrigé dans les trois endroits qui portaient la valeur : `deploy/deploy.env.example`
(versionné), `deploy/deploy.dev.env` (l'environnement réel, non versionné — c'est LUI
que `01-gcp-deploy.sh` lit) et le repli du script. `tests/test_deploy_env_example.py`
fait désormais échouer la suite si la valeur redevient 0, avec la séquence de logs en
docstring pour que la raison ne se perde pas.

**N11 est clos par la même ligne** — mais pas pour la raison que j'avais écrite. Je
l'avais justifiée par la perte de 10 minutes d'écritures à chaque mise en veille : c'est
**faux**, et mesuré comme tel dans les journaux du 2026-08-28 — Cloud Run envoie SIGTERM,
Redis écrit son instantané final (`BGSAVE done`, `DB saved on disk`) en ~400 ms. La perte
à l'arrêt **propre** est nulle ; la fenêtre de 10 minutes ne concerne qu'une mort brutale.
La vraie raison est le tirage du montage rejoué à chaque réveil. Coût assumé : une
instance facturée en continu (la CPU y était déjà non bridée).

⚠️ **Et ce réglage déplace l'échec plus qu'il ne le supprime.** Avec une instance
minimale, la révision n'est prête qu'après un démarrage réussi : un montage raté fait
donc échouer le **déploiement entier**, ce qui s'est produit sur la révision
`clef-api-00017-srg` à 21:06. C'est un meilleur endroit pour échouer — un déploiement qui
refuse vaut mieux qu'un bénévole devant un 500 — mais ce n'est pas une parade. Les trois
réessais de `01-gcp-deploy.sh` sont ce qui rend le déploiement praticable en attendant
que le montage sorte du chemin de démarrage (N9).

### Ce qui reste ouvert

- **N9 reste ouvert, requalifié.** Le montage peut encore échouer lors d'un
  *remplacement* d'instance (déploiement, maintenance de la plateforme) — la fenêtre
  passe de « chaque période d'inactivité » à « rare ». Le repli architectural nommé par
  N9 (RDB local recopié périodiquement vers GCS, le montage quittant le chemin critique
  de démarrage) n'est **pas** fait : c'est un amendement à l'ADR 0008, avec une
  restauration à définir.
- ⚠️ **`02-logs.sh` tronque à 300 entrées par requête, et le bruit gcsfuse mange le
  budget.** La configuration complète de gcsfuse est imprimée à chaque montage sur une
  seule ligne de ~4 ko : deux montages suffisent à noyer la collecte. La première lecture
  a conclu à tort « aucune donnée » sur la révision courante. En cas d'incident, resserrer :
  `./02-logs.sh dev --what=run --service=api --freshness=15m --limit=1000`.
## Cas d'usage multi-délégation, à concevoir (2026-08-29)

Issus du `/brainstorm` sur le multi-DT (`docs/product/brief.md`). Ce ne sont pas des
défauts : ce sont deux besoins métier que le cloisonnement actuel rend impossibles, et
qui doivent être conçus **avant** que l'architecture ne les interdise pour de bon.

### U1 — Un véhicule vendu à une autre délégation

Un véhicule change de propriétaire entre délégations. Ce n'est pas une correction de
donnée, c'est un **transfert** : il quitte le périmètre de la DT75 pour celui de la DT92.

Les questions à trancher, aucune n'étant évidente :

- **l'historique suit-il le véhicule ?** Dossiers de réparation, sinistres, factures,
  carnet de bord, photos — ils portent le nom de bénévoles et de garages de la
  délégation d'origine. Les transférer, c'est exporter des données personnelles vers un
  autre périmètre ; ne pas les transférer, c'est livrer un véhicule sans passé, alors
  que le contrôle technique et l'entretien sont précisément ce qu'on veut connaître ;
- **le QR code collé sur le véhicule** encode `https://{DOMAIN}/vehicle/{id}`. Après
  transfert, il pointe la délégation d'origine. Faut-il réimprimer, ou faire rediriger
  l'ancienne délégation vers la nouvelle — donc conserver une trace du départ ?
- **les réservations en cours** au moment du transfert.
- **le sens de l'écriture** : la délégation d'origine peut-elle écrire dans celle
  d'arrivée, ou l'arrivée doit-elle accepter une proposition ?

⚠️ Toute clé Redis étant préfixée par le code de délégation, un transfert est une
**réécriture complète** sous un autre préfixe, pas une mise à jour de champ. C'est ce qui
en fait un chantier et non un correctif.

### U2 — Recherche et réservation inter-délégation (renfort)

Un bénévole cherche par défaut les véhicules **de son UL**, et doit pouvoir élargir : les
autres UL de sa délégation, les véhicules de la délégation elle-même, puis les mêmes
recherches **dans une autre délégation** — c'est le cas du **renfort**.

⚠️ **Et cela va jusqu'à l'écriture.** Un bénévole de la DT75 qui réserve un véhicule de
la DT92 matérialise la réservation **dans la DT92**, à l'initiative de quelqu'un qui n'en
fait pas partie. Le cloisonnement n'est donc pas « aucune écriture croisée » : c'est
« aucune écriture croisée **implicite** ». Ce qu'il faut concevoir :

- la réservation écrite dans la DT92 **référence un bénévole de la DT75** — donc une
  identité hors de son périmètre. Comment l'afficher, la contacter, et que devient-elle
  si ce bénévole est désactivé chez lui ?
- **la traçabilité** : qui a initié, depuis quelle délégation, et qui a autorisé. Un
  renfort n'est pas un libre-service.
- l'**élargissement est un geste explicite** de l'utilisateur, jamais un défaut : une
  recherche qui ratisserait toutes les délégations par défaut ferait fuiter la flotte de
  chacune à tout le monde.

Ces deux cas d'usage partagent une conclusion : le préfixe de délégation restera le
mécanisme d'isolation, mais il lui faut **des points de passage explicites, nommés et
tracés** — pas des exceptions ajoutées au coup par coup.

### U3 — Renommer `{dt}:benevoles:*` en `{dt}:ben:*`

Décidé le 2026-08-29 avec la spec `import-referentiel-structures.md` : les clés doivent
être **courtes et indexées par identifiant**, jamais par libellé. La tranche 2 renomme
`{dt}:unite_locale:{id}` → `{dt}:ul:{id}`, `{dt}:unite_locales:index` → `{dt}:ul:idx` et
`{dt}:benevoles:by_ul:{libellé}` → `{dt}:ben:ul:{id}`, mais **s'arrête là**.

Reste donc à renommer les documents et leurs deux index :

```
{dt}:benevoles:{nivol}     → {dt}:ben:{nivol}          ~4546 documents
{dt}:benevoles:index       → {dt}:ben:idx
{dt}:benevoles:by_email    → {dt}:ben:mail
```

⚠️ **Pourquoi ce n'est pas dans la tranche 2** : `by_email` est sur le chemin
d'authentification. Une migration à moitié faite ferme l'application à tout le monde. Elle
mérite sa propre fenêtre, avec un `MULTI`/`EXEC` unique — Redis étant mono-thread sur
l'exécution d'une transaction, les ~4550 `RENAME` s'appliquent alors tout ou rien — plus
un mode de vérification et le renommage inverse en repli.

D'ici là le schéma est **mixte** : `{dt}:ben:ul:{id}` voisine `{dt}:benevoles:{nivol}`.
C'est assumé et écrit, pas un oubli.

### U4 — Obtenir un export exhaustif des unités locales

Mesuré le 2026-08-29 sur `init_data/DTUL.csv` : **36 des 108 délégations n'y ont aucune
unité locale** — DT93, DT2A, DT2B, Martinique, Réunion, Guyane, Mayotte, DT60, DT61… soit
576 UL exportées pour un réseau qui en compte davantage.

Conséquence dans le code, déjà traitée : l'import ne réconcilie jamais, et un
`Id Structure` inconnu ne fait pas rejeter un bénévole
(`docs/specs/import-referentiel-structures.md`, E4 et AC-18). Conséquence **hors** code :
la jointure stricte `Id Structure → UL → délégation` ne couvrira ces délégations que
lorsqu'un export complet sera disponible. Action non technique.
