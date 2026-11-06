"""Inventario de ONUs, detalle, interfaces y etiquetas.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import Depends, APIRouter, HTTPException, Query
from app.services.genieacs import genieacs
from app.services.device_normalizer import NORMALIZE_PROJECTION, normalize_device

from app.api.deps import is_staff, require_user
from app.models.user import User


router = APIRouter()


@router.get("/api/devices")
async def devices(
    limit: int = Query(default=100, ge=1, le=2000),
    q: str | None = Query(default=None),
):

    try:
        raw_devices = await genieacs.get_devices(
            limit=limit,
            projection=NORMALIZE_PROJECTION,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible consultar GenieACS: {exc}",
        )

    normalized = [
        normalize_device(device)
        for device in raw_devices
    ]

    if q:
        search = q.lower().strip()

        def matches(device):
            values = [
                device.get("id"),
                device.get("manufacturer"),
                device.get("product_class"),
                device.get("serial_number"),
                device.get("software_version"),
                device.get("oui"),
            ]

            tags = device.get("tags") or []

            if isinstance(tags, (list, tuple, set)):
                values.extend(tags)
            else:
                values.append(tags)

            return any(
                search in str(value).lower()
                for value in values
                if value is not None
            )

        normalized = [
            device
            for device in normalized
            if matches(device)
        ]

    return {
        "count": len(normalized),
        "devices": normalized,
    }


@router.get("/api/devices/{device_id}")
async def device_detail(
    device_id: str,
    raw: bool = False,
    user: User = Depends(require_user),
):

    # El documento crudo incluye la URL del ACS y las credenciales de
    # connection request: solo staff.
    if raw and not is_staff(user):
        raise HTTPException(status_code=403, detail="Requiere rol staff")

    try:
        device = await genieacs.get_device(device_id)

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error consultando GenieACS: {exc}",
        )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada",
        )

    response = {
        "device": normalize_device(device),
    }

    if raw:
        response["raw"] = device

    return response


# ACS_TAG_WRITE_08C

@router.post("/api/devices/{device_id}/tags/{tag}")
async def add_device_tag(device_id: str, tag: str):

    tag = tag.strip()

    if not tag or len(tag) > 64 or "/" in tag:
        raise HTTPException(
            status_code=400,
            detail="Etiqueta no válida"
        )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    await genieacs.add_tag(device_id, tag)

    device = await genieacs.get_device(device_id)

    return {
        "ok": True,
        "action": "tag_added",
        "tag": tag,
        "tags": device.get("_tags") or []
    }


@router.delete("/api/devices/{device_id}/tags/{tag}")
async def delete_device_tag(device_id: str, tag: str):

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    await genieacs.remove_tag(device_id, tag)

    device = await genieacs.get_device(device_id)

    return {
        "ok": True,
        "action": "tag_removed",
        "tag": tag,
        "tags": device.get("_tags") or []
    }


# ACS_INTERFACE_INVENTORY_12D1
@router.get("/api/devices/{device_id}/interfaces")
async def device_interfaces(device_id: str):

    from app.services.interface_inventory import inventory

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            404,
            "ONU no encontrada"
        )

    interfaces = inventory(device)

    return {
        "count": len(interfaces),
        "interfaces": interfaces
    }
