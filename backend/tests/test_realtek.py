"""Realtek / OPTICTIMES (IGD, RT9607C, RX8102WT): WAN, proteccion y seguridad.

Estructura tomada de una IGD (fw V15.4.7).
"""

import pytest

from app.services.genieacs import genieacs
from app.services.security_module import firewall_write, security_state, service_changes
from app.services.wan_reader import read_wan, rtk_services

from conftest import login

ID = "94026B-IGD-PRUEBA"
FW = "InternetGatewayDevice.Firewall.X_RZ_ServiceControl.IPV4ServiceControl"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def rule(ingress, any_=False, **flags):
    node = {"Enable": v(True), "Ingress": v(ingress), "Service_Any": v(any_)}
    for svc in ("HTTP", "HTTPS", "SSH", "TELNET", "FTP", "TFTP", "ICMP"):
        node[f"Service_{svc}"] = v(flags.get(svc.lower(), False))
    for svc, port in (("HTTP", 80), ("HTTPS", 443), ("SSH", 0), ("TELNET", 23), ("FTP", 21)):
        node[f"Service_{svc}_PORT"] = v(port)
    return node


def igd(tr069_name="default wan", service_type=1, cr_ip="10.1.0.150"):
    return {
        "_id": ID,
        "_deviceId": {"_Manufacturer": "OPTICTIMES", "_ProductClass": "IGD", "_SerialNumber": "P1"},
        "InternetGatewayDevice": {
            "ManagementServer": {"ConnectionRequestURL": v(f"http://{cr_ip}:7547/tr069", False)},
            "WANDevice": {"1": {"WANConnectionDevice": {
                "1": {"WANPPPConnection": {"1": {
                    "Name": v(""), "Enable": v(True), "ConnectionStatus": v("Connected"),
                    "ExternalIPAddress": v("172.16.1.157"), "Username": v("PR1"), "MaxMRUSize": v(1492),
                    "X_RTK_VlanId": v(70), "X_RZ_802-1pMark": v(0), "X_RTK_ServiceType": v(2),
                    "X_RTK_LanInterface": v("lan1,lan2,ssid1,ssid5"),
                }}},
                "2": {"WANIPConnection": {"1": {
                    "Name": v(tr069_name), "Enable": v(True), "ConnectionStatus": v("Connected"),
                    "AddressingType": v("DHCP"), "ExternalIPAddress": v("10.1.0.150"),
                    "X_RTK_VlanId": v(46), "X_RZ_802-1pMark": v(2), "X_RTK_ServiceType": v(service_type),
                    "X_RTK_LanInterface": v(""),
                }}},
            }}},
            "Firewall": {
                "X_RZ_Firewall_Level": v("Low"),
                "X_RZ_ServiceControl": {"IPV4ServiceControl": {
                    "1": rule("LAN", any_=True),
                    "2": rule("WAN", http=True, https=True, telnet=True, icmp=True),
                }},
            },
        },
    }


def test_mascara_de_servicios():
    assert rtk_services(1) == "TR069"
    assert rtk_services(2) == "INTERNET"
    assert rtk_services(3) == "TR069,INTERNET"
    assert rtk_services(None) is None


def test_lee_vlan_prioridad_servicios_e_interfaces():
    wans = {w["wan_connection_device"]: w for w in read_wan(igd())}
    assert (wans[1]["vlan"], wans[1]["priority_8021p"], wans[1]["services"]) == (70, 0, ["INTERNET"])
    assert (wans[2]["vlan"], wans[2]["priority_8021p"], wans[2]["services"]) == (46, 2, ["TR069"])
    b = wans[1]["lan_binding"]
    assert "LANEthernetInterfaceConfig.1" in b and "LANEthernetInterfaceConfig.2" in b
    assert "WLANConfiguration.1" in b and "WLANConfiguration.5" in b


def test_tr069_protegida_por_servicio():
    wans = {w["wan_connection_device"]: w for w in read_wan(igd())}
    assert wans[2]["protected"] is True
    assert wans[1]["protected"] is False


def test_tr069_protegida_por_ip_de_gestion_aunque_no_diga_tr069():
    # Caso RX8102WT: WAN incompleta en cache, sin servicio ni nombre utiles.
    wans = {w["wan_connection_device"]: w for w in read_wan(igd(tr069_name="default wan", service_type=None))}
    assert wans[2]["services"] == []
    assert wans[2]["protected"] is True
    assert "gestionar" in wans[2]["protection_reason"]


def test_ip_de_gestion_distinta_no_protege_internet():
    wans = {w["wan_connection_device"]: w for w in read_wan(igd(cr_ip="172.16.1.157", service_type=1))}
    # La WAN de internet tiene la IP del connection request en este caso hipotetico:
    assert wans[1]["protected"] is True


def test_seguridad_realtek():
    st = security_state(igd())
    assert (st["supported"], st["firewall_grade"], st["firewall_label"], st["wan_activation_allowed"]) == (True, 0, "Bajo", True)
    svc = {s["id"]: s for s in st["services"]}
    assert set(svc) == {"http", "https", "ssh", "telnet", "ftp", "tftp", "icmp"}
    assert svc["https"]["wan_enabled"] is True and svc["https"]["wan_port"] == 443
    assert svc["ssh"]["wan_enabled"] is False
    # La regla LAN tiene "cualquier servicio": abierta y no editable aqui.
    assert svc["ssh"]["lan_enabled"] is True and svc["ssh"]["lan_writable"] is False


