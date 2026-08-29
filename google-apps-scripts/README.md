# CLEF Google Apps Script - Installation Guide

Ce guide explique comment installer les scripts Apps Script pour synchroniser les données entre la Google Spreadsheet et le backend CLEF.

## Prérequis

- Accès à la Google Spreadsheet CLEF
- Droits d'édition sur la Spreadsheet
- API Key CLEF fournie par l'administrateur
- URL de l'API CLEF (par défaut : https://dev.clef.paquerette.com)

## Installation

### 1. Ouvrir l'éditeur Apps Script

1. Ouvrir la Google Spreadsheet CLEF
2. Menu **Extensions** > **Apps Script**
3. Un nouvel onglet s'ouvre avec l'éditeur Apps Script

### 2. Créer les fichiers de script

⚠️ **Il y a DEUX classeurs, et ils ne reçoivent pas les mêmes fichiers.** Les scripts
de synchronisation lisent chacun un onglet précis : installer `sync-referentiel.gs`
dans « CLEF Benevoles » produirait une erreur « Onglet Référentiel introuvable » à
chaque déclenchement.

| Fichier | Référentiel Véhicules | CLEF Benevoles |
|---|:---:|:---:|
| `config.gs` | ✅ | ✅ |
| `api.gs` | ✅ | ✅ |
| `logger.gs` | ✅ | ✅ |
| `triggers.gs` | — | ✅ |
| `sync-referentiel.gs` | ✅ | ❌ |
| `sync-responsables.gs` | ✅ | ❌ |
| `sync-benevoles.gs` | ❌ | ✅ |
| `menu.gs` | ✅ | ⚠️ à adapter |

⚠️ **`menu.gs` dans « CLEF Benevoles »** : son `onOpen` déclare des entrées
« Refresh Référentiel » et « Refresh Responsables » dont les fonctions n'existent pas
dans ce classeur — elles échoueraient en « Script function not found ». Y remplacer
`onOpen` par :

```javascript
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🚗 CLEF')
    .addItem('📤 Push Bénévoles', 'syncBenevoles')
    .addItem('⏰ Installer le déclencheur horaire', 'installBenevolesTrigger')
    .addItem('🔍 Lister les déclencheurs', 'listTriggers')
    .addSeparator()
    .addItem('⚙️ Configuration', 'showConfig')
    .addToUi();
}
```

Dans l'éditeur Apps Script, créer les fichiers voulus (bouton **+** à côté de
« Fichiers ») en copiant le contenu de chacun. Vous pouvez supprimer le `Code.gs` par
défaut s'il existe.

### 3. Configurer les propriétés du script

1. Dans l'éditeur Apps Script, cliquer sur **Paramètres du projet** (icône engrenage)
2. Aller dans **Propriétés du script**
3. Ajouter les propriétés suivantes :

| Propriété | Valeur | Description |
|-----------|--------|-------------|
| `CLEF_API_URL` | `https://dev.clef.paquerette.com` | URL de l'API CLEF. ⚠️ **Obligatoire, sans défaut** : `config.gs` retombait sur `https://clef-api.run.app`, une URL qui n'a jamais existé — l'échec survenait alors sur une résolution DNS, loin de sa cause. Absente, `callApi` refuse en le nommant |
| `CLEF_API_KEY` | `votre-api-key` | API Key fournie par l'admin |
| `CLEF_DT` | `DT75` | Code de la délégation territoriale |

### 4. Créer l'onglet TECHLOG

**Rien à faire : `logger.gs` le crée au premier passage**, en dernière position, avec
son en-tête figé :

| Timestamp | Onglet | Statut | Message | Durée (ms) | Lignes |
|-----------|--------|--------|---------|------------|--------|

⚠️ Auparavant, un onglet absent faisait **renoncer au journal en silence** : la
synchronisation tournait et personne ne savait ce qu'elle avait fait. Si la création
échoue — classeur en lecture seule —, le journal est abandonné mais la synchronisation
aboutit : c'est le seul ordre de priorité acceptable.

Le journal est plafonné à 1000 lignes ; les plus anciennes sont supprimées.

### Les libellés de colonnes sont un contrat que nous ne possédons pas

L'onglet « Bénévoles » reçoit l'import du **référentiel bénévole**, issu de Gaia. Ses
libellés de colonnes — dont **`Id Structure`** — forment un contrat d'interface entre ce
référentiel et les **plusieurs classeurs qui l'importent**, dont CLEF n'est qu'un.

