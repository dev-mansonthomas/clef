# CLEF — carte d'entrée pour agents

> Ce fichier est la carte du dépôt. Le modèle de sécurité, la boucle de travail
> (Qualify → Spec → Plan → Implement → Review → Ship → Document) et les règles
> git/VM sont définis dans `~/.claude/CLAUDE.md` et **ne sont pas répétés ici**.
>
> **Reconstruit le 2026-08-13 depuis le code seul.** L'agent qui a construit ce
> projet a perdu ses notes : il n'existe aucun dossier de reprise. Tout ce qui
> suit est soit **vérifié par exécution**, soit explicitement marqué
> `(inferred — verify)`. Les décisions et leur *pourquoi* sont largement perdus —
> voir `docs/migration-status.md`.

## Ce que c'est

Application de **gestion de flotte de véhicules** pour la **Croix-Rouge française**,
délégation territoriale **DT75 (Paris)**. Le domaine, le code et l'historique git
sont en français ; les identifiants techniques sont en anglais.

Deux applications utilisateur distinctes, un seul backend :

| Application | Public | Usage |
|---|---|---|
| `admin` | Gestionnaires DT, Responsables UL | Back-office : référentiel véhicules, dossiers de réparation, devis/factures, réservations, configuration |
| `form` | Bénévoles sur le terrain | Prise et retour de véhicule (km, carburant, état, photos, signature), réservations |

Un troisième projet Angular, `frontend`, est un **squelette CLI vide et non déployé**
(`app.routes.ts` = `[]`) — ne pas y travailler.

## Stack (versions vérifiées)

| Couche | Techno | Version |
|---|---|---|
| Backend | FastAPI + Pydantic v2, Uvicorn | fastapi 0.115.0, pydantic 2.9.2 |
| Runtime backend | Python | **3.13** requis (`backend/pyproject.toml` `requires-python = ">=3.13"`) |
| Datastore | **Valkey 8** (bundle avec modules **JSON** et **Search**) | image `valkey/valkey-bundle:8` |
| Client datastore | `redis` (asyncio) | 5.2.0 |
| Frontend | Angular standalone + Angular Material | **21.2.4**, TypeScript 5.9 |
| Runtime frontend | Node | **22** en CI/Docker (la VM a 24 — voir Pièges) |
| Tests backend | pytest + `fakeredis[json]` | 8.3.4 / 2.26.2 |
| Tests frontend | **Vitest** via `@angular/build:unit-test` | 4.0.8 |
| E2E | Playwright (chromium) | 1.58.2 |
| IaC | OpenTofu / Terraform, provider google | `>= 1.0`, google 7.23.0 |
| Cible de déploiement | GCP Cloud Run + Memorystore for Valkey + Secret Manager + KMS | — |

## Commandes réelles (toutes exécutées le 2026-08-13, sorties authentiques)

### Backend — installation

⚠️ **`python3 -m venv` ne fonctionne pas dans cette VM** (`ensurepip` absent) et le
`python3` du PATH est en 3.12.3 alors que le projet exige 3.13. Utiliser `uv`, qui
dispose d'un CPython 3.13.14 managé :

```sh
cd backend
uv venv .venv                                            # crée un venv en Python 3.13.14
uv pip install --python .venv/bin/python -r requirements.txt
```

### Backend — tests

```sh
cd backend
export USE_MOCKS=true
.venv/bin/python -m pytest tests/ -q
```

Sortie réelle, sans Valkey (conditions identiques à la CI) :

```
12 failed, 356 passed, 1 skipped, 349 warnings in 3.40s
```

Avec un Valkey réel disponible sur `localhost:6379` :

```sh
docker run -d --rm --name clef-valkey -p 6379:6379 valkey/valkey-bundle:8
export USE_MOCKS=true REDIS_URL="redis://localhost:6379/0"
.venv/bin/python -m pytest tests/ -q
#  → 8 failed, 360 passed, 1 skipped
```

**La suite n'est pas verte, et ne l'était pas non plus sur `main`.** Les 8 à 12
échecs restants sont documentés dans `docs/TODO.md` avec leur cause racine. Le
module JSON est indispensable : c'est pourquoi l'image est `valkey-bundle` et non
`valkey`, et pourquoi `requirements.txt` épingle `fakeredis[json]`.

### Backend — démarrage

