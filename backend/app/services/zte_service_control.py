"""ZTE F6600P: acceso remoto por WAN (HTTP, HTTPS, PING, Telnet, FTP).

No hay un interruptor por servicio. La ONU permite servicios desde la WAN con
reglas en una tabla (vacia de fabrica = todo cerrado):

    InternetGatewayDevice.Firewall.X_ZTE-COM_ServiceControl.IPV4ServiceControl.{i}.
        Enable       true/false
        ServiceType  "HTTP,HTTPS,PING" (acepta HTTP, HTTPS, PING, TELNET, FTP;
                     SSH, TFTP e ICMP dan cwmp.9003)
        Ingress      "WAN_ALL"
        Mode         "Accept"
        IPStart/IPEnd  origen permitido; 0.0.0.0 = cualquiera
        Name         texto libre

ACS-Control crea una regla por servicio (Name "ACS_<SERVICIO>") para poder
limitar cada uno a una IP. Al leer tambien cuenta reglas hechas a mano con
varios servicios; al apagar un servicio se lo quita de todas.

El puerto de cada servicio esta en
Firewall.X_ZTE-COM_ServiceControl.IPV4RemoteServicePortControl.{i}.Port
(HTTP, FTP, TELNET, HTTPS), que es un parametro normal.

Validado en una F6600P (fw V9.0.10P6N44, 2026-11-19): con la regla de HTTP y
HTTPS la pagina de la ONU responde desde la WAN.
"""

import asyncio
import ipaddress

ROOT = "InternetGatewayDevice.Firewall.X_ZTE-COM_ServiceControl"
TABLE = f"{ROOT}.IPV4ServiceControl"
PORTS = f"{ROOT}.IPV4RemoteServicePortControl"

# servicio de ACS-Control -> palabra de la ONU
TOKENS = {"http": "HTTP", "https": "HTTPS", "icmp": "PING", "telnet": "TELNET", "ftp": "FTP"}

ANY = "0.0.0.0"
PSEUDO = "zte-sc:"


class ServiceControlError(RuntimeError):
    pass


def _v(node, name):
    x = (node or {}).get(name)
    return x.get("_value") if isinstance(x, dict) else None


def _bool(x):
    return x is True or str(x).strip().lower() in ("true", "1")


def _service_control(device):
    try:
        node = device["InternetGatewayDevice"]["Firewall"]["X_ZTE-COM_ServiceControl"]
    except Exception:
        return None
    return node if isinstance(node, dict) else None


def supported(device):
    sc = _service_control(device)
    return bool(sc) and isinstance(sc.get("IPV4ServiceControl"), dict)


def rules(device):
    """[{index, enabled, services, ingress, mode, ip_start, ip_end, name}]"""

    table = (_service_control(device) or {}).get("IPV4ServiceControl") or {}
    out = []

    for key, node in table.items():
        if not str(key).isdigit() or not isinstance(node, dict):
            continue
        out.append({
            "index": int(key),
            "enabled": _bool(_v(node, "Enable")),
            "services": [s.strip().upper() for s in str(_v(node, "ServiceType") or "").split(",") if s.strip()],
            "ingress": str(_v(node, "Ingress") or ""),
            "mode": str(_v(node, "Mode") or ""),
            "ip_start": str(_v(node, "IPStart") or ANY),
            "ip_end": str(_v(node, "IPEnd") or ANY),
            "name": str(_v(node, "Name") or ""),
        })

    return sorted(out, key=lambda r: r["index"])


def _opens_wan(rule):
    return rule["enabled"] and rule["mode"].lower() == "accept" and rule["ingress"].upper().startswith("WAN")


def wan_state(device, token):
    """(abierto, ip) del servicio. ip = "" si se permite desde cualquier IP."""

    open_rules = [r for r in rules(device) if _opens_wan(r) and token in r["services"]]

    if not open_rules:
        return False, ""

    # Si alguna regla lo abre a cualquier IP, esta abierto a todos.
    for r in open_rules:
        if r["ip_start"] in (ANY, "") and r["ip_end"] in (ANY, ""):
            return True, ""

    r = open_rules[0]
    return True, r["ip_start"] if r["ip_start"] == r["ip_end"] else f"{r['ip_start']}-{r['ip_end']}"


def port_nodes(device):
    """{"HTTP": (ruta, nodo)} de IPV4RemoteServicePortControl."""

    table = (_service_control(device) or {}).get("IPV4RemoteServicePortControl") or {}
    out = {}

    for key, node in table.items():
        if str(key).isdigit() and isinstance(node, dict) and isinstance(node.get("Port"), dict):
            name = str(_v(node, "Name") or "").upper()
            if name:
                out[name] = (f"{PORTS}.{key}.Port", node["Port"])

    return out


