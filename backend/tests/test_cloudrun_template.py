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
    "CORS_ORIGINS": "https://frontend.example,https://api.example",
    "GOOGLE_REDIRECT_URI": "https://api.example/auth/callback",
    "DT_OAUTH_REDIRECT_URI": "https://api.example/auth/callback-dt",
    "ALLOWED_FRONTEND_URLS": "https://frontend.example",
    "FRONTEND_URL": "https://frontend.example",
    "DOMAIN": "frontend.example",
    "BACKEND_URL": "https://api.example",
    "VEHICULES_SPREADSHEET_ID": "id-vehicules",
    "BENEVOLES_SPREADSHEET_ID": "id-benevoles",
    "RESPONSABLES_SPREADSHEET_ID": "id-responsables",
    "REDIS_MEMORY": "512Mi",
    "REDIS_MAXMEMORY": "332mb",
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
    # Le rendu vit dans `deploy_api()`, appelé une ou deux fois selon qu'on crée le
    # service ou qu'on le met à jour.
    fonction = script[script.index("deploy_api() {") : script.index("envsubst < \"$TEMPLATE\"")]
    manquantes = [v for v in SUBSTITUTIONS if f"{v}=" not in fonction]
    assert not manquantes, (
        f"01-gcp-deploy.sh ne transmet pas à envsubst : {manquantes}. "
        "Elles seraient rendues comme chaîne vide."
    )


def test_l_outil_de_journaux_filtre_par_conteneur():
    """Le nom du conteneur est un label Cloud Logging, pas un champ.

    Sans `labels."run.googleapis.com/container_name"`, les lignes du backend et
    celles du sidecar redis arrivent entremêlées, et on attribue une erreur au
    mauvais conteneur — exactement le genre de diagnostic qui coûte une heure.

    Ce test tient aussi le fait que l'outil interroge Cloud Logging par NOM DE
    RÉVISION : une révision qui échoue au démarrage n'a jamais servi de trafic et
    n'apparaît donc pas dans `gcloud run services logs read`.
    """
    outil = TEMPLATE.parents[1] / "02-logs.sh"
    assert outil.is_file(), "02-logs.sh absent"
    src = outil.read_text(encoding="utf-8")
    assert 'labels.\\"run.googleapis.com/container_name\\"' in src, (
        "les journaux doivent être filtrés par conteneur"
    )
    assert "resource.labels.revision_name" in src, (
        "interroger par nom de révision, sinon les révisions en échec sont invisibles"
    )
    assert "status.conditions" in src, (
        "les conditions du service portent le message d'échec réel"
    )
    # Les adresses de service account doivent rester lisibles.
    assert "gserviceaccount" in src, (
        "le masquage doit épargner les adresses de service account, sinon le "
        "`describe` devient inutilisable pour le diagnostic."
    )


def test_l_outil_de_journaux_ne_confond_pas_echec_et_absence():
    """« ∅ aucune révision » ne doit jamais être le symptôme d'un gcloud en échec.

    `derniere_revision()` faisait `2>/dev/null` : jeton expiré, droit manquant, API
    désactivée, mauvais projet sortaient tous en chaîne vide, et l'appelant affichait
    « ∅ aucune révision » — le diagnostic exactement inverse, le service étant bien là.

    Constaté le 2026-08-28 : une collecte `--what=run` a écrit un index à
    `"fichiers": []` et `"collectesEnEchec": []` — donc « tout va bien, il n'y a
    rien » — alors que cinq révisions existaient.

    Second piège, trouvé en exécution : la fonction appelée en `$(...)` tourne dans un
    sous-shell, et l'erreur remontée par variable globale était perdue. D'où
    l'interdiction de la substitution de commande ici.
    """
    src = (TEMPLATE.parents[1] / "02-logs.sh").read_text(encoding="utf-8")
    bloc = src[src.index("derniere_revision() {") :]
    bloc = bloc[: bloc.index("\n}\n")]
    assert "2>/dev/null" not in bloc, (
        "la liste des révisions ne doit pas jeter stderr : l'échec deviendrait "
        "indiscernable de l'absence"
    )
    # Le commentaire de la fonction CITE la forme fautive pour l'expliquer : ne
    # regarder que le code exécuté.
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "$(derniere_revision" not in code, (
        "appelée en substitution de commande, la fonction tourne dans un sous-shell "
        "et son erreur est perdue — passer par DERNIERE_REVISION"
    )
    assert "revision-introuvable" in src, (
        "l'échec doit produire un FICHIER portant le message de gcloud, sinon l'index "
        "paraît simplement vide"
    )
    assert "le service n'a jamais été déployé" in src, (
        "et le cas « réellement aucune révision » doit rester distinct de l'échec"
    )