```sh
cd backend
export USE_MOCKS=true REDIS_URL="redis://localhost:6379/0"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Vérifié :

```
GET /health   → 200  {"status":"healthy","redis":"connected"}
GET /docs     → 200  (Swagger UI)
GET /auth/me  → 401  (sans cookie de session — comportement attendu)
openapi.json  → 86 routes, titre "CLEF API 0.1.0"
```

### Frontend — installation et build

```sh
cd frontend
npm ci
npx ng build admin --configuration production      # exit 0
npx ng build form  --configuration production      # exit 0
```

Tailles réelles : `admin` ≈ 1,5 Mo initial (566 kB pour le chunk `vehicle-edit`),
`form` 1,36 Mo initial / 290 kB transféré.

### Frontend — tests unitaires : ❌ CASSÉS

```sh
cd frontend && npx ng test admin --watch=false
```

```
✘ TS2304: Cannot find name 'spyOn'.        qr-code-generator.component.spec.ts:83
✘ TS2445: Property 'printQrCodes' is protected …
✘ TS2349: Type 'TestContext' has no call signatures.   qr-code.service.spec.ts:32
```

Les 8 specs sont écrites en **Jasmine** (`spyOn`, `done()`) alors que le projet a
migré vers **Vitest**. Elles ne compilent pas : **zéro test unitaire frontend
exécutable**. La CI ne lançant jamais `ng test`, personne ne l'a vu.

### E2E

```sh
cd frontend && npx playwright test        # non exécuté ici : démarre 2 serveurs Angular
```

6 specs dans `frontend/e2e/`, backend mocké via `e2e/helpers/mock-api.ts`.

### Environnement complet en local

```sh
./run_local.sh          # docker compose down puis up --build ; exige docker + docker compose
```

Services compose : `valkey`, `backend`, `frontend`, `frontend-form`.

### Terraform — ❌ CASSÉ (validation seule dans la VM, jamais d'apply)

```sh
tofu -chdir=backend/terraform init -backend=false -upgrade && \
tofu -chdir=backend/terraform validate
```

```
Error: Reference to undeclared resource
  on outputs.tf line 21, in output "valkey_internal_ip":
  21:   value = google_compute_instance.valkey.network_interface[0].network_ip
