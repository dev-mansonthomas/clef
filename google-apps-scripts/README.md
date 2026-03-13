# CLEF Google Apps Script - Installation Guide

Ce guide explique comment installer les scripts Apps Script pour synchroniser les données entre la Google Spreadsheet et le backend CLEF.

## Prérequis

- Accès à la Google Spreadsheet CLEF
- Droits d'édition sur la Spreadsheet
- API Key CLEF fournie par l'administrateur
- URL de l'API CLEF (par défaut : https://clef-api.run.app)

## Installation

### 1. Ouvrir l'éditeur Apps Script

1. Ouvrir la Google Spreadsheet CLEF
2. Menu **Extensions** > **Apps Script**
3. Un nouvel onglet s'ouvre avec l'éditeur Apps Script

### 2. Créer les fichiers de script

Dans l'éditeur Apps Script, créer les fichiers suivants (bouton **+** à côté de "Fichiers") :

1. **config.gs** - Copier le contenu du fichier `config.gs`
2. **api.gs** - Copier le contenu du fichier `api.gs`
3. **sync-referentiel.gs** - Copier le contenu du fichier `sync-referentiel.gs`
4. **sync-responsables.gs** - Copier le contenu du fichier `sync-responsables.gs`
5. **sync-benevoles.gs** - Copier le contenu du fichier `sync-benevoles.gs`
6. **menu.gs** - Copier le contenu du fichier `menu.gs`
7. **logger.gs** - Copier le contenu du fichier `logger.gs`

Vous pouvez supprimer le fichier `Code.gs` par défaut s'il existe.

### 3. Configurer les propriétés du script

1. Dans l'éditeur Apps Script, cliquer sur **Paramètres du projet** (icône engrenage)
2. Aller dans **Propriétés du script**
3. Ajouter les propriétés suivantes :

| Propriété | Valeur | Description |
|-----------|--------|-------------|
| `CLEF_API_URL` | `https://clef-api.run.app` | URL de l'API CLEF |
| `CLEF_API_KEY` | `votre-api-key` | API Key fournie par l'admin |
| `CLEF_DT` | `DT75` | Code de la délégation territoriale |

### 4. Créer l'onglet TECHLOG

Dans la Google Spreadsheet, créer un nouvel onglet nommé **TECHLOG** avec les colonnes suivantes :

| Timestamp | Onglet | Statut | Message | Durée (ms) | Lignes |
|-----------|--------|--------|---------|------------|--------|

### 5. Configurer les triggers (déclencheurs)

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

