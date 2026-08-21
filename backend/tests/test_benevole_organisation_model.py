"""Le modèle bénévole sépare l'identité (feuille) de l'organisation (CLEF).

Voir `docs/specs/synchronisation-referentiel-benevoles.md` §« Partage de propriété ».

La feuille « CLEF Benevoles » porte l'identité : nivol, nom, prénom, UL, téléphone,
email. CLEF porte l'organisation : statut, responsabilité d'UL, fonctions DT. Le champ
`role` à valeur unique disparaît : il ne pouvait pas exprimer qu'un bénévole est
responsable de son UL **et** porteur d'une fonction à la DT.
"""
import pytest

from app.models.redis_models import BenevoleData


def _minimal(**overrides) -> dict:
    data = {
        "nivol": "00123456A",
        "dt": "DT75",
        "nom": "Dupont",
        "prenom": "Jean",
        "ul": "UL Paris 15",
    }
    data.update(overrides)
    return data


def test_new_fields_have_safe_defaults():
    """Un bénévole créé sans organisation est actif et sans responsabilité."""
    benevole = BenevoleData(**_minimal())

    assert benevole.statut == "actif"
    assert benevole.responsable_ul is False
    assert benevole.fonctions_dt == []
    assert benevole.telephone is None


def test_organisation_fields_are_settable():
    benevole = BenevoleData(**_minimal(
        statut="inactif",
        responsable_ul=True,
        fonctions_dt=["Référent flotte", "Suppléant logistique"],
        telephone="+33 6 12 34 56 78",
    ))

    assert benevole.statut == "inactif"
    assert benevole.responsable_ul is True
    assert benevole.fonctions_dt == ["Référent flotte", "Suppléant logistique"]
    assert benevole.telephone == "+33 6 12 34 56 78"


def test_a_benevole_can_hold_both_responsibilities():
    """Le cas que l'ancien champ `role` ne pouvait pas représenter."""
    benevole = BenevoleData(**_minimal(
        responsable_ul=True, fonctions_dt=["Référent flotte"]
    ))

    assert benevole.responsable_ul is True
    assert benevole.fonctions_dt == ["Référent flotte"]


def test_statut_only_accepts_actif_or_inactif():
    with pytest.raises(Exception):
        BenevoleData(**_minimal(statut="suspendu"))


def test_role_field_is_gone():
    """Garde structurelle : plus aucun code ne doit lire `role` sur un bénévole."""
    assert "role" not in BenevoleData.model_fields


def test_legacy_document_without_new_fields_still_parses():
    """Un document écrit avant cette évolution doit rester lisible.

    `get_benevole` est sur le chemin d'authentification : un document hérité qui
    ferait échouer la validation transformerait un problème de donnée en refus
    d'authentification généralisé, sans rapport apparent.
    """
    legacy = {
        "nivol": "00999999Z", "dt": "DT75", "ul": "UL Paris 20",
        "nom": "Ancien", "prenom": "Format", "email": "ancien@croix-rouge.fr",
    }

    benevole = BenevoleData(**legacy)

    assert benevole.statut == "actif"
    assert benevole.responsable_ul is False


def test_legacy_document_carrying_role_is_tolerated_and_ignored():
    """Un document non migré porte encore `role` : ne pas planter, ne pas le lire.

    Pydantic ignore les champs supplémentaires par défaut. Le vérifier explicitement,
    car l'alternative — une erreur de validation — bloquerait l'authentification de
    tout bénévole non migré.
    """
    benevole = BenevoleData(**_minimal(role="responsable_ul"))

    assert not hasattr(benevole, "role")
    assert benevole.responsable_ul is False  # non déduit : c'est le rôle de la migration


def test_ul_stays_optional_in_the_model():
    """Tolérant à la lecture, strict à l'écriture.

    La spec exige une UL pour tout bénévole, et la synchronisation la refuse si elle
    est vide (erreur de ligne). Mais le modèle reste permissif : un document hérité
    sans UL doit se lire, sinon l'authentification tombe pour cette personne sans
    diagnostic. Écart à la spec, assumé et documenté.
    """
    benevole = BenevoleData(**{k: v for k, v in _minimal().items() if k != "ul"})

    assert benevole.ul is None
