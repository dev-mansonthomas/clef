# Spec — Import CSV du référentiel véhicules

> Reconstruit le 2026-08-13 depuis le code et les tests seuls. Faits cités avec
> `fichier:ligne` ; déductions marquées `(inferred — verify)`.

## Objet

Importer en masse le référentiel véhicules depuis l'export CSV du Google Sheet
« Référentiel Véhicules DT75 & UL ». Assistant en 4 étapes côté `admin`, avec
détection des lignes de métadonnées à ignorer, correspondance de colonnes assistée,
puis import idempotent (création ou mise à jour par immatriculation).

Réservé aux gestionnaires DT : `require_authenticated_user` plus contrôle de rôle
en ligne (`backend/app/routers/import_vehicles.py`).

## Parcours en 4 étapes

| Étape | Composant frontend | Rôle |
|---|---|---|
| 1. Dépôt | `features/import-vehicles/components/file-upload.component.ts` | envoi du CSV, obtention de la prévisualisation |
| 2. Correspondance | `column-mapper.component.ts` (385 lignes) | associer chaque colonne CSV à un champ cible |
| 3. Configuration | `import-config.component.ts` | nombre de lignes à ignorer, options |
| 4. Résultat | `import-result.component.ts` | créés / mis à jour / ignorés / erreurs |

## Entrées / sorties

| Méthode | Chemin | Garde | Corps | Réponse |
|---|---|---|---|---|
| `POST` | `/api/{dt}/import/vehicles/preview` | authentifié + rôle DT | `multipart` : fichier CSV | `total_lines`, `skip_lines`, `columns[]`, `preview_rows[]`, `suggested_mappings[]` |
| `POST` | `/api/{dt}/import/vehicles` | authentifié + rôle DT | `multipart` : fichier + `config_json` | `total_lines`, `created`, `updated`, `ignored_lines`, `errors[]` |

`config_json` a la forme (`tests/test_import_vehicles.py:158-162`) :

```json
{
  "skip_lines": 4,
  "mappings": [
    {"csv_column": 0, "target_field": "dt_ul"},
    {"csv_column": 1, "target_field": "immat"},
    {"csv_column": 2, "target_field": "indicatif"}
  ]
}
```

## Règles métier

1. Les `skip_lines` premières lignes sont des métadonnées et sont ignorées ; la
   ligne suivante est la **ligne d'en-têtes** (`test_import_vehicles.py:199`).
2. `skip_lines` vaut **4** par défaut, valeur détectée et renvoyée par la
   prévisualisation (`:74`).
3. Le CSV comporte **19 colonnes** (`:77`).
4. Une correspondance est **suggérée automatiquement** depuis l'en-tête : la colonne
   0 « DT 75 / UL » propose `dt_ul` (`:82-83`).
5. Trois champs sont requis dans les suggestions : `dt_ul`, `immat`, `indicatif`
   (`:87-89`).
6. L'**immatriculation est la clé d'identité**. Une ligne dont l'immat vaut `N/A`
   est **ignorée**, pas mise en erreur (`:205`).
7. L'import est **idempotent** : un véhicule existant est mis à jour, d'où le
   comptage combiné `created + updated` dans les tests (`:212-213`).
8. Un `config_json` invalide renvoie `400`
   (`test_import_csv_invalid_config_json`).
9. Un CSV comptant moins de lignes que `skip_lines` renvoie `400` avec un message
   contenant « skip » (`:114-115`) ; un CSV vide renvoie `400` avec « empty »
   (`:100-101`).
10. Un appelant non gestionnaire DT est rejeté (`test_import_csv_non_dt_manager`).

## ⚠️ Fixture de test perdue — reconstruction

**Constat vérifié.** Les **8 tests** de `backend/tests/test_import_vehicles.py`
échouent tous avec :

```
FileNotFoundError: [Errno 2] No such file or directory:
  '.../backend/tests/fixtures/vehicles_import_sample.csv'
```

Ce fichier **n'a jamais été committé** — 0 occurrence dans l'historique complet,
toutes branches confondues. La règle `.gitignore:156 *.csv`, posée pour protéger les
données personnelles des bénévoles, l'a avalé. La machine qui le détenait a été
supprimée. **La fixture est définitivement perdue** ; seule sa forme est
reconstructible depuis les assertions.

### Forme exigée par les tests

| Contrainte | Valeur | Source |
|---|---|---|
| Lignes totales | **12** | commentaire `:199` |
| Lignes de métadonnées à ignorer | **4** | `:74`, `:158` |
| Ligne d'en-têtes | ligne **5** | déduit de `skip_lines=4` |
| Colonnes | **19** | `:77` |
| En-tête colonne 0 | contient `DT 75 / UL` | `:82` |
| Lignes de données | **≥ 5** | `:202` |
| Dont invalides | **1**, immat = `N/A`, en **ligne 9** | `:205` et son commentaire |
| Véhicules créés ou mis à jour | **≥ 4** | `:212` |

### Les 19 colonnes

Correspondance établie en croisant les `target_field` du test « tous les champs »
(`test_import_vehicles.py:222-258`) avec les en-têtes réels du référentiel
(`Référentiel Véhicules DT75 & UL - Référentiel.csv`, ligne 6) — les deux listes
concordent exactement, dans l'ordre :

| # | En-tête CSV | `target_field` |
|---|---|---|
| 0 | `DT 75 / UL` | `dt_ul` |
| 1 | `Immat` | `immat` |
| 2 | `Indicatif` | `indicatif` |
| 3 | `Opérationnel Mécanique` | `statut` |
| 4 | `Raison Indispo` | `raison_indispo` |
| 5 | `Prochain Controle Technique` | `prochain_ct` |
| 6 | `Prochain Controle Pollution` | `prochain_pollution` |
| 7 | `Marque` | `marque` |
| 8 | `Modèle` | `modele` |
| 9 | `Type` | `type` |
| 10 | `Date de MEC` | `date_mec` |
| 11 | `Nom Syntéthique` | `nom_synthetique` |
| 12 | `Carte Grise` | `carte_grise` |
| 13 | `# de Place` | `nb_places` |
| 14 | `Commentaires` | `commentaires` |
| 15 | `Lieu de Stationnement` | `lieu_stationnement` |
| 16 | `Instructions pour récuperer le véhicule (lien vers google docs)` | `instructions` |
| 17 | `Assurance` | `assurance` |
| 18 | `N° Serie BAUS` | `num_baus` |

Noter que `Nom Syntéthique` et `récuperer` comportent les fautes d'orthographe du
fichier source : **les reproduire à l'identique**, la détection d'en-tête s'appuie
dessus.

⚠️ La fixture n'était **pas** une copie du référentiel réel : dans ce dernier
l'en-tête est en ligne 6 (et la ligne 5 compte 21 colonnes). La fixture était
fabriquée pour le test, avec l'en-tête en ligne 5.

### Deux options pour rétablir la couverture

Décision à prendre — voir `docs/TODO.md` :

- **A.** Recréer le fichier avec des données 100 % fictives et l'exempter :
  `!backend/tests/fixtures/*.csv`. Les 8 tests restent inchangés, mais on rouvre une
  brèche dans la règle de protection des données.
- **B.** Générer le CSV dans une fixture pytest (`tmp_path`). Aucun `.csv` dans git,
  règle préservée, forme attendue explicitée dans le code, et cette classe de panne
  (« fichier de test perdu ») disparaît. Coût : adapter les 8 tests.

## Critères d'acceptation

| Critère | Test | État |
|---|---|---|
| Prévisualisation renvoie colonnes, aperçu et suggestions | `test_import_vehicles.py::TestImportVehiclesPreview::test_preview_csv_success` | ❌ échoue (fixture) |
| `skip_lines` détecté à 4 | idem | ❌ échoue (fixture) |
| Import crée ou met à jour les véhicules | `::TestImportVehicles::test_import_csv_success` | ❌ échoue (fixture) |
| Les 19 champs sont persistés | `::test_import_csv_all_fields_saved_to_redis` | ❌ échoue (fixture) |
| Champs requis manquants → erreur | `::test_import_csv_missing_required_fields` | ❌ échoue (fixture) |
| `config_json` invalide → 400 | `::test_import_csv_invalid_config_json` | ❌ échoue (fixture) |
| Non gestionnaire DT → refus | `::test_import_csv_non_dt_manager` | ❌ échoue (fixture) |
| Colonne ignorée via `skip_field` | `::test_import_csv_with_skip_field` | ❌ échoue (fixture) |
| Import sans indicatif | `::test_import_csv_without_indicatif` | ❌ échoue (fixture) |
| CSV vide → 400 « empty » | présent | ✅ passe |
| Moins de lignes que `skip_lines` → 400 « skip » | présent | ✅ passe |
| Parcours complet de l'assistant | `frontend/e2e/import-wizard.spec.ts` | ⚠️ non exécuté en CI |

## Écarts connus

| Écart | Sévérité |
|---|---|
| Fixture `vehicles_import_sample.csv` perdue → **8 tests en échec**, seule cause restante de CI rouge | **haute** |
| `vehicle-import.service.ts:96,118` code `dt = 'DT75'` en dur au lieu du contexte utilisateur (`TODO` dans le code) | moyenne |
| `frontend/e2e/import-wizard.spec.ts` n'est jamais exécuté : la CI ne lance pas Playwright | moyenne |
