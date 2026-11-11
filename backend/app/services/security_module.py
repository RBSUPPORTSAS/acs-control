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


SERVICES_LABEL = {
    "HTTP": "HTTP",
    "HTTPS": "HTTPS",
    "SSH": "SSH",
    "TELNET": "Telnet",
    "FTP": "FTP",
    "TFTP": "TFTP",
    "ICMP": "Ping",
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


# X_CMCC (RX8414CDW fw V02.01.02): firewall encendido/apagado en
# X_CMCC_Security.FirewallEnable; Telnet/FTP en DeviceInfo.X_CMCC_ServiceManage
# (TelnetEnable = servicio, TelnetWANEnable = acceso desde WAN). Las
# contrasenas de Telnet/FTP de esa rama nunca se muestran.
CMCC_SECURITY = "InternetGatewayDevice.X_CMCC_Security"
CMCC_SERVICES = "InternetGatewayDevice.DeviceInfo.X_CMCC_ServiceManage"
CMCC_MAP = {
    "TELNETLanEnable": "TelnetEnable",
    "TELNETWanEnable": "TelnetWANEnable",
    "TELNETWanPort": "TelnetPort",
    "FTPLanEnable": "FtpEnable",
    "FTPWanPort": "FtpPort",
}
CMCC_NOTES = (
    ("DoSEnable", "Protección contra DoS"),
    ("PortScanEnable", "Protección contra escaneo de puertos"),
    ("IPFilterInEnable", "Filtro IP de entrada"),
    ("IPFilterOutEnable", "Filtro IP de salida"),
    ("MacFilterEnable", "Filtro MAC"),
    ("UrlFilterEnable", "Filtro URL"),
)


def _cmcc(device, branch):
    try:
        if branch == "security":
            return device["InternetGatewayDevice"]["X_CMCC_Security"]
        return device["InternetGatewayDevice"]["DeviceInfo"]["X_CMCC_ServiceManage"]
    except Exception:
        return None


# Misma rama ServiceManage con otros prefijos: X_CT-COM (MONU
# xPON+1GE+1FE+WIFI+CATV fw V3.3.0: Telnet/FTP sin variante WAN).
SERVICE_MANAGE = ("X_CMCC_ServiceManage", "X_CT-COM_ServiceManage")


def cmcc_table(device):
    info = ((device or {}).get("InternetGatewayDevice") or {}).get("DeviceInfo") or {}

    for branch in SERVICE_MANAGE:
        node = info.get(branch)

        if not isinstance(node, dict):
            continue

        nodes, paths = {}, {}

        for name, param in CMCC_MAP.items():
            if isinstance(node.get(param), dict):
                nodes[name] = node[param]
                paths[name] = f"InternetGatewayDevice.DeviceInfo.{branch}.{param}"

        if nodes:
            return nodes, paths

    return {}, {}


def cmcc_notes(device):
    node = _cmcc(device, "security")

    if not isinstance(node, dict):
        return []

    return [
        {"label": label, "value": "Activado" if to_bool(node.get(param)) else "Desactivado"}
        for param, label in CMCC_NOTES
        if isinstance(node.get(param), dict)
    ]


# CDTC FD714 (GS1-R850 fw V4.3.4, GS3-R851 fw V3.3.14): X_CT-COM_Security.ACL.{i}
# es una regla con Interface (WAN/LAN), Mode (Permit), Servics (lista
# "WEB,HTTPS,PING"; el nombre trae ese error de la ONU) y rango StartIP-EndIP.
# Por ahora solo lectura: una regla puede mezclar varios servicios y no se
# ha validado en laboratorio que pasa al desactivarla.
CTCOM_ACL_SERVICES = {
    "WEB": "HTTP",
    "HTTP": "HTTP",
    "HTTPS": "HTTPS",
    "PING": "ICMP",
    "ICMP": "ICMP",
    "TELNET": "TELNET",
    "SSH": "SSH",
    "FTP": "FTP",
    "TFTP": "TFTP",
}
ANY_RANGE = ("", "0.0.0.0-255.255.255.255", "0.0.0.0-0.0.0.0")


def ctcom_acl_rules(device):
    try:
        table = device["InternetGatewayDevice"]["X_CT-COM_Security"]["ACL"]
    except Exception:
        return []

    rules = []

    for index, node in sorted(
        ((k, v) for k, v in (table or {}).items() if str(k).isdigit() and isinstance(v, dict)),
        key=lambda item: int(item[0]),
    ):
        services = [
            CTCOM_ACL_SERVICES.get(x.strip().upper(), x.strip().upper())
            for x in str(unwrap(node.get("Servics")) or unwrap(node.get("Services")) or "").split(",")
            if x.strip()
        ]
        start = str(unwrap(node.get("StartIP")) or "")
        end = str(unwrap(node.get("EndIP")) or "")

        rules.append({
            "index": int(index),
            "interface": str(unwrap(node.get("Interface")) or "").upper(),
            "mode": str(unwrap(node.get("Mode")) or "").lower(),
            "enabled": to_bool(node.get("Enable")),
            "services": services,
            "range": f"{start}-{end}" if start or end else "",
        })

    return rules


def ctcom_table(device):
    nodes = {}

    for rule in ctcom_acl_rules(device):
        side = {"WAN": "Wan", "LAN": "Lan"}.get(rule["interface"])

        if not side:
            continue

        allowed = rule["enabled"] and rule["mode"] == "permit"

        for svc in rule["services"]:
            if svc not in RZ_SERVICES:
                continue

            name = f"{svc}{side}Enable"
            current = nodes.get(name, {}).get("_value", False)
            nodes[name] = {"_value": current or allowed, "_writable": False}

            if allowed and side == "Wan" and rule["range"] not in ANY_RANGE:
                nodes[f"{svc}WanSpecificIp"] = {"_value": rule["range"], "_writable": False}

    return nodes


def ctcom_notes(device):
    rules = ctcom_acl_rules(device)

    if not rules:
        return []

    notes = []

    for rule in rules:
        names = ", ".join(SERVICES_LABEL.get(s, s) for s in rule["services"]) or "-"
        origin = (
            "cualquier IP"
            if rule["range"] in ANY_RANGE
            else rule["range"]
        )
        state = (
            "Permitido" if rule["mode"] == "permit" else rule["mode"].capitalize()
        ) if rule["enabled"] else "Regla desactivada"

        notes.append({
            "label": f"Regla {rule['index']} ({rule['interface'] or '?'}): {names}",
            "value": f"{state} desde {origin}" if rule["enabled"] else state,
        })

    notes.append({
        "label": "Edición",
        "value": "Solo lectura en este modelo (reglas ACL de X_CT-COM_Security)",
    })

    return notes


# ZTE (F6600P fw V9.0.10): Telnet y FTP en X_ZTE-COM_Telnet / X_ZTE-COM_FTP
# (Enable = servicio encendido; no distingue WAN/LAN), nivel del firewall en
# Firewall.Config (texto Low/Middle/High). Solo lectura: el modelo esta en
# evaluacion. Usuarios y contrasenas de esas ramas nunca se muestran.
def _zte(device, name):
    try:
        node = device["InternetGatewayDevice"][name]
    except Exception:
        return None
    return node if isinstance(node, dict) else None


def zte_table(device):
    nodes = {}

    for branch, svc in (("X_ZTE-COM_Telnet", "TELNET"), ("X_ZTE-COM_FTP", "FTP")):
        node = _zte(device, branch)
        if node and isinstance(node.get("Enable"), dict):
            nodes[f"{svc}LanEnable"] = {"_value": to_bool(node["Enable"]), "_writable": False}

    return nodes


ZTE_NOTES = (
    ("X_ZTE-COM_DoS.Anti-PortScan.Enable", "Protección contra escaneo de puertos"),
    ("X_ZTE-COM_DMZ.Enable", "DMZ"),
    ("X_ZTE-COM_MacFilterService.Enable", "Filtro MAC"),
    ("X_ZTE-COM_URLFilterService.Enable", "Filtro URL"),
)


def zte_notes(device):
    firewall = _zte(device, "Firewall")

    if not firewall or not isinstance(firewall.get("X_ZTE-COM_ALG"), dict) and not _zte(device, "X_ZTE-COM_Telnet"):
        return []

    notes = []

    for path, label in ZTE_NOTES:
        node = firewall
        for part in path.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict) and "_value" in node:
            notes.append({"label": label, "value": "Activado" if to_bool(node) else "Desactivado"})

    if isinstance(firewall.get("Enable"), dict):
        notes.insert(0, {
            "label": "Firewall",
            "value": "Encendido" if to_bool(firewall["Enable"]) else "Apagado",
        })

    notes.append({"label": "Edición", "value": "Solo lectura (modelo en evaluación)"})
    return notes


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
        nodes, paths = cmcc_table(device)

        if not nodes:
            nodes, paths = ctcom_table(device), {}

        if not nodes:
            nodes, paths = zte_table(device), {}

        return (nodes or None), paths

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

    node = (_cmcc(device, "security") or {}).get("FirewallEnable")

    if isinstance(node, dict):
        return "cmcc", node

    firewall = _zte(device, "Firewall")

    if firewall and isinstance(firewall.get("X_ZTE-COM_ALG"), dict) and isinstance(firewall.get("Config"), dict):
        return "zte", firewall["Config"]

    return None, None


def firewall_grade(device):
    kind, node = firewall_source(device)

    if kind == "grade":
        return to_int(node)

    if kind in ("huawei", "rz", "zte"):
        return HUAWEI_LEVELS.get(str(unwrap(node) or "").strip().lower())

    if kind == "cmcc":
        # Firewall apagado = nivel Bajo (permite abrir servicios por WAN).
        return 1 if to_bool(node) else 0

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

    if kind == "cmcc":
        return f"{CMCC_SECURITY}.FirewallEnable", grade == 1, "xsd:boolean"

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
            None
            if firewall_source(device)[0] is None
            else ("Encendido" if grade == 1 else "Apagado")
            if firewall_source(device)[0] == "cmcc"
            else firewall_label(grade)
            if firewall_source(device)[0] in ("huawei", "rz", "zte") or grade in (0, 1)
            # V2804AX30-H fw V1.1.00: FireWallGrade llega vacio.
            else "No reportado" if grade is None
            else f"Desconocido ({grade})"
        ),

        "firewall_kind": firewall_source(device)[0],

        # Estado de otras protecciones (solo lectura).
        "notes": cmcc_notes(device) + ctcom_notes(device) + zte_notes(device),

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
