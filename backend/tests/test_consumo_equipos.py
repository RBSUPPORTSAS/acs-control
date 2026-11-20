"""Consumo por equipo en ZTE F6600P (Hosts.Host.{i}.X_ZTE-COM_*)."""

from app.services.hosts_reader import read_hosts

TS = "2026-11-20T13:00:00.000Z"


def v(value, t="xsd:string"):
    return {"_value": value, "_type": t, "_timestamp": TS, "_writable": False, "_object": False}


def host(mac, kind, l2, rx, tx, tot_rx, tot_tx):
    return {"_object": True, "Active": v(True, "xsd:boolean"), "MACAddress": v(mac), "IPAddress": v("192.168.1.2"),
            "InterfaceType": v(kind), "Layer2Interface": v(l2), "HostName": v("equipo"),
            "X_ZTE-COM_RxRate": v(rx, "xsd:unsignedInt"), "X_ZTE-COM_TxRate": v(tx, "xsd:unsignedInt"),
            "X_ZTE-COM_TotalBytesReceived": v(tot_rx, "xsd:unsignedLong"),
            "X_ZTE-COM_TotalBytesSent": v(tot_tx, "xsd:unsignedLong"),
            "X_ZTE-COM_OnlineDuration": v(1955314, "xsd:unsignedInt")}


def zte():
    lan = "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.4"
    wlan = "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1"
    assoc = {"_object": True, "1": {"_object": True,
             "AssociatedDeviceMACAddress": v("aa:bb:cc:00:00:12"), "X_ZTE-COM_RSSI": v(-60, "xsd:int"),
             # En AssociatedDevice RxRate/TxRate son la velocidad negociada: no es consumo.
             "X_ZTE-COM_RxRate": v(24000, "xsd:unsignedInt"), "X_ZTE-COM_TxRate": v(65000, "xsd:unsignedInt")}}
    return {"InternetGatewayDevice": {"LANDevice": {"1": {
        "Hosts": {"_object": True, "_timestamp": TS, "Host": {"_object": True,
            "4": host("aa:bb:cc:00:00:04", "Ethernet", lan, 84, 82, 37027809, 114479306),
            "12": host("aa:bb:cc:00:00:12", "802.11", wlan, 1346, 58, 896893, 78658),
        }},
        "WLANConfiguration": {"1": {"_object": True, "Standard": v("b,g,n,ax"), "SSID": v("Red"),
                                    "AssociatedDevice": assoc}},
    }}}}


def by_mac(r):
    return {h["mac"]: h for h in r["hosts"]}


def test_consumo_por_equipo_cableado_y_wifi():
    r = read_hosts(zte())
    assert r["traffic_supported"] is True
    lan, wifi = by_mac(r)["aa:bb:cc:00:00:04"], by_mac(r)["aa:bb:cc:00:00:12"]
    assert (lan["download_kbps"], lan["upload_kbps"]) == (84, 82)
    # Totales en KiB en la ONU -> bytes.
    assert lan["download_bytes"] == 37027809 * 1024 and lan["upload_bytes"] == 114479306 * 1024
    # El consumo del Wi-Fi sale de Hosts, no de la velocidad negociada.
    assert (wifi["download_kbps"], wifi["upload_kbps"]) == (1346, 58)
    assert wifi["signal_dbm"] == -60


def test_modelos_sin_consumo():
    d = zte()
    for h in d["InternetGatewayDevice"]["LANDevice"]["1"]["Hosts"]["Host"].values():
        if isinstance(h, dict):
            for k in [k for k in h if k.startswith("X_ZTE-COM_") and k != "X_ZTE-COM_OnlineDuration"]:
                del h[k]
    r = read_hosts(d)
    assert r["traffic_supported"] is False
    assert all(h["download_kbps"] is None and h["download_bytes"] is None for h in r["hosts"])
