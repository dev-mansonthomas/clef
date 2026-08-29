# Administration globale des délégations et amorçage Google

> Tranche 3 du chantier multi-délégation. Cadrage : `docs/product/brief.md`.
> Décisions et tranches : `docs/specs/multi-delegation.md`.
> Tranches précédentes : `docs/specs/dt-depuis-utilisateur-authentifie.md` (1),
> `docs/specs/import-referentiel-structures.md` (2).
>
> ⚠️ Le titre historique de cette tranche parlait d'un « Apps Script d'amorçage ».
> **Il n'y en aura pas** : la décision D6 a été révisée le 2026-08-29 — la délégation OAuth
> du gestionnaire DT existe déjà et le backend crée les ressources Google lui-même.

## Purpose

Une délégation ne peut aujourd'hui entrer dans CLEF que par une variable d'environnement
et un redéploiement : `EMAIL_GESTIONNAIRE_DT` désigne un unique gestionnaire, et
`DEFAULT_DT` une unique délégation. Cette tranche donne au super admin un **écran
d'administration globale** — la page `/super-admin` est aujourd'hui un gabarit de 11
lignes affichant « Page en construction » — pour déclarer une délégation, désigner son
gestionnaire, et suivre son état d'amorçage.

Elle referme aussi la boucle Google. Le parcours de consentement étendu
(`/auth/authorize-dt` → `/auth/callback-dt`, scopes `drive`, `calendar`, `gmail.send`,
jeton de rafraîchissement chiffré par KMS) est **fonctionnel mais enfoui** dans un écran
d'administration : un gestionnaire qui ne l'ouvre jamais n'accorde jamais rien, et les
fonctions Drive, Gmail et Calendar de sa délégation échouent sans qu'il sache pourquoi.
Le consentement devient une **invitation qu'on ne peut pas manquer**, déclenchée juste
après sa connexion, et l'état de l'autorisation devient une donnée lisible plutôt qu'une
surprise au premier dépôt de document par un tiers.

## Décisions prises pour cette tranche

| # | Décision | Pourquoi |
|---|---|---|
| F1 | **Le dossier racine doit être dans un Drive partagé.** L'URL fournie par le gestionnaire est refusée si elle désigne un dossier de son Drive personnel | Correction du propriétaire : l'arborescence **est déjà** dans un Drive partagé, et c'est structurel — un Drive personnel plafonne à **5 Go, courriels inclus**, ce qui ne tiendra pas. Conséquence heureuse : les fichiers n'appartiennent pas au gestionnaire, donc son départ ne déplace rien et le jeton n'est plus qu'un laissez-passer interchangeable. Vérifié : `drive_service.py` passe **déjà** `supportsAllDrives` sur ses 8 appels — aucun changement de client |
| F2 | **Création minimale** : code de délégation + email du gestionnaire, puis le gestionnaire complète | Décision du propriétaire. Une création « complète » dépendrait du consentement d'un tiers absent : elle échouerait à moitié par construction. Ici, une seule chose peut échouer à la fois |
| F3 | **Consentement incrémental, gestionnaire DT seulement**, déclenché juste après sa connexion | Tranché le 2026-08-29. Demander `drive` et `gmail.send` à tout utilisateur serait disproportionné — un bénévole terrain n'en a aucun usage — et un scope Drive large sur tout le domaine attire la procédure de vérification Google |
| F4 | **La délégation d'un utilisateur est résolue par balayage pipeliné des délégations en service**, sans nouvel index global | `{dt}:benevoles:by_email:{email}` est une clé simple : un `MGET` sur N délégations est **un seul aller-retour**. D7 le disait déjà (« un balayage tiendrait à 3 délégations, pas à 108 »). Un index global email → délégation serait une seconde source de vérité à maintenir — la classe de bug qui a rendu nécessaire `backfill_benevole_email_index.py` — et il ferait sortir 4546 adresses du cloisonnement par préfixe |
| F5 | **Rafraîchissement de fond du jeton** par le scheduler APScheduler existant | Son apport n'est pas le renouvellement — `get_access_token` rafraîchit déjà à l'usage — mais la **détection précoce d'une révocation**. Sans lui, on l'apprend au moment où un tiers dépose un document : au pire moment, et pour la mauvaise personne |
| F6 | Le registre des délégations **n'ajoute aucune clé globale** : il s'appuie sur `clef:st:*` et son drapeau `utilise_clef`, posés par la tranche 2 | D7 prévoyait un registre séparé avec un index par email de gestionnaire. La tranche 2 l'a rendu inutile : la structure porte déjà son code, son libellé et son drapeau. Moins de clés hors préfixe, donc moins d'exceptions à l'invariant d'isolation |

