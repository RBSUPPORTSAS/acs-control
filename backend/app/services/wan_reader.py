def unwrap(v):
    if isinstance(v, dict):
        return v.get("_value")
    return v


def field(obj, name):
    if not isinstance(obj, dict):
        return None
    return unwrap(obj.get(name))


def children(obj):
    if not isinstance(obj, dict):
        return []

    return [
        (int(k), v)
        for k, v in obj.items()
        if str(k).isdigit() and isinstance(v, dict)
    ]


# Realtek (IGD, RT9607C, RX8102WT): X_RTK_ServiceType es una mascara de
# bits. Confirmado en las 14 ONUs del GenieACS: 1 en todas las WAN TR-069
# (VLAN 46, la IP del connection request), 2 en internet.
RTK_SERVICE_BITS = (
    (1, "TR069"),
    (2, "INTERNET"),
    (4, "OTHER"),
    (8, "VOICE"),
)


def rtk_services(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    return ",".join(name for bit, name in RTK_SERVICE_BITS if value & bit) or None


def rtk_lan_binding(obj):
    """Realtek: X_RTK_LanInterface = "lan1,lan2,ssid1,ssid5" -> rutas."""

    raw = field(obj, "X_RTK_LanInterface")

    if not raw:
        return None

    paths = []

    for item in str(raw).split(","):
        item = item.strip().lower()

        if item.startswith("lan") and item[3:].isdigit():
            paths.append(f"InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.{item[3:]}")
        elif item.startswith("ssid") and item[4:].isdigit():
            paths.append(f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{item[4:]}")

    return ",".join(paths) or None


def huawei_lan_binding(obj):
    """Huawei: X_HW_LANBIND.Lan1Enable..SSID4Enable (1 = asociada).

    Se convierte al mismo formato que X_CT-COM_LanInterface (rutas
    separadas por comas) para que la interfaz las muestre igual.
    """

    bind = obj.get("X_HW_LANBIND") if isinstance(obj, dict) else None

    if not isinstance(bind, dict):
        return None

    paths = []

    for key in sorted(bind):
        if key.startswith("_") or str(unwrap(bind[key])) not in ("1", "True", "true"):
            continue

        if key.startswith("Lan") and key.endswith("Enable"):
            n = key[3:-6]
            paths.append(f"InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.{n}")

        elif key.startswith("SSID") and key.endswith("Enable"):
            n = key[4:-6]
            paths.append(f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{n}")

    return ",".join(paths) or None


def text_bool(value):
    """Algunos firmwares (X_CMCC, ZY704) reportan booleanos como texto
    "TRUE"/"FALSE"; se convierten para que "FALSE" no cuente como activo."""

    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"

    return value


def read_connection(obj, wcd, instance, kind, wcd_obj=None):

    conn_type = field(obj, "ConnectionType")
    addressing = field(obj, "AddressingType")

    raw_status = field(obj, "ConnectionStatus")
    enabled = text_bool(field(obj, "Enable"))
    external_ip = field(obj, "ExternalIPAddress")
    ppp_session = field(obj, "PPPoESessionID")

    # 0.0.0.0 es "sin IP" (p. ej. Huawei mientras intenta conectar).
    has_ip = external_ip not in (None, "", "0.0.0.0")

    if enabled is False:
        operational_status = "Disabled"

    elif raw_status == "Connected":
        operational_status = "Connected"

    elif (
        kind == "WANPPPConnection"
        and has_ip
        and ppp_session not in (None, 0, "")
    ):
        operational_status = "Connected"

    elif (
        kind == "WANIPConnection"
        and has_ip
    ):
        operational_status = "Connected"

    elif raw_status:
        operational_status = raw_status

    else:
        operational_status = "Unknown"

    if kind == "WANPPPConnection":
        access_type = field(obj, "TransportType") or "PPPoE"
    else:
        access_type = addressing or "IP"

    mode = (
        "Router"
        if conn_type == "IP_Routed"
        else "Bridge"
        if conn_type and "Bridg" in str(conn_type)
        else conn_type
    )

    # ServiceList segun fabricante: CT-COM (VSOL, HG102DWT), X_CATV o
    # X_HW (Huawei). Si no se lee, la WAN TR-069 no quedaria protegida.
    services = field(obj, "X_CT-COM_ServiceList")

    if services in (None, ""):
        services = field(obj, "X_CATV_ServiceList")

    if services in (None, ""):
        services = field(obj, "X_HW_SERVICELIST")

    if services in (None, ""):
        services = rtk_services(field(obj, "X_RTK_ServiceType"))

    if services in (None, ""):
        services = field(obj, "X_CMCC_ServiceList")  # RX8414CDW, ZC-500W

    # Segun el fabricante, la VLAN/802.1p viven en la conexion
    # (X_CT-COM_VLANIDMark, VSOL) o en el WCD: X_CATV_WANGponLinkConfig
    # o X_CT-COM_WANGponLinkConfig (p. ej. HG102DWT).
    link = {}

    if isinstance(wcd_obj, dict):
        link = (
            wcd_obj.get("X_CATV_WANGponLinkConfig")
            or wcd_obj.get("X_CT-COM_WANGponLinkConfig")
            or {}
        )

    vlan = field(obj, "X_CT-COM_VLANIDMark")

    if vlan is None:
        vlan = field(link, "VLANIDMark")

    if vlan is None:
        vlan = field(obj, "X_HW_VLAN")  # Huawei

    if vlan is None:
        vlan = field(obj, "X_RTK_VlanId")  # Realtek

    if vlan is None:
        vlan = field(obj, "X_CMCC_VLANIDMark")  # X_CMCC (RX8414CDW)

    priority = field(obj, "X_CT-COM_802-1pMark")

    if priority is None:
        priority = field(link, "802-1pMark")

    if priority is None:
        priority = field(obj, "X_HW_PRI")  # Huawei

    if priority is None:
        priority = field(obj, "X_RZ_802-1pMark")  # Realtek (IGD)

    if priority is None:
        priority = field(obj, "VlanPriMark")  # Realtek (RX8102WT)

    if priority is None:
        priority = field(obj, "X_CMCC_802-1pMark")  # X_CMCC (RX8414CDW)

    lan_binding = field(
        obj,
        "X_CT-COM_LanInterface"
    )

    if not lan_binding:
        lan_binding = field(
            obj,
            "X_CATV_LanInterface"
        )

    if not lan_binding:
        cmcc_binding = field(obj, "X_CMCC_LanInterface")
        if cmcc_binding is not None:
            lan_binding = cmcc_binding

    if not lan_binding:
        lan_binding = huawei_lan_binding(obj) or rtk_lan_binding(obj) or lan_binding

    if isinstance(services, str):
        services = [
            x.strip()
            for x in services.split(",")
            if x.strip()
        ]
    else:
        services = []

    tr069 = (
        "TR069" in services
        or "TR069" in str(field(obj, "Name") or "").upper().replace("-", "")
    )

    return {
        "wan_connection_device": wcd,
        "instance": instance,
        "object_type": kind,
        "type": access_type,
        "enabled": enabled,
        "status": operational_status,
        "raw_status": raw_status,
        "mode": mode,
        "name": field(obj, "Name") or field(obj, "vsName"),

        "vlan": vlan,
        "priority_8021p": priority,

        "nat": text_bool(field(obj, "NATEnabled")),

        "username": (
            field(obj, "Username")
            if kind == "WANPPPConnection"
            else None
        ),

        "mtu": (
            field(obj, "MaxMRUSize")
            if kind == "WANPPPConnection"
            else field(obj, "MaxMTUSize")
        ),

        "addressing_type": addressing,
        "ip": external_ip,
        "subnet_mask": field(obj, "SubnetMask"),
        "gateway": field(obj, "DefaultGateway"),
        "dns": field(obj, "DNSServers"),

        "services": services,

        # Red de seguridad: tambien se protege si el nombre dice TR069,
        # por si un fabricante reporta el servicio en otro parametro.
        "protected": tr069,
        "protection_reason": (
            "Esta WAN transporta TR-069 y modificarla puede perder la gestión remota."
            if tr069
            else None
        ),

        "lan_binding": lan_binding,
    }


def has_values(obj):
    """True si al menos un parametro directo de la conexion trae valor."""

    return any(
        isinstance(v, dict) and "_value" in v
        for k, v in obj.items()
        if not str(k).startswith("_")
    )


def read_wan(device):

    igd = device.get(
        "InternetGatewayDevice",
        {}
    )

    wan_device = (
        igd.get("WANDevice", {})
        .get("1", {})
    )

    root = wan_device.get(
        "WANConnectionDevice",
        {}
    )

    result = []

    for wcd_id, wcd in children(root):

        for kind in (
            "WANPPPConnection",
            "WANIPConnection",
        ):

            container = wcd.get(kind, {})

            for instance, obj in children(container):

                # X_CATV: tras borrar un WCD la ONU sigue listando sus
                # parametros sin valores. Esa conexion "fantasma" no existe.
                if (
                    isinstance(wcd.get("X_CATV_WANGponLinkConfig"), dict)
                    and not has_values(obj)
                ):
                    continue

                result.append(
                    read_connection(
                        obj,
                        wcd_id,
                        instance,
                        kind,
                        wcd,
                    )
                )

    # Complementar inventario con X_CATV_WANIndex.
    # Algunos equipos reportan WAN especiales (ej. TR069/WCD 0)
    # únicamente a través de este índice.
    indexed = read_x_catv_wan_index(device)

    existing = {
        (
            item.get("wan_connection_device"),
            item.get("instance"),
            item.get("object_type"),
        ): item
        for item in result
    }

    for item in indexed:
        key = (
            item.get("wan_connection_device"),
            item.get("instance"),
            item.get("object_type"),
        )

        current = existing.get(key)

        if current is None:
            result.append(item)
            existing[key] = item
            continue

        # El árbol real sigue siendo la fuente principal.
        # X_CATV_WANIndex solo completa datos ausentes.
        if current.get("vlan") is None:
            current["vlan"] = item.get("vlan")

        if not current.get("services"):
            current["services"] = item.get("services") or []

        if item.get("protected"):
            current["protected"] = True
            current["protection_reason"] = item.get(
                "protection_reason"
            )

    # Realtek RT9607C: el 802.1p vive en Layer2Bridging.Marking del WCD.
    from app.services import l2_marking

    if l2_marking.uses_marking(device):
        for item in result:
            if item.get("priority_8021p") is None and not item.get("synthetic"):
                item["priority_8021p"] = l2_marking.read_priority(
                    device, item.get("wan_connection_device")
                )

    # Red de seguridad para cualquier marca: la WAN cuya IP es la del
    # connection request (la que usa el ACS para hablar con la ONU) es la
    # de gestion, aunque su servicio o nombre no digan TR069.
    management_ip = connection_request_host(device)

    if management_ip:
        for item in result:
            if item.get("ip") == management_ip and not item.get("protected"):
                item["protected"] = True
                item["protection_reason"] = (
                    "Esta WAN es la que usa el ACS para gestionar la ONU; "
                    "modificarla puede perder la gestión remota."
                )

    result.sort(
        key=lambda x: (
            x.get("wan_connection_device", 9999),
            x.get("instance", 9999),
        )
    )

    return result


def connection_request_host(device):
    """IP del ConnectionRequestURL (TR-098 o TR-181), o None."""

    for root in ("InternetGatewayDevice", "Device"):
        url = field(
            (device.get(root) or {}).get("ManagementServer") or {},
            "ConnectionRequestURL",
        )

        if url:
            host = str(url).split("//", 1)[-1].split("/", 1)[0]
            host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
            if host and host not in ("0.0.0.0",):
                return host

    return None

def friendly_bindings(device, raw):
    if not raw:
        return []

    wlan_root = (
        device
        .get("InternetGatewayDevice", {})
        .get("LANDevice", {})
        .get("1", {})
        .get("WLANConfiguration", {})
    )

    result = []

    for path in raw.split(","):
        path = path.strip()

        if "LANEthernetInterfaceConfig." in path:
            index = path.split("LANEthernetInterfaceConfig.")[-1]

            result.append({
                "type": "lan",
                "index": index,
                "label": f"LAN {index}",
            })
            continue

        if "WLANConfiguration." in path:
            index = path.split("WLANConfiguration.")[-1]

            obj = wlan_root.get(index, {})

            ssid = field(obj, "SSID")
            enabled = field(obj, "Enable")
            standard = field(obj, "Standard")

            if standard and "a" in str(standard):
                band = "5 GHz"
            else:
                band = "2.4 GHz"

            result.append({
                "type": "wifi",
                "index": index,
                "band": band,
                "ssid": ssid,
                "enabled": enabled,
                "label": f"{band} · {ssid or ('WLAN ' + index)}",
            })
            continue

        result.append({
            "type": "unknown",
            "label": path,
        })

    return result


def enrich_wan_bindings(device, connections):
    for connection in connections:
        connection["bindings"] = friendly_bindings(
            device,
            connection.get("lan_binding")
        )

    return connections


def read_x_catv_wan_index(device):
    import csv
    import io
    from urllib.parse import urlparse
    from app.services.device_normalizer import online_status

    wan_device = (
        device
        .get("InternetGatewayDevice", {})
        .get("WANDevice", {})
        .get("1", {})
    )

    raw = field(
        wan_device,
        "X_CATV_WANIndex"
    )

    if not raw or not isinstance(raw, str):
        return []

    try:
        rows = next(
            csv.reader(
                io.StringIO(raw),
                skipinitialspace=True
            )
        )
    except Exception:
        return []

    result = []

    management = (
        device
        .get("InternetGatewayDevice", {})
        .get("ManagementServer", {})
    )

    connection_request_url = field(
        management,
        "ConnectionRequestURL"
    )

    acs_url = field(
        management,
        "URL"
    )

    management_mac = field(
        management,
        "mac"
    )

    cwmp_enabled = field(
        management,
        "EnableCWMP"
    )

    nat_detected = field(
        management,
        "NATDetected"
    )

    device_online = online_status(
        device.get("_lastInform")
    )

    management_ip = None

    if connection_request_url:
        try:
            management_ip = urlparse(
                connection_request_url
            ).hostname
        except Exception:
            management_ip = None

    forwarding = (
        device
        .get("InternetGatewayDevice", {})
        .get("Layer3Forwarding", {})
        .get("Forwarding", {})
    )

    for row in rows:
        parts = [
            part.strip()
            for part in row.strip().strip('"').split(";")
        ]

        if len(parts) < 4:
            continue

        instance_id, connection, vlan_raw, service_raw = parts[:4]

        try:
            wcd_raw, instance_raw = instance_id.split(".", 1)
            wcd = int(wcd_raw)
            instance = int(instance_raw)
        except Exception:
            continue

        connection_upper = connection.upper()

        if connection_upper.startswith("PPPOE"):
            object_type = "WANPPPConnection"
            access_type = "PPPoE"
            addressing = None
        elif connection_upper.startswith("DHCP"):
            object_type = "WANIPConnection"
            access_type = "DHCP"
            addressing = "DHCP"
        elif connection_upper.startswith("STATIC"):
            object_type = "WANIPConnection"
            access_type = "Static"
            addressing = "Static"
        else:
            object_type = "WANIPConnection"
            access_type = connection
            addressing = None

        mode = (
            "Router"
            if "ROUTED" in connection_upper
            else "Bridge"
            if "BRIDGE" in connection_upper
            else None
        )

        try:
            vlan = int(vlan_raw)
        except Exception:
            vlan = None

        services = [
            x.strip()
            for x in service_raw.split(",")
            if x.strip()
        ]

        protected = "TR069" in services

        subnet_mask = None
        network = None

        if protected and isinstance(forwarding, dict):

            expected_interface = (
                "InternetGatewayDevice."
                "WANDevice.1."
                f"WANConnectionDevice.{wcd}."
                f"{object_type}.{instance}"
            )

            for route_id, route in forwarding.items():

                if not str(route_id).isdigit():
                    continue

                if not isinstance(route, dict):
                    continue

                interface = field(
                    route,
                    "Interface"
                )

                if interface != expected_interface:
                    continue

                network = field(
                    route,
                    "DestIPAddress"
                )

                subnet_mask = field(
                    route,
                    "DestSubnetMask"
                )

                break

        result.append({
            "wan_connection_device": wcd,
            "instance": instance,
            "object_type": object_type,
            "type": access_type,
            "enabled": (
                cwmp_enabled
                if protected
                else None
            ),
            "status": (
                "Connected"
                if (
                    protected
                    and device_online
                    and management_ip
                    and cwmp_enabled is not False
                )
                else "Unknown"
            ),
            "raw_status": None,
            "mode": mode,
            "name": None,
            "vlan": vlan,
            "priority_8021p": None,
            "nat": None,
            "username": None,
            "mtu": None,
            "addressing_type": addressing,
            "ip": (
                management_ip
                if protected
                else None
            ),
            "subnet_mask": (
                subnet_mask
                if protected
                else None
            ),
            "gateway": None,
            "dns": None,
            "services": services,
            "protected": protected,
            "protection_reason": (
                "Esta WAN transporta TR-069 y modificarla puede perder la gestión remota."
                if protected
                else None
            ),
            "lan_binding": None,
            "bindings": [],
            "source": "X_CATV_WANIndex",
            "synthetic": True,
            "network": (
                network
                if protected
                else None
            ),
            "mac": (
                management_mac
                if protected
                else None
            ),
            "connection_request_url": (
                connection_request_url
                if protected
                else None
            ),
            "acs_url": (
                acs_url
                if protected
                else None
            ),
            "cwmp_enabled": (
                cwmp_enabled
                if protected
                else None
            ),
            "nat_detected": (
                nat_detected
                if protected
                else None
            ),
        })

    return result
