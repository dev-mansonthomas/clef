"""Les URL que le produit fabrique doivent être servies par nginx.

Trois défauts réels, tous constatés au premier déploiement, tous de la même famille :
une URL fabriquée d'un côté, servie — ou pas — de l'autre.

1. **`<base href="/">` alors que les applications vivent sous un sous-chemin.** Le
   navigateur demandait `main-XXX.js`, `styles-XXX.css` et les `chunk-*.js` à la
   RACINE du domaine, où nginx n'a rien : page sans style, une douzaine de 404, et un
   « Refused to apply style ... MIME type ('text/html') » parce que le repli renvoie
   du HTML là où le navigateur attend du CSS.

2. **`https://{DOMAIN}/vehicle/{id}`**, encodé dans les QR codes **collés sur les
   véhicules**, donnait un 404 : la page vit sous `/form/vehicle/{id}`.

3. **`{FRONTEND_URL}/approbation/{token}`**, envoyé par courriel aux **garages**,
   donnait un 404 : la page vit sous `/admin/approbation/{token}`.

Les deux derniers sortent du produit — un QR code imprimé et un courriel envoyé ne se
corrigent pas par un redéploiement. D'où des redirections dans nginx plutôt qu'un
allongement des URL.

Le dernier test cherche **de nouvelles occurrences** au lieu de se contenter de la
liste connue : c'est lui qui compte.
"""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
DOCKERFILE = RACINE / "frontend" / "Dockerfile"
NGINX = RACINE / "frontend" / "clef.conf.template"

# Préfixe sous lequel chaque application est servie.
APPS = {"admin": "/admin/", "form": "/form/"}


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def nginx() -> str:
    return NGINX.read_text(encoding="utf-8")


@pytest.mark.parametrize("app,prefixe", sorted(APPS.items()))
def test_chaque_application_est_construite_avec_sa_base(dockerfile: str, app: str, prefixe: str):
    """Sans `--base-href`, aucune ressource n'est trouvée."""
    attendu = f"ng build {app}"
    ligne = next(
        (l for l in dockerfile.splitlines() if attendu in l and "--configuration" in l), None
    )
    assert ligne, f"aucune construction de production pour « {app} »"
    assert f"--base-href={prefixe}" in ligne, (
        f"« {app} » est servie sous {prefixe} mais construite sans `--base-href`. "
        "index.html garderait la base racine, et le navigateur chercherait "
        "main-*.js, styles-*.css et les chunks à la racine du domaine."
    )


def test_les_redirections_sont_relatives(nginx: str):
    """`absolute_redirect off` — sinon nginx redirige vers http:// derrière Cloud Run.

    nginx fabrique par défaut un `Location:` absolu depuis son propre hôte et son port
    d'écoute (80). Le client, lui, parle HTTPS à Cloud Run : la redirection partait
    donc en clair, avec un aller-retour de plus.
    """
    assert re.search(r"^\s*absolute_redirect\s+off\s*;", nginx, re.M), (
        "sans `absolute_redirect off`, /admin redirige vers http:// et non https://"
    )


def test_le_proxy_couvre_les_deux_prefixes_du_backend(nginx: str):
    """`/api` ET `/auth` : le second porte tout le parcours OAuth."""
    assert re.search(r"location\s+~\s+\^/\(api\|auth\)/", nginx), (
        "le relais doit couvrir /api et /auth"
    )


# Chemins fabriqués hors du frontend, avec l'application qui les héberge réellement.
# Toute nouvelle entrée trouvée par le test suivant doit être ajoutée ici ET redirigée.
URLS_DU_PRODUIT = {
    "vehicle": "form",        # QR codes collés sur les véhicules
    "approbation": "admin",   # courriels aux garages
}


