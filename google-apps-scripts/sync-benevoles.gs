/**
 * Synchronisation du référentiel bénévoles vers CLEF
 *
 * ⚠️ Ce script s'installe dans le classeur **« CLEF Benevoles »**, qui reçoit l'import
 * périodique du référentiel bénévole du département. Il lit l'onglet « Bénévoles » et
 * envoie les lignes brutes à l'API CLEF.
 *
 * Partage de propriété — à comprendre avant toute modification :
 *
 *   • La feuille possède l'IDENTITÉ : Nivol, Nom, Prénom, UL, Téléphone, Email.
 *   • CLEF possède l'ORGANISATION : statut, responsabilité d'UL, fonctions DT.
 *
 * La synchronisation écrase la première et ne touche jamais la seconde. N'ajoutez donc
 * pas de colonne « rôle » ou « statut » à la feuille en espérant qu'elle soit reprise :
 * elle serait ignorée.
 *
 * Le lot envoyé est un INSTANTANÉ COMPLET de la délégation. C'est ce qui permet à CLEF
 * de désactiver les bénévoles qui n'y figurent plus — donc de leur retirer l'accès.
 * Conséquence directe : ne jamais synchroniser depuis une feuille filtrée ou tronquée.
 * CLEF refuse de désactiver au-delà de 20 % des actifs en une passe, mais ce garde-fou
 * est un filet, pas une autorisation.
 *
 * Voir docs/specs/synchronisation-referentiel-benevoles.md
 *
 * Trigger : toutes les heures
 */

/**
 * Synchronise les bénévoles vers CLEF.
 * Appelé automatiquement par le trigger horaire.
 */
function syncBenevoles() {
  const startTime = new Date();

  try {
    const sheetName = CONFIG.SHEETS.BENEVOLES;
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);

    if (!sheet) {
      throw new Error(
        `Onglet "${sheetName}" introuvable dans ce classeur. ` +
        `Ce script doit être installé dans « CLEF Benevoles ».`
      );
    }

    const data = sheet.getDataRange().getValues();

    if (data.length < 2) {
      // Seulement l'en-tête, ou feuille vide. On n'envoie RIEN : un lot vide serait
      // interprété par CLEF comme « aucun bénévole », et c'est précisément le mode de
      // panne dont il faut se prémunir. CLEF le refuserait de toute façon, mais mieux
      // vaut ne pas lui poser la question.
      logError('Bénévoles', startTime,
        'Onglet vide ou réduit à son en-tête : synchronisation annulée.');
      return;
    }

    // La première ligne porte les en-têtes. Ils constituent le contrat d'API : les
    // clés envoyées sont les libellés de colonnes, et le backend les attend
    // littéralement — « Nivol », « Nom », « Prénom », « UL », « Téléphone », « Email ».
    // Renommer une colonne casse la synchronisation ; le backend nommera la colonne
    // manquante dans sa réponse.
    const headers = data[0];

    const rows = data.slice(1)
      .map(function (row) {
        const obj = {};
        headers.forEach(function (header, index) {
          obj[String(header).trim()] = row[index];
        });
        return obj;
      })
      // Les feuilles importées comportent souvent des lignes vides en queue : les
      // envoyer produirait autant d'erreurs de ligne inutiles dans le rapport.
      .filter(function (obj) {
        return Object.keys(obj).some(function (key) {
          return String(obj[key] || '').trim() !== '';
        });
      });

    if (rows.length === 0) {
      logError('Bénévoles', startTime,
        'Aucune ligne de données exploitable : synchronisation annulée.');
      return;
    }

    const endpoint = `/api/sync/${CONFIG.DT}/benevoles`;
    const result = callApi(endpoint, 'POST', rows);

    // Journaliser le détail, et non un simple « OK ». Une synchronisation
    // partiellement réussie — lignes en erreur, réconciliation abandonnée — passait
    // auparavant pour un succès complet.
    const summary =
      `${result.created} créé(s), ${result.updated} mis à jour, ` +
      `${result.reactivated} réactivé(s), ${result.deactivated} désactivé(s)`;

    if (result.reconciliation_skipped) {
      logError('Bénévoles', startTime,
        `RÉCONCILIATION ABANDONNÉE — ${result.reconciliation_skipped_reason} ` +
        `(${summary})`);
      return;
    }

    if (result.errors && result.errors.length > 0) {
      const details = result.errors.slice(0, 10).map(function (e) {
        return `ligne ${e.line} : ${e.reason}`;
      }).join(' | ');
      logError('Bénévoles', startTime,
        `${result.errors.length} ligne(s) en erreur — ${summary}. ${details}`);
      return;
    }

    logSuccess('Bénévoles', startTime, result.created + result.updated);

  } catch (e) {
    logError('Bénévoles', startTime, e.message);
    throw e; // Re-throw pour que le trigger enregistre l'erreur
  }
}
