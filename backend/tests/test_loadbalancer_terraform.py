"""Le routage du load balancer est du code : il se teste.

Sur un LB applicatif global devant deux services Cloud Run, une règle de chemin
mal placée ne produit pas d'erreur — elle envoie du trafic au mauvais service. Le
symptôme est alors un 404 côté frontend pour un appel d'API, ou l'inverse, sans rien
dans aucun journal applicatif.

Le fichier `deploy/terraform/loadbalancer.tf` porte six blocs `test` que **GCP**
évalue à l'apply : un url map dont un `test` échoue est refusé. C'est le garde-fou le
plus solide, parce qu'il ne dépend pas de notre lecture. Les tests ci-dessous
vérifient que ces blocs existent et couvrent les cas qui comptent — sinon la
protection disparaît sans bruit.

Ils vérifient aussi les invariants qu'un `tofu validate` ne peut pas voir : la
politique TLS, la conditionnalité sur le domaine, la présence de l'API compute, et le
fait que le script dérive toutes les URL d'une seule variable.
"""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
TF = RACINE / "deploy" / "terraform"
LB = TF / "loadbalancer.tf"
SCRIPT = RACINE / "01-gcp-deploy.sh"
NGINX = RACINE / "frontend" / "clef.conf.template"


@pytest.fixture(scope="module")
def lb() -> str:
    assert LB.is_file(), f"{LB} absent"
    return LB.read_text(encoding="utf-8")


def test_le_load_balancer_est_conditionne_au_domaine(lb: str):
    """Sans domaine, aucune ressource : un LB inutile est facturé à l'heure."""
    assert re.search(r'lb_active\s*=\s*var\.public_domain\s*==\s*""\s*\?\s*0\s*:\s*1', lb), (
        "le fichier doit être conditionné à la présence d'un domaine"
    )
    ressources = re.findall(r'^resource "([a-z_]+)" "([a-z_]+)" \{', lb, re.M)
    assert ressources, "aucune ressource trouvée — les motifs ont dérivé"
    for typ, nom in ressources:
        bloc = lb[lb.index(f'resource "{typ}" "{nom}" {{') :]
        bloc = bloc[: bloc.index("\n}\n") + 3]
        assert "count" in bloc, (
            f"{typ}.{nom} n'a pas de `count` : elle serait créée même sans domaine."
        )


# Chemin → service attendu. C'est la table de routage de la spec.
ROUTAGE = {
    "/api/*": "api",
    "/auth/*": "api",
    "/admin/super/*": "api",
}


@pytest.mark.parametrize("chemin,service", sorted(ROUTAGE.items()))
def test_les_prefixes_du_backend_sont_routes_vers_l_api(lb: str, chemin: str, service: str):
    """`/auth` compte autant que `/api`, et `/admin/super` autant que les deux."""
    motif = re.compile(
        r"path_rule\s*\{[^}]*paths\s*=\s*\[([^\]]*)\][^}]*service\s*=\s*"
        r"google_compute_backend_service\." + service,
        re.S,
    )
    couvert = any(f'"{chemin}"' in m.group(1) for m in motif.finditer(lb))
    assert couvert, (
        f"{chemin} n'est pas routé vers le service « {service} ». Sans cette règle, "
        "la requête part au frontend, qui répond 404 sans qu'aucun journal "
        "applicatif ne le dise."
    )


def test_le_frontend_est_le_service_par_defaut(lb: str):
    """Le cas majoritaire — accueil, /admin/*, /form/*, statiques — doit être le défaut."""
    assert re.search(
        r"default_service\s*=\s*google_compute_backend_service\.frontend", lb
    ), "le frontend doit être le service par défaut de l'url map et du path matcher"


