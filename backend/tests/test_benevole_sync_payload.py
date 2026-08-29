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
    RAISON_CHAMP_INVALIDE,
    RAISON_COLONNE_ABSENTE,
    RAISON_IDENTITE_DIVERGENTE,
    RAISON_UL_DIVERGENTES,
    RAISON_UL_DIVERGENTES_MULTIPLES,
    BenevoleReferentielRow,
    est_ul_de_delegation,
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
        # Colonne ajoutée à l'export le 2026-08-29, obligatoire : l'identifiant de
        # structure de l'UL du bénévole (889 = UNITE LOCALE DE PARIS 1ER ET 2EME).
        "Id Structure": "889",
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
    assert errors[0]["reason"] == RAISON_CHAMP_INVALIDE
    assert "Nivol" in errors[0]["values"]["Détail"]


def test_missing_ul_is_a_row_error():
    identites, errors = parse_referentiel_rows([_row(UL="")])

    assert identites == []
    assert errors[0]["reason"] == RAISON_CHAMP_INVALIDE
    assert "ul" in errors[0]["values"]["Détail"].lower()


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
    assert errors[0]["reason"] == RAISON_COLONNE_ABSENTE
    assert "Nivol" in errors[0]["values"]["Détail"], (
        "un onglet renommé doit produire un message actionnable : la colonne manquante "
        "est NOMMÉE, dans sa propre colonne de l'onglet ERREURS SYNCHRO"
    )


def test_mandatory_columns_are_declared():
    """La liste des colonnes obligatoires est explicite, pas déduite du modèle.

    Elle sert au contrôle « colonne absente de toutes les lignes », qui doit nommer
    la colonne manquante plutôt que rapporter dix erreurs de ligne identiques.
    """
    assert MANDATORY_COLUMNS == ("Nivol", "Nom", "Prénom", "UL", "Id Structure")


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


# ─── Le partage UL / DT, tel que le référentiel réel le pratique ─────────────
#
# Découvert au premier import réel, le 2026-08-28 : 120 « doublons » sur 4546 lignes,
# tous de la même nature. Un bénévole porteur d'une fonction à la délégation figure
# DEUX FOIS au référentiel — une ligne sous son unité locale, une sous la DT :
#
#   MASSY BOUKHOUF  01100078356D  BOUKHOUF  MASSY  UNITE LOCALE DE PARIS XII  …
#   MASSY BOUKHOUF  01100078356D  BOUKHOUF  MASSY  DT DE PARIS                …

UL_REELLE = "UNITE LOCALE DE PARIS XII"
UL_DELEGATION = "DT DE PARIS"


@pytest.mark.parametrize("ordre", [
    (UL_REELLE, UL_DELEGATION),
    (UL_DELEGATION, UL_REELLE),
])
def test_le_benevole_de_la_dt_conserve_son_unite_locale(ordre):
    """L'unité locale réelle gagne, QUEL QUE SOIT l'ordre des lignes.

    « La dernière occurrence gagne » faisait dépendre l'UL de l'ordre de la feuille, et
    perdait donc une fois sur deux la seule information utile des deux lignes.
    """
    identites, errors = parse_referentiel_rows(
        [_row(Nivol="01100078356D", UL=ul) for ul in ordre]
    )

    assert len(identites) == 1
    assert identites[0].ul == UL_REELLE
    assert identites[0].rattachement_dt is True
    assert errors == [], (
        "ce doublon est structurel : le signaler comme une erreur noierait les vraies "
        "anomalies — 120 lignes sur 4546 au premier import réel"
    )


def test_un_benevole_seulement_a_la_dt_garde_ce_libelle():
    """Sans ligne d'unité locale, il n'y a rien d'autre à conserver."""
    identites, errors = parse_referentiel_rows([_row(UL=UL_DELEGATION)])
    assert identites[0].ul == UL_DELEGATION
    assert identites[0].rattachement_dt is True
    assert errors == []


def test_le_rattachement_dt_n_est_pas_une_fonction_dt():
    """Un bénévole sans ligne DT n'est pas rattaché — le défaut est faux, pas vrai."""
    identites, _ = parse_referentiel_rows([_row(UL=UL_REELLE)])
    assert identites[0].rattachement_dt is False


