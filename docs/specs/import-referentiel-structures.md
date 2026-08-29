# Import du référentiel des structures

> Tranche 2 du chantier multi-délégation. Cadrage : `docs/product/brief.md`.
> Décisions et tranches : `docs/specs/multi-delegation.md`.
> Tranche précédente : `docs/specs/dt-depuis-utilisateur-authentifie.md`.

## Purpose

CLEF connaît aujourd'hui les structures Croix-Rouge par **une liste écrite en dur** :
`backend/scripts/init_ul_data.py` porte les 18 unités locales de Paris et les 108
délégations, et `app/main.py:150` les écrit à **chaque démarrage**. Cette liste est juste
— je l'ai comparée au référentiel national, 0 écart sur les 18 UL et les 108 délégations,
mêmes identifiants et mêmes libellés — mais elle est figée, parisienne, et personne ne
peut la corriger sans livrer du code.

Cette tranche la remplace par un **import du référentiel national des structures** :
684 entités, chacune écrite sous son `id_structure` dans un référentiel **global**, hors
préfixe de délégation. Elle rend au passage possible la jointure stricte que la tranche 1
a préparée sans l'exploiter : un bénévole porte son `Id Structure`, le référentiel dit à
quelle délégation cette structure est rattachée. Le libellé de l'UL — aujourd'hui la
seule charnière entre la feuille des bénévoles et CLEF, et un texte libre qui change —
cesse d'être une clé.

## Décisions prises pour cette tranche

