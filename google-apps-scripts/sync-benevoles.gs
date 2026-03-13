/**
 * Synchronisation des bénévoles vers Valkey
 * 
 * Ce script lit l'onglet "Bénévoles" de la Spreadsheet
 * et envoie les données vers l'API CLEF pour stockage dans Valkey.
 * 
 * Trigger : Toutes les heures
 */

/**
 * Synchronise les bénévoles vers Valkey
 * Appelé automatiquement par le trigger toutes les heures
 */
function syncBenevoles() {
  const startTime = new Date();
  
  try {
    // Récupérer l'onglet Bénévoles
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEETS.BENEVOLES);
    
    if (!sheet) {
      throw new Error(`Sheet "${CONFIG.SHEETS.BENEVOLES}" not found`);
    }
    
    // Récupérer toutes les données de l'onglet
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) {
      // Pas de données (seulement l'en-tête ou vide)
      logSuccess('Bénévoles', startTime, 0);
      return;
    }
    
    // La première ligne contient les en-têtes
    const headers = data[0];
    
    // Convertir les lignes en objets
    const benevoles = data.slice(1).map(row => {
      const obj = {};
      headers.forEach((header, index) => {
        obj[header] = row[index];
      });
      return obj;
    });
    
    // Envoyer les données à l'API
    const endpoint = `/api/sync/${CONFIG.DT}/benevoles`;
    const result = callApi(endpoint, 'POST', benevoles);
    
    // Logger le succès avec le nombre de bénévoles traités
    const count = result.count || benevoles.length;
    logSuccess('Bénévoles', startTime, count);
    
  } catch (e) {
    // Logger l'erreur
    logError('Bénévoles', startTime, e.message);
    throw e; // Re-throw pour que le trigger enregistre l'erreur
  }
}

