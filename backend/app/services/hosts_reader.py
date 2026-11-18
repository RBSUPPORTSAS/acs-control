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

Señal Wi-Fi: WLANConfiguration.{i}.AssociatedDevice.{j} (TR-098) o
WiFi.AccessPoint.{i}.AssociatedDevice.{j} (TR-181), cruzado por MAC.
- ZTE F6600P: AssociatedDeviceRssi / X_ZTE-COM_RSSI (dBm), X_ZTE-COM_SNR,
  X_ZTE-COM_Noise, X_ZTE-COM_TxRate / RxRate (kbps), X_ZTE-COM_WorkingMode
  (11n/11ac), X_ZTE-COM_ClientChannelWidth, X_ZTE-COM_AssociatedDeviceName.
- VSOL V2804AX30-H: AssociatedDevice sin señal; la señal viene en Hosts.PowerLevel.
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


# Parametros de señal (dBm) por fabricante, en orden de preferencia.
RSSI_KEYS = (
    "AssociatedDeviceRssi", "X_ZTE-COM_RSSI", "X_ZTE-COM_SignalStrength",
    "X_HW_RSSI", "X_CT-COM_RSSI", "X_CMCC_RSSI", "X_RTK_RSSI", "RSSI",
    "SignalStrength", "PowerLevel",
)
# Velocidades de enlace en kbps (TR-098 / ZTE).
TX_KBPS = ("X_ZTE-COM_TxRate", "LastDataTransmitRate", "AssociatedDeviceRate", "LastDataDownlinkRate")
RX_KBPS = ("X_ZTE-COM_RxRate", "LastDataReceiveRate", "LastDataUplinkRate")


def signal_quality(dbm):
    """Calificacion del RSSI para el tecnico (umbrales habituales de Wi-Fi)."""

    if dbm is None:
        return None
    if dbm >= -55:
        return {"level": "excelente", "label": "Excelente"}
    if dbm >= -67:
        return {"level": "buena", "label": "Buena"}
    if dbm >= -75:
        return {"level": "regular", "label": "Regular"}
    return {"level": "debil", "label": "Débil"}


def _mbps(kbps):
    value = _to_int(kbps)
    if value is None or value <= 0:
        return None
    return round(value / 1000) if value >= 1000 else value


def _dbm(value):
    dbm = _to_int(value)
    # Algunas ONU reportan 0 o valores positivos cuando no hay dato.
    return dbm if dbm is not None and -120 < dbm < 0 else None


def associated_devices(device):
    """{mac: datos de la asociacion Wi-Fi} desde AssociatedDevice."""

    out = {}

    def add(node, band, wlan_path):
        mac = str(_v(node, "AssociatedDeviceMACAddress", "X_ZTE-COM_MACAddress", "MACAddress") or "").lower()
        if not mac:
            return
        out[mac] = {
            "signal_dbm": _dbm(_v(node, *RSSI_KEYS)),
            "snr_db": _to_int(_v(node, "X_ZTE-COM_SNR", "SNR")),
            "noise_dbm": _dbm(_v(node, "X_ZTE-COM_Noise", "Noise")),
            "tx_mbps": _mbps(_v(node, *TX_KBPS)),
            "rx_mbps": _mbps(_v(node, *RX_KBPS)),
            "wifi_mode": _v(node, "X_ZTE-COM_WorkingMode", "X_ZTE-COM_ClientMode", "OperatingStandard"),
            "channel_width": _v(node, "X_ZTE-COM_ClientChannelWidth", "AssociatedDeviceBandWidth"),
            "ip": _v(node, "AssociatedDeviceIPAddress"),
            "name": _v(node, "X_ZTE-COM_AssociatedDeviceName"),
            "seconds": _to_int(_v(node, "X_ZTE-COM_Uptime", "X_ZTE-COM_StayTime")),
            "band": band,
            "wlan_path": wlan_path,
        }

    igd = (device or {}).get("InternetGatewayDevice")
    if isinstance(igd, dict):
        for li, lan in _children(igd.get("LANDevice")):
            for wi, wlan in _children(lan.get("WLANConfiguration")):
                band = detect_band(wlan)
                path = f"InternetGatewayDevice.LANDevice.{li}.WLANConfiguration.{wi}"
                for _, node in _children(wlan.get("AssociatedDevice")):
                    add(node, band, path)

    tr181 = (device or {}).get("Device")
    if isinstance(tr181, dict):
        for ai, ap in _children((tr181.get("WiFi") or {}).get("AccessPoint")):
            path = f"Device.WiFi.AccessPoint.{ai}"
            for _, node in _children(ap.get("AssociatedDevice")):
                add(node, None, path)

    return out