def test_deux_unites_locales_differentes_restent_une_anomalie():
    """Aucune des deux n'est la délégation : c'est la feuille qui est fausse."""
    identites, errors = parse_referentiel_rows([
        _row(Nivol="01100078356D", UL=UL_REELLE),
        _row(Nivol="01100078356D", UL="UNITE LOCALE DE PARIS V"),
    ])
    assert len(identites) == 1
    assert identites[0].rattachement_dt is False
    assert len(errors) == 1
    assert errors[0]["reason"] == RAISON_UL_DIVERGENTES
    assert errors[0]["values"]["UL 1"] == "UNITE LOCALE DE PARIS V"
    assert errors[0]["values"]["UL 2"] == UL_REELLE


def test_une_identite_divergente_est_signalee():
    """Deux personnes sous un même matricule, ou une correction faite d'un seul côté."""
    _, errors = parse_referentiel_rows([
        _row(Nivol="01100078356D", UL=UL_REELLE),
        _row(Nivol="01100078356D", UL=UL_DELEGATION, Email="autre@croix-rouge.fr"),
    ])
    assert len(errors) == 1
    assert errors[0]["reason"] == RAISON_IDENTITE_DIVERGENTE
    assert errors[0]["values"]["Détail"].startswith("email")
    # Nom et prénom accompagnent l'erreur : on corrige dans la feuille, à l'œil.
    assert errors[0]["values"]["Nom"] == "Dupont"


@pytest.mark.parametrize("ul,attendu", [
    ("DT DE PARIS", True),
    ("Délégation Territoriale de Paris", True),
    ("DÉLÉGATION TERRITORIALE DE PARIS", True),
    ("UNITE LOCALE DE PARIS XII", False),
    ("UL Paris 15", False),
    ("DTP", False),          # frontière de mot : « DTP » n'est pas « DT »
    ("", False),
])
def test_la_reconnaissance_de_l_ul_de_delegation(ul, attendu):
    """La règle porte sur le LIBELLÉ, faute de colonne qui le dise.

    Un libellé non reconnu retombe sur le traitement de doublon ordinaire : signalé,
    donc visible — jamais fusionné à tort en silence.
    """
    assert est_ul_de_delegation(ul) is attendu


def test_une_raison_ne_porte_jamais_de_donnee():
    """L'invariant qui rend l'onglet ERREURS SYNCHRO triable et dénombrable.

    Une raison interpolée — « Doublon de NIVOL 011… : 2 unités locales différentes
    (UL A, UL B) » — n'est ni triable par UL, ni dénombrable par nature : le résumé
    devait effacer les valeurs à coups d'expressions régulières, donc DEVINER ce qui
    variait. Chaque donnée a désormais sa colonne, et la raison est une constante.

    Ce test compare à la liste exhaustive : une nouvelle nature d'erreur doit être
    déclarée en constante, sinon la suite échoue.
    """
    constantes = {
        RAISON_COLONNE_ABSENTE,
        RAISON_CHAMP_INVALIDE,
        RAISON_UL_DIVERGENTES,
        RAISON_UL_DIVERGENTES_MULTIPLES,
        RAISON_IDENTITE_DIVERGENTE,
    }

    lot = [
        _row(Nivol="", UL=UL_REELLE),                                  # champ invalide
        {k: v for k, v in _row().items() if k != "Nivol"},              # colonne absente
        _row(Nivol="DOUBLE", UL=UL_REELLE),
        _row(Nivol="DOUBLE", UL="UNITE LOCALE DE PARIS V"),             # 2 UL
        _row(Nivol="TRIPLE", UL=UL_REELLE),
        _row(Nivol="TRIPLE", UL="UNITE LOCALE DE PARIS V"),
        _row(Nivol="TRIPLE", UL="UNITE LOCALE DE PARIS IX"),            # 3 UL
        _row(Nivol="MAIL", UL=UL_REELLE),
        _row(Nivol="MAIL", UL=UL_DELEGATION, Email="autre@croix-rouge.fr"),
    ]

    _, errors = parse_referentiel_rows(lot)
    assert errors, "le lot doit produire des erreurs, sinon le test ne vérifie rien"

    for e in errors:
        assert e["reason"] in constantes, (
            f"raison non constante : {e['reason']!r}. Toute donnée doit passer par "
            "`values`, qui alimente une colonne dédiée."
        )
        for interdit in ("(", "«", ":"):
            assert interdit not in e["reason"] or e["reason"].count(":") == 1, (
                f"la raison {e['reason']!r} ressemble à une phrase interpolée"
            )


