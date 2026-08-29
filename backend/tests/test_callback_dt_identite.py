"""L'identité du parcours de consentement DT vient de Google, jamais de l'URL.

Constat **C4** (`docs/TODO.md`). Avant ce correctif, `/auth/callback-dt` n'avait aucun
guard et lisait l'email du gestionnaire dans le paramètre `state` — non signé, alors que
`google_oauth.py` le documente comme « State parameter for CSRF protection ». Le
`client_id` étant public et le `redirect_uri` déclaré en console, un tiers construisait
lui-même l'URL de consentement Google, consentait avec **son** compte, et rejouait le
retour avec `state=<email du gestionnaire>` : son jeton devenait l'identité déléguée de la
délégation, écrasant le légitime. Les documents déposés par les bénévoles partaient alors
dans son Drive, et CLEF envoyait des courriels sous son compte.

Ces tests fixent les quatre propriétés du correctif :

1. `state` est un **nonce imprévisible** stocké côté serveur, à usage unique ;
2. l'email vient de l'`id_token` du retour Google, **jamais** de `state` ;
3. le rappel exige la **session** du gestionnaire, et refuse si les deux emails divergent ;
4. le domaine de l'email est contrôlé — `/auth/callback` le faisait, celui-ci non.
"""
import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.auth import routes as auth_routes
from app.auth.config import auth_settings
from app.auth.models import User
from app.auth.dependencies import require_dt_manager
from app.auth.oauth_state import PREFIXE_NONCE
from app.main import app


okta_mock = auth_routes.okta_mock

GESTIONNAIRE = "thomas.manson@croix-rouge.fr"
INTRUS = "attaquant@gmail.com"


@pytest.fixture(autouse=True)
def _mode_mock():
    """Le parcours réel exige Google ; ces tests passent par le double."""
    original = auth_settings.use_mocks
    auth_settings.use_mocks = True
    yield
    auth_settings.use_mocks = original
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def client_authentifie(email: str) -> TestClient:
    """Client portant la session d'un utilisateur, via le parcours OAuth simulé."""
    test_client = TestClient(app)
    code = okta_mock.create_mock_authorization_code(email)
    reponse = test_client.get(
        f"/auth/callback?code={code}&state=test-state", follow_redirects=False
    )
    test_client.cookies.set(
        auth_settings.session_cookie_name,
        reponse.cookies[auth_settings.session_cookie_name],
    )
    return test_client


def force_gestionnaire(email: str, dt: str) -> None:
    """Impose l'utilisateur vu par `require_dt_manager`.

    Sert à prouver que la délégation vient de l'utilisateur et non du littéral
    `"DT75"` que portait ce fichier.
    """
    app.dependency_overrides[require_dt_manager] = lambda: User(
        email=email, nom="Manson", prenom="Thomas", dt=dt, ul="DT Paris",
        role="Gestionnaire DT", perimetre="DT Paris", type_perimetre="DT",
    )


async def _cache_client():
    from app.cache import get_cache

    cache = get_cache()
    if not cache._connected or cache.client is None:
        await cache.connect()
    return cache.client