# Ce que les blocs `test` de l'url map doivent couvrir, et vers quoi.
CAS_ATTENDUS = [
    ("/", "frontend"),
    ("/admin/vehicles", "frontend"),          # ne doit PAS partir vers l'API
    ("/form/vehicle/abc123", "frontend"),
    ("/api/vehicles/DT75", "api"),
    ("/auth/callback", "api"),
    ("/admin/super/cache", "api"),            # doit gagner sur le défaut
]


@pytest.mark.parametrize("chemin,service", CAS_ATTENDUS)
def test_gcp_valide_le_routage_a_l_apply(lb: str, chemin: str, service: str):
    """Chaque cas qui compte doit avoir son bloc `test`, évalué par GCP.

    Un url map dont un `test` échoue est **refusé à la création**. Retirer ces blocs
    supprimerait la seule vérification du routage qui ne dépende pas de notre lecture
    — d'où ce test qui les exige.

    Les deux cas `/admin/…` sont les plus importants : ils encadrent la collision
    entre le préfixe de l'application Angular et celui du router super-admin.
    """
    motif = re.compile(
        r"test\s*\{[^}]*path\s*=\s*\"" + re.escape(chemin) +
        r"\"[^}]*service\s*=\s*google_compute_backend_service\." + service,
        re.S,
    )
    assert motif.search(lb), (
        f"aucun bloc `test` ne vérifie que {chemin} va vers « {service} »."
    )


def test_la_politique_tls_refuse_les_versions_anciennes(lb: str):
    """C'est la raison d'être du LB ici.

    Le mappage de domaine Cloud Run ne permet pas de désactiver TLS 1.0 et 1.1 —
    c'est ce qui a fait écarter cette option. Perdre la politique reviendrait à
    payer un LB pour rien.
    """
    assert 'min_tls_version = "TLS_1_2"' in lb, "TLS 1.2 minimum"
    assert 'profile         = "MODERN"' in lb or 'profile = "MODERN"' in lb
    assert re.search(r"ssl_policy\s*=\s*google_compute_ssl_policy", lb), (
        "la politique doit être RATTACHÉE au proxy HTTPS, sinon elle ne s'applique pas"
    )


def test_le_http_ne_sert_rien_et_redirige(lb: str):
    """Aucun contenu en clair, et le chemin est conservé.

    `strip_query = false` compte : les URL des QR codes et des courriels d'approbation
    portent un identifiant ou un jeton dans le chemin, parfois une requête.
    """
    assert "https_redirect         = true" in lb or "https_redirect = true" in lb
    assert "strip_query            = false" in lb or "strip_query = false" in lb
    assert re.search(r'port_range\s*=\s*"80"', lb), "le port 80 doit être servi, pour rediriger"


def test_l_ip_est_statique_et_protegee(lb: str):
    """Elle est publiée dans le DNS : la perdre impose DNS et certificat à refaire."""
    bloc = lb[lb.index('resource "google_compute_global_address"') :]
    bloc = bloc[: bloc.index("\n}\n")]
    assert "prevent_destroy = true" in bloc


def test_l_api_compute_est_declaree():
    """Elle avait été retirée avec Memorystore ; le LB en dépend entièrement."""
    apis = (TF / "apis.tf").read_text(encoding="utf-8")
    assert '"compute.googleapis.com"' in apis, (
        "sans l'API compute, aucune ressource du load balancer ne peut être créée"
    )