| # | Décision | Pourquoi |
|---|---|---|
| E1 | Le fichier entre **par l'image, pas par git** : `01-gcp-deploy.sh` recopie `init_data/DTUL.csv` en `backend/data/structures.csv` avant `gcloud builds submit backend` | Le propriétaire a choisi « embarqué dans l'image ». ⚠️ Le `.gitignore` interdit explicitement toute nouvelle exception à `*.csv` (« ce n'est pas à nous de le republier »), et `gcloud builds submit backend` ne lit **que** `backend/.gcloudignore` — jamais le `.gitignore` de la racine. Les deux exigences tiennent donc ensemble : dans l'image, absent du dépôt |
| E2 | **Référentiel global seul** : `clef:st:*`. Aucune projection dans `{dt}:ul:*` pour les délégations dormantes | La jointure n'a besoin que du référentiel global. Et l'export **n'est pas exhaustif** : mesuré, **36 des 108 délégations n'y ont aucune UL** (DT93, DT2A, DT2B, Martinique, Réunion…). Leur écrire un index d'UL vide affirmerait « cette délégation n'a pas d'UL » là où la vérité est « l'export ne les liste pas ». La projection appartient à la création d'une délégation (tranche 3) |
| E3 | Clés **plus courtes et indexées par `id_structure`**, jamais par libellé | Décision du propriétaire : « les labels changent parfois ». `{dt}:unite_locale:{id}` → `{dt}:ul:{id}` ; `{dt}:unite_locales:index` → `{dt}:ul:idx` ; `{dt}:benevoles:by_ul:{libellé}` → `{dt}:ben:ul:{id}` |
| E4 | **Aucune réconciliation.** Une structure absente du fichier n'est jamais supprimée ni désactivée | Conséquence directe de la non-exhaustivité mesurée. C'est l'inverse du contrat de la synchronisation bénévoles, où le lot **est** un instantané complet — la différence doit être écrite, sinon quelqu'un « harmonisera » les deux |
| E5 | Le discriminant délégation/UL est le **rattachement**, pas `Type_structure` | D3. Vérifié : les 108 structures rattachées à `1 - INSTANCES NATIONALES` sont exactement les 108 délégations, et aucune UL n'y est rattachée. Filtrer sur `Type_structure == 'DT'` en perdrait 72 sur 108, dont Paris |
| E6 | `utilise_clef` est **propriété de CLEF**, l'import ne l'écrase jamais | Exactement le motif de l'ADR 0007 (identité / organisation) appliqué aux structures. C'est ce drapeau qui interdit l'écrasement d'une délégation en service (D9) |

## User stories / acceptance criteria

- En tant que **super admin**, j'obtiens le référentiel réel des 108 délégations et
  576 unités locales sans qu'aucune liste ne soit écrite dans le code.
- En tant que **gestionnaire DT**, mon écran de configuration UL continue d'afficher mes
  18 unités locales, avec les mêmes identifiants qu'avant l'import.
- En tant qu'**exploitant**, un import qui trouve une anomalie me la nomme par ligne, avec
  une raison constante et les valeurs en colonnes — la même forme que la synchronisation
  des bénévoles.
- En tant qu'**agent** reprenant ce code, une clé indexée par libellé fait échouer la
  suite.

### Critères — source et parcours du fichier

- [ ] **AC-1 — Le fichier est dans l'image, pas dans le dépôt.**
      `git check-ignore -q backend/data/structures.csv` réussit (le fichier reste ignoré
      par la règle `*.csv`), **et** ni `backend/.gcloudignore` ni `backend/.dockerignore`
      n'excluent `data/` ou `*.csv`, **et** `01-gcp-deploy.sh` recopie
      `init_data/DTUL.csv` vers `backend/data/structures.csv` **avant**
      `gcloud builds submit backend`. Les trois assertions dans un même test : elles ne
      valent que réunies.
- [ ] **AC-2 — Fichier absent : refus silencieux mais explicite.** Quand
      `STRUCTURES_CSV` désigne un fichier inexistant, alors le démarrage réussit, **aucune
      clé n'est écrite**, et un `WARNING` nomme le chemin attendu. C'est le cas d'une image
      construite par la CI, qui n'a pas le fichier.
- [ ] **AC-3 — En-tête tolérant, colonne manquante fatale au lot.** Les libellés sont
      comparés par `normaliser_entete` (sans accent, casse ni séparateur) : `N_structure`,
      `n structure` et `N-STRUCTURE` désignent la même colonne. Si une colonne obligatoire
      est absente de **toutes** les lignes, alors **une seule** erreur de niveau en-tête
      est produite, nommant la colonne attendue **et** les en-têtes reçus, et **rien n'est
      écrit**.
- [ ] **AC-4 — Import nominal.** Étant donné un fichier de 684 lignes conforme, quand
      l'import s'exécute, alors : 684 documents `clef:st:{id}`, `clef:st:dts` compte 108
      membres, `clef:st:code` compte 108 entrées dont `DT75 → 80`, `clef:st:ul:80` compte
      18 membres, `clef:st:ul:97` compte 30 membres, et `errors` est vide.
- [ ] **AC-5 — `Type_structure` ne décide de rien.** Étant donné une ligne
      `DELEGATION DEPARTEMENTALE - DD` rattachée à `1 - INSTANCES NATIONALES`, quand
      l'import s'exécute, alors elle est traitée en **délégation** et figure dans
      `clef:st:dts`. Le test porte les deux formes, `DD` et `DT`, et la structure 80
      (Paris) est de forme `DD`.
- [ ] **AC-6 — Code de délégation dérivé et validé.** `DT 75 → DT75`,
      `DT MARTINIQUE → DTMARTINIQUE`, `DT 2A → DT2A`, `DT 01 → DT01`. La dérivation part
      **toujours** de `Libelle_court`, jamais de `Libelle` (`DT DE L'AIN` ne donnerait
      pas un code utilisable). Une délégation dont le code dérivé ne vérifie pas
      `^DT[A-Z0-9]+$` produit une **erreur de ligne** et n'est pas écrite ; ses UL le sont,
      mais leur rattachement est signalé.
- [ ] **AC-7 — Empreinte : pas de réécriture inutile.** Quand l'import s'exécute deux fois
      sur le même fichier, alors le second passage n'émet **aucun** `JSON.SET` et le
      rapport porte `inchange: true`. Un octet modifié déclenche un réimport complet.
      ⚠️ Cloud Run redescend à zéro instance : sans cette garde, chaque démarrage à froid
      réécrirait 684 documents sur le chemin de la sonde de démarrage.
- [ ] **AC-8 — Aucune réconciliation.** Étant donné `clef:st:9999` en base et absent du
      fichier, quand l'import s'exécute, alors `clef:st:9999` **existe toujours**, ne perd
      aucun champ, et le rapport le liste sous `absentes_du_fichier`.
- [ ] **AC-9 — `utilise_clef` survit à l'import.** Étant donné `clef:st:97`
      (`DT92`) avec `utilise_clef: true`, quand l'import réécrit son identité, alors
      `utilise_clef` vaut **toujours** `true`. À la **première** écriture d'une structure,
      `utilise_clef` vaut `code == DEFAULT_DT` — donc `true` pour la seule DT75.
- [ ] **AC-10 — Une délégation en service n'est pas écrasée.** Étant donné `DT75` avec
      `utilise_clef: true` et ses 18 UL déjà sous `DT75:ul:*`, quand l'import s'exécute,
      alors **aucune** clé préfixée `DT75:` n'est écrite, et le rapport porte les écarts
      entre le référentiel et l'état en service. Mesuré sur les données réelles : **0
      écart** — les 18 UL en dur sont identiques au fichier, mêmes id, mêmes libellés.
- [ ] **AC-11 — Le rapport est lisible sans lire les journaux.** L'import écrit
      `clef:st:rapport`, et `GET /admin/super/structures` (super admin) le renvoie :
      compteurs, `errors` de la même forme que la synchronisation bénévoles (`line`,
      `reason` **constante**, `values`), `ecarts` par délégation en service.
- [ ] **AC-12 — Le code en dur disparaît.** `backend/scripts/init_ul_data.py` est
      **supprimé**, `app/main.py` ne l'importe plus, et la clé `clef:dts` n'est plus
      écrite (aucun lecteur : vérifié par recherche sur tout le dépôt). Un test échoue si
      `UL_PARIS_DATA`, `DT_DATA` ou `clef:dts` réapparaissent.

### Critères — renommage des clés

- [ ] **AC-13 — Garde structurelle.** Un test échoue si `unite_locale:`,
      `unite_locales:index` ou `benevoles", "by_ul` apparaissent sous `backend/app/`.
      **Écrit d'abord** : il doit échouer sur l'état actuel en nommant les 18 occurrences
      et leurs 3 fichiers (`routers/unites_locales.py`, `routers/ul_config.py`,
      `admin/super_admin_routes.py`, plus `services/redis_service.py` pour `by_ul`).
- [ ] **AC-14 — L'index des bénévoles par UL est indexé par identifiant.**
      `{dt}:ben:ul:{ul_id_structure}` remplace `{dt}:benevoles:by_ul:{libellé}`. Un
      bénévole qui change d'UL est **retiré** de l'ancien identifiant et **ajouté** au
      nouveau (le test existant `test_ul_change_moves_the_by_ul_index` est repris sur les
      identifiants). Une UL **renommée** dans le référentiel ne déplace **rien** : c'est
      le gain.
- [ ] **AC-15 — Migration idempotente et sans balayage.** `scripts/migrate_ul_keys.py`
      parcourt `{dt}:ul:idx` puis `{dt}:benevoles:index` — **aucun `KEYS`, aucun `SCAN`**.
      Relancé, il ne fait rien et le dit. Il refuse d'écraser une clé cible existante.
- [ ] **AC-16 — Bénévole hérité sans identifiant de structure.** Un document sans
      `ul_id_structure` (permis à la lecture, D10) **n'est pas indexé** ; la migration le
      liste par nivol. La synchronisation horaire, qui est un instantané complet, remplit
      le champ au passage suivant.

### Critères — la jointure devient exploitable

- [ ] **AC-17 — Résolveur.** `StructuresService.resolve_delegation(id_structure)` renvoie
      le code de la délégation de rattachement, ou celui de la structure elle-même si
      c'est une délégation, ou `None` si l'identifiant est inconnu. Testé sur les trois
      cas : `900 → DT75`, `80 → DT75`, `9999 → None`.
- [ ] **AC-18 — Identifiant inconnu : signalé, jamais rejeté.** Quand la synchronisation
      des bénévoles reçoit un `Id Structure` absent du référentiel, alors la ligne **est
      importée** et une erreur `RAISON_ID_STRUCTURE_INCONNUE` porte `bloquant: false`.
      ⚠️ Rejeter serait rejouer la panne du 2026-08-28 : un libellé inattendu avait vidé
      un lot de 4546 lignes. Et le référentiel est incomplet par construction (E2).
- [ ] **AC-19 — UL d'une autre délégation : signalée.** Quand l'identifiant est **connu**
      et rattaché à une autre délégation que celle de l'URL, alors la ligne est importée
      et une erreur `RAISON_UL_AUTRE_DELEGATION` porte `bloquant: false`, avec la
      délégation attendue et celle trouvée dans `values`.
- [ ] **AC-20 — La détection DT/UL cesse de dépendre d'un libellé.** Quand le référentiel
      est chargé, l'appartenance d'une ligne à la délégation est déterminée par
      `Id Structure` (la structure **est** une délégation) et non par
      `UL_DE_DELEGATION`. Sans référentiel, le repli sur le libellé s'applique et un
      `INFO` le dit. Les deux chemins sont testés, et le second sur les 84 rattachements
      réels observés.
- [ ] **AC-21 — Bloquant ou non, c'est écrit.** Chaque erreur de la synchronisation porte
      `bloquant: bool` — `true` quand la ligne est écartée, `false` quand elle est importée
      malgré le signalement. L'onglet `ERREURS SYNCHRO` gagne une colonne **Bloquant**
      (11 colonnes), triable comme les autres.

## Inputs & outputs

### Le fichier — contrat d'interface, pas notre format

14 colonnes, séparateur `;`, encodage UTF-8, fins de ligne **CRLF** (vérifié : `file` dit
« with CRLF line terminators » — le module `csv` de la bibliothèque standard s'en charge,
`newline=''` à l'ouverture).

| Colonne | Usage | Obligatoire |
|---|---|---|
| `N_structure` | identifiant interne, **clé primaire** — entier positif | oui |
| `Type_structure` | conservé **informatif** ; ne décide de rien (E5) | oui |
| `Libelle_court` | `DT 75` → source du code de délégation (D2) | oui |
| `Libelle` | `UNITE LOCALE DE PARIS XII` — libellé affiché | oui |
| `Structure_de_rattachement_associatif` | `80 - DT DE PARIS` — **discriminant** et lien parent | oui |
| `Adresse_physique_N_voie`, `_type_voie`, `_libelle_voie`, `_lieu_dit` | composés en une `adresse` | non |
| `Adresse_physique_CP`, `_Commune` | `cp`, `ville` | non |
| `Indicatif`, `Telephone` | conservés **séparément** — l'indicatif n'est pas constant : mesuré `+33` ×672, mais `+590` ×3 (Guadeloupe), `+262` ×2 (Réunion), `+681`, `+596`, `+594`, `+508`, `+689`, `+687` | non |
| `Email_de_la_structure` | `email` — 0 doublon mesuré | non |

⚠️ **Ces libellés ne sont pas les nôtres.** Comme pour la feuille des bénévoles, ils
forment un contrat d'interface avec un export dont nous ne sommes qu'un consommateur. On
s'y adapte ; on ne les renomme pas. La comparaison passe par `normaliser_entete`, qui doit
être **extrait** de `app/routers/sync.py` vers `app/services/referentiel_csv.py` et
importé des deux côtés — pas dupliqué.

### Ce que le fichier valide déjà, mesuré ligne à ligne

| Propriété | Résultat |
|---|---|
| Lignes | 684 = 576 UL + 108 délégations (72 `DD`, 36 `DT`) |
| `N_structure` en doublon | 0 |
| Codes de délégation dérivés, uniques et conformes `^DT[A-Z0-9]+$` | **108 / 108** |
| Rattachements mal formés | 0 |
| UL orphelines (parent inconnu) | 0 |
| Structures rattachées à `1` qui ne sont pas des délégations | 0 |
| Libellé du parent ≠ `Libelle` du parent | 0 |
| Champs obligatoires vides | 0 |
| Délégations **sans aucune UL** dans l'export | **36** ⚠️ voir E2/E4 |

### Le modèle

```python
# app/models/structure.py (nouveau)
class Structure(BaseModel):
    """Une structure Croix-Rouge : délégation ou unité locale.

    Deux moitiés, deux propriétaires — même motif que BenevoleData (ADR 0007) :
      • identité, propriété du référentiel national — écrasée à chaque import ;
      • `utilise_clef`, propriété de CLEF — jamais touchée par l'import.
    """
    id: str                       # N_structure, forme canonique (str(int(...)))
    type: Literal["DT", "UL"]     # dérivé du rattachement, pas de Type_structure
    code: Optional[str] = None    # délégations seulement : ^DT[A-Z0-9]+$
    nom: str                      # Libelle
    court: str                    # Libelle_court
    type_source: str              # Type_structure brut, informatif
    parent: str                   # id de la structure de rattachement
    adresse: Optional[str] = None
    cp: Optional[str] = None
    ville: Optional[str] = None
    indicatif: Optional[str] = None
    tel: Optional[str] = None
    email: Optional[str] = None
    utilise_clef: bool = False    # ← CLEF, jamais écrasé (E6)
    maj: str                      # horodatage ISO de la dernière écriture d'identité
```

### Les clés Redis

**Nouvelles — globales, hors préfixe de délégation** (⚠️ voir *Risques*) :

| Clé | Type | Contenu | Cardinalité réelle |
|---|---|---|---|
| `clef:st:{id}` | JSON | une `Structure` | 684 |
| `clef:st:dts` | SET | identifiants des délégations | 108 |
| `clef:st:code` | HASH | code → identifiant (`DT75` → `80`) | 108 |
| `clef:st:ul:{id_dt}` | SET | identifiants des UL d'une délégation | 72 clés, 3 à 30 membres |
| `clef:st:src` | JSON | `{sha256, importe_le, lignes, delegations, uls}` | 1 |
| `clef:st:rapport` | JSON | dernier rapport d'import | 1 |

Exemple, valeurs réelles :

```
clef:st:80    {"id":"80","type":"DT","code":"DT75","nom":"DT DE PARIS","court":"DT 75",
               "type_source":"DELEGATION DEPARTEMENTALE - DD","parent":"1",
               "adresse":"12 Rue Chardin","cp":"75016","ville":"PARIS",
               "indicatif":"+33","tel":"01 44 14 68 88","email":"dt75@croix-rouge.fr",
               "utilise_clef":true,"maj":"2026-08-29T…Z"}
clef:st:900   {"id":"900","type":"UL","code":null,"nom":"UNITE LOCALE DE PARIS XII",
               "court":"UL PARIS12","parent":"80","adresse":"14 Boulevard Soult",
               "cp":"75012","ville":"PARIS","email":"ul.paris12@croix-rouge.fr",
               "utilise_clef":false,"maj":"2026-08-29T…Z"}
clef:st:code  {"DT75":"80","DT92":"97","DT93":"4631", …}
clef:st:ul:80 {"889","892","893","894","895", …,"908"}      18 membres
clef:st:ul:97 {"1151","1152","1153", …}                     30 membres
```

**Renommées** (E3) :

| Avant | Après | Lecteurs |
|---|---|---|
| `{dt}:unite_locale:{id}` | `{dt}:ul:{id}` | `routers/unites_locales.py`, `routers/ul_config.py`, `admin/super_admin_routes.py`, `routers/api_keys.py` (via `RedisService`) |
| `{dt}:unite_locales:index` | `{dt}:ul:idx` | les mêmes |
| `{dt}:benevoles:by_ul:{libellé}` | `{dt}:ben:ul:{id}` | `RedisService.list_benevoles(ul=…)` — **aucun appelant en production** aujourd'hui, seulement des tests : le renommage est donc peu risqué |

⚠️ `{dt}:benevoles:{nivol}`, `{dt}:benevoles:index` et `{dt}:benevoles:by_email` **ne sont
pas renommés** : `by_email` est sur le chemin d'authentification, et 4546 documents à
renommer méritent leur propre fenêtre, pas d'être embarqués dans un import de structures.
Le schéma reste donc mixte — `{dt}:ben:ul:{id}` à côté de `{dt}:benevoles:{nivol}`. C'est
inscrit dans les questions ouvertes et dans `docs/TODO.md`.

### Les points d'entrée

```python
# app/services/structures_service.py (nouveau)
class StructuresService:
    async def importer(self, csv_bytes: bytes, *, force: bool = False) -> RapportImport
    async def resolve_delegation(self, id_structure: str) -> Optional[str]
    async def est_delegation(self, id_structure: str) -> bool
    async def uls_de(self, code_dt: str) -> List[Structure]
```

```python
# app/models/structure.py
class RapportImport(BaseModel):
    inchange: bool                     # empreinte identique : rien n'a été écrit
    lignes: int
    delegations: int
    uls: int
    ecrites: int
    absentes_du_fichier: List[str]     # présentes en base, pas dans le fichier (E4)
    ecarts: Dict[str, List[Dict]]      # par code de délégation en service (AC-10)
    errors: List[Dict[str, Any]]       # {line, reason (constante), values}
```

Raisons constantes, sur le modèle de la synchronisation bénévoles :

```python
RAISON_COLONNE_ABSENTE      = "Colonne absente"
RAISON_CHAMP_INVALIDE       = "Champ invalide"
RAISON_RATTACHEMENT_INVALIDE = "Rattachement illisible"
RAISON_RATTACHEMENT_INCONNU  = "Structure de rattachement inconnue"
RAISON_CODE_INVALIDE        = "Code de délégation non conforme"
RAISON_ID_DUPLIQUE          = "Identifiant de structure en doublon"
```

Déclenchement : au **démarrage**, dans le `lifespan`, à la place de l'appel actuel à
`init_data_async`. Lecture seule côté API :

```
GET /admin/super/structures            → RapportImport du dernier import (super admin)
```

Nouvelle variable d'environnement, à ajouter à `backend/.env.example` (dont les 44 clés
sont vérifiées dans les deux sens par `tests/test_env_example.py`) :

```
STRUCTURES_CSV=data/structures.csv     # relatif au dossier backend ; absent = import ignoré
```

## Behavior & edge cases

**Chemin nominal.** Le conteneur démarre. `STRUCTURES_CSV` existe ; son empreinte diffère
de `clef:st:src` ; les 684 lignes sont lues, validées, écrites en **un pipeline** ;
`clef:st:src` et `clef:st:rapport` sont posés ; un `INFO` résume
`684 structures · 108 délégations · 576 UL · 0 erreur`. DT75, en service, n'est pas
touchée : son rapport d'écarts est vide.

| Cas limite | Comportement attendu |
|---|---|
| Fichier absent | `WARNING` nommant le chemin, aucune écriture, démarrage réussi (AC-2). C'est le cas d'une image construite par la CI |
| Fichier vide ou sans en-tête exploitable | une erreur de niveau en-tête, aucune écriture |
| Colonne obligatoire absente partout | **une seule** erreur nommant la colonne et les en-têtes reçus (AC-3) |
| Empreinte identique | aucune écriture, `inchange: true` (AC-7) |
| `N_structure` non entier, vide, ou ≤ 0 | erreur de ligne, structure ignorée ; ses UL éventuelles voient leur rattachement inconnu |
| `N_structure` en doublon | la **première** occurrence gagne ; erreur de ligne sur les suivantes. Mesuré : 0 aujourd'hui |
| Rattachement illisible (pas `\d+ - libellé`) | erreur de ligne, structure ignorée |
| Rattachement vers un identifiant absent du fichier | la structure **est écrite**, son `parent` conservé tel quel, et une erreur non bloquante le signale : le fichier est un extrait, pas un instantané (E4) |
| Code dérivé non conforme `^DT[A-Z0-9]+$` | erreur de ligne, délégation non écrite ; ses UL le sont |
| Deux délégations donnant le **même** code | la première gagne ; erreur de ligne. Mesuré : 0 sur 108 |
| Délégation sans aucune UL dans le fichier | **normal** : 36 cas mesurés. Aucun `clef:st:ul:{id}` n'est créé — une clé vide et une clé absente ne disent pas la même chose |
| Structure en base, absente du fichier | **conservée**, listée dans `absentes_du_fichier` (AC-8) |
| Délégation en service (`utilise_clef: true`) | rien n'est écrit sous son préfixe ; les écarts sont rapportés (AC-10) |
| L'import lève une exception | capturée, `ERROR`, **le démarrage continue** : un référentiel non importé dégrade la jointure, il n'empêche pas de servir |
| Redis indisponible au démarrage | comportement existant du `lifespan`, inchangé |
| Bénévole dont l'`Id Structure` est inconnu | ligne importée, erreur non bloquante (AC-18) |
| Bénévole dont l'UL appartient à une autre délégation | ligne importée, erreur non bloquante nommant les deux délégations (AC-19) |
| Bénévole dont l'`Id Structure` désigne une **délégation** | c'est le cas normal d'un bénévole n'ayant qu'une ligne DT : `rattachement_dt` vaut `true`, aucune erreur. La fusion des doublons conserve déjà la ligne UL quand elle existe, donc son identifiant d'UL réelle |

### Ce que la migration fait, dans l'ordre

1. `{dt}:unite_locales:index` → `{dt}:ul:idx` (`RENAME`, refusé si la cible existe).
2. Pour chaque identifiant de l'index : `{dt}:unite_locale:{id}` → `{dt}:ul:{id}`.
3. Pour chaque nivol de `{dt}:benevoles:index` : lire le document, `SADD` dans
   `{dt}:ben:ul:{ul_id_structure}`, et mémoriser son libellé `ul` pour supprimer
   `{dt}:benevoles:by_ul:{libellé}` à la fin. **Aucun balayage** : les libellés se
   déduisent des documents (AC-15).
4. Les nivols sans `ul_id_structure` sont listés, pas indexés (AC-16).
5. Relancé, le script constate que les cibles existent et s'arrête sans rien faire.

⚠️ **À lancer une fois après le déploiement**, comme
`backfill_benevole_email_index.py`. Le noter dans `DEPLOYMENT.md` et dans `CLAUDE.md`.

## Out of scope

- **La projection dans `{dt}:ul:*` des délégations dormantes** — appartient à la création
  d'une délégation, tranche 3 (E2).
- **Le menu d'administration globale**, la création d'une délégation, le registre par
  email de gestionnaire, l'amorçage Google — tranche 3.
- **Un écran d'import** ou un endpoint d'upload : le fichier passe par l'image (E1).
- **Le renommage de `{dt}:benevoles:*` en `{dt}:ben:*`** — chemin d'authentification,
  fenêtre propre.
- **Dériver la délégation d'un bénévole** de sa chaîne `Id Structure` au lieu du segment
  d'URL : cette tranche **signale** le désaccord, elle ne change pas la source (AC-19).
- **Supprimer, désactiver ou fusionner** une structure ; toute réconciliation (E4).
- **Rendre le référentiel exhaustif** : 36 délégations sans UL, c'est l'export qui est
  partiel. Obtenir un export complet est une action hors code.
- L'exploitation des adresses, téléphones et courriels de structure par l'application.

## Test plan

**Fixtures — générées, jamais versionnées.** La règle `.gitignore *.csv` a déjà fait
disparaître définitivement deux fixtures (`docs/TODO.md` H2). Les tests **construisent**
leur CSV en mémoire, comme `conftest.py` le fait pour l'import des véhicules. Un
générateur partagé produit un extrait crédible : 2 délégations (une `DD`, une `DT`), leurs
UL, et les cas limites demandés par chaque test.

| Fichier | Couvre |
|---|---|
| `tests/test_structures_source.py` *(nouveau)* | AC-1, AC-2 — chemin du fichier, ignore files, recopie par `01-gcp-deploy.sh`, absence tolérée |
| `tests/test_structures_import.py` *(nouveau)* | AC-3 à AC-9 — en-têtes, import nominal sur un extrait, discriminant `DD`/`DT`, dérivation du code, empreinte, non-réconciliation, `utilise_clef` |
| `tests/test_structures_en_service.py` *(nouveau)* | AC-10 — aucune écriture sous le préfixe d'une délégation en service, rapport d'écarts non vide quand l'état diverge |
| `tests/test_structures_rapport.py` *(nouveau)* | AC-11 — forme du rapport, route super admin, refus pour un non-super-admin |
| `tests/test_pas_de_cle_par_libelle.py` *(nouveau)* | AC-13 — garde structurelle. **Écrite d'abord**, doit échouer en nommant les 18 occurrences |
| `tests/test_migration_cles_ul.py` *(nouveau)* | AC-14 à AC-16 — migration, idempotence, absence de `KEYS`/`SCAN`, bénévole hérité |
| `tests/test_structures_jointure.py` *(nouveau)* | AC-17 — résolveur sur `900`, `80`, `9999` |
| `tests/test_benevole_sync_payload.py` *(étendu)* | AC-18 à AC-21 — signalements non bloquants, détection DT/UL par identifiant et son repli, champ `bloquant` |
| `tests/test_unites_locales.py`, `test_super_admin_routes.py`, `test_redis_service.py`, `test_benevole_sync_merge.py` *(adaptés)* | non-régression sur les clés renommées |
| `tests/test_env_example.py` | échoue tant que `STRUCTURES_CSV` n'est pas documentée — garde existante, aucune action |

**Test d'intégration** (marqueur `integration`, ignoré sans Redis joignable) : importer un
extrait généré dans `fakeredis[json]`, puis vérifier les cardinalités exactes de
`clef:st:dts`, `clef:st:code` et `clef:st:ul:{id}`.

**Éprouver chaque garde par mutation** : retirer une exclusion d'un `.gcloudignore`,
remettre un `unite_locale:`, réintroduire `clef:dts` — chaque garde doit échouer. Une
garde non éprouvée est une garde qui passe sur une liste vide ; c'est exactement ainsi que
le premier test de `main.py` a réussi sur `app.routes` non aplati.

**Non-régression** : les quatre suites vertes — backend `657 passed, 1 skipped` (plus les
nouveaux), `ng test admin` 39, `ng test form` 11, Playwright 30.

⚠️ **À éprouver en exécution, avant et après déploiement** :

1. **Avant** de supprimer `init_ul_data.py`, vérifier que dev porte bien ses 18 UL —
   `GET /api/DT75/unites-locales` doit répondre `total: 18`. Le script les réécrit à
   chaque démarrage ; si Redis les avait perdues, sa suppression rendrait la perte
   visible, et la faute serait imputée à cette tranche.
2. **Après** : relancer une synchronisation des bénévoles et vérifier `0` erreur bloquante
   et un nombre d'`Id Structure` inconnus **nul** — les 18 UL de Paris sont dans le
   référentiel, donc tout autre résultat signale un identifiant faux dans la feuille.

## Dependencies & risks

**Aucune dépendance nouvelle** : `csv` et `hashlib` sont dans la bibliothèque standard,
`normaliser_entete` existe déjà dans `app/routers/sync.py` et doit être extrait. Rien à
vérifier côté versions, donc pas de passage par Context7.

| Risque | Portée et atténuation |
|---|---|
| **Premières clés hors préfixe de délégation** | L'isolation multi-tenant de CLEF **est** le préfixe `{dt}:` — c'est le seul mécanisme, appliqué par l'application. `clef:st:*` y fait exception. Atténuations : le référentiel est en **lecture seule** pour tout le code applicatif (seul l'import écrit) ; il ne contient **aucune** donnée personnelle ; sa seule route est réservée au super admin. À noter : `clef:dts` était **déjà** une clé globale — l'exception existe depuis l'origine, elle est ici bornée et documentée au lieu d'être accidentelle |
| **Suppression de `init_ul_data.py`** | Il réécrit les 18 UL à chaque démarrage : c'est un filet involontaire. Le retirer sur un datastore qui les aurait perdues vide l'écran de configuration UL et la liste de choix de `vehicle-edit`. D'où la vérification n° 1 ci-dessus, **avant** la suppression |
| **Renommage de clés en service** | `{dt}:ul:*` est lu par 4 fichiers, `by_ul` par un seul et **par aucun appelant de production**. Le risque réel est une migration à moitié faite : le script refuse d'écraser une cible et se relance sans effet. Il ne touche ni `benevoles:by_email` ni les documents des bénévoles — l'authentification est hors de portée |
| **L'import est sur le chemin de démarrage** | Cloud Run redescend à zéro instance, et un démarrage lent est un démarrage en échec. 684 `JSON.SET` en un pipeline contre un Redis en sidecar, c'est de l'ordre de la dizaine de millisecondes ; l'empreinte (AC-7) supprime le coût dès le second démarrage. À **mesurer** au premier déploiement, dans le journal de démarrage |
| **Le fichier n'est pas dans le dépôt** | Une image construite par la CI n'a pas le référentiel : l'import est alors un `no-op` silencieux (AC-2) et le référentiel reste celui du dernier déploiement depuis l'hôte. C'est le prix de E1, et c'est le comportement le moins nuisible. Le rapport dit toujours d'où vient l'état courant (`clef:st:src`) |
| **La confiance dans un référentiel partiel** | Le plus insidieux. 36 délégations sans UL, et rien dans les données ne distingue « pas d'UL » de « pas exporté ». C'est pourquoi l'absence n'entraîne **jamais** ni suppression (E4) ni rejet d'un bénévole (AC-18) : tout écart est un signalement, jamais une décision |

## Questions encore ouvertes

- `{dt}:benevoles:*` → `{dt}:ben:*` : quand ouvrir la fenêtre ? Le schéma reste mixte
  d'ici là.
- `utilise_clef` est préréglé à `code == DEFAULT_DT` à la première écriture. Faut-il, en
  plus, le déduire de l'existence de `{dt}:configuration` pour qu'un environnement dont le
  drapeau a été perdu se répare seul — au risque d'avoir deux sources de vérité ?
- Le référentiel des structures nomme la colonne `N_structure`, la feuille des bénévoles
  `Id Structure`, et notre modèle `ul_id_structure`. Trois libellés pour le même
  identifiant, dont deux sont des contrats d'interface qu'on ne maîtrise pas.
- Obtenir un export **complet** des unités locales (les 36 délégations vides) : hors code,
  mais c'est ce qui limite la portée de la jointure aujourd'hui.

## Suite

`/plan-feature import-referentiel-structures` — en commençant par la garde structurelle
AC-13 et par la vérification n° 1 (les 18 UL de dev), toutes deux avant la moindre
suppression de code.