# ─── L'identifiant de structure de l'UL ──────────────────────────────────────
#
# L'UL d'un bénévole est un LIBELLÉ LIBRE dans la feuille (« UNITE LOCALE DE PARIS XII »).
# La jointure avec le référentiel national des structures se ferait donc sur du texte :
# une variante d'orthographe ou un accent décomposé, et le bénévole se retrouve sans UL
# connue, donc sans périmètre. L'`id_structure` rend cette jointure stricte — ce qui n'a
# de valeur que s'il est TOUJOURS présent, d'où une colonne obligatoire.

def test_l_id_de_structure_est_obligatoire():
    """Sa colonne manquante est NOMMÉE, comme les quatre autres obligatoires.

    Sur un lot d'une seule ligne, la colonne est absente de tout le lot : c'est donc
    l'erreur d'EN-TÊTE qui sort, avec les libellés reçus. Le contrôle par ligne est
    vérifié séparément — voir `test_une_seule_ligne_fautive_reste_une_erreur_de_ligne`.
    """
    row = _row()
    del row["Id Structure"]

    identites, errors = parse_referentiel_rows([row])

    assert identites == []
    assert errors[0]["reason"] == RAISON_COLONNE_ABSENTE
    assert errors[0]["values"]["Détail"].startswith("Id Structure")


@pytest.mark.parametrize("brut,attendu", [
    ("889", "889"),
    ("  889 ", "889"),          # cellule texte copiée avec des espaces
    (889, "889"),               # cellule numérique de Sheets
    (889.0, "889"),             # …et sa variante flottante
    ("00889", "889"),           # forme canonique, sans zéros de tête
])
def test_l_id_de_structure_est_normalise(brut, attendu):
    identites, errors = parse_referentiel_rows([_row(**{"Id Structure": brut})])
    assert errors == []
    assert identites[0].ul_id_structure == attendu


@pytest.mark.parametrize("invalide", ["", "0", "-1", "UL PARIS12", "889 bis", None])
def test_un_id_de_structure_non_entier_positif_est_refuse(invalide):
    """Refuser à la ligne, plutôt que laisser échouer la jointure plus tard.

    Une valeur comme « 0 » ou « UL PARIS12 » produirait une jointure qui échoue loin
    d'ici, sur un bénévole précis — alors que le défaut est dans la colonne.
    """
    identites, errors = parse_referentiel_rows([_row(**{"Id Structure": invalide})])

    assert identites == []
    assert errors[0]["reason"] == RAISON_CHAMP_INVALIDE
    assert "Id Structure" in errors[0]["values"]["Détail"]


def test_l_id_de_structure_reste_optionnel_A_LA_LECTURE():
    """Asymétrie voulue : obligatoire à l'écriture, tolérée à la lecture.

    Les 4546 bénévoles déjà en base ont été écrits avant l'ajout de la colonne. Si
    `BenevoleData` l'exigeait, leur simple lecture échouerait — et comme cette lecture
    est sur le chemin d'authentification, un problème de donnée deviendrait un refus de
    connexion sans diagnostic. C'est le raisonnement déjà tenu pour `ul`.
    """
    from app.models.redis_models import BenevoleData

    herite = BenevoleData(
        nivol="00123456A", dt="DT75", nom="Dupont", prenom="Jean", ul="UL Paris 15"
    )
    assert herite.ul_id_structure is None


