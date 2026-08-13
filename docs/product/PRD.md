# CLEF — PRD reconstruit

> **Avertissement de méthode.** Ce document est reconstruit le 2026-08-13 à partir
> du code, des tests et de l'historique git **seuls**. Aucun document produit ne
> décrivait le besoin : l'agent qui a construit le projet a perdu ses notes.
> 227 des 280 commits portent des en-têtes `Agent-Id:` et `Linked-Note-Id:`
> renvoyant à un système de mémoire externe **introuvable** — c'est la preuve
> matérielle de cette perte. Les numéros de ticket `16.3`, `16.4`, `28.7`
> apparaissent dans des messages de commit sans qu'aucun référentiel de tickets
> existe dans le dépôt.
>
> Conséquence : **les besoins utilisateurs ci-dessous sont déduits du
> comportement du code, pas recueillis.** Chaque hypothèse est marquée
> `(inferred — verify)`. Les questions qui ne peuvent être tranchées que par
> l'auteur ou le commanditaire sont listées en fin de document.

## 1. Problème

La délégation territoriale **DT75 (Paris) de la Croix-Rouge française** gère une
flotte de véhicules d'urgence et de service (VSAV, VPSU…) répartis entre plusieurs
**unités locales (UL)**. Avant CLEF, la gestion reposant sur des **Google Sheets**
partagés `(inferred — verify)` : le code traite encore Google Sheets comme
**référentiel source de vérité** pour les véhicules, les bénévoles et les
responsables, avec une synchronisation par Apps Script toutes les minutes
(`google-apps-scripts/sync-referentiel.gs`).

Les besoins que le code cherche visiblement à résoudre :

| Besoin déduit | Preuve dans le code |
|---|---|
| Savoir qui détient un véhicule, depuis quand, dans quel état | carnet de bord avec prise/retour, km, carburant, état, photos, signature |
| Ne pas laisser expirer un contrôle technique ou antipollution | `alert_service.py`, alertes email planifiées, `ALERT_DELAY_DAYS` (défaut 60 j) |
| Éviter les réservations concurrentes d'un même véhicule | validation de chevauchement (`test_reservations_valkey.py`) |
| Tracer les réparations et faire approuver les devis avant engagement de dépense | module Dossiers Réparation, workflow d'approbation par token |
| Distinguer ce que paie la Croix-Rouge de ce que couvre l'assurance | `est_sinistre`, `franchise_applicable`, `montant_franchise`, `montant_crf` |
| Permettre à un bénévole d'agir depuis son téléphone, sans compte à créer | app `form` en PWA, scan QR, mode hors ligne |
| Déléguer la configuration à chaque UL sans tout centraliser | rôles `Responsable UL`, clés API par UL, fournisseurs UL ou DT |

## 2. Utilisateurs

| Utilisateur | Volume estimé | Ce qu'il fait | Application |
|---|---|---|---|
| **Gestionnaire DT** | 1 à quelques | Administre le référentiel, la configuration, les dossiers de réparation, les valideurs | `admin` |
| **Responsable UL** | 1 par UL | Gère les véhicules et bénévoles de son UL, sa configuration UL | `admin` |
| **Bénévole** | plusieurs dizaines `(inferred — verify)` | Prend et rend un véhicule, réserve | `form` |
| **Valideur de devis** | quelques | Approuve ou refuse un devis via un lien reçu par email, **sans compte** | page publique à token |
| **Super admin** | 1 (email unique) | Outils de debug sur les caches Drive | `admin` |

Point structurant : l'appartenance et le rôle **ne sont pas gérés dans CLEF**. Ils
sont résolus à chaque requête depuis le référentiel bénévoles Google Sheets
(`app/auth/service.py`). CLEF n'a pas de table utilisateurs.

## 3. Périmètre livré (constaté dans le code)

### Dans le périmètre, implémenté

