"""ZTE F6600P: asociar puertos LAN / SSID a una WAN.

La ONU no usa un parametro en la conexion (como X_CT-COM_LanInterface) sino
una tabla aparte:

    InternetGatewayDevice.X_ZTE-COM_PortBinding.{i}.
        WANInterface  ruta de la conexion (…WANConnectionDevice.1.WANIPConnection.2)
        LANInterface  rutas separadas por coma (…LANEthernetInterfaceConfig.4,
                      …WLANConfiguration.5), mismo formato que X_CT-COM_LanInterface

Validado en una F6600P (fw V9.0.10P6N44, 2026-11-19): la ONU acepta LAN y
SSID en la misma entrada y responde cwmp.9003 a rutas inexistentes. La tabla
viene vacia de fabrica y GenieACS no la lee si no se pide (rama propia).
"""

import asyncio

ROOT = "InternetGatewayDevice.X_ZTE-COM_PortBinding"


class PortBindingError(RuntimeError):
    pass


def _value(node, name):
    v = (node or {}).get(name)
    return v.get("_value") if isinstance(v, dict) else None


def entries(device):
    """{instancia: (wan_path, [lan_paths])} de la tabla de la ONU."""

    table = (device or {}).get("InternetGatewayDevice", {}).get("X_ZTE-COM_PortBinding") or {}
    out = {}

    for key, node in table.items():
        if not str(key).isdigit() or not isinstance(node, dict):
            continue
        wan = str(_value(node, "WANInterface") or "").strip().rstrip(".")
        lans = [p.strip() for p in str(_value(node, "LANInterface") or "").split(",") if p.strip()]
        out[int(key)] = (wan, lans)

    return out


def binding_for(device, conn_path):
    """LANInterface de la WAN (cadena con comas) o None si no tiene."""

    conn_path = conn_path.rstrip(".")

    for wan, lans in entries(device).values():
        if wan == conn_path and lans:
            return ",".join(lans)

    return None


async def _refresh(client, device_id):
    await client.post_task(
        device_id,
        {"name": "refreshObject", "objectName": ROOT},
        connection_request=True,
        wait_ms=15000,
    )
    return await client.get_device(device_id)


async def _set(client, device_id, values):
    sent = await client.set_parameter_values(device_id, values, wait_ms=15000)
    task_id = (sent or {}).get("task_id")

    if not task_id:
        return

    for fault in await client.get_faults(device_id):
        if str(fault.get("_id", "")).endswith(f"task_{task_id}"):
            await client.delete_fault(fault["_id"])
            await client.delete_task(task_id)
            detail = fault.get("detail") or {}
            raise PortBindingError(
                "La ONU rechazó la asociación de puertos "
                f"({fault.get('code')}: {detail.get('faultString') or fault.get('message') or ''})"
            )


async def _delete_entry(client, device_id, instance):
    await client.post_task(
        device_id,
        {"name": "deleteObject", "objectName": f"{ROOT}.{instance}"},
        connection_request=True,
        wait_ms=15000,
    )


async def apply(client, device_id, conn_path, binding_string):
    """Deja la WAN conn_path asociada exactamente a binding_string.

    Un puerto solo puede ir a una WAN: si estaba en otra entrada se le quita
    de alli (y la entrada se borra si queda vacia).
    """

    conn_path = conn_path.rstrip(".")
    wanted = [p.strip() for p in str(binding_string or "").split(",") if p.strip()]

    device = await _refresh(client, device_id)
    table = entries(device)

    mine = [i for i, (wan, _) in table.items() if wan == conn_path]

    # Quitar los puertos pedidos de las entradas de otras WAN.
    for instance, (wan, lans) in table.items():
        if wan == conn_path:
            continue
        rest = [p for p in lans if p not in wanted]
        if rest == lans:
            continue
        if rest:
            await _set(client, device_id, [[f"{ROOT}.{instance}.LANInterface", ",".join(rest), "xsd:string"]])
        else:
            await _delete_entry(client, device_id, instance)

    # Sin puertos: borrar la(s) entrada(s) de esta WAN.
    if not wanted:
        for instance in mine:
            await _delete_entry(client, device_id, instance)
        await _refresh(client, device_id)
        return

    for extra in mine[1:]:
        await _delete_entry(client, device_id, extra)

    if mine:
        instance = mine[0]
    else:
        before = set(table)
        await client.post_task(
            device_id,
            {"name": "addObject", "objectName": ROOT},
            connection_request=True,
            wait_ms=15000,
        )
        instance = None
        for _ in range(5):
            new = set(entries(await _refresh(client, device_id))) - before
            if new:
                instance = min(new)
                break
            await asyncio.sleep(2)
        if instance is None:
            raise PortBindingError("La ONU no confirmó la nueva entrada de asociación de puertos")

    try:
        await _set(client, device_id, [
            [f"{ROOT}.{instance}.WANInterface", conn_path, "xsd:string"],
            [f"{ROOT}.{instance}.LANInterface", ",".join(wanted), "xsd:string"],
        ])
    except PortBindingError:
        # No dejar una entrada vacia creada por nosotros.
        if not mine:
            await _delete_entry(client, device_id, instance)
        raise

    await _refresh(client, device_id)


async def remove_for(client, device_id, device, conn_path):
    """Al borrar una WAN: quitar su entrada (la ONU no la limpia sola)."""

    conn_path = conn_path.rstrip(".")
    for instance, (wan, _) in entries(device).items():
        if wan == conn_path:
            await _delete_entry(client, device_id, instance)
