"""802.1p en Layer2Bridging.Marking (Realtek RT9607C fw -1.2.0.30).

Esta ONU no tiene X_RZ_802-1pMark en la conexion. La prioridad (y una
copia de la VLAN) vive en una marca de Layer2Bridging que apunta al WCD:

  AvailableInterface.{k}.InterfaceReference = ...WANConnectionDevice.{wcd}
  Marking.{m}.MarkingInterface = "{k}"
  Marking.{m}.EthernetPriorityMark = 802.1p   (-1 = sin marcar)
  Marking.{m}.VLANIDMark = VLAN, VLANIDMarkOverride = True

La interfaz web de la ONU crea esa marca al configurar el 802.1p; al
crear una WAN por TR-069 la ONU registra el WCD en AvailableInterface
pero no crea la marca. Validado en una RT9607C de laboratorio: addObject Marking +
setParameterValues, la ONU la guarda igual que la de su interfaz web.
"""

L2 = "InternetGatewayDevice.Layer2Bridging"
WCD_PREFIX = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice."


def _val(node, name):
    item = node.get(name) if isinstance(node, dict) else None
    return item.get("_value") if isinstance(item, dict) else None


def _children(node):
    return [
        (k, v) for k, v in (node or {}).items()
        if str(k).isdigit() and isinstance(v, dict)
    ]


def _l2(device):
    return (device or {}).get("InternetGatewayDevice", {}).get("Layer2Bridging") or {}


def uses_marking(device):
    """True si la prioridad va en Layer2Bridging: Realtek sin
    X_RZ_802-1pMark en ninguna conexion y con tabla Marking."""

    igd = (device or {}).get("InternetGatewayDevice", {})
    wcds = igd.get("WANDevice", {}).get("1", {}).get("WANConnectionDevice", {})
    rtk = False

    for _, wcd in _children(wcds):
        for container in ("WANIPConnection", "WANPPPConnection"):
            for _, conn in _children(wcd.get(container)):
                if "X_RZ_802-1pMark" in conn:
                    return False
                rtk = rtk or "X_RTK_VlanId" in conn

    return rtk and isinstance(_l2(device).get("Marking"), dict)


def interface_key(device, wcd):
    """Clave de AvailableInterface del WCD (no de la conexion)."""

    target = f"{WCD_PREFIX}{wcd}"

    for _, item in _children(_l2(device).get("AvailableInterface")):
        ref = str(_val(item, "InterfaceReference") or "").rstrip(".")
        if ref == target:
            key = _val(item, "AvailableInterfaceKey")
            return str(key) if key is not None else None

    return None


def find_marking(device, wcd):
    """(instancia, nodo) de la marca activa del WCD, o (None, None)."""

    key = interface_key(device, wcd)

    if key is None:
        return None, None

    for number, mark in _children(_l2(device).get("Marking")):
        if str(_val(mark, "MarkingInterface")) == key and _val(mark, "MarkingEnable") is True:
            return number, mark

    return None, None


def read_priority(device, wcd):
    _, mark = find_marking(device, wcd)
    value = _val(mark, "EthernetPriorityMark") if mark else None

    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 7:
        return value

    return None


def marking_values(number, key=None, vlan=None, priority=None):
    base = f"{L2}.Marking.{number}"
    values = []

    if key is not None:
        values += [
            [f"{base}.MarkingBridgeReference", 0, "xsd:int"],
            [f"{base}.MarkingInterface", str(key), "xsd:string"],
            [f"{base}.VLANIDMarkOverride", True, "xsd:boolean"],
            [f"{base}.VLANIDUntag", False, "xsd:boolean"],
        ]

    if vlan is not None:
        values.append([f"{base}.VLANIDMark", int(vlan), "xsd:int"])

    if priority is not None:
        values.append([f"{base}.EthernetPriorityMark", int(priority), "xsd:int"])

    if key is not None:
        values.append([f"{base}.MarkingEnable", True, "xsd:boolean"])

    return values


