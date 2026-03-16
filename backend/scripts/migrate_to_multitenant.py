#!/usr/bin/env python3
"""
Migration script to convert existing Valkey data to multi-tenant structure.

This script:
1. Scans for existing keys without DT prefix
2. Migrates them to DT-prefixed keys
3. Preserves all data and indices
4. Can be run multiple times safely (idempotent)

Usage:
    python scripts/migrate_to_multitenant.py --dt DT75 [--dry-run]
"""
import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from redis.asyncio import Redis
from app.cache.redis_cache import RedisCache
from app.services.valkey_service import ValkeyService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_keys(redis_client: Redis, dt: str, dry_run: bool = False):
    """
    Migrate existing keys to multi-tenant structure.
    
    Args:
        redis_client: Redis client
        dt: DT identifier (e.g., "DT75")
        dry_run: If True, only show what would be migrated
    """
    logger.info(f"Starting migration to DT: {dt} (dry_run={dry_run})")
    
    # Patterns to migrate
    patterns = [
        "vehicules:*",
        "benevoles:*",
        "carnet:*",
        "configuration"
    ]
    
    migrated_count = 0
    skipped_count = 0
    
    for pattern in patterns:
        logger.info(f"Scanning pattern: {pattern}")
        
        # Find all keys matching pattern
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            
            for key in keys:
                # Skip if already has DT prefix
                if key.startswith(f"{dt}:"):
                    skipped_count += 1
                    continue
                
                # Build new key with DT prefix
                new_key = f"{dt}:{key}"
                
                if dry_run:
                    logger.info(f"Would migrate: {key} -> {new_key}")
                else:
                    # Get key type
                    key_type = await redis_client.type(key)
                    
                    if key_type == "string":
                        # Copy string value
                        value = await redis_client.get(key)
                        ttl = await redis_client.ttl(key)
                        await redis_client.set(new_key, value)
                        if ttl > 0:
                            await redis_client.expire(new_key, ttl)
                        logger.info(f"Migrated string: {key} -> {new_key}")
                    
                    elif key_type == "set":
                        # Copy set members
                        members = await redis_client.smembers(key)
                        if members:
                            await redis_client.sadd(new_key, *members)
                        logger.info(f"Migrated set: {key} -> {new_key} ({len(members)} members)")
                    
                    elif key_type == "hash":
                        # Copy hash fields
                        hash_data = await redis_client.hgetall(key)
                        if hash_data:
                            await redis_client.hset(new_key, mapping=hash_data)
                        logger.info(f"Migrated hash: {key} -> {new_key}")
                    
                    else:
                        logger.warning(f"Unsupported key type {key_type} for key: {key}")
                        continue
                    
                    migrated_count += 1
            
            if cursor == 0:
                break
    
    logger.info(f"Migration complete: {migrated_count} keys migrated, {skipped_count} keys skipped")
    
    if not dry_run:
        logger.info("Note: Old keys were NOT deleted. Review and delete manually if needed.")


async def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate Valkey data to multi-tenant structure")
    parser.add_argument("--dt", required=True, help="DT identifier (e.g., DT75)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without making changes")
    parser.add_argument("--redis-url", help="Redis URL (default: from REDIS_URL env var)")
    
    args = parser.parse_args()
    
    # Get Redis connection
    redis_url = args.redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    logger.info(f"Connecting to Redis: {redis_url}")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    
    try:
        # Test connection
        await redis_client.ping()
        logger.info("Connected to Redis successfully")
        
        # Run migration
        await migrate_keys(redis_client, args.dt, args.dry_run)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

