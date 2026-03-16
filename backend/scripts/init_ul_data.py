#!/usr/bin/env python3
"""
Script d'initialisation des Unités Locales (UL) et Délégations Territoriales (DT).
Charge les données de base dans Valkey au démarrage de l'application.
"""
import os
import sys
import json
from datetime import datetime, timezone

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import redis


# Données des UL de Paris (DT75)
UL_PARIS_DATA = [
    {"id": "889", "nom": "UNITE LOCALE DE PARIS 1ER ET 2EME", "dt": "DT75"},
    {"id": "892", "nom": "UNITE LOCALE DE PARIS IV", "dt": "DT75"},
    {"id": "893", "nom": "UNITE LOCALE DE PARIS V", "dt": "DT75"},
    {"id": "894", "nom": "UNITE LOCALE DE PARIS VI", "dt": "DT75"},
    {"id": "895", "nom": "UNITE LOCALE DE PARIS VII", "dt": "DT75"},
    {"id": "896", "nom": "UNITE LOCALE DE PARIS VIII", "dt": "DT75"},
    {"id": "897", "nom": "UNITE LOCALE DE PARIS IX", "dt": "DT75"},
    {"id": "898", "nom": "UNITE LOCALE DE PARIS X", "dt": "DT75"},
    {"id": "899", "nom": "UNITE LOCALE DE PARIS XI", "dt": "DT75"},
    {"id": "900", "nom": "UNITE LOCALE DE PARIS XII", "dt": "DT75"},
    {"id": "901", "nom": "UNITE LOCALE DE PARIS XIII", "dt": "DT75"},
    {"id": "902", "nom": "UNITE LOCALE DE PARIS XIV", "dt": "DT75"},
    {"id": "903", "nom": "UNITE LOCALE DE PARIS XV", "dt": "DT75"},
    {"id": "904", "nom": "UNITE LOCALE DE PARIS XVI", "dt": "DT75"},
    {"id": "905", "nom": "UNITE LOCALE DE PARIS XVII", "dt": "DT75"},
    {"id": "906", "nom": "UNITE LOCALE DE PARIS XVIII", "dt": "DT75"},
    {"id": "907", "nom": "UNITE LOCALE DE PARIS XIX", "dt": "DT75"},
    {"id": "908", "nom": "UNITE LOCALE DE PARIS XX", "dt": "DT75"},
]

