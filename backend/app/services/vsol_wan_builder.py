def validate_common(data):
    vlan = int(data.get("vlan", 0))
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1500))

    if not 1 <= vlan <= 4094:
        raise ValueError("VLAN inválida")

    if not 0 <= priority <= 7:
        raise ValueError("802.1p inválido")

    if not 576 <= mtu <= 1500:
        raise ValueError("MTU inválido")

    return vlan, priority, mtu


def build_vsol_ip(wcd, data):
    vlan, priority, mtu = validate_common(data)

    mode = str(data.get("addressing_type", "DHCP")).upper()

    if mode not in ("DHCP", "STATIC"):
        raise ValueError("Tipo válido: DHCP o STATIC")

    name = f"{wcd}_INTERNET_R_VID_{vlan}"

    base = (
        "InternetGatewayDevice.WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    link_values = [
        [f"{base}.WanName", name, "xsd:string"],

        [
            f"{base}.X_CT-COM_WANGponLinkConfig.Enable",
            True,
            "xsd:boolean"
        ],
        [
            f"{base}.X_CT-COM_WANGponLinkConfig.Mode",
            2,
            "xsd:unsignedInt"
        ],
        [
            f"{base}.X_CT-COM_WANGponLinkConfig.VLANIDMark",
            vlan,
            "xsd:unsignedInt"
        ],
        [
            f"{base}.X_CT-COM_WANGponLinkConfig.802-1pMark",
            priority,
            "xsd:unsignedInt"
        ],
    ]

    return {
        "wcd": wcd,
        "name": name,
        "mode": mode,
        "vlan": vlan,
        "priority": priority,
        "mtu": mtu,
        "base": base,
        "link_values": link_values,
    }


def build_vsol_wanip(wcd, instance, data):
    common = build_vsol_ip(wcd, data)

    mode = common["mode"]
    base = (
        f'{common["base"]}.'
        f'WANIPConnection.{instance}'
    )

    bindings = data.get("bindings", [])

    values = [
        [f"{base}.Enable", False, "xsd:boolean"],
        [f"{base}.ConnectionType", "IP_Routed", "xsd:string"],
        [
            f"{base}.AddressingType",
            "Static" if mode == "STATIC" else "DHCP",
            "xsd:string"
        ],

        [
            f"{base}.NATEnabled",
            bool(data.get("nat", True)),
            "xsd:boolean"
        ],

        [
            f"{base}.MaxMTUSize",
            common["mtu"],
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_VLANMode",
            1,
            "xsd:unsignedInt"
        ],
        [
            f"{base}.X_CT-COM_VLANIDMark",
            common["vlan"],
            "xsd:unsignedInt"
        ],
        [
            f"{base}.X_CT-COM_802-1pMark",
            common["priority"],
            "xsd:unsignedInt"
        ],
        [
            f"{base}.X_CT-COM_IPMode",
            1,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_ServiceList",
            "INTERNET",
            "xsd:string"
        ],

        [
            f"{base}.X_CT-COM_LanInterface",
            ",".join(bindings),
            "xsd:string"
        ],

        # VSOL lo deja true tanto en DHCP como Static.
        [
            f"{base}.X_CT-COM_LanInterface-DHCPEnable",
            True,
            "xsd:boolean"
        ],

        [f"{base}.Name", common["name"], "xsd:string"],
        [f"{base}.vsName", common["name"], "xsd:string"],
    ]

    if mode == "STATIC":
        required = (
            "ip",
            "subnet_mask",
            "gateway",
            "dns",
        )

        missing = [
            key for key in required
            if not str(data.get(key, "")).strip()
        ]

        if missing:
            raise ValueError(
                "Faltan datos Static: "
                + ", ".join(missing)
            )

        values.extend([
            [
                f"{base}.ExternalIPAddress",
                data["ip"],
                "xsd:string"
            ],
            [
                f"{base}.SubnetMask",
                data["subnet_mask"],
                "xsd:string"
            ],
            [
                f"{base}.DefaultGateway",
                data["gateway"],
                "xsd:string"
            ],
            [
                f"{base}.DNSServers",
                data["dns"],
                "xsd:string"
            ],
        ])

    return {
        **common,
        "instance": instance,
        "parameter_values": values,
    }


