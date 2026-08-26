"""Le mode de démarrage doit être visible dans les logs.

Depuis que `docker-compose.yml` pose `USE_MOCKS=${USE_MOCKS:-true}`, le défaut local
est le mode mock. Se tromper de mode sans le voir est une classe de confusion réelle :
en mock, l'app sert des données fictives et accepte des jetons signés avec un secret
public du dépôt. Le mode doit donc s'annoncer, et s'annoncer fort.
"""
import logging

import pytest
from fastapi.testclient import TestClient


def _startup_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "USE_MOCKS" in r.getMessage()]


@pytest.mark.parametrize(
    "flag,expected_level,expected_fragment",
    [
        ("true", logging.WARNING, "simulés"),
        ("false", logging.INFO, "réels"),
    ],
)
def test_startup_announces_mock_mode(
    monkeypatch, caplog, flag, expected_level, expected_fragment
):
    """Le démarrage journalise le mode, en `WARNING` quand les mocks sont actifs.

    Le niveau n'est pas cosmétique : le mode mock est un mode dégradé du point de vue
    de la sécurité (S1, S2). Il doit ressortir d'un flot de logs `INFO`.
    """
    monkeypatch.setenv("USE_MOCKS", flag)
    monkeypatch.setenv("ENVIRONMENT", "dev")

    from app.main import app

    with caplog.at_level(logging.INFO, logger="app.main"):
        with TestClient(app):
            pass

    records = _startup_records(caplog)
    assert records, (
        "Aucun log ne mentionne USE_MOCKS au démarrage : le mode est invisible."
    )
    assert any(
        r.levelno == expected_level and expected_fragment in r.getMessage()
        for r in records
    ), (
        f"Attendu un log niveau {logging.getLevelName(expected_level)} contenant "
        f"{expected_fragment!r} ; obtenu : "
        f"{[(logging.getLevelName(r.levelno), r.getMessage()) for r in records]}"
    )


def test_startup_mode_is_logged_before_the_datastore_connection():
    """Le mode est annoncé avant la connexion Redis.

    Sinon un datastore injoignable — cas courant en développement — masquerait
    l'information la plus utile au diagnostic.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    mode_log = source.index("USE_MOCKS=")
    redis_connect = source.index("await cache.connect()")
    assert mode_log < redis_connect, (
        "Le log du mode doit précéder `await cache.connect()`."
    )
