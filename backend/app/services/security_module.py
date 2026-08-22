import ipaddress

BASE = (
    "InternetGatewayDevice."
    "X_HW_Security."
    "AclServices."
)

SERVICES = {
    "http": {
        "label": "HTTP",
        "wan": "HTTPWanEnable",
        "lan": "HTTPLanEnable",
        "port": "HTTPWanPort",
        "ip": "HTTPWanSpecificIp",
        "risk": "high",
    },
    "https": {
        "label": "HTTPS",
        "wan": "HTTPSWanEnable",
        "lan": "HTTPSLanEnable",
        "port": "HTTPSWanPort",
        "ip": "HTTPSWanSpecificIp",
        "risk": "medium",
    },
    "ssh": {
        "label": "SSH",
        "wan": "SSHWanEnable",
        "lan": "SSHLanEnable",
        "port": "SSHWanPort",
        "ip": "SSHWanSpecificIp",
        "risk": "medium",
    },
    "telnet": {
        "label": "Telnet",
        "wan": "TELNETWanEnable",
        "lan": "TELNETLanEnable",
        "port": "TELNETWanPort",
        "ip": "TELNETWanSpecificIp",
        "risk": "high",
    },
    "ftp": {
        "label": "FTP",
        "wan": "FTPWanEnable",
        "lan": "FTPLanEnable",
        "port": "FTPWanPort",
        "ip": "FTPWanSpecificIp",
        "risk": "high",
    },
    "tftp": {
        "label": "TFTP",
        "wan": "TFTPWanEnable",
        "lan": "TFTPLanEnable",
        "port": None,
        "ip": "TFTPWanSpecificIp",
        "risk": "high",
    },
    "icmp": {
        "label": "Ping / ICMP",
        "wan": "ICMPWanEnable",
        "lan": "ICMPLanEnable",
        "port": None,
        "ip": "ICMPWanSpecificIp",
        "risk": "low",
    },
}


def unwrap(value):
    if isinstance(value, dict):
        return value.get("_value")
    return value


def writable(value):
    return (
        isinstance(value, dict)
        and value.get("_writable") is True
    )


def to_bool(value):
    value = unwrap(value)

    return (
        value is True
        or value == 1
        or value == "1"
        or str(value).lower() == "true"
    )


def to_int(value):
    value = unwrap(value)

    try:
        return int(value)
    except Exception:
        return None


def get_acl(device):
    try:
        return (
            device["InternetGatewayDevice"]
            ["X_HW_Security"]
            ["AclServices"]
        )
    except Exception:
        return None


def firewall_grade(device):
    acl = get_acl(device)

    if not acl:
        return None

    return to_int(
        acl.get("FireWallGrade")
    )


def firewall_label(grade):
    if grade == 0:
        return "Bajo"

    if grade == 1:
        return "Alto"

    return f"Desconocido ({grade})"


def security_state(device):
    acl = get_acl(device)

    if not acl:
        return {
            "supported": False,
            "firewall_grade": None,
            "firewall_label": None,
            "services": [],
            "tr069_protected": True,
        }

    grade_obj = acl.get("FireWallGrade")
    grade = to_int(grade_obj)

    services = []

    for service_id, cfg in SERVICES.items():

        wan_obj = acl.get(cfg["wan"])
        lan_obj = acl.get(cfg["lan"])

        supported = (
            isinstance(wan_obj, dict)
            or isinstance(lan_obj, dict)
        )

        if not supported:
            continue

        port_obj = (
            acl.get(cfg["port"])
            if cfg["port"]
            else None
        )

        ip_obj = (
            acl.get(cfg["ip"])
            if cfg["ip"]
            else None
        )

        services.append({
            "id": service_id,
            "label": cfg["label"],
            "risk": cfg["risk"],

            "wan_enabled":
                to_bool(wan_obj),

            "lan_enabled":
                to_bool(lan_obj),

            "wan_writable":
                writable(wan_obj),

            "lan_writable":
                writable(lan_obj),

            "wan_port":
                to_int(port_obj),

            "port_supported":
                port_obj is not None,

            "port_writable":
                writable(port_obj),

            "specific_ip":
                unwrap(ip_obj) or "",

            "ip_supported":
                ip_obj is not None,

            "ip_writable":
                writable(ip_obj),
        })

    return {
        "supported": True,

        "firewall_grade": grade,
        "firewall_label":
            firewall_label(grade),

        "firewall_writable":
            writable(grade_obj),

        # Regla operativa del módulo.
        "wan_activation_allowed":
            grade == 0,

        # Nunca se modifica CWMP aquí.
        "tr069_protected": True,

        "services": services,
    }


def service_changes(
    device,
    service_id,
    payload,
):
    if service_id not in SERVICES:
        raise ValueError(
            "Servicio no soportado"
        )

    acl = get_acl(device)

    if not acl:
        raise ValueError(
            "La ONU no expone AclServices"
        )

    cfg = SERVICES[service_id]
    grade = firewall_grade(device)

    values = []
    requested = {}

    if "wan_enabled" in payload:

        enabled = bool(
            payload["wan_enabled"]
        )

        # REGLA PRINCIPAL:
        # solo nivel Bajo permite NUEVAS
        # activaciones desde WAN.
        if enabled and grade != 0:
            raise ValueError(
                "Para activar servicios por WAN "
                "el firewall debe estar en nivel Bajo"
            )

        obj = acl.get(cfg["wan"])

        if not writable(obj):
            raise ValueError(
                f"{cfg['label']} WAN no es escribible"
            )

        values.append([
            BASE + cfg["wan"],
            enabled,
            "xsd:boolean"
        ])

        requested["wan_enabled"] = enabled

    if "lan_enabled" in payload:

        enabled = bool(
            payload["lan_enabled"]
        )

        obj = acl.get(cfg["lan"])

        if not writable(obj):
            raise ValueError(
                f"{cfg['label']} LAN no es escribible"
            )

        values.append([
            BASE + cfg["lan"],
            enabled,
            "xsd:boolean"
        ])

        requested["lan_enabled"] = enabled

    if (
        cfg["port"]
        and "wan_port" in payload
    ):
        obj = acl.get(cfg["port"])

        if not writable(obj):
            raise ValueError(
                "Puerto WAN no es escribible"
            )

        port = int(
            payload["wan_port"]
        )

        if not 1 <= port <= 65535:
            raise ValueError(
                "Puerto inválido"
            )

        values.append([
            BASE + cfg["port"],
            port,
            "xsd:unsignedInt"
        ])

        requested["wan_port"] = port

    if (
        cfg["ip"]
        and "specific_ip" in payload
    ):
        obj = acl.get(cfg["ip"])

        if not writable(obj):
            raise ValueError(
                "IP específica no es escribible"
            )

        ip = str(
            payload["specific_ip"]
            or ""
        ).strip()

        if ip:
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                raise ValueError(
                    "IP permitida inválida"
                )

        values.append([
            BASE + cfg["ip"],
            ip,
            "xsd:string"
        ])

        requested["specific_ip"] = ip

    if not values:
        raise ValueError(
            "No hay cambios para aplicar"
        )

    return values, requested