## Préalable — hors de cette spec, et bloquant

⚠️ **`/auth/callback-dt` accepte l'identité d'un paramètre d'URL non signé.** La route n'a
aucun guard, et `state` — que `google_oauth.py` documente comme « State parameter for CSRF
protection » — est utilisé comme identité : `store_tokens(dt_id=…, email=state, …)`
(`app/auth/routes.py:318-380`). Le `client_id` est public et le `redirect_uri` est déclaré
en console : un tiers construit l'URL de consentement, consent avec **son** compte, et
rejoue le retour avec `state=<email du gestionnaire>`. Le jeton délégué de la délégation
devient le sien, écrasant le légitime — donc les dossiers Drive créés par CLEF et les
documents déposés par les bénévoles atterrissent dans son Drive, et CLEF envoie des
courriels sous son compte. `dt_id = "DT75"` étant codé en dur ligne 351, la cible est
toujours DT75.

**Corrigé à part, avant cette tranche** (décision du propriétaire) : branche dédiée, email
dérivé de l'`id_token` du retour Google, `state` réduit à un nonce imprévisible lié à la
session, et `require_dt_manager` sur le rappel. Voir `docs/TODO.md` **C4**. Cette spec
part d'un flux assaini et n'en refait pas la démonstration.

## User stories / acceptance criteria

- En tant que **super admin**, je déclare une délégation avec son code et l'email de son
  gestionnaire, et je vois où elle en est de son amorçage.
- En tant que **gestionnaire DT** d'une délégation neuve, je me connecte et l'application
  me demande d'accorder l'accès Drive, Calendar et Gmail — je ne peux pas passer à côté.
- En tant que **gestionnaire DT**, si je colle l'URL d'un dossier de mon Drive personnel,
  CLEF refuse et m'explique qu'il faut un Drive partagé.
- En tant que **responsable véhicule**, quand je dépose un document et que le gestionnaire
  n'a pas accordé l'accès, je lis « le gestionnaire n'a pas encore accordé l'accès Drive »
  et non une erreur Google.
- En tant que **bénévole de la DT92**, je me connecte et je vois les données de la DT92,
  alors qu'aucune variable d'environnement ne mentionne ma délégation.

### Critères — registre et résolution de la délégation

- [ ] **AC-1 — Résolution par balayage pipeliné.** Étant donné DT75 et DT92 en service et
      un bénévole de DT92, quand il s'authentifie, alors `current_user.dt == "DT92"`, et la
      résolution consomme **un seul aller-retour** Redis (un `MGET` sur les clés
      `by_email` des délégations en service). Vérifié en comptant les appels sur un client
      instrumenté.
- [ ] **AC-2 — Ordre déterministe et collision signalée.** Si le même email est connu de
      **deux** délégations en service, alors la résolution retient celle dont le code est
      le plus petit en ordre lexicographique **et** journalise un `WARNING` nommant les
      deux. Un bénévole ne doit pas changer de délégation au gré de l'ordre d'un `SMEMBERS`.
- [ ] **AC-3 — Gestionnaire hors référentiel.** Étant donné DT92 dont le gestionnaire
      déclaré est `g@croix-rouge.fr`, absent du référentiel bénévoles, quand il
      s'authentifie, alors `dt == "DT92"`, `role == "Gestionnaire DT"`. La résolution passe
      par `clef:st:{id}.gestionnaire_email`, pas par `EMAIL_GESTIONNAIRE_DT`.
