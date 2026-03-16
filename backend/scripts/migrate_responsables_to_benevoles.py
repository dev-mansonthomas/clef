#!/usr/bin/env python3
"""
Migration script to merge responsables into benevoles with role field.

This script:
1. Connects to Valkey
2. For each DT, migrates DT:responsables:* into DT:benevoles:*
3. Adds role field to benevoles based on responsable data
4. Deletes old responsables keys

Usage:
    python backend/scripts/migrate_responsables_to_benevoles.py [--dt DT75] [--dry-run]
"""
import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.cache import get_cache
from app.services.valkey_service import ValkeyService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_dt(dt: str, dry_run: bool = False):
    """
    Migrate responsables to benevoles for a specific DT.
    
    Args:
        dt: DT identifier (e.g., "DT75")
        dry_run: If True, only show what would be done without making changes
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Starting migration for {dt}")
    
    # Get cache and connect
    cache = get_cache()
    if not cache._connected:
        await cache.connect()
    
    if not cache.client:
        logger.error("Failed to connect to Valkey")
        return
    
    # Create ValkeyService for this DT
    valkey = ValkeyService(redis_client=cache.client, dt=dt)
    
    # Get migration stats
    if dry_run:
        # In dry run, just count what would be migrated
        responsable_emails = await valkey.list_responsables()
        logger.info(f"[DRY RUN] Would migrate {len(responsable_emails)} responsables")
        
        for email in responsable_emails:
            responsable = await valkey.get_responsable(email)
            if responsable:
                logger.info(f"[DRY RUN] Would process: {email} - {responsable.role}")
    else:
        # Perform actual migration
        stats = await valkey.migrate_responsables_to_benevoles()
        
        logger.info(f"Migration completed for {dt}:")
        logger.info(f"  - Responsables found: {stats['responsables_found']}")
        logger.info(f"  - Benevoles updated: {stats['benevoles_updated']}")
        logger.info(f"  - Benevoles created: {stats['benevoles_created']}")
        logger.info(f"  - Responsables deleted: {stats['responsables_deleted']}")
        logger.info(f"  - Errors: {stats['errors']}")
        
        # Verify migration
        remaining = await valkey.list_responsables()
        if remaining:
            logger.warning(f"Warning: {len(remaining)} responsables still remain")
        else:
            logger.info("✓ All responsables successfully migrated")
    
    await cache.disconnect()


async def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(
        description="Migrate responsables to benevoles with role field"
    )
    parser.add_argument(
        "--dt",
        default="DT75",
        help="DT identifier to migrate (default: DT75)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    try:
        await migrate_dt(args.dt, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