async def apply(client, device_id, wcd, vlan=None, priority=None):
    """Escribe VLAN/802.1p en la marca del WCD; la crea si no existe y
    hay prioridad que guardar. Devuelve la instancia de la marca o None."""

    if vlan is None and priority is None:
        return None

    async def reread(path):
        await client.post_task(
            device_id,
            {"name": "refreshObject", "objectName": path},
            connection_request=True,
            wait_ms=30000,
        )
        return await client.get_device(device_id)

    device = await client.get_device(device_id)
    number, mark = find_marking(device, wcd)

    if number is not None:
        values = marking_values(number, vlan=vlan, priority=priority)
        await client.post_task(
            device_id,
            {"name": "setParameterValues", "parameterValues": values},
            connection_request=True,
            wait_ms=30000,
        )
        return number

    # Sin marca: solo se crea si hay prioridad (la VLAN ya va en X_RTK_VlanId).
    if priority is None:
        return None

    key = interface_key(device, wcd)

    if key is None:
        device = await reread(f"{L2}.AvailableInterface")
        key = interface_key(device, wcd)

    if key is None:
        raise RuntimeError("La ONU no registró la WAN en Layer2Bridging; no se pudo guardar el 802.1p")

    before = {n for n, _ in _children(_l2(device).get("Marking"))}

    await client.post_task(device_id, {"name": "addObject", "objectName": f"{L2}.Marking"})
    device = await reread(f"{L2}.Marking")
    new = sorted({n for n, _ in _children(_l2(device).get("Marking"))} - before, key=int)

    if not new:
        raise RuntimeError("La ONU no confirmó la marca de 802.1p en Layer2Bridging")

    number = new[0]

    if vlan is None:
        conn = _vlan_of(device, wcd)
        vlan = conn if conn is not None else -1

    await client.post_task(
        device_id,
        {"name": "setParameterValues",
         "parameterValues": marking_values(number, key=key, vlan=vlan, priority=priority)},
        connection_request=True,
        wait_ms=30000,
    )

    return number


def _vlan_of(device, wcd):
    igd = (device or {}).get("InternetGatewayDevice", {})
    node = igd.get("WANDevice", {}).get("1", {}).get("WANConnectionDevice", {}).get(str(wcd), {})

    for container in ("WANIPConnection", "WANPPPConnection"):
        for _, conn in _children(node.get(container)):
            vlan = _val(conn, "X_RTK_VlanId")
            if vlan is not None:
                return vlan

    return None


def wcd_keys(device, wcd):
    """Claves de AvailableInterface del WCD y de sus conexiones."""

    target = f"{WCD_PREFIX}{wcd}"
    keys = set()

    for _, item in _children(_l2(device).get("AvailableInterface")):
        ref = str(_val(item, "InterfaceReference") or "").rstrip(".")
        if ref == target or ref.startswith(target + "."):
            key = _val(item, "AvailableInterfaceKey")
            if key is not None:
                keys.add(str(key))

    return keys


async def remove(client, device_id, device, wcd):
    """Antes de borrar un WCD: borrar su marca (la ONU la deja huerfana
    con interfaz vacia) y los filtros de puente de sus interfaces (la ONU
    tambien los deja). Solo se encolan; corren en la sesion del borrado."""

    # Releer la tabla: la ONU agrega filtros al crear la WAN y el cache de
    # GenieACS puede no conocerlos.
    await client.post_task(
        device_id,
        {"name": "refreshObject", "objectName": L2},
        connection_request=True,
        wait_ms=30000,
    )
    device = await client.get_device(device_id) or device

    keys = wcd_keys(device, wcd)
    removed = []

    for table, field in (("Marking", "MarkingInterface"), ("Filter", "FilterInterface")):
        for number, item in _children(_l2(device).get(table)):
            if str(_val(item, field)) in keys:
                await client.post_task(
                    device_id,
                    {"name": "deleteObject", "objectName": f"{L2}.{table}.{number}"},
                )
                removed.append(f"{table}.{number}")

    return removed