- [ ] **AC-4 — `EMAIL_GESTIONNAIRE_DT` cesse d'être une identité.** Le défaut en dur
      `thomas.manson@croix-rouge.fr` (`app/auth/config.py`) devient `""`. Un test échoue si
      une adresse électronique littérale réapparaît comme valeur par défaut dans
      `app/auth/config.py`. La variable reste lue **uniquement** comme amorçage de
      `DEFAULT_DT` tant qu'aucune délégation n'est déclarée.
- [ ] **AC-5 — Périmètre déduit, plus écrit.** `ul="DT Paris"` et `perimetre="DT Paris"`
      (`app/auth/service.py`) disparaissent au profit du libellé de la structure
      (`clef:st:{id}.nom`, soit `DT DE PARIS`). Un test échoue sur tout littéral
      `"DT Paris"` sous `backend/app/` hors mocks : c'est un codage en dur que la garde
      `DT75` de la tranche 1 **ne voit pas**.
- [ ] **AC-6 — Aucune nouvelle clé globale.** Un test énumère les préfixes non préfixés par
      une délégation écrits par `backend/app/` et échoue si un autre que `clef:st:*`
      apparaît. L'exception à l'invariant d'isolation reste bornée à un seul espace de noms.

### Critères — création d'une délégation

- [ ] **AC-7 — Création minimale.** `POST /admin/super/delegations` avec
      `{"code": "DT92", "gestionnaire_email": "g@croix-rouge.fr"}` par le super admin,
      alors : `clef:st:97.utilise_clef` passe à `true`, `clef:st:97.gestionnaire_email` est
      écrit, `DT92:configuration` existe avec `dt`, `nom` et `gestionnaire_email`
      renseignés, et `DT92:ul:idx` compte les 30 UL projetées depuis `clef:st:ul:97`.
      Rien d'autre n'est écrit — aucun appel Google.
- [ ] **AC-8 — Code inconnu du référentiel refusé.** `{"code": "DT99"}` absent de
      `clef:st:code` → **404** nommant le code, et **aucune** écriture. On ne crée pas une
      délégation qui n'existe pas dans le référentiel national.
- [ ] **AC-9 — Code mal formé refusé.** `dt92`, `DT 92`, `92`, `DTÉ` → **422**. La règle
      est `^DT[A-Z0-9]+$`, la même qu'à l'import (D2).
- [ ] **AC-10 — Email hors domaine refusé.** Un `gestionnaire_email` ne finissant pas par
      `@croix-rouge.fr` → **422**. Un gestionnaire hors domaine ne pourrait pas s'y
      connecter, et son jeton Google ne serait pas celui de l'organisation.
- [ ] **AC-11 — Création idempotente.** Rejouée sur une délégation déjà en service, la
      création **ne réinitialise rien** : `utilise_clef` reste `true`, la configuration
      existante est conservée, les UL ne sont pas réécrites, et la réponse porte
      `deja_en_service: true`. Un `POST` deux fois cliqué ne doit pas remettre une
      délégation à zéro.
- [ ] **AC-12 — Réservé au super admin.** Un gestionnaire DT, un responsable UL et un
      bénévole reçoivent **403** sur les quatre routes de `/admin/super/delegations`.
- [ ] **AC-13 — Retrait sans destruction.** `DELETE /admin/super/delegations/{code}` passe
      `utilise_clef` à `false` et **ne supprime aucune** clé préfixée : les données de la
      délégation restent lisibles, elle cesse simplement d'être servie. La suppression
      définitive n'existe pas dans cette tranche.
- [ ] **AC-14 — L'écran global liste et raconte.** `GET /admin/super/delegations` renvoie,
      pour chaque délégation en service : code, libellé, email du gestionnaire, état du
      consentement (`authorized`, `authorized_at`, `expires_at`), présence et nature du
      dossier racine Drive (`partage: bool`), nombre d'UL, nombre de bénévoles actifs,
      horodatage de la dernière synchronisation. Une délégation dont le consentement
      manque est **visuellement distincte** dans l'écran.

