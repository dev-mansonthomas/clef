#!/usr/bin/env python3
"""
Migre le champ `role` des bénévoles vers `responsable_ul` + `fonctions_dt`.

⚠️ **À LANCER AVANT LE DÉPLOIEMENT du code qui lit les nouveaux champs.**

Le nouveau modèle sépare l'identité (propriété de la feuille « CLEF Benevoles ») de
l'organisation (propriété de CLEF). Sur un document non migré, Pydantic donne
`responsable_ul=False` et `fonctions_dt=[]` : **tous les responsables perdraient leurs
droits** jusqu'au passage de cette migration. L'ordre compte.

Correspondance :

    role == "responsable_ul"  →  responsable_ul = True
    role == "responsable_dt"  →  fonctions_dt   = ["Gestionnaire DT"]
    role absent ou null       →  ni l'un ni l'autre

La migration reconstruit aussi l'index `by_email`, absent des documents hérités et
sans lequel l'authentification ne retrouve pas le bénévole.

Idempotent : un document déjà migré est laissé intact, organisation comprise.

Usage:
    python backend/scripts/migrate_benevole_role_to_organisation.py [--dt DT75] [--dry-run]
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.cache import get_cache  # noqa: E402
from app.services.redis_service import RedisService  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run(dt: str, dry_run: bool) -> int:
    cache = get_cache()
    await cache.connect()
    if not cache.client:
        logger.error("Client Redis indisponible — vérifier REDIS_URL")
        return 1

    store = RedisService(redis_client=cache.client, dt=dt)

    if dry_run:
        # Aucune écriture : on inventorie ce qui serait fait, sans rien toucher.
        nivols = await store.list_benevoles()
        to_migrate = {"responsable_ul": 0, "responsable_dt": 0, "sans_role": 0}
        already, without_ul, missing = 0, 0, 0

        for nivol in nivols:
            raw = await store.redis.json().get(store._key("benevoles", nivol))
            if not raw:
                missing += 1
                continue
            if not raw.get("ul"):
                without_ul += 1
            if "role" not in raw:
                already += 1
                continue
            role = raw.get("role")
            if role == "responsable_ul":
                to_migrate["responsable_ul"] += 1
            elif role == "responsable_dt":
                to_migrate["responsable_dt"] += 1
            else:
                to_migrate["sans_role"] += 1

        logger.info(
            "[dry-run] %s : %d bénévoles — à migrer : %d responsable_ul, "
            "%d responsable_dt, %d sans rôle ; %d déjà migrés",
            dt, len(nivols), to_migrate["responsable_ul"],
            to_migrate["responsable_dt"], to_migrate["sans_role"], already
        )
        if without_ul:
            logger.warning(
                "[dry-run] %d bénévole(s) sans UL : à corriger dans la feuille source, "
                "la migration ne les inventera pas", without_ul
            )
        if missing:
            logger.warning(
                "[dry-run] %d NIVOL à l'index sans document : incohérence antérieure",
                missing
            )
        logger.info("[dry-run] Aucune écriture effectuée.")
    else:
        counters = await store.migrate_benevole_role_to_organisation()
        logger.info(
            "%s : %d parcourus, %d migrés, %d déjà migrés, %d sans UL, "
            "%d documents manquants",
            dt, counters["total"], counters["migrated"],
            counters["already_migrated"], counters["without_ul"], counters["missing"]
        )
        if counters["without_ul"]:
            logger.warning(
                "%d bénévole(s) sans UL. La règle « un bénévole a toujours une UL » "
                "est imposée à la synchronisation : ces lignes seront refusées tant "
                "que la feuille n'est pas corrigée.", counters["without_ul"]
            )

    await cache.disconnect()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dt", default="DT75", help="Délégation à traiter (défaut : DT75)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="N'écrit rien ; inventorie ce qui serait migré."
    )
    args = parser.parse_args()
    return asyncio.run(run(args.dt, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
