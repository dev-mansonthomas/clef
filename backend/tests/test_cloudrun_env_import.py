"""L'application doit démarrer avec l'environnement que Cloud Run lui donne.

Ce fichier existe à cause d'une panne réelle. Le premier déploiement a échoué avec
« The user-provided container failed the configured startup probe checks » — un
message qui parle de sonde. La cause était ailleurs :

    pydantic_settings.exceptions.SettingsError: error parsing value for field
    "allowed_frontend_urls" from source "EnvSettingsSource"

`pydantic-settings` exige du **JSON** pour tout champ de type complexe lu depuis
l'environnement. `ALLOWED_FRONTEND_URLS=https://clef-frontend-xxx.run.app` levait donc
une exception à l'**import** de `app.auth.config`, donc avant que l'application
existe — et Cloud Run ne pouvait rapporter que l'absence de réponse.

Le piège de fond : **en local, aucune de ces variables n'est définie.** Les valeurs par
défaut s'appliquent, tout passe, et la suite entière était verte. Aucun test ne
plaçait l'application dans l'environnement où elle allait réellement tourner.

D'où ce fichier : il rend l'environnement de production **la** condition testée, plutôt
qu'une variable après l'autre au fil des pannes. `test_cloudrun_template.py` vérifie la
forme du descripteur ; celui-ci vérifie que l'application y survit.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RACINE = Path(__file__).resolve().parents[2]
TEMPLATE = RACINE / "deploy" / "cloudrun-api.yaml.tpl"

# Valeurs réalistes, de la FORME que le script de déploiement produit réellement —
# pas des valeurs commodes. `ALLOWED_FRONTEND_URLS` est une URL nue, pas du JSON :
# c'est précisément ce que 01-gcp-deploy.sh transmet.
VALEURS = {
    "SERVICE_NAME": "clef-api",
    "ENVIRONMENT": "dev",
    "MAX_INSTANCES": "1",
    "MIN_INSTANCES": "0",
    "SERVICE_ACCOUNT": "clef-backend@projet.iam.gserviceaccount.com",
    "BACKEND_IMAGE": "europe-west1-docker.pkg.dev/projet/clef-images/clef-api:t",
    "PROJECT_ID": "projet",
    "EMAIL_GESTIONNAIRE_DT": "prenom.nom@croix-rouge.fr",
    "CORS_ORIGINS": "https://clef-frontend-abc.europe-west1.run.app,https://clef-api-abc.europe-west1.run.app",
    "ALLOWED_FRONTEND_URLS": "https://clef-frontend-abc.europe-west1.run.app",
    "FRONTEND_URL": "https://clef-frontend-abc.europe-west1.run.app",
    "DOMAIN": "clef-frontend-abc.europe-west1.run.app",
    "GOOGLE_REDIRECT_URI": "https://clef-frontend-abc.europe-west1.run.app/auth/callback",
    "BACKEND_URL": "https://clef-api-abc.europe-west1.run.app",
    "VEHICULES_SPREADSHEET_ID": "",
    "BENEVOLES_SPREADSHEET_ID": "",
    "RESPONSABLES_SPREADSHEET_ID": "",
    "REDIS_MEMORY": "512Mi",
    "REDIS_MAXMEMORY": "332mb",
    "SNAPSHOTS_BUCKET": "projet-clef-redis-snapshots",
}

VARIABLE = re.compile(r"\$\{([A-Z_]+)\}")


def _env_du_gabarit() -> dict[str, str]:
    """Les variables d'environnement telles que Cloud Run les posera.

    On lit le descripteur rendu plutôt qu'une liste recopiée : ajouter une variable au
    gabarit la fait automatiquement entrer dans ce test.
    """
    brut = TEMPLATE.read_text(encoding="utf-8")
    rendu = yaml.safe_load(VARIABLE.sub(lambda m: VALEURS[m.group(1)], brut))
    backend = next(
        c for c in rendu["spec"]["template"]["spec"]["containers"] if c["name"] == "backend"
    )
    env = {}
    for e in backend.get("env", []):
        if "value" in e:
            env[e["name"]] = str(e["value"])
        else:
            # Injecté par secretKeyRef : Cloud Run pose une valeur opaque. On en met
            # une, la forme important plus que le contenu.
            env[e["name"]] = "valeur-de-secret-factice"
    return env


def _executer(code: str, env_supplementaire: dict[str, str]) -> subprocess.CompletedProcess:
    env = {
        # Un environnement volontairement MINIMAL : sur Cloud Run, rien de la machine
        # de développement n'est présent. Un test qui hérite de l'environnement local
        # peut passer grâce à une variable que la production n'aura pas.
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "USE_MOCKS": "true",  # aucun appel réseau depuis un test
        **env_supplementaire,
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=RACINE / "backend",
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_la_configuration_survit_a_l_environnement_de_production():
    """Le cas exact qui a fait échouer le premier déploiement."""
    env = _env_du_gabarit()
    r = _executer(
        "from app.auth.config import auth_settings as s;"
        "import json;"
        "print(json.dumps({'urls': s.allowed_frontend_urls,"
        " 'redirect': s.google_redirect_uri,"
        " 'secure': s.session_cookie_secure}))",
        env,
    )
    assert r.returncode == 0, (
        "app.auth.config ne s'importe pas avec l'environnement de Cloud Run.\n"
        "C'est une panne au démarrage du conteneur, que Cloud Run rapportera comme "
        "un échec de sonde — sans nommer la configuration.\n\n"
        f"{r.stderr[-2500:]}"
    )
    lu = json.loads(r.stdout.strip().splitlines()[-1])
    assert lu["urls"] == [VALEURS["ALLOWED_FRONTEND_URLS"]], (
        f"ALLOWED_FRONTEND_URLS mal interprétée : {lu['urls']}"
    )
    assert lu["redirect"].endswith("/auth/callback")
    assert lu["secure"] is True, (
        "SESSION_COOKIE_SECURE doit être actif : le cookie part sur une origine HTTPS."
    )


def test_l_application_s_importe_avec_l_environnement_de_production():
    """Plus large : tout le module `app.main`, donc les 21 routers et les gardes.

    L'import de `app.main` exécute `assert_mocks_not_in_production()` et construit
    l'objet FastAPI. C'est ce que fait uvicorn au démarrage du conteneur.
    """
    env = _env_du_gabarit()
    r = _executer("import app.main; print('IMPORT OK', len(app.main.app.routes))", env)
    assert r.returncode == 0, (
        f"app.main ne s'importe pas avec l'environnement de Cloud Run.\n\n{r.stderr[-2500:]}"
    )
    assert "IMPORT OK" in r.stdout


def test_la_documentation_interactive_est_fermee_dans_cet_environnement():
    """Le gabarit ne pose pas ENABLE_API_DOCS : le défaut doit donc fermer /docs."""
    env = _env_du_gabarit()
    r = _executer(
        "import app.main as m;"
        "print('DOCS', m.app.docs_url, m.app.openapi_url, m.app.redoc_url)",
        env,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "DOCS None None None" in r.stdout, (
        f"/docs, /openapi.json ou /redoc restent exposés : {r.stdout.strip()}"
    )


@pytest.mark.parametrize(
    "variable,valeur",
    [
        # Les formes tordues que le script peut produire en vrai.
        ("ALLOWED_FRONTEND_URLS", ""),          # tout premier déploiement
        ("ALLOWED_FRONTEND_URLS", "https://a.run.app,https://b.run.app"),
        ("CORS_ORIGINS", ""),
        ("GOOGLE_REDIRECT_URI", ""),
        ("DOMAIN", ""),
        ("FRONTEND_URL", ""),
    ],
)
def test_les_valeurs_degradees_ne_font_pas_planter_l_import(variable: str, valeur: str):
    """Une variable vide doit dégrader le service, jamais l'empêcher de démarrer.

    Le script rend plusieurs de ces variables vides au tout premier déploiement, avant
    que l'URL du service existe. Un plantage à l'import rendrait alors la seconde passe
    — celle qui les renseigne — impossible à atteindre.
    """
    env = _env_du_gabarit()
    env[variable] = valeur
    r = _executer("import app.main; print('IMPORT OK')", env)
    assert r.returncode == 0, (
        f"{variable}={valeur!r} empêche l'import : le conteneur ne démarrerait pas, "
        f"et la seconde passe du script serait inatteignable.\n\n{r.stderr[-2000:]}"
    )
