"""Le gabarit Cloud Run est du code : il se teste.

`deploy/cloudrun-api.yaml.tpl` décrit un service à deux conteneurs, appliqué par
`gcloud run services replace`. Trois de ses réglages sont des pièges silencieux —
ils n'échouent pas au déploiement, ils dégradent le service sans le dire :

* l'ordre de démarrage se déclare par **annotation**, alors que la syntaxe la plus
  répandue (`depends_on` sur le conteneur) est celle du provider Terraform et se
  fait ignorer par l'API v1 ;
* cette annotation n'a d'effet que si le conteneur dont on dépend porte un
  `startupProbe` ;
* sans `cpu-throttling: "false"`, Cloud Run bride le CPU hors requête et les
  instantanés périodiques de Redis, qui sont des tâches de fond, ne partent jamais
  — la durabilité annoncée est alors fictive.

Ces tests lisent le gabarit **non rendu** : ils portent sur les décisions, pas sur
une valeur d'environnement. Voir `docs/adr/0008-*.md`.
"""
import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

TEMPLATE = Path(__file__).resolve().parents[2] / "deploy" / "cloudrun-api.yaml.tpl"

# Valeurs factices : le gabarit doit être un YAML valide **quelles que soient**
# les substitutions, on ne teste donc pas des valeurs mais une structure.
SUBSTITUTIONS = {
    "SERVICE_NAME": "clef-api",
    "ENVIRONMENT": "dev",
    "MAX_INSTANCES": "1",
    "MIN_INSTANCES": "0",
    "SERVICE_ACCOUNT": "clef-backend@projet.iam.gserviceaccount.com",
    "BACKEND_IMAGE": "europe-west1-docker.pkg.dev/projet/clef-images/clef-api:tag",
    "PROJECT_ID": "projet",
    "EMAIL_GESTIONNAIRE_DT": "prenom.nom@croix-rouge.fr",
    "ALLOWED_FRONTEND_URLS": "https://frontend.example",
    "BACKEND_URL": "https://api.example",
    "VEHICULES_SPREADSHEET_ID": "id-vehicules",
    "BENEVOLES_SPREADSHEET_ID": "id-benevoles",
    "RESPONSABLES_SPREADSHEET_ID": "id-responsables",
    "REDIS_MEMORY": "512Mi",
    "SNAPSHOTS_BUCKET": "projet-clef-redis-snapshots",
}


@pytest.fixture(scope="module")
def raw() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


VARIABLE = re.compile(r"\$\{([A-Z_]+)\}")


def _substitue(raw: str) -> str:
    """Reproduit `envsubst` : seuls les `${NOM_MAJUSCULE}` sont substitués.

    `string.Template` ne convient pas — il rejette le `${...}` littéral qui
    apparaît dans un commentaire d'en-tête du gabarit, là où `envsubst` le laisse
    tranquille.
    """
    return VARIABLE.sub(lambda m: SUBSTITUTIONS[m.group(1)], raw)


@pytest.fixture(scope="module")
def rendered(raw: str) -> dict:
    return yaml.safe_load(_substitue(raw))


@pytest.fixture(scope="module")
def containers(rendered: dict) -> dict:
    return {c["name"]: c for c in rendered["spec"]["template"]["spec"]["containers"]}


@pytest.fixture(scope="module")
def annotations(rendered: dict) -> dict:
    return rendered["spec"]["template"]["metadata"]["annotations"]


def test_toutes_les_variables_sont_connues(raw: str):
    """Aucune variable du gabarit n'échappe à la liste que le script transmet.

    `envsubst` remplace une variable non définie par la **chaîne vide**, sans
    broncher : une variable oubliée produit un descripteur silencieusement amputé.
    """
    used = set(VARIABLE.findall(raw))
    assert used == set(SUBSTITUTIONS), (
        f"variables du gabarit non couvertes : {used - set(SUBSTITUTIONS)} ; "
        f"couvertes mais absentes du gabarit : {set(SUBSTITUTIONS) - used}"
    )


def test_le_script_transmet_bien_ces_variables():
    """Le contrôle précédent ne vaut que si le script passe la même liste."""
    script = (TEMPLATE.parents[1] / "01-gcp-deploy.sh").read_text(encoding="utf-8")
    envsubst_call = script[script.index("RENDERED=$(mktemp)") : script.index("envsubst <")]
    manquantes = [v for v in SUBSTITUTIONS if f"{v}=" not in envsubst_call]
    assert not manquantes, (
        f"01-gcp-deploy.sh ne transmet pas à envsubst : {manquantes}. "
        "Elles seraient rendues comme chaîne vide."
    )


