#!/usr/bin/env python3
"""
Reconstruit l'index `{dt}:benevoles:by_email` pour les bénévoles déjà en base.

Pourquoi c'est nécessaire
-------------------------
Depuis la tâche N2, l'authentification identifie l'utilisateur en cherchant son email
dans cet index (`RedisService.get_benevole_by_email`). L'index est alimenté par
`set_benevole`, donc par la synchronisation Apps Script — mais les bénévoles écrits
**avant** son introduction n'y figurent pas. Ils seraient alors introuvables, et
silencieusement ramenés à « Bénévole » sans UL ni périmètre : le symptôme exact du
constat M31 que N2 corrige.

À lancer **une fois** après le déploiement, avant que quiconque tente de se connecter.
Idempotent : relancer ne fait que réécrire les mêmes entrées.

Usage:
    python backend/scripts/backfill_benevole_email_index.py [--dt DT75] [--dry-run]
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
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
        # Aucune écriture : on énumère ce qui serait indexé, et surtout ce qui manque.
        nivols = await store.list_benevoles()
        indexable, without_email, already = 0, 0, 0
        for nivol in nivols:
            benevole = await store.get_benevole(nivol)
            if not benevole or not benevole.email:
                without_email += 1
                continue
            indexable += 1
            if await store.get_benevole_by_email(benevole.email):
                already += 1
        logger.info(
            "[dry-run] %s : %d bénévoles, %d indexables (%d déjà indexés), "
            "%d sans email",
            dt, len(nivols), indexable, already, without_email
        )
        logger.info("[dry-run] Aucune écriture effectuée.")
    else:
        counters = await store.backfill_benevole_email_index()
        logger.info(
            "%s : %d parcourus, %d indexés, %d sans email, %d documents manquants",
            dt, counters["total"], counters["indexed"],
            counters["without_email"], counters["missing"]
        )
        if counters["missing"]:
            logger.warning(
                "%d NIVOL présents à l'index mais sans document : incohérence de "
                "données antérieure, à investiguer séparément.",
                counters["missing"]
            )

    await cache.disconnect()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dt", default="DT75", help="Délégation à traiter (défaut : DT75)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="N'écrit rien ; rapporte seulement ce qui serait indexé."
    )
    args = parser.parse_args()
    return asyncio.run(run(args.dt, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
