# Synchronisation du référentiel bénévoles

> Spec agent-facing. Établie le 2026-08-21, sur décisions du propriétaire.
> Remplace le comportement décrit dans `docs/specs/authentification-roles.md` §« Rôles
> et résolution », qui documentait une lecture Google Sheets à chaque requête.
> Faits cités avec `fichier:ligne` ; déductions marquées `(à confirmer)`.

## Purpose

Faire de la spreadsheet **« CLEF Benevoles »** le référentiel d'**identité** de tous les
bénévoles du département, et de CLEF le propriétaire de tout ce qui relève de
l'**organisation** — appartenance à la DT, statut, responsabilité d'UL.

Aujourd'hui la synchronisation écrase le document entier à chaque passage : elle
détruit donc toute donnée saisie dans CLEF, ne supprime jamais rien, perd le statut, et
dépend d'un contrat de colonnes implicite. Cette spec définit une synchronisation
**fusionnante et réconciliante** : elle met à jour l'identité, préserve
l'organisation, et révoque l'accès des bénévoles disparus du référentiel.

L'enjeu n'est pas cosmétique : depuis la tâche N2, **l'authentification lit ce
référentiel**. Une ligne perdue, c'est un accès perdu ; une ligne fantôme, c'est un
accès qui survit à un départ.

## Partage de propriété

C'est le cœur de la spec. Toute implémentation qui brouille cette frontière est fausse.

| Champ | Propriétaire | Origine | Modifiable dans CLEF |
|---|---|---|---|
| `nivol` | **feuille** | colonne `Nivol` — clé primaire | non |
| `nom`, `prenom` | **feuille** | colonnes `Nom`, `Prénom` | non |
| `ul` | **feuille** | colonne `UL` | non |
| `email` | **feuille** | colonne `Email` | non |
| `telephone` | **feuille** | colonne `Téléphone` | non |
| `statut` | **CLEF** | `actif` \| `inactif` | oui (réconciliation + admin) |
| `responsable_ul` | **CLEF** | booléen | oui (admin) |
| `fonctions_dt` | **CLEF** | liste de libellés | oui (admin) |

Un bénévole **appartient toujours à une UL** (la feuille le garantit) et **peut en
plus** porter une ou plusieurs fonctions à la DT. Ces deux appartenances coexistent :
c'est précisément ce que l'ancien champ `role` à valeur unique ne pouvait pas exprimer.

### Rôle applicatif dérivé

Le rôle n'est plus stocké : il est **calculé**, dans cet ordre.

| Condition | Rôle | `perimetre` | `type_perimetre` |
|---|---|---|---|
| `email == EMAIL_GESTIONNAIRE_DT` | `Gestionnaire DT` | `DT Paris` | `DT` |
| `fonctions_dt` non vide | `Gestionnaire DT` | `DT Paris` | `DT` |
| `responsable_ul` vrai | `Responsable UL` | `ul` | `UL` |
| sinon | `Bénévole` | `ul` | `UL` |

`statut == "inactif"` court-circuite tout : l'authentification est **refusée**, quel que
soit le reste (voir AC-9).

## User stories / acceptance criteria

- En tant que **gestionnaire DT**, je mets à jour la feuille depuis le référentiel
  bénévole du département, et CLEF reflète les identités sans que je perde les rôles
  que j'ai saisis.
- En tant que **gestionnaire DT**, je nomme un responsable d'UL ou j'attribue une
  fonction DT dans CLEF, et la synchronisation suivante ne l'efface pas.
- En tant que **responsable de la protection des données**, un bénévole parti du
  département perd son accès à CLEF au prochain passage de la synchronisation, sans que
  l'historique de ses prises de véhicule disparaisse.
- En tant que **bénévole**, je choisis un chauffeur dans le formulaire de réservation et
  je vois son téléphone.

### Critères d'acceptation

- [ ] **AC-1 — Fusion.** Étant donné un bénévole en base avec
      `responsable_ul=true`, `fonctions_dt=["Référent flotte"]`, `statut="actif"`,
      quand la synchronisation le renvoie avec un nom et une UL modifiés, alors
      `nom` et `ul` sont mis à jour **et** les trois champs CLEF sont inchangés.
- [ ] **AC-2 — Création.** Un `Nivol` absent de la base est créé avec
      `statut="actif"`, `responsable_ul=false`, `fonctions_dt=[]`.
