# La délégation vient de l'utilisateur authentifié

> Tranche 1 du chantier multi-délégation. Cadrage : `docs/product/brief.md`.
> Décisions et tranches : `docs/specs/multi-delegation.md`.

## Purpose

Le backend de CLEF est conçu multi-tenant — toute clé Redis est préfixée par le code de
délégation, et c'est le **seul** mécanisme d'isolation. Mais `DT75` est écrit en dur à
**21 endroits** qui décident : deux chemins d'authentification, l'amorçage du référentiel,
et 18 emplacements du frontend dont 6 services qui ne consultent jamais l'utilisateur
connecté. Une seconde délégation ne verrait donc pas ses données : elle verrait celles de
la DT75, sans qu'aucune erreur ne le signale.

Cette tranche supprime tout littéral `DT75` du code de production et fait venir la
délégation **de l'utilisateur authentifié**. Elle ajoute une conséquence visible, voulue
par le propriétaire : un compte absent du référentiel ne se connecte plus — il recevait
jusqu'ici un accès sans périmètre, rattaché à la DT75 par défaut.

Aucune interface nouvelle. C'est ce qui rend possibles les tranches 2 (import du
référentiel des structures) et 3 (administration globale).

## User stories / acceptance criteria

- En tant que **gestionnaire DT**, je me connecte et l'application n'affiche que les
  données de **ma** délégation, sans qu'aucun code ne la suppose.
- En tant que **bénévole absent du référentiel**, je reçois un refus explicite plutôt
  qu'un accès vide dont je ne comprends pas l'inutilité.
- En tant qu'**agent** reprenant ce code, une régression `DT75` fait échouer la suite
  plutôt que de survivre à la relecture.

### Critères

- [ ] **AC-1 — Garde structurelle backend.** Un test échoue si `"DT75"` ou `'DT75'`
      apparaît sous `backend/app/`, hors : `auth/config.py` (valeur par défaut de
      `default_dt`), `app/mocks/**`, et les docstrings/commentaires d'exemple. Le test
      **nomme le fichier et la ligne** fautifs.
- [ ] **AC-2 — Garde structurelle frontend.** Le même test échoue si `'DT75'` apparaît
      sous `frontend/projects/admin/src/` ou `frontend/projects/form/src/`, hors fichiers
      `*.spec.ts`. Aucune autre exception.
- [ ] **AC-3 — Bénévole connu.** Étant donné un bénévole `actif` en base avec
      `dt = "DT92"`, quand il s'authentifie, alors `current_user.dt == "DT92"` —
      inchangé, et ce test fixe le comportement déjà correct.
- [ ] **AC-4 — Gestionnaire d'amorçage.** Étant donné `EMAIL_GESTIONNAIRE_DT = x@…` et
      `DEFAULT_DT = "DT92"`, quand `x@…` s'authentifie **sans** être au référentiel,
      alors `current_user.dt == "DT92"` et `role == "Gestionnaire DT"`. Aucun littéral
      n'intervient.
- [ ] **AC-5 — Inconnu refusé.** Étant donné un email `@croix-rouge.fr` absent du
      référentiel, qui **n'est ni** le gestionnaire d'amorçage **ni** le super admin,
      quand il s'authentifie, alors la requête reçoit **401** et le refus est journalisé
      avec l'email. Aucun `User` n'est construit.
- [ ] **AC-6 — Super admin.** Étant donné `SUPER_ADMIN_EMAIL = s@…` absent du
      référentiel, quand `s@…` s'authentifie, alors il obtient un `User` avec
      `dt == DEFAULT_DT` — sans quoi le super admin ne pourrait pas atteindre le menu
      global qu'il est le seul à pouvoir utiliser.
- [ ] **AC-7 — Amorçage du référentiel mock.** Quand `USE_MOCKS=true`, l'amorçage écrit
      dans `DEFAULT_DT`, pas dans une délégation codée en dur.
