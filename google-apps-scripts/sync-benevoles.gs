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
    // littéralement.
    //
    //   OBLIGATOIRES  « Nivol », « Nom », « Prénom », « UL », « id_structure »
    //   FACULTATIVES  « Téléphone », « Email »
    //   IGNORÉES      toute autre, dont « Prénom Nom »
    //
    // ⚠️ « id_structure » est l'identifiant interne Croix-Rouge de l'UNITÉ LOCALE, et il
    // doit être un entier positif. Il rend stricte la jointure avec le référentiel
    // national des structures, là où « UL » n'est qu'un libellé libre.
    //
    // Renommer une colonne casse la synchronisation ; le backend nomme la colonne
    // manquante dans sa réponse, et l'onglet ERREURS SYNCHRO la porte en clair.
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

    // Payer le démarrage à froid sur une requête bon marché, pas sur le lot.
    wakeUpApi();

    const endpoint = `/api/sync/${CONFIG.DT}/benevoles`;
    const result = callApi(endpoint, 'POST', rows);

    // Journaliser le détail, et non un simple « OK ». Une synchronisation
    // partiellement réussie — lignes en erreur, réconciliation abandonnée — passait
    // auparavant pour un succès complet.
    const summary =
      `${result.created} créé(s), ${result.updated} mis à jour, ` +
      `${result.reactivated} réactivé(s), ${result.deactivated} désactivé(s)` +
      (result.rattachements_dt
        ? `, ${result.rattachements_dt} rattaché(s) à la DT`
        : '');

    if (result.reconciliation_skipped) {
      logError('Bénévoles', startTime,
        `RÉCONCILIATION ABANDONNÉE — ${result.reconciliation_skipped_reason} ` +
        `(${summary})`);
      return;
    }

    if (result.errors && result.errors.length > 0) {
      // ⚠️ Un DÉNOMBREMENT PAR NATURE avant le détail.
      //
      // Le journal listait les dix premières erreurs et leur nombre total. Sur le
      // premier import réel — 120 erreurs sur 4546 lignes — c'était insuffisant pour
      // répondre à la seule question qui compte : « de quoi s'agit-il ? ». Dix lignes
      // ne disent pas si les 110 autres sont de la même nature.
      const parNature = {};
      // Un simple comptage : l'API garantit une `reason` CONSTANTE, les valeurs étant
      // dans `values`. Cette boucle effaçait auparavant nivols, décomptes et libellés
      // d'UL à coups d'expressions régulières — donc devinait ce qui variait, et se
      // serait trompée au premier message de forme nouvelle.
      result.errors.forEach(function (e) {
        const nature = String(e.reason);
        parNature[nature] = (parNature[nature] || 0) + 1;
      });
      const resume = Object.keys(parNature)
        .sort(function (a, b) { return parNature[b] - parNature[a]; })
        .map(function (nature) { return `${parNature[nature]}× ${nature}`; })
        .join(' | ');

      const details = result.errors.slice(0, 5).map(function (e) {
        return `ligne ${e.line}`;
      }).join(', ');

      // Le détail va dans son propre onglet : c'est là qu'on corrige la feuille.
      logErrorsDetail('Bénévoles', result.errors);

      logError('Bénévoles', startTime,
        `${result.errors.length} ligne(s) en erreur — ${summary}. ` +
        `NATURES : ${resume}. Premières lignes : ${details}. ` +
        `Détail complet dans l'onglet « ${CONFIG.SHEETS.ERREURS} ».`);
      return;
    }

    // ⚠️ Vider le détail en cas de succès : laisser les erreurs de la passe
    // précédente ferait croire à un problème résolu qu'il faut encore corriger.
    logErrorsDetail('Bénévoles', []);

    logSuccess('Bénévoles', startTime, result.created + result.updated);

  } catch (e) {
    logError('Bénévoles', startTime, e.message);
    throw e; // Re-throw pour que le trigger enregistre l'erreur
  }
}
