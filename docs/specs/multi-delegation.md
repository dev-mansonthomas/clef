# Multi-délégation — décisions, tranches, et état du chantier

> **Document de reprise**, écrit le 2026-08-29 avant compactage du contexte. Il porte ce
> qu'un agent repartant de zéro doit savoir : les décisions prises et leur *pourquoi*, ce
> qui est déjà dans l'arbre de travail, et les trois specs à écrire.
>
> Le cadrage complet est dans **`docs/product/brief.md`** (issu d'un `/brainstorm`). Ici,
> l'essentiel plus l'état d'avancement. Les cas d'usage reportés sont dans
> `docs/TODO.md`, section « Cas d'usage multi-délégation » (U1, U2).

## Décisions, avec leur raison

| # | Décision | Pourquoi, et ce qui l'a établie |
|---|---|---|
| D1 | Ambition : **supprimer la dette et poser le socle** maintenant ; le multi-DT national est la cible, pas l'échéance | Décision du propriétaire. Conséquence : l'UI et l'API doivent être propres dès maintenant pour ne pas payer deux fois |
| D2 | Code de délégation : `^DT[A-Z0-9]+$`, dérivé du `Libelle_court` du référentiel national (majuscules, sans espace ni accent) | **Mesuré sur `init_data/DTUL.csv`** : mon motif initial `^DT[0-9]{2,3}[AB]?$` rejetait **14 des 108** entités (`DT MARTINIQUE`, `DT REUNION`, `DT 2A`…). La normalisation donne **108 codes distincts sur 108**. Et `Libelle_court` de la structure 80 vaut `DT 75` → code `DT75`, celui que CLEF utilise déjà : **aucune migration** des 4546 bénévoles |
| D3 | `DD` et `DT` désignent la **même** chose ; `DL` et `UL` aussi | Renommage inachevé dans le référentiel : 72 lignes `DELEGATION DEPARTEMENTALE - DD` contre 36 `DELEGATION TERRITORIALE - DT`, Paris (structure 80) étant encore `DD`. ⚠️ `Type_structure` ne doit **jamais** conditionner un traitement : filtrer sur `== 'DT'` perdrait les deux tiers des délégations, dont Paris |
| D4 | Le super admin est désigné par **l'environnement**, non attribuable dans l'application | Décision du propriétaire. ⚠️ `SUPER_ADMIN_EMAIL` n'est injecté dans **aucun** environnement déployé : personne n'est super admin, `/admin/super/*` est inaccessible à tous. À corriger, sinon le menu global est inatteignable |
| D5 | L'application **admin** n'est ouverte qu'au gestionnaire DT et aux **responsables véhicules** ; tout autre `@croix-rouge.fr` est refusé | Décision du propriétaire. ⚠️ Changement de comportement : aujourd'hui n'importe quelle adresse du domaine entre comme « Bénévole » rattachée à `DT75` **en dur**. Trois exceptions d'amorçage : le super admin, l'email déclaré gestionnaire d'une DT, les responsables véhicules |
| D6 | ~~Apps Script d'amorçage~~ → **la délégation OAuth du gestionnaire DT**, qui existe déjà | ✅ Révisée le 2026-08-29. `services/drive_service.py` agit **déjà** sous l'identité du gestionnaire, via son jeton de rafraîchissement chiffré par KMS (`dt_token_service`), avec les scopes `drive`, `calendar` et `gmail.send`. N13 ne s'y applique pas : il ne concerne que le **service account** (`drive_real.py`). Il n'y a donc aucun quatrième script à écrire — le backend peut créer l'arborescence Drive lui-même |
| D7 | Registre des délégations **hors préfixe de DT** : ensemble des codes, un document par délégation, index par email de gestionnaire | Les index sont écrits **à la création** — rien à deviner à la connexion. ⚠️ Premières clés Redis non préfixées : l'invariant d'isolation gagne une exception, à écrire, tester et **borner** à ce registre. Un balayage tiendrait à 3 délégations, pas à 108 |
| D8 | Le modèle porte l'**`id_structure`** (identifiant interne Croix-Rouge) et le rattachement | Paris = 80, valeur déjà dans la configuration (`SUPER_ADMIN_DT_NUMERIC_ID`). Le rattachement d'une UL vaut `{id_structure} - {libellé}` ; celui d'une délégation vaut `1 - INSTANCES NATIONALES`, non exploité |
| D9 | L'import du référentiel n'écrase **jamais** une délégation qui utilise CLEF | Un drapeau par délégation décide : en service → l'import signale les écarts sans rien écrire ; dormante → écrasement. C'est ce qui permet de rejouer l'import quand les structures bougent |
| D10 | `id_structure` est **obligatoire à l'écriture** de la synchronisation bénévoles, **optionnel à la lecture** | ✅ Arbitré le 2026-08-29. Obligatoire dans le modèle de lecture faisait échouer **85 fixtures** et surtout la lecture de tout document antérieur — donc l'authentification. Le code du projet avait déjà tranché ainsi pour `ul` : « un document hérité sans UL doit se lire, sinon le problème de donnée devient un refus d'authentification sans diagnostic ». Un test vérifie que le seul chemin d'écriture ne peut pas produire un bénévole sans cet identifiant |

## Ce qui est DÉJÀ fait, dans l'arbre de travail (non committé)

29 fichiers modifiés, 3 ajoutés. Suite verte : **backend 647 passed, 1 skipped** ·
`ng test admin` 39 · `ng test form` 11 · Playwright 30.

### Synchronisation des bénévoles

- **Fusion des doublons UL + DT.** Un bénévole porteur d'une fonction à la délégation
  figure deux fois au référentiel ; « la dernière occurrence gagne » faisait dépendre son
  UL de l'ordre des lignes. Les deux lignes sont fusionnées : l'UL réelle est conservée,
  `rattachement_dt` passe à `true`. **Mesuré en production : 120 « doublons » → 37**, et
  84 rattachements DT reconnus. ⚠️ `rattachement_dt` n'est **pas** un rôle : aucun droit,
  aucun rapport avec `fonctions_dt`.
- **Les 37 restants** sont de vraies anomalies : même NIVOL sous deux unités locales
  réelles. À corriger dans la feuille.
- **`id_structure` obligatoire** (colonne ajoutée en fin de ligne), entier positif, trim,
  cellule numérique acceptée, forme canonique (`00889` → `889`). Voir D10.
- **Raisons d'erreur constantes** (`RAISON_*`) et données dans `values` : `Nivol`, `Nom`,
  `Prénom`, `UL 1`, `UL 2`, `Détail`. Une raison interpolée n'était ni triable ni
  dénombrable.

### Apps Script (`google-apps-scripts/`)

- `triggers.gs` **(nouveau)** : `installBenevolesTrigger` idempotent, `listTriggers`.
- `logger.gs` : onglet `TECHLOG` **auto-créé**, nouvel onglet **`ERREURS SYNCHRO`**
  (10 colonnes, réécrit à chaque passage), horodatage en **heure de Paris**.
- `api.gs` : réessais sur 5xx, réveil `/health` avant l'envoi du lot, refus explicite si
  `CLEF_API_URL` manque (le défaut `clef-api.run.app` n'a jamais existé).
- `config.gs` : plus de défaut d'URL impossible ; onglet `ERREURS` déclaré.
- `README.md` : quel fichier dans quel classeur, `menu.gs` à adapter pour « CLEF
  Benevoles ».

⚠️ **À recopier dans l'éditeur Apps Script** : `api.gs`, `config.gs`, `logger.gs`,
`sync-benevoles.gs`, et créer `triggers.gs`.

### Écran de configuration

`CLEF_API_URL` (la **base**) et `CLEF_DT` sont affichés comme valeurs à coller, plus un
tableau des **trois** flux (classeur, script, sens, appel). L'écran montrait une URL
complète `https://clef-api.run.app/api/sync/DT75/vehicules` : domaine inexistant, et
valeur d'aucune propriété de script.

### Déploiement et infrastructure

- Réessais de `gcloud run services replace` (3 × 20 s) : le montage GCS échoue par
  intermittence — `GetStorageLayout … Unimplemented`, **3 échecs en 25 min**. La
  documentation gcsfuse dit ce contrôle « integral … cannot be skipped » : **aucune
  option de montage** ne le contourne.
- `MIN_INSTANCES` : décision en suspens. ⚠️ `minScale = 1` transforme le défaut de
  montage en **échec de déploiement** (la révision n'est prête qu'après un démarrage
  réussi) ; `minScale = 0` le laisse passer et échoue à la première requête.
- **Correction documentaire** : Redis écrit son instantané final sur SIGTERM en ~400 ms
  (mesuré). Le commentaire du gabarit affirmait le contraire en l'attribuant à tort à
  l'ADR 0008, qui disait juste.
- `init_data/` ajouté au `.gitignore`.

## Les trois specs à écrire

### Tranche 1 — La délégation vient de l'utilisateur authentifié

**La seule à lancer maintenant.** Ne change aucun comportement visible : rend la suivante
possible.

1. Un **test structurel** qui échoue sur tout littéral `DT75` hors configuration, mocks
   et tests. **Écrit d'abord** — c'est lui qui rend les corrections vérifiables.
2. Backend : `app/auth/service.py:52` et `:116`, `app/main.py:136` passent par
   `DEFAULT_DT` comme valeur d'**amorçage**, jamais comme repli de chemin de données.
3. Frontend : 12 occurrences. Quatre services décident sans consulter l'utilisateur —
   `api-keys` (déjà exposé en `readonly dt`), `stats`, `unite-locale`, `vehicle-import` —
   plus `vehicle-edit` qui injecte `'DT75'` dans une liste d'options et `dt-admin` qui
   l'envoie dans une requête. Les trois replis `?? 'DT75'` disparaissent : un utilisateur
   sans délégation est une anomalie, pas un cas à masquer.
4. `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_DT_ID`, `SUPER_ADMIN_DT_NUMERIC_ID` injectés par le
   gabarit Cloud Run et documentés dans `deploy/deploy.env.example`.

### Tranche 2 — Import du référentiel des structures

✅ **Spec écrite le 2026-08-29 : `docs/specs/import-referentiel-structures.md`** (21
critères). Trois décisions y ont été arbitrées par le propriétaire :

| # | Arbitrage |
|---|---|
| E1 | Le fichier entre **par l'image, pas par git** — `01-gcp-deploy.sh` le recopie avant `gcloud builds submit backend`, qui ne lit que `backend/.gcloudignore`. Aucune exception au `.gitignore`, aucun endpoint d'upload |
| E2 | **Référentiel global seul** (`clef:st:*`). Aucune projection dans `{dt}:ul:*` pour les 107 délégations dormantes : elle appartient à la création d'une délégation (tranche 3) |
| E3 | Clés **plus courtes et indexées par `id_structure`**, jamais par libellé — « les labels changent parfois ». `{dt}:unite_locale:{id}` → `{dt}:ul:{id}`, `{dt}:unite_locales:index` → `{dt}:ul:idx`, `{dt}:benevoles:by_ul:{libellé}` → `{dt}:ben:ul:{id}` |

**Deux mesures qui ont façonné la spec :**

- Les 18 UL de DT75 aujourd'hui **en dur** dans `backend/scripts/init_ul_data.py` sont
  **identiques** au référentiel — mêmes identifiants, mêmes libellés, 0 écart — de même
  que les 108 délégations. L'import est donc un remplacement à comportement constant, et
  le rapport d'écarts de DT75 sera vide.
- ⚠️ **L'export n'est pas exhaustif : 36 des 108 délégations n'y ont aucune UL** (DT93,
  DT2A, DT2B, Martinique, Réunion…). D'où E4 : l'import ne réconcilie **jamais** —
  contrairement à la synchronisation bénévoles, dont le lot *est* un instantané complet.
  Une structure absente du fichier n'est ni supprimée, ni désactivée, et un `Id Structure`
  inconnu ne fait **jamais** rejeter un bénévole.

Le drapeau « utilise CLEF » décide de l'écrasement (D9) : il devient `utilise_clef` sur le
document de structure, propriété de CLEF, que l'import n'écrase jamais — le motif de
l'ADR 0007 appliqué aux structures.

### Tranche 3 — Administration globale des délégations et amorçage Google

✅ **Spec écrite le 2026-08-29 : `docs/specs/administration-globale-delegations.md`** (22
critères). Le titre historique parlait d'un « Apps Script d'amorçage » : **il n'y en aura
pas** (D6 révisée). Arbitrages du propriétaire :

| # | Arbitrage |
|---|---|
| F1 | **Le dossier racine doit être dans un Drive partagé**, et CLEF le vérifie. Correction du propriétaire : c'est déjà le cas, et c'est structurel — un Drive personnel plafonne à **5 Go, courriels inclus**. Conséquence : les fichiers n'appartiennent pas au gestionnaire, son départ ne déplace rien, et le jeton n'est qu'un laissez-passer interchangeable. Vérifié : `drive_service.py` passe **déjà** `supportsAllDrives` sur ses 8 appels |
| F2 | **Création minimale** — code + email du gestionnaire, puis le gestionnaire complète. Une création complète dépendrait du consentement d'un tiers absent : elle échouerait à moitié par construction |
| F4 | La délégation d'un email est résolue par **balayage pipeliné** des délégations en service — un `MGET`, un aller-retour — et **non** par un index global : ce serait une seconde source de vérité à maintenir, et 4546 adresses sorties du cloisonnement par préfixe |
| F6 | **Aucune clé globale nouvelle** : le registre s'appuie sur `clef:st:*` et son drapeau `utilise_clef` (tranche 2). D7 prévoyait un registre séparé ; la tranche 2 l'a rendu inutile |

⚠️ **Préalable bloquant, décidé le 2026-08-29 : le correctif de `docs/TODO.md` C4**, à
livrer sur sa propre branche **avant** cette tranche. `/auth/callback-dt` n'a aucun guard
et prend l'identité du gestionnaire dans le paramètre `state`, non signé : n'importe quel
compte pouvant consentir peut faire de son propre compte Google l'identité déléguée de la
délégation. Découvert en écrivant cette spec ; déployé en dev.

#### Ce qui existe déjà, et qu'il ne faut pas réécrire

| Élément | Où | État |
|---|---|---|
| Parcours de consentement étendu | `GET /auth/authorize-dt` → `GET /auth/callback-dt` | fonctionnel, mais **vulnérable** — voir C4 |
| Scopes demandés | `auth/config.py` : `calendar`, `drive`, `gmail.send` | suffisants |
| Stockage du jeton | `dt_token_service` — rafraîchissement chiffré par KMS, renouvelé **à l'usage** | fonctionnel ; il manque le rafraîchissement de fond, dont l'apport est la **détection précoce d'une révocation** |
| Client Drive délégué | `services/drive_service.py` — `supportsAllDrives` déjà posé partout | fonctionnel |
| Création de l'arborescence | `PATCH /api/config` → `_run_drive_sync` → `vehicle_document_service.ensure_vehicle_trees_for_all_vehicles`, avec suivi de progression et annulation | **fonctionnel** : la tranche 3 y ajoute le contrôle de Drive partagé et les messages d'absence de jeton, elle ne le réécrit pas |
| Écran de déclenchement | composant `dt-admin` | fonctionnel, mais **enfoui** : d'où le consentement incrémental après connexion |
| Écran global | `pages/super-admin/super-admin.component.ts` | **gabarit de 11 lignes** — « Page en construction ». Le lien de navigation existe déjà, gardé par `isSuperAdmin` |

⚠️ **Deux classes portent le même nom `DriveService`** : `services/drive.py` (abstraite,
service account, implémentée par `drive_real.py`) et `services/drive_service.py`
(déléguée). Trois modules utilisent la déléguée, **trois la famille service account**
(`routers/upload.py`, `upload_service.py`, `carnet_bord_service.py`) — laquelle tombe sous
la même cause structurelle que N13. À vérifier par exécution ; chantier propre.

## Questions encore ouvertes

- ~~La création d'une DT écrit-elle une configuration complète ?~~ tranché (F2) : le
  strict nécessaire, puis le gestionnaire complète.
- ~~L'Apps Script d'amorçage~~ : sans objet, la délégation OAuth existante s'en charge.
- **Le jeton de délégation appartient à une personne** — mais **les fichiers, non** :
  l'arborescence est dans un **Drive partagé** (F1), donc un départ ne déplace rien et le
  jeton se remplace à chaud. Reste ouvert : un seul jeton remplaçable, ou plusieurs avec
  ordre de repli ?
- ~~Le moment du consentement~~ : tranché — incrémental, gestionnaire DT seulement.
- `MIN_INSTANCES` : 0 ou 1 ? Voir l'arbitrage montage GCS ci-dessus.
- Trois libellés pour le même identifiant : `N_structure` (référentiel des structures),
  `Id Structure` (feuille des bénévoles), `ul_id_structure` (notre modèle). Deux sont des
  contrats d'interface qu'on ne maîtrise pas.
- `{dt}:benevoles:*` → `{dt}:ben:*` : la tranche 2 renomme l'index par UL mais **pas** les
  documents ni `by_email`, qui est sur le chemin d'authentification. Le schéma reste mixte
  jusqu'à cette fenêtre.