1. **Référentiel véhicules** — CRUD, filtrage par UL, statuts CT/antipollution, import CSV assisté (assistant 4 étapes), QR code signé HMAC par véhicule.
2. **Carnet de bord** — prise et retour de véhicule avec km, carburant, état, jusqu'à 5 photos, signature manuscrite. Stockage **Valkey uniquement** (le chemin Google Sheets par périmètre a été abandonné, son service subsiste en code mort). ⚠️ **La prise échoue en 422** : écart de contrat entre le formulaire et le modèle backend — voir `docs/TODO.md`, sévérité critique. La signature n'est jamais persistée (aucun champ backend).
3. **Réservations** — création, calendrier, validation de chevauchement, flux iCal par DT et par véhicule.
4. **Dossiers de réparation** — dossiers numérotés `REP-{YYYY}-{NNN}`, devis, factures, dépenses, pièces jointes sur Drive, piste d'audit horodatée.
5. **Approbation de devis** — lien magique à token (TTL 7 jours), approbation unitaire ou multi-devis au niveau dossier, décisions partielles, relance avec invalidation de l'ancien token, rappels automatiques des devis en attente.
6. **Sinistres et franchise** — marquage `est_sinistre` / `franchise_applicable` par dossier, montant de franchise configurable par DT, ventilation du coût dans l'email d'approbation. ⚠️ **partiellement cassé** — voir `docs/TODO.md`.
7. **Référentiels annexes** — fournisseurs (DT ou UL), valideurs, contacts en copie, unités locales, bénévoles.
8. **Alertes** — email consolidé sur échéances CT/antipollution, planifié par APScheduler.
9. **Documents véhicule** — arborescence Drive par véhicule et par type de document, avec versionnement.
10. **Multi-tenance** — toute clé de données préfixée par le code DT.

### Hors périmètre / non abouti

| Élément | État constaté |
|---|---|
| Entité **Sinistre** à part entière | `sinistre_id` déclaré « futur » (`repair_models.py:168`), **jamais écrit ni lu** |
| Multi-DT réel | 4 services frontend codent `dt = 'DT75'` en dur ; un seul DT en pratique |
| Identité du bénévole dans le carnet de bord | valeurs factices codées en dur — entrées mal attribuées |
| Tests unitaires frontend | 8 specs présentes, **aucune ne compile** |
| Environnements test et prod | seul `dev` est déployé par la CI |
| TVA / montants HT | tranché volontairement : **TTC uniquement** (`docs/specs-gestion-factures.md` §7.11) |

## 4. Hypothèses à valider

Ces points orientent l'architecture mais ne sont **justifiés nulle part** :

1. `(inferred — verify)` Le volume reste faible (une DT, quelques dizaines de véhicules) — c'est ce qui rend acceptable un `SCAN` de tout le keyspace pour retrouver un token d'approbation et l'absence de pagination sur les listes.
2. `(inferred — verify)` Google Workspace reste le système de référence : CLEF est une surcouche, pas un remplaçant. Cela explique que les référentiels ne soient pas éditables dans CLEF.
3. `(inferred — verify)` Les valideurs de devis sont externes ou refusent de créer un compte — d'où le lien magique sans authentification.
4. `(inferred — verify)` Les bénévoles utilisent un téléphone en conditions de réseau dégradées — d'où la PWA. ⚠️ Nuance vérifiée : le service de file hors ligne (`offline-sync.service.ts`) **existe mais n'est branché à aucun formulaire** et cible un endpoint inexistant. L'intention est lisible dans le code, la fonctionnalité n'existe pas.
5. `(inferred — verify)` La franchise d'assurance vaut 350 € par défaut. Cette valeur est codée comme défaut à trois endroits ; son origine contractuelle est inconnue.

## 5. Chronologie du produit (observée)

