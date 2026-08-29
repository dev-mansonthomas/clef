/**
 * Configuration CLEF Apps Script
 * 
 * Ce fichier contient toutes les constantes de configuration pour les scripts
 * de synchronisation entre la Google Spreadsheet et l'API CLEF.
 */

const CONFIG = {
  // URL de base de l'API CLEF — DOIT être configurée dans les propriétés du script.
  //
  // ⚠️ Aucun défaut, volontairement. Il y en avait un — « https://clef-api.run.app » —
  // et cette URL n'a jamais existé : un classeur mal configuré échouait donc sur une
  // résolution DNS, message qui ne dit rien de la vraie cause. Un défaut qui ne peut
  // pas fonctionner est pire que pas de défaut : il déplace l'erreur loin de sa cause.
  API_BASE_URL: PropertiesService.getScriptProperties().getProperty('CLEF_API_URL'),
  
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
    // Onglet du classeur « CLEF Benevoles ». Surchargeable par la propriété de
    // script CLEF_SHEET_BENEVOLES si le classeur venait à le renommer.
    BENEVOLES: PropertiesService.getScriptProperties()
      .getProperty('CLEF_SHEET_BENEVOLES') || 'Bénévoles',
    TECHLOG: 'TECHLOG',
    // Détail ligne par ligne des erreurs de la dernière synchronisation. Créé et
    // réécrit automatiquement — voir logger.gs.
    ERREURS: 'ERREURS SYNCHRO'
  }
};

