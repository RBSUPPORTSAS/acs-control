"""Modulo de seguridad del CPE: firewall y servicios.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.genieacs import genieacs


router = APIRouter()


# ACS_SECURITY_MODULE_16B1

@router.get(
    "/api/devices/{device_id}/security-module"
)
async def security_module_state(
    device_id: str,
):
    from app.services.security_module import (
        security_state,
    )

    device = await genieacs.get_device(
        device_id
    )

    if not device:
        raise HTTPException(
            404,
            "ONU no encontrada"
        )

    return security_state(device)


@router.patch(
    "/api/devices/{device_id}/"
    "security-module/firewall"
)
async def security_module_firewall(
    device_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.security_module import (
        get_acl,
        security_state,
        to_int,
        writable,
    )

    from app.services.audit_service import (
        add_audit,
        update_audit,
    )

    try:
        grade = int(
            payload.get("grade")
        )
    except Exception:
        raise HTTPException(
            400,
            "Nivel firewall inválido"
        )

    if grade not in (0, 1):
        raise HTTPException(
            400,
            "0 = Bajo, 1 = Alto"
        )

    device = await genieacs.get_device(
        device_id
    )

    if not device:
        raise HTTPException(
            404,
            "ONU no encontrada"
        )

    acl = get_acl(device)

    if not acl:
        raise HTTPException(
            404,
            "AclServices no disponible"
        )

    obj = acl.get("FireWallGrade")

    if not writable(obj):
        raise HTTPException(
            403,
            "FireWallGrade no es escribible"
        )

    before = to_int(obj)

    if before == grade:
        return {
            "ok": True,
            "status": "SIN_CAMBIOS",
            **security_state(device),
        }

    audit = await add_audit(
        db=db,
        action="SEGURIDAD_FIREWALL_NIVEL",
        target_id=device_id,
        before={
            "firewall_grade": before
        },
        after={
            "firewall_grade": grade
        },
        result="SOLICITADO",
        message=(
            f"Firewall {before} -> {grade}"
        ),
    )

    try:

        await genieacs.set_parameter_value(
            device_id,
            (
                "InternetGatewayDevice."
                "X_HW_Security."
                "AclServices."
                "FireWallGrade"
            ),
            grade,
            "xsd:unsignedInt"
        )

        confirmed = False
        current = None

        for _ in range(5):

            await asyncio.sleep(2)

            current = await genieacs.get_device(
                device_id
            )

            state = security_state(
                current
            )

            if (
                state.get("firewall_grade")
                == grade
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
                "Nivel firewall confirmado"
                if confirmed
                else
                "Esperando confirmación ONU"
            )
        )

        return {
            "ok": True,
            "status": status,
            **security_state(current or device),
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


@router.patch(
    "/api/devices/{device_id}/"
    "security-module/service/{service_id}"
)
async def security_module_service(
    device_id: str,
    service_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.security_module import (
        security_state,
        service_changes,
    )

    from app.services.audit_service import (
        add_audit,
        update_audit,
    )

    device = await genieacs.get_device(
        device_id
    )

    if not device:
        raise HTTPException(
            404,
            "ONU no encontrada"
        )

    state_before = security_state(
        device
    )

    before = next(
        (
            x
            for x
            in state_before.get(
                "services", []
            )
            if x["id"] == service_id
        ),
        None
    )

    if not before:
        raise HTTPException(
            404,
            "Servicio no encontrado"
        )

    try:
        values, requested = (
            service_changes(
                device,
                service_id,
                payload
            )
        )
    except ValueError as exc:
        raise HTTPException(
            400,
            str(exc)
        )

    audit = await add_audit(
        db=db,
        action="SEGURIDAD_SERVICIO",
        target_id=device_id,
        before={
            "service": service_id,
            **before,
        },
        after={
            "service": service_id,
            **requested,
        },
        result="SOLICITADO",
        message=(
            f"Seguridad {service_id.upper()}"
        ),
    )

    try:

        await genieacs.set_parameter_values(
            device_id,
            values
        )

        confirmed = False
        current_service = None

        for _ in range(5):

            await asyncio.sleep(2)

            current_device = (
                await genieacs.get_device(
                    device_id
                )
            )

            current_state = security_state(
                current_device
            )

            current_service = next(
                (
                    x
                    for x
                    in current_state["services"]
                    if x["id"] == service_id
                ),
                None
            )

            if (
                current_service
                and all(
                    current_service.get(k)
                    == v
                    for k, v
                    in requested.items()
                )
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
                "Cambio confirmado"
                if confirmed
                else
                "Esperando confirmación ONU"
            )
        )

        return {
            "ok": True,
            "status": status,
            "service": current_service,
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
