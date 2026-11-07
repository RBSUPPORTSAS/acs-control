"""WAN en ONUs que no usan X_CT-COM_*: Huawei, Realtek y X_CATV.

Validado con escrituras reales (WAN de prueba en VLAN 999/998, sin
afectar las WAN existentes):
- Huawei HG8145V5 HWTC364325A4 (fw V5R019C10S270).
- Realtek/OPTICTIMES IGD 4F505449556E1F25 (fw V15.4.7).

Los constructores existentes arman los valores con nombres X_CT-COM_*;
aqui se traducen al formato de cada fabricante justo antes de enviarlos.
Solo se usa cuando wan_driver detecta "huawei", "realtek", "cmcc" o "x_catv_wan".

X_CATV (KM1303, SML-702XW, ONT1GE1FE1TV...): la VLAN y el 802.1p viven
solo en el WCD (X_CATV_WANGponLinkConfig); el resto cambia de prefijo
(X_CATV_ServiceList, X_CATV_LanInterface con rutas, X_CATV_IPMode).
Validado en KM1303 70A56A54155F (fw V2.1.14).

| Dato        | X_CT-COM (VSOL)        | Huawei            | Realtek              |
|-------------|------------------------|-------------------|----------------------|
| VLAN        | X_CT-COM_VLANIDMark    | X_HW_VLAN         | X_RTK_VlanId (int)   |
| Prioridad   | X_CT-COM_802-1pMark    | X_HW_PRI          | X_RZ_802-1pMark      |
| Servicios   | X_CT-COM_ServiceList   | X_HW_SERVICELIST  | X_RTK_ServiceType    |
|             |                        |                   | (mascara: 1 TR069,   |
|             |                        |                   |  2 INTERNET, 4, 8)   |
| Interfaces  | X_CT-COM_LanInterface  | X_HW_LANBIND.*    | X_RTK_LanInterface   |
|             | (rutas)                | (0/1 por puerto)  | ("lan1,ssid1")       |
"""

from app.services.x_ctcom_wan_builder import (
    base_wcd,
    build_dhcp_values,
    build_enable_values,
    build_pppoe_values,
)
from app.services.x_ctcom_wan_creator import (
    wait_new_connection,
    wait_new_wcd,
    wcd_numbers,
)

# Parametros que en estos fabricantes no existen o no aplican.
DROP = {
    "X_CT-COM_VLANMode",
    "X_CT-COM_IPMode",
    "vsName",
    "WanName",
}

LAN_PREFIX = "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig."
WLAN_PREFIX = "InternetGatewayDevice.LANDevice.1.WLANConfiguration."

RTK_SERVICE_BITS = {"TR069": 1, "INTERNET": 2, "OTHER": 4, "VOICE": 8}


def _interfaces(binding_string):
    """Rutas -> [("lan"|"ssid", "N"), ...]."""

    out = []

    for path in [p.strip() for p in str(binding_string or "").split(",") if p.strip()]:
        if path.startswith(LAN_PREFIX):
            out.append(("lan", path[len(LAN_PREFIX):]))
        elif path.startswith(WLAN_PREFIX):
            out.append(("ssid", path[len(WLAN_PREFIX):]))
        else:
            raise ValueError(f"Interfaz no reconocida: {path}")

    return out


def lanbind_values(conn_base, binding_string):
    """Huawei: X_HW_LANBIND.Lan1..4Enable / SSID1..4Enable (1 asociada)."""

    selected = set()

    for kind, n in _interfaces(binding_string):
        key = "Lan" if kind == "lan" else "SSID"

        if n not in ("1", "2", "3", "4"):
            raise ValueError(
                f"Esta ONU Huawei solo permite asociar {key}1 a {key}4 "
                f"por TR-069 (se pidió {key} {n})"
            )

        selected.add(f"{key}{n}Enable")

    return [
        [f"{conn_base}.X_HW_LANBIND.{name}", 1 if name in selected else 0, "xsd:unsignedInt"]
        for name in (
            [f"Lan{i}Enable" for i in range(1, 5)]
            + [f"SSID{i}Enable" for i in range(1, 5)]
        )
    ]


def rtk_lan_interface(conn_base, binding_string):
    """Realtek: X_RTK_LanInterface = "lan1,lan2,ssid1"."""

    value = ",".join(f"{kind}{n}" for kind, n in _interfaces(binding_string))
    return [[f"{conn_base}.X_RTK_LanInterface", value, "xsd:string"]]


def rtk_service_type(services):
    mask = 0

    for name in str(services or "").split(","):
        name = name.strip().upper()
        if not name:
            continue
        if name not in RTK_SERVICE_BITS:
            raise ValueError(f"Servicio no soportado en esta ONU: {name}")
        mask |= RTK_SERVICE_BITS[name]

    return mask


