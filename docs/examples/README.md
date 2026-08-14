# Exemples de format

Fichiers d'exemple **100 % fictifs**, versionnés pour documenter les formats
attendus par l'application. Aucune donnée personnelle ne doit entrer ici.

## `referentiel-vehicules-exemple.csv`

Forme attendue par l'import CSV du référentiel véhicules
(`POST /api/{dt}/import/vehicles`). Voir `docs/specs/import-vehicules-csv.md`
pour les règles métier.

| Contrainte | Valeur |
|---|---|
| Lignes de métadonnées à ignorer | 4 (`skip_lines`, détecté automatiquement) |
| Ligne d'en-têtes | 5 |
| Colonnes | 19 |
| Lignes de données | 5, dont une avec `Immat = N/A` (ignorée à l'import) |

⚠️ Les en-têtes `Nom Syntéthique` et `Instructions pour récuperer le véhicule`
comportent les **fautes d'orthographe du Google Sheet source**. Elles sont
volontaires : `HEADER_MAPPINGS`
(`backend/app/routers/import_vehicles.py`) reconnaît les libellés réels, et ces
deux colonnes ne sont délibérément pas auto-suggérées.

### Rapport avec les tests

Ce fichier est **de la documentation, pas une fixture de test**. Les tests
d'import génèrent leur propre CSV via les fixtures `vehicles_import_sample_csv`
et `vehicles_no_indicatif_csv` de `backend/tests/conftest.py`, qui partagent la
même source de vérité (`VEHICLES_CSV_HEADERS`, `_vehicle_row`).

Cette séparation est délibérée : les fixtures d'origine étaient des fichiers
`.csv` versionnés, que la règle `.gitignore` `*.csv` a fini par avaler — ils sont
définitivement perdus et 8 tests ont échoué pendant des mois (`docs/TODO.md` H2).
Un test ne doit pas dépendre d'un fichier que le `.gitignore` peut faire
disparaître.

L'exception `!docs/examples/*.csv` du `.gitignore` est **strictement limitée à ce
répertoire**. Elle ne doit pas être élargie.