There is no managed resource "google_compute_instance" "valkey"
```

Les **deux** racines Terraform échouent à `validate` (`backend/terraform/` et
`infra/`). Détails et causes dans `docs/TODO.md`.

## Carte des modules

### `backend/`

| Chemin | Responsabilité |
|---|---|
| `app/main.py` | Point d'entrée FastAPI, monte 21 routers. ⚠️ contient aussi des routes inline **sans authentification** — voir Pièges |
| `app/routers/` | Un router par domaine métier (véhicules, dossiers de réparation, réservations, config, sync, iCal…) |
| `app/services/` | Logique métier et adaptateurs externes. `valkey_service.py` (1849 lignes) est la couche d'accès aux données de tout le domaine |
| `app/models/` | Modèles Pydantic. `repair_models.py` porte le domaine réparation/sinistre/franchise |
| `app/auth/` | Session par cookie, OAuth Google, guards de rôle, mock OIDC |
| `app/cache/` | Client Redis async partagé (`redis_cache.py`) ; `cache_service.py` est marqué déprécié |
| `app/mocks/` | Doubles de Google Sheets/Drive/Gmail/Calendar + Okta, activés par `USE_MOCKS=true` |
| `app/admin/` | Routes de debug réservées au super admin |
| `app/scheduler.py` | Tâches de fond APScheduler (alertes CT/pollution, rappels de devis) |
| `scripts/` | Scripts ponctuels d'ops et de migration |
| `terraform/` | IaC OpenTofu : APIs GCP, KMS, Memorystore Valkey, service account |
| `tests/` | ~40 fichiers pytest, un par domaine |

### `frontend/`

| Chemin | Responsabilité |
|---|---|
| `projects/admin/` | Back-office. Routes **lazy** (`loadComponent`), guards par rôle |
| `projects/admin/src/app/vehicles/dossier-reparation/` | Cœur du domaine réparation/sinistre/franchise. `dossier-detail.component.ts` fait **1028 lignes** — le point chaud |
| `projects/admin/src/app/services/` | 17 services HTTP. `repair.service.ts` porte 20+ appels |
| `projects/form/` | App terrain. Routes **eager**, aucun lazy loading |
| `projects/frontend/` (racine `src/`) | Squelette vide, non déployé — ignorer |
| `e2e/` | Playwright, backend mocké |

### Autres

| Chemin | Responsabilité |
|---|---|
| `google-apps-scripts/` | Scripts Apps Script poussant les données référentiel vers l'API via clé API |
| `infra/` | Seconde racine Terraform, apparemment antérieure `(inferred — verify)` |
| `docs/` | Docs agent (ce chantier) + `specs-gestion-factures.md`, antérieur et conservé |

## Conventions

- **Langue** : domaine, commentaires et messages de commit en **français** ;
  identifiants de code en anglais. Conserver cette séparation.
- **Commits** : Conventional Commits. Les PR sont **squash-mergées** — voir Pièges.
- **Clés Valkey** : `ValkeyService._key()` produit toujours
  `f"{dt}:{...}"`. **Le code DT est le premier segment de toute clé** ; c'est le
  *seul* mécanisme d'isolation multi-tenant, appliqué par l'application et non par
  le datastore.
- **Aucun `KEYS`** dans le code — un seul `SCAN` (`routers/approbation.py:60`).
  Ne pas introduire de `KEYS`.
- **Mocks** : `USE_MOCKS=true` bascule tous les services Google et l'OIDC sur des
  doubles en mémoire. Aucun appel réseau, aucune credential nécessaire.
- **Angular** : composants standalone, nouveau control flow (`@if`/`@for`),
  signals partiellement adoptés. `OnPush` n'est utilisé que dans **un** fichier —
  ne pas en déduire une convention établie.

## Pièges

1. **Les tests ne sont pas verts, et ne l'ont jamais été récemment.** Ne pas
   conclure qu'un changement a cassé quelque chose sans comparer à la référence
   documentée dans `docs/TODO.md` (8 échecs avec Valkey, 12 sans).

2. **Le fuseau horaire cassait 86 tests.** `datetime.utcnow()` renvoie un datetime
   *naïf* : `.timestamp()` l'interprète en heure locale. Corrigé dans
   `app/mocks/okta_mock.py`, mais **23 autres `datetime.utcnow()` subsistent** dans
   le code de production. Ils comparent du naïf à du naïf, donc restent cohérents,
   mais `datetime.utcnow()` est déprécié depuis Python 3.12.

3. **`main.py` n'a aucun `Depends`.** Trois routes y exposent des **données
   personnelles de bénévoles sans authentification** — vérifié par requête réelle.
   Sévérité critique, détaillé dans `docs/TODO.md`. Ne pas ajouter de route dans
   `main.py` : passer par un router avec un guard.

4. **La CI déploie sans tests.** `Backend Tests` et `Frontend Build` ne tournent que
   sur `pull_request` ; `Deploy to Dev` tourne sur `push` vers `main` **sans
   `needs:`**. Un merge sur `main` déploie donc sans qu'aucun test ne s'exécute.

5. **Les PR sont squash-mergées.** Une branche vivante affiche « ahead de N
   commits » alors que leur contenu est déjà dans `main`. Ne jamais réutiliser un
   nom de branche déjà associé à une PR mergée : les outils qui cherchent « la PR
   de cette branche » retombent sur l'ancienne et concluent à tort « déjà mergée ».

6. **`ng test` ne compile pas** (specs Jasmine sur runner Vitest). Il n'y a
   aucun filet de sécurité unitaire côté frontend.

7. **Le champ « Montant de la franchise » de l'écran Configuration est décoratif.**
   L'UI l'envoie, mais `ConfigUpdate` (`app/models/config.py`) ne le déclare pas :
   `model_dump(exclude_none=True)` le jette. La valeur reste à 350 €.

8. **4 services admin codent `dt = 'DT75'` en dur** (`api-keys`, `stats`,
   `unite-locale`, `vehicle-import`). L'application est mono-DT en pratique, malgré
   un backend conçu multi-tenant.

9. **L'app `form` envoie une identité bénévole factice** (`'user@example.com'`,
   `'Nom'`, `'Prénom'`) au lieu de l'utilisateur authentifié : les prises et retours
   sont mal attribués. Voir les TODO dans `prise-form.component.ts:178` et
   `retour-form.component.ts:147`.

10. **`*.csv` est gitignoré** (protection des données personnelles des bénévoles).
    Cette règle a avalé une fixture de test : `backend/tests/fixtures/vehicles_import_sample.csv`
    n'a **jamais** été committée et est perdue — 8 tests d'import échouent de ce fait.

11. **La VM a Node 24, le projet épingle Node 22.** Les trois builds passent
    quand même. Voir la section toolchain de `docs/migration-status.md`.

## Où commencer selon la tâche

| Tâche | Point d'entrée |
|---|---|
| Domaine réparation / sinistre / franchise | `backend/app/models/repair_models.py`, `backend/app/routers/dossiers_reparation.py`, `frontend/.../dossier-reparation/dossier-detail.component.ts` |
| Accès aux données, nouvelle entité | `backend/app/services/valkey_service.py` |
| Authentification, rôles | `backend/app/auth/dependencies.py` |
| Nouvel écran admin | `frontend/projects/admin/src/app/app.routes.ts` (lazy + guard) |
| Écran terrain bénévole | `frontend/projects/form/src/app/` |
| Infra GCP | `backend/terraform/` (⚠️ cassé, voir `docs/TODO.md`) |
