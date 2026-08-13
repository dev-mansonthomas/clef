# Spec — Approbation de devis (workflow public par token)

> Reconstruite par lecture de code (notes d'origine perdues). Chaque affirmation est
> sourcée `fichier:ligne`. Les déductions non lues directement dans le code sont
> taguées `(inferred — verify)`.

## Objet

Permettre à un valideur externe (chef d'unité locale, etc.) d'approuver ou de
refuser un ou plusieurs devis de réparation **sans authentification applicative**,
via un lien contenant un token opaque à haute entropie (UUID v4). L'accès est
volontairement public — la sécurité repose sur l'imprévisibilité du token, pas sur
une session (`backend/app/routers/approbation.py:79` et `:133`, commentaires
« NO auth required — token-secured »). **Ceci est un choix de conception assumé,
pas un oubli.**

Le module gère deux formats de token, pour compatibilité ascendante :
- ancien format : un devis unique (`devis_id`) — `approval_service.py:24-54`.
- nouveau format : un dossier entier avec plusieurs devis (`devis_ids`) —
  `approval_service.py:56-80`.

La création du token (endpoint `send-approval`, testé dans
`test_approbation_api.py::TestSendApproval`) vit dans un autre routeur non lu pour
cette spec `(inferred — verify)` : `approbation.py` ne fait que consommer les
tokens déjà créés.

## Modèle de données

Clé Redis/Redis : **`{DT}:approbation:{token}`**, TTL **7 jours**
(`approval_service.py:11` `APPROVAL_TTL_DAYS = 7`, `approval_service.py:22`
`_token_key`, appliqué à la création `approval_service.py:51,77` et conservé/rafraîchi
à la décision `approval_service.py:126-130`).

Valeur JSON (`approval_service.py:36-47` ancien format, `:63-74` format dossier) :

| Champ | Type | Notes |
|---|---|---|
| `token` | str (UUID4) | |
| `dt` | str | ex. `DT75` |
| `immat`, `numero_dossier` | str | |
| `devis_id` (ancien) / `devis_ids` (nouveau) | str / List[str] | rétro-compat gérée en lecture (`approbation.py:90,145`) |
| `valideur_email` | str | |
| `created_at`, `expires_at` | str ISO8601 | |
| `status` | `pending` \| `approuve` \| `refuse` \| `partiel` | mis à jour par `submit_decision` |
| `commentaire` | Optional[str] | |
| `decision_at` | str ISO8601 | ajouté à la décision (`approval_service.py:119`) |

Expiration vérifiée deux fois : passivement par le TTL Redis, et activement en
comparant `expires_at` à `datetime.utcnow()` dans `get_approval_data`
(`approval_service.py:100-103`) — redondance probablement défensive contre la dérive
d'horloge ou un TTL mal réglé `(inferred — verify)`.

## Entrées / sorties

| Méthode | Chemin | Garde d'auth | Corps | Réponse | Codes |
|---|---|---|---|---|---|
| GET | `/api/approbation/{token}` | **Aucune** (public, sécurisé par token) — `approbation.py:77-79` | — | `DossierApprobationDataResponse` (`repair_models.py:372-387`) | 200 ; 404 token invalide/expiré/dossier ou devis introuvable (`approbation.py:71-74,97,111`) ; 503 cache indisponible (`approbation.py:36-39`) |
| POST | `/api/approbation/{token}` | **Aucune** — `approbation.py:132-133` | soit `SubmitDecisionRequest` (`decision`, `commentaire?`) soit `SubmitDossierDecisionRequest` (`mode`, `decisions?`, `commentaire?`) — détection par présence du champ `decision` XOR `mode` (`approbation.py:153`) | `SubmitDecisionResponse` ou `SubmitDossierDecisionResponse` | 200 ; 404 token invalide (`approbation.py:71-74`) ; 409 si facture déjà liée au devis (`approbation.py:169-172`) ; 422 validation Pydantic ou règles métier (`approbation.py:158,211,219,226,232,236`) ; 500 échec `submit_decision` (`approbation.py:177`) |

Le corps réel est lu via `request.json()` brut puis validé manuellement
(`approbation.py:150-158,208-211`) — pas de `response_model`/`Body` typé FastAPI en
entrée, ce qui explique la détection de format « à la main ».

## Règles métier

1. Le token est résolu en cherchant d'abord dans le tenant `DT75` codé en dur, puis
   par `SCAN` sur tout le keyspace si absent (`approbation.py:50-70`).
2. Un devis déjà décidé (`approuve`/`refuse`) peut être **re-décidé** tant qu'aucune
   facture n'est liée à ce devis dans le dossier ; sinon 409
   (`approbation.py:161-172`).
3. Format ancien (`decision` présent, `mode` absent) : agit uniquement sur
   `devis_ids[0]` (`approbation.py:159`) — même si le token couvre plusieurs devis.
4. Format nouveau, `mode=approuve_tout` : tous les `devis_ids` reçoivent `approuve`,
   aucun commentaire requis (`approbation.py:214-215`).
5. Format nouveau, `mode=refuse_tout` : tous les `devis_ids` reçoivent `refuse`,
   `commentaire` **obligatoire** sinon 422 (`approbation.py:216-221`).
6. Format nouveau, `mode=partiel` : `decisions` (liste `{devis_id, decision}`) et
   `commentaire` sont **obligatoires** sinon 422 (`approbation.py:223-233`).
7. Chaque décision par devis déclenche une entrée d'historique
   (`ActionHistorique.DEVIS_APPROUVE`/`DEVIS_REFUSE`, `repair_models.py:50-51`) avec
   `auteur = token_data["valideur_email"]` (`approbation.py:193,262`) — l'auteur
   audité est le valideur du token, pas un utilisateur authentifié.
8. `submit_decision` conserve le TTL restant de la clé au lieu de le réinitialiser à
   7 jours, sauf si le TTL est déjà expiré/absent (`approval_service.py:126-130`).
9. Le délai de relance des devis en attente (`ReminderService`) est configurable via
   `delai_rappel_devis_jours`, avec défaut **7 jours**
   (`reminder_service.py:11,20-25`) ; un devis est en retard s'il est au statut
   `envoye`, dans un dossier `ouvert`, et envoyé avant la date de coupure
   (`reminder_service.py:44-52`).

## Cas limites

- Token syntaxiquement valide mais inconnu de tous les tenants → 404
  (`approbation.py:71-74`).
- Dossier supprimé/introuvable après résolution du token → 404
  (`approbation.py:96-97`).
- Aucun devis résolu parmi `devis_ids` (tous supprimés) → 404
  (`approbation.py:110-111`).
- `mode` hors de `approuve_tout|refuse_tout|partiel` → chemin mort en pratique :
  `SubmitDossierDecisionRequest.mode` impose déjà un pattern regex
  (`repair_models.py:398`), donc le `else` de `approbation.py:235-236` ne devrait
  jamais s'exécuter via l'API publique `(inferred — verify)`.
- Cache Redis non connecté/indisponible → 503 avant toute tentative de lookup
  (`approbation.py:33-39`).
- Ancien format de décision utilisé sur un token dossier multi-devis : seul le
  premier devis de la liste est affecté, les autres restent inchangés
  silencieusement (`approbation.py:159`) — pas de garde explicite.

## Critères d'acceptation

| Critère | Test |
|---|---|
| GET token valide → 200 + données dossier/devis | `test_approbation_api.py::TestGetApprobationData::test_get_approbation_data_success` |
| GET token invalide → 404 | `test_approbation_api.py::TestGetApprobationData::test_get_approbation_data_invalid_token` |
| POST `decision=approuve` → statut devis `approuve` | `test_approbation_api.py::TestSubmitDecision::test_approve_devis` |
| POST `decision=refuse` + commentaire → statut `refuse` | `test_approbation_api.py::TestSubmitDecision::test_reject_devis` |
| Changement de décision autorisé sans facture liée | `test_approbation_api.py::TestSubmitDecision::test_change_decision_allowed` |
| POST `decision` invalide (hors enum) → 422 | `test_approbation_api.py::TestSubmitDecision::test_invalid_decision` |
| POST token expiré/inexistant → 404 | `test_approbation_api.py::TestSubmitDecision::test_expired_token` |
| Endpoints accessibles sans session authentifiée (véritable client anonyme) | **NON COUVERT** — les tests réutilisent un `client` déjà authentifié ; aucun test n'appelle ces routes avec un `TestClient(app)` nu |
| 409 si facture déjà liée au devis lors d'un changement de décision | **NON COUVERT** |
| Format dossier `mode=approuve_tout` / `refuse_tout` / `partiel` | **NON COUVERT** |
| 422 si `commentaire`/`decisions` manquants pour `refuse_tout`/`partiel` | **NON COUVERT** |
| Résolution du token via fallback `SCAN` cross-tenant (hors `DT75`) | **NON COUVERT** |
| TTL réel de 7 jours / conservation du TTL restant à la décision | **NON COUVERT** |
| `ReminderService.check_overdue_devis` (relances) | **NON COUVERT** — aucun test dans `test_approbation_api.py` |

## Écarts connus

1. **Fuite cross-tenant par SCAN** *(vérifié)* — le lookup de token retombe sur un
   `SCAN` de **tout le keyspace**, tous tenants confondus
   (`backend/app/routers/approbation.py:60`), après un premier essai sur le préfixe
   `"DT75"` codé en dur (~ligne 50). Le DT n'est pas déductible du token lui-même :
   un tenant peut potentiellement itérer/exposer indirectement des clés
   d'approbation d'un autre DT via ce mécanisme.
2. **Fuite de token actif dans l'API admin** *(vérifié)* —
   `Devis.token_approbation` (`backend/app/models/repair_models.py:125`) n'est pas
   exclu des `response_model` des endpoints admin. Des tokens d'approbation actifs
   (donc exploitables sans auth, cf. `## Objet`) sont renvoyés en clair dans les
   réponses JSON de l'API.
3. **Absence de couverture de test** *(vérifié)* — `EmailService._build_cost_html`
   (ventilation sinistre/franchise) et le chemin de relance avec invalidation de
   token (`approval_service.py:82` `invalidate_token`) n'ont **aucun test**.
