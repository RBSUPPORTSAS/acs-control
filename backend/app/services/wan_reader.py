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


def read_connection(obj, wcd, instance, kind, wcd_obj=None):

    conn_type = field(obj, "ConnectionType")
    addressing = field(obj, "AddressingType")

    raw_status = field(obj, "ConnectionStatus")
    enabled = field(obj, "Enable")
    external_ip = field(obj, "ExternalIPAddress")
    ppp_session = field(obj, "PPPoESessionID")

    if enabled is False:
        operational_status = "Disabled"

    elif raw_status == "Connected":
        operational_status = "Connected"

    elif (
        kind == "WANPPPConnection"
        and external_ip
        and ppp_session not in (None, 0, "")
    ):
        operational_status = "Connected"

    elif (
        kind == "WANIPConnection"
        and external_ip
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

    # ServiceList puede usar CT-COM o X_CATV
    services = field(obj, "X_CT-COM_ServiceList")

    if services in (None, ""):
        services = field(obj, "X_CATV_ServiceList")

    # En X_CATV la VLAN/802.1p viven en el WCD, no en la conexión.
    link = {}

    if isinstance(wcd_obj, dict):
        link = wcd_obj.get(
            "X_CATV_WANGponLinkConfig",
            {}
        )

    vlan = field(obj, "X_CT-COM_VLANIDMark")

    if vlan is None:
        vlan = field(link, "VLANIDMark")

    priority = field(obj, "X_CT-COM_802-1pMark")

    if priority is None:
        priority = field(link, "802-1pMark")

    lan_binding = field(
        obj,
        "X_CT-COM_LanInterface"
    )

    if not lan_binding:
        lan_binding = field(
            obj,
            "X_CATV_LanInterface"
        )

    if isinstance(services, str):
        services = [
            x.strip()
            for x in services.split(",")
            if x.strip()
        ]
    else:
        services = []

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

        "nat": field(obj, "NATEnabled"),

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

        "protected": "TR069" in services,
        "protection_reason": (
            "Esta WAN transporta TR-069 y modificarla puede perder la gestión remota."
            if "TR069" in services
            else None
        ),

        "lan_binding": lan_binding,
    }


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

    result.sort(
        key=lambda x: (
            x.get("wan_connection_device", 9999),
            x.get("instance", 9999),
        )
    )

    return result

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
