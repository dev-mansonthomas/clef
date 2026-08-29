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
/**
 * Réveille l'API et attend qu'elle soit prête, AVANT d'envoyer un lot.
 *
 * ⚠️ Pourquoi un réveil séparé plutôt qu'un simple réessai du POST.
 *
 * Le service tourne en « scale to zero » : la première requête après une mise en
 * veille paie un démarrage à froid — chargement de l'instantané Redis, montage du
 * volume GCS — et ce démarrage peut échouer (constaté le 2026-08-28 : 503 après 9,8 s,
 * montage GCS en échec, la requête n'ayant jamais atteint l'application).
 *
 * ⚠️ Il est IMPOSSIBLE de « demander avant d'envoyer » si l'instance dort : la question
 * est elle-même ce qui la réveille. Demander ne coûte donc rien de plus qu'envoyer —
 * sauf que `/health` pèse quelques centaines d'octets là où un instantané du
 * référentiel en pèse des centaines de milliers. C'est tout l'intérêt : on paie le
 * démarrage à froid sur la requête bon marché, et le lot part sur une instance chaude.
 *
 * @return {boolean} true si l'API a répondu, false après épuisement des tentatives
 */
function wakeUpApi() {
  if (!CONFIG.API_BASE_URL) {
    throw new Error(
      'CLEF_API_URL non configurée dans les propriétés du script ' +
      '(ex. https://dev.clef.paquerette.com).'
    );
  }

  const attentes = [5000, 10000, 20000];

  for (let essai = 0; essai <= attentes.length; essai++) {
    // `/health` n'exige aucune authentification et ne traverse pas le proxy nginx :
    // c'est le point d'entrée le moins coûteux qui prouve que le backend répond.
    const response = UrlFetchApp.fetch(CONFIG.API_BASE_URL + '/health', {
      method: 'get',
      muteHttpExceptions: true
    });

    if (response.getResponseCode() === 200) {
      if (essai > 0) {
        console.info('API réveillée au ' + (essai + 1) + 'e essai.');
      }
      return true;
    }

    if (essai === attentes.length) {
      console.warn(
        'API toujours indisponible (' + response.getResponseCode() + ') après ' +
        (attentes.length + 1) + ' tentatives — le lot est tenté quand même.'
      );
      return false;
    }

    Utilities.sleep(attentes[essai]);
  }

  return false;
}

function callApi(endpoint, method = 'GET', payload = null) {
  // Vérifier que l'API Key est configurée
  if (!CONFIG.API_KEY) {
    throw new Error('API Key not configured. Please set CLEF_API_KEY in script properties.');
  }

  // Et l'URL : elle n'a plus de défaut, parce que le défaut d'avant n'existait pas.
  if (!CONFIG.API_BASE_URL) {
    throw new Error(
      'CLEF_API_URL non configurée dans les propriétés du script ' +
      '(ex. https://dev.clef.paquerette.com).'
    );
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

  // ⚠️ RÉESSAIS sur 5xx — le service est en « scale to zero ».
  //
  // Constaté le 2026-08-28 : une synchronisation a échoué en « API Error 503 » après
  // 9,8 s. La requête n'avait jamais atteint l'application — Cloud Run n'était pas
  // parvenu à démarrer l'instance (le montage GCS du volume d'instantanés avait
  // échoué). L'instance suivante a démarré normalement.
  //
  // Avec MIN_INSTANCES=0, toute requête qui arrive après une mise en veille paie un
  // démarrage à froid, et un démarrage à froid peut échouer. Un 503 est donc un état
  // NORMAL de ce déploiement, pas une anomalie : il doit être réessayé, pas rapporté.
  //
  // On ne réessaie QUE les 5xx et le 429. Un 401, 403 ou 422 est un refus motivé —
  // clé API invalide, périmètre refusé, données non conformes : le réessayer masquerait
  // la cause et enverrait trois fois le même lot.
  const attentes = [15000, 30000]; // ms avant le 2e puis le 3e essai
  let response;
  let responseCode;

  for (let essai = 0; essai <= attentes.length; essai++) {
    response = UrlFetchApp.fetch(url, options);
    responseCode = response.getResponseCode();

    if (responseCode === 200) {
      if (essai > 0) {
        console.info('Requête aboutie au ' + (essai + 1) + 'e essai (' + endpoint + ').');
      }
      return JSON.parse(response.getContentText());
    }

    const reessayable = responseCode >= 500 || responseCode === 429;
    if (!reessayable || essai === attentes.length) {
      break;
    }

    console.warn(
      'API ' + responseCode + ' sur ' + endpoint + ' — nouvelle tentative dans ' +
      (attentes[essai] / 1000) + ' s (démarrage à froid probable).'
    );
    Utilities.sleep(attentes[essai]);
  }

  throw new Error(`API Error ${responseCode}: ${response.getContentText()}`);
}

