/**
 * Installation des déclencheurs (« triggers ») CLEF
 *
 * ⚠️ Un déclencheur Apps Script ne se versionne pas : il vit dans le projet de script,
 * attaché au compte qui l'a créé. La documentation décrivait donc un chemin de clics à
 * refaire à l'identique dans chaque classeur — et un chemin de clics est une étape
 * qu'on oublie, ou qu'on refait de travers (deux déclencheurs pour une même fonction,
 * donc deux synchronisations concurrentes).
 *
 * Ces fonctions rendent l'opération idempotente et vérifiable : `installBenevolesTrigger`
 * remplace ce qui existe, `listTriggers` dit ce qui est réellement installé.
 *
 * À lancer UNE FOIS depuis l'éditeur, ou depuis le menu « 🚗 CLEF ».
 */

/** Périodicités acceptées par Apps Script pour un déclencheur horaire. */
const HEURES_AUTORISEES = [1, 2, 4, 6, 8, 12];

/**
 * (Ré)installe le déclencheur horaire de synchronisation des bénévoles.
 *
 * Périodicité : propriété de script `CLEF_SYNC_BENEVOLES_HOURS`, 1 heure par défaut.
 *
 * ⚠️ Tout déclencheur existant sur `syncBenevoles` est SUPPRIMÉ d'abord. Sans cela,
 * relancer cette fonction empilerait les déclencheurs : deux instantanés complets
 * envoyés en parallèle, et une réconciliation qui court contre elle-même.
 */
function installBenevolesTrigger() {
  const heures = Number(
    PropertiesService.getScriptProperties().getProperty('CLEF_SYNC_BENEVOLES_HOURS') || 1
  );

  if (HEURES_AUTORISEES.indexOf(heures) === -1) {
    throw new Error(
      'CLEF_SYNC_BENEVOLES_HOURS = ' + heures + ' : Apps Script n\'accepte que ' +
      HEURES_AUTORISEES.join(', ') + ' heures pour un déclencheur horaire.'
    );
  }

  const supprimes = removeBenevolesTriggers();

  ScriptApp.newTrigger('syncBenevoles')
    .timeBased()
    .everyHours(heures)
    .create();

  const message = 'Déclencheur installé : syncBenevoles toutes les ' + heures +
    ' h' + (supprimes > 0 ? ' (' + supprimes + ' ancien(s) remplacé(s))' : '');
  console.info(message);
  return message;
}

/**
 * Supprime tous les déclencheurs portant sur `syncBenevoles`.
 * @return {number} combien ont été supprimés
 */
function removeBenevolesTriggers() {
  let supprimes = 0;
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'syncBenevoles') {
      ScriptApp.deleteTrigger(trigger);
      supprimes += 1;
    }
  });
  return supprimes;
}

/**
 * Liste ce qui est RÉELLEMENT installé — la seule source de vérité.
 *
 * L'interface des déclencheurs se consulte à trois clics ; cette fonction répond dans
 * le journal d'exécution, et sert à vérifier après coup qu'on n'a pas empilé.
 */
function listTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  if (triggers.length === 0) {
    console.info('Aucun déclencheur installé dans ce projet.');
    return [];
  }
  const lignes = triggers.map(function (t) {
    return t.getHandlerFunction() + ' — ' + t.getEventType();
  });
  lignes.forEach(function (l) { console.info(l); });
  return lignes;
}
