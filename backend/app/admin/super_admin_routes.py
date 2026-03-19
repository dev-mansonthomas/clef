"""Super admin backend routes."""
from fastapi import APIRouter, Depends

from app.auth.dependencies import require_authenticated_user, require_super_admin, user_is_super_admin
from app.auth.models import User
from app.services.valkey_dependencies import get_valkey_service
from app.services.valkey_service import ValkeyService


router = APIRouter(prefix="/admin/super", tags=["super-admin"])


def _extract_vehicle_folder_summary(vehicle) -> dict | None:
    drive_folders = getattr(vehicle, "drive_folders", {}) or {}
    vehicle_folder = drive_folders.get("vehicle_folder") or {}
    folder_id = vehicle_folder.get("folder_id")
    if not folder_id:
        return None

    return {
        "immat": vehicle.immat,
        "nom_synthetique": vehicle.nom_synthetique,
        "drive_folder_id": folder_id,
        "drive_folder_url": vehicle_folder.get("folder_url"),
    }


@router.get("/status")
async def get_super_admin_status(current_user: User = Depends(require_authenticated_user)):
    """Return whether the authenticated user is the configured super admin."""
    return {"is_super_admin": user_is_super_admin(current_user)}


@router.get("/cache/drive-folders")
async def get_drive_cache(
    current_user: User = Depends(require_super_admin),
    valkey: ValkeyService = Depends(get_valkey_service),
):
    """List cached Google Drive folders for the current DT."""
    _ = current_user
    config = await valkey.get_configuration()

    ul_ids = sorted(await valkey.redis.smembers(f"{valkey.dt}:unite_locales:index"))
    uls = []
    for ul_id in ul_ids:
        ul_data = await valkey.redis.json().get(f"{valkey.dt}:unite_locale:{ul_id}")
        if ul_data and ul_data.get("drive_folder_id"):
            uls.append({
                "id": ul_id,
                "nom": ul_data.get("nom"),
                "drive_folder_id": ul_data.get("drive_folder_id"),
                "drive_folder_url": ul_data.get("drive_folder_url"),
            })

    vehicles_with_folders = []
    for immat in sorted(await valkey.list_vehicles()):
        vehicle = await valkey.get_vehicle(immat)
        if not vehicle:
            continue
        summary = _extract_vehicle_folder_summary(vehicle)
        if summary:
            vehicles_with_folders.append(summary)

    return {
        "dt_config": {
            "drive_folder_id": config.drive_folder_id if config else None,
            "drive_folder_url": config.drive_folder_url if config else None,
            "drive_vehicles_folder_id": config.drive_vehicles_folder_id if config else None,
            "drive_vehicles_folder_url": config.drive_vehicles_folder_url if config else None,
            "drive_dt_folder_id": config.drive_dt_folder_id if config else None,
            "drive_dt_folder_url": config.drive_dt_folder_url if config else None,
        },
        "unites_locales": uls,
        "vehicles_count": len(vehicles_with_folders),
        "vehicles": vehicles_with_folders[:10],
    }


@router.delete("/cache/drive-folders")
async def clear_drive_cache(
    current_user: User = Depends(require_super_admin),
    valkey: ValkeyService = Depends(get_valkey_service),
):
    """Clear cached Google Drive folders for DT config, ULs, and vehicles."""
    _ = current_user
    cleared = {"dt_config": False, "unites_locales": 0, "vehicles": 0}

    config = await valkey.get_configuration()
    if config:
        had_dt_cache = any([
            config.drive_folder_id,
            config.drive_folder_url,
            config.drive_vehicles_folder_id,
            config.drive_vehicles_folder_url,
            config.drive_dt_folder_id,
            config.drive_dt_folder_url,
        ])
        if had_dt_cache:
            config.drive_folder_id = None
            config.drive_folder_url = None
            config.drive_vehicles_folder_id = None
            config.drive_vehicles_folder_url = None
            config.drive_dt_folder_id = None
            config.drive_dt_folder_url = None
            await valkey.set_configuration(config)
            cleared["dt_config"] = True

    ul_ids = await valkey.redis.smembers(f"{valkey.dt}:unite_locales:index")
    for ul_id in ul_ids:
        ul_key = f"{valkey.dt}:unite_locale:{ul_id}"
        ul_data = await valkey.redis.json().get(ul_key)
        if not ul_data:
            continue
        if ul_data.get("drive_folder_id") or ul_data.get("drive_folder_url"):
            updated_ul = dict(ul_data)
            updated_ul["drive_folder_id"] = None
            updated_ul["drive_folder_url"] = None
            await valkey.redis.json().set(ul_key, "$", updated_ul)
            cleared["unites_locales"] += 1

    for immat in await valkey.list_vehicles():
        vehicle = await valkey.get_vehicle(immat)
        if not vehicle or not getattr(vehicle, "drive_folders", {}):
            continue
        vehicle.drive_folders = {}
        await valkey.set_vehicle(vehicle)
        cleared["vehicles"] += 1

    return {
        "success": True,
        "cleared": cleared,
        "message": (
            f"Cache vidé: config DT, {cleared['unites_locales']} ULs, "
            f"{cleared['vehicles']} véhicules"
        ),
    }