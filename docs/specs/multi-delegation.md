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
| D6 | Les ressources Google d'une nouvelle DT sont créées par un **Apps Script d'amorçage** sous l'identité du gestionnaire | Seule voie disponible : le service account ne peut pas créer de document dans ce Workspace (constat **N13**, structurel) |
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

Option de déploiement initialisant les 108 délégations et 576 unités locales depuis
`init_data/DTUL.csv` (séparateur `;`), avec un compte rendu d'erreurs de la même forme
que la synchronisation bénévoles — raison constante, données en colonnes.

Le drapeau « utilise CLEF » décide de l'écrasement (D9). ⚠️ Cette tranche touche des
données **en service** : elle mérite sa propre spec.

**Ce que le fichier valide déjà**, vérifié par lecture : 0 rattachement mal formé, 0 UL
orpheline, 108 codes uniques. **Ce qui reste fragile** : la jointure entre une UL du
référentiel et l'UL nommée dans la feuille des bénévoles se fait sur le `Libelle`
(`UNITE LOCALE DE PARIS XII`), pas sur le libellé court (`UL PARIS12`) —
l'`id_structure`, désormais transporté et stocké, est là pour la rendre stricte. **Il
n'est pas encore exploité.**

### Tranche 3 — Menu d'administration globale et Apps Script d'amorçage

Création d'une délégation par le super admin : code validé (D2), email du gestionnaire,
configuration initiale, puis amorçage des ressources Google par Apps Script (D6).

## Questions encore ouvertes

- La création d'une DT écrit-elle une configuration initiale complète, ou le strict
  nécessaire pour que le gestionnaire se connecte ?
- L'Apps Script d'amorçage : un quatrième script à installer, ou une extension du menu
  existant ?
- `MIN_INSTANCES` : 0 ou 1 ? Voir l'arbitrage montage GCS ci-dessus.
- Le libellé retenu pour la colonne d'identifiant de structure est `id_structure` ; le
  référentiel des structures la nomme `N_structure`. Un seul libellé est accepté
  aujourd'hui côté bénévoles.