def test_une_colonne_absente_de_tout_le_lot_est_une_erreur_d_en_tete():
    """4546 erreurs identiques ne valent pas mieux qu'une, et coûtent un onglet illisible.

    C'est ce que la déclaration explicite de `MANDATORY_COLUMNS` promettait — « nommer la
    colonne manquante plutôt que produire N erreurs de ligne identiques » — et que le
    contrôle par ligne ne tenait pas. L'ajout de `id_structure` l'a montré le 2026-08-29.

    ⚠️ Les EN-TÊTES REÇUS sont joints : sans eux, « Colonne absente : Id Structure »
    laisse chercher entre une colonne oubliée, une casse différente et un accent
    décomposé — trois causes indiscernables. La vraie panne du jour était de cette
    famille.
    """
    lot = []
    for i in range(3):
        row = _row(Nivol=f"NIV{i}")
        del row["Id Structure"]
        lot.append(row)

    identites, errors = parse_referentiel_rows(lot)

    assert identites == []
    assert len(errors) == 1, "une erreur d'en-tête, pas une par ligne"
    assert errors[0]["line"] is None, "elle ne vise aucune ligne : c'est l'en-tête"
    assert errors[0]["reason"] == RAISON_COLONNE_ABSENTE

    detail = errors[0]["values"]["Détail"]
    assert "Id Structure" in detail
    assert "3 lignes du lot" in detail
    # Ce qui rend la comparaison immédiate.
    assert "En-têtes reçus" in detail and "Nivol" in detail


@pytest.mark.parametrize("libelle", [
    "id_structure",
    "Id Structure",       # le libellé RÉEL de la feuille, constaté le 2026-08-29
    "ID_STRUCTURE",
    "Id-Structure",
    "  Id Structure  ",
    "IdStructure",
])
def test_les_variantes_de_casse_et_de_separateur_sont_acceptees(libelle):
    """Deux pannes de la même semaine, même cause : un libellé d'en-tête « presque » bon.

    D'abord `Prénom` avec un accent DÉCOMPOSÉ — identique à l'œil, différent en octets.
    Puis `Id Structure` refusée parce que j'avais inventé le libellé `id_structure` :
    lot devenu vide, et le vrai message masqué par le garde-fou de réconciliation.

    La comparaison se fait donc sur une forme normalisée — sans accent, sans casse, sans
    séparateur. Ce n'est pas de la complaisance : ces libellés viennent d'un export dont
    on ne maîtrise ni la casse ni la ponctuation, et rien dans la donnée ne justifie de
    distinguer `Id Structure` de `ID STRUCTURE`. Le libellé du référentiel fait foi.
    """
    row = _row()
    row[libelle] = row.pop("Id Structure")

    identites, errors = parse_referentiel_rows([row])

    assert errors == [], f"le libellé {libelle!r} doit être reconnu"
    assert identites[0].ul_id_structure == "889"


def test_un_accent_decompose_est_reconnu():
    """`Prénom` en NFD s'affiche à l'identique et pesait une colonne introuvable."""
    import unicodedata

    row = _row()
    row[unicodedata.normalize("NFD", "Prénom")] = row.pop("Prénom")

    identites, errors = parse_referentiel_rows([row])

    assert errors == []
    assert identites[0].prenom == "Jean"


def test_un_vrai_renommage_reste_refuse():
    """La tolérance porte sur la FORME du libellé, pas sur son sens.

    `Nom` → `Patronyme` n'est pas une variante d'écriture : c'est une autre colonne.
    L'erreur nomme l'attendu et liste les en-têtes reçus.
    """
    row = _row()
    row["Patronyme"] = row.pop("Nom")

    identites, errors = parse_referentiel_rows([row])

    assert identites == []
    detail = errors[0]["values"]["Détail"]
    assert detail.startswith("Nom")
    assert "Patronyme" in detail, "les en-têtes reçus doivent être listés"


def test_une_seule_ligne_fautive_reste_une_erreur_de_ligne():
    """La passe d'en-tête ne doit pas avaler le contrôle par ligne."""
    bonne = _row(Nivol="BON")
    fautive = _row(Nivol="FAUTIF")
    del fautive["Id Structure"]

    identites, errors = parse_referentiel_rows([bonne, fautive])

    assert len(identites) == 1
    assert len(errors) == 1
    assert errors[0]["line"] == 3, "le numéro de ligne de la feuille, en-tête comprise"
