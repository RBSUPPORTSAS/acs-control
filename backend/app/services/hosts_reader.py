"""Equipos conectados a la ONU (LANDevice.{n}.Hosts / Device.Hosts).

Solo se muestra lo que GenieACS tiene guardado: si la ONU no publica la rama
Hosts (o ACS-Control la omite porque corta la sesion, p. ej. XPON fw 230825),
se responde supported=False con el motivo.

Campos por fabricante vistos:
- Estandar TR-098: HostName, IPAddress, MACAddress, Active, AddressSource,
  InterfaceType, Layer2Interface, LeaseTimeRemaining.
- ZTE F6600P: X_ZTE-COM_OnlineDuration, X_ZTE-COM_RxRate / TxRate.
- VSOL V2804AX30-H: OnlineTime, PowerLevel (dBm), up/downLinkNegotiationRate.
- TR-181: Device.Hosts.Host.{i}.PhysAddress, Layer1Interface.
"""

from datetime import datetime

from app.services.device_refresh import known_heavy
from app.services.wifi_writer import detect_band


def _v(node, *names):
    for name in names:
        item = node.get(name) if isinstance(node, dict) else None
        if isinstance(item, dict) and "_value" in item:
            value = item["_value"]
            if value not in ("", None):
                return value
    return None


def _children(node):
    return [
        (k, v) for k, v in (node or {}).items()
        if str(k).isdigit() and isinstance(v, dict)
    ]


def _ts(node):
    newest = None
    for value in (node or {}).values():
        if isinstance(value, dict):
            raw = value.get("_timestamp")
            if raw:
                try:
                    stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if newest is None or stamp > newest:
                    newest = stamp
    return newest


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _interface(device, path, kind):
    """Ruta de Layer2Interface -> etiqueta legible ("LAN 4", "Wi-Fi 5 GHz · SSID")."""

    path = str(path or "").rstrip(".")
    parts = path.split(".")

    if "LANEthernetInterfaceConfig" in parts:
        return f"LAN {parts[parts.index('LANEthernetInterfaceConfig') + 1]}"

    if "WLANConfiguration" in parts:
        index = parts[parts.index("WLANConfiguration") + 1]
        node = device
        for part in parts:
            node = node.get(part, {}) if isinstance(node, dict) else {}
        band = detect_band(node) if node else "Wi-Fi"
        ssid = _v(node, "SSID")
        return f"Wi-Fi {band}" + (f" · {ssid}" if ssid else f" · WLAN {index}")

    if kind:
        return "Wi-Fi" if "802.11" in str(kind) else str(kind)

    return path or None


def _host(device, node):
    kind = _v(node, "InterfaceType")
    l2 = _v(node, "Layer2Interface", "ConnectInterface", "Layer1Interface")
    online = _to_int(_v(node, "X_ZTE-COM_OnlineDuration", "OnlineTime"))
    signal = _v(node, "PowerLevel", "X_ZTE-COM_RSSI", "SignalStrength")
    rate = _to_int(_v(node, "downLinkNegotiationRate"))  # Mbps (VSOL)

    return {
        "hostname": _v(node, "HostName"),
        "ip": _v(node, "IPAddress"),
        "mac": (str(_v(node, "MACAddress", "PhysAddress") or "").lower() or None),
        "active": _bool(_v(node, "Active")),
        "address_source": _v(node, "AddressSource"),
        "interface": _interface(device, l2, kind),
        "connection": (
            "wifi" if "802.11" in str(kind) or "WLAN" in str(l2) or "WiFi" in str(l2)
            else "lan" if kind or l2 else None
        ),
        "lease_remaining": _to_int(_v(node, "LeaseTimeRemaining")),
        "online_seconds": online,
        "signal_dbm": _to_int(signal),
        "link_rate": rate,
    }


def read_hosts(device):
    """{"supported", "reason", "hosts": [...], "updated_at", "reported_count"}."""

    tables = []

    igd = (device or {}).get("InternetGatewayDevice")
    if isinstance(igd, dict):
        for _, lan in _children(igd.get("LANDevice")):
            hosts = lan.get("Hosts")
            if isinstance(hosts, dict):
                tables.append(hosts)

    tr181 = (device or {}).get("Device")
    if isinstance(tr181, dict) and isinstance(tr181.get("Hosts"), dict):
        tables.append(tr181["Hosts"])

    if not tables:
        skipped = any(p.endswith(".Hosts") for p in known_heavy(device)[1])
        return {
            "supported": False,
            "reason": (
                "Este firmware corta la sesión TR-069 al pedir los equipos conectados; "
                "ACS-Control no los lee."
                if skipped
                else "GenieACS no tiene la lista de equipos conectados de esta ONU."
            ),
            "hosts": [],
            "updated_at": None,
            "reported_count": None,
        }

    hosts, newest, reported = [], None, None

    for table in tables:
        count = _to_int(_v(table, "HostNumberOfEntries"))
        if count is not None:
            reported = (reported or 0) + count

        for _, node in _children(table.get("Host")):
            # Instancias sin valores: GenieACS conoce el nombre pero no los datos.
            if not any(isinstance(v, dict) and "_value" in v for v in node.values()):
                continue

            hosts.append(_host(device, node))
            stamp = _ts(node)
            if stamp and (newest is None or stamp > newest):
                newest = stamp

    hosts.sort(key=lambda h: (h["active"] is False, h["connection"] or "", h["ip"] or ""))

    return {
        "supported": True,
        "reason": None,
        "hosts": hosts,
        "updated_at": newest.isoformat().replace("+00:00", "Z") if newest else None,
        "reported_count": reported,
    }
