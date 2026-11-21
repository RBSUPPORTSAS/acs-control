"""Inventario de ONUs, detalle, interfaces y etiquetas.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import Depends, APIRouter, HTTPException, Query
from app.services.genieacs import genieacs
from app.services.device_normalizer import NORMALIZE_PROJECTION, normalize_device

from app.api.deps import is_admin, require_network, require_user
from app.core.database import get_db
from app.services.audit_service import add_audit
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.config import settings
from app.services import device_refresh
from app.api.routers.tags import catalog_names, valid_tag_name


router = APIRouter()


# Campos de identidad que GenieACS puede filtrar rapido (estan en el
# documento de la ONU, no en el arbol de parametros). Un $regex sobre un
# parametro (p. ej. SoftwareVersion) puede dejar la consulta colgada.
SEARCH_FIELDS = (
    "_id",
    "_deviceId._SerialNumber",
    "_deviceId._ProductClass",
    "_deviceId._Manufacturer",
    "_deviceId._OUI",
    "_tags",
)

def search_regex(text):
    """Expresion para buscar `text` en GenieACS sin distinguir mayusculas.

    GenieACS 1.2 se cuelga (~26 s y cierra la conexion) con dos formas de
    $regex: con "$options": "i" cuando no hay coincidencias, y cuando el
    texto son solo digitos ("260205", "9782"), que parece leer como numero.
    Por eso: sin $options (cada letra va como [aA]) y envuelto en (?:...).
    """

    import re

    out = []
    for ch in text:
        if ch.isalpha() and ch.lower() != ch.upper():
            out.append(f"[{ch.lower()}{ch.upper()}]")
        else:
            out.append(re.escape(ch))
    return "(?:" + "".join(out) + ")"


# Para IP TR-069 y firmware se revisan, ademas, hasta tantas ONUs.
SEARCH_SCAN_LIMIT = 2000


def _matches(device, search):
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


@router.get("/api/devices", summary="Listar o buscar ONUs")
async def devices(
    limit: int = Query(default=100, ge=1, le=2000),
    q: str | None = Query(
        default=None,
        description="Texto a buscar: serial (o sus ultimos digitos), modelo, fabricante, OUI, etiqueta, IP TR-069 o firmware.",
    ),
):
    """Sin q: las primeras `limit` ONUs. Con q: las que coinciden, hasta `limit`.

    Antes la busqueda filtraba solo dentro de las primeras `limit` ONUs: con
    limit=20 no encontraba una ONU que estuviera mas adelante.
    """

    import re

    search = (q or "").lower().strip()

    try:
        if not search:
            raw_devices = await genieacs.get_devices(
                limit=limit,
                projection=NORMALIZE_PROJECTION,
            )
        else:
            pattern = {"$regex": search_regex(search)}
            raw_devices = await genieacs.get_devices(
                limit=limit,
                projection=NORMALIZE_PROJECTION,
                query={"$or": [{field: pattern} for field in SEARCH_FIELDS]},
            )

            # IP TR-069 y firmware: no se filtran en GenieACS (ver arriba).
            if len(raw_devices) < limit:
                seen = {d.get("_id") for d in raw_devices}
                for device in await genieacs.get_devices(
                    limit=SEARCH_SCAN_LIMIT,
                    projection=NORMALIZE_PROJECTION,
                ):
                    if device.get("_id") not in seen:
                        raw_devices.append(device)

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible consultar GenieACS: {exc}",
        )

    normalized = [
        normalize_device(device)
        for device in raw_devices
    ]

    if search:
        normalized = [d for d in normalized if _matches(d, search)][:limit]

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

    # Errores de presets de GenieACS que dejan la ONU sin procesar tareas.
    try:
        from app.services import genie_health

        response["genieacs"] = await genie_health.health(device_id)
    except Exception:
        response["genieacs"] = None

    if raw:
        response["raw"] = device

    return response


@router.post("/api/devices/{device_id}/genieacs/unblock", dependencies=[Depends(require_network)])
async def device_genieacs_unblock(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Borra los faults de presets de GenieACS y despierta la ONU.

    No cambia nada en la ONU: solo deja que GenieACS vuelva a procesar la
    cola de tareas (lecturas y cambios pendientes).
    """

    from app.services import genie_health

    device = await genieacs.get_device(device_id)

    if not device:
        raise HTTPException(status_code=404, detail="ONU no encontrada")

    before = await genie_health.health(device_id)

    try:
        result = await genie_health.unblock(device_id, device)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible destrabar en GenieACS: {str(exc) or type(exc).__name__}")

    await add_audit(
        db, action="GENIEACS_DESTRABAR", target_id=device_id,
        before={"errores": [f["channel"] + " " + str(f["code"]) for f in before["faults"]], "tareas_en_cola": before["pending_tasks"]},
        after={"borrados": result["cleared"], "onu_respondio": result["answered"], "tareas_en_cola": result["pending_tasks"]},
        result="CONFIRMADO" if result["answered"] else "PENDIENTE",
    )

    return result


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


