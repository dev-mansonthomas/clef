#!/usr/bin/env python3
"""
Script d'initialisation des Unités Locales (UL) pour DT75.
Charge les 18 UL initiales dans Valkey.
"""
import os
import sys
import json
from datetime import datetime, timezone

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import redis


# Données des 18 UL de DT75
UL_DATA = [
    {"id": "81", "nom": "UL 01-02", "dt": "DT75"},
    {"id": "82", "nom": "UL 03-10", "dt": "DT75"},
    {"id": "83", "nom": "UL 04", "dt": "DT75"},
    {"id": "84", "nom": "UL 05", "dt": "DT75"},
    {"id": "85", "nom": "UL 06", "dt": "DT75"},
    {"id": "86", "nom": "UL 07", "dt": "DT75"},
    {"id": "87", "nom": "UL 08", "dt": "DT75"},
    {"id": "88", "nom": "UL 09", "dt": "DT75"},
    {"id": "89", "nom": "UL 11", "dt": "DT75"},
    {"id": "90", "nom": "UL 12", "dt": "DT75"},
    {"id": "91", "nom": "UL 13", "dt": "DT75"},
    {"id": "92", "nom": "UL 14", "dt": "DT75"},
    {"id": "93", "nom": "UL 15", "dt": "DT75"},
    {"id": "94", "nom": "UL 16", "dt": "DT75"},
    {"id": "95", "nom": "UL 17", "dt": "DT75"},
    {"id": "96", "nom": "UL 18", "dt": "DT75"},
    {"id": "97", "nom": "UL 19", "dt": "DT75"},
    {"id": "98", "nom": "UL 20", "dt": "DT75"},
]


def init_ul_data():
    """Initialize UL data in Valkey."""
    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    print(f"Connecting to Redis at {redis_url}...")
    
    try:
        # Connect to Redis
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        r.ping()
        print("✓ Connected to Redis")
        
        # Add timestamp to each UL
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Initialize each UL
        for ul in UL_DATA:
            ul_with_timestamp = {**ul, "created_at": timestamp}
            
            # Store UL data
            key = f"{ul['dt']}:unite_locale:{ul['id']}"
            r.set(key, json.dumps(ul_with_timestamp, ensure_ascii=False))
            
            # Add to index
            index_key = f"{ul['dt']}:unite_locales:index"
            r.sadd(index_key, ul['id'])
            
            print(f"✓ Initialized {ul['nom']} (ID: {ul['id']})")
        
        print(f"\n✅ Successfully initialized {len(UL_DATA)} Unités Locales for DT75")
        
        # Verify data
        index_key = "DT75:unite_locales:index"
        count = r.scard(index_key)
        print(f"✓ Verification: {count} UL in index")
        
    except redis.ConnectionError as e:
        print(f"❌ Error connecting to Redis: {e}")
        print(f"   Make sure Redis is running at {redis_url}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error initializing UL data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_ul_data()