### Critères — consentement et amorçage Google

- [ ] **AC-15 — Invitation qu'on ne peut pas manquer.** Étant donné un gestionnaire DT dont
      `GET /auth/dt-authorization-status` renvoie `authorized: false`, quand il arrive sur
      le tableau de bord, alors une invitation **bloquante et non renvoyable** propose
      d'accorder l'accès. Elle n'apparaît **jamais** pour un autre rôle : vérifié par spec
      Angular sur les quatre rôles.
- [ ] **AC-16 — Le statut porte la délégation de l'utilisateur.** Les trois routes du flux
      (`/auth/authorize-dt`, `/auth/dt-authorization-status`,
      `/auth/revoke-dt-authorization`) prennent `current_user.dt` : les quatre littéraux
      `dt_id = "DT75"` de `app/auth/routes.py` (lignes 351, 353, 398, 421) disparaissent.
      ⚠️ Ces quatre-là **manquent à l'inventaire de la tranche 1**, qui n'en listait que
      trois pour tout le backend.
- [ ] **AC-17 — Drive partagé exigé.** Quand le gestionnaire enregistre un
      `drive_folder_url` désignant un dossier **hors** Drive partagé (`files.get` ne renvoie
      pas de `driveId`), alors **400** avec un message explicite — « ce dossier appartient à
      un Drive personnel (5 Go, courriels inclus) ; utilisez un Drive partagé » — et
      **aucune** synchronisation d'arborescence n'est lancée. Le contrôle précède
      l'écriture de la configuration.
- [ ] **AC-18 — Contrôle impossible sans jeton.** Si le contrôle d'AC-17 ne peut pas
      s'exécuter faute d'autorisation, alors la réponse est **409** avec « le gestionnaire
      n'a pas encore accordé l'accès Drive », et non un 400 laissant croire que l'URL est
      fautive. Distinguer « refusé » de « pas pu conclure » : c'est la leçon des sondes de
      `01-gcp-deploy.sh`.
- [ ] **AC-19 — Absence de jeton lisible partout.** Les trois chemins qui dépendent du
      jeton — dépôt de document, dépôt de photo, dossier de réparation — renvoient **409**
      et le message d'AC-18 quand `get_access_token` rend `None`, au lieu de propager une
      erreur Google. Un test par chemin.
- [ ] **AC-20 — Rafraîchissement de fond.** Une tâche APScheduler parcourt les délégations
      en service et rafraîchit chaque jeton avant échéance. Un rafraîchissement qui échoue
      **n'efface pas** le jeton : il écrit `revocation_suspectee_le` dans son document, ce
      que l'écran global et l'écran d'administration DT affichent. Le passage suivant
      réessaie ; deux échecs consécutifs font passer l'état à `revoque`.
- [ ] **AC-21 — Révoquer révoque chez Google.** `POST /auth/revoke-dt-authorization`
      appelle `https://oauth2.googleapis.com/revoke` **avant** de supprimer la clé locale.
      Aujourd'hui elle ne fait que `DELETE` : l'autorisation restait vivante côté Google,
      donc « révoqué » était faux. Si l'appel échoue, la clé locale est tout de même
      supprimée et un `WARNING` le dit — l'accès de CLEF cesse dans les deux cas.
- [ ] **AC-22 — L'arborescence est rejouable.** Relancer l'amorçage sur une délégation déjà
      amorcée ne crée **aucun** doublon de dossier : `get_or_create_folder` est idempotent,
      et le test le prouve en comptant les dossiers avant et après.

## Inputs & outputs

### Le document de structure gagne sa moitié « organisation »

Écrite par la création d'une délégation, jamais par l'import du référentiel (tranche 2,
E6) :

```python
# app/models/structure.py — champs ajoutés
class Structure(BaseModel):
    ...
    utilise_clef: bool = False              # existant (tranche 2)
    gestionnaire_email: Optional[str] = None
    en_service_depuis: Optional[str] = None
    retire_le: Optional[str] = None
```

