"""Lectura y edicion de redes Wi-Fi.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.genieacs import genieacs
from app.services.device_normalizer import normalize_device


router = APIRouter()


# ACS_WIFI_ENDPOINT
@router.get("/api/devices/{device_id}/wifi")
async def device_wifi(device_id: str):
    from app.services.wifi_reader import read_wifi

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="ONU no encontrada")

    return {
        "device": normalize_device(device),
        "wifi": read_wifi(device),
        "mode": "read-only"
    }


# ACS_WLAN_INVENTORY_11C
@router.get("/api/devices/{device_id}/wlan-interfaces")
async def wlan_interfaces(device_id: str):

    from app.services.wlan_inventory import read_wlan_interfaces

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    interfaces = read_wlan_interfaces(device)

    return {
        "count": len(interfaces),
        "interfaces": interfaces,
        "mode": "read-only"
    }


# ACS_WIFI_CAPABILITIES_15A
@router.get("/api/devices/{device_id}/wifi-capabilities")
async def device_wifi_capabilities(device_id: str):

    from app.services.wifi_capabilities import wifi_capabilities

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            404,
            "ONU no encontrada"
        )

    return {
        "interfaces":
            wifi_capabilities(device)
    }


# ACS_WIFI_WRITE_15B1
@router.patch("/api/devices/{device_id}/wifi/{index}")
async def edit_wifi(
    device_id: str,
    index: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wifi_writer import (
        build_wifi_changes,
        wifi_state,
    )

    from app.services.audit_service import (
        add_audit,
        update_audit,
    )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    before = wifi_state(device, index)

    if not before:
        raise HTTPException(
            404,
            "Interfaz Wi-Fi no encontrada"
        )

    try:
        values, requested = build_wifi_changes(
            device,
            index,
            payload
        )

    except ValueError as exc:
        raise HTTPException(
            400,
            str(exc)
        )

    # Nunca guardar la contraseña.
    audit_after = dict(requested)

    if payload.get("password"):
        audit_after["password_changed"] = True

    audit = await add_audit(
        db=db,
        action="WIFI_EDITAR",
        target_id=device_id,
        before=before,
        after=audit_after,
        result="SOLICITADO",
        message=f"Editando WLANConfiguration.{index}",
    )

    try:

        await genieacs.set_parameter_values(
            device_id,
            values
        )

        confirmed = False
        current_state = None

        # Confirmamos solo campos observables.
        for _ in range(5):
            await asyncio.sleep(2)

            current_device = await genieacs.get_device(
                device_id
            )

            current_state = wifi_state(
                current_device,
                index
            )

            if not current_state:
                continue

            if all(
                current_state.get(key) == value
                for key, value in requested.items()
            ):
                confirmed = True
                break

        status = (
            "CONFIRMADO"
            if confirmed
            else "PENDIENTE"
        )

        await update_audit(
            db,
            audit,
            status,
            (
                "Cambios Wi-Fi confirmados"
                if confirmed
                else "Cambios enviados; esperando actualización"
            ),
            audit_after
        )

        return {
            "ok": True,
            "status": status,
            "wifi": current_state,
            "password_changed":
                bool(payload.get("password"))
        }

    except Exception as exc:

        await update_audit(
            db,
            audit,
            "FALLIDO",
            str(exc)
        )

        raise HTTPException(
            502,
            str(exc)
        )