def _host(device, node):
    kind = _v(node, "InterfaceType")
    l2 = _v(node, "Layer2Interface", "ConnectInterface", "Layer1Interface")
    online = _to_int(_v(node, "X_ZTE-COM_OnlineDuration", "OnlineTime"))
    signal = _v(node, "PowerLevel", "X_ZTE-COM_RSSI", "SignalStrength")
    rate = _to_int(_v(node, "downLinkNegotiationRate"))  # Mbps (VSOL)
    rate_up = _to_int(_v(node, "upLinkNegotiationRate"))  # Mbps (VSOL)

    ip = _v(node, "IPAddress")
    if ip == "0.0.0.0":
        ip = None
    if str(kind).strip().lower() in ("unknown", "unkown"):  # ZTE: "Unkown"
        kind = None

    return {
        "hostname": _v(node, "HostName"),
        "ip": ip,
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
        "signal_dbm": _dbm(signal),
        "link_rate": rate,
        "rx_rate": rate_up,
    }


def _merge_wifi(device, host, assoc):
    """Completa un equipo con su asociacion Wi-Fi (señal, velocidades, modo)."""

    if host.get("signal_dbm") is None:
        host["signal_dbm"] = assoc["signal_dbm"]
    if not host.get("link_rate"):
        host["link_rate"] = assoc["tx_mbps"]
    if not host.get("rx_rate"):
        host["rx_rate"] = assoc["rx_mbps"]
    host["snr_db"] = assoc["snr_db"]
    host["noise_dbm"] = assoc["noise_dbm"]
    host["wifi_mode"] = assoc["wifi_mode"]
    host["channel_width"] = assoc["channel_width"]
    host["connection"] = "wifi"
    if not host.get("hostname"):
        host["hostname"] = assoc["name"]
    if not host.get("ip") and assoc["ip"] not in (None, "", "0.0.0.0"):
        host["ip"] = assoc["ip"]
    # La radio donde esta asociado manda: la V2804AX30-H reporta en Hosts
    # ConnectInterface = WLANConfiguration.1 (5 GHz) para todos los equipos,
    # aunque esten asociados a la WLAN 5 (2.4 GHz).
    if assoc.get("wlan_path"):
        host["interface"] = _interface(device, assoc["wlan_path"], "802.11")
    if host.get("online_seconds") is None:
        host["online_seconds"] = assoc["seconds"]


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
    assoc = associated_devices(device)

    for table in tables:
        count = _to_int(_v(table, "HostNumberOfEntries"))
        if count is not None:
            reported = (reported or 0) + count

        for _, node in _children(table.get("Host")):
            # Instancias sin valores: GenieACS conoce el nombre pero no los datos.
            if not any(isinstance(v, dict) and "_value" in v for v in node.values()):
                continue

            host = _host(device, node)
            if host["mac"] in assoc:
                _merge_wifi(device, host, assoc.pop(host["mac"]))
            hosts.append(host)
            stamp = _ts(node)
            if stamp and (newest is None or stamp > newest):
                newest = stamp

    # Asociados al Wi-Fi que la tabla Hosts no lista (o aun no se leyo).
    for mac, data in assoc.items():
        host = {
            "hostname": None, "ip": None, "mac": mac, "active": True,
            "address_source": None, "interface": None, "connection": "wifi",
            "lease_remaining": None, "online_seconds": None,
            "signal_dbm": None, "link_rate": None,
        }
        _merge_wifi(device, host, data)
        hosts.append(host)

    for host in hosts:
        host.setdefault("rx_rate", None)
        host.setdefault("snr_db", None)
        host.setdefault("noise_dbm", None)
        host.setdefault("wifi_mode", None)
        host.setdefault("channel_width", None)
        host["signal_quality"] = signal_quality(host.get("signal_dbm"))

    hosts.sort(key=lambda h: (h["active"] is False, h["connection"] or "", h["ip"] or ""))

    return {
        "supported": True,
        "reason": None,
        "hosts": hosts,
        "updated_at": newest.isoformat().replace("+00:00", "Z") if newest else None,
        "reported_count": reported,
    }
