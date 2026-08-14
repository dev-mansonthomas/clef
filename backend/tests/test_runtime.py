"""Garde sur le runtime Python.

Le dépôt a déjà connu une dérive silencieuse entre la version exigée par le projet
et celle utilisée par la VM, la CI et les images Docker. Ce test fait échouer la
suite dès que l'interpréteur qui l'exécute ne satisfait plus le `requires-python`
déclaré, plutôt que de laisser la divergence se manifester en production.
"""
import sys
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _required_minimum() -> tuple[int, ...]:
    """Extrait le minimum de `requires-python` (forme attendue : `>=X.Y`)."""
    with PYPROJECT.open("rb") as handle:
        requires = tomllib.load(handle)["project"]["requires-python"]

    spec = requires.strip()
    assert spec.startswith(">="), (
        f"requires-python vaut {requires!r} ; ce test ne sait lire que la forme '>=X.Y'."
    )
    return tuple(int(part) for part in spec.removeprefix(">=").strip().split("."))


def test_runtime_satisfies_pyproject():
    """L'interpréteur courant satisfait le `requires-python` du pyproject."""
    minimum = _required_minimum()
    current = sys.version_info[: len(minimum)]
    assert current >= minimum, (
        f"Python {'.'.join(map(str, current))} exécute la suite, mais le projet "
        f"exige >= {'.'.join(map(str, minimum))}. "
        "Recréer le venv : uv venv --python 3.14 .venv"
    )


def test_pyproject_and_requirements_agree_on_pydantic_major():
    """`pyproject` et `requirements.txt` ne divergent pas sur Pydantic.

    Les deux fichiers coexistent (l'un pour le packaging, l'autre pour l'install
    reproductible) et rien ne les synchronise. Pydantic v1 vs v2 est la divergence
    qui casserait le plus silencieusement tout `app/models/`.
    """
    requirements = (PYPROJECT.parent / "requirements.txt").read_text(encoding="utf-8")
    pinned = [
        line for line in requirements.splitlines()
        if line.strip().startswith("pydantic==")
    ]
    assert len(pinned) == 1, f"Attendu un seul pin pydantic==, trouvé {pinned}"
    assert pinned[0].split("==")[1].startswith("2."), (
        f"Le code cible Pydantic v2 ; requirements.txt épingle {pinned[0]}"
    )