VENDORS = {
    "huawei": {
        "rename": {
            "X_CT-COM_VLANIDMark": ("X_HW_VLAN", "xsd:unsignedInt"),
            "X_CT-COM_802-1pMark": ("X_HW_PRI", "xsd:unsignedInt"),
            "X_CT-COM_ServiceList": ("X_HW_SERVICELIST", "xsd:string"),
        },
        "interfaces": lanbind_values,
    },
    "x_catv": {
        "rename": {
            "X_CT-COM_ServiceList": ("X_CATV_ServiceList", "xsd:string"),
            "X_CT-COM_IPMode": ("X_CATV_IPMode", "xsd:unsignedInt"),
        },
        # En la conexion no hay VLAN: va en X_CATV_WANGponLinkConfig.
        "drop": {"X_CT-COM_VLANIDMark", "X_CT-COM_802-1pMark"},
        "link": "X_CATV_WANGponLinkConfig",
        "interfaces": lambda conn_base, value: [
            [f"{conn_base}.X_CATV_LanInterface", value, "xsd:string"]
        ],
    },
    "realtek": {
        "rename": {
            "X_CT-COM_VLANIDMark": ("X_RTK_VlanId", "xsd:int"),
            "X_CT-COM_802-1pMark": ("X_RZ_802-1pMark", "xsd:unsignedInt"),
        },
        "interfaces": rtk_lan_interface,
    },
    # X_CMCC (RX8414CDW fw V02.01.02, ZC-500W): mismos nombres que X_CT-COM
    # con otro prefijo; VLAN en la conexion (sin WANGponLinkConfig).
    # X_CMCC_VLANMode 2 = etiquetar con la VLAN (asi estan las WAN de fabrica).
    "cmcc": {
        "rename": {
            "X_CT-COM_VLANIDMark": ("X_CMCC_VLANIDMark", "xsd:int"),
            "X_CT-COM_802-1pMark": ("X_CMCC_802-1pMark", "xsd:int"),
            "X_CT-COM_ServiceList": ("X_CMCC_ServiceList", "xsd:string"),
            "X_CT-COM_IPMode": ("X_CMCC_IPMode", "xsd:int"),
            "X_CT-COM_VLANMode": ("X_CMCC_VLANMode", "xsd:int"),
        },
        "force": {"X_CMCC_VLANMode": 2},
        "interfaces": lambda conn_base, value: [
            [f"{conn_base}.X_CMCC_LanInterface", value, "xsd:string"]
        ],
    },
    # RX8102WT (fw V1.9.2.0-220715): 802.1p en VlanPriMark de la conexion.
    "realtek_vpm": {
        "rename": {
            "X_CT-COM_VLANIDMark": ("X_RTK_VlanId", "xsd:int"),
            "X_CT-COM_802-1pMark": ("VlanPriMark", "xsd:unsignedInt"),
        },
        "interfaces": rtk_lan_interface,
    },
}


def vendor_of(driver):
    """Driver de wan_driver -> clave de VENDORS."""

    return "x_catv" if driver == "x_catv_wan" else driver


def vendor_for(device, driver):
    """Como vendor_of, pero mira la ONU: las Realtek RX8102WT guardan el
    802.1p en VlanPriMark en vez de X_RZ_802-1pMark."""

    vendor = vendor_of(driver)

    if vendor == "realtek" and _has_conn_param(device, "VlanPriMark"):
        return "realtek_vpm"

    return vendor


def _has_conn_param(device, name):
    wcds = (
        (device or {}).get("InternetGatewayDevice", {})
        .get("WANDevice", {}).get("1", {}).get("WANConnectionDevice", {})
    )

    for key, wcd in wcds.items():
        if not str(key).isdigit() or not isinstance(wcd, dict):
            continue
        for container in ("WANIPConnection", "WANPPPConnection"):
            for inst, conn in (wcd.get(container) or {}).items():
                if str(inst).isdigit() and isinstance(conn, dict) and name in conn:
                    return True

    return False


def translate(values, vendor="huawei"):
    """Valores X_CT-COM_* -> nombres del fabricante. Lo demas se descarta."""

    spec = VENDORS[vendor]
    out = []

    for path, value, value_type in values:
        if "WANGponLinkConfig" in path:
            if spec.get("link"):
                out.append([
                    path.replace("X_CT-COM_WANGponLinkConfig", spec["link"]),
                    value,
                    value_type,
                ])
            continue

        conn_base, name = path.rsplit(".", 1)

        if name in spec.get("rename", {}):
            new_name, new_type = spec["rename"][name]
            value = spec.get("force", {}).get(new_name, value)
            out.append([f"{conn_base}.{new_name}", value, new_type])
            continue

        if name in DROP or name in spec.get("drop", ()):
            continue

        if name == "X_CT-COM_LanInterface":
            out.extend(spec["interfaces"](conn_base, value))
            continue

        if name == "X_CT-COM_ServiceList" and vendor in ("realtek", "realtek_vpm"):
            out.append([f"{conn_base}.X_RTK_ServiceType", rtk_service_type(value), "xsd:int"])
            continue

        out.append([path, value, value_type])

    return out