def test_aucun_timeout_sur_les_backends_serverless(lb: str):
    """`timeout_sec` est REFUSÉ par GCP sur un NEG serverless.

    Ce test remplace un `test_le_timeout_de_l_api_couvre_celui_du_service` qui
    comparait le délai du load balancer à celui du service Cloud Run. Le raisonnement
    était faux : le champ n'existe pas pour ce type de backend, et GCP rejette la
    création.

        Error 400: Invalid value for field 'resource.timeoutSec': '300'.
        Timeout sec is not supported for a backend service with Serverless
        network endpoint groups.

    Le piège est que la valeur par défaut passe : le backend frontend, à 30 s, a été
    créé sans broncher parce que le provider n'envoyait rien. Seul l'écart explicite
    de l'API a échoué. Un test qui n'aurait vérifié que le premier aurait conclu à
    tort que le champ est accepté.

    Le délai de requête effectif est celui du service Cloud Run — `timeoutSeconds`
    du gabarit, vérifié par test_cloudrun_template.py.
    """
    for nom in ("frontend", "api"):
        bloc = lb[lb.index(f'resource "google_compute_backend_service" "{nom}"') :]
        bloc = bloc[: bloc.index("\n}\n")]
        lignes_actives = [
            l for l in bloc.splitlines() if "timeout_sec" in l and not l.strip().startswith("#")
        ]
        assert not lignes_actives, (
            f"backend service « {nom} » : {lignes_actives}. GCP refuse `timeout_sec` "
            "sur un NEG serverless — la création du backend échoue."
        )


