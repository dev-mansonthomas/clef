"""Le démarrage ne lit plus Google Sheets — sauf amorçage explicite en mode mock.

`docs/specs/synchronisation-referentiel-benevoles.md` §« Ce qui disparaît ».

`app/main.py` préchargeait le référentiel depuis Sheets à chaque démarrage. C'était un
**second chemin d'écriture**, avec un contrat différent de celui de la synchronisation
— notamment un repli `email → nivol` qui stockait un bénévole sous son email en guise
de clé primaire. Deux chemins, deux contrats, sur la même donnée : c'est la
contradiction relevée au point 2 de l'audit du 2026-08-20.

[ADR 0002](../docs/adr/0002-google-workspace-comme-referentiel-de-verite.md) : Sheets
est la source *en amont*, la synchronisation Apps Script est le **seul** pont.

Reste une commodité assumée : en `USE_MOCKS=true`, un amorçage peuple le référentiel
pour que le développement local et les tests aient des utilisateurs. Jamais un chemin
de production.
"""
from pathlib import Path

MAIN = Path(__file__).resolve().parent.parent / "app" / "main.py"


def test_startup_does_not_preload_from_sheets_unconditionally():
    """Garde structurelle : plus de lecture Sheets inconditionnelle au démarrage.

    Le test porte sur la source parce que le comportement est difficile à observer :
    le préchargement était enveloppé dans un `except Exception` qui journalisait un
    avertissement et continuait. Une régression serait donc silencieuse.
    """
    source = MAIN.read_text(encoding="utf-8")

    assert "sheets_service.get_benevoles()" not in source, (
        "main.py précharge à nouveau le référentiel depuis Sheets : c'est le second "
        "chemin d'écriture que la spec supprime."
    )
    assert "sheets_service.get_responsables()" not in source


def test_the_mock_bootstrap_is_guarded_by_use_mocks():
    """L'amorçage de développement doit être explicitement conditionné.

    Sans garde, il redeviendrait un préchargement de production par accident.
    """
    source = MAIN.read_text(encoding="utf-8")

    marker = "await _bootstrap_referentiel_mock("
    if marker not in source:
        return  # amorçage absent : rien à garder

    # Viser l'**appel**, pas la définition : chercher le nom nu trouverait d'abord
    # `async def _bootstrap_referentiel_mock(`, dont le voisinage ne porte aucune garde.
    window = source[max(0, source.index(marker) - 400):source.index(marker)]
    assert "use_mocks()" in window, (
        "L'appel à l'amorçage doit être gardé par `use_mocks()`."
    )


def test_bootstrap_maps_the_legacy_role_to_the_new_model():
    """L'amorçage doit produire des bénévoles au modèle **actuel**.

    Le mock Sheets porte encore l'ancien champ `role`, que `BenevoleData` ignore
    désormais. Sans traduction, tous les utilisateurs de développement deviendraient
    de simples bénévoles — et l'écran d'administration DT serait inaccessible en
    local, sans que la cause soit visible.
    """
    source = MAIN.read_text(encoding="utf-8")

    if "_bootstrap_referentiel_mock" not in source:
        return

    assert "responsable_ul" in source and "fonctions_dt" in source, (
        "L'amorçage doit traduire `role` vers responsable_ul / fonctions_dt."
    )
