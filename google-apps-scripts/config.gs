/**
 * Configuration CLEF Apps Script
 * 
 * Ce fichier contient toutes les constantes de configuration pour les scripts
 * de synchronisation entre la Google Spreadsheet et l'API CLEF.
 */

const CONFIG = {
  // URL de base de l'API CLEF
  // Peut être surchargée via les propriétés du script
  API_BASE_URL: PropertiesService.getScriptProperties().getProperty('CLEF_API_URL') || 'https://clef-api.run.app',
  
  // API Key pour l'authentification
  // DOIT être configurée dans les propriétés du script
  API_KEY: PropertiesService.getScriptProperties().getProperty('CLEF_API_KEY'),
  
  // Code de la délégation territoriale
  // Par défaut DT75, peut être surchargé via les propriétés du script
  DT: PropertiesService.getScriptProperties().getProperty('CLEF_DT') || 'DT75',
  
  // Noms des onglets de la Spreadsheet
  SHEETS: {
    REFERENTIEL: 'Référentiel',
    RESPONSABLES: 'Responsables Véhicules',
    BENEVOLES: 'Bénévoles',
    TECHLOG: 'TECHLOG'
  }
};