@pytest.mark.parametrize("script", ["00-infra.sh", "01-gcp-deploy.sh", "02-logs.sh"])
def test_un_seul_trap_exit_par_script(script: str):
    """Les traps bash ne s'additionnent pas — le second REMPLACE le premier.

    Défaut réel : `00-infra.sh` posait `trap ecrire_rapport EXIT` en tête, puis
    `trap 'rm -f "$PLAN_FILE"' EXIT` à l'étape du plan. Le second écrasait le
    premier, et le rapport JSON n'était donc **jamais** écrit sur une exécution
    complète.

    Le piège dans le piège : mon test d'origine ne sortait qu'en échec précoce —
    avant l'installation du second trap — donc il passait. Un test qui n'atteint pas
    le code fautif donne une confiance qu'il ne mérite pas.

    Le nettoyage doit vivre DANS la fonction du trap unique, avec le code de sortie
    capturé avant.
    """
    src = (TEMPLATE.parents[1] / script).read_text(encoding="utf-8")
    traps = [
        l.strip()
        for l in src.splitlines()
        if l.strip().startswith("trap ") and "EXIT" in l
    ]
    assert len(traps) <= 1, (
        f"{script} pose {len(traps)} traps EXIT : {traps}. Le dernier remplace les "
        "autres. Fusionner le nettoyage dans la fonction du trap unique."
    )


def test_le_build_reste_dans_la_region():
    """Cloud Build doit déposer ses sources dans un bucket régional.

    `--region` place le BUILD dans la région ; il ne dit rien du bucket de staging.
    Par défaut Cloud Build en crée un en multi-région **US**, que la policy
    d'organisation `constraints/gcp.resourceLocations` refuse :

        ERROR: (gcloud.builds.submit) HTTPError 412:
               'us' violates constraint 'constraints/gcp.resourceLocations'

    Le message nomme « us » sans jamais nommer le bucket — rien n'y mène. C'est la
    même famille de piège que la réplication `auto` des secrets : les valeurs par
    défaut de GCP visent des emplacements interdits sur ce projet.
    """
    script = (TEMPLATE.parents[1] / "01-gcp-deploy.sh").read_text(encoding="utf-8")
    assert "--default-buckets-behavior=regional-user-owned-bucket" in script, (
        "sans ce drapeau, `gcloud builds submit` crée son bucket de staging en "
        "multi-région US et la policy d'organisation refuse le build."
    )
    # Et le drapeau ne vaut rien si les builds ne passent pas par ce jeu d'options.
    for composant in ("backend", "frontend"):
        assert f'gcloud builds submit {composant} --tag=' in script, (
            f"le build {composant} doit passer par BUILD_FLAGS."
        )


