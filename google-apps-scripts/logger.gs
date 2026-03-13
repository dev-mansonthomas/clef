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
    // Récupérer l'onglet TECHLOG
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.TECHLOG);
    
    if (!sheet) {
      // Si l'onglet TECHLOG n'existe pas, ne pas logger (éviter les erreurs en cascade)
      return;
    }
    
    // Calculer la durée de l'opération en millisecondes
    const duration = new Date() - startTime;
    
    // Ajouter une nouvelle ligne avec les informations de log
    sheet.appendRow([
      new Date().toISOString(),  // Timestamp au format ISO
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

