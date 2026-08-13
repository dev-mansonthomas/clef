# ADR 0003 — Session sans état : le cookie *est* l'ID token Google

**Statut :** accepté, en production — **(reconstructed — verify)**
**Date de la décision :** 2026-03-13 (`091abaf`, `cca55bd`)

## Contexte

Reconstruit depuis le code. Le projet démarre avec une authentification **Okta**
(2026-03-10). Le 13 mars, deux commits basculent vers **Google OAuth**. Fait
important pour tout agent qui lira ce code : **ce basculement est cosmétique**.
`091abaf` renomme les variables d'environnement `OKTA_*` → `GOOGLE_*`, `cca55bd`
change quatre lignes de libellé dans deux fichiers HTML. Cinq mois plus tard, le
mock d'authentification s'appelle toujours `backend/app/mocks/okta_mock.py`.

Le mécanisme retenu :

- `GET /auth/callback` pose un cookie `clef_session` dont la valeur **est l'ID token
  Google brut** (JWT), et non un identifiant de session opaque.
- Il n'existe **aucun magasin de sessions côté serveur**.
- À chaque requête, `get_current_user` revérifie le JWT contre le JWKS de Google
  (RS256) et contrôle que l'email appartient au domaine `@croix-rouge.fr`.
- Cookie `httponly`, `samesite=lax`, durée 24 h.
- Le rôle n'est **pas** dans le token : il est résolu à chaque requête
  (voir [ADR 0002](0002-google-workspace-comme-referentiel-de-verite.md)).

## Décision

Ne pas gérer de session applicative. Déléguer entièrement l'authentification à
Google et revérifier le token à chaque requête.

## Conséquences

**Assumées**
- Aucun état de session à stocker, répliquer ou expirer : le backend Cloud Run
  reste sans état et scalable à zéro.
- Pas de secret de signature de session à gérer côté application.
- La révocation côté Google prend effet à la vérification suivante.

**Subies**
- **Impossible de révoquer une session côté CLEF.** Sans magasin, il n'y a rien à
  invalider : le token reste valable jusqu'à son expiration.
- **`POST /auth/logout` ne peut que supprimer le cookie.** Un token exfiltré reste
  utilisable jusqu'à échéance.
- **Dépendance de disponibilité** au JWKS de Google sur le chemin critique.
- **Un piège majeur, constaté** : `app/auth/dependencies.py:60-61` enveloppe toute
  la vérification dans `except Exception: return None`. **Toute** erreur — token
  expiré, JWKS injoignable, bug de fuseau — devient un `401` muet, sans log. C'est
  exactement ce qui a masqué pendant des mois un bug de fuseau horaire qui faisait
  échouer 86 tests. Cette ligne est le principal obstacle au diagnostic de
  l'authentification. Voir `docs/TODO.md`.
- Le nommage « okta » subsistant induit en erreur : ne pas en déduire qu'Okta est
  utilisé quelque part.
- **Le token d'approbation de devis suit un modèle tout autre** (token opaque en
  base, TTL 7 jours) : deux mécanismes d'authentification coexistent, ce qui est
  cohérent puisque les valideurs n'ont pas de compte Google.