### Routes

```
GET    /admin/super/delegations            → List[DelegationEtat]      (super admin)
POST   /admin/super/delegations            → DelegationEtat            (super admin)
PATCH  /admin/super/delegations/{code}     → DelegationEtat            (super admin)
DELETE /admin/super/delegations/{code}     → 204, utilise_clef = false (super admin)
```

```python
class DelegationCreate(BaseModel):
    code: str                    # ^DT[A-Z0-9]+$, doit exister dans clef:st:code
    gestionnaire_email: str      # @croix-rouge.fr

class DelegationEtat(BaseModel):
    code: str
    id_structure: str
    nom: str                     # libellé du référentiel : « DT DE PARIS »
    gestionnaire_email: Optional[str]
    en_service_depuis: Optional[str]
    deja_en_service: bool = False
    # Consentement Google
    autorise: bool
    autorise_le: Optional[str]
    autorise_pour: Optional[str]      # email réellement porteur du jeton
    revocation_suspectee_le: Optional[str]
    # Ressources
    drive_racine_id: Optional[str]
    drive_racine_partage: Optional[bool]   # None = non vérifiable faute de jeton
    # Volumétrie
    uls: int
    benevoles_actifs: int
    derniere_synchro_benevoles: Optional[str]
```

### Résolution de la délégation d'un email (F4)

```python
# app/services/delegations_service.py (nouveau)
async def delegations_en_service() -> List[Structure]:
    """Structures de type DT portant utilise_clef == True, triées par code."""

async def resolve_delegation_par_email(email: str) -> Optional[str]:
    """Code de la délégation qui connaît cet email, ou None.

    Un seul aller-retour : MGET sur `{code}:benevoles:by_email:{email}` pour chaque
    délégation en service. Voir F4 pour le refus d'un index global.
    """
```

Point d'insertion : `app/auth/dependencies.py:_referentiel_store()`, qui construit
aujourd'hui un `RedisService` sur `auth_settings.default_dt`. Il devient :

```python
code = await resolve_delegation_par_email(email) \
       or await gestionnaire_de(email) \
       or auth_settings.default_dt      # amorçage seulement
return RedisService(redis_client=cache.client, dt=code)
```

⚠️ `_referentiel_store()` ne reçoit pas l'email aujourd'hui : sa signature change, et
`get_current_user` doit résoudre le jeton **avant** de choisir le magasin. C'est le seul
réordonnancement structurel de cette tranche.

### Clés Redis

| Clé | Type | Statut |
|---|---|---|
| `clef:st:{id}` | JSON | **existante** (tranche 2), gagne 3 champs |
| `{dt}:configuration` | JSON | existante, écrite à la création |
| `{dt}:ul:{id}`, `{dt}:ul:idx` | JSON, SET | existantes (tranche 2), projetées à la création |
| `{dt}:oauth:mgr` | STRING | **renommée** depuis `{dt}:oauth:dt_manager_tokens` (E3), gagne `revocation_suspectee_le` et `etat` |
| `clef:oauth:nonce:{nonce}` | STRING, TTL 600 s | **nouvelle**, posée par le correctif préalable (C4) ; nommée ici pour mémoire |

⚠️ Renommer `{dt}:oauth:dt_manager_tokens` **invalide le jeton existant de DT75** : le
gestionnaire doit reconsentir une fois. C'est acceptable — le parcours dure quinze
secondes — mais doit être annoncé, pas découvert. La migration `RENAME` est aussi
possible ; à trancher au plan.

## Behavior & edge cases

**Chemin nominal.** Le super admin ouvre `/super-admin`, saisit `DT92` et l'email du
gestionnaire. CLEF vérifie que `DT92` existe dans `clef:st:code`, écrit
`utilise_clef: true`, `gestionnaire_email`, une configuration minimale, et projette les
30 UL. Le gestionnaire se connecte : la résolution le trouve par
`clef:st:97.gestionnaire_email`, il obtient `dt="DT92"` et le rôle `Gestionnaire DT`. Le
tableau de bord lui présente l'invitation ; il consent ; le jeton est chiffré et stocké.
Il colle l'URL d'un dossier de Drive partagé ; CLEF vérifie le `driveId`, écrit la
configuration et lance l'arborescence.

