/**
 * Fonctions pour appeler l'API CLEF
 */

/**
 * Appelle un endpoint de l'API CLEF
 * 
 * @param {string} endpoint - Le chemin de l'endpoint (ex: '/api/sync/DT75/vehicules')
 * @param {string} method - La méthode HTTP (GET, POST, PUT, DELETE)
 * @param {Object} payload - Les données à envoyer (pour POST/PUT)
 * @return {Object} La réponse JSON de l'API
 * @throws {Error} Si l'API retourne une erreur
 */
function callApi(endpoint, method = 'GET', payload = null) {
  // Vérifier que l'API Key est configurée
  if (!CONFIG.API_KEY) {
    throw new Error('API Key not configured. Please set CLEF_API_KEY in script properties.');
  }
  
  // Options de la requête HTTP
  const options = {
    method: method,
    headers: {
      'X-API-Key': CONFIG.API_KEY,
      'Content-Type': 'application/json'
    },
    muteHttpExceptions: true
  };
  
  // Ajouter le payload pour les requêtes POST/PUT
  if (payload) {
    options.payload = JSON.stringify(payload);
  }
  
  // Construire l'URL complète
  const url = CONFIG.API_BASE_URL + endpoint;
  
  // Effectuer la requête
  const response = UrlFetchApp.fetch(url, options);
  const responseCode = response.getResponseCode();
  
  // Vérifier le code de réponse
  if (responseCode !== 200) {
    throw new Error(`API Error ${responseCode}: ${response.getContentText()}`);
  }
  
  // Parser et retourner la réponse JSON
  return JSON.parse(response.getContentText());
}