def table_nodes(device):
    """Nodos/rutas para security_module (formato de AclServices)."""

    nodes, paths = {}, {}

    if not supported(device):
        return nodes, paths

    ports = port_nodes(device)

    for service, token in TOKENS.items():
        name = "ICMP" if token == "PING" else token
        opened, ip = wan_state(device, token)

        nodes[f"{name}WanEnable"] = {"_value": opened, "_writable": True}
        paths[f"{name}WanEnable"] = f"{PSEUDO}{token}:enable"

        nodes[f"{name}WanSpecificIp"] = {"_value": ip, "_writable": True}
        paths[f"{name}WanSpecificIp"] = f"{PSEUDO}{token}:ip"

        if token in ports:
            path, node = ports[token]
            nodes[f"{name}WanPort"] = node
            paths[f"{name}WanPort"] = path

    return nodes, paths


def split_pseudo(values):
    """Separa los cambios de reglas (pseudo-rutas) de los parametros normales."""

    pseudo = [v for v in values if str(v[0]).startswith(PSEUDO)]
    normal = [v for v in values if not str(v[0]).startswith(PSEUDO)]
    return normal, pseudo


async def _refresh(client, device_id):
    await client.post_task(
        device_id,
        {"name": "refreshObject", "objectName": TABLE},
        connection_request=True,
        wait_ms=15000,
    )
    return await client.get_device(device_id)


async def _set(client, device_id, values):
    sent = await client.set_parameter_values(device_id, values, wait_ms=15000)
    task_id = (sent or {}).get("task_id")

    if not task_id:
        return

    for fault in await client.get_faults(device_id):
        if str(fault.get("_id", "")).endswith(f"task_{task_id}"):
            await client.delete_fault(fault["_id"])
            await client.delete_task(task_id)
            detail = fault.get("detail") or {}
            raise ServiceControlError(
                "La ONU rechazó la regla de acceso remoto "
                f"({fault.get('code')}: {detail.get('faultString') or fault.get('message') or ''})"
            )


async def _new_rule(client, device_id, before):
    await client.post_task(
        device_id,
        {"name": "addObject", "objectName": TABLE},
        connection_request=True,
        wait_ms=15000,
    )

    for _ in range(5):
        device = await _refresh(client, device_id)
        new = {r["index"] for r in rules(device)} - before
        if new:
            return min(new)
        await asyncio.sleep(2)

    raise ServiceControlError("La ONU no confirmó la nueva regla de acceso remoto")


def _ip_range(ip):
    ip = str(ip or "").strip()

    if not ip:
        return ANY, ANY

    if "-" in ip:
        start, end = [x.strip() for x in ip.split("-", 1)]
    else:
        start = end = ip

    for x in (start, end):
        addr = ipaddress.ip_address(x)
        if addr.version != 4:
            raise ValueError("Solo IPv4")

    return start, end


async def apply(client, device_id, device, pseudo):
    """Aplica [["zte-sc:HTTP:enable", True, ...], ["zte-sc:HTTP:ip", "x", ...]]."""

    wanted = {}

    for path, value, _ in pseudo:
        token, what = path[len(PSEUDO):].split(":")
        wanted.setdefault(token, {})[what] = value

    for token, change in wanted.items():
        device = await _refresh(client, device_id)
        current = rules(device)
        opened, current_ip = wan_state(device, token)

        enable = change.get("enable", opened)
        ip = change.get("ip", current_ip)
        start, end = _ip_range(ip)

        own = next((r for r in current if r["name"] == f"ACS_{token}"), None)

        # Quitar el servicio de cualquier otra regla que lo abra (incluida
        # una regla compartida hecha a mano): la regla ACS_<token> manda.
        for r in current:
            if r is own or token not in r["services"] or not _opens_wan(r):
                continue
            rest = [s for s in r["services"] if s != token]
            if rest:
                await _set(client, device_id, [[f"{TABLE}.{r['index']}.ServiceType", ",".join(rest), "xsd:string"]])
            else:
                await _set(client, device_id, [[f"{TABLE}.{r['index']}.Enable", False, "xsd:boolean"]])

        if not enable:
            if own and own["enabled"]:
                await _set(client, device_id, [[f"{TABLE}.{own['index']}.Enable", False, "xsd:boolean"]])
            continue

        created = False
        if own is None:
            index = await _new_rule(client, device_id, {r["index"] for r in current})
            created = True
        else:
            index = own["index"]

        try:
            await _set(client, device_id, [
                [f"{TABLE}.{index}.Name", f"ACS_{token}", "xsd:string"],
                [f"{TABLE}.{index}.ServiceType", token, "xsd:string"],
                [f"{TABLE}.{index}.Ingress", "WAN_ALL", "xsd:string"],
                [f"{TABLE}.{index}.Mode", "Accept", "xsd:string"],
                [f"{TABLE}.{index}.IPStart", start, "xsd:string"],
                [f"{TABLE}.{index}.IPEnd", end, "xsd:string"],
                [f"{TABLE}.{index}.Enable", True, "xsd:boolean"],
            ])
        except ServiceControlError:
            if created:
                await client.post_task(
                    device_id,
                    {"name": "deleteObject", "objectName": f"{TABLE}.{index}"},
                    connection_request=True,
                    wait_ms=15000,
                )
            raise

    await _refresh(client, device_id)
