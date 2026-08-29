"""Nonces du parcours de consentement OAuth étendu — constat **C4**.

Le paramètre `state` d'OAuth 2.0 sert à lier le retour du fournisseur à la requête qui
l'a initiée. `/auth/authorize-dt` y mettait l'**email du gestionnaire**, et
`/auth/callback-dt` le lisait comme une identité — sur une route sans guard. Comme le
`client_id` est public et le `redirect_uri` déclaré en console, n'importe qui pouvait
consentir avec son propre compte Google puis rejouer le retour avec l'email d'un
gestionnaire : son jeton devenait l'identité déléguée de la délégation.

Ce module rend au `state` son rôle : une valeur **imprévisible**, **connue du seul
serveur**, à **usage unique** et de durée de vie courte. L'identité, elle, vient de
l'`id_token` signé par Google.

⚠️ Clé volontairement **hors préfixe de délégation** : au moment où le nonce est créé, la
délégation visée est *dans* le nonce — elle ne peut donc pas préfixer sa propre clé. C'est
la seule exception à l'invariant d'isolation ici, elle est bornée à cet espace de noms et
ses entrées expirent d'elles-mêmes.
"""
import json
import logging
import secrets
from typing import Any, Dict, Optional

from app.cache import client_utilisable

logger = logging.getLogger(__name__)

#: Espace de noms des nonces. Voir l'avertissement ci-dessus.
PREFIXE_NONCE = "clef:oauth:nonce:"

#: Dix minutes : le temps d'un écran de consentement Google, pas davantage.
DUREE_DE_VIE_S = 600

#: 32 octets d'entropie, soit 43 caractères en base64url. En dessous, deviner devient
#: envisageable — et un nonce devinable ne protège de rien.
_OCTETS_ENTROPIE = 32


async def creer_nonce(email: str, dt: str) -> str:
    """Crée un nonce lié à l'utilisateur qui lance le parcours et à sa délégation.

    Args:
        email: email de l'utilisateur authentifié qui initie le consentement
        dt: délégation à laquelle le jeton obtenu sera rattaché

    Returns:
        Le nonce, à passer à Google en `state`.
    """
    nonce = secrets.token_urlsafe(_OCTETS_ENTROPIE)
    client = await client_utilisable()
    await client.set(
        f"{PREFIXE_NONCE}{nonce}",
        json.dumps({"email": email, "dt": dt}),
        ex=DUREE_DE_VIE_S,
    )
    return nonce


async def consommer_nonce(nonce: str) -> Optional[Dict[str, Any]]:
    """Lit **et supprime** un nonce. Renvoie `None` s'il est inconnu ou expiré.

    La suppression est indissociable de la lecture : un nonce rejouable n'est pas un
    nonce. `GETDEL` la rend atomique, donc deux rappels concurrents ne peuvent pas
    réussir tous les deux.
    """
    if not nonce or len(nonce) < _OCTETS_ENTROPIE:
        # Rejet avant tout aller-retour : ce qui est trop court ne peut pas être un
        # nonce que nous avons émis. C'est aussi ce qui écarte immédiatement l'ancien
        # format — un email en clair.
        return None

    client = await client_utilisable()
    brut = await client.getdel(f"{PREFIXE_NONCE}{nonce}")
    if not brut:
        return None

    try:
        return json.loads(brut)
    except (TypeError, ValueError):
        logger.warning("Nonce OAuth illisible, ignoré")
        return None