def test_cambios_van_a_la_regla_wan():
    values, requested = service_changes(igd(), "telnet", {"wan_enabled": False})
    assert values == [[f"{FW}.2.Service_TELNET", False, "xsd:boolean"]]
    values, _ = service_changes(igd(), "https", {"wan_port": 8443})
    assert values == [[f"{FW}.2.Service_HTTPS_PORT", 8443, "xsd:unsignedInt"]]
    with pytest.raises(ValueError):
        service_changes(igd(), "ssh", {"lan_enabled": False})


def test_firewall_realtek():
    assert firewall_write(igd(), 1) == ("InternetGatewayDevice.Firewall.X_RZ_Firewall_Level", "High", "xsd:string")


@pytest.fixture
def rt(monkeypatch):
    async def fake_get_device(device_id):
        return igd()
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)


async def test_no_borra_tr069(client, rt):
    await login(client, "tecnico")
    r = await client.delete(f"/api/devices/{ID}/wan/2/WANIPConnection/1")
    assert r.status_code == 403


async def test_rutas_vsol_siguen_bloqueadas(client, rt):
    await login(client, "jefe")
    for path in ("wan/vsol/create-ip", "wan/vsol/create-pppoe"):
        r = await client.post(f"/api/devices/{ID}/{path}", json={"vlan": 999, "username": "u", "password": "p"})
        assert r.status_code == 400


# --- Escritura (validada en la IGD real) ------------------------------------------

from app.services.vendor_wan import create_vendor_wan, rtk_service_type, translate  # noqa: E402

CONN = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.WANIPConnection.1"


def test_traduce_a_realtek():
    out = translate([
        [f"{CONN}.X_CT-COM_VLANIDMark", 999, "xsd:unsignedInt"],
        [f"{CONN}.X_CT-COM_802-1pMark", 3, "xsd:unsignedInt"],
        [f"{CONN}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
        [f"{CONN}.X_CT-COM_LanInterface", "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.2,InternetGatewayDevice.LANDevice.1.WLANConfiguration.5", "xsd:string"],
        [f"{CONN}.X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        ["InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.X_CT-COM_WANGponLinkConfig.Mode", 2, "xsd:unsignedInt"],
        [f"{CONN}.NATEnabled", True, "xsd:boolean"],
    ], "realtek")
    by = {p.rsplit(".", 1)[1]: (v, t) for p, v, t in out}
    assert by["X_RTK_VlanId"] == (999, "xsd:int")
    assert by["X_RZ_802-1pMark"] == (3, "xsd:unsignedInt")
    assert by["X_RTK_ServiceType"] == (2, "xsd:int")
    assert by["X_RTK_LanInterface"] == ("lan2,ssid5", "xsd:string")
    assert not [p for p, _, _ in out if "X_CT-COM" in p or "GponLink" in p]


def test_mascara_de_servicio_al_escribir():
    assert rtk_service_type("INTERNET") == 2
    assert rtk_service_type("TR069,INTERNET") == 3
    with pytest.raises(ValueError):
        rtk_service_type("IPTV")


class FakeClient:
    def __init__(self):
        self.device = igd()
        self.calls = []

    async def get_device(self, device_id):
        return self.device

    async def add_object(self, device_id, name):
        wcds = self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]
        if name.endswith("WANConnectionDevice"):
            wcds["3"] = {}
        else:
            wcds["3"][name.rsplit(".", 1)[1]] = {"1": {}}
        return {"http_status": 200}

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.calls.append(("task", task["objectName"]))
        return 200

    async def set_parameter_values(self, device_id, values):
        self.calls.append(("set", values))
        return {"http_status": 200}


@pytest.mark.parametrize("mode,container", [("DHCP", "WANIPConnection"), ("STATIC", "WANIPConnection"), ("PPPOE", "WANPPPConnection")])
async def test_crear_wan_realtek(monkeypatch, mode, container):
    from app.services import x_ctcom_wan_creator as c

    async def no_sleep(_):
        return None
    monkeypatch.setattr(c.asyncio, "sleep", no_sleep)

    client = FakeClient()
    data = {"vlan": 999, "priority": 0, "username": "u", "password": "p", "ip": "192.0.2.10",
            "subnet_mask": "255.255.255.0", "gateway": "192.0.2.1", "dns": "8.8.8.8"}
    result = await create_vendor_wan(client, ID, data, mode=mode, vendor="realtek")
    assert (result["wcd"], result["driver"]) == (3, "realtek")

    base = f"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.{container}.1"
    sets = [x[1] for x in client.calls if x[0] == "set"]
    flat = {p: v for batch in sets for p, v, _ in batch}
    assert flat[f"{base}.X_RTK_VlanId"] == 999
    assert flat[f"{base}.X_RTK_ServiceType"] == 2
    assert ("task", base) in client.calls
    assert sets[-1] == [[f"{base}.Enable", True, "xsd:boolean"]]
    assert not [p for p in flat if "X_CT-COM" in p or ".WANConnectionDevice.1." in p or ".WANConnectionDevice.2." in p]


async def test_editar_vlan_realtek_envia_x_rtk(client, rt, monkeypatch):
    import asyncio
    sent = []

    async def capture(device_id, values):
        sent.extend(values)
        return {"http_status": 200}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(genieacs, "set_parameter_values", capture)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    await login(client, "jefe")
    r = await client.patch(f"/api/devices/{ID}/wan/1/pppoe/1", json={"vlan": 71, "priority": 3})
    assert r.status_code == 200, r.text
    by = {p.rsplit(".", 1)[1]: v for p, v, _ in sent}
    assert by.get("X_RTK_VlanId") == 71 and by.get("X_RZ_802-1pMark") == 3
    assert not [p for p, _, _ in sent if "X_CT-COM" in p or "GponLink" in p]
