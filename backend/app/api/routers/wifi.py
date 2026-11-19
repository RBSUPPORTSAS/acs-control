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
class WifiRejected(Exception):
    pass


async def _task_fault(device_id, task_id):
    """Mensaje si la tarea termino en fault (y la limpia); None si no."""

    if not task_id:
        return None

    for fault in await genieacs.get_faults(device_id):
        if not str(fault.get("_id", "")).endswith(f"task_{task_id}"):
            continue

        await genieacs.delete_fault(fault["_id"])
        await genieacs.delete_task(task_id)

        detail = fault.get("detail") or {}
        text = detail.get("faultString") or fault.get("message") or ""
        return (
            f"La ONU rechazó el cambio ({fault.get('code')}: {text}). "
            "No se aplicó nada."
        )

    return None


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
        drop_unchanged,
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

    payload = drop_unchanged(device, index, payload)

    if not payload:
        return {
            "ok": True,
            "status": "SIN_CAMBIOS",
            "wifi": before,
            "password_changed": False,
        }

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

        sent = await genieacs.set_parameter_values(
            device_id,
            values,
            wait_ms=10000,
        )
        task_id = (sent or {}).get("task_id")

        confirmed = False
        current_state = None

        # Confirmamos solo campos observables.
        for _ in range(5):
            await asyncio.sleep(2)

            # Si la ONU rechazo el paquete, no esperar: avisar y no dejar la
            # tarea en cola (GenieACS la reintentaria en cada inform).
            fault = await _task_fault(device_id, task_id)
            if fault:
                raise WifiRejected(fault)

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

    except WifiRejected as exc:

        await update_audit(db, audit, "FALLIDO", str(exc))

        raise HTTPException(422, str(exc))

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
