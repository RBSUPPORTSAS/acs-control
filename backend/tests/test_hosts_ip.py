"""IP TR-069 en el inventario y equipos conectados (LANDevice.Hosts)."""

from app.services.device_normalizer import NORMALIZE_PROJECTION, normalize_device
from app.services.hosts_reader import read_hosts

TS = "2026-11-12T21:45:09.175Z"


def v(value):
    return {"_value": value, "_object": False, "_writable": False, "_timestamp": TS}


def test_ip_tr069_desde_connection_request_url():
    d = {"_id": "X", "InternetGatewayDevice": {"ManagementServer": {
        "ConnectionRequestURL": v("http://192.0.2.38:58000/b9c8d6"),
    }}}
    assert normalize_device(d)["tr069_ip"] == "192.0.2.38"
    assert "InternetGatewayDevice.ManagementServer.ConnectionRequestURL" in NORMALIZE_PROJECTION
    assert normalize_device({"_id": "Y"})["tr069_ip"] is None


def test_valor_sin_dato_no_se_muestra_como_objeto():
    d = {"_id": "X", "InternetGatewayDevice": {"DeviceInfo": {"UpTime": {"_object": False}}}}
    assert normalize_device(d)["uptime"] is None


def lan(hosts, count=None):
    table = {"_object": True, "Host": {"_object": True, **hosts}}
    if count is not None:
        table["HostNumberOfEntries"] = v(count)
    return {"_id": "X", "InternetGatewayDevice": {"LANDevice": {"1": {
        "Hosts": table,
        "WLANConfiguration": {"5": {"Standard": v("a,n,ac,ax"), "SSID": v("RED-5G")}},
    }}}}


def test_hosts_zte_y_vsol():
    d = lan({
        "4": {"HostName": v("tv"), "IPAddress": v("192.168.1.5"), "MACAddress": v("8C:98:06:20:59:35"),
              "Active": v(True), "AddressSource": v("DHCP"), "InterfaceType": v("Ethernet"),
              "Layer2Interface": v("InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.4"),
              "X_ZTE-COM_OnlineDuration": v("1295592")},
        "8": {"HostName": v("tel"), "IPAddress": v("192.168.1.3"), "Active": v(True),
              "InterfaceType": v("802.11"), "PowerLevel": v("-41"), "downLinkNegotiationRate": v(143),
              "ConnectInterface": v("InternetGatewayDevice.LANDevice.1.WLANConfiguration.5."),
              "OnlineTime": v(13018)},
        "9": {"_object": True},
    }, count=2)
    r = read_hosts(d)
    assert r["supported"] and r["reported_count"] == 2 and len(r["hosts"]) == 2
    h = {x["ip"]: x for x in r["hosts"]}
    assert h["192.168.1.5"]["interface"] == "LAN 4" and h["192.168.1.5"]["mac"] == "8c:98:06:20:59:35"
    assert h["192.168.1.5"]["online_seconds"] == 1295592
    assert h["192.168.1.3"]["interface"] == "Wi-Fi 5 GHz · RED-5G"
    assert h["192.168.1.3"]["signal_dbm"] == -41 and h["192.168.1.3"]["link_rate"] == 143
    assert r["updated_at"] == "2026-11-12T21:45:09.175000Z"


def test_sin_rama_hosts_no_soportado():
    r = read_hosts({"_id": "X", "InternetGatewayDevice": {"LANDevice": {"1": {}}}})
    assert r["supported"] is False and r["hosts"] == []
    assert "GenieACS" in r["reason"]


def test_firmware_que_corta_sesion_explica_el_motivo():
    d = {"_id": "X", "InternetGatewayDevice": {
        "DeviceInfo": {"SoftwareVersion": v("V2.1.00-230825")},
        "LANDevice": {"1": {}},
    }}
    r = read_hosts(d)
    assert r["supported"] is False and "corta la sesión" in r["reason"]


def test_tr181():
    d = {"_id": "X", "Device": {"Hosts": {"Host": {"1": {
        "PhysAddress": v("AA:BB:CC:DD:EE:FF"), "IPAddress": v("192.168.0.10"), "Active": v("true"),
        "Layer1Interface": v("Device.Ethernet.Interface.2"),
    }}}}}
    h = read_hosts(d)["hosts"][0]
    assert h["mac"] == "aa:bb:cc:dd:ee:ff" and h["active"] is True and h["connection"] == "lan"