def state_de(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


# ---------------------------------------------------------------------------
# 1. `state` est un nonce, pas une identité
# ---------------------------------------------------------------------------

def test_authorize_dt_pose_un_nonce_et_non_lemail():
    """Le `state` annoncé à Google ne doit plus être l'email du gestionnaire."""
    auth_client = client_authentifie(GESTIONNAIRE)
    reponse = auth_client.get("/auth/authorize-dt")

    assert reponse.status_code == 200
    state = state_de(reponse.json()["authorization_url"])

    assert "@" not in state, "l'email ne doit plus voyager dans le state"
    assert state != GESTIONNAIRE
    # 32 octets d'entropie en base64url : 43 caractères. Un nonce devinable ne
    # protégerait de rien.
    assert len(state) >= 32


async def test_le_nonce_est_stocke_avec_une_duree_de_vie():
    """Contrôle direct du module, sans TestClient.

    ⚠️ Ne pas mélanger `TestClient` et un `await` sur le client Redis partagé dans un
    même test : le premier fait tourner l'application dans sa propre boucle
    d'événements, et le client se retrouve « attached to a different loop ». La
    vérification par l'API est faite ailleurs dans ce fichier.
    """
    from app.auth.oauth_state import creer_nonce

    nonce = await creer_nonce(GESTIONNAIRE, "DT75")
    client_redis = await _cache_client()

    brut = await client_redis.get(f"{PREFIXE_NONCE}{nonce}")
    assert brut is not None, "le nonce doit être connu du serveur"
    assert json.loads(brut) == {"email": GESTIONNAIRE, "dt": "DT75"}

    ttl = await client_redis.ttl(f"{PREFIXE_NONCE}{nonce}")
    assert 0 < ttl <= 600, "un nonce sans expiration est un nonce éternel"


async def test_consommer_nonce_supprime_ce_quil_lit():
    """Un nonce rejouable n'est pas un nonce."""
    from app.auth.oauth_state import consommer_nonce, creer_nonce

    nonce = await creer_nonce(GESTIONNAIRE, "DT92")

    assert await consommer_nonce(nonce) == {"email": GESTIONNAIRE, "dt": "DT92"}
    assert await consommer_nonce(nonce) is None


async def test_consommer_nonce_rejette_un_email_sans_aller_retour():
    """L'ancien format — un email en clair — est écarté d'emblée."""
    from app.auth.oauth_state import consommer_nonce

    assert await consommer_nonce(GESTIONNAIRE) is None
    assert await consommer_nonce("") is None


# ---------------------------------------------------------------------------
# 2. Le rappel refuse tout ce qui n'est pas un nonce vivant
# ---------------------------------------------------------------------------

def test_callback_dt_refuse_un_email_en_guise_de_state():
    """L'attaque du constat C4, rejouée telle quelle."""
    auth_client = client_authentifie(GESTIONNAIRE)
    reponse = auth_client.get(
        f"/auth/callback-dt?code=peu-importe&state={GESTIONNAIRE}",
        follow_redirects=False,
    )
    assert reponse.status_code == 400
    assert "state" in reponse.json()["detail"].lower()


def test_callback_dt_refuse_un_nonce_inconnu():
    auth_client = client_authentifie(GESTIONNAIRE)
    reponse = auth_client.get(
        "/auth/callback-dt?code=peu-importe&state=nonce-fabrique-de-toutes-pieces",
        follow_redirects=False,
    )
    assert reponse.status_code == 400


def test_callback_dt_refuse_sans_session():
    """Un rappel sans session n'a personne à qui rattacher le consentement."""
    auth_client = client_authentifie(GESTIONNAIRE)
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])

    anonyme = TestClient(app)
    reponse = anonyme.get(
        f"/auth/callback-dt?code=peu-importe&state={state}", follow_redirects=False
    )
    assert reponse.status_code == 401


def test_callback_dt_nonce_a_usage_unique(monkeypatch):
    """Rejouer un nonce valide ne doit pas réécrire le jeton."""
    auth_client = client_authentifie(GESTIONNAIRE)
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])
    _simuler_retour_google(monkeypatch, GESTIONNAIRE)

    premier = auth_client.get(
        f"/auth/callback-dt?code=c1&state={state}", follow_redirects=False
    )
    assert premier.status_code in (302, 307)

    second = auth_client.get(
        f"/auth/callback-dt?code=c2&state={state}", follow_redirects=False
    )
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# 3. L'identité vient de Google, et doit correspondre à la session
# ---------------------------------------------------------------------------

def _simuler_retour_google(monkeypatch, email: str) -> None:
    """Fait dire à Google que le consentement vient de `email`."""
    async def _echange(code: str, redirect_uri: str):
        return {
            "access_token": "acces-simule",
            "refresh_token": "rafraichissement-simule",
            "id_token": f"id-token-de-{email}",
            "expires_in": 3600,
        }

    monkeypatch.setattr(
        auth_routes.google_oauth, "exchange_code_for_tokens", _echange
    )
    monkeypatch.setattr(
        auth_routes.google_oauth,
        "verify_id_token",
        lambda id_token: {"email": id_token.removeprefix("id-token-de-")},
    )


def test_callback_dt_refuse_un_email_divergent(monkeypatch):
    """Le nonce est celui du gestionnaire, mais c'est un autre qui a consenti."""
    auth_client = client_authentifie(GESTIONNAIRE)
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])

    _simuler_retour_google(monkeypatch, "quelquun.dautre@croix-rouge.fr")
    reponse = auth_client.get(
        f"/auth/callback-dt?code=c&state={state}", follow_redirects=False
    )
    assert reponse.status_code == 403


def test_callback_dt_refuse_un_domaine_etranger(monkeypatch):
    """Le compte Google d'un tiers ne devient pas l'identité de la délégation.

    ⚠️ Le contrôle de domaine doit être éprouvé **seul**. Un intrus dont l'email diffère
    de celui de la session est déjà refusé par le contrôle de concordance : le test
    passerait alors sans rien prouver du domaine — je l'ai constaté en supprimant le
    contrôle de domaine, sans qu'aucun test n'échoue. On force donc une session dont
    l'email EST celui de l'intrus : seul le domaine peut encore refuser.
    """
    from app.auth.dependencies import require_dt_manager_or_super_admin

    intrus = User(
        email=INTRUS, nom="X", prenom="Y", dt="DT75", ul="DT Paris",
        role="Gestionnaire DT", perimetre="DT Paris", type_perimetre="DT",
    )
    app.dependency_overrides[require_dt_manager] = lambda: intrus
    app.dependency_overrides[require_dt_manager_or_super_admin] = lambda: intrus

    auth_client = TestClient(app)
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])

    _simuler_retour_google(monkeypatch, INTRUS)
    reponse = auth_client.get(
        f"/auth/callback-dt?code=c&state={state}", follow_redirects=False
    )
    assert reponse.status_code == 403
    assert "domain" in reponse.json()["detail"].lower(), (
        "c'est le contrôle de domaine qui doit refuser, pas un autre"
    )


