"""Sonde de routage publique — et rien d'autre.

`GET /api/test` était déclarée EN LIGNE dans `main.py`. Or ce fichier ne porte aucun
`Depends` : toute route qui y est déclarée est publique par construction — c'est la
famille du constat C1, qui avait rendu l'annuaire des bénévoles anonymement lisible.
Celle-ci renvoyait `environment` et `using_mocks`, désormais publiés sur le domaine
public de la Croix-Rouge par le load balancer : un appelant anonyme apprenait le nom
de l'environnement et si les services Google étaient simulés.

La route reste **publique** et reste **à `/api/test`**, délibérément : les critères
d'acceptation de `docs/specs/domaine-personnalise-alb.md` s'en servent comme sonde de
la règle de chemin `/api/*` du load balancer, et `01-gcp-deploy.sh` la sonde après
chaque déploiement. Une sonde qui exigerait une session ne vérifierait plus le
routage. Seule la charge utile change : elle ne dit plus que « l'API répond ».

Le diagnostic a déménagé derrière le guard super-admin, en `GET
/admin/super/environnement`.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["probe"])


@router.get("/test")
async def probe_routage() -> dict[str, str]:
    """Sonde de routage : l'API répond, et rien de plus n'est divulgué.

    Aucune information d'environnement ici. Ce que ce point d'entrée prouve, et qui
    suffit, c'est que la requête a bien atteint `clef-api` et pas le frontend.
    """
    return {"service": "clef-api", "status": "ok"}
