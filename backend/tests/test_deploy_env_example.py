"""`deploy/deploy.<env>.env` est l'unique source des variables d'un environnement.

Avant le 2026-08-28, il y en avait DEUX : ce fichier, et
`deploy/terraform/environments/<env>.tfvars`, qui portait `project_id`, `region` et
`public_domain`. `00-infra.sh` lisait le second, `01-gcp-deploy.sh` et `02-logs.sh` le
premier. Conséquence vécue le jour même : le domaine de dev corrigé d'un seul côté,
avec pour symptôme un certificat qui ne couvre pas l'hôte que l'application annonce —
et personne ne pense à aller chercher une valeur d'environnement dans du code Terraform.

Les tfvars sont supprimés ; Terraform reçoit ses valeurs en `-var`. Ces tests tiennent
la règle : une seule source, et le fichier d'exemple — le seul des deux qui soit
VERSIONNÉ, celui d'un environnement réel portant des données personnelles — documente
toutes les clés.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
EXEMPLE = RACINE / "deploy" / "deploy.env.example"
INFRA = RACINE / "00-infra.sh"
DEPLOIEMENT = RACINE / "01-gcp-deploy.sh"
COMMUN = RACINE / "deploy" / "env-commun.sh"


def _cles_de_l_exemple() -> set[str]:
    noms = set()
    for ligne in EXEMPLE.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            noms.add(ligne.split("=", 1)[0].strip())
    return noms


def test_aucun_tfvars_dans_la_racine_terraform_active():
    """Un tfvars qui réapparaît recrée la seconde source, donc la divergence.

    ⚠️ Le contrôle est volontairement borné à `deploy/` : `backend/terraform/` et
    `infra/` — les DEUX anciennes racines, périmées — portent encore leurs propres
    tfvars et leurs `terraform.tfstate` locaux. C'est le constat N12, une suppression
    qui n'a pas été faite ici parce qu'elle touche des fichiers d'état.
    """
    actifs = sorted(
        p.relative_to(RACINE).as_posix() for p in (RACINE / "deploy").rglob("*.tfvars")
    )
    assert not actifs, (
        f"fichiers tfvars présents : {actifs}. Les variables d'environnement vivent "
        "dans deploy/deploy.<env>.env, et 00-infra.sh les passe en -var."
    )


def test_terraform_recoit_ses_variables_du_fichier_d_environnement():
    """`-var-file` ferait de Terraform une source ; `-var` en fait un consommateur."""
    src = INFRA.read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "-var-file" not in code, (
        "00-infra.sh ne doit plus lire de fichier de variables Terraform"
    )
    assert 'charger_env_deploiement "$ENVIRONMENT"' in code, (
        "00-infra.sh doit lire deploy/deploy.<env>.env, comme les deux autres scripts"
    )
    assert re.search(r'-var "project_id=\$PROJECT_ID"', code), (
        "les valeurs doivent être passées explicitement en -var"
    )


def test_toute_variable_passee_a_terraform_est_documentee():
    """Sinon la source unique devient une source incomplète.

    Le fichier d'un environnement réel est gitignoré — il porte l'adresse du
    gestionnaire DT, une donnée personnelle. L'exemple est donc le SEUL endroit
    versionné où un opérateur peut découvrir qu'une clé existe.
    """
    src = INFRA.read_text(encoding="utf-8")
    # -var "nom_terraform=$VARIABLE_SHELL"
    variables = set(re.findall(r'-var "[a-z_]+=\$\{?([A-Z_][A-Z0-9_]*)', src))
    assert variables, "aucune variable passée à Terraform — le motif a dérivé"

    # ENVIRONMENT vient de l'argument de ligne de commande, pas du fichier.
    variables.discard("ENVIRONMENT")

    manquantes = variables - _cles_de_l_exemple()
    assert not manquantes, (
        f"variables passées à Terraform et absentes de deploy.env.example : "
        f"{sorted(manquantes)}. Un opérateur ne peut pas deviner qu'elles existent."
    )


def test_la_validation_du_domaine_est_partagee():
    """Deux validations pour une même valeur, c'est deux règles qui divergent.

    La même valeur alimente le certificat managé (via 00-infra.sh) et les URL de
    l'application (via 01-gcp-deploy.sh). Une règle par script aurait fini par
    accepter d'un côté ce que l'autre refuse — sur l'hôte qui finit imprimé sur les
    véhicules.
    """
    commun = COMMUN.read_text(encoding="utf-8")
    assert "valider_domaine_public()" in commun
    assert r"'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'" in commun, (
        "la règle de forme du domaine doit vivre dans deploy/env-commun.sh"
    )
    for script in (INFRA, DEPLOIEMENT):
        src = script.read_text(encoding="utf-8")
        assert "./deploy/env-commun.sh" in src, f"{script.name} doit sourcer env-commun.sh"
        assert 'valider_domaine_public "${PUBLIC_DOMAIN:-}"' in src, (
            f"{script.name} doit valider le domaine avant d'agir"
        )


def test_chaque_variable_du_service_est_traçable_depuis_l_exemple():
    """« Je n'aurais jamais pensé à aller voir là » ne doit plus arriver.

    Le service déployé reçoit ses variables de QUATRE origines : ce fichier, les
    secrets de Secret Manager, les valeurs dérivées par `01-gcp-deploy.sh`, et les
    valeurs fixes du gabarit. Un opérateur qui cherche d'où vient une variable n'a
    aucun moyen de le deviner — sauf si le fichier de référence les nomme toutes, y
    compris celles qui ne s'y configurent PAS.

    Ce test exige donc que chaque variable injectée dans le gabarit Cloud Run
    apparaisse dans `deploy.env.example` : soit comme clé, soit dans la carte
    « Ce qui n'est PAS ici, et où c'est ».
    """
    gabarit = (RACINE / "deploy" / "cloudrun-api.yaml.tpl").read_text(encoding="utf-8")
    injectees = {
        nom for nom in re.findall(r"^\s+- name: ([A-Z][A-Z0-9_]*)$", gabarit, re.M)
    }
    assert len(injectees) > 15, f"seulement {len(injectees)} variables trouvées — motif dérivé"

    texte = EXEMPLE.read_text(encoding="utf-8")
    absentes = sorted(nom for nom in injectees if nom not in texte)
    assert not absentes, (
        f"variables injectées dans le service et introuvables dans "
        f"deploy/deploy.env.example : {absentes}. Même celles qui ne se configurent pas "
        "ici doivent y être nommées, avec leur origine — sinon on les cherche dans le "
        "mauvais fichier, ce qui a déjà coûté trois cycles de déploiement."
    )


def _valeur(fichier: Path, cle: str) -> str | None:
    """Valeur affectée à `cle` dans un fichier d'environnement, sans les commentaires."""
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne.startswith(f"{cle}="):
            return ligne.split("=", 1)[1].strip()
    return None


