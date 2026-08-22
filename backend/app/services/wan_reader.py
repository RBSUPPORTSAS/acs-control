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


def read_connection(obj, wcd, instance, kind):

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

    services = field(obj, "X_CT-COM_ServiceList")

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

        "vlan": field(obj, "X_CT-COM_VLANIDMark"),
        "priority_8021p": field(obj, "X_CT-COM_802-1pMark"),

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

        "lan_binding": field(
            obj,
            "X_CT-COM_LanInterface"
        ),
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
