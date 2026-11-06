"""Lectura y control de CATV.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.genieacs import genieacs
from app.services.device_normalizer import normalize_device


router = APIRouter()


# ACS_CATV_ENDPOINT
@router.get("/api/devices/{device_id}/catv")
async def device_catv(device_id: str):
    from app.services.catv_reader import read_catv, resolve_catv_profile

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    return {
        "device": normalize_device(device),
        "catv": read_catv(device),
        "mode": "read-only"
    }


# ACS_CATV_WRITE_09A
@router.post("/api/devices/{device_id}/catv/{action}")
async def change_catv(
    device_id: str,
    action: str,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.catv_reader import read_catv, resolve_catv_profile
    from app.services.audit_service import (
        add_audit,
        update_audit,
    )

    if action not in ("on", "off"):
        raise HTTPException(
            status_code=400,
            detail="Acción válida: on u off"
        )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    before = read_catv(device)
    profile = resolve_catv_profile(device)

    if not profile:
        raise HTTPException(
            status_code=400,
            detail="CATV no soportado por esta ONU"
        )

    if not profile.get("writable"):
        raise HTTPException(
            status_code=400,
            detail="CATV detectado, pero el parámetro no es escribible"
        )

    requested = (
        profile["on_value"]
        if action == "on"
        else profile["off_value"]
    )

    audit = await add_audit(
        db=db,
        action=(
            "CATV_ACTIVAR"
            if action == "on"
            else "CATV_DESACTIVAR"
        ),
        target_id=device_id,
        before={
            "catv_enable": before.get("enabled")
        },
        after={
            "catv_enable_solicitado": requested
        },
        result="SOLICITADO",
        message="Enviando tarea a GenieACS",
    )

    try:
        task = await genieacs.set_parameter_value(
            device_id,
            profile["parameter"],
            requested,
            profile["value_type"]
        )

    except Exception as exc:

        await update_audit(
            db,
            audit,
            "FALLIDO",
            str(exc),
        )

        raise HTTPException(
            status_code=502,
            detail=f"Error GenieACS: {exc}"
        )

    # Intentar confirmar hasta 4 veces
    confirmed_value = None

    for _ in range(4):

        await asyncio.sleep(2)

        current_device = await genieacs.get_device(device_id)

        if not current_device:
            continue

        current = read_catv(current_device)
        confirmed_value = current.get("enabled")

        if str(confirmed_value) == str(requested):

            await update_audit(
                db,
                audit,
                "CONFIRMADO",
                "Valor confirmado desde GenieACS",
                {
                    "catv_enable_solicitado": requested,
                    "catv_enable_confirmado": confirmed_value,
                }
            )

            return {
                "ok": True,
                "status": "CONFIRMADO",
                "before": before.get("enabled"),
                "requested": requested,
                "confirmed": confirmed_value,
                "audit_id": audit.id,
            }

    await update_audit(
        db,
        audit,
        "PENDIENTE",
        "GenieACS aceptó la tarea, pero el nuevo valor aún no aparece",
        {
            "catv_enable_solicitado": requested,
            "ultimo_valor_observado": confirmed_value,
        }
    )

    return {
        "ok": True,
        "status": "PENDIENTE",
        "before": before.get("enabled"),
        "requested": requested,
        "observed": confirmed_value,
        "audit_id": audit.id,
    }
