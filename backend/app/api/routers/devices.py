"""Inventario de ONUs, detalle, interfaces y etiquetas.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import Depends, APIRouter, HTTPException, Query
from app.services.genieacs import genieacs
from app.services.device_normalizer import NORMALIZE_PROJECTION, normalize_device

from app.api.deps import is_admin, require_user
from app.core.database import get_db
from app.services.audit_service import add_audit
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.config import settings
from app.services import device_refresh


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
                device.get("tr069_ip"),
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
    # connection request: solo admin.
    if raw and not is_admin(user):
        raise HTTPException(status_code=403, detail="Requiere rol admin")

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

    from app.services.wan_driver import certification

    response = {
        "device": normalize_device(device),
        # Modelos no certificados: la interfaz oculta la gestion.
        "certification": certification(device),
        # Si faltan datos o estan viejos, la interfaz pide leerlos a la ONU.
        "data_status": device_refresh.data_status(
            device,
            max_age=settings.refresh_max_age_minutes * 60,
        ),
    }

    if raw:
        response["raw"] = device

    return response


@router.get("/api/devices/{device_id}/hosts")
async def device_hosts(device_id: str):
    """Equipos conectados que GenieACS tiene guardados de la ONU."""

    from app.services.hosts_reader import read_hosts

    try:
        device = await genieacs.get_device(device_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error consultando GenieACS: {exc}")

    if not device:
        raise HTTPException(status_code=404, detail="ONU no encontrada")

    return {"device": normalize_device(device), **read_hosts(device)}


# Lectura de datos bajo demanda (solo lectura en la ONU)

@router.post("/api/devices/{device_id}/refresh")
async def device_refresh_request(device_id: str, force: bool = False):
    """Pide a la ONU las ramas que faltan o estan viejas.

    force=true las vuelve a leer todas aunque esten al dia.
    """

    try:
        device = await genieacs.get_device(device_id)

        if not device:
            raise HTTPException(status_code=404, detail="ONU no encontrada")

        max_age = 0 if force else settings.refresh_max_age_minutes * 60
        result = await device_refresh.request_refresh(device_id, device, max_age=max_age)

    except HTTPException:
        raise

    except Exception as exc:
        # Algunos errores (p. ej. timeouts de httpx) no traen mensaje.
        raise HTTPException(
            status_code=502,
            detail=(
                "No fue posible pedir la lectura a GenieACS: "
                f"{str(exc) or type(exc).__name__}"
            ),
        )

    return result


@router.get("/api/devices/{device_id}/refresh")
async def device_refresh_state(device_id: str):
    """Lecturas pendientes, fallidas y estado de los datos."""

    try:
        state = await device_refresh.refresh_status(device_id)
        device = await genieacs.get_device(device_id)

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible consultar GenieACS: {exc}",
        )

    if not device:
        raise HTTPException(status_code=404, detail="ONU no encontrada")

    state["data_status"] = device_refresh.data_status(
        device,
        max_age=settings.refresh_max_age_minutes * 60,
    )

    return state


# ACS_TAG_WRITE_08C

@router.post("/api/devices/{device_id}/tags/{tag}")
async def add_device_tag(
    device_id: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
):

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

    await add_audit(
        db, action="ETIQUETA_AGREGAR", target_id=device_id,
        after={"etiqueta": tag}, result="CONFIRMADO",
    )

    device = await genieacs.get_device(device_id)

    return {
        "ok": True,
        "action": "tag_added",
        "tag": tag,
        "tags": device.get("_tags") or []
    }


@router.delete("/api/devices/{device_id}/tags/{tag}")
async def delete_device_tag(
    device_id: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
):

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    await genieacs.remove_tag(device_id, tag)

    await add_audit(
        db, action="ETIQUETA_QUITAR", target_id=device_id,
        before={"etiqueta": tag}, result="CONFIRMADO",
    )

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
