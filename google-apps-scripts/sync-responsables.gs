/**
 * Synchronisation des responsables de véhicules
 * 
 * Ce script récupère la liste des responsables depuis l'API CLEF
 * et met à jour l'onglet "Responsables Véhicules" de la Spreadsheet.
 * 
 * Trigger : Toutes les heures
 */

/**
 * Synchronise les responsables de véhicules
 * Appelé automatiquement par le trigger toutes les heures
 */
function syncResponsables() {
  const startTime = new Date();
  
  try {
    // Appeler l'API pour récupérer les responsables
    const endpoint = `/api/sync/${CONFIG.DT}/responsables`;
    const data = callApi(endpoint);
    
    // Récupérer l'onglet Responsables Véhicules
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.RESPONSABLES);
    
    if (!sheet) {
      throw new Error(`Sheet "${CONFIG.SHEETS.RESPONSABLES}" not found`);
    }
    
    // Effacer les données existantes (garder l'en-tête en ligne 1)
    if (sheet.getLastRow() > 1) {
      sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).clearContent();
    }
    
    // Écrire les nouvelles données
    if (data && data.length > 0) {
      // Extraire les en-têtes depuis le premier objet
      const headers = Object.keys(data[0]);
      
      // Convertir les objets en tableau de valeurs
      const rows = data.map(item => headers.map(h => item[h] || ''));
      
      // Écrire les données dans la feuille (à partir de la ligne 2)
      sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
    }
    
    // Logger le succès
    logSuccess('Responsables', startTime, data ? data.length : 0);
    
  } catch (e) {
    // Logger l'erreur
    logError('Responsables', startTime, e.message);
    throw e; // Re-throw pour que le trigger enregistre l'erreur
  }
}