# Données de toutes les DT de France
DT_DATA = [
    {"id": "5", "nom": "DT DE L'AIN"},
    {"id": "6", "nom": "DT DE L'AISNE"},
    {"id": "7", "nom": "DT DE L'ALLIER"},
    {"id": "9", "nom": "DT DES HAUTES ALPES"},
    {"id": "10", "nom": "DT DES ALPES MARITIMES"},
    {"id": "11", "nom": "DT DE L'ARDECHE"},
    {"id": "12", "nom": "DT DES ARDENNES"},
    {"id": "13", "nom": "DT DE L'ARIEGE"},
    {"id": "14", "nom": "DT DE L'AUBE"},
    {"id": "15", "nom": "DT DE L'AUDE"},
    {"id": "17", "nom": "DT DES BOUCHES DU RHONE"},
    {"id": "18", "nom": "DT DU CALVADOS"},
    {"id": "19", "nom": "DT DU CANTAL"},
    {"id": "20", "nom": "DT DE LA CHARENTE"},
    {"id": "21", "nom": "DT DE CHARENTE MARITIME"},
    {"id": "23", "nom": "DT DE LA CORREZE"},
    {"id": "26", "nom": "DT DE LA COTE D'OR"},
    {"id": "30", "nom": "DT DU DOUBS"},
    {"id": "31", "nom": "DT DE LA DROME"},
    {"id": "32", "nom": "DT DE L'EURE"},
    {"id": "33", "nom": "DT D'EURE ET LOIR"},
    {"id": "34", "nom": "DT DU FINISTERE"},
    {"id": "35", "nom": "DT DU GARD"},
    {"id": "36", "nom": "DT DE HAUTE GARONNE"},
    {"id": "37", "nom": "DT DU GERS"},
    {"id": "38", "nom": "DT DE LA GIRONDE"},
    {"id": "39", "nom": "DT DE L'HERAULT"},
    {"id": "40", "nom": "DT DE L'ILLE ET VILAINE"},
    {"id": "41", "nom": "DT DE L'INDRE"},
    {"id": "42", "nom": "DT D'INDRE ET LOIRE"},
    {"id": "43", "nom": "DT DE L'ISERE"},
    {"id": "44", "nom": "DT DU JURA"},
    {"id": "45", "nom": "DT DES LANDES"},
    {"id": "46", "nom": "DT DU LOIR ET CHER"},
    {"id": "47", "nom": "DT DE LA LOIRE"},
    {"id": "48", "nom": "DT DE LA HAUTE LOIRE"},
    {"id": "49", "nom": "DT DE LA LOIRE ATLANTIQUE"},
    {"id": "50", "nom": "DT DU LOIRET"},
    {"id": "52", "nom": "DT DU LOT ET GARONNE"},
    {"id": "53", "nom": "DT DE LA LOZERE"},
    {"id": "54", "nom": "DT DU MAINE ET LOIRE"},
    {"id": "55", "nom": "DT DE LA MANCHE"},
    {"id": "56", "nom": "DT DE LA MARNE"},
    {"id": "57", "nom": "DT DE LA HAUTE MARNE"},
    {"id": "58", "nom": "DT DE LA MAYENNE"},
    {"id": "59", "nom": "DT DE MEURTHE ET MOSELLE"},
    {"id": "61", "nom": "DT DU MORBIHAN"},
    {"id": "62", "nom": "DT DE LA MOSELLE"},
    {"id": "63", "nom": "DT DE LA NIEVRE"},
    {"id": "64", "nom": "DT DU NORD"},
    {"id": "67", "nom": "DT DU PAS DE CALAIS"},
    {"id": "68", "nom": "DT DU PUY DE DOME"},
    {"id": "69", "nom": "DT DES PYRENEES ATLANTIQUES"},
    {"id": "71", "nom": "DT DES PYRENEES ORIENTALES"},
    {"id": "72", "nom": "DT DU BAS RHIN"},
    {"id": "73", "nom": "DT DU HAUT RHIN"},
    {"id": "74", "nom": "DT DU RHONE"},
    {"id": "76", "nom": "DT DE SAONE ET LOIRE"},
    {"id": "77", "nom": "DT DE LA SARTHE"},
    {"id": "79", "nom": "DT DE LA HAUTE SAVOIE"},
    {"id": "80", "nom": "DT DE PARIS"},
    {"id": "81", "nom": "DT DE LA SEINE MARITIME"},
    {"id": "82", "nom": "DT DE LA SEINE ET MARNE"},
    {"id": "83", "nom": "DT DES YVELINES"},
    {"id": "85", "nom": "DT DE LA SOMME"},
    {"id": "86", "nom": "DT DU TARN"},
    {"id": "87", "nom": "DT DU TARN ET GARONNE"},
    {"id": "89", "nom": "DT DU VAUCLUSE"},
    {"id": "90", "nom": "DT DE VENDEE"},
    {"id": "91", "nom": "DT DE LA VIENNE"},
    {"id": "92", "nom": "DT DE LA HAUTE VIENNE"},
    {"id": "94", "nom": "DT DE L'YONNE"},
    {"id": "95", "nom": "DT DU TERRITOIRE DE BELFORT"},
    {"id": "96", "nom": "DT DE L'ESSONNE"},
    {"id": "97", "nom": "DT DES HAUTS DE SEINE"},
    {"id": "99", "nom": "DT DU VAL DE MARNE"},
    {"id": "100", "nom": "DT DU VAL D'OISE"},
    {"id": "102", "nom": "DT DE LA GUADELOUPE"},
    {"id": "103", "nom": "DT DE LA MARTINIQUE"},
    {"id": "104", "nom": "DT DE NOUVELLE CALEDONIE"},
    {"id": "1285", "nom": "DT DE TAHITI"},
    {"id": "1286", "nom": "DT DE MAYOTTE"},
    {"id": "2570", "nom": "DT DE LA GUYANE"},
    {"id": "2571", "nom": "DT DE SAINT PIERRE ET MIQUELON"},
    {"id": "3667", "nom": "DT DE ST BARTHELEMY"},
    {"id": "3668", "nom": "DT DE ST MARTIN"},
    {"id": "3884", "nom": "DT DE FUTUNA"},
    {"id": "3959", "nom": "DT DE LA REUNION"},
    {"id": "3965", "nom": "DT DE LA CORSE DU SUD"},
    {"id": "3966", "nom": "DT DES VOSGES"},
    {"id": "3967", "nom": "DT DE LA HAUTE CORSE"},
    {"id": "3968", "nom": "DT DE LA DORDOGNE"},
    {"id": "3969", "nom": "DT DES HAUTES PYRENEES"},
    {"id": "3970", "nom": "DT DU CHER"},
    {"id": "3971", "nom": "DT DES COTES D'ARMOR"},
    {"id": "3986", "nom": "DT DE LA SAVOIE"},
    {"id": "3997", "nom": "DT DES ALPES DE HAUTE PROVENCE"},
    {"id": "4017", "nom": "DT DU VAR"},
    {"id": "4284", "nom": "DT DE L'ORNE"},
    {"id": "4303", "nom": "DT DE WALLIS"},
    {"id": "4381", "nom": "DT DES DEUX SEVRES"},
    {"id": "4394", "nom": "DT DE HAUTE SAONE"},
    {"id": "4395", "nom": "DT DE L'AVEYRON"},
    {"id": "4396", "nom": "DT DE L'OISE"},
    {"id": "4631", "nom": "DT DE SEINE SAINT DENIS"},
    {"id": "4649", "nom": "DT DE LA MEUSE"},
    {"id": "4662", "nom": "DT DE LA CREUSE"},
    {"id": "4674", "nom": "DT DU LOT"},
]


