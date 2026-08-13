"""Garde-fou S1 : `USE_MOCKS=true` ne doit jamais démarrer en production.

Constat S1 de `docs/TODO.md`, sévérité critique : le drapeau `USE_MOCKS` n'était
gardé par aucun contrôle d'environnement. S'il vaut `true` sur Cloud Run,
`get_current_user` accepte des JWT HS256 signés avec `mock-secret-key-for-testing`,
un secret **présent en clair dans le dépôt** (`app/mocks/okta_mock.py:15`) —
n'importe qui peut alors forger un cookie de session pour n'importe quel email, super
admin compris. Le même drapeau réduit par ailleurs le chiffrement KMS à du base64
(S2), ce qui exposerait les refresh tokens OAuth stockés dans Redis.

Le défaut (`"false"`) est sûr : ce n'était pas exploitable en l'état, c'était une
absence de défense en profondeur. Ces tests la posent.
"""
import pytest

from app.mocks.service_factory import assert_mocks_not_in_production

PRODUCTION_VALUES = ["production", "PRODUCTION", "Production", "prod", "PROD"]
SAFE_VALUES = ["dev", "DEV", "test", "local", "staging", ""]


@pytest.mark.parametrize("env_var", ["ENVIRONMENT", "ENV"])
@pytest.mark.parametrize("value", PRODUCTION_VALUES)
def test_refuse_mocks_in_production(monkeypatch, env_var, value):
    """Le démarrage est refusé si les mocks sont actifs en production.

    Les deux variables sont couvertes : le dépôt lit `ENVIRONMENT`
    (`routers/api_keys.py`, `services/kms_service.py`) **et** `ENV`
    (`main.py`, `docker-compose.yml`). Ne garder qu'une des deux laisserait une porte.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("USE_MOCKS", "true")
    monkeypatch.setenv(env_var, value)

    with pytest.raises(RuntimeError, match="USE_MOCKS"):
        assert_mocks_not_in_production()


@pytest.mark.parametrize("value", SAFE_VALUES)
def test_allow_mocks_outside_production(monkeypatch, value):
    """Les mocks restent autorisés partout ailleurs — c'est leur raison d'être."""
    monkeypatch.setenv("USE_MOCKS", "true")
    monkeypatch.setenv("ENVIRONMENT", value)
    monkeypatch.setenv("ENV", value)

    assert_mocks_not_in_production()  # ne doit pas lever


@pytest.mark.parametrize("value", PRODUCTION_VALUES + SAFE_VALUES)
def test_allow_production_without_mocks(monkeypatch, value):
    """Sans mocks, aucun environnement n'est bloqué."""
    monkeypatch.setenv("USE_MOCKS", "false")
    monkeypatch.setenv("ENVIRONMENT", value)
    monkeypatch.setenv("ENV", value)

    assert_mocks_not_in_production()  # ne doit pas lever


def test_guard_runs_at_import_of_main():
    """`main.py` appelle la garde **à l'import**, pas dans le `lifespan`.

    C'est essentiel : le `lifespan` enveloppe son démarrage dans un
    `except Exception` qui journalise puis continue (« Application will continue
    despite startup errors »). Une `RuntimeError` levée là serait avalée et l'app
    servirait quand même. À l'import, elle empêche l'application d'exister.
    """
    source = (
        __import__("pathlib").Path(__file__).resolve().parent.parent / "app" / "main.py"
    ).read_text(encoding="utf-8")

    guard_call = source.index("assert_mocks_not_in_production()")
    app_creation = source.index("app = FastAPI(")
    assert guard_call < app_creation, (
        "La garde doit être appelée avant la création de l'app, au niveau module."
    )
    assert "assert_mocks_not_in_production()" not in source[app_creation:], (
        "Ne pas déplacer la garde dans le lifespan : ses exceptions y sont avalées."
    )