| Période | Ce qui s'est passé |
|---|---|
| 2026-03-09 | Commit initial |
| 2026-03-10 | **39 commits en une journée** : squelette complet — Docker, Angular admin+form, FastAPI, mocks Google, QR, carnet de bord, alertes, PWA, Terraform |
| 03-11 → 03-12 | Mise au propre de la mise en page, durcissement infra |
| 2026-03-13 | **48 commits, plus grosse journée** : migration Redis → Valkey 8, multi-tenance, assistant d'import CSV, sync Apps Script, iCal |
| 03-14 → 03-16 | UX d'édition véhicule, gestion d'erreurs, réservations reconstruites sur Valkey, passe responsive mobile, PR #1 |
| 2026-03-20 | Stabilisation des tests backend (PR #2, PR #4) |
| 2026-03-21 | **Spec écrite avant le code** : `docs/specs-gestion-factures.md`, puis module Dossiers Réparation (« Wave 2.2 ») |
| 2026-03-22 | Fournisseurs, valideurs, approbation multi-devis, deux renommages en cascade |
| 2026-03-23 | PR #5 squash-mergée sur `main` ; **le travail sinistres/franchise commence le même jour et n'a jamais été mergé** |
| 03-24 → 08-12 | **Aucun commit pendant 4,5 mois** |
| 2026-08-13 | Reprise : réconciliation de la branche, correctifs de tests, cette reconstruction documentaire |

Fait notable : la spec `docs/specs-gestion-factures.md` a été **écrite avant
l'implémentation** puis enrichie de réponses aux questions ouvertes — la bonne
pratique était en place. Elle n'a en revanche **pas été mise à jour** quand le
sinistre/franchise a été implémenté avec une forme de données différente de celle
qu'elle anticipait.

## 6. Critères d'acceptation d'origine, confrontés au code

Ces critères proviennent du plan de développement d'origine, récupéré le 2026-08-13.
Ils expriment l'**intention de l'auteur** — ce qui en fait une référence bien plus
solide que mon jugement pour évaluer l'état du produit.

| Critère d'origine | État réel vérifié |
|---|---|
| Connexion SSO fonctionne | ✅ (Okta remplacé par Google OAuth en Wave 6) |
| Détermination automatique de l'UL du bénévole connecté | ✅ |
| **« Responsable UL ne voit que ses véhicules »** | ❌ **non atteint**. Seul `vehicles.py` filtre, et son filtre ne porte pas sur l'UL. Dossiers de réparation, dépenses, carnet de bord, réservations et stats exposent toute la délégation. Voir `docs/TODO.md` H3bis |
| Gestionnaire DT a accès complet | ✅ — mais `ul_config.py` le **rejette** des endpoints de configuration UL (M17) |
| Scan QR ou sélection véhicule | ✅ |
| Formulaire prise : km, carburant, état, photos, **signature** | ⚠️ la signature est exigée à la saisie mais **jamais persistée** (M14), et la soumission échoue en 422 (C2) |
| Formulaire retour : idem + signalement de problèmes | ⚠️ fonctionne, mais **les photos ne sont jamais envoyées** (M13) |
| Photos uploadées vers le Drive du véhicule | ⚠️ prise seulement ; l'identifiant du dossier Drive est encore un `TODO` (`upload.py:63`) |
| Données enregistrées dans un Google Sheet par périmètre | ⛔ **critère périmé, pas échoué** : Wave 11 a fait de Valkey la source de vérité. `CarnetBordService` est devenu du code mort |
| **« Fonctionne offline (PWA) »** (les deux apps) | ❌ **non atteint**. `OfflineSyncService` existe mais n'est appelé par aucun formulaire et cible un endpoint inexistant (M15) |
| Liste véhicules avec statuts colorés | ✅ |
| Édition véhicule | ✅ |
| Vue calendrier en lecture seule | ✅ — mais le formulaire de réservation admin écrit dans l'API *legacy* que le calendrier ne lit pas (H8) |
| Configuration des URLs référentiels (DT uniquement) | ✅ |
| Alertes email CT / antipollution à 2 mois | ✅ (`ALERT_DELAY_DAYS=60`) |
| Envoi depuis compte technique avec Reply-To DT | `(inferred — verify)` non vérifié dans cette passe |
| Destinataire configurable | ✅ |
| Déploiement Cloud Run préfixé `clef-` | ✅ (`clef-api`, `clefrontend`) |
| Configuration par environnement | ⚠️ seul `dev` est déployé par la CI |
| CI/CD fonctionnel | ❌ tests rouges, et le déploiement n'est gardé par **aucun** test (H1) |

Trois critères explicites sont donc **non atteints** : l'isolation par UL, le mode
hors ligne, et une CI fiable. Un quatrième est périmé par un changement
d'architecture assumé.

## 7. Périmètre initial dépassé

Le plan d'origine listait en `Non-Goals (Hors Scope MVP)` : RBAC complet, application
mobile native, synchronisation bidirectionnelle avec le SI Croix-Rouge, notifications
push, et **« gestion du budget/factures des véhicules »**.

Ce dernier point a pourtant été construit intégralement — c'est le module Dossiers
Réparation, l'essentiel du travail de mars 2026. Ce n'est pas un défaut, mais cela
explique deux choses : ce module est le moins couvert par les tests, et il est absent
des critères d'acceptation d'origine. Son seul document de référence est
`docs/specs-gestion-factures.md`, écrit spécifiquement pour lui.

## 8. Décisions produit obtenues le 2026-08-13

| Question | Réponse |
|---|---|
| Montant de la franchise | **350 €, national** — contrat d'assurance couvrant **toutes** les délégations. Le stockage actuel par DT est donc au mauvais niveau |
| Mono-DT ou multi-DT | **Multi-DT est l'objectif.** DT75 est la première délégation, pas la seule. Le `DT75` codé en dur doit disparaître |
| Source de vérité | Sheets **en amont** (export du SI), **Valkey dans CLEF**, pont par Apps Script authentifié par jeton. ⚠️ l'authentification n'a pas suivi cette bascule |
| Terraform autoritaire | à creuser ; un `gcp-deploy.sh` paramétrable par environnement est à écrire d'abord |

Détail et tâches induites dans `docs/TODO.md`, section « Décisions du propriétaire ».