def test_min_instances_nest_pas_zero():
    """`MIN_INSTANCES=0` est la cause d'un 500 observé en production le 2026-08-29.

    Séquence relevée dans Cloud Logging (heures de Paris), sur `GET /api/config` :

        20:11:36.508  ERROR  The request failed because the instance failed the
                             readiness check.
        20:11:36.513  WARNING The request was aborted because there was no
                             available instance.
        20:11:36.543  INFO   Starting new instance. Reason: AUTOSCALING
        20:11:37.441  Error: … storageLayout call failed … code = Unimplemented
        20:11:38.650  WARNING Container called exit(255).
        20:11:40.575  ERROR  terminated: … volume (type: gcs, name: snapshots):
                             mount operation failed
        20:11:40.889  INFO   GetStorageLayout -> (…) 62 msec      ← réussit

    Le montage gcsfuse a échoué **une fois**, puis le même appel a réussi en 62 ms.
    C'est un échec transitoire, et Cloud Run l'a lui-même rattrapé — mais la requête
    en vol, elle, était déjà perdue. Aucune ligne `GET /api/config` n'atteint uvicorn :
    ce n'était pas un bug applicatif.

    `MIN_INSTANCES=0` est ce qui expose l'utilisateur à cette classe de panne : sans
    instance tiède, **chaque premier clic après une période d'inactivité** déclenche un
    démarrage à froid, donc une tentative de montage. Cloud Run n'expose aucune option
    de montage permettant d'activer les réessais (`enable-mount-retries` n'est pas dans
    la liste supportée), et la configuration imprimée par gcsfuse confirme
    `EnableMountRetries:false`.

    Le même réglage ferme le constat N11 : à 0, chaque mise en veille repart du dernier
    instantané RDB, donc perd jusqu'à 10 minutes d'écritures.

    ⚠️ Ce test ne lit que le fichier VERSIONNÉ. Le fichier d'un environnement réel
    (`deploy/deploy.dev.env`, non versionné) doit être corrigé à la main — c'est lui que
    `01-gcp-deploy.sh` lit réellement.
    """
    for source, nom in (
        (EXEMPLE, "deploy/deploy.env.example"),
        (DEPLOIEMENT, "01-gcp-deploy.sh (valeur de repli)"),
    ):
        contenu = source.read_text(encoding="utf-8")
        if source is DEPLOIEMENT:
            trouve = re.search(r'MIN_INSTANCES="\$\{MIN_INSTANCES:-(\d+)\}"', contenu)
            assert trouve, "Le repli de MIN_INSTANCES a disparu de 01-gcp-deploy.sh"
            valeur = trouve.group(1)
        else:
            valeur = _valeur(source, "MIN_INSTANCES")
            assert valeur is not None, f"MIN_INSTANCES absent de {nom}"
        assert valeur != "0", (
            f"{nom} porte MIN_INSTANCES=0. Un démarrage à froid dont le montage gcsfuse "
            "échoue renvoie 500 à la requête en vol (constat du 2026-08-29), et chaque "
            "mise en veille perd jusqu'à 10 min d'écritures (N11)."
        )