def test_le_script_derive_toutes_les_url_du_domaine_public():
    """Une seule variable à changer, sinon on en oublie une.

    C'est déjà arrivé : `ALLOWED_FRONTEND_URLS` retirée par erreur, `FRONTEND_URL` et
    `DOMAIN` oubliées. Toutes doivent découler de `PUBLIC_DOMAIN`.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r'PUBLIC_BASE="https://\$\{PUBLIC_DOMAIN\}"', src), (
        "le script doit construire une base publique depuis PUBLIC_DOMAIN"
    )
    assert 'local front="${PUBLIC_BASE:-${frontend_url:-$backend_url}}"' in src, (
        "le domaine public doit PRIMER sur les URL run.app, avec repli quand il est vide"
    )
    # Les quatre variables qui en découlent.
    for variable in ("ALLOWED_FRONTEND_URLS", "FRONTEND_URL", "DOMAIN", "GOOGLE_REDIRECT_URI"):
        assert re.search(rf'{variable}="\$\{{?(front|domain)', src), (
            f"{variable} doit dériver de `front`/`domain`, donc de PUBLIC_DOMAIN"
        )


# ─── Ce que la revue du 2026-08-28 a corrigé ─────────────────────────────────
# Cinq défauts d'une même famille : une ressource ou une variable dont le comportement
# réel contredisait ce que le fichier — ou la documentation — en disait.


def test_le_nom_du_certificat_change_avec_le_domaine(lb: str):
    """`create_before_destroy` sur un nom FIXE ne peut pas fonctionner.

    Changer `public_domain` force le remplacement du certificat managé. Avec
    `create_before_destroy`, Terraform crée d'abord — et GCP refuse le doublon de nom :

        Error 400: The resource 'clef-dev-cert' already exists

    L'apply échouait donc, et la bascule sans coupure que cette option promet n'avait
    jamais lieu. Le nom doit dériver du domaine (la doc du provider obtient le même
    effet avec `random_id` et ses `keepers`).
    """
    bloc = lb[lb.index('resource "google_compute_managed_ssl_certificate"') :]
    bloc = bloc[: bloc.index("\n}\n")]
    ligne_nom = next(l for l in bloc.splitlines() if re.match(r"\s*name\s*=", l))
    assert "var.public_domain" in ligne_nom, (
        f"le nom du certificat ne dépend pas du domaine : {ligne_nom.strip()}. "
        "Avec create_before_destroy, GCP refusera le doublon de nom au changement "
        "de domaine."
    )
    assert "create_before_destroy = true" in bloc, (
        "sans create_before_destroy, changer de domaine coupe le service entre la "
        "destruction et la réémission"
    )


def test_chaque_ressource_attend_l_activation_des_apis(lb: str):
    """Une ressource qui ne référence rien ne dépend de rien — le provider n'invente pas.

    L'adresse et les deux NEG portaient `depends_on = [google_project_service.apis]` ;
    la politique TLS et le certificat, non. Ces deux-là ne référencent aucune autre
    ressource : au premier apply d'un environnement où `compute.googleapis.com`
    s'active dans la même passe, elles couraient l'activation et échouaient en
    SERVICE_DISABLED. Les backend services, eux, héritent de la dépendance par les NEG.
    """
    for typ, nom in re.findall(r'^resource "([a-z_]+)" "([a-z_]+)" \{', lb, re.M):
        bloc = lb[lb.index(f'resource "{typ}" "{nom}" {{') :]
        bloc = bloc[: bloc.index("\n}\n")]
        actif = "\n".join(
            l for l in bloc.splitlines() if not l.strip().startswith("#")
        )
        if "google_project_service.apis" in actif:
            continue
        assert re.search(r"=\s*google_compute_", actif), (
            f"{typ}.{nom} ne référence aucune autre ressource compute et n'attend pas "
            "google_project_service.apis : au premier apply elle court l'activation "
            "de l'API et échoue en SERVICE_DISABLED."
        )


def test_l_interrupteur_du_load_balancer_reste_applicable(lb: str):
    """`prevent_destroy` n'est pas une expression — il vaut aussi quand `count` = 0.

    Vider `public_domain` est l'interrupteur documenté. Avec l'adresse gardée par
    `prevent_destroy` ET conditionnée à `lb_active`, cet interrupteur planifiait la
    destruction d'une ressource protégée : Terraform échouait AU PLAN
    (« Instance cannot be destroyed »), rendant la racine entière inapplicable —
    y compris pour des changements sans rapport — et bloquant `tofu destroy`.

    L'adresse suit donc sa propre condition, et reste réservée quand le LB s'éteint :
    le DNS publié reste valide.
    """
    assert re.search(r"ip_active\s*=\s*var\.public_domain\s*!=\s*\"\"", lb), (
        "l'adresse doit avoir sa propre condition, distincte de lb_active"
    )
    bloc = lb[lb.index('resource "google_compute_global_address"') :]
    bloc = bloc[: bloc.index("\n}\n")]
    assert "count   = local.ip_active" in bloc or "count = local.ip_active" in bloc, (
        "l'adresse est encore conditionnée à lb_active : vider public_domain "
        "échouera au plan sur son prevent_destroy"
    )
    assert "prevent_destroy = true" in bloc, "l'IP publiée dans le DNS reste protégée"

    variables = (TF / "variables.tf").read_text(encoding="utf-8")
    bloc_var = variables[variables.index('variable "keep_public_ip"') :]
    assert "default     = true" in bloc_var, (
        "conserver l'IP doit être le DÉFAUT : la libérer impose un nouvel "
        "enregistrement DNS et la réémission du certificat"
    )


def test_le_relais_nginx_couvre_les_memes_prefixes_que_le_load_balancer(lb: str):
    """Deux chemins vers l'API, un seul jeu de préfixes.

    Le LB route `/api/*`, `/auth/*` et `/admin/super/*`. Le relais nginx du frontend
    reste le seul chemin par l'URL run.app tant que l'ingress n'est pas verrouillé :
    un préfixe présent d'un côté et pas de l'autre donne un 404 — ou pire, l'index.html
    de l'application admin là où le client attend du JSON. C'est ce qui manquait pour
    `/admin/super`.
    """
    prefixes_lb = set()
    for paths in re.findall(r"path_rule\s*\{[^}]*paths\s*=\s*\[([^\]]*)\]", lb, re.S):
        for chemin in re.findall(r'"([^"]+)"', paths):
            prefixes_lb.add(chemin.lstrip("/").removesuffix("/*"))

    nginx = NGINX.read_text(encoding="utf-8")
    motif = re.search(r"location\s+~\s+\^/\(([^)]*)\)/", nginx)
    assert motif, "le relais du backend a disparu de clef.conf.template"
    prefixes_nginx = {p.strip() for p in motif.group(1).split("|")}

    assert prefixes_lb == prefixes_nginx, (
        f"divergence : load balancer {sorted(prefixes_lb)}, "
        f"nginx {sorted(prefixes_nginx)}. Les deux chemins doivent router les mêmes "
        "préfixes vers l'API."
    )


# ─── Le script de déploiement ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_les_destinations_de_connexion_gardent_les_origines_run_app(script: str):
    """`ALLOWED_FRONTEND_URLS` est une LISTE, pas une valeur.

    `validate_redirect_url` (app/auth/routes.py) la découpe sur les virgules et refuse
    toute destination absente. Réduite au seul domaine public, l'origine `*.run.app`
    disparaissait des destinations valides alors que ce service reste publiquement
    invocable et présent dans CORS_ORIGINS : une connexion entamée depuis cette URL
    repartait en « 400 Invalid redirect URL ».
    """
    assert "ALLOWED_FRONTEND_URLS=\"${front_allowed}\"" in script, (
        "ALLOWED_FRONTEND_URLS doit recevoir la liste, pas la seule valeur `front`"
    )
    bloc = script[script.index("local front_allowed=") :]
    bloc = bloc[: bloc.index("SERVICE_NAME=")]
    assert 'front_allowed="${front_allowed},${origine}"' in bloc, (
        "les origines run.app doivent être AJOUTÉES à la liste, pas la remplacer"
    )
    assert '"$frontend_url" "$backend_url"' in bloc, (
        "les deux origines run.app doivent être conservées comme destinations"
    )


def test_l_uri_de_redirection_affiche_est_celui_qui_est_deploye(script: str):
    """Un URI recomposé pour l'affichage garantit un redirect_uri_mismatch.

    Le message affichait « ${BACKEND_URL}/auth/callback » alors que le service part
    avec « ${PUBLIC_BASE}/auth/callback » dès qu'un domaine est configuré. L'opérateur
    enregistrait donc l'URI `*.run.app` sur le client OAuth, l'application en
    annonçait un autre, et TOUTE connexion échouait.
    """
    # Les commentaires du script CITENT l'ancienne valeur pour expliquer le piège :
    # ne regarder que le code exécuté.
    code = "\n".join(
        l for l in script.splitlines() if not l.lstrip().startswith("#")
    )
    assert '${BACKEND_URL}/auth/callback' not in code, (
        "l'URI de redirection ne doit jamais être recomposé pour l'affichage : "
        "afficher $R_REDIRECT_URI, la valeur réellement déployée"
    )
    assert 'echo "     URI de redirection : $R_REDIRECT_URI"' in script


def test_le_domaine_public_est_valide_avant_tout_deploiement(script: str):
    """Un domaine collé avec son schéma finissait IMPRIMÉ sur les véhicules.

    `PUBLIC_BASE="https://${PUBLIC_DOMAIN}"` utilisait la valeur brute : la forme
    « https://dev.clef.paquerette.com », celle qu'affiche la documentation, donnait
    « https://https://dev.clef… » dans FRONTEND_URL, GOOGLE_REDIRECT_URI et DOMAIN —
    l'hôte encodé dans les QR codes des véhicules, donc irréversible.

    La règle vit dans `deploy/env-commun.sh` et non ici : la même valeur alimente le
    certificat managé (via 00-infra.sh) et les URL de l'application. Deux validations
    auraient fini par diverger — voir `test_deploy_env_example.py`, qui tient le
    partage. Ce test-ci vérifie seulement que ce script s'en sert et refuse.
    """
    assert 'valider_domaine_public "${PUBLIC_DOMAIN:-}"' in script, (
        "le script doit valider PUBLIC_DOMAIN avec la règle partagée"
    )
    assert "exit 2" in script.split('valider_domaine_public "${PUBLIC_DOMAIN:-}"')[1][:200], (
        "une valeur invalide doit ARRÊTER le déploiement, pas l'avertir"
    )


@pytest.mark.parametrize(
    "sonde,raison",
    [
        ("${PUBLIC_BASE}/health", "le service par défaut du LB — le frontend"),
        ("${PUBLIC_BASE}/api/test", "la règle de chemin /api/* — le NEG de l'API"),
        ("http://${PUBLIC_DOMAIN}/form/", "la redirection 301 depuis le clair"),
    ],
)
def test_la_verification_eprouve_le_domaine_public(script: str, sonde: str, raison: str):
    """Sonder l'URL run.app ne dit rien du domaine.

    L'étape de vérification ne sondait que `${BACKEND_URL}/health` — l'URL que
    personne n'utilise dès qu'il y a un domaine. Un certificat encore en
    FAILED_NOT_VISIBLE, un enregistrement A absent ou un NEG visant le mauvais service
    passaient inaperçus, et le script concluait « ✅ Déploiement terminé ».
    """
    assert sonde in script, f"la vérification doit éprouver {sonde} : {raison}"


def test_la_sonde_de_redirection_tolere_le_port_explicite(script: str):
    """GCP renvoie `https://hote:443/chemin`, pas `https://hote/chemin`.

    Valeur réellement observée au premier déploiement du 2026-08-28 :

        Location: https://clef.paquerette.com:443/form/

    La première version de la sonde comparait à l'URL sans port et affichait
    « ❌ http:// redirige, mais pas où il faut » sur une redirection parfaitement
    correcte. Un contrôle qui crie au loup vaut à peine mieux qu'un contrôle absent :
    on apprend à ignorer sa sortie, et le vrai défaut passe avec.
    """
    assert "sed 's|:443/|/|'" in script, (
        "la cible de la redirection doit être normalisée du port explicite avant "
        "comparaison, sinon la sonde échoue sur une redirection correcte"
    )
    assert '[ "$PUB_CODE" = "301" ]' in script, (
        "le code 301 doit rester vérifié séparément de la cible"
    )


def test_le_deploiement_du_backend_est_reessaye(script: str):
    """Le montage du volume GCS échoue par intermittence, et il bloque le démarrage.

    `GetStorageLayout … Unimplemented` : gcsfuse interroge un appel de plan de contrôle
    qui sert à détecter un espace de noms hiérarchique, que ce bucket n'a pas. La
    documentation gcsfuse dit ce contrôle « integral … cannot be skipped » : il n'y a
    aucune option de montage à ajouter.

    Trois échecs constatés le 2026-08-28/29 — un réveil, deux déploiements — pour un
    succès. `minScale = 1` transforme ce défaut en échec de DÉPLOIEMENT : la révision
    n'est prête qu'après un démarrage réussi. Réessayer est la seule réponse disponible
    tant que le montage n'est pas sorti du chemin de démarrage.
    """
    assert "for essai in 1 2 3; do" in script, (
        "`gcloud run services replace` doit être réessayé : un montage GCS raté fait "
        "échouer le déploiement entier, et il échoue une fois sur deux"
    )
    bloc = script[script.index("for essai in 1 2 3; do") :]
    # Jusqu'au comptage des passes : `rm -f` apparaît DANS la branche d'échec, donc
    # avant le `sleep` — s'y arrêter tronquait la boucle.
    bloc = bloc[: bloc.index("R_PASSES=$((R_PASSES + 1))")]
    assert "sleep 20" in bloc, "laisser un délai entre deux tentatives"
    assert "mount operation failed" in bloc, (
        "l'échec définitif doit NOMMER la cause probable et où la vérifier — sinon "
        "trois échecs identiques n'apprennent rien"
    )


def test_le_script_ne_conclut_pas_au_succes_si_le_domaine_ne_repond_pas(script: str):
    """Le message final doit refléter les sondes, sinon elles ne servent à rien."""
    bloc = script[script.index('R_STEP="terminé"') :]
    assert 'if [ "$PUB_FAIL" = true ]; then' in bloc, (
        "le message final doit dépendre du résultat des sondes du domaine public"
    )