@router.post("/api/devices/{device_id}/hosts/refresh")
async def device_hosts_refresh(device_id: str):
    """Relee solo los equipos conectados y la señal Wi-Fi (rapido, solo lectura).

    Pide Hosts y cada WLANConfiguration.{i}.AssociatedDevice en la misma
    sesion; espera hasta ~25 s y devuelve los datos nuevos.
    """

    import asyncio
    from app.services.device_refresh import known_heavy
    from app.services.hosts_reader import read_hosts

    device = await genieacs.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="ONU no encontrada")

    skip = known_heavy(device)[1]
    paths = []

    igd = device.get("InternetGatewayDevice")
    if isinstance(igd, dict):
        for li, lan in (igd.get("LANDevice") or {}).items():
            if not str(li).isdigit() or not isinstance(lan, dict):
                continue
            base = f"InternetGatewayDevice.LANDevice.{li}"
            if "Hosts" in lan and not any(f"{base}.Hosts".startswith(x) for x in skip):
                paths.append(f"{base}.Hosts")
            for wi, wlan in (lan.get("WLANConfiguration") or {}).items():
                if str(wi).isdigit() and isinstance(wlan, dict):
                    paths.append(f"{base}.WLANConfiguration.{wi}.AssociatedDevice")

    tr181 = device.get("Device")
    if isinstance(tr181, dict):
        if "Hosts" in tr181:
            paths.append("Device.Hosts")
        for ai, ap in ((tr181.get("WiFi") or {}).get("AccessPoint") or {}).items():
            if str(ai).isdigit():
                paths.append(f"Device.WiFi.AccessPoint.{ai}.AssociatedDevice")

    if not paths:
        return {"device": normalize_device(device), "status": "sin_datos", **read_hosts(device)}

    status = "en_cola"
    try:
        for i, path in enumerate(paths):
            last = i == len(paths) - 1
            code = await genieacs.post_task(
                device_id,
                {"name": "refreshObject", "objectName": path},
                connection_request=last,
                wait_ms=25000,
            )
            if last and code == 200:
                status = "actualizado"
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible pedir la lectura: {str(exc) or type(exc).__name__}")

    device = await genieacs.get_device(device_id) or device

    # Si la ONU no proceso todo (offline o lenta), no dejar tareas colgadas
    # que se ejecuten horas despues.
    if status != "actualizado":
        for task in await genieacs.get_tasks(device_id):
            if task.get("name") == "refreshObject" and task.get("objectName") in paths:
                await genieacs.delete_task(task["_id"])
        await asyncio.sleep(0)

    return {"device": normalize_device(device), "status": status, **read_hosts(device)}


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

@router.post("/api/devices/{device_id}/tags/{tag}", dependencies=[Depends(require_network)])
async def add_device_tag(
    device_id: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_network),
):

    tag = valid_tag_name(tag)

    # Admin puede usar etiquetas libres; technical solo las del catalogo.
    if user.role != "admin" and tag not in await catalog_names(db):
        raise HTTPException(
            status_code=403,
            detail="Solo puede asignar etiquetas del catálogo definido por el administrador",
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


@router.delete("/api/devices/{device_id}/tags/{tag}", dependencies=[Depends(require_network)])
async def delete_device_tag(
    device_id: str,
    tag: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_network),
):

    # Las etiquetas fuera del catalogo pueden activar presets de GenieACS:
    # solo admin las quita.
    if user.role != "admin" and tag not in await catalog_names(db):
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador puede quitar etiquetas fuera del catálogo",
        )

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