def _connections(device, wcd, container):
    node = (
        (device or {}).get("InternetGatewayDevice", {})
        .get("WANDevice", {}).get("1", {}).get("WANConnectionDevice", {})
        .get(str(wcd), {}).get(container) or {}
    )
    return {int(k) for k, v in node.items() if str(k).isdigit() and isinstance(v, dict)}


async def _add_connection_in_wcd(client, device_id, device, container):
    """Agrega la conexion en el primer WCD existente y devuelve (wcd, instancia)."""

    numbers = sorted(wcd_numbers(device))

    if not numbers:
        raise RuntimeError("La ONU no tiene WANConnectionDevice donde crear la WAN")

    wcd = numbers[0]
    before = _connections(device, wcd, container)
    path = f"{base_wcd(wcd)}.{container}"

    # La ONU tarda ~40 s en sesion: encolar addObject + refresh y esperar.
    await client.post_task(device_id, {"name": "addObject", "objectName": path})
    await client.post_task(
        device_id,
        {"name": "refreshObject", "objectName": path},
        connection_request=True,
        wait_ms=60000,
    )

    import asyncio

    for _ in range(20):
        current = await client.get_device(device_id)
        new = _connections(current, wcd, container) - before

        if new:
            return wcd, min(new)

        await asyncio.sleep(2)

    return wcd, None


async def create_vendor_wan(client, device_id, data, mode="DHCP", vendor="huawei"):
    """Crea una WAN en un WCD nuevo. mode: DHCP, STATIC o PPPOE."""

    mode = str(mode).upper()

    if mode not in ("DHCP", "STATIC", "PPPOE"):
        raise ValueError("Tipo valido: DHCP, STATIC o PPPOE")

    container = "WANPPPConnection" if mode == "PPPOE" else "WANIPConnection"

    def build(wcd, instance):
        if mode == "PPPOE":
            return build_pppoe_values(wcd, instance, data)
        return build_dhcp_values(wcd, instance, data, mode=mode)

    # Validar (incluida la traduccion de interfaces) antes de crear nada.
    translate(build(0, 0)["parameter_values"], vendor)

    device = await client.get_device(device_id)

    if not device:
        raise RuntimeError("ONU no encontrada")

    previous = wcd_numbers(device)
    key = vendor_for(device, vendor)

    if vendor == "cmcc":
        # RX8414CDW: addObject de WANConnectionDevice da cwmp.9002; todas
        # las WAN (tambien la TR-069) son conexiones del mismo WCD.
        wcd, instance = await _add_connection_in_wcd(client, device_id, device, container)
    else:
        await client.add_object(
            device_id,
            "InternetGatewayDevice.WANDevice.1.WANConnectionDevice",
        )

        wcd = await wait_new_wcd(client, device_id, previous)

        if wcd is None:
            raise RuntimeError("La ONU no confirmó el nuevo WANConnectionDevice")

        await client.add_object(device_id, f"{base_wcd(wcd)}.{container}")

        instance = await wait_new_connection(client, device_id, wcd, container, set())

    if instance is None:
        raise RuntimeError(f"La ONU no confirmó {container}")

    # Huawei la crea encendida en VLAN 1; Realtek apagada, en bridge y VLAN 0.
    # Se lee para que GenieACS conozca sus parametros y se configura.
    # (X_CMCC ya la leyo al crearla: se ahorra una sesion de ~40 s.)
    if vendor != "cmcc":
        await client.post_task(
            device_id,
            {"name": "refreshObject", "objectName": f"{base_wcd(wcd)}.{container}.{instance}"},
            connection_request=True,
            wait_ms=10000,
        )

    config = build(wcd, instance)

    await client.set_parameter_values(device_id, translate(config["parameter_values"], key))
    await client.set_parameter_values(device_id, build_enable_values(wcd, container, instance))

    # Releer la conexion: la tarea de encendido puede seguir en cola cuando
    # el endpoint consulta el estado, y mostraria "Disabled".
    await client.post_task(
        device_id,
        {"name": "refreshObject", "objectName": f"{base_wcd(wcd)}.{container}.{instance}"},
        connection_request=True,
        wait_ms=60000 if vendor == "cmcc" else 10000,
    )

    # RT9607C: el 802.1p va en Layer2Bridging.Marking (no hay X_RZ_802-1pMark).
    if vendor == "realtek":
        from app.services import l2_marking

        priority = int(data.get("priority", 0) or 0)

        if priority and l2_marking.uses_marking(await client.get_device(device_id)):
            await l2_marking.apply(client, device_id, wcd, vlan=int(data["vlan"]), priority=priority)

    return {
        "status": 200,
        "driver": vendor,
        "wcd": wcd,
        "instance": instance,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }
