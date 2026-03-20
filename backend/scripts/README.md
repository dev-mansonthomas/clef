# Backend Scripts

Utility scripts for the CLEF backend.

## convert_csv_to_mock.py

Converts CSV reference files to JSON mock data for local development.

### Usage

```bash
python3 backend/scripts/convert_csv_to_mock.py
```

### Required CSV Files

Place these files at the project root:

1. **`Référentiel Véhicules DT75 & UL - Référentiel.csv`**
   - Contains vehicle data (82 vehicles expected)
   - First 4 lines are headers (skipped)
   - Line 5 contains column names

2. **`Référentiel Véhicules DT75 & UL - Responsables Véhicules.csv`**
   - Contains responsables data
   - First column is empty (skipped)
   - Columns: DT75/UL, e-mail, téléphone, DT75 Spécialisation

### Output Files

The script generates:

- `backend/app/mocks/data/vehicules.json` - Vehicle mock data
- `backend/app/mocks/data/responsables.json` - Responsables mock data

### Features

- **Date conversion**: Converts DD/MM/YY and DD/MM/YYYY to ISO format (YYYY-MM-DD)
- **Data cleaning**: Removes #N/A values and empty entries
- **Validation**: Filters out vehicles with empty or N/A immatriculation
- **UTF-8 support**: Handles French characters correctly

### Example

```bash
$ python3 backend/scripts/convert_csv_to_mock.py
🔄 Converting CSV files to mock JSON data...

✅ Converted 82 vehicles to backend/app/mocks/data/vehicules.json

✅ Converted 15 responsables to backend/app/mocks/data/responsables.json

✅ Conversion complete!
```

### Testing

After conversion, restart the backend to load the new data:

```bash
# With Docker
docker-compose restart backend

# Or locally
cd backend
uvicorn app.main:app --reload
```

Then verify at http://localhost:4200/vehicles

### Column Mapping

#### Vehicles

| CSV Column | JSON Field |
|------------|------------|
| DT 75 / UL | dt_ul |
| Immat | immat |
| Indicatif | indicatif |
| Opérationnel Mécanique | operationnel_mecanique |
| Raison Indispo | raison_indispo |
| Prochain Controle Technique | prochain_controle_technique |
| Prochain Controle Pollution | prochain_controle_pollution |
| Marque | marque |
| Modèle | modele |
| Type | type |
| Date de MEC | date_mec |
| Nom Syntéthique | nom_synthetique |
| Carte Grise | carte_grise |
| # de Place | nb_places |
| Commentaires | commentaires |
| Lieu de Stationnement | lieu_stationnement |
| Instructions pour récuperer le véhicule | instructions_recuperation |
| Assurance 2026 | assurance_2026 |
| N° Serie BAUS | numero_serie_baus |

#### Responsables

| CSV Column | JSON Field |
|------------|------------|
| DT75 / UL | dt_ul |
| e-mail | email |
| téléphone | telephone |
| DT75 Spécialisation | specialisation |