| Cas limite | Comportement attendu |
|---|---|
| Code absent de `clef:st:code` | 404, aucune écriture (AC-8). Si le référentiel n'a jamais été importé, le message le dit — sinon on conclurait à tort que le code est faux |
| Référentiel des structures absent | Les routes de création répondent **503** avec « référentiel des structures non importé ». Sans lui, ni le libellé ni les UL ne sont connus |
| Création rejouée | Aucune réinitialisation, `deja_en_service: true` (AC-11) |
| Retrait d'une délégation | `utilise_clef: false`, aucune clé supprimée. Ses utilisateurs cessent d'être résolus, donc de se connecter (tranche 1 : inconnu → 401) |
| Le gestionnaire déclaré est aussi bénévole d'une **autre** délégation | Le chemin gestionnaire l'emporte, et un `WARNING` nomme les deux. Cas réel : un cadre de la DT75 bénévole en UL 92 |
| Deux délégations connaissent le même email | Ordre lexicographique, `WARNING` (AC-2) |
| Gestionnaire qui ne consent jamais | L'invitation reste ; les fonctions Google renvoient 409 avec un message qui le nomme (AC-19). Aucune fonction ne tombe en 403 Google |
| Consentement sans `refresh_token` | Google n'en renvoie pas si l'utilisateur a déjà accordé : le comportement existant lève une erreur explicite (« révoquez l'accès puis réessayez »). Conservé |
| URL de Drive personnel | 400 explicite (AC-17) |
| URL d'un dossier auquel le jeton n'a pas accès | 403 relayé en **404** côté CLEF avec « dossier introuvable ou non partagé avec le gestionnaire » : ne pas révéler l'existence d'un dossier hors périmètre |
| Jeton révoqué chez Google | Le rafraîchissement de fond le constate, `revocation_suspectee_le` puis `revoque` après deux échecs. Le jeton **n'est pas effacé** au premier échec : une panne réseau ne doit pas coûter un reconsentement |
| Gestionnaire remplacé | `PATCH` change `gestionnaire_email`. Le jeton du prédécesseur reste valide jusqu'à révocation — **et les fichiers ne bougent pas**, étant dans un Drive partagé (F1). C'est précisément ce que ce choix achète |
| Scheduler désactivé (`SCHEDULER_ENABLED=false`) | Pas de rafraîchissement de fond ; le rafraîchissement à l'usage subsiste. L'écran global doit dire que la surveillance est inactive, sinon « aucune révocation détectée » se lit à tort comme « tout va bien » |
| `USE_MOCKS=true` | Le consentement est simulé : le statut renvoie `autorise: true` et le contrôle de Drive partagé rend `true`. Aucun appel réseau |

## Out of scope

- **Le correctif de `/auth/callback-dt`** : chantier séparé et préalable (C4).
- **La création de l'arborescence Drive elle-même** : elle **existe** —
  `PATCH /api/config` extrait le `folder_id`, puis
  `vehicle_document_service.ensure_vehicle_trees_for_all_vehicles` la construit en tâche de
  fond avec suivi de progression. Cette tranche y ajoute le contrôle de Drive partagé et
  les messages d'absence de jeton, elle ne la réécrit pas.
- **Créer le Drive partagé** : geste Workspace, hors application. CLEF exige et vérifie, il
  ne provisionne pas.
- **Unifier les deux familles de clients Drive.** ⚠️ Deux classes portent le **même nom
  `DriveService`** : `app/services/drive.py` (abstraite, service account, implémentée par
  `drive_real.py`) et `app/services/drive_service.py` (déléguée, jeton du gestionnaire).
  Trois modules utilisent la déléguée (`dossiers_reparation.py`,
  `vehicle_photo_service.py`, `vehicle_document_service.py`) et trois la famille service
  account (`routers/upload.py`, `upload_service.py`, `carnet_bord_service.py`). Cette
  seconde famille tombe sous la même cause structurelle que **N13** — à vérifier par
  exécution, ce n'est pas mesuré. Chantier propre.
- **Les cas d'usage U1 et U2** (véhicule vendu, réservation inter-délégation) et le
  renommage **U3**.
- **Migrer les données de DT75** : elle est déjà en service, elle reçoit seulement son
  drapeau et son `gestionnaire_email`.
- Toute suppression définitive de délégation, tout renommage de code.

## Test plan

| Fichier | Couvre |
|---|---|
| `tests/test_delegations_resolution.py` *(nouveau)* | AC-1 à AC-3 — deux délégations peuplées dans `fakeredis`, un seul aller-retour compté sur un client instrumenté, collision, gestionnaire hors référentiel |
| `tests/test_pas_de_perimetre_en_dur.py` *(nouveau)* | AC-4, AC-5 — littéraux `"DT Paris"` et adresse électronique par défaut. **Écrit d'abord**, doit échouer sur l'état actuel |
| `tests/test_cles_globales_bornees.py` *(nouveau)* | AC-6 — aucun préfixe global autre que `clef:st:*` |
| `tests/test_delegations_crud.py` *(nouveau)* | AC-7 à AC-14 — création, refus (404/422), idempotence, retrait, guards sur les quatre routes, forme de `DelegationEtat` |
| `tests/test_dt_authorization_delegation.py` *(nouveau)* | AC-16 — les trois routes prennent `current_user.dt` ; test paramétré sur `DT75` et `DT92` |
| `tests/test_drive_partage.py` *(nouveau)* | AC-17, AC-18 — `files.get` simulé avec et sans `driveId`, et sans jeton (409) |
| `tests/test_absence_jeton_lisible.py` *(nouveau)* | AC-19 — les trois chemins, `get_access_token` rendant `None` |
| `tests/test_refresh_fond.py` *(nouveau)* | AC-20, AC-21 — échec unique puis double, non-effacement, appel à l'endpoint de révocation Google avant suppression locale |
| `tests/test_amorcage_idempotent.py` *(nouveau)* | AC-22 — comptage des dossiers avant/après |
| `tests/test_mock_parity.py` *(existant)* | échoue si une méthode nouvelle des services Drive/Gmail manque au double. Aucune action, mais c'est lui qui a rattrapé M16, M31 et M32 |
| `tests/test_env_example.py` *(existant)* | échoue tant que les variables nouvelles ne sont pas documentées |

**Frontend** — `super-admin.component.spec.ts` *(nouveau, la page est un gabarit)* : liste,
formulaire de création, distinction visuelle d'une délégation sans consentement.
`dashboard.component.spec.ts` *(étendu)* : l'invitation d'AC-15 apparaît pour le
gestionnaire DT non autorisé et **pour aucun autre rôle** — quatre cas.

**E2E** — un parcours Playwright avec backend mocké : le super admin crée `DT92`, la voit
listée sans consentement ; le gestionnaire se connecte et rencontre l'invitation.
⚠️ Vérifier les motifs de route des mocks contre les URL réelles avant d'écrire : trois
d'entre eux ne correspondaient à rien, et le symptôme était `ENOTFOUND backend` plus une
assertion qui échoue « sans raison ».

**Éprouver chaque garde par mutation** : remettre un `"DT Paris"`, un `dt_id = "DT75"`, une
adresse par défaut, une clé globale hors `clef:st:*`.

⚠️ **À éprouver en exécution, et rien ne le remplacera** :

1. Créer une **vraie** seconde délégation en dev et s'y connecter avec un compte qui n'est
   pas de la DT75. C'est le seul test du multi-délégation de bout en bout.
2. Coller l'URL d'un dossier de Drive **personnel** et lire le message d'AC-17.
3. Révoquer l'accès depuis la console Google, attendre un passage du scheduler, et vérifier
   que l'écran global l'affiche **avant** qu'un tiers ne dépose un document.

**Non-régression** : les quatre suites vertes.

## Dependencies & risks

**Aucune dépendance nouvelle.** `authlib`, `httpx`, `google-api-python-client`, APScheduler
et `kms_service` sont en place ; l'endpoint de révocation Google
(`https://oauth2.googleapis.com/revoke`) est un simple `POST` avec `token=`. Rien à
vérifier côté versions, donc pas de passage par Context7.

| Risque | Portée et atténuation |
|---|---|
| **Le réordonnancement de `get_current_user`** | Le plus dangereux de la tranche : la résolution de la délégation entre **sur le chemin d'authentification de chaque requête**. Une erreur y ferme l'application à tout le monde. Atténuations : la signature change de façon visible (le compilateur ne dira rien, mais tous les appelants sont dans un fichier) ; un repli sur `DEFAULT_DT` reste en dernier recours pour l'amorçage ; et le coût reste d'un aller-retour, mesuré |
| **Un seul jeton pour les actions de tous** | Quand un responsable véhicule dépose un document, l'écriture Drive se fait sous le compte du gestionnaire. Le Drive partagé (F1) règle la **propriété** des fichiers, pas la **traçabilité** : le Drive ne dira pas qui a déposé. À conserver côté CLEF, et c'est déjà le cas dans les métadonnées du document |
| **Renommage de `{dt}:oauth:dt_manager_tokens`** | Invalide le jeton de DT75 : un reconsentement de quinze secondes, à annoncer. Ou un `RENAME` en migration — à trancher au plan |
| **Le contrôle de Drive partagé exige un jeton valide** | Donc l'ordre du parcours est contraint : consentir **puis** déclarer l'URL. Un gestionnaire qui fait l'inverse doit lire un 409 clair, pas un 400 trompeur (AC-18) |
| **`SUPER_ADMIN_EMAIL` n'est injecté dans aucun environnement déployé** | Personne n'est super admin aujourd'hui : cette tranche serait **inatteignable**. La tranche 1 le corrige (son AC-11). Si elle ne l'a pas fait, cette tranche est bloquée avant sa première ligne |
| **Le rafraîchissement de fond dans Cloud Run à `minScale = 0`** | Une instance qui n'existe pas n'exécute aucun scheduler. La surveillance de révocation est donc **au mieux opportuniste** tant que `MIN_INSTANCES` vaut 0 — et c'est le cas. À écrire dans l'écran plutôt qu'à supposer : « surveillance active depuis … », non « aucune révocation » |
| **Deux classes `DriveService` homonymes** | Un appel dirigé vers la mauvaise famille échoue en 403 Google sans expliquer pourquoi, et le nom identique désarme la relecture. Hors périmètre, mais nommé ici pour que personne ne le découvre à ses frais |

## Questions encore ouvertes

- **La traçabilité des dépôts Drive** : le propriétaire du fichier n'est pas son auteur.
  CLEF le sait, le Drive non. Faut-il l'inscrire dans le nom du fichier, dans une propriété
  Drive, ou s'en tenir aux métadonnées CLEF ?
- **Plusieurs gestionnaires par délégation** : le Drive partagé rend le repli possible sans
  déplacer de fichier (F1). Faut-il stocker plusieurs jetons avec un ordre de repli, ou un
  seul, remplaçable ?
- **`{dt}:oauth:mgr`** : renommer avec migration `RENAME`, ou accepter un reconsentement ?
- **Le libellé affiché d'une délégation** dans la liste de choix de `vehicle-edit` : le
  code (`DT75`) est technique, le libellé du référentiel (`DT DE PARIS`) est long. Question
  restée ouverte depuis la tranche 1.

## Suite

`/plan-feature administration-globale-delegations` — mais **après** le correctif de C4, qui
en est le préalable, et après la tranche 1 dont l'AC-11 (`SUPER_ADMIN_EMAIL` injecté)
conditionne l'accès à tout ce qui est spécifié ici. Commencer par les deux gardes
structurelles (`test_pas_de_perimetre_en_dur.py`, `test_cles_globales_bornees.py`), qui
doivent échouer sur l'état actuel.