def init_data():
    """Initialize DT and UL data in Valkey if not already present."""
    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    print(f"Connecting to Redis at {redis_url}...")

    try:
        # Connect to Redis
        r = redis.from_url(redis_url, decode_responses=True)

        # Test connection
        r.ping()
        print("✓ Connected to Redis")

        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # ========== Initialize DTs ==========
        dt_key = "clef:dts"

        # Check if DTs already exist
        try:
            existing_dts = r.json().get(dt_key)
        except:
            existing_dts = None

        if existing_dts:
            print(f"ℹ️  DTs already initialized ({len(existing_dts)} DTs found), skipping...")
        else:
            # Store all DTs as a JSON array
            r.json().set(dt_key, "$", DT_DATA)
            print(f"✅ Initialized {len(DT_DATA)} Délégations Territoriales")

        # ========== Initialize ULs for DT75 ==========
        index_key = "DT75:unite_locales:index"
        existing_ul_count = r.scard(index_key)

        if existing_ul_count > 0:
            print(f"ℹ️  ULs for DT75 already initialized ({existing_ul_count} ULs found), skipping...")
        else:
            # Initialize each UL for Paris
            for ul in UL_PARIS_DATA:
                ul_with_timestamp = {**ul, "created_at": timestamp}

                # Store UL data using JSON native storage
                key = f"{ul['dt']}:unite_locale:{ul['id']}"
                r.json().set(key, "$", ul_with_timestamp)

                # Add to index
                r.sadd(index_key, ul['id'])

                print(f"✓ Initialized {ul['nom']} (ID: {ul['id']})")

            print(f"✅ Successfully initialized {len(UL_PARIS_DATA)} Unités Locales for DT75")

        # Verify data
        final_ul_count = r.scard(index_key)
        print(f"\n✓ Verification: {final_ul_count} UL in DT75 index")

        try:
            final_dts = r.json().get(dt_key)
            if final_dts:
                print(f"✓ Verification: {len(final_dts)} DTs in global list")
        except:
            pass

    except redis.ConnectionError as e:
        print(f"❌ Error connecting to Redis: {e}")
        print(f"   Make sure Redis is running at {redis_url}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error initializing data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def init_data_async(redis_client):
    """
    Async version for use in FastAPI startup.

    Args:
        redis_client: Async Redis client instance
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # ========== Initialize DTs ==========
        dt_key = "clef:dts"

        # Check if DTs already exist
        try:
            existing_dts = await redis_client.json().get(dt_key)
        except:
            existing_dts = None

        if existing_dts:
            logger.info(f"DTs already initialized ({len(existing_dts)} DTs found), skipping...")
        else:
            # Store all DTs as a JSON array
            await redis_client.json().set(dt_key, "$", DT_DATA)
            logger.info(f"Initialized {len(DT_DATA)} Délégations Territoriales")

        # ========== Initialize ULs for DT75 ==========
        index_key = "DT75:unite_locales:index"
        existing_ul_count = await redis_client.scard(index_key)

        if existing_ul_count > 0:
            logger.info(f"ULs for DT75 already initialized ({existing_ul_count} ULs found), skipping...")
        else:
            # Initialize each UL for Paris
            for ul in UL_PARIS_DATA:
                ul_with_timestamp = {**ul, "created_at": timestamp}

                # Store UL data using JSON native storage
                key = f"{ul['dt']}:unite_locale:{ul['id']}"
                await redis_client.json().set(key, "$", ul_with_timestamp)

                # Add to index
                await redis_client.sadd(index_key, ul['id'])

            logger.info(f"Initialized {len(UL_PARIS_DATA)} Unités Locales for DT75")

        # Verify data
        final_ul_count = await redis_client.scard(index_key)
        logger.info(f"Verification: {final_ul_count} UL in DT75 index")

        try:
            final_dts = await redis_client.json().get(dt_key)
            if final_dts:
                logger.info(f"Verification: {len(final_dts)} DTs in global list")
        except:
            pass

    except Exception as e:
        logger.error(f"Error initializing data: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    init_data()

