# ADR 0007 — La feuille possède l'identité, CLEF possède l'organisation

**Statut :** accepté
**Date de la décision :** 2026-08-21
**Complète :** [ADR 0002 — Redis est la source de vérité applicative](0002-google-workspace-comme-referentiel-de-verite.md)

## Contexte

L'[ADR 0002](0002-google-workspace-comme-referentiel-de-verite.md) établit que Google
Sheets est la source **en amont** et Redis la source **dans** CLEF, le pont étant un
Apps Script de synchronisation. Il ne dit rien de ce qui se passe quand les deux côtés
veulent écrire la **même entité**.

Or c'est le cas des bénévoles, et l'implémentation d'origine tranchait implicitement en
faveur de la feuille : `set_benevole` faisait un `JSON.SET "$"`, donc un **remplacement
intégral du document**. Conséquences observées :

- Un Responsable UL nommé dans l'écran d'administration redevenait simple bénévole à la
  synchronisation suivante — au plus tard une heure après.
- Le `statut` porté par la feuille (« Actif ») n'était pas même importé : un bénévole
  parti restait indistinguable d'un bénévole en poste.
- La synchronisation ne supprimait ni ne désactivait jamais rien : un départ du
  département ne retirait aucun accès. Depuis la tâche N2, où l'authentification lit ce
  référentiel, c'était devenu un trou de révocation.

Le propriétaire a par ailleurs précisé le besoin : un bénévole **appartient toujours à
une UL** et **peut en plus** porter des fonctions à la DT. Le champ `role` à valeur
unique (`responsable_ul` | `responsable_dt` | null) ne pouvait pas l'exprimer.

## Décision

**La frontière de propriété est explicite, et structurelle.**

| Donnée | Propriétaire | Écrite par |
|---|---|---|
| `nivol`, `nom`, `prenom`, `ul`, `email`, `telephone` | **feuille** | synchronisation |
| `statut`, `responsable_ul`, `fonctions_dt` | **CLEF** | écran d'administration |

Trois conséquences de conception :

1. **Deux points d'entrée disjoints**, et non une convention à respecter :
   `upsert_benevole_identite(BenevoleIdentite)` n'accepte structurellement aucun champ
   d'organisation ; `set_benevole_organisation(...)` ne touche aucun champ d'identité.
   Il est impossible d'écraser l'un par l'autre par inadvertance.
2. **Le rôle applicatif n'est plus stocké, il est dérivé** — une fonction DT l'emporte
   sur la responsabilité d'UL, la personne pouvant être les deux. Un champ dérivé ne
   peut pas se désynchroniser de ce dont il dérive.
3. **Le lot de synchronisation est un instantané complet** du département : une absence
   est donc significative et vaut désactivation. C'est ce qui rend la révocation
   possible.

## Conséquences

**Acquis :**

- Ce qui est saisi dans CLEF y reste. C'était la panne la plus visible.
- Un départ du référentiel révoque l'accès dans l'heure, sans effacer l'historique :
  les entrées de carnet de bord et les réservations référencent le bénévole.
- La double appartenance UL + DT est représentable.
- Le téléphone est disponible pour joindre le chauffeur d'une réservation.

**Prix payé, assumé :**

- **La réconciliation peut retirer des accès en masse.** Une feuille filtrée ou tronquée
  ressemble en tout point à un départ collectif. D'où un garde-fou de ratio (20 % des
  actifs par défaut), un traitement à part du lot vide, une désactivation jamais
  destructrice, et un log nominatif par désactivation. Le garde-fou est un filet, pas
  une autorisation : c'est écrit dans le README de l'Apps Script.
- **L'ordre de déploiement devient contraignant.** Le code lit `responsable_ul` et
  `fonctions_dt` ; sur un document non migré, Pydantic donne `False` et `[]` — donc
  *tous* les responsables perdent leurs droits. La migration doit **précéder** le
  déploiement.
- **Une donnée personnelle de plus** à protéger : le téléphone. Exposé, sur décision du
  propriétaire, à tout utilisateur authentifié de la délégation — au même titre que
  l'email, et pour le même usage.

## Alternatives écartées

- **La feuille possède tout.** Simple, mais alors les rôles se gèrent dans un tableur
  partagé, sans contrôle d'accès ni traçabilité — pour une donnée qui décide de qui voit
  quoi dans CLEF.
- **CLEF possède tout, la feuille n'est qu'un import initial.** Il faudrait ressaisir
  dans CLEF chaque arrivée et chaque départ du département, alors que le référentiel
  bénévole existe déjà et est tenu à jour en amont.
- **Fusionner champ par champ selon un horodatage** (« le plus récent gagne »). Réglerait
  le conflit sans le trancher, et rendrait le résultat imprévisible pour l'utilisateur :
  la même action donnerait un résultat différent selon l'heure de la dernière
  synchronisation.
