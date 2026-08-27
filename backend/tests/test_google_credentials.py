"""Chargement des credentials Google : fichier de clé en local, ADC en Cloud Run.

Quatre services dupliquaient exactement le même `_get_credentials()` : lire
`GOOGLE_APPLICATION_CREDENTIALS`, échouer s'il est absent. Conséquence : un déploiement
**exigeait une clé de service account à longue durée**, ce que le constat H6 pointe
comme le mauvais patron — et cette clé se retrouvait en clair dans le state Terraform.

Sur Cloud Run, le service s'exécute **sous** le service account : les credentials
viennent du serveur de métadonnées, sans clé. C'est ce que fait
`google.auth.default()`.

L'identité obtenue est la même dans les deux cas ; seule la provenance change. Aucune
délégation à l'échelle du domaine n'est utilisée dans le dépôt (vérifié), donc rien ne
requiert de clé.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.google_credentials import load_service_credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def test_key_file_is_used_when_the_variable_points_at_one(monkeypatch, tmp_path):
    """En local, un fichier de clé explicite reste prioritaire."""
    key = tmp_path / "sa.json"
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))

    with patch(
        "app.services.google_credentials.service_account.Credentials"
        ".from_service_account_file"
    ) as from_file:
        from_file.return_value = MagicMock(name="creds-fichier")
        creds = load_service_credentials(SCOPES)

    from_file.assert_called_once()
    assert from_file.call_args.kwargs["scopes"] == SCOPES
    assert creds is from_file.return_value


def test_adc_is_used_when_the_variable_is_absent(monkeypatch):
    """Sans variable, on prend l'identité attachée — le cas de Cloud Run."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    with patch("app.services.google_credentials.google_auth_default") as default:
        default.return_value = (MagicMock(name="creds-adc"), "rcq-fr-dev")
        creds = load_service_credentials(SCOPES)

    default.assert_called_once_with(scopes=SCOPES)
    assert creds is default.return_value[0]


def test_adc_is_used_when_the_path_does_not_exist(monkeypatch):
    """Une variable pointant un fichier absent ne doit pas faire échouer le démarrage.

    Cas réel : un `.env` hérité du développement local, déployé tel quel, qui pointe
    `/credentials/…` alors que rien n'est monté. Échouer là rendrait le service
    inutilisable pour une raison de configuration, alors que l'identité attachée
    suffit.
    """
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/credentials/absent.json")

    with patch("app.services.google_credentials.google_auth_default") as default:
        default.return_value = (MagicMock(name="creds-adc"), "rcq-fr-dev")
        creds = load_service_credentials(SCOPES)

    default.assert_called_once()
    assert creds is default.return_value[0]


def test_adc_failure_is_reported_with_context(monkeypatch):
    """Si ni clé ni ADC ne sont disponibles, le message doit être actionnable."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    with patch("app.services.google_credentials.google_auth_default") as default:
        default.side_effect = Exception("metadata server unreachable")
        with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS"):
            load_service_credentials(SCOPES)


def test_the_four_services_share_the_helper():
    """Garde structurelle : plus de duplication du chargement de credentials.

    Le même bloc existait dans sheets_real, drive_real, gmail_real et
    carnet_bord_service. Quatre copies, c'est quatre endroits où oublier le repli ADC.
    """
    from pathlib import Path

    services = Path(__file__).resolve().parent.parent / "app" / "services"
    for name in (
        "sheets_real.py", "drive_real.py", "gmail_real.py", "carnet_bord_service.py"
    ):
        source = (services / name).read_text(encoding="utf-8")
        assert "load_service_credentials" in source, f"{name} n'utilise pas le helper"
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in source, (
            f"{name} lit encore la variable directement : le repli ADC y sera oublié"
        )
