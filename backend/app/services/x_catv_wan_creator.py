"""Crear WAN en ONUs X_CATV (KM1303, SML-702XW, ONT1GE1FE1TV...).

Validado con escrituras reales en una KM1303 (fw V2.1.14),
WAN de prueba en VLAN 999/998, sin tocar la WAN de internet ni la de
gestion.

Lo que hace distinta a esta familia:

- La WAN TR-069 (VLAN 46) no se publica por TR-069: solo aparece en
  X_CATV_WANIndex. wan_reader la arma a partir de ese indice.
- Puede listar un WANConnectionDevice "fantasma": GenieACS lo ve, pero
  sus parametros responden "Invalid parameter name" y un addObject
  dentro termina en too_many_commits. Al crear un WCD nuevo, la ONU
  devuelve ese mismo numero. Por eso nunca se reutiliza un WCD "vacio"
  y el WCD nuevo se reconoce por tener enlace real, no por numero nuevo.
- Tarda ~30 s en abrir sesion tras la connection request. Las tareas se
  encolan juntas y una sola connection request las ejecuta en la misma
  sesion: 3 sesiones en total (~1,5 min).
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.services.vendor_wan import translate
from app.services.wan_reader import has_values
from app.services.x_catv_wan_builder import build_link_values
from app.services.x_ctcom_wan_builder import (
    base_wcd,
    build_dhcp_values,
    build_enable_values,
)

WCD_PATH = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"

# PPPoE bloqueado: en la KM1303 (fw V2.1.14), leer la WANPPPConnection
# recien creada corto la sesion TR-069 y el cliente TR-069 de la ONU dejo
# de responder (puerto 7547 cerrado) hasta reiniciarla.
PPPOE_BLOCKED_MSG = (
    "Crear PPPoE no está habilitado en este modelo de ONU: en la prueba "
    "la ONU dejó de responder a TR-069. Usa DHCP o IP fija."
)

# Espera por sesion. La ONU tarda ~30 s en conectarse.
SESSION_MS = 60000


def _wcds(device):
    try:
        obj = device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]
    except (KeyError, TypeError):
        return {}

    return {int(k): v for k, v in obj.items() if str(k).isdigit() and isinstance(v, dict)}


def _instances(node):
    if not isinstance(node, dict):
        return set()
    return {int(k) for k in node if str(k).isdigit()}


def connection_numbers(device, wcd, container):
    """Conexiones con valores (las "fantasma" no cuentan)."""

    node = _wcds(device).get(wcd, {}).get(container) or {}

    return {
        int(k)
        for k, conn in node.items()
        if str(k).isdigit() and isinstance(conn, dict) and has_values(conn)
    }


def real_wcds(device):
    """WCD que existen de verdad: tienen conexiones con valores o un enlace
    con VLAN numerica. Un fantasma reporta el enlace como "" y sus
    conexiones sin valores."""

    out = set()

    for number, wcd in _wcds(device).items():
        connections = [
            conn
            for container in ("WANIPConnection", "WANPPPConnection")
            for key, conn in (wcd.get(container) or {}).items()
            if str(key).isdigit() and isinstance(conn, dict)
        ]

        if any(has_values(conn) for conn in connections):
            out.add(number)
            continue

        vlan = (wcd.get("X_CATV_WANGponLinkConfig") or {}).get("VLANIDMark")
        value = vlan.get("_value") if isinstance(vlan, dict) else None

        if isinstance(value, int) and not isinstance(value, bool):
            out.add(number)

    return out


async def _session(client, device_id, tasks, check):
    """Encola tasks; la ultima despierta a la ONU. Devuelve check(device)
    en cuanto deja de ser None."""

    for task in tasks[:-1]:
        await client.post_task(device_id, task)

    await client.post_task(device_id, tasks[-1], connection_request=True, wait_ms=SESSION_MS)

    # 200: la sesion ya termino. 202: sigue en cola; se espera un poco mas.
    for _ in range(30):
        device = await client.get_device(device_id)
        found = check(device) if device else None

        if found is not None:
            return found

        await asyncio.sleep(2)

    return None


def now_stamp():
    # Margen de 5 s por diferencia de reloj con GenieACS.
    return (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S")


async def clean_ghost_faults(client, device_id, object_name, since):
    """Tras borrar un WCD, en esa misma sesion la ONU aun lista sus
    parametros pero no entrega valores (9002). Los presets que leen todo
    el arbol fallan una vez; se borran solo esos fallos (los que nombran
    el WCD borrado) para que no queden bloqueados."""

    prefix = object_name.rstrip(".") + "."

    try:
        for fault in await client.get_faults(device_id):
            if (
                str(fault.get("timestamp", "")) >= since
                and prefix in str(fault.get("message", ""))
            ):
                await client.delete_fault(fault["_id"])
    except Exception:
        pass


async def _cleanup(client, device_id, since):
    """Si algo falla, no dejar tareas que GenieACS reintente en cada inform."""

    try:
        for task in await client.get_tasks(device_id):
            if str(task.get("timestamp", "")) >= since:
                await client.delete_task(task["_id"])

        for fault in await client.get_faults(device_id):
            if str(fault.get("timestamp", "")) >= since:
                await client.delete_fault(fault["_id"])
    except Exception:
        pass


async def create_x_catv_wan(client, device_id, data, mode="DHCP"):
    """Crea una WAN DHCP o STATIC en un WCD nuevo y la enciende."""

    mode = str(mode).upper()

    if mode == "PPPOE":
        raise RuntimeError(PPPOE_BLOCKED_MSG)

    if mode not in ("DHCP", "STATIC"):
        raise ValueError("Tipo valido: DHCP o STATIC")

    container = "WANIPConnection"

    def build(wcd, instance):
        return build_dhcp_values(wcd, instance, data, mode=mode)

    # Validar datos (IP fija completa, etc.) antes de tocar la ONU.
    translate(build(0, 0)["parameter_values"], "x_catv")
    build_link_values(0, data)

    device = await client.get_device(device_id)

    if not device:
        raise RuntimeError("ONU no encontrada")

    since = now_stamp()
    before = real_wcds(device)

    try:
        # Sesion 1: crear el WCD y releer la lista.
        def new_wcd(current):
            new = real_wcds(current) - before
            if len(new) > 1:
                raise RuntimeError("Se detectaron varios WANConnectionDevice nuevos")
            return next(iter(new)) if new else None

        wcd = await _session(client, device_id, [
            {"name": "addObject", "objectName": WCD_PATH},
            {"name": "refreshObject", "objectName": WCD_PATH},
        ], new_wcd)

        if wcd is None:
            raise RuntimeError("La ONU no confirmó el nuevo WANConnectionDevice")

        # Sesion 2: VLAN del enlace y crear la conexion.
        base = base_wcd(wcd)
        before_conn = connection_numbers(await client.get_device(device_id), wcd, container)

        def new_conn(current):
            new = connection_numbers(current, wcd, container) - before_conn
            return min(new) if new else None

        instance = await _session(client, device_id, [
            {"name": "setParameterValues", "parameterValues": build_link_values(wcd, data)},
            {"name": "addObject", "objectName": f"{base}.{container}"},
            {"name": "refreshObject", "objectName": f"{base}.{container}"},
        ], new_conn)

        if instance is None:
            raise RuntimeError(f"La ONU no confirmó {container}")

        # Sesion 3: configurar, encender y releer.
        config = build(wcd, instance)
        path = f"{base}.{container}.{instance}"

        def configured(current):
            conn = _wcds(current).get(wcd, {}).get(container, {}).get(str(instance), {})
            name = (conn.get("Name") or {}).get("_value")
            return True if name == config["name"] else None

        await _session(client, device_id, [
            {"name": "setParameterValues",
             "parameterValues": translate(config["parameter_values"], "x_catv")},
            {"name": "setParameterValues",
             "parameterValues": build_enable_values(wcd, container, instance)},
            {"name": "refreshObject", "objectName": path},
        ], configured)

    except Exception:
        await _cleanup(client, device_id, since)
        raise

    return {
        "status": 200,
        "driver": "x_catv_wan",
        "wcd": wcd,
        "instance": instance,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }


async def create_x_catv_pppoe(client, device_id, data):
    raise RuntimeError(PPPOE_BLOCKED_MSG)


async def create_x_catv_dhcp(client, device_id, data, mode="DHCP"):
    return await create_x_catv_wan(client, device_id, data, mode=mode)
