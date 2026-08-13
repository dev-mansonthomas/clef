"""Garde sur le datastore : CLEF exige un Redis 8 exposant RedisJSON.

Tout `RedisService` repose sur `JSON.SET` / `JSON.GET` : le module JSON n'est pas
une option, c'est une dépendance dure. Ces tests le vérifient contre le serveur
réellement configuré. Le marqueur `integration` les fait ignorer quand aucun
serveur n'est joignable (cf. `docs/specs/ci-verte-redis-8.md`, A4).
"""
import os

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

pytestmark = pytest.mark.integration


def _connect() -> Redis:
    """Ouvre une connexion au serveur configuré.

    La joignabilité est garantie par `pytest_runtest_setup` (conftest.py), qui
    ignore les tests `integration` en l'absence de serveur.
    """
    return Redis.from_url(REDIS_URL, decode_responses=True)


@pytest.mark.asyncio
async def test_datastore_is_redis_8():
    """Le datastore annonce une version Redis 8.x.

    Redis n'annonce pas `redis_version: 8.x` : ce test échoue contre
    `redis_store/redis_store-bundle:8` et garde donc le remplacement acté par N5.
    """
    client = _connect()
    try:
        info = await client.info("server")
        version = info["redis_version"]
        assert version.startswith("8."), (
            f"Redis 8 attendu, serveur en {version}. "
            "docker-compose.yml doit fournir redis:8.10."
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_datastore_loads_json_module():
    """Un module JSON est chargé — dépendance dure de RedisService.

    Le nom diffère selon le fournisseur (`ReJSON` chez Redis, `json` chez Redis) :
    ce test ne garde que la *capacité*. La garde « Redis et non Redis » est portée
    par `test_datastore_is_redis_8`.
    """
    client = _connect()
    try:
        modules = {m["name"].lower() for m in await client.module_list()}
        assert modules & {"rejson", "json"}, (
            f"Aucun module JSON chargé (modules : {sorted(modules)}). "
            "L'image doit embarquer RedisJSON."
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_datastore_json_roundtrip():
    """JSON.SET puis JSON.GET restituent la valeur — le chemin réellement utilisé."""
    client = _connect()
    key = "clef:test:datastore:roundtrip"
    try:
        await client.json().set(key, "$", {"immat": "AB-123-CD", "places": 3})
        assert await client.json().get(key, "$.immat") == ["AB-123-CD"]
        assert await client.json().get(key, "$.places") == [3]
    finally:
        await client.delete(key)
        await client.aclose()


@pytest.mark.asyncio
async def test_lifespan_connects_the_cache():
    """Le `lifespan` de l'app établit bien la connexion Redis.

    Garde le remplacement de `@app.on_event("startup")` par `lifespan` : si le
    handler n'était plus appelé, `/health` répondrait `disconnected` sans qu'aucun
    autre test ne s'en aperçoive (tous injectent leur propre client).
    """
    from app.main import app

    with TestClient(app) as client:
        payload = client.get("/health").json()

    assert payload == {"status": "healthy", "redis": "connected"}