- [ ] **AC-8 — Frontend admin.** Chaque appel des six services et composants listés
      ci-dessous porte la délégation de l'utilisateur connecté. Vérifié par spec Angular
      avec un `AuthService` simulé rendant `dt = "DT92"` : l'URL appelée contient `DT92`.
- [ ] **AC-9 — Frontend form.** L'interface `User` de l'app terrain porte `dt`, et les
      trois composants de réservation l'utilisent. Même vérification qu'AC-8.
- [ ] **AC-10 — Aucun repli silencieux.** Aucun `?? 'DT75'` ni `|| 'DT75'` ne subsiste :
      un utilisateur authentifié **a toujours** une délégation (garanti par AC-5), donc
      un repli masquerait une anomalie au lieu de la révéler.
- [ ] **AC-11 — Variables du super admin injectées.** `SUPER_ADMIN_EMAIL`,
      `SUPER_ADMIN_DT_ID` et `SUPER_ADMIN_DT_NUMERIC_ID` figurent dans
      `deploy/cloudrun-api.yaml.tpl` et dans `deploy/deploy.env.example`. Vérifié par
      `test_cloudrun_template.py`, qui exige déjà que toute variable injectée soit lue.

## Inputs & outputs

### La résolution de la délégation, par ordre de priorité

`AuthService.get_user_from_token(token_data, redis_store) -> User` — trois chemins, dans
cet ordre :

| # | Condition | `dt` retenu | Rôle |
|---|---|---|---|
| 1 | `email == auth_settings.dt_manager_email` | `auth_settings.default_dt` | `Gestionnaire DT` |
| 2 | `get_benevole_by_email(email)` renvoie un bénévole `actif` | **`benevole.dt`** | dérivé de `fonctions_dt` / `responsable_ul` |
| 3 | `email == auth_settings.super_admin_email` | `auth_settings.default_dt` | `Bénévole`, `is_super_admin=True` |
| — | aucun des trois | **aucun** — `HTTPException(401)` | — |

Un bénévole trouvé mais `statut != "actif"` continue de produire un **401** avec son
nivol journalisé : comportement existant, inchangé.

### Signatures touchées

```python
# app/auth/service.py — les deux littéraux disparaissent
dt=self.default_dt          # chemin 1, était dt="DT75"
raise HTTPException(401, …) # chemin 4, était un User avec dt="DT75"

# app/main.py:147 — amorçage mock
redis_store = RedisService(redis_client=cache.client, dt=auth_settings.default_dt)

# app/routers/config.py:611 — repli à supprimer
dt_id = current_user.dt      # était `current_user.dt or "DT75"`
```

### Frontend

```typescript
// Les deux applications : une seule source, l'utilisateur connecté.
protected readonly dt = computed(() => this.authService.currentUser()?.dt);
```

`form/src/app/models/user.model.ts` **gagne le champ `dt: string`** — il ne l'a pas,
alors que le backend le renvoie. C'est ce qui empêche aujourd'hui les six occurrences de
l'app terrain de lire la valeur.

### Fichiers et lignes concernés

**Backend (3 littéraux décisionnels + 1 repli)**

| Fichier | Ligne | Nature |
|---|---|---|
| `app/auth/service.py` | 52 | `dt="DT75"` — gestionnaire d'amorçage |
| `app/auth/service.py` | 116 | `dt="DT75"` — repli inconnu, **supprimé** au profit d'un 401 |
| `app/main.py` | 147 | `dt="DT75"` — amorçage du référentiel mock |
| `app/routers/config.py` | 611 | `current_user.dt or "DT75"` — repli |

Les occurrences de `app/routers/sync.py` (6) sont des **exemples de docstring**
(`dt: DT identifier (e.g., "DT75")`) : hors périmètre, et l'exception doit être portée
par la garde d'AC-1 sans autoriser le code.

**Frontend admin (12 occurrences, 8 fichiers)**

