/**
 * CSV de référentiel véhicules pour les tests e2e, construit **en mémoire**.
 *
 * Les specs d'import chargeaient auparavant `e2e/fixtures/test-vehicles.csv`.
 * Ce fichier n'a jamais été committé : la règle `.gitignore` `*.csv`, posée pour
 * protéger les données personnelles des bénévoles, l'a avalé — exactement comme
 * les fixtures du backend (docs/TODO.md H2). Les 7 tests d'import échouaient donc
 * en `ENOENT`.
 *
 * `setInputFiles` accepte une charge utile en mémoire : aucun fichier n'a besoin
 * d'exister sur disque, et cette classe de panne disparaît.
 *
 * La forme reproduit celle du référentiel réel, comme les fixtures backend
 * (`backend/tests/conftest.py`) : 4 lignes de métadonnées, en-tête en ligne 5,
 * 19 colonnes. Les fautes d'orthographe (« Syntéthique », « récuperer ») sont
 * celles du fichier source et sont volontaires.
 */

const HEADERS = [
  'DT 75 / UL',
  'Immat',
  'Indicatif',
  'Opérationnel Mécanique',
  'Raison Indispo',
  'Prochain Controle Technique',
  'Prochain Controle Pollution',
  'Marque',
  'Modèle',
  'Type',
  'Date de MEC',
  'Nom Syntéthique',
  'Carte Grise',
  '# de Place',
  'Commentaires',
  'Lieu de Stationnement',
  'Instructions pour récuperer le véhicule (lien vers google docs)',
  'Assurance',
  'N° Serie BAUS',
];

const METADATA_LINES = [
  'Référentiel Véhicules — export de test',
  'Délégation Territoriale de Paris (DT75)',
  'Document fictif — aucune donnée réelle',
  '',
];

function vehicleRow(
  dtUl: string,
  immat: string,
  indicatif: string,
  marque: string,
  modele: string,
  type: string,
  nomSynthetique: string,
): string {
  const suffix = immat.replace(/-/g, '');
  return [
    dtUl,
    immat,
    indicatif,
    'Dispo',
    '',
    '2027-06-30',
    '2027-06-30',
    marque,
    modele,
    type,
    '12/03/2020',
    nomSynthetique,
    `CG-${suffix}`,
    '3',
    '',
    'Garage fictif',
    '',
    'Contrat fictif 2026',
    `BAUS-${suffix}`,
  ].join(',');
}

/** Contenu CSV : 4 lignes de métadonnées, en-tête ligne 5, 5 lignes de données. */
export function vehiclesCsvContent(): string {
  return [
    ...METADATA_LINES,
    HEADERS.join(','),
    vehicleRow('UL Paris 1', 'AA-101-AA', 'PARIS-01-01', 'Renault', 'Master', 'VSAV', 'vsav-paris-01'),
    vehicleRow('UL Paris 5', 'AB-202-BB', 'PARIS-05-01', 'Peugeot', 'Boxer', 'VPSP', 'vpsp-paris-05'),
    vehicleRow('UL Paris 12', 'AC-303-CC', 'PARIS-12-01', 'Citroën', 'Jumper', 'VL', 'vl-paris-12'),
    vehicleRow('UL Paris 15', 'N/A', 'PARIS-15-01', 'Renault', 'Trafic', 'VL', 'vl-paris-15'),
    vehicleRow('UL Paris 20', 'AD-404-DD', 'PARIS-20-01', 'Ford', 'Transit', 'VPSP', 'vpsp-paris-20'),
    '',
  ].join('\n');
}

/** Charge utile prête pour `locator.setInputFiles(...)`. */
export function vehiclesCsvFile() {
  return {
    name: 'test-vehicles.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(vehiclesCsvContent(), 'utf-8'),
  };
}
