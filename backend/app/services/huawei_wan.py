"""WAN en ONUs Huawei (HG8145V5, HG8546M...).

Validado en una HG8145V5 real (fw V5R019C10S270): crear, editar y
eliminar WAN DHCP, IP fija y PPPoE en VLAN de prueba, sin afectar las WAN
existentes.

Huawei no usa los parametros X_CT-COM_* ni X_CT-COM_WANGponLinkConfig:
- VLAN y prioridad: X_HW_VLAN y X_HW_PRI en la conexion.
- Servicios: X_HW_SERVICELIST.
- Interfaces asociadas: X_HW_LANBIND.Lan1..4Enable / SSID1..4Enable (0/1).

En vez de duplicar los constructores, los valores que arman los
constructores existentes se traducen aqui antes de enviarlos. Solo se
usa cuando la ONU es Huawei (wan_driver.huawei_wan).
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

RENAME = {
    "X_CT-COM_VLANIDMark": ("X_HW_VLAN", "xsd:unsignedInt"),
    "X_CT-COM_802-1pMark": ("X_HW_PRI", "xsd:unsignedInt"),
    "X_CT-COM_ServiceList": ("X_HW_SERVICELIST", "xsd:string"),
}

# Parametros que en Huawei no existen o no aplican.
DROP = {
    "X_CT-COM_VLANMode",
    "X_CT-COM_IPMode",
    "vsName",
    "WanName",
}

LAN_PREFIX = "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig."
WLAN_PREFIX = "InternetGatewayDevice.LANDevice.1.WLANConfiguration."


def lanbind_values(conn_base, binding_string):
    """Ruta de cada interfaz -> X_HW_LANBIND.*Enable (1 asociada, 0 no)."""

    selected = set()

    for path in [p.strip() for p in str(binding_string or "").split(",") if p.strip()]:
        if path.startswith(LAN_PREFIX):
            key, n = "Lan", path[len(LAN_PREFIX):]
        elif path.startswith(WLAN_PREFIX):
            key, n = "SSID", path[len(WLAN_PREFIX):]
        else:
            raise ValueError(f"Interfaz no reconocida: {path}")

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


def translate(values):
    """Valores X_CT-COM_* -> nombres Huawei. Lo que no aplica se descarta."""

    out = []

    for path, value, value_type in values:
        if "WANGponLinkConfig" in path:
            continue

        conn_base, name = path.rsplit(".", 1)

        if name in DROP:
            continue

        if name == "X_CT-COM_LanInterface":
            out.extend(lanbind_values(conn_base, value))
            continue

        if name in RENAME:
            new_name, new_type = RENAME[name]
            out.append([f"{conn_base}.{new_name}", value, new_type])
            continue

        out.append([path, value, value_type])

    return out


async def create_huawei_wan(client, device_id, data, mode="DHCP"):
    """Crea una WAN en un WCD nuevo. mode: DHCP, STATIC o PPPOE."""

    mode = str(mode).upper()

    if mode not in ("DHCP", "STATIC", "PPPOE"):
        raise ValueError("Tipo valido: DHCP, STATIC o PPPOE")

    container = "WANPPPConnection" if mode == "PPPOE" else "WANIPConnection"

    def build(wcd, instance):
        if mode == "PPPOE":
            return build_pppoe_values(wcd, instance, data)
        return build_dhcp_values(wcd, instance, data, mode=mode)

    # Validar (y la traduccion de interfaces) antes de crear nada en la ONU.
    translate(build(0, 0)["parameter_values"])

    device = await client.get_device(device_id)

    if not device:
        raise RuntimeError("ONU no encontrada")

    previous = wcd_numbers(device)

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

    # Huawei crea la conexion ya encendida en VLAN 1: se lee para que
    # GenieACS conozca sus parametros y se configura de inmediato.
    await client.post_task(
        device_id,
        {"name": "refreshObject", "objectName": f"{base_wcd(wcd)}.{container}.{instance}"},
        connection_request=True,
        wait_ms=10000,
    )

    config = build(wcd, instance)

    await client.set_parameter_values(device_id, translate(config["parameter_values"]))
    await client.set_parameter_values(device_id, build_enable_values(wcd, container, instance))

    return {
        "status": 200,
        "driver": "huawei",
        "wcd": wcd,
        "instance": instance,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }
