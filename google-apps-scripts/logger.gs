/**
 * Logger pour l'onglet TECHLOG
 * 
 * Ce script fournit des fonctions pour logger les opérations de synchronisation
 * dans l'onglet TECHLOG de la Spreadsheet.
 */

/**
 * Log une opération réussie
 * 
 * @param {string} onglet - Nom de l'onglet concerné (Référentiel, Responsables, Bénévoles)
 * @param {Date} startTime - Heure de début de l'opération
 * @param {number} rowCount - Nombre de lignes traitées
 */
function logSuccess(onglet, startTime, rowCount) {
  log(onglet, 'SUCCESS', '', startTime, rowCount);
}

/**
 * Log une erreur
 * 
 * @param {string} onglet - Nom de l'onglet concerné (Référentiel, Responsables, Bénévoles)
 * @param {Date} startTime - Heure de début de l'opération
 * @param {string} message - Message d'erreur
 */
function logError(onglet, startTime, message) {
  log(onglet, 'ERROR', message, startTime, 0);
}

/**
 * Horodatage en heure de PARIS, pas en UTC.
 *
 * ⚠️ `new Date().toISOString()` rend de l'UTC : le journal affichait 13:07 pour une
 * synchronisation lancée à 15:07. Sur un outil que des bénévoles et des gestionnaires
 * consultent pour comprendre ce qui s'est passé « il y a dix minutes », deux heures
 * d'écart ne se devinent pas — et invitent à chercher un incident ailleurs.
 *
 * ⚠️ Le fuseau est écrit EN DUR, plutôt que pris du classeur
 * (`SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone()`) : celui d'un
 * classeur dépend de qui l'a créé, et un classeur en `America/New_York` produirait un
 * journal illisible sans que personne ne comprenne pourquoi. La délégation est à Paris.
 *
 * Format court plutôt qu'ISO : c'est une colonne qu'on lit, pas qu'on parse.
 */
function horodatageParis() {
  return Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd HH:mm:ss');
}

/** En-tête de l'onglet TECHLOG. L'ordre est celui des colonnes écrites par `log`. */
const TECHLOG_HEADERS = ['Timestamp', 'Onglet', 'Statut', 'Message', 'Durée (ms)', 'Lignes'];

/**
 * Renvoie l'onglet TECHLOG, en le CRÉANT s'il n'existe pas.
 *
 * ⚠️ Auparavant, un onglet absent faisait renoncer au journal — silencieusement. Le
 * compte rendu de chaque synchronisation était alors perdu sans qu'aucune erreur ne le
 * signale, ce qui est le pire des deux mondes : la synchronisation tourne, et on ne
 * sait pas ce qu'elle a fait. Un journal qui se crée tout seul supprime une étape
 * d'installation manuelle, donc une étape qu'on oublie.
 *
 * La création reste enveloppée par l'appelant : si elle échoue — droits en lecture
 * seule sur le classeur —, on renonce au journal, jamais à la synchronisation.
 *
 * @return {Sheet|null} l'onglet, ou null si sa création est impossible
 */
function ensureSheet(nom, entetes, largeurs) {
  const classeur = SpreadsheetApp.getActiveSpreadsheet();

  let sheet = classeur.getSheetByName(nom);
  if (sheet) {
    return sheet;
  }

  // ⚠️ Créé en DERNIÈRE position : ces onglets sont techniques, ils n'ont pas à
  // s'insérer devant les données que l'utilisateur consulte.
  sheet = classeur.insertSheet(nom, classeur.getNumSheets());
  sheet.appendRow(entetes);
  sheet.getRange(1, 1, 1, entetes.length).setFontWeight('bold');
  sheet.setFrozenRows(1);
  (largeurs || []).forEach(function (largeur, index) {
    if (largeur) {
      sheet.setColumnWidth(index + 1, largeur);
    }
  });
  console.info('Onglet ' + nom + ' créé.');
  return sheet;
}

function ensureTechlogSheet() {
  // La colonne 4 porte le message : c'est celle qu'on lit vraiment.
  return ensureSheet(CONFIG.SHEETS.TECHLOG, TECHLOG_HEADERS, [180, 0, 0, 520]);
}

/**
 * En-tête de l'onglet de détail des erreurs.
 *
 * ⚠️ Une colonne par donnée, et la RAISON est une constante. Un message interpolé
 * — « Doublon de NIVOL 011… : 2 unités locales différentes (UL A, UL B) » — n'est ni
 * triable ni dénombrable : impossible de traiter une unité locale à la fois, et le
 * regroupement par nature exigeait d'effacer les valeurs à coups d'expressions
 * régulières, donc de deviner ce qui variait.
 *
 * L'ordre suit ce qu'on lit : où (ligne), qui (nivol, nom, prénom), quoi (UL 1, UL 2,
 * détail), et enfin pourquoi.
 */
const ERREURS_HEADERS = [
  'Horodatage', 'Onglet', 'Ligne', 'Nivol', 'Nom', 'Prénom',
  'UL 1', 'UL 2', 'Détail', 'Raison'
];

/**
 * Écrit le DÉTAIL, ligne par ligne, des erreurs de la dernière synchronisation.
 *
 * ⚠️ Le TECHLOG ne peut pas porter ce détail : une cellule par synchronisation, et
 * 37 erreurs n'y tiennent pas — on y met un dénombrement par nature, qui répond à
 * « de quoi s'agit-il ? » mais pas à « quelles lignes corriger ? ». Or c'est la
 * seconde question qui fait agir : ces erreurs se corrigent DANS LA FEUILLE.
 *
 * ⚠️ L'onglet est RÉÉCRIT à chaque passage, pas complété. Ces erreurs décrivent l'état
 * COURANT de la feuille, pas une histoire : garder les 37 mêmes lignes toutes les
 * heures produirait un journal que personne ne relit. L'horodatage dit de quand
 * date le constat.
 *
 * @param {string} onglet - onglet d'origine (« Bénévoles »)
 * @param {Array} errors - erreurs renvoyées par l'API : {line, reason, values}
 */
function logErrorsDetail(onglet, errors) {
  try {
    const sheet = ensureSheet(CONFIG.SHEETS.ERREURS, ERREURS_HEADERS,
      [150, 90, 60, 130, 150, 120, 230, 230, 200, 280]);

    if (sheet.getLastRow() > 1) {
      sheet.getRange(2, 1, sheet.getLastRow() - 1, ERREURS_HEADERS.length).clearContent();
    }

    if (!errors || errors.length === 0) {
      return;
    }

    // Plafond de sûreté : une feuille entière en erreur ne doit pas produire
    // 5000 écritures et faire dépasser le quota d'exécution du déclencheur.
    const MAX = 500;
    const horodatage = horodatageParis();
    const lignes = errors.slice(0, MAX).map(function (e) {
      const v = e.values || {};
      return [
        horodatage,
        onglet,
        e.line || '',
        v['Nivol'] || '',
        v['Nom'] || '',
        v['Prénom'] || '',
        v['UL 1'] || '',
        v['UL 2'] || '',
        v['Détail'] || '',
        e.reason || ''
      ];
    });

    sheet.getRange(2, 1, lignes.length, ERREURS_HEADERS.length).setValues(lignes);

    if (errors.length > MAX) {
      sheet.getRange(2 + lignes.length, 1, 1, 2).setValues([[
        horodatage, `… et ${errors.length - MAX} autres non listées`
      ]]);
    }

    console.info(lignes.length + ' erreur(s) détaillée(s) dans ' + CONFIG.SHEETS.ERREURS);
  } catch (e) {
    // Comme pour le TECHLOG : on renonce au détail, jamais à la synchronisation.
    console.error('Impossible d\'écrire le détail des erreurs : ' + e.message);
  }
}

/**
 * Fonction interne pour écrire dans l'onglet TECHLOG
 * 
 * @param {string} onglet - Nom de l'onglet concerné
 * @param {string} status - Statut (SUCCESS ou ERROR)
 * @param {string} message - Message (vide pour SUCCESS, message d'erreur pour ERROR)
 * @param {Date} startTime - Heure de début de l'opération
 * @param {number} rowCount - Nombre de lignes traitées
 */
function log(onglet, status, message, startTime, rowCount) {
  try {
    const sheet = ensureTechlogSheet();

    if (!sheet) {
      // La création a échoué — droits insuffisants, par exemple. On renonce au
      // journal plutôt que de faire échouer la synchronisation elle-même.
      return;
    }

    // Calculer la durée de l'opération en millisecondes
    const duration = new Date() - startTime;
    
    // Ajouter une nouvelle ligne avec les informations de log
    sheet.appendRow([
      horodatageParis(),          // heure de Paris, pas UTC
      onglet,                     // Nom de l'onglet
      status,                     // SUCCESS ou ERROR
      message,                    // Message d'erreur (vide si SUCCESS)
      duration,                   // Durée en millisecondes
      rowCount                    // Nombre de lignes traitées
    ]);
    
    // Limiter le nombre de lignes de log à 1000
    // (garder l'en-tête + 1000 lignes de données)
    const maxRows = 1001;
    if (sheet.getLastRow() > maxRows) {
      const rowsToDelete = sheet.getLastRow() - maxRows;
      sheet.deleteRows(2, rowsToDelete);
    }
    
  } catch (e) {
    // En cas d'erreur lors du logging, ne rien faire
    // (éviter les erreurs en cascade)
    console.error('Error logging to TECHLOG:', e.message);
  }
}

