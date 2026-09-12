def base_wcd(wcd):
    return (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )


def build_link_values(wcd, data):
    vlan = int(data["vlan"])
    priority = int(data.get("priority", 0))

    link = (
        f"{base_wcd(wcd)}."
        "X_CT-COM_WANGponLinkConfig"
    )

    return [
        [f"{link}.Enable", True, "xsd:boolean"],
        [f"{link}.Mode", 2, "xsd:unsignedInt"],
        [f"{link}.VLANIDMark", vlan, "xsd:unsignedInt"],
        [f"{link}.802-1pMark", priority, "xsd:unsignedInt"],
    ]


def build_pppoe_values(wcd, instance, data):
    vlan = int(data["vlan"])
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1492))

    base = (
        f"{base_wcd(wcd)}."
        f"WANPPPConnection.{instance}"
    )

    name = f"ACS_INTERNET_R_VID_{vlan}"

    values = [
        [f"{base}.Enable", False, "xsd:boolean"],
        [f"{base}.ConnectionType", "IP_Routed", "xsd:string"],
        [f"{base}.NATEnabled", bool(data.get("nat", True)), "xsd:boolean"],
        [f"{base}.Username", data["username"], "xsd:string"],
        [f"{base}.Password", data["password"], "xsd:string"],
        [f"{base}.MaxMRUSize", mtu, "xsd:unsignedInt"],

        [f"{base}.X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_VLANIDMark", vlan, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_802-1pMark", priority, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],

        [f"{base}.Name", name, "xsd:string"],
    ]

    bindings = data.get("bindings") or []

    if bindings:
        values.append([
            f"{base}.X_CT-COM_LanInterface",
            ",".join(bindings),
            "xsd:string",
        ])

    return {
        "name": name,
        "parameter_values": values,
    }


def build_dhcp_values(wcd, instance, data):
    vlan = int(data["vlan"])
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1500))

    base = (
        f"{base_wcd(wcd)}."
        f"WANIPConnection.{instance}"
    )

    name = f"ACS_INTERNET_DHCP_R_VID_{vlan}"

    values = [
        [f"{base}.Enable", False, "xsd:boolean"],
        [f"{base}.ConnectionType", "IP_Routed", "xsd:string"],
        [f"{base}.AddressingType", "DHCP", "xsd:string"],
        [f"{base}.NATEnabled", bool(data.get("nat", True)), "xsd:boolean"],
        [f"{base}.MaxMTUSize", mtu, "xsd:unsignedInt"],

        [f"{base}.X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_VLANIDMark", vlan, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_802-1pMark", priority, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],

        [f"{base}.Name", name, "xsd:string"],
    ]

    bindings = data.get("bindings") or []

    if bindings:
        values.append([
            f"{base}.X_CT-COM_LanInterface",
            ",".join(bindings),
            "xsd:string",
        ])

    return {
        "name": name,
        "parameter_values": values,
    }
