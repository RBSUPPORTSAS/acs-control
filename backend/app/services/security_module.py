from app.services.device_normalizer import get_parameter
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


# Huawei (HG8145V5, HG8546M...) guarda el nivel como texto en
# X_HW_Security.X_HW_FirewallLevel. VSOL usa un numero en
# AclServices.FireWallGrade. Internamente se usa el mismo codigo.
HUAWEI_LEVEL_PATH = "InternetGatewayDevice.X_HW_Security.X_HW_FirewallLevel"

HUAWEI_LEVELS = {
    "low": 0,
    "high": 1,
    "middle": 2,
    "custom": 3,
}

HUAWEI_WRITE = {
    0: "Low",
    1: "High",
}


# Realtek/OPTICTIMES (IGD): Firewall.X_RZ_ServiceControl.IPV4ServiceControl.{i}
# es una regla por origen (Ingress WAN o LAN) con Service_HTTP, _HTTPS,
# _SSH, _TELNET, _FTP, _TFTP, _ICMP y sus _PORT. El nivel esta en
# Firewall.X_RZ_Firewall_Level (texto, como Huawei).
RZ_FIREWALL = "InternetGatewayDevice.Firewall"
RZ_LEVEL_PATH = RZ_FIREWALL + ".X_RZ_Firewall_Level"
RZ_SERVICES = ("HTTP", "HTTPS", "SSH", "TELNET", "FTP", "TFTP", "ICMP")


def rz_rules(device):
    """{"WAN": (ruta, nodo), "LAN": (ruta, nodo)} de X_RZ_ServiceControl."""

    try:
        table = (
            device["InternetGatewayDevice"]["Firewall"]
            ["X_RZ_ServiceControl"]["IPV4ServiceControl"]
        )
    except Exception:
        return {}

    rules = {}

    for index, node in (table or {}).items():
        if not str(index).isdigit() or not isinstance(node, dict):
            continue

        ingress = str(unwrap(node.get("Ingress")) or "").upper()

        if ingress in ("WAN", "LAN") and ingress not in rules:
            rules[ingress] = (
                f"{RZ_FIREWALL}.X_RZ_ServiceControl.IPV4ServiceControl.{index}.",
                node,
            )

    return rules


def access_table(device):
    """Servicios por WAN/LAN con los nombres de AclServices.

    Devuelve (nodos, rutas): nodos[nombre] es el nodo de GenieACS y
    rutas[nombre] la ruta completa para escribirlo. Para Huawei/VSOL son
    los de X_HW_Security.AclServices; para Realtek se arman desde las
    reglas X_RZ_ServiceControl.
    """

    acl = get_acl(device)

    if acl:
        names = [k for k in acl if not k.startswith("_")]
        return acl, {name: BASE + name for name in names}

    rules = rz_rules(device)

    if not rules:
        return None, {}

    nodes, paths = {}, {}

    for ingress, (prefix, node) in rules.items():
        side = "Wan" if ingress == "WAN" else "Lan"
        allow_any = to_bool(node.get("Service_Any"))

        for svc in RZ_SERVICES:
            flag = node.get(f"Service_{svc}")

            if not isinstance(flag, dict):
                continue

            name = f"{svc}{side}Enable"

            if allow_any:
                # "Cualquier servicio" ya permitido: el servicio esta abierto
                # aunque su casilla individual diga False. No se edita aqui.
                nodes[name] = {"_value": True, "_writable": False}
            else:
                nodes[name] = flag
                paths[name] = prefix + f"Service_{svc}"

            port = node.get(f"Service_{svc}_PORT")

            if side == "Wan" and isinstance(port, dict):
                nodes[f"{svc}WanPort"] = port
                paths[f"{svc}WanPort"] = prefix + f"Service_{svc}_PORT"

    return nodes, paths


def firewall_source(device):
    """("grade", nodo) para VSOL, ("huawei", nodo) para Huawei o (None, None)."""

    acl = get_acl(device)

    if acl and isinstance(acl.get("FireWallGrade"), dict):
        return "grade", acl.get("FireWallGrade")

    try:
        node = device["InternetGatewayDevice"]["X_HW_Security"]["X_HW_FirewallLevel"]
    except Exception:
        node = None

    if isinstance(node, dict):
        return "huawei", node

    try:
        node = device["InternetGatewayDevice"]["Firewall"]["X_RZ_Firewall_Level"]
    except Exception:
        node = None

    if isinstance(node, dict):
        return "rz", node

    return None, None


def firewall_grade(device):
    kind, node = firewall_source(device)

    if kind == "grade":
        return to_int(node)

    if kind in ("huawei", "rz"):
        return HUAWEI_LEVELS.get(str(unwrap(node) or "").strip().lower())

    return None


def firewall_label(grade):
    if grade == 0:
        return "Bajo"

    if grade == 1:
        return "Alto"

    if grade == 2:
        return "Medio"

    if grade == 3:
        return "Personalizado"

    return f"Desconocido ({grade})"


def firewall_write(device, grade):
    """Parametro, valor y tipo para fijar el nivel (0 Bajo, 1 Alto)."""

    kind, node = firewall_source(device)

    if kind == "grade":
        return (
            "InternetGatewayDevice.X_HW_Security.AclServices.FireWallGrade",
            grade,
            "xsd:unsignedInt",
        )

    if kind == "huawei":
        return HUAWEI_LEVEL_PATH, HUAWEI_WRITE[grade], "xsd:string"

    if kind == "rz":
        return RZ_LEVEL_PATH, HUAWEI_WRITE[grade], "xsd:string"

    return None


def unsupported_info(device):
    """Que se puede decir de una ONU sin firewall/servicios por TR-069.

    RT9607C (fw -1.2.0.30) y RX8102WT: no tienen rama Firewall; la
    RT9607C solo publica DeviceInfo.X_RZ_WebEnable (interfaz web).
    """

    notes = []
    web = get_parameter(device, "InternetGatewayDevice.DeviceInfo.X_RZ_WebEnable")

    if web is not None:
        notes.append({
            "label": "Interfaz web de la ONU",
            "value": "Habilitada" if str(web).lower() in ("true", "1") else "Deshabilitada",
        })

    if not notes:
        return {}

    return {
        "reason": (
            "Este firmware no expone firewall ni control de servicios "
            "(HTTP, HTTPS, Telnet, SSH...) por TR-069."
        ),
        "notes": notes,
    }


def security_state(device):
    acl, _paths = access_table(device)

    if not acl:
        return {
            "supported": False,
            "firewall_grade": None,
            "firewall_label": None,
            "services": [],
            "tr069_protected": True,
            **unsupported_info(device),
        }

    _, grade_obj = firewall_source(device)
    grade = firewall_grade(device)

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
        # Medio/Personalizado solo estan confirmados en Huawei; en el
        # formato numerico (VSOL) otros valores siguen como "Desconocido".
        "firewall_label": (
            firewall_label(grade)
            if firewall_source(device)[0] in ("huawei", "rz") or grade in (0, 1)
            else f"Desconocido ({grade})"
        ),

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

    acl, paths = access_table(device)

    if not acl:
        raise ValueError(
            "La ONU no expone sus servicios de acceso"
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
            paths.get(cfg["wan"], BASE + cfg["wan"]),
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
            paths.get(cfg["lan"], BASE + cfg["lan"]),
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
            paths.get(cfg["port"], BASE + cfg["port"]),
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
            paths.get(cfg["ip"], BASE + cfg["ip"]),
            ip,
            "xsd:string"
        ])

        requested["specific_ip"] = ip

    if not values:
        raise ValueError(
            "No hay cambios para aplicar"
        )

    return values, requested