@pytest.mark.parametrize("chemin,app", sorted(URLS_DU_PRODUIT.items()))
def test_les_url_du_produit_sont_redirigees(nginx: str, chemin: str, app: str):
    """Chaque URL courte doit mener à la page, sous le préfixe de son application."""
    motif = re.compile(
        rf"location\s+~\s+\^/{chemin}/\(\.\*\)\$\s*\{{\s*return\s+301\s+/{app}/{chemin}/\$1\s*;",
        re.S,
    )
    assert motif.search(nginx), (
        f"/{chemin}/… n'est pas redirigé vers /{app}/{chemin}/…. "
        f"Ces URL sont émises hors du frontend et ne peuvent plus être changées "
        f"une fois imprimées ou envoyées."
    )


def test_la_page_d_accueil_est_un_fichier_et_mene_aux_deux_applications(dockerfile: str):
    """La racine du domaine est une surface produit, pas un provisoire.

    `clef.<domaine>` sert cette page et l'utilisateur y choisit son application. Elle
    était produite par un `RUN echo` dans le Dockerfile : deux liens sans style, pris
    pour un défaut de CSS alors que c'était l'absence de page.

    Elle est volontairement autonome — aucune ressource externe, aucun build — pour
    s'afficher même si les deux applications Angular sont en panne.
    """
    assert "COPY landing.html /usr/share/nginx/html/index.html" in dockerfile, (
        "la page d'accueil doit être un fichier versionné, pas un `RUN echo`"
    )
    page = (RACINE / "frontend" / "landing.html").read_text(encoding="utf-8")

    for prefixe in APPS.values():
        assert f'href="{prefixe}"' in page, (
            f"la page d'accueil ne mène pas à {prefixe}. Et la barre oblique finale "
            "compte : sans elle, chaque visite subit une redirection 301."
        )

    assert 'lang="fr"' in page, "la langue doit être déclarée (lecteurs d'écran)"
    assert "aria-label" in page, "la navigation et le logo doivent être étiquetés"
    assert "http://" not in page.replace("http://www.w3.org", ""), (
        "aucune ressource externe : la page doit tenir seule"
    )


def test_aucune_url_de_produit_non_couverte():
    """Cherche de NOUVELLES occurrences, au lieu de se fier à la liste connue.

    C'est le test qui a de la valeur : il relit le backend à chaque exécution et
    échoue si quelqu'un fabrique une URL de frontend dont nginx ne sait rien. Les
    trois défauts d'origine ont été trouvés à la main, un par un, après déploiement.
    """
    app_dir = RACINE / "backend" / "app"
    # Formes réelles : f"{frontend_url}/xxx/{...}" et f"https://{domain}/xxx/{...}"
    motifs = [
        re.compile(r'f"\{frontend_url\}/([a-z][a-z0-9_-]*)/'),
        re.compile(r'f"https://\{domain\}/([a-z][a-z0-9_-]*)/'),
        re.compile(r'f"\{FRONTEND_URL\}/([a-z][a-z0-9_-]*)/'),
    ]
    trouves: dict[str, str] = {}
    for f in app_dir.rglob("*.py"):
        texte = f.read_text(encoding="utf-8")
        for m in motifs:
            for chemin in m.findall(texte):
                trouves[chemin] = f.relative_to(RACINE).as_posix()

    inconnus = {c: src for c, src in trouves.items() if c not in URLS_DU_PRODUIT}
    assert not inconnus, (
        "URL de frontend fabriquées par le backend et non couvertes par nginx :\n"
        + "\n".join(f"  /{c}/…  ({src})" for c, src in sorted(inconnus.items()))
        + "\n\nAjouter le chemin à URLS_DU_PRODUIT ci-dessus ET une redirection dans "
        "frontend/clef.conf.template. Sinon l'URL donne un 404 — et si elle est "
        "imprimée sur un QR code ou envoyée par courriel, elle n'est plus corrigeable."
    )
    # Garde-fou du garde-fou : si les motifs ne trouvent plus rien, le test ne teste
    # plus rien. Les deux occurrences connues doivent rester détectées.
    assert set(trouves) >= set(URLS_DU_PRODUIT), (
        f"les motifs de détection ne trouvent plus les URL connues : {sorted(trouves)}. "
        "Le code a probablement changé de forme — mettre les motifs à jour, sinon ce "
        "test devient une coquille vide."
    )