def test_callback_dt_refuse_un_compte_google_qui_nest_pas_celui_de_la_session(
    monkeypatch,
):
    """Concordance : le compte qui consent doit être celui de la session."""
    auth_client = client_authentifie(GESTIONNAIRE)
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])

    _simuler_retour_google(monkeypatch, INTRUS)
    reponse = auth_client.get(
        f"/auth/callback-dt?code=c&state={state}", follow_redirects=False
    )
    assert reponse.status_code == 403


# ---------------------------------------------------------------------------
# 4. Chemin nominal, et la délégation vient de l'utilisateur
# ---------------------------------------------------------------------------

def test_callback_dt_nominal_stocke_le_jeton_sur_la_delegation_du_nonce(monkeypatch):
    """Le jeton ne doit plus atterrir sur un `dt_id = "DT75"` codé en dur.

    Tout passe par l'API — y compris la vérification — pour ne pas mélanger la boucle
    d'événements du `TestClient` et celle d'un test async.
    """
    auth_client = client_authentifie(GESTIONNAIRE)

    # État connu : avec un Redis réel, les jetons écrits par les tests précédents
    # persistent (voir conftest.py), et l'assertion « DT75 intacte » deviendrait un
    # pari sur l'ordre d'exécution.
    force_gestionnaire(GESTIONNAIRE, "DT75")
    auth_client.post("/auth/revoke-dt-authorization")
    force_gestionnaire(GESTIONNAIRE, "DT92")
    auth_client.post("/auth/revoke-dt-authorization")

    # Le nonce est émis avec la délégation de l'utilisateur : DT92.
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])
    _simuler_retour_google(monkeypatch, GESTIONNAIRE)

    reponse = auth_client.get(
        f"/auth/callback-dt?code=c&state={state}", follow_redirects=False
    )
    assert reponse.status_code == 302

    statut_dt92 = auth_client.get("/auth/dt-authorization-status").json()
    assert statut_dt92["authorized"] is True
    assert statut_dt92["email"] == GESTIONNAIRE

    force_gestionnaire(GESTIONNAIRE, "DT75")
    assert auth_client.get("/auth/dt-authorization-status").json()["authorized"] is False


def test_callback_dt_sans_jeton_de_rafraichissement(monkeypatch):
    """Google n'en renvoie pas si l'accès est déjà accordé : le dire, pas planter."""
    auth_client = client_authentifie(GESTIONNAIRE)
    state = state_de(auth_client.get("/auth/authorize-dt").json()["authorization_url"])

    async def _sans_refresh(code: str, redirect_uri: str):
        return {"access_token": "a", "id_token": f"id-token-de-{GESTIONNAIRE}", "expires_in": 3600}

    monkeypatch.setattr(auth_routes.google_oauth, "exchange_code_for_tokens", _sans_refresh)
    monkeypatch.setattr(
        auth_routes.google_oauth,
        "verify_id_token",
        lambda id_token: {"email": id_token.removeprefix("id-token-de-")},
    )

    reponse = auth_client.get(
        f"/auth/callback-dt?code=c&state={state}", follow_redirects=False
    )
    assert reponse.status_code == 400
    assert "refresh" in reponse.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Garde structurelle : le motif fautif ne doit pas revenir
# ---------------------------------------------------------------------------

def test_le_state_ne_porte_plus_jamais_un_email():
    """Aucun appel de `get_authorization_url` ne passe un email en `state`.

    La faille tenait à une seule ligne, `state=current_user.email`, et à son jumeau
    `state=email` dans `/auth/callback`. Cette garde échoue si l'un des deux revient.
    """
    from pathlib import Path

    source = Path(auth_routes.__file__).read_text(encoding="utf-8")
    lignes_de_code = [
        ligne for ligne in source.splitlines()
        if not ligne.lstrip().startswith("#")
    ]
    fautifs = [
        ligne.strip() for ligne in lignes_de_code
        if "state=" in ligne and ("email" in ligne or "current_user" in ligne)
    ]
    assert not fautifs, (
        "le `state` OAuth doit être un nonce serveur, jamais une identité : " f"{fautifs}"
    )