`services/api-keys.service.ts:16` · `services/stats.service.ts` ·
`services/unite-locale.service.ts` · `services/vehicle-import.service.ts:97,119` ·
`components/dt-admin/dt-admin.component.ts:302` ·
`components/calendar-view/calendar-view.component.ts:42,76` ·
`vehicles/vehicle-edit/vehicle-edit.ts:242,248` ·
`pages/config/config-page.component.ts:32` ·
`pages/configuration-ul/configuration-ul.component.ts:46`

**Frontend form (6 occurrences, 3 fichiers)**

`features/reservations/reservation-list.component.ts` ·
`reservation-form.component.ts` · `reservation-detail.component.ts`

⚠️ `vehicle-edit.ts:242` est un cas à part : `['DT75', ...unites_locales]` construit une
**liste de choix** où la délégation figure à côté de ses UL. Le littéral devient la
délégation de l'utilisateur ; le libellé affiché reste à décider (le code DT n'est pas un
nom d'unité).

### Clés Redis

Aucune clé nouvelle, aucune migration. Les lectures existantes restent
`{dt}:benevoles:by_email` et `{dt}:benevole:{nivol}`, avec `{dt}` désormais
systématiquement issu de la session ou du réglage.

## Behavior & edge cases

**Chemin nominal.** Un bénévole synchronisé se connecte ; `dt` vient de son document
Redis, écrit par la synchronisation depuis le segment `{dt}` de l'URL d'appel. Rien ne
change.

| Cas limite | Comportement attendu |
|---|---|
| Bénévole `inactif` | 401, nivol journalisé — existant |
| Email inconnu, ni gestionnaire ni super admin | **401** (nouveau : renvoyait un `User` sans périmètre) |
| `EMAIL_GESTIONNAIRE_DT` non renseigné | le chemin 1 ne peut pas correspondre ; un inconnu est donc refusé. ⚠️ Sur une délégation neuve, **personne** ne peut se connecter : c'est le rôle du super admin (chemin 3) d'ouvrir la porte |
| `SUPER_ADMIN_EMAIL` non renseigné | chemin 3 inopérant. C'est l'état de **tous** les environnements déployés aujourd'hui — d'où AC-11 |
| Bénévole en base avec `dt` vide | `current_user.dt` est vide ; le frontend n'a plus de repli. Traité comme une anomalie de donnée : 401, journalisé — sinon l'utilisateur navigue dans une délégation indéterminée |
| Utilisateur non encore résolu côté frontend | `dt` est un `computed` sur le signal utilisateur : les écrans n'émettent aucun appel tant qu'il est absent. Le cas « résolu sans `dt` » est impossible par AC-5 |
| Bénévole dont l'UL appartient à une autre délégation | non détecté par cette tranche — voir « Prévoir la chaîne `Id Structure` » |

### Prévoir la chaîne `Id Structure` (sans l'implémenter)

Le référentiel des structures apportera, pour chaque UL, son `id_structure` et
l'`id_structure` de sa **délégation parente**. Les bénévoles portent déjà leur
`ul_id_structure` — transporté, validé, stocké depuis le 2026-08-29, et **pas encore
exploité**.

Cette chaîne permettra de **dériver** la délégation d'un bénévole
(`ul_id_structure` → UL → délégation parente) au lieu de la tenir du segment d'URL de la
synchronisation, et surtout de **détecter le désaccord** entre les deux — un bénévole
poussé dans `/api/sync/DT75/benevoles` alors que son UL appartient à la DT92.

**Ce que cette tranche doit garantir pour que ce soit possible plus tard** : ne pas
introduire de chemin où `dt` serait déduit autrement que de l'utilisateur ou du réglage,
et conserver `ul_id_structure` intact à l'écriture comme à la lecture. C'est le cas.

## Out of scope

- **L'import du référentiel des structures** et la dérivation effective de la délégation
  par la chaîne `Id Structure` — tranche 2.
- Le **menu d'administration globale**, le registre des délégations et l'Apps Script
  d'amorçage — tranche 3.
- La restriction de l'application **admin** aux seuls gestionnaires et responsables
  véhicules (décision D5) : cette tranche refuse les **inconnus**, elle ne filtre pas les
  bénévoles connus.