def test_le_bucket_de_state_est_regional():
    """Même piège, autre commande : un bucket créé sans `--location` part en US."""
    script = (TEMPLATE.parents[1] / "00-infra.sh").read_text(encoding="utf-8")
    creation = script[script.index("gcloud storage buckets create") :]
    creation = creation[: creation.index("\n\n")]
    assert '--location="$REGION"' in creation, (
        "le bucket de state Terraform doit être créé dans la région : sans "
        "`--location`, gcloud le place en multi-région US, interdite ici — et ce "
        "bucket contient le state, donc des données sensibles."
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


def test_redis_sauvegarde_sur_sigterm(containers: dict):
    """Les directives `save` ne servent pas qu'à l'instantané périodique.

    C'est leur présence qui fait que Redis écrit un **dernier instantané sur SIGTERM**,
    donc qu'un arrêt propre — mise en veille, redéploiement — ne perde RIEN. Vérifié
    dans les journaux du 2026-08-28, 400 ms au total :

        Received SIGTERM scheduling shutdown...
        * Saving the final RDB snapshot before exiting.
        * BGSAVE done, 21 keys saved, 4426 bytes written.
        * DB saved on disk

    Sans aucune directive `save`, Redis s'arrêterait **sans sauvegarder** : la perte
    serait alors la pleine fenêtre depuis le dernier instantané, à chaque mise en
    veille. Un commentaire du gabarit affirmait d'ailleurs que c'était le cas — d'où ce
    test, qui fixe la propriété plutôt que la croyance.
    """
    args = containers["redis"]["args"]
    fenetres = [args[i + 1] for i, a in enumerate(args) if a == "--save"]
    assert fenetres, (
        "aucune directive `save` : Redis s'arrêterait sans écrire son instantané "
        "final, et chaque mise en veille perdrait les écritures depuis le dernier."
    )
    # Une fenêtre longue pour le régime normal, une courte pour les rafales.
    assert any(int(f.split()[0]) <= 600 for f in fenetres), (
        f"fenêtres déclarées : {fenetres}. Au moins une doit être ≤ 600 s."
    )


def test_redis_ne_fait_pas_d_aof(containers: dict):
    """Pas de journal en append sur un système de fichiers objet."""
    args = " ".join(containers["redis"]["args"])
    assert "--appendonly no" in args


def test_redis_n_evince_aucune_cle(containers: dict):
    """Redis est la base, pas un cache : évincer, c'est perdre de la donnée."""
    args = " ".join(containers["redis"]["args"])
    assert "--maxmemory-policy noeviction" in args


def test_redis_a_une_limite_memoire(containers: dict):
    """`noeviction` sans `--maxmemory` ne protège de rien.

    Sans limite, Redis n'a rien à comparer : c'est Cloud Run qui tue le conteneur en
    dépassement, et l'instance repart du dernier instantané — jusqu'à 10 minutes
    d'écritures perdues, sans signal côté Redis. Avec une limite, Redis refuse
    l'écriture et le client reçoit une erreur explicite.
    """
    args = containers["redis"]["args"]
    assert "--maxmemory" in args, (
        "aucune limite mémoire : le dépassement se traduit par un OOM-kill "
        "silencieux, pas par un refus d'écriture."
    )
    limite = args[args.index("--maxmemory") + 1]
    assert limite and limite != "0", f"limite mémoire vide ou nulle : {limite!r}"


def test_toute_variable_injectee_est_lue_par_le_code(containers: dict):
    """Une variable injectée sous un nom que le code ne lit pas est du vide utile.

    C'est la classe de bug la plus coûteuse du gabarit, parce qu'elle est
    silencieuse des deux côtés : le déploiement réussit, la variable est bien
    présente dans la révision, et l'application applique son défaut de
    développement. Trois occurrences réelles ont été trouvées ainsi —
    `ALLOWED_FRONTEND_URLS` (le code lit `CORS_ORIGINS`), `GOOGLE_REDIRECT_URI`
    absent (défaut `http://localhost:8000/auth/callback`, connexion cassée), et
    `JWT_SECRET_KEY` qu'aucun code ne lit.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    lus = set()
    for f in app_dir.rglob("*.py"):
        texte = f.read_text(encoding="utf-8")
        lus |= set(
            re.findall(r'(?:getenv|environ\.get)\(\s*"([A-Z_][A-Z0-9_]*)"', texte)
        )
        lus |= set(re.findall(r'environ\[\s*"([A-Z_][A-Z0-9_]*)"', texte))

    # ⚠️ Un grep sur `getenv` ne suffit pas : `pydantic-settings` lit l'environnement
    # **par nom de champ**, sans aucun appel visible. `ALLOWED_FRONTEND_URLS` est
    # exactement dans ce cas depuis qu'elle est portée par un champ annoté plutôt que
    # par un `os.getenv` dans la valeur par défaut. Sans cette source, le test
    # déclarerait orpheline une variable pourtant lue.
    from app.auth.config import AuthSettings

    lus |= {nom.upper() for nom in AuthSettings.model_fields}

    injectees = {e["name"] for e in containers["backend"]["env"]}
    orphelines = injectees - lus
    assert not orphelines, (
        f"variables injectées que le code ne lit jamais : {sorted(orphelines)}. "
        "Soit le nom est faux, soit la variable est inutile — dans les deux cas "
        "l'application tourne sur son défaut, sans erreur."
    )


@pytest.mark.parametrize(
    "variable,defaut_dangereux",
    [
        ("CORS_ORIGINS", "le navigateur bloque les appels du frontend déployé"),
        ("GOOGLE_REDIRECT_URI", "Google renvoie les utilisateurs vers localhost:8000"),
        ("DT_OAUTH_REDIRECT_URI",
         "la délégation Calendar/Drive/Gmail d'un gestionnaire DT échoue en "
         "redirect_uri_mismatch, Google recevant localhost:8000/auth/callback-dt"),
    ],
)
def test_variables_dont_le_defaut_casse_la_production(
    containers: dict, variable: str, defaut_dangereux: str
):
    """Deux variables qui ont un défaut, et dont le défaut est faux en production.

    Leur absence ne provoque aucune erreur — c'est pour cela qu'elles méritent un
    test plutôt qu'une relecture.
    """
    noms = {e["name"] for e in containers["backend"]["env"]}
    assert variable in noms, f"{variable} absente : {defaut_dangereux}."


# Variables que le code lit avec un défaut FAUX en production, et dont l'absence ne
# provoque aucune erreur. La liste est explicite plutôt que déduite : toutes les
# `getenv` du code n'ont pas à être injectées, seules celles-ci.
VARIABLES_OBLIGATOIRES = {
    "CORS_ORIGINS": "le navigateur bloque les appels au backend en accès direct",
    "GOOGLE_REDIRECT_URI": "Google renvoie les utilisateurs vers localhost:8000",
    "ALLOWED_FRONTEND_URLS": "toute connexion est rejetée en 400 « Invalid redirect URL »",
    "FRONTEND_URL": "les liens d'approbation de devis envoyés aux garages pointent sur localhost",
    "DOMAIN": "les QR codes IMPRIMÉS encodent https://clef.example.com",
    "SESSION_COOKIE_SECURE": "le cookie de session n'est pas marqué Secure sur un site HTTPS",
}


@pytest.mark.parametrize("variable", sorted(VARIABLES_OBLIGATOIRES))
def test_variables_dont_l_absence_est_indetectable(containers: dict, variable: str):
    """L'inverse du test précédent, et c'est lui qui manquait.

    `test_toute_variable_injectee_est_lue_par_le_code` vérifie une inclusion dans un
    seul sens : tout ce qui est injecté est lu. Il ne pouvait donc pas voir une
    variable **manquante** — c'est ainsi que `ALLOWED_FRONTEND_URLS`, pourtant lue
    par `app/auth/config.py:65`, a pu être retirée du gabarit sans qu'aucun test ne
    tombe.
    """
    noms = {e["name"] for e in containers["backend"]["env"]}
    assert variable in noms, (
        f"{variable} absente du gabarit : {VARIABLES_OBLIGATOIRES[variable]}."
    )


def test_la_documentation_interactive_reste_fermee(containers: dict):
    """Ni /docs, ni /redoc, ni /openapi.json sur un service public.

    Le service est déployé avec `allUsers` / `roles/run.invoker` — il le faut, les
    gardes sont applicatifs. Mais le schéma OpenAPI décrit alors les 86 routes à qui
    le demande : routes super-admin, gestion des clés d'API, nom de l'en-tête
    X-API-Key de la synchronisation, et les modèles du référentiel bénévoles.
    Aucun accès n'en découle, mais tout le tâtonnement disparaît.

    Le défaut du code est déjà `false` ; ce test interdit de l'ouvrir depuis le
    gabarit — c'est-à-dire d'un geste, sans revue.
    """
    env = {e["name"]: e.get("value") for e in containers["backend"]["env"]}
    assert env.get("ENABLE_API_DOCS", "false").lower() != "true", (
        "ENABLE_API_DOCS=true expose /docs et /openapi.json sur un service public."
    )


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


def test_le_preflight_verifie_la_FORME_des_secrets():
    """Une version présente ne dit rien du contenu — et deux valeurs fausses l'ont prouvé.

    Le contrôle ne comptait que les versions actives. Le 2026-08-28, deux valeurs de
    `CLEF_GOOGLE_CLIENT_ID` ont chacune coûté un cycle complet de déploiement, avec
    pour seul symptôme un « Error 401: invalid_client » rendu par Google :

      1. `ton-client-id.apps.googleusercontent.com` — la commande de DEPLOYMENT.md
         lancée telle quelle, sans substituer la valeur ;
      2. `CLEF-rcq-fr-dev-client_secret_1022015855967-2irg….apps.googleusercontent.com`
         — le NOM du fichier de credentials téléchargé, collé au lieu du champ
         `.web.client_id` qu'il contient.

    Les deux finissent par `.apps.googleusercontent.com` : un contrôle de suffixe
    n'aurait rien vu. C'est la STRUCTURE qui les distingue — `<numéro de
    projet>-<empreinte>.apps.googleusercontent.com`.
    """
    src = (TEMPLATE.parents[1] / "01-gcp-deploy.sh").read_text(encoding="utf-8")

    assert r"'^[0-9]+(-[a-z0-9]+)?\.apps\.googleusercontent\.com$'" in src, (
        "le client_id doit être validé sur sa STRUCTURE, pas sur son suffixe : les "
        "deux valeurs fausses observées finissaient par .apps.googleusercontent.com"
    )
    assert "PLACEHOLDERS=" in src, "les valeurs bouchons doivent être refusées"

    # ⚠️ Sans la sentinelle, le contrôle de caractère blanc est MORT : `$(...)`
    # supprime les retours ligne finaux, et c'est précisément le défaut cherché
    # (`echo` au lieu de `printf '%s'`). Vérifié en exécution : la valeur passait.
    assert "printf 'S%s' \"$?\"" in src, (
        "la lecture du secret doit poser une sentinelle, sinon un \\n final est "
        "invisible à la substitution de commande et le contrôle ne sert à rien"
    )
    assert "ILLISIBLE" in src, (
        "une valeur illisible (droit manquant) doit être distinguée d'une valeur "
        "fausse — ne pas rejouer le défaut de derniere_revision() dans 02-logs.sh"
    )

    # Aucune valeur de secret ne doit être journalisée. Une seule exception, assumée :
    # le client_id refusé, que Google publie de toute façon dans chaque URL
    # d'autorisation et que l'opérateur doit comparer à sa console.
    lignes = src.splitlines()
    affichages = []
    for i, ligne in enumerate(lignes):
        nu = ligne.strip()
        if "VALEUR_SECRET" not in nu or not nu.startswith(("echo ", "printf ", "if ")):
            continue
        # `printf … | grep` n'affiche RIEN : la valeur part dans le tuyau. Le tuyau
        # peut être sur la ligne suivante, la commande étant coupée par un `\`.
        suite = nu + (lignes[i + 1].strip() if nu.endswith("\\") and i + 1 < len(lignes) else "")
        if "|" in suite:
            continue
        affichages.append(nu)
    assert len(affichages) == 1, (
        f"{len(affichages)} lignes affichent une valeur de secret : {affichages}. "
        "Le script journalise tout via tee — un secret y resterait sur disque."
    )
    assert "CLIENT_ID" in src[: src.index(affichages[0])].rsplit("case", 1)[-1], (
        "la seule valeur affichable est le client_id, qui n'est pas confidentiel"
    )
