/**
 * Menu personnalisé CLEF
 * 
 * Ce script ajoute un menu "🚗 CLEF" dans la barre de menu de la Spreadsheet
 * avec des boutons pour déclencher manuellement les synchronisations.
 */

/**
 * Fonction appelée automatiquement à l'ouverture de la Spreadsheet
 * Crée le menu personnalisé CLEF
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🚗 CLEF')
    .addItem('🔄 Refresh Référentiel', 'syncReferentiel')
    .addItem('🔄 Refresh Responsables', 'syncResponsables')
    .addItem('📤 Push Bénévoles', 'syncBenevoles')
    .addSeparator()
    .addItem('⚙️ Configuration', 'showConfig')
    .addToUi();
}

/**
 * Affiche la configuration actuelle dans une boîte de dialogue
 */
function showConfig() {
  const ui = SpreadsheetApp.getUi();
  
  // Construire le message de configuration
  const apiUrl = CONFIG.API_BASE_URL;
  const dt = CONFIG.DT;
  const apiKeyStatus = CONFIG.API_KEY ? '***configured***' : 'NOT SET';
  
  const message = `API URL: ${apiUrl}\nDT: ${dt}\nAPI Key: ${apiKeyStatus}`;
  
  ui.alert('Configuration CLEF', message, ui.ButtonSet.OK);
}