⚠️ **Le script ne les renomme donc pas.** Une version l'a fait brièvement, corrigeant
`Id Structure` en `id_structure` : c'était modifier un contrat qui ne nous appartient
pas, au détriment des autres consommateurs. Retiré.

C'est l'API qui s'adapte : `Id Structure` est son libellé attendu, et la comparaison des
en-têtes y est **normalisée** — sans accent, sans casse, sans séparateur. `Id Structure`,
`ID STRUCTURE` et `Id_Structure` sont donc reconnus, ce qui absorbe une dérive
d'écriture sans rien exiger de la feuille. Un vrai renommage — `Nom` → `Patronyme` —
reste refusé, et le message nomme la colonne attendue **et** les en-têtes reçus.

### L'onglet « ERREURS SYNCHRO »

Créé de la même façon, et **réécrit** à chaque synchronisation — une ligne par erreur,
**une colonne par donnée** :

| Horodatage | Onglet | Ligne | Nivol | Nom | Prénom | UL 1 | UL 2 | Détail | Raison |
|---|---|---|---|---|---|---|---|---|---|

⚠️ **La `Raison` est une constante** : `Colonne absente`, `Champ invalide`,
`Doublon : unités locales différentes`, `Doublon : plus de deux unités locales`,
`Doublon : identité divergente`. Aucune donnée n'y est interpolée.

C'est ce qui rend l'onglet **triable** — par `UL 1` pour traiter une unité locale à la
fois, par `Raison` pour ne voir qu'une nature — et **dénombrable** : le résumé du
TECHLOG est un simple comptage, là où il devait auparavant effacer nivols, décomptes et
libellés d'UL à coups d'expressions régulières, donc deviner ce qui variait.

`Détail` porte le complément textuel selon la nature : la colonne manquante, le champ
invalide, ou les unités locales au-delà de la deuxième.

⚠️ Le TECHLOG ne peut pas porter ce détail — une cellule par synchronisation, et
37 erreurs n'y tiennent pas. Il donne un dénombrement par nature, qui répond à « de
quoi s'agit-il ? » ; cet onglet répond à « **quelles lignes corriger ?** », et c'est
celle-là qui fait agir : ces erreurs se corrigent dans la feuille.

Réécrit, et non complété : ces erreurs décrivent l'état **courant** de la feuille, pas
une histoire. Il est vidé quand une synchronisation ne rapporte plus d'erreur — sans
quoi un problème résolu continuerait de s'afficher.

### 5. Configurer les triggers (déclencheurs)

### Dans « CLEF Benevoles » : une fonction, pas un chemin de clics

Lancer **une fois** `installBenevolesTrigger` depuis l'éditeur (ou le menu « 🚗 CLEF ») :

```
Déclencheur installé : syncBenevoles toutes les 1 h
```

La fonction est **idempotente** — elle supprime d'abord tout déclencheur existant sur
`syncBenevoles`. ⚠️ Sans cette précaution, la relancer empilerait les déclencheurs :
deux instantanés complets envoyés en parallèle, et une réconciliation qui court contre
elle-même. `listTriggers` dit ce qui est réellement installé.

Périodicité : propriété de script `CLEF_SYNC_BENEVOLES_HOURS`, 1 heure par défaut.
Apps Script n'accepte que 1, 2, 4, 6, 8 ou 12 — toute autre valeur est refusée avec ce
message plutôt qu'ignorée.

⚠️ Un déclencheur appartient au **compte qui l'a créé** et s'exécute sous son identité.
Si ce compte perd l'accès au classeur, la synchronisation s'arrête — et c'est Google
qui prévient, par son récapitulatif quotidien d'échecs de déclencheurs.

### Dans « Référentiel Véhicules » : à la main

1. Dans l'éditeur Apps Script, cliquer sur **Déclencheurs** (icône horloge)
2. Cliquer sur **+ Ajouter un déclencheur**
3. Créer les déclencheurs suivants :

#### Trigger 1 : Sync Référentiel (toutes les 1 minute)
- Fonction : `syncReferentiel`
- Source de l'événement : **Temporel**
- Type de déclencheur temporel : **Minuteur**
- Intervalle : **Toutes les minutes**

#### Trigger 2 : Sync Responsables (toutes les heures)
- Fonction : `syncResponsables`
- Source de l'événement : **Temporel**
- Type de déclencheur temporel : **Minuteur**
- Intervalle : **Toutes les heures**