- Le constat **C3** — trois routers prenant le `dt` d'un paramètre d'URL. Cette tranche ne
  doit pas en ajouter ; les corriger est un autre chantier.
- Tout renommage, migration ou suppression de délégation.

## Test plan

**Garde structurelle** — `backend/tests/test_pas_de_dt_en_dur.py` *(nouveau)*

Scanne `backend/app/`, `frontend/projects/admin/src/`, `frontend/projects/form/src/`.
Signale chaque `DT75` littéral avec son chemin et sa ligne. Exceptions **explicites et
justifiées dans le code du test** : `auth/config.py` (défaut du réglage), `app/mocks/**`,
`*.spec.ts`, et les lignes de commentaire ou docstring. Écrit **avant** les corrections :
il doit échouer sur l'état actuel, avec les 21 emplacements listés.

**Authentification** — `backend/tests/test_auth_dt_resolution.py` *(nouveau)*

| Test | Couvre |
|---|---|
| `test_benevole_actif_garde_sa_delegation` | AC-3, avec `dt="DT92"` — jamais `DT75`, pour que le test échoue si un défaut réapparaît |
| `test_gestionnaire_amorcage_prend_la_delegation_par_defaut` | AC-4, avec `DEFAULT_DT="DT92"` |
| `test_email_inconnu_est_refuse_en_401` | AC-5, et vérifie que l'email est journalisé |
| `test_super_admin_inconnu_du_referentiel_passe` | AC-6 |
| `test_benevole_sans_delegation_est_refuse` | cas limite `dt` vide |
| `test_benevole_inactif_reste_refuse` | non-régression du comportement existant |

**Frontend** — une spec par service ou composant modifié, avec `AuthService` simulé
rendant `dt = "DT92"` : l'URL appelée doit contenir `DT92`. Le modèle du plus proche
existant est `api-keys.service.spec.ts`, déjà en place.

**Non-régression** — les quatre suites doivent rester vertes : backend `657 passed`,
`ng test admin` 39, `ng test form` 11, Playwright 30.

⚠️ **À éprouver en exécution avant déploiement** : se connecter avec un compte
`@croix-rouge.fr` **absent** du référentiel et constater le 401 et son message. C'est le
seul changement visible de cette tranche, et un test ne dira pas si le message est
compréhensible.

## Dependencies & risks

**Aucune dépendance nouvelle.** `default_dt`, `super_admin_email` et `dt_manager_email`
existent déjà dans `app/auth/config.py` ; `get_redis_service` utilise déjà
`auth_settings.default_dt` (`app/auth/dependencies.py:53`). Rien à vérifier côté versions.

| Risque | Portée |
|---|---|
| **Le refus des inconnus enferme quelqu'un dehors** | Le plus dangereux. Aujourd'hui n'importe quel `@croix-rouge.fr` entre. Les 4546 bénévoles synchronisés sont en base, donc non concernés — mais un bénévole arrivé après la dernière synchronisation l'est. Atténuation : le message doit dire d'attendre la synchronisation, et la synchro est horaire |
| **`SUPER_ADMIN_EMAIL` absent des environnements déployés** | Si AC-11 n'est pas faite, le chemin 3 n'existe pas et la seule porte d'entrée d'une délégation neuve est `EMAIL_GESTIONNAIRE_DT` |
| **18 corrections frontend sans filet** | Le filet unitaire frontend est mince (50 tests pour ~100 composants). D'où la garde structurelle **écrite d'abord** : elle ne prouve pas la correction, mais elle prouve l'absence de littéral |
| **`vehicle-edit.ts:242`** | Le seul cas où le littéral n'est pas un identifiant d'appel mais une **entrée de liste de choix** affichée à l'utilisateur. Une correction mécanique y afficherait un code technique |

## Suite

`/plan-feature dt-depuis-utilisateur-authentifie` — en commençant par la garde
structurelle, qui doit échouer avant de corriger quoi que ce soit.
