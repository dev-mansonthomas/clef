"""Ce qui monte vers Cloud Build finit dans l'image.

`gcloud builds submit backend` ne lit que `backend/.gcloudignore`, ou à défaut
`backend/.gitignore` — **jamais** ceux de la racine. Et `backend/Dockerfile` fait
`COPY . .`.

Conséquence trouvée le 2026-08-27, juste avant le premier déploiement : sans
`backend/.gcloudignore`, `backend/.env` — qui porte `GOOGLE_CLIENT_SECRET`,
`QR_CODE_SALT` et `SYNC_API_KEY` — aurait été livré **en clair dans une image de
conteneur** poussée sur un registre. Avec, en prime, 244 Mo de virtualenv.

Le piège est que la racine, elle, exclut bien `.env` et `.venv/` : on en déduit
qu'ils sont exclus partout.
"""
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]


def _motifs(chemin: Path) -> list[str]:
    return [
        l.strip()
        for l in chemin.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


@pytest.mark.parametrize("source", ["backend", "frontend"])
def test_le_repertoire_source_a_son_gcloudignore(source: str):
    """Sans fichier propre, gcloud retombe sur le .gitignore local — insuffisant."""
    assert (RACINE / source / ".gcloudignore").is_file(), (
        f"{source}/.gcloudignore absent : gcloud utiliserait {source}/.gitignore, "
        "qui n'exclut ni les secrets ni les dépendances locales."
    )


@pytest.mark.parametrize(
    "source,motif,pourquoi",
    [
        ("backend", ".env", "GOOGLE_CLIENT_SECRET, QR_CODE_SALT, SYNC_API_KEY en clair"),
        ("backend", ".env.*", "les variantes dev/test/prod portent les mêmes secrets"),
        ("backend", "credentials/", "clés de service account"),
        ("backend", ".venv/", "244 Mo de virtualenv, copiés dans l'image"),
        ("frontend", "node_modules/", "362 Mo réinstallés par npm ci de toute façon"),
        ("frontend", ".env", "secrets de build"),
    ],
)
def test_motifs_indispensables(source: str, motif: str, pourquoi: str):
    motifs = _motifs(RACINE / source / ".gcloudignore")
    assert motif in motifs, f"{source}/.gcloudignore doit exclure {motif} — {pourquoi}."


def test_les_fichiers_dont_l_image_a_besoin_ne_sont_pas_exclus():
    """Un .gcloudignore trop large casse la construction, pas la sécurité.

    `scripts/` compte : `app/main.py` importe `scripts.init_ul_data` au démarrage.
    """
    motifs = set(_motifs(RACINE / "backend" / ".gcloudignore"))
    for besoin in ("requirements.txt", "Dockerfile", "app/", "scripts/"):
        assert besoin not in motifs and besoin.rstrip("/") not in motifs, (
            f"{besoin} est exclu : l'image ne pourrait pas démarrer."
        )
        assert (RACINE / "backend" / besoin.rstrip("/")).exists()


def test_aucun_secret_reel_n_est_versionne():
    """Garde de bord : les .env doivent rester hors de git, quoi qu'il arrive."""
    import subprocess

    suivis = subprocess.run(
        ["git", "ls-files", "backend/"], cwd=RACINE, capture_output=True, text=True
    ).stdout.split()
    fautifs = [
        f for f in suivis if Path(f).name.startswith(".env") and not f.endswith(".example")
    ]
    assert not fautifs, f"fichiers d'environnement versionnés : {fautifs}"
