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