def test_deux_conteneurs_backend_et_redis(containers: dict):
    assert set(containers) == {"backend", "redis"}


def test_ordre_de_demarrage_par_annotation(annotations: dict, containers: dict):
    """Redis d'abord — et déclaré de la seule façon que l'API v1 comprenne."""
    key = "run.googleapis.com/container-dependencies"
    assert key in annotations, (
        "l'ordre de démarrage n'est pas déclaré. Le backend lit le référentiel dans "
        "Redis dès la première requête (tâche N2)."
    )
    assert json.loads(annotations[key]) == {"backend": ["redis"]}

    for nom, conteneur in containers.items():
        assert "dependsOn" not in conteneur and "depends_on" not in conteneur, (
            f"conteneur {nom} : `depends_on` est la syntaxe du provider Terraform. "
            "`gcloud run services replace` l'ignore SANS ERREUR — utiliser "
            f"l'annotation {key}."
        )


def test_redis_porte_une_sonde_de_demarrage(containers: dict):
    """Sans sonde, l'annotation de dépendance ne garantit rien."""
    probe = containers["redis"].get("startupProbe")
    assert probe, (
        "container-dependencies exige un startupProbe sur le conteneur dont on "
        "dépend : c'est lui qui signale à Cloud Run que Redis est prêt."
    )
    assert probe["tcpSocket"]["port"] == 6379


def test_seul_le_conteneur_d_entree_expose_un_port(containers: dict):
    """Contrainte Cloud Run : un seul conteneur peut exposer un port."""
    assert containers["backend"]["ports"][0]["containerPort"] == 8000
    assert "ports" not in containers["redis"], (
        "un sidecar ne doit pas déclarer de ports — le déploiement serait refusé."
    )


def test_cpu_jamais_bridee(annotations: dict):
    """Le réglage sans lequel la persistance annoncée n'existe pas."""
    assert annotations["run.googleapis.com/cpu-throttling"] == "false", (
        "CPU bridée hors requête ⇒ les BGSAVE périodiques de Redis ne partent "
        "jamais ⇒ le bucket d'instantanés reste vide."
    )


def test_gen2_pour_le_volume_gcs(annotations: dict, rendered: dict):
    assert annotations["run.googleapis.com/execution-environment"] == "gen2", (
        "gen2 est requis pour monter un volume Cloud Storage."
    )
    volume = rendered["spec"]["template"]["spec"]["volumes"][0]
    assert volume["csi"]["driver"] == "gcsfuse.run.googleapis.com"


def test_une_seule_instance(annotations: dict):
    """Une instance = un Redis. Deux instances = deux bases qui divergent."""
    assert annotations["autoscaling.knative.dev/maxScale"] == "1", (
        "maxScale > 1 donnerait un jeu de données par instance, sans aucun signal."
    )


def test_le_volume_est_monte_par_redis(containers: dict):
    mounts = containers["redis"]["volumeMounts"]
    assert [m["mountPath"] for m in mounts] == ["/snapshots"]
    args = " ".join(containers["redis"]["args"])
    assert "--dir /snapshots" in args, (
        "Redis doit écrire son RDB dans le volume monté, sinon les instantanés "
        "restent dans le conteneur et disparaissent avec lui."
    )


def test_redis_ne_fait_pas_d_aof(containers: dict):
    """Pas de journal en append sur un système de fichiers objet."""
    args = " ".join(containers["redis"]["args"])
    assert "--appendonly no" in args


def test_redis_n_evince_aucune_cle(containers: dict):
    """Redis est la base, pas un cache : évincer, c'est perdre de la donnée."""
    args = " ".join(containers["redis"]["args"])
    assert "--maxmemory-policy noeviction" in args


@pytest.mark.parametrize("interdite", ["USE_MOCKS", "GOOGLE_APPLICATION_CREDENTIALS"])
def test_variables_interdites_en_production(containers: dict, interdite: str):
    """Deux variables dont la seule présence serait un défaut.

    `USE_MOCKS` ferait servir des données fictives — le backend refuse d'ailleurs de
    démarrer dans ce cas (garde-fou S1). `GOOGLE_APPLICATION_CREDENTIALS` forcerait
    la recherche d'un fichier de clé qui n'existe pas : sur Cloud Run,
    l'authentification passe par les Application Default Credentials
    (`app/services/google_credentials.py`, constat H6).
    """
    noms = {e["name"] for e in containers["backend"].get("env", [])}
    assert interdite not in noms