#### Trigger 3 : Push Bénévoles (toutes les heures)
- Fonction : `syncBenevoles`
- Source de l'événement : **Temporel**
- Type de déclencheur temporel : **Minuteur**
- Intervalle : **Toutes les heures**
- ⚠️ **Classeur d'installation : « CLEF Benevoles »**, onglet **« Bénévoles »**

##### Ce que la synchronisation des bénévoles écrit — et n'écrit pas

Le référentiel bénévoles a un partage de propriété strict
(`docs/specs/synchronisation-referentiel-benevoles.md`) :

| Donnée | Propriétaire | Conséquence |
|---|---|---|
| Nivol, Nom, Prénom, UL, Téléphone, Email | **la feuille** | écrasés à chaque passage |
| statut, responsabilité d'UL, fonctions DT | **CLEF** | jamais touchés par la synchronisation |

Ajouter une colonne « rôle » ou « statut » à la feuille est donc sans effet : ces
informations se saisissent dans CLEF, et la synchronisation les préserve.

**Les en-têtes de colonnes sont le contrat d'API.** Les clés envoyées sont les
libellés lus en première ligne : `Nivol`, `Nom`, `Prénom`, `UL`, `Téléphone`, `Email`.
Renommer une colonne casse la synchronisation — le backend répond en nommant la
colonne manquante. La colonne `Prénom Nom` est ignorée.

**Le lot est un instantané complet du département.** C'est ce qui permet à CLEF de
désactiver les bénévoles qui n'y figurent plus, donc de leur **retirer l'accès**.
Ne jamais synchroniser depuis une feuille filtrée ou tronquée. CLEF refuse de
désactiver plus de 20 % des bénévoles actifs en une passe et abandonne alors la
réconciliation en le journalisant — c'est un filet de sécurité, pas une autorisation.

**Lire le TECHLOG.** Le script y journalise le détail : créés, mis à jour, réactivés,
désactivés, et les dix premières lignes en erreur. Une synchronisation partielle n'est
plus rapportée comme un succès.

#### Trigger 4 : Menu au chargement
- Fonction : `onOpen`
- Source de l'événement : **À l'ouverture de la feuille de calcul**

### 6. Autoriser les permissions

Lors de la première exécution, Google Apps Script demandera des autorisations :
- Accès à la Spreadsheet
- Accès aux services externes (API CLEF)

Accepter toutes les autorisations demandées.

### 7. Tester l'installation

1. Fermer et rouvrir la Spreadsheet
2. Vérifier que le menu **🚗 CLEF** apparaît dans la barre de menu
3. Cliquer sur **🚗 CLEF** > **🔄 Refresh Référentiel**
4. Vérifier que l'onglet **Référentiel** se remplit avec les données
5. Vérifier que l'onglet **TECHLOG** contient une ligne de log

## Utilisation

### Menu Extensions

Le menu **🚗 CLEF** propose les actions suivantes :

- **🔄 Refresh Référentiel** : Synchronise manuellement les véhicules depuis l'API
- **🔄 Refresh Responsables** : Synchronise manuellement les responsables depuis l'API
- **📤 Push Bénévoles** : Envoie manuellement les bénévoles vers Valkey
- **⚙️ Configuration** : Affiche la configuration actuelle

### Synchronisation automatique

Les triggers configurés assurent la synchronisation automatique :
- **Référentiel** : toutes les 1 minute
- **Responsables** : toutes les heures
- **Bénévoles** : toutes les heures

### Logs techniques

L'onglet **TECHLOG** enregistre toutes les opérations de synchronisation :
- Timestamp de l'opération
- Onglet concerné
- Statut (SUCCESS ou ERROR)
- Message d'erreur éventuel
- Durée de l'opération en millisecondes
- Nombre de lignes traitées

Les logs sont automatiquement limités aux 1000 dernières entrées.

## Dépannage

### Erreur "API Key not configured"
Vérifier que la propriété `CLEF_API_KEY` est bien configurée dans les paramètres du projet.

### Erreur "API Error 401"
L'API Key est invalide ou expirée. Contacter l'administrateur pour obtenir une nouvelle clé.

### Erreur "API Error 404"
L'URL de l'API est incorrecte ou le endpoint n'existe pas. Vérifier la propriété `CLEF_API_URL`.

### Les triggers ne s'exécutent pas
Vérifier dans **Déclencheurs** que les triggers sont bien actifs et qu'il n'y a pas d'erreurs d'exécution.

### L'onglet TECHLOG ne se remplit pas
Vérifier que l'onglet existe bien et qu'il s'appelle exactement **TECHLOG** (sensible à la casse).

## Support

Pour toute question ou problème, contacter l'équipe technique CLEF.

