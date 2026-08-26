"""Contrat de la charge utile de synchronisation : en-têtes et validation par ligne.

`docs/specs/synchronisation-referentiel-benevoles.md`, critères AC-7, AC-8, AC-14.

Deux fragilités corrigées ici :

- **Les en-têtes de la feuille étaient le contrat d'API, implicitement.** L'Apps Script
  envoie des objets dont les clés sont les libellés de colonnes ; le modèle attendait
  des noms anglais en minuscules. Un `Nom` majuscule suffisait à tout faire échouer.
- **C'était tout ou nothing.** Le corps typé `List[BenevoleSync]` était validé par
  Pydantic *avant* d'entrer dans la fonction : une seule ligne malformée rejetait le
  lot entier en 422, et le `try/except` par ligne dans la boucle ne pouvait rien
  attraper.
"""
import pytest

from app.routers.sync import (
    MANDATORY_COLUMNS,
    BenevoleReferentielRow,
    parse_referentiel_rows,
)


def _row(**overrides) -> dict:
    row = {
        "Prénom Nom": "Jean Dupont",
        "Nivol": "00123456A",
        "Nom": "Dupont",
        "Prénom": "Jean",
        "UL": "UL Paris 15",
        "Téléphone": "+33 6 12 34 56 78",
        "Email": "jean.dupont@croix-rouge.fr",
    }
    row.update(overrides)
    return {k: v for k, v in row.items() if v is not ...}


def test_french_headers_are_mapped():
    """AC-8 — les libellés de la feuille « CLEF Benevoles » sont le contrat."""
    parsed = BenevoleReferentielRow(**_row())

    assert parsed.nivol == "00123456A"
    assert parsed.nom == "Dupont"
    assert parsed.prenom == "Jean"
    assert parsed.ul == "UL Paris 15"
    assert parsed.telephone == "+33 6 12 34 56 78"
    assert parsed.email == "jean.dupont@croix-rouge.fr"


def test_prenom_nom_column_is_ignored():
    """AC-8 — la colonne de concaténation n'entre pas dans le modèle."""
    parsed = BenevoleReferentielRow(**_row())

    assert not hasattr(parsed, "prenom_nom")
    assert parsed.prenom == "Jean" and parsed.nom == "Dupont"


def test_values_are_stripped():
    """Une feuille contient des espaces parasites ; ils ne doivent pas polluer les clés."""
    parsed = BenevoleReferentielRow(**_row(
        Nivol="  00123456A  ", Email="  jean.dupont@croix-rouge.fr  "
    ))

    assert parsed.nivol == "00123456A"
    assert parsed.email == "jean.dupont@croix-rouge.fr"


def test_invalid_rows_do_not_abort_the_batch():
    """AC-7 — 10 lignes dont 2 invalides : 8 importées, 2 erreurs situées."""
    rows = [_row(Nivol=f"NIV{i:05d}", Email=f"n{i}@croix-rouge.fr") for i in range(10)]
    rows[3]["Nivol"] = ""       # sans clé primaire
    rows[7]["UL"] = ""          # un bénévole a toujours une UL

    identites, errors = parse_referentiel_rows(rows)

    assert len(identites) == 8
    assert len(errors) == 2
    # Les numéros de ligne sont ceux de la feuille : en-tête = ligne 1, données dès 2.
    assert {e["line"] for e in errors} == {5, 9}
    assert all(e["reason"] for e in errors)


def test_missing_nivol_is_a_row_error():
    """AC-14 — sans NIVOL, pas de clé primaire : ligne refusée, lot poursuivi."""
    identites, errors = parse_referentiel_rows([_row(Nivol=""), _row(Nivol="NIV1")])

    assert len(identites) == 1
    assert "Nivol" in errors[0]["reason"]


def test_missing_ul_is_a_row_error():
    identites, errors = parse_referentiel_rows([_row(UL="")])

    assert identites == []
    assert "UL" in errors[0]["reason"]


def test_absent_email_is_accepted():
    """Un bénévole sans email existe, mais ne pourra pas s'authentifier.

    L'authentification passe par l'index email. C'est une limitation à connaître, pas
    une erreur de donnée : la ligne est importée.
    """
    identites, errors = parse_referentiel_rows([_row(Email="")])

    assert errors == []
    assert identites[0].email is None


def test_missing_mandatory_column_names_it():
    """AC-8 — un onglet renommé ou réordonné doit produire un message actionnable."""
    row = _row()
    del row["Nivol"]

    identites, errors = parse_referentiel_rows([row])

    assert identites == []
    assert "Nivol" in errors[0]["reason"]


def test_mandatory_columns_are_declared():
    """La liste des colonnes obligatoires est explicite, pas déduite du modèle.

    Elle sert au contrôle « colonne absente de toutes les lignes », qui doit nommer
    la colonne manquante plutôt que rapporter dix erreurs de ligne identiques.
    """
    assert MANDATORY_COLUMNS == ("Nivol", "Nom", "Prénom", "UL")


def test_duplicate_nivol_last_wins():
    """Deux lignes pour un même NIVOL : la dernière gagne, et c'est signalé."""
    rows = [
        _row(Nivol="NIVDUP", Nom="Ancien"),
        _row(Nivol="NIVDUP", Nom="Nouveau"),
    ]

    identites, errors = parse_referentiel_rows(rows)

    assert len(identites) == 1
    assert identites[0].nom == "Nouveau"
    assert any("doublon" in e["reason"].lower() for e in errors)


def test_row_errors_carry_a_safe_excerpt():
    """Une erreur doit être diagnosticable sans recopier toute la ligne.

    On expose de quoi retrouver la ligne dans la feuille, pas l'intégralité des
    données personnelles dans des journaux à audience plus large.
    """
    _, errors = parse_referentiel_rows([_row(Nivol="")])

    assert "values" in errors[0]
    assert "Téléphone" not in errors[0]["values"]
