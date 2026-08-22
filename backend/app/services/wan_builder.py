def build_pppoe(data):

    vlan = int(data.get("vlan", 0))
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1492))

    if vlan < 1 or vlan > 4094:
        raise ValueError("VLAN inválida")

    if priority < 0 or priority > 7:
        raise ValueError("802.1p inválido")

    username = str(data.get("username", "")).strip()

    if not username:
        raise ValueError("Usuario PPPoE obligatorio")

    password = str(data.get("password", ""))

    bindings = data.get("bindings", [])

    binding_string = ",".join(bindings)

    object_name = (
        "InternetGatewayDevice."
        "WANDevice.1."
        "WANConnectionDevice.1."
        "WANPPPConnection"
    )

    values = [
        ["Enable", True, "xsd:boolean"],
        ["ConnectionType", "IP_Routed", "xsd:string"],
        ["NATEnabled", bool(data.get("nat", True)), "xsd:boolean"],
        ["Username", username, "xsd:string"],
        ["Password", password, "xsd:string"],
        ["MaxMRUSize", mtu, "xsd:unsignedInt"],
        ["X_CT-COM_VLANIDMark", vlan, "xsd:int"],
        ["X_CT-COM_802-1pMark", priority, "xsd:int"],
        ["X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
    ]

    if binding_string:
        values.append([
            "X_CT-COM_LanInterface",
            binding_string,
            "xsd:string"
        ])

    return {
        "object_name": object_name,
        "connection_type": "PPPoE",
        "parameter_values": values,
    }


def build_dhcp(data):

    vlan = int(data.get("vlan", 0))
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1500))

    if not 1 <= vlan <= 4094:
        raise ValueError("VLAN inválida")

    if not 0 <= priority <= 7:
        raise ValueError("802.1p inválido")

    if not 576 <= mtu <= 1500:
        raise ValueError("MTU inválido")

    bindings = data.get("bindings", [])
    binding_string = ",".join(bindings)

    values = [
        ["Enable", False, "xsd:boolean"],
        ["ConnectionType", "IP_Routed", "xsd:string"],
        ["AddressingType", "DHCP", "xsd:string"],
        ["NATEnabled", bool(data.get("nat", True)), "xsd:boolean"],
        ["MaxMTUSize", mtu, "xsd:unsignedInt"],

        ["X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        ["X_CT-COM_VLANIDMark", vlan, "xsd:unsignedInt"],
        ["X_CT-COM_802-1pMark", priority, "xsd:unsignedInt"],

        ["X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        ["X_CT-COM_ServiceList", "INTERNET", "xsd:string"],

        [
            "Name",
            f"ACS_INTERNET_R_VID_{vlan}",
            "xsd:string"
        ],
    ]

    if binding_string:
        values.append([
            "X_CT-COM_LanInterface",
            binding_string,
            "xsd:string"
        ])

    return {
        "object_name": (
            "InternetGatewayDevice."
            "WANDevice.1."
            "WANConnectionDevice.1."
            "WANIPConnection"
        ),
        "connection_type": "DHCP",
        "parameter_values": values,
    }