- [ ] **AC-3 — Réconciliation.** Un bénévole présent en base et **absent** du lot
      passe à `statut="inactif"`. Son document et ses index subsistent.
- [ ] **AC-4 — Réactivation.** Un bénévole `inactif` qui réapparaît dans le lot repasse
      à `actif`, en conservant `responsable_ul` et `fonctions_dt`.
- [ ] **AC-5 — Garde-fou de rayon d'action.** Si un lot désactiverait plus de
      `SYNC_MAX_DEACTIVATION_RATIO` (défaut **0,2**) des bénévoles actifs, la
      réconciliation est **abandonnée** — les créations et mises à jour sont conservées
      —, la réponse porte `reconciliation_skipped: true` avec le motif, et un `ERROR`
      est journalisé.
- [ ] **AC-6 — Lot vide.** Un lot vide n'entraîne **aucune** désactivation
      (cas particulier de AC-5, testé séparément : c'est le mode de panne le plus
      probable d'une lecture de feuille).
- [ ] **AC-7 — Validation ligne à ligne.** Un lot de 10 lignes dont 2 sont invalides
      importe les 8 valides, renvoie `errors` de longueur 2 avec le numéro de ligne et
      le motif, et un code HTTP **200**.
- [ ] **AC-8 — En-têtes.** Les colonnes sont reconnues par leurs libellés exacts.
      **Obligatoires** : `Nivol`, `Nom`, `Prénom`, `UL`, `id_structure`.
      **Facultatives** : `Téléphone`, `Email`. Toute autre est **ignorée**, dont
      `Prénom Nom`. Une colonne obligatoire manquante produit une erreur qui **nomme la
      colonne**.
- [ ] **AC-15 — `id_structure`.** L'identifiant interne Croix-Rouge de l'**unité
      locale** du bénévole est **obligatoire** et doit être un **entier positif** :
      espaces retirés, cellule numérique acceptée, forme canonique conservée
      (`00889` → `889`). `0`, un négatif ou du texte sont refusés **à la ligne**.

      Il est obligatoire parce que `UL` est un **libellé libre**
      (« UNITE LOCALE DE PARIS XII ») : la jointure avec le référentiel national des
      structures se ferait sinon sur du texte, et une variante d'orthographe suffirait à
      laisser un bénévole sans UL connue, donc sans périmètre. Un identifiant qui manque
      une fois sur dix ne rend rien strict.

      ⚠️ **Asymétrie voulue** : obligatoire à l'**écriture** (`BenevoleIdentite`),
      optionnel à la **lecture** (`BenevoleData`). Les bénévoles écrits avant l'ajout de
      la colonne doivent pouvoir se lire — cette lecture est sur le chemin
      d'authentification, et l'exiger transformerait un problème de donnée en refus de
      connexion sans diagnostic. Même raisonnement que pour `ul`.
- [ ] **AC-9 — Révocation.** Un bénévole `inactif` qui présente un cookie de session
      valide reçoit **401**, et le refus est journalisé avec son email.
- [ ] **AC-10 — Clé par délégation.** `POST /api/sync/{dt}/benevoles` n'accepte qu'une
      clé API appartenant à **ce** `{dt}`. Une clé valide d'une autre délégation est
      rejetée en **401**.
- [ ] **AC-11 — Rôle dérivé.** `fonctions_dt` non vide donne `Gestionnaire DT` même si
      `responsable_ul` est vrai ; `responsable_ul` seul donne `Responsable UL` avec
      `perimetre == ul`.
- [ ] **AC-12 — Idempotence.** Deux exécutions consécutives du même lot laissent la
      base identique, et la seconde ne désactive personne.
- [ ] **AC-13 — Téléphone exposé.** `GET /api/benevoles` renvoie `telephone` au même
      titre que `email`, pour tout utilisateur authentifié de la délégation.
- [ ] **AC-14 — Nivol manquant.** Une ligne sans `Nivol` est refusée en erreur de ligne
      (elle n'a pas de clé primaire), sans interrompre le lot.

## Inputs & outputs

### Spreadsheet source

Classeur **« CLEF Benevoles »**, alimenté par l'import périodique du référentiel
bénévole du département. Le code Apps Script est installé **dans ce classeur**.

Ligne d'en-têtes, dans cet ordre :

```
Prénom Nom | Nivol | Nom | Prénom | UL | Téléphone | Email | id_structure
```

`Prénom Nom` est une concaténation de commodité : **ignorée**. `id_structure` a été
**ajoutée en fin de ligne le 2026-08-29** — l'ordre des colonnes n'a aucune importance,
l'Apps Script envoyant un objet clé par en-tête.

L'onglet s'appelle **« Bénévoles »** (confirmé par le propriétaire le 2026-08-21).
Le nom reste surchargeable par la propriété de script `CLEF_SHEET_BENEVOLES`, dont la
valeur par défaut est `Bénévoles`.

### `POST /api/sync/{dt}/benevoles`

**Authentification** : en-tête `X-API-Key`, validée par
`RedisService.validate_api_key(key)` sur le `{dt}` de l'URL — donc **intrinsèquement
cadrée** sur cette délégation. Remplace la variable d'environnement globale
`SYNC_API_KEY` (constat C3).

**Corps** — liste de lignes brutes, clés = libellés de colonnes :

```json
[
  {
    "Nivol": "00123456A",
    "Nom": "Dupont",
    "Prénom": "Jean",
    "UL": "UL Paris 15",
    "Téléphone": "+33 6 12 34 56 78",
    "Email": "jean.dupont@croix-rouge.fr",
    "Prénom Nom": "Jean Dupont"
  }
]
```

Le lot est un **instantané complet** de la délégation : c'est ce qui autorise la
réconciliation.

**Réponse** — `200` même en présence d'erreurs de ligne :

```json
{
  "success": true,
  "created": 3,
  "updated": 147,
  "deactivated": 2,
  "reactivated": 1,
  "unchanged": 0,
  "errors": [
    {"line": 42, "reason": "Colonne 'Nivol' vide", "values": {"Email": "x@y.fr"}}
  ],
  "reconciliation_skipped": false,
  "reconciliation_skipped_reason": null
}
```

**Codes** : `200` succès (même partiel) · `401` clé absente, invalide, ou appartenant à
une autre délégation · `422` corps non-JSON ou non-liste · `400` colonne obligatoire
absente de **toutes** les lignes.

### Modèle stocké

`BenevoleData` (`app/models/redis_models.py`) évolue :

```python
class BenevoleData(BaseModel):
    # Identité — propriété de la feuille
    nivol: str
    dt: str
    nom: str
    prenom: str
    ul: str                      # devient REQUIS : un bénévole a toujours une UL
    email: Optional[str] = None
    telephone: Optional[str] = None      # NOUVEAU

    # Organisation — propriété de CLEF
    statut: Literal["actif", "inactif"] = "actif"   # NOUVEAU
    responsable_ul: bool = False                     # NOUVEAU
    fonctions_dt: List[str] = Field(default_factory=list)  # NOUVEAU

    # Retiré : `role` (remplacé par responsable_ul + fonctions_dt)
```

### Clés Redis

| Clé | Type | Rôle |
|---|---|---|
| `{dt}:benevoles:{nivol}` | JSON | document du bénévole |
| `{dt}:benevoles:index` | SET | tous les nivols de la DT |
| `{dt}:benevoles:by_ul:{ul}` | SET | nivols d'une UL |
| `{dt}:benevoles:by_email:{email}` | STRING | email normalisé → nivol (lu par l'auth) |

Aucune nouvelle clé. `by_ul` doit être **mis à jour au changement d'UL** : retirer le
nivol de l'ancien SET, l'ajouter au nouveau — omission actuelle de `set_benevole`.

### Signatures attendues

```python
# app/services/redis_service.py
async def upsert_benevole_identite(self, identite: BenevoleIdentite) -> str:
    """Crée ou met à jour l'identité en préservant statut/responsable_ul/fonctions_dt.
    Retourne 'created' | 'updated' | 'reactivated'."""

async def deactivate_benevoles_absent_from(
    self, nivols_presents: set[str], max_ratio: float
) -> dict:
    """Passe à 'inactif' les bénévoles actifs absent du jeu fourni.
    Abandonne et renvoie le motif si le ratio serait dépassé."""

async def set_benevole_organisation(
    self, nivol: str, *, responsable_ul: bool | None = None,
    fonctions_dt: list[str] | None = None, statut: str | None = None
) -> Optional[BenevoleData]:
    """Met à jour les seuls champs propriété de CLEF. Ne touche jamais l'identité."""
```

## Behavior & edge cases

### Chemin nominal

1. Le trigger horaire appelle `syncBenevoles()` dans « CLEF Benevoles ».
2. L'onglet est lu en entier ; chaque ligne devient un objet clé=en-tête.
3. `POST /api/sync/{dt}/benevoles` avec la clé API de la délégation.
4. Le backend **valide ligne à ligne**, accumulant les erreurs sans interrompre.
5. Chaque ligne valide est **fusionnée** : identité écrasée, organisation préservée.
6. Les bénévoles actifs absents du lot sont **désactivés**, sous garde-fou de ratio.
7. La réponse détaille créés / mis à jour / désactivés / réactivés / erreurs.

### Cas limites

| Situation | Comportement attendu |
|---|---|
| `Nivol` vide ou absent | erreur de ligne, ligne ignorée (AC-14) |
| `Nivol` en doublon, **une ligne UL + une ligne DT** | **fusion** : l'unité locale réelle est conservée, `rattachement_dt` passe à `true`. Aucune erreur — c'est la forme normale du référentiel |
| `Nivol` en doublon, **deux unités locales différentes** | la dernière listée gagne ; erreur de ligne portant les deux UL dans `values["UL 1"]` et `values["UL 2"]` |
| `Nivol` en doublon, **identité divergente** (nom, prénom, email, téléphone) | la ligne retenue gagne ; erreur de ligne portant le champ dans `values["Détail"]` |

**La `reason` d'une erreur est une CONSTANTE** (`RAISON_*` dans `routers/sync.py`), et
`values` porte les données : `Nivol`, `Nom`, `Prénom`, `UL 1`, `UL 2`, `Détail`. Une
raison interpolée n'est ni triable ni dénombrable — impossible de traiter une unité
locale à la fois, et le regroupement par nature devait effacer les valeurs par
expressions régulières, donc deviner ce qui variait. `test_benevole_sync_payload.py`
vérifie l'invariant sur la liste exhaustive des constantes.

⚠️ `values` ne portait que le nivol, « pour ne pas déverser de données personnelles dans
des journaux à audience plus large que la base ». La précaution reste, son périmètre
était mal posé : ces valeurs sont écrites dans un onglet du classeur qui contient déjà
ces personnes — même public. Ce qui tient toujours : le **serveur** ne journalise que
des compteurs et des nivols, jamais ces `values`.
| `UL` vide | erreur de ligne : un bénévole a toujours une UL |
| `Email` vide | accepté. Le bénévole existe mais **ne pourra pas s'authentifier** (l'auth passe par l'index email). Journalisé en `INFO`, compté dans la réponse |
| `Email` en doublon dans le lot | la dernière occurrence gagne l'entrée d'index ; `WARNING`, car deux bénévoles se disputent une identité de connexion |

### Le référentiel liste deux fois les bénévoles de la délégation

Découvert au premier import réel, le 2026-08-28 : **120 « doublons » sur 4546 lignes**,
tous de la même nature. Un bénévole porteur d'une fonction à la délégation figure deux
fois, une ligne sous son unité locale et une sous la DT :

```
MASSY BOUKHOUF  01100078356D  BOUKHOUF  MASSY  UNITE LOCALE DE PARIS XII  06…  massy.boukhouf@croix-rouge.fr
MASSY BOUKHOUF  01100078356D  BOUKHOUF  MASSY  DT DE PARIS                06…  massy.boukhouf@croix-rouge.fr
```

La règle « la dernière occurrence gagne » faisait donc dépendre l'UL enregistrée de
**l'ordre des lignes de la feuille**, et perdait une fois sur deux la seule information
utile des deux : l'unité locale réelle.

Les deux lignes sont désormais **fusionnées** : `ul` reçoit l'unité locale réelle, et
`rattachement_dt` passe à `true`.

⚠️ **`rattachement_dt` n'est pas un rôle.** Il ne confère aucun droit dans CLEF et n'a
aucun rapport avec `fonctions_dt`, qui appartient à CLEF et que la synchronisation ne
touche jamais. C'est un fait d'appartenance lu dans la feuille, exposé par l'annuaire
pour distinguer ces personnes dans un sélecteur.

⚠️ La reconnaissance porte sur le **libellé** de l'UL, faute de colonne qui le dise :
`^DT\b` ou `^DÉLÉGATION TERRITORIALE\b`, insensible à la casse. Un libellé non reconnu
retombe sur le traitement de doublon ordinaire — donc signalé, jamais fusionné à tort en
silence.
| Changement d'`UL` | `by_ul` mis à jour des deux côtés. ⚠️ Si `responsable_ul` était vrai, il est **conservé** — la personne devient responsable de sa nouvelle UL. `WARNING` pour que ce soit revu |
| Changement d'`Email` | l'ancienne entrée `by_email` est **supprimée** (sinon l'ancienne adresse continuerait d'ouvrir une session) |
| Lot vide | aucune désactivation (AC-6), `reconciliation_skipped: true` |
| Ratio de désactivation dépassé | créations et mises à jour appliquées, réconciliation abandonnée, `ERROR` journalisé (AC-5) |
| Bénévole `inactif` avec session valide | `get_current_user` renvoie `None` → **401**, refus journalisé (AC-9) |
| Colonne obligatoire absente de toutes les lignes | `400` nommant la colonne — c'est le symptôme d'un onglet renommé ou réordonné |
| Redis injoignable pendant la synchronisation | `500`, aucune écriture partielle silencieuse ; l'Apps Script journalise et le trigger réessaiera |
| Champ `role` héritage présent en base | migré par script (voir *Dependencies*), jamais lu par le nouveau code |

### Ce qui disparaît

- **La lecture Google Sheets au démarrage** (`app/main.py`, préchargement) est
  **retirée** : elle constituait un second chemin d'écriture, avec un contrat différent
  (repli `email → nivol`), contradictoire avec celui-ci. Conforme à
  [ADR 0002](../adr/0002-google-workspace-comme-referentiel-de-verite.md) : la
  synchronisation est le **seul** pont.
- **Exception assumée** : en `USE_MOCKS=true`, un amorçage peuple le référentiel depuis
  le mock Sheets, pour que le développement local et les tests aient des utilisateurs.
  Explicitement une commodité de développement, jamais un chemin de production.
- **`SYNC_API_KEY`** (variable globale) et le champ `role` de `BenevoleData`.

## Out of scope

- **L'écran d'administration** permettant de saisir `responsable_ul`, `fonctions_dt` et
  `statut`. Cette spec définit l'API (`set_benevole_organisation`) et le stockage ; l'UI
  fera l'objet d'une spec distincte. En attendant, `PATCH /api/{dt}/benevoles/{email}`
  est adapté au nouveau modèle.
- **La liste fermée des fonctions DT.** `fonctions_dt` est une liste de chaînes libres.
  Un référentiel de fonctions est un chantier produit à part.
- **Le filtrage par UL des données métier** (constat H3bis) : indépendant.
- **La synchronisation des véhicules et des responsables véhicules**
  (`sync-referentiel.gs`, `sync-responsables.gs`), inchangées.
- **Le référentiel legacy `responsables`** (`set_responsable`, `ResponsableData`) :
  son retrait est un chantier de nettoyage distinct.
- **La purge RGPD** des bénévoles inactifs après délai : la décision retenue est
  « désactiver, ne jamais supprimer ». Une purge planifiée reste à spécifier.
- **Le multi-DT réel** : l'authentification interrogera toujours `auth_settings.default_dt`.

## Test plan

### Unitaires — `tests/test_benevole_sync_merge.py`

| Test | Critère |
|---|---|
| `test_identity_is_updated_and_organisation_preserved` | AC-1 |
| `test_new_benevole_gets_default_organisation` | AC-2 |
| `test_absent_benevole_is_deactivated_not_deleted` | AC-3 |
| `test_reappearing_benevole_is_reactivated_keeping_functions` | AC-4 |
| `test_deactivation_aborts_beyond_ratio` | AC-5 |
| `test_empty_batch_deactivates_nobody` | AC-6 |
| `test_ul_change_moves_the_by_ul_index` | cas limite UL |
| `test_email_change_drops_the_stale_index_entry` | cas limite email |
| `test_two_consecutive_runs_are_idempotent` | AC-12 |

### Unitaires — `tests/test_benevole_sync_payload.py`

| Test | Critère |
|---|---|
| `test_french_headers_are_mapped` | AC-8 |
| `test_prenom_nom_column_is_ignored` | AC-8 |
| `test_invalid_rows_do_not_abort_the_batch` | AC-7 |
| `test_missing_nivol_is_a_row_error` | AC-14 |
| `test_missing_mandatory_column_names_it` | AC-8 |
| `test_duplicate_nivol_last_wins_and_warns` | cas limite doublon |

### Intégration — `tests/test_sync_api.py` (étendu)

| Test | Critère |
|---|---|
| `test_sync_requires_a_key_of_this_dt` | **AC-10** — clé de DT92 rejetée sur `/api/DT75/...` |
| `test_sync_response_counts_are_accurate` | forme de réponse |

### Intégration — `tests/test_auth_redis.py` (étendu)

| Test | Critère |
|---|---|
| `test_inactive_benevole_cannot_authenticate` | **AC-9** |
| `test_dt_function_wins_over_ul_responsibility` | AC-11 |
| `test_responsable_ul_perimeter_is_their_ul` | AC-11 |

### Intégration — `tests/test_referentiel_directory.py` (étendu)

| Test | Critère |
|---|---|
| `test_directory_exposes_telephone` | AC-13 |
| `test_directory_excludes_inactive_benevoles` | cohérence avec AC-3 |

### Garde structurelle

- `tests/test_mock_parity.py` : inchangé, mais la dette
  `sheets_service.get_vehicule_by_indicatif` reste (M32, hors périmètre).
- Un test doit vérifier que `app/main.py` **ne lit plus** Google Sheets hors mode mock.

## Dependencies & risks

### Dépendances

Aucune bibliothèque nouvelle. Tout repose sur l'existant : `pydantic 2.13.4`,
`redis 5.2.0`, `fakeredis[json] 2.37.0` (versions vérifiées dans
`docs/specs/ci-verte-redis-8.md`). Rien à valider via Context7.

Machinerie réutilisée : `RedisService.validate_api_key` et
`generate_api_key_dt` (`redis_service.py:86,159`) existent déjà et sont cadrées par le
`dt` du service — C3 se corrige donc sans nouveau mécanisme.

### Migration obligatoire

`scripts/migrate_benevole_role_to_organisation.py`, à lancer **une fois avant** le
déploiement du nouveau code :

| Ancien | Nouveau |
|---|---|
| `role == "responsable_ul"` | `responsable_ul=true`, `fonctions_dt=[]` |
| `role == "responsable_dt"` | `fonctions_dt=["Gestionnaire DT"]`, `responsable_ul=false` |
| `role` absent ou `null` | `responsable_ul=false`, `fonctions_dt=[]` |
| tous | `statut="actif"`, `telephone=None` |

Le script doit être idempotent et offrir `--dry-run`, comme
`backfill_benevole_email_index.py`.

### Le plus risqué : la réconciliation

C'est la seule opération de cette spec qui **retire un accès en masse**. Un onglet
tronqué, un filtre laissé actif dans la feuille, une erreur de quota Sheets renvoyant
une lecture partielle — et la synchronisation désactive des bénévoles en règle.

Dé-risquage, par ordre d'efficacité :

1. **Garde-fou de ratio** (AC-5), avec un défaut prudent à 0,2. Une désactivation
   massive légitime demandera un passage explicite du paramètre.
2. **Lot vide traité à part** (AC-6) : c'est le mode de panne le plus probable.
3. **Désactivation, jamais suppression** : toute erreur est réversible d'un `PATCH`.
4. **Journalisation nominale** de chaque désactivation, pour qu'un accès perdu soit
   explicable sans fouiller la feuille.

Second risque, plus insidieux : **l'ordre de déploiement**. Le nouveau code lit
`statut`, `responsable_ul` et `fonctions_dt` ; des documents non migrés ne les ont pas.
Pydantic leur donnerait des valeurs par défaut — donc `statut="actif"` (sans effet) mais
aussi **`responsable_ul=false` et `fonctions_dt=[]`** : tous les responsables
perdraient leurs droits jusqu'à la migration. La migration doit donc précéder le
déploiement, et non le suivre.

---

Étape suivante : **`/plan-feature synchronisation-referentiel-benevoles`**.