def build_vsol_pppoe(wcd, instance, data):
    vlan = int(data.get("vlan", 0))
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1492))

    if not 1 <= vlan <= 4094:
        raise ValueError("VLAN inválida")

    if not 0 <= priority <= 7:
        raise ValueError("802.1p inválido")

    if not 576 <= mtu <= 1492:
        raise ValueError("MTU PPPoE inválido")

    username = str(data.get("username", "")).strip()

    if not username:
        raise ValueError("Usuario PPPoE obligatorio")

    password = str(data.get("password", ""))

    name = f"{wcd}_INTERNET_R_VID_{vlan}"

    wcd_base = (
        "InternetGatewayDevice.WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    base = (
        f"{wcd_base}."
        f"WANPPPConnection.{instance}"
    )

    bindings = ",".join(
        data.get("bindings", [])
    )

    link_values = [
        [f"{wcd_base}.WanName", name, "xsd:string"],

        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.Enable",
            True,
            "xsd:boolean"
        ],
        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.Mode",
            2,
            "xsd:unsignedInt"
        ],
        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.VLANIDMark",
            vlan,
            "xsd:unsignedInt"
        ],
        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.802-1pMark",
            priority,
            "xsd:unsignedInt"
        ],
    ]

    values = [
        [f"{base}.Enable", False, "xsd:boolean"],

        [
            f"{base}.ConnectionType",
            "IP_Routed",
            "xsd:string"
        ],

        [
            f"{base}.ConnectionTrigger",
            "AlwaysOn",
            "xsd:string"
        ],

        [
            f"{base}.NATEnabled",
            bool(data.get("nat", True)),
            "xsd:boolean"
        ],

        [
            f"{base}.Username",
            username,
            "xsd:string"
        ],

        [
            f"{base}.Password",
            password,
            "xsd:string"
        ],

        [
            f"{base}.MaxMRUSize",
            mtu,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_VLANMode",
            1,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_VLANIDMark",
            vlan,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_802-1pMark",
            priority,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_IPMode",
            1,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_ServiceList",
            "INTERNET",
            "xsd:string"
        ],

        [
            f"{base}.X_CT-COM_LanInterface",
            bindings,
            "xsd:string"
        ],

        [
            f"{base}.X_CT-COM_LanInterface-DHCPEnable",
            True,
            "xsd:boolean"
        ],

        [f"{base}.Name", name, "xsd:string"],
        [f"{base}.vsName", name, "xsd:string"],
    ]

    return {
        "wcd": wcd,
        "instance": instance,
        "name": name,
        "vlan": vlan,
        "priority": priority,
        "mtu": mtu,
        "link_values": link_values,
        "parameter_values": values,
    }


def build_vsol_pppoe(wcd, instance, data):
    vlan = int(data.get("vlan", 0))
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1492))

    if not 1 <= vlan <= 4094:
        raise ValueError("VLAN inválida")

    if not 0 <= priority <= 7:
        raise ValueError("802.1p inválido")

    if not 576 <= mtu <= 1492:
        raise ValueError("MTU PPPoE inválido")

    username = str(data.get("username", "")).strip()

    if not username:
        raise ValueError("Usuario PPPoE obligatorio")

    password = str(data.get("password", ""))

    name = f"{wcd}_INTERNET_R_VID_{vlan}"

    wcd_base = (
        "InternetGatewayDevice.WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    base = (
        f"{wcd_base}."
        f"WANPPPConnection.{instance}"
    )

    bindings = ",".join(
        data.get("bindings", [])
    )

    link_values = [
        [f"{wcd_base}.WanName", name, "xsd:string"],

        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.Enable",
            True,
            "xsd:boolean"
        ],
        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.Mode",
            2,
            "xsd:unsignedInt"
        ],
        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.VLANIDMark",
            vlan,
            "xsd:unsignedInt"
        ],
        [
            f"{wcd_base}.X_CT-COM_WANGponLinkConfig.802-1pMark",
            priority,
            "xsd:unsignedInt"
        ],
    ]

    values = [
        [f"{base}.Enable", False, "xsd:boolean"],

        [
            f"{base}.ConnectionType",
            "IP_Routed",
            "xsd:string"
        ],

        [
            f"{base}.ConnectionTrigger",
            "AlwaysOn",
            "xsd:string"
        ],

        [
            f"{base}.NATEnabled",
            bool(data.get("nat", True)),
            "xsd:boolean"
        ],

        [
            f"{base}.Username",
            username,
            "xsd:string"
        ],

        [
            f"{base}.Password",
            password,
            "xsd:string"
        ],

        [
            f"{base}.MaxMRUSize",
            mtu,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_VLANMode",
            1,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_VLANIDMark",
            vlan,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_802-1pMark",
            priority,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_IPMode",
            1,
            "xsd:unsignedInt"
        ],

        [
            f"{base}.X_CT-COM_ServiceList",
            "INTERNET",
            "xsd:string"
        ],

        [
            f"{base}.X_CT-COM_LanInterface",
            bindings,
            "xsd:string"
        ],

        [
            f"{base}.X_CT-COM_LanInterface-DHCPEnable",
            True,
            "xsd:boolean"
        ],

        [f"{base}.Name", name, "xsd:string"],
        [f"{base}.vsName", name, "xsd:string"],
    ]

    return {
        "wcd": wcd,
        "instance": instance,
        "name": name,
        "vlan": vlan,
        "priority": priority,
        "mtu": mtu,
        "link_values": link_values,
        "parameter_values": values,
    }
