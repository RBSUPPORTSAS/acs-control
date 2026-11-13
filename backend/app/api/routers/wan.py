"""Lectura, creacion, edicion y borrado de conexiones WAN.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.genieacs import genieacs
from app.services.device_normalizer import normalize_device


router = APIRouter()


# ACS_WAN_READ_11A
@router.get("/api/devices/{device_id}/wan")
async def device_wan(device_id: str):

    from app.services.wan_reader import read_wan

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    wan = read_wan(device)

    from app.services.wan_reader import enrich_wan_bindings

    wan = enrich_wan_bindings(device, wan)

    return {
        "device": normalize_device(device),
        "count": len(wan),
        "wan": wan,
        "mode": "read-only"
    }


# ACS_WAN_CAPABILITIES_11F
@router.get("/api/devices/{device_id}/wan-capabilities")
async def wan_capabilities(device_id: str):

    from app.services.wan_capabilities import (
        read_capabilities
    )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    return read_capabilities(device)


# ACS_WAN_PREVIEW_12A
@router.post("/api/devices/{device_id}/wan/preview")
async def wan_preview(
    device_id: str,
    payload: dict
):
    from app.services.wan_builder import build_pppoe, build_dhcp

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    wan_type = payload.get("type")

    try:
        if wan_type == "pppoe":
            result = build_pppoe(payload)

        elif wan_type == "dhcp":
            result = build_dhcp(payload)

        else:
            raise HTTPException(
                status_code=400,
                detail="Tipo WAN válido: pppoe o dhcp"
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    # Contraseña nunca regresa al navegador
    safe_values = []

    for row in result["parameter_values"]:
        copy = list(row)

        if copy[0] == "Password":
            copy[1] = "********"

        safe_values.append(copy)

    return {
        "mode": "PREVIEW",
        "writes": False,
        "device_id": device_id,
        "object_name": result["object_name"],
        "connection_type": result["connection_type"],
        "parameter_values": safe_values,
    }


# ACS_WAN_CREATE_12B
@router.post("/api/devices/{device_id}/wan/create-pppoe")
async def create_pppoe_wan(
    device_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_create import create_pppoe
    from app.services.wan_reader import read_wan
    from app.services.wan_driver import detect_wan_driver
    from app.services.x_catv_wan_creator import create_x_catv_pppoe
    from app.services.x_ctcom_wan_creator import create_x_ctcom_pppoe
    from app.services.audit_service import (
        add_audit,
        update_audit,
    )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="ONU no encontrada"
        )

    vlan = int(payload.get("vlan", 0))

    if vlan < 1 or vlan > 4094:
        raise HTTPException(
            status_code=400,
            detail="VLAN inválida"
        )

    if not payload.get("username"):
        raise HTTPException(
            status_code=400,
            detail="Usuario PPPoE obligatorio"
        )

    audit = await add_audit(
        db=db,
        action="WAN_CREAR_PPPOE",
        target_id=device_id,
        before=None,
        after={
            "vlan": vlan,
            "service": "INTERNET",
            "enabled": detect_wan_driver(device) in ("x_ctcom_wan", "huawei"),
        },
        result="SOLICITADO",
        message="Creando nueva WAN PPPoE",
    )

    try:

        driver = detect_wan_driver(device)

        if driver == "x_catv_wan":
            result = await create_x_catv_pppoe(
                genieacs,
                device_id,
                payload,
            )

        elif driver == "x_ctcom_wan":
            result = await create_x_ctcom_pppoe(
                genieacs,
                device_id,
                payload,
            )

        elif driver == "huawei":
            from app.services.huawei_wan import create_huawei_wan

            result = await create_huawei_wan(
                genieacs,
                device_id,
                payload,
                mode="PPPOE",
            )

        else:
            result = await create_pppoe(
                device_id,
                payload
            )

        if result["status"] == 202:

            await update_audit(
                db,
                audit,
                "PENDIENTE",
                "Tarea en cola hasta próximo Inform",
            )

            return {
                "ok": True,
                "status": "PENDIENTE",
                "http_status": 202,
                "audit_id": audit.id,
            }

        await asyncio.sleep(3)

        updated = await genieacs.get_device(
            device_id
        )

        connections = read_wan(updated)

        created = next(
            (
                w for w in connections
                if w.get("name") == result["name"]
            ),
            None
        )

        if created:

            await update_audit(
                db,
                audit,
                "CONFIRMADO",
                "WAN creada correctamente",
                {
                    "vlan": vlan,
                    "service": "INTERNET",
                    "enabled": created.get("enabled"),
                    "instance": created.get("instance"),
                    "name": created.get("name"),
                }
            )

            return {
                "ok": True,
                "status": "CONFIRMADO",
                "wan": created,
                "audit_id": audit.id,
            }

        await update_audit(
            db,
            audit,
            "PENDIENTE",
            "addObject ejecutado, esperando actualización del árbol",
        )

        return {
            "ok": True,
            "status": "PENDIENTE",
            "http_status": result["status"],
            "audit_id": audit.id,
        }

    except Exception as exc:

        await update_audit(
            db,
            audit,
            "FALLIDO",
            str(exc),
        )

        raise HTTPException(
            status_code=502,
            detail=str(exc)
        )


# ACS_WAN_DELETE_12C
@router.delete("/api/devices/{device_id}/wan/pppoe/{instance}")
async def delete_pppoe_wan(
    device_id: str,
    instance: int,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_reader import read_wan
    from app.services.audit_service import (
        add_audit,
        update_audit,
    )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    connections = read_wan(device)

    wan = next(
        (
            w for w in connections
            if w.get("object_type") == "WANPPPConnection"
            and w.get("instance") == instance
        ),
        None
    )

    if not wan:
        raise HTTPException(
            404,
            "WAN PPPoE no encontrada"
        )

    if wan.get("protected"):
        raise HTTPException(
            403,
            "WAN protegida: transporta TR-069 y no puede eliminarse"
        )

    audit = await add_audit(
        db=db,
        action="WAN_ELIMINAR_PPPOE",
        target_id=device_id,
        before={
            "instance": instance,
            "name": wan.get("name"),
            "vlan": wan.get("vlan"),
            "services": wan.get("services"),
        },
        after=None,
        result="SOLICITADO",
        message="Eliminando WAN PPPoE",
    )

    object_name = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wan['wan_connection_device']}."
        f"WANPPPConnection.{instance}"
    )

    try:

        result = await genieacs.delete_object(
            device_id,
            object_name
        )

        await asyncio.sleep(3)

        updated = await genieacs.get_device(device_id)
        remaining = read_wan(updated)

        still_exists = any(
            w.get("object_type") == "WANPPPConnection"
            and w.get("instance") == instance
            for w in remaining
        )

        status = (
            "PENDIENTE"
            if still_exists
            else "CONFIRMADO"
        )

        await update_audit(
            db,
            audit,
            status,
            (
                "Esperando actualización del árbol"
                if still_exists
                else "WAN eliminada correctamente"
            )
        )

        return {
            "ok": True,
            "status": status,
            "instance": instance,
            "task": result,
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


# ACS_WAN_TOGGLE_12E1
@router.post("/api/devices/{device_id}/wan/pppoe/{instance}/{action}")
async def toggle_pppoe_wan(
    device_id: str,
    instance: int,
    action: str,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    if action not in ("enable", "disable"):
        raise HTTPException(
            400,
            "Acción válida: enable o disable"
        )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    connections = read_wan(device)

    wan = next(
        (
            w for w in connections
            if w.get("object_type") == "WANPPPConnection"
            and w.get("instance") == instance
        ),
        None
    )

    if not wan:
        raise HTTPException(
            404,
            "WAN PPPoE no encontrada"
        )

    # No permitimos tocar una WAN de gestión.
    if wan.get("protected"):
        raise HTTPException(
            403,
            "WAN protegida: contiene TR069"
        )

    desired = action == "enable"

    # Evita enviar tareas innecesarias.
    if wan.get("enabled") is desired:
        return {
            "ok": True,
            "status": "SIN_CAMBIOS",
            "instance": instance,
            "enabled": desired,
        }

    path = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wan['wan_connection_device']}."
        f"WANPPPConnection.{instance}.Enable"
    )

    audit = await add_audit(
        db=db,
        action=(
            "WAN_ACTIVAR_PPPOE"
            if desired
            else "WAN_DESACTIVAR_PPPOE"
        ),
        target_id=device_id,
        before={
            "instance": instance,
            "name": wan.get("name"),
            "vlan": wan.get("vlan"),
            "enabled": wan.get("enabled"),
        },
        after={
            "instance": instance,
            "enabled": desired,
        },
        result="SOLICITADO",
        message=(
            "Activando WAN PPPoE"
            if desired
            else "Desactivando WAN PPPoE"
        ),
    )

    try:
        await genieacs.set_parameter_value(
            device_id,
            path,
            desired,
            "xsd:boolean"
        )

        confirmed = False

        for _ in range(4):
            await asyncio.sleep(2)

            current_device = await genieacs.get_device(device_id)
            current_wans = read_wan(current_device)

            current = next(
                (
                    w for w in current_wans
                    if w.get("object_type") == "WANPPPConnection"
                    and w.get("instance") == instance
                ),
                None
            )

            if current and current.get("enabled") is desired:
                confirmed = True
                break

        if confirmed:
            await update_audit(
                db,
                audit,
                "CONFIRMADO",
                (
                    "WAN activada correctamente"
                    if desired
                    else "WAN desactivada correctamente"
                ),
                {
                    "instance": instance,
                    "enabled": desired,
                }
            )

            return {
                "ok": True,
                "status": "CONFIRMADO",
                "instance": instance,
                "enabled": desired,
            }

        await update_audit(
            db,
            audit,
            "PENDIENTE",
            "Tarea enviada; esperando confirmación de la ONU"
        )

        return {
            "ok": True,
            "status": "PENDIENTE",
            "instance": instance,
            "enabled": desired,
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


# ACS_WAN_EDIT_12F1
@router.patch("/api/devices/{device_id}/wan/pppoe/{instance}")
async def edit_pppoe_wan(
    device_id: str,
    instance: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    connections = read_wan(device)

    wan = next(
        (
            w for w in connections
            if w.get("object_type") == "WANPPPConnection"
            and w.get("instance") == instance
        ),
        None
    )

    if not wan:
        raise HTTPException(404, "WAN PPPoE no encontrada")

    if wan.get("protected"):
        raise HTTPException(
            403,
            "WAN protegida: contiene TR069"
        )

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wan['wan_connection_device']}."
        f"WANPPPConnection.{instance}."
    )

    values = []
    requested = {}

    if "vlan" in payload:
        vlan = int(payload["vlan"])
        if not 1 <= vlan <= 4094:
            raise HTTPException(400, "VLAN inválida")

        values.append([
            base + "X_CT-COM_VLANIDMark",
            vlan,
            "xsd:unsignedInt"
        ])
        requested["vlan"] = vlan

    if "priority" in payload:
        priority = int(payload["priority"])
        if not 0 <= priority <= 7:
            raise HTTPException(400, "802.1p inválido")

        values.append([
            base + "X_CT-COM_802-1pMark",
            priority,
            "xsd:unsignedInt"
        ])
        requested["priority_8021p"] = priority

    if "nat" in payload:
        nat = bool(payload["nat"])
        values.append([
            base + "NATEnabled",
            nat,
            "xsd:boolean"
        ])
        requested["nat"] = nat

    if "mtu" in payload:
        mtu = int(payload["mtu"])
        if not 576 <= mtu <= 1492:
            raise HTTPException(
                400,
                "MTU PPPoE permitido: 576-1492"
            )

        values.append([
            base + "MaxMRUSize",
            mtu,
            "xsd:unsignedInt"
        ])
        requested["mtu"] = mtu

    if "username" in payload:
        username = str(payload["username"]).strip()
        if not username:
            raise HTTPException(
                400,
                "Usuario PPPoE vacío"
            )

        values.append([
            base + "Username",
            username,
            "xsd:string"
        ])
        requested["username"] = username

    password_changed = False

    if payload.get("password"):
        values.append([
            base + "Password",
            str(payload["password"]),
            "xsd:string"
        ])
        password_changed = True

    if "bindings" in payload:

        bindings = payload["bindings"]

        if not isinstance(bindings, list) or not bindings:
            raise HTTPException(
                400,
                "Selecciona al menos una interfaz"
            )

        allowed = (
            "InternetGatewayDevice.LANDevice.1."
            "LANEthernetInterfaceConfig.",
            "InternetGatewayDevice.LANDevice.1."
            "WLANConfiguration.",
        )

        if any(
            not str(x).startswith(allowed)
            for x in bindings
        ):
            raise HTTPException(
                400,
                "Binding no permitido"
            )

        binding_string = ",".join(bindings)

        values.append([
            base + "X_CT-COM_LanInterface",
            binding_string,
            "xsd:string"
        ])

        requested["lan_binding"] = binding_string

    if not values:
        raise HTTPException(
            400,
            "No hay cambios para aplicar"
        )

    before = {
        "instance": instance,
        "vlan": wan.get("vlan"),
        "priority_8021p": wan.get("priority_8021p"),
        "nat": wan.get("nat"),
        "mtu": wan.get("mtu"),
        "username": wan.get("username"),
        "lan_binding": wan.get("lan_binding"),
    }

    audit_after = dict(requested)

    if password_changed:
        audit_after["password_changed"] = True

    audit = await add_audit(
        db=db,
        action="WAN_EDITAR_PPPOE",
        target_id=device_id,
        before=before,
        after=audit_after,
        result="SOLICITADO",
        message=f"Editando WAN PPPoE {instance}",
    )

    try:

        # Huawei: X_CT-COM_* -> X_HW_* (VLAN, prioridad, servicios, interfaces)

        from app.services.wan_driver import huawei_wan

        if huawei_wan(device):

            from app.services.huawei_wan import translate

            values = translate(values)


        await genieacs.set_parameter_values(
            device_id,
            values
        )

        confirmed = False

        # Contraseña no puede leerse; confirmamos
        # solamente los campos observables.
        observable = dict(requested)

        for _ in range(4):

            await asyncio.sleep(2)

            current_device = await genieacs.get_device(
                device_id
            )

            current_wans = read_wan(current_device)

            current = next(
                (
                    w for w in current_wans
                    if w.get("object_type")
                    == "WANPPPConnection"
                    and w.get("instance") == instance
                ),
                None
            )

            if not current:
                continue

            if observable and all(
                current.get(key) == value
                for key, value in observable.items()
            ):
                confirmed = True
                break

        if confirmed:

            await update_audit(
                db,
                audit,
                "CONFIRMADO",
                "Cambios WAN confirmados por GenieACS",
                audit_after
            )

            return {
                "ok": True,
                "status": "CONFIRMADO",
                "instance": instance,
            }

        message = (
            "Contraseña enviada; no puede leerse "
            "desde el CPE para confirmarla"
            if password_changed and not observable
            else
            "Cambios enviados; esperando actualización del CPE"
        )

        await update_audit(
            db,
            audit,
            "PENDIENTE",
            message,
            audit_after
        )

        return {
            "ok": True,
            "status": "PENDIENTE",
            "instance": instance,
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


# ACS_WAN_DHCP_CREATE_13B
@router.post("/api/devices/{device_id}/wan/create-dhcp")
@router.post("/api/devices/{device_id}/wan/create-ip")
async def create_dhcp_wan(
    device_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_create import create_dhcp
    from app.services.wan_reader import read_wan
    from app.services.wan_driver import detect_wan_driver
    from app.services.x_catv_wan_creator import create_x_catv_dhcp
    from app.services.x_ctcom_wan_creator import create_x_ctcom_dhcp
    from app.services.audit_service import add_audit, update_audit

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    vlan = int(payload.get("vlan", 0))
    priority = int(payload.get("priority", 0))
    mtu = int(payload.get("mtu", 1500))

    if not 1 <= vlan <= 4094:
        raise HTTPException(400, "VLAN inválida")

    if not 0 <= priority <= 7:
        raise HTTPException(400, "802.1p inválido")

    if not 576 <= mtu <= 1500:
        raise HTTPException(400, "MTU inválido")

    # /create-ip acepta addressing_type DHCP o STATIC. IP fija fuera de
    # VSOL solo esta validada en la familia x_ctcom (p. ej. HG102DWT).
    mode = str(payload.get("addressing_type") or "DHCP").upper()

    if mode not in ("DHCP", "STATIC"):
        raise HTTPException(400, "Tipo válido: DHCP o STATIC")

    driver = detect_wan_driver(device)

    if mode == "STATIC":
        import ipaddress

        if driver not in ("x_ctcom_wan", "huawei"):
            raise HTTPException(
                400,
                "IP fija no está validada para este modelo de ONU",
            )

        try:
            ipaddress.IPv4Address(str(payload.get("ip", "")).strip())
            ipaddress.IPv4Address(str(payload.get("gateway", "")).strip())
            ipaddress.IPv4Network(
                f"0.0.0.0/{str(payload.get('subnet_mask', '')).strip()}"
            )
        except ValueError:
            raise HTTPException(400, "IP, máscara o gateway inválidos")

        if not str(payload.get("dns", "")).strip():
            raise HTTPException(400, "Falta el DNS")

    label = "Static" if mode == "STATIC" else "DHCP"

    audit_after = {
        "vlan": vlan,
        "service": "INTERNET",
        "type": label,
        "enabled": driver in ("x_ctcom_wan", "huawei"),
    }

    if mode == "STATIC":
        audit_after.update({
            "ip": payload.get("ip"),
            "subnet_mask": payload.get("subnet_mask"),
            "gateway": payload.get("gateway"),
            "dns": payload.get("dns"),
        })

    audit = await add_audit(
        db=db,
        action="WAN_CREAR_ESTATICA" if mode == "STATIC" else "WAN_CREAR_DHCP",
        target_id=device_id,
        before=None,
        after=audit_after,
        result="SOLICITADO",
        message=f"Creando nueva WAN {label}",
    )

    try:

        if driver == "x_catv_wan":
            result = await create_x_catv_dhcp(
                genieacs,
                device_id,
                payload,
            )

        elif driver == "x_ctcom_wan":
            result = await create_x_ctcom_dhcp(
                genieacs,
                device_id,
                payload,
                mode=mode,
            )

        elif driver == "huawei":
            from app.services.huawei_wan import create_huawei_wan

            result = await create_huawei_wan(
                genieacs,
                device_id,
                payload,
                mode=mode,
            )

        else:
            result = await create_dhcp(
                device_id,
                payload
            )

        if result["status"] == 202:
            await update_audit(
                db,
                audit,
                "PENDIENTE",
                "Tarea DHCP en cola"
            )

            return {
                "ok": True,
                "status": "PENDIENTE",
                "http_status": 202,
                "audit_id": audit.id,
            }

        await asyncio.sleep(3)

        updated = await genieacs.get_device(device_id)
        connections = read_wan(updated)

        created = next(
            (
                w for w in connections
                if w.get("name") == result["name"]
            ),
            None
        )

        if created:
            await update_audit(
                db,
                audit,
                "CONFIRMADO",
                f"WAN {label} creada correctamente",
                {
                    "instance": created.get("instance"),
                    "name": created.get("name"),
                    "vlan": vlan,
                    "type": label,
                    "enabled": created.get("enabled"),
                }
            )

            return {
                "ok": True,
                "status": "CONFIRMADO",
                "wan": created,
                "audit_id": audit.id,
            }

        await update_audit(
            db,
            audit,
            "PENDIENTE",
            "addObject ejecutado; esperando actualización"
        )

        return {
            "ok": True,
            "status": "PENDIENTE",
            "audit_id": audit.id,
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


# ACS_VSOL_WAN_CREATE_13D2
@router.post("/api/devices/{device_id}/wan/vsol/create-ip")
async def create_vsol_ip_wan(
    device_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.vsol_wan_creator import create_vsol_ip
    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    mode = str(
        payload.get("addressing_type", "DHCP")
    ).upper()

    if mode not in ("DHCP", "STATIC"):
        raise HTTPException(
            400,
            "Tipo válido: DHCP o STATIC"
        )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    from app.services.wan_driver import HUAWEI_CREATE_MSG, huawei_wan

    if huawei_wan(device):
        raise HTTPException(400, HUAWEI_CREATE_MSG)

    audit_payload = {
        "type": "DHCP" if mode == "DHCP" else "Static",
        "vlan": payload.get("vlan"),
        "priority": payload.get("priority", 0),
        "nat": payload.get("nat", True),
        "mtu": payload.get("mtu", 1500),
        "bindings": payload.get("bindings", []),
        "enabled": False,
    }

    if mode == "STATIC":
        audit_payload.update({
            "ip": payload.get("ip"),
            "subnet_mask": payload.get("subnet_mask"),
            "gateway": payload.get("gateway"),
            "dns": payload.get("dns"),
        })

    audit = await add_audit(
        db=db,
        action=(
            "WAN_CREAR_VSOL_DHCP"
            if mode == "DHCP"
            else "WAN_CREAR_VSOL_STATIC"
        ),
        target_id=device_id,
        before=None,
        after=audit_payload,
        result="SOLICITADO",
        message="Creando WAN VSOL",
    )

    state = {}

    try:
        result = await create_vsol_ip(
            genieacs,
            device_id,
            payload,
            state
        )

        confirmed = None

        for _ in range(6):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)

            current_wans = read_wan(current)

            confirmed = next(
                (
                    w for w in current_wans
                    if w.get("wan_connection_device")
                    == result["wcd"]
                    and w.get("object_type")
                    == "WANIPConnection"
                    and w.get("instance")
                    == result["instance"]
                ),
                None
            )

            if confirmed:
                break

        if confirmed:
            await update_audit(
                db,
                audit,
                "CONFIRMADO",
                "WAN VSOL creada correctamente",
                {
                    **audit_payload,
                    "wcd": result["wcd"],
                    "instance": result["instance"],
                    "name": result["name"],
                }
            )

            return {
                "ok": True,
                "status": "CONFIRMADO",
                "wan": confirmed,
            }

        await update_audit(
            db,
            audit,
            "PENDIENTE",
            "WAN creada; esperando actualización del árbol",
            {
                **audit_payload,
                **result,
            }
        )

        return {
            "ok": True,
            "status": "PENDIENTE",
            **result,
        }

    except Exception as exc:

        cleanup = "No requerido"

        # Si ya creamos el WCD y algo posterior falló,
        # intentamos eliminar el contenedor completo.
        if state.get("wcd") is not None:
            try:
                object_name = (
                    "InternetGatewayDevice."
                    "WANDevice.1."
                    "WANConnectionDevice."
                    f'{state["wcd"]}'
                )

                await genieacs.delete_object(
                    device_id,
                    object_name
                )

                cleanup = "WCD incompleto eliminado"

            except Exception as cleanup_exc:
                cleanup = (
                    "Falló limpieza: "
                    + str(cleanup_exc)
                )

        await update_audit(
            db,
            audit,
            "FALLIDO",
            f"{exc} | {cleanup}",
            audit_payload
        )

        raise HTTPException(
            502,
            f"{exc} | {cleanup}"
        )


# ACS_VSOL_PPPOE_CREATE_13E2
@router.post("/api/devices/{device_id}/wan/vsol/create-pppoe")
async def create_vsol_pppoe_wan(
    device_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.vsol_wan_creator import create_vsol_pppoe
    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    from app.services.wan_driver import HUAWEI_CREATE_MSG, huawei_wan

    if huawei_wan(device):
        raise HTTPException(400, HUAWEI_CREATE_MSG)

    audit_data = {
        "type": "PPPoE",
        "vlan": payload.get("vlan"),
        "priority": payload.get("priority", 0),
        "nat": payload.get("nat", True),
        "mtu": payload.get("mtu", 1492),
        "username": payload.get("username"),
        "bindings": payload.get("bindings", []),
        "enabled": False,
        "password_changed": bool(payload.get("password")),
    }

    audit = await add_audit(
        db=db,
        action="WAN_CREAR_VSOL_PPPOE",
        target_id=device_id,
        before=None,
        after=audit_data,
        result="SOLICITADO",
        message="Creando WAN PPPoE VSOL",
    )

    state = {}

    try:
        result = await create_vsol_pppoe(
            genieacs,
            device_id,
            payload,
            state
        )

        confirmed = None

        for _ in range(6):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)
            wans = read_wan(current)

            confirmed = next(
                (
                    w for w in wans
                    if w.get("wan_connection_device") == result["wcd"]
                    and w.get("object_type") == "WANPPPConnection"
                    and w.get("instance") == result["instance"]
                ),
                None
            )

            if confirmed:
                break

        status = "CONFIRMADO" if confirmed else "PENDIENTE"

        await update_audit(
            db,
            audit,
            status,
            (
                "WAN PPPoE VSOL creada correctamente"
                if confirmed
                else "WAN creada; esperando actualización"
            ),
            {
                **audit_data,
                **result,
            }
        )

        return {
            "ok": True,
            "status": status,
            "wan": confirmed,
            **result,
        }

    except Exception as exc:

        if state.get("wcd") is not None:
            try:
                await genieacs.delete_object(
                    device_id,
                    (
                        "InternetGatewayDevice."
                        "WANDevice.1."
                        "WANConnectionDevice."
                        f'{state["wcd"]}'
                    )
                )
            except Exception:
                pass

        await update_audit(
            db,
            audit,
            "FALLIDO",
            str(exc),
            audit_data
        )

        raise HTTPException(502, str(exc))


# ACS_WAN_TOGGLE_WCD_14B1
@router.post(
    "/api/devices/{device_id}/wan/"
    "{wcd}/pppoe/{instance}/{action}"
)
async def toggle_pppoe_wan_wcd(
    device_id: str,
    wcd: int,
    instance: int,
    action: str,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    if action not in ("enable", "disable"):
        raise HTTPException(400, "Acción inválida")

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    connections = read_wan(device)

    wan = next(
        (
            w for w in connections
            if w.get("wan_connection_device") == wcd
            and w.get("object_type") == "WANPPPConnection"
            and w.get("instance") == instance
        ),
        None
    )

    if not wan:
        raise HTTPException(404, "WAN PPPoE no encontrada")

    if wan.get("protected"):
        raise HTTPException(
            403,
            "WAN protegida: contiene TR069"
        )

    desired = action == "enable"

    path = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}."
        f"WANPPPConnection.{instance}.Enable"
    )

    audit = await add_audit(
        db=db,
        action=(
            "WAN_ACTIVAR_PPPOE"
            if desired
            else "WAN_DESACTIVAR_PPPOE"
        ),
        target_id=device_id,
        before={
            "wcd": wcd,
            "instance": instance,
            "enabled": wan.get("enabled"),
            "vlan": wan.get("vlan"),
        },
        after={
            "wcd": wcd,
            "instance": instance,
            "enabled": desired,
        },
        result="SOLICITADO",
        message="Cambio estado WAN PPPoE",
    )

    try:
        await genieacs.set_parameter_value(
            device_id,
            path,
            desired,
            "xsd:boolean"
        )

        confirmed = False

        for _ in range(4):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)
            current_wans = read_wan(current)

            target = next(
                (
                    w for w in current_wans
                    if w.get("wan_connection_device") == wcd
                    and w.get("object_type") == "WANPPPConnection"
                    and w.get("instance") == instance
                ),
                None
            )

            if target and target.get("enabled") is desired:
                confirmed = True
                break

        status = "CONFIRMADO" if confirmed else "PENDIENTE"

        await update_audit(
            db,
            audit,
            status,
            (
                "Estado WAN confirmado"
                if confirmed
                else "Esperando confirmación ONU"
            )
        )

        return {
            "ok": True,
            "status": status,
            "wcd": wcd,
            "instance": instance,
            "enabled": desired,
        }

    except Exception as exc:
        await update_audit(
            db,
            audit,
            "FALLIDO",
            str(exc)
        )

        raise HTTPException(502, str(exc))


# ACS_WAN_DELETE_WCD_14B3
@router.delete(
    "/api/devices/{device_id}/wan/{wcd}/{object_type}/{instance}"
)
async def delete_wan_wcd(
    device_id: str,
    wcd: int,
    object_type: str,
    instance: int,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    allowed_types = {
        "WANPPPConnection",
        "WANIPConnection",
    }

    if object_type not in allowed_types:
        raise HTTPException(
            400,
            "Tipo WAN no permitido"
        )

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    wans = read_wan(device)

    target = next(
        (
            w for w in wans
            if w.get("wan_connection_device") == wcd
            and w.get("object_type") == object_type
            and w.get("instance") == instance
        ),
        None
    )

    if not target:
        raise HTTPException(
            404,
            "WAN no encontrada"
        )

    # Todas las conexiones que viven dentro del mismo WCD.
    same_wcd = [
        w for w in wans
        if w.get("wan_connection_device") == wcd
    ]

    # Seguridad crítica:
    # si cualquier conexión del WCD transporta TR069,
    # jamás eliminamos el contenedor.
    if any(w.get("protected") for w in same_wcd):
        raise HTTPException(
            403,
            "WAN protegida: el WANConnectionDevice contiene TR069"
        )

    before = {
        "wcd": wcd,
        "object_type": object_type,
        "instance": instance,
        "name": target.get("name"),
        "vlan": target.get("vlan"),
        "services": target.get("services"),
    }

    audit = await add_audit(
        db=db,
        action="WAN_ELIMINAR_WCD",
        target_id=device_id,
        before=before,
        after=None,
        result="SOLICITADO",
        message=f"Eliminando WANConnectionDevice {wcd}",
    )

    object_name = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    try:

        await genieacs.delete_object(
            device_id,
            object_name
        )

        confirmed = False

        for _ in range(6):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)
            current_wans = read_wan(current)

            exists = any(
                w.get("wan_connection_device") == wcd
                for w in current_wans
            )

            if not exists:
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
                "WANConnectionDevice eliminado correctamente"
                if confirmed
                else "DeleteObject enviado; esperando actualización"
            )
        )

        return {
            "ok": True,
            "status": status,
            "wcd": wcd,
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


# ACS_WAN_EDIT_WCD_14B4
@router.patch(
    "/api/devices/{device_id}/wan/{wcd}/pppoe/{instance}"
)
async def edit_pppoe_wan_wcd(
    device_id: str,
    wcd: int,
    instance: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio

    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    wans = read_wan(device)

    wan = next(
        (
            w for w in wans
            if w.get("wan_connection_device") == wcd
            and w.get("object_type") == "WANPPPConnection"
            and w.get("instance") == instance
        ),
        None
    )

    if not wan:
        raise HTTPException(404, "WAN PPPoE no encontrada")

    if wan.get("protected"):
        raise HTTPException(
            403,
            "WAN protegida: contiene TR069"
        )

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}."
        f"WANPPPConnection.{instance}."
    )

    values = []
    requested = {}

    if "vlan" in payload:
        vlan = int(payload["vlan"])

        if not 1 <= vlan <= 4094:
            raise HTTPException(400, "VLAN inválida")

        values.extend([
            [
                base + "X_CT-COM_VLANIDMark",
                vlan,
                "xsd:unsignedInt"
            ],
            [
                (
                    "InternetGatewayDevice.WANDevice.1."
                    f"WANConnectionDevice.{wcd}."
                    "X_CT-COM_WANGponLinkConfig.VLANIDMark"
                ),
                vlan,
                "xsd:unsignedInt"
            ],
        ])

        requested["vlan"] = vlan

    if "priority" in payload:
        priority = int(payload["priority"])

        if not 0 <= priority <= 7:
            raise HTTPException(400, "802.1p inválido")

        values.extend([
            [
                base + "X_CT-COM_802-1pMark",
                priority,
                "xsd:unsignedInt"
            ],
            [
                (
                    "InternetGatewayDevice.WANDevice.1."
                    f"WANConnectionDevice.{wcd}."
                    "X_CT-COM_WANGponLinkConfig.802-1pMark"
                ),
                priority,
                "xsd:unsignedInt"
            ],
        ])

        requested["priority_8021p"] = priority

    if "nat" in payload:
        nat = bool(payload["nat"])

        values.append([
            base + "NATEnabled",
            nat,
            "xsd:boolean"
        ])

        requested["nat"] = nat

    if "mtu" in payload:
        mtu = int(payload["mtu"])

        if not 576 <= mtu <= 1492:
            raise HTTPException(
                400,
                "MTU PPPoE permitido: 576-1492"
            )

        values.append([
            base + "MaxMRUSize",
            mtu,
            "xsd:unsignedInt"
        ])

        requested["mtu"] = mtu

    if "username" in payload:
        username = str(payload["username"]).strip()

        if not username:
            raise HTTPException(
                400,
                "Usuario PPPoE vacío"
            )

        values.append([
            base + "Username",
            username,
            "xsd:string"
        ])

        requested["username"] = username

    password_changed = False

    if payload.get("password"):
        values.append([
            base + "Password",
            str(payload["password"]),
            "xsd:string"
        ])

        password_changed = True

    if "bindings" in payload:

        bindings = payload["bindings"]

        if not isinstance(bindings, list):
            raise HTTPException(
                400,
                "Bindings inválidos"
            )

        binding_string = ",".join(bindings)

        values.append([
            base + "X_CT-COM_LanInterface",
            binding_string,
            "xsd:string"
        ])

        requested["lan_binding"] = binding_string

    if not values:
        raise HTTPException(
            400,
            "No hay cambios para aplicar"
        )

    audit_after = dict(requested)

    if password_changed:
        audit_after["password_changed"] = True

    audit = await add_audit(
        db=db,
        action="WAN_EDITAR_PPPOE_WCD",
        target_id=device_id,
        before={
            "wcd": wcd,
            "instance": instance,
            "vlan": wan.get("vlan"),
            "priority_8021p": wan.get("priority_8021p"),
            "nat": wan.get("nat"),
            "mtu": wan.get("mtu"),
            "username": wan.get("username"),
            "lan_binding": wan.get("lan_binding"),
        },
        after=audit_after,
        result="SOLICITADO",
        message=f"Editando WCD {wcd} PPPoE {instance}",
    )

    try:

        # Huawei: X_CT-COM_* -> X_HW_* (VLAN, prioridad, servicios, interfaces)

        from app.services.wan_driver import huawei_wan

        if huawei_wan(device):

            from app.services.huawei_wan import translate

            values = translate(values)


        await genieacs.set_parameter_values(
            device_id,
            values
        )

        confirmed = False

        for _ in range(5):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)
            current_wans = read_wan(current)

            target = next(
                (
                    w for w in current_wans
                    if w.get("wan_connection_device") == wcd
                    and w.get("object_type") == "WANPPPConnection"
                    and w.get("instance") == instance
                ),
                None
            )

            if not target:
                continue

            if requested and all(
                target.get(key) == value
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
                "Cambios WAN confirmados"
                if confirmed
                else "Cambios enviados; esperando confirmación"
            ),
            audit_after
        )

        return {
            "ok": True,
            "status": status,
            "wcd": wcd,
            "instance": instance,
        }

    except Exception as exc:

        await update_audit(
            db,
            audit,
            "FALLIDO",
            str(exc)
        )

        raise HTTPException(502, str(exc))


# ACS_WANIP_CONTROLS_14C1

@router.post("/api/devices/{device_id}/wan/{wcd}/ip/{instance}/{action}")
async def toggle_ip_wan_wcd(
    device_id: str,
    wcd: int,
    instance: int,
    action: str,
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    if action not in ("enable", "disable"):
        raise HTTPException(400, "Acción inválida")

    device = await genieacs.get_device(device_id)
    if not device:
        raise HTTPException(404, "ONU no encontrada")

    wans = read_wan(device)

    wan = next((
        w for w in wans
        if w.get("wan_connection_device") == wcd
        and w.get("object_type") == "WANIPConnection"
        and w.get("instance") == instance
    ), None)

    if not wan:
        raise HTTPException(404, "WAN IP no encontrada")

    if wan.get("protected"):
        raise HTTPException(403, "WAN protegida: contiene TR069")

    desired = action == "enable"

    if wan.get("enabled") is desired:
        return {
            "ok": True,
            "status": "SIN_CAMBIOS",
            "enabled": desired
        }

    path = (
        "InternetGatewayDevice.WANDevice.1."
        f"WANConnectionDevice.{wcd}."
        f"WANIPConnection.{instance}.Enable"
    )

    audit = await add_audit(
        db=db,
        action="WAN_IP_ACTIVAR" if desired else "WAN_IP_DESACTIVAR",
        target_id=device_id,
        before={
            "wcd": wcd,
            "instance": instance,
            "enabled": wan.get("enabled")
        },
        after={
            "wcd": wcd,
            "instance": instance,
            "enabled": desired
        },
        result="SOLICITADO",
        message="Cambio estado WAN IP"
    )

    try:
        await genieacs.set_parameter_value(
            device_id,
            path,
            desired,
            "xsd:boolean"
        )

        confirmed = False

        for _ in range(5):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)
            current_wans = read_wan(current)

            target = next((
                w for w in current_wans
                if w.get("wan_connection_device") == wcd
                and w.get("object_type") == "WANIPConnection"
                and w.get("instance") == instance
            ), None)

            if target and target.get("enabled") is desired:
                confirmed = True
                break

        status = "CONFIRMADO" if confirmed else "PENDIENTE"

        await update_audit(
            db,
            audit,
            status,
            "Estado WAN confirmado" if confirmed
            else "Esperando confirmación ONU"
        )

        return {
            "ok": True,
            "status": status,
            "wcd": wcd,
            "instance": instance,
            "enabled": desired
        }

    except Exception as exc:
        await update_audit(db, audit, "FALLIDO", str(exc))
        raise HTTPException(502, str(exc))


@router.patch("/api/devices/{device_id}/wan/{wcd}/ip/{instance}")
async def edit_ip_wan_wcd(
    device_id: str,
    wcd: int,
    instance: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    from app.services.wan_reader import read_wan
    from app.services.audit_service import add_audit, update_audit

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(404, "ONU no encontrada")

    wans = read_wan(device)

    wan = next((
        w for w in wans
        if w.get("wan_connection_device") == wcd
        and w.get("object_type") == "WANIPConnection"
        and w.get("instance") == instance
    ), None)

    if not wan:
        raise HTTPException(404, "WAN IP no encontrada")

    if wan.get("protected"):
        raise HTTPException(403, "WAN protegida: contiene TR069")

    mode = str(
        wan.get("addressing_type") or "DHCP"
    ).upper()

    base = (
        "InternetGatewayDevice.WANDevice.1."
        f"WANConnectionDevice.{wcd}."
        f"WANIPConnection.{instance}."
    )

    wcd_base = (
        "InternetGatewayDevice.WANDevice.1."
        f"WANConnectionDevice.{wcd}."
    )

    values = []
    requested = {}

    if "vlan" in payload:
        vlan = int(payload["vlan"])

        if not 1 <= vlan <= 4094:
            raise HTTPException(400, "VLAN inválida")

        name = f"{wcd}_INTERNET_R_VID_{vlan}"

        values += [
            [base + "X_CT-COM_VLANIDMark",
             vlan, "xsd:unsignedInt"],

            [wcd_base + "X_CT-COM_WANGponLinkConfig.VLANIDMark",
             vlan, "xsd:unsignedInt"],

            [wcd_base + "WanName",
             name, "xsd:string"],

            [base + "Name",
             name, "xsd:string"],

            [base + "vsName",
             name, "xsd:string"],
        ]

        requested["vlan"] = vlan

    if "priority" in payload:
        priority = int(payload["priority"])

        if not 0 <= priority <= 7:
            raise HTTPException(400, "802.1p inválido")

        values += [
            [base + "X_CT-COM_802-1pMark",
             priority, "xsd:unsignedInt"],

            [wcd_base + "X_CT-COM_WANGponLinkConfig.802-1pMark",
             priority, "xsd:unsignedInt"],
        ]

        requested["priority_8021p"] = priority

    if "nat" in payload:
        nat = bool(payload["nat"])

        values.append([
            base + "NATEnabled",
            nat,
            "xsd:boolean"
        ])

        requested["nat"] = nat

    if "mtu" in payload:
        mtu = int(payload["mtu"])

        if not 576 <= mtu <= 1500:
            raise HTTPException(400, "MTU inválido")

        values.append([
            base + "MaxMTUSize",
            mtu,
            "xsd:unsignedInt"
        ])

        requested["mtu"] = mtu

    if "bindings" in payload:
        bindings = payload["bindings"]

        if not isinstance(bindings, list):
            raise HTTPException(400, "Bindings inválidos")

        binding_string = ",".join(bindings)

        values.append([
            base + "X_CT-COM_LanInterface",
            binding_string,
            "xsd:string"
        ])

        requested["lan_binding"] = binding_string

    if mode == "STATIC":
        fields = {
            "ip": "ExternalIPAddress",
            "subnet_mask": "SubnetMask",
            "gateway": "DefaultGateway",
            "dns": "DNSServers",
        }

        for api_name, parameter in fields.items():
            if api_name in payload:
                value = str(payload[api_name]).strip()

                if not value:
                    raise HTTPException(
                        400,
                        f"{api_name} no puede estar vacío"
                    )

                values.append([
                    base + parameter,
                    value,
                    "xsd:string"
                ])

                requested[api_name] = value

    if not values:
        raise HTTPException(400, "No hay cambios")

    audit = await add_audit(
        db=db,
        action="WAN_EDITAR_IP",
        target_id=device_id,
        before={
            "wcd": wcd,
            "type": wan.get("addressing_type"),
            "vlan": wan.get("vlan"),
            "ip": wan.get("ip"),
            "gateway": wan.get("gateway"),
        },
        after=requested,
        result="SOLICITADO",
        message=f"Editando WAN IP WCD {wcd}"
    )

    try:
        # Huawei: X_CT-COM_* -> X_HW_* (VLAN, prioridad, servicios, interfaces)
        from app.services.wan_driver import huawei_wan
        if huawei_wan(device):
            from app.services.huawei_wan import translate
            values = translate(values)

        await genieacs.set_parameter_values(
            device_id,
            values
        )

        confirmed = False

        for _ in range(5):
            await asyncio.sleep(2)

            current = await genieacs.get_device(device_id)
            current_wans = read_wan(current)

            target = next((
                w for w in current_wans
                if w.get("wan_connection_device") == wcd
                and w.get("object_type") == "WANIPConnection"
                and w.get("instance") == instance
            ), None)

            if target and all(
                target.get(k) == v
                for k, v in requested.items()
            ):
                confirmed = True
                break

        status = "CONFIRMADO" if confirmed else "PENDIENTE"

        await update_audit(
            db,
            audit,
            status,
            "Cambios confirmados" if confirmed
            else "Esperando actualización ONU",
            requested
        )

        return {
            "ok": True,
            "status": status,
            "wcd": wcd,
            "instance": instance
        }

    except Exception as exc:
        await update_audit(db, audit, "FALLIDO", str(exc))
        raise HTTPException(502, str(exc))
