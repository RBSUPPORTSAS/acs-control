"""Huawei (HG8145V5): lectura de WAN, proteccion TR-069 y firewall.

Estructura tomada de una HG8145V5 real (fw V5R019C10S270).
"""

import pytest

from app.services.genieacs import genieacs
from app.services.security_module import firewall_write, security_state
from app.services.wan_reader import read_wan

from conftest import login

HW_ID = "00259E-HG8145V5-PRUEBA"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def huawei(level="Low"):
    def conn(name, addressing, vlan, pri, services, lan):
        return {
            "Name": v(name), "AddressingType": v(addressing), "ConnectionType": v("IP_Routed"),
            "Enable": v(True), "ConnectionStatus": v("Connected"), "MaxMTUSize": v(1500),
            "X_HW_VLAN": v(vlan), "X_HW_PRI": v(pri), "X_HW_SERVICELIST": v(services),
            "X_HW_LANBIND": {
                "Lan1Enable": v(lan), "Lan2Enable": v(lan), "Lan3Enable": v(0), "Lan4Enable": v(0),
                "SSID1Enable": v(lan), "SSID2Enable": v(0),
            },
        }

    return {
        "_id": HW_ID,
        "_deviceId": {"_Manufacturer": "Huawei", "_ProductClass": "HG8145V5", "_SerialNumber": "HW1"},
        "InternetGatewayDevice": {
            "WANDevice": {"1": {"WANConnectionDevice": {
                "1": {"WANIPConnection": {"1": conn("1_INTERNET_R_VID_300", "Static", 300, 0, "INTERNET", 1)}},
                "2": {"WANIPConnection": {"1": conn("OLT_C_TR069_DHCP_WAN", "DHCP", 46, 2, "TR069", 0)}},
            }}},
            "X_HW_Security": {
                "X_HW_FirewallLevel": v(level),
                "AclServices": {"HTTPWanEnable": v(False), "HTTPLanEnable": v(True)},
            },
        },
    }


def test_lee_vlan_prioridad_servicios_y_puertos():
    wans = {w["wan_connection_device"]: w for w in read_wan(huawei())}
    assert (wans[1]["vlan"], wans[1]["priority_8021p"], wans[1]["services"]) == (300, 0, ["INTERNET"])
    assert (wans[2]["vlan"], wans[2]["priority_8021p"]) == (46, 2)
    binding = wans[1]["lan_binding"]
    assert "LANEthernetInterfaceConfig.1" in binding and "LANEthernetInterfaceConfig.2" in binding
    assert "WLANConfiguration.1" in binding and "LANEthernetInterfaceConfig.3" not in binding


def test_wan_tr069_huawei_protegida():
    wans = {w["wan_connection_device"]: w for w in read_wan(huawei())}
    assert wans[2]["protected"] is True
    assert wans[1]["protected"] is False


def test_tr069_protegida_por_nombre_aunque_falte_el_servicio():
    d = huawei()
    conn = d["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["2"]["WANIPConnection"]["1"]
    del conn["X_HW_SERVICELIST"]
    wans = {w["wan_connection_device"]: w for w in read_wan(d)}
    assert wans[2]["protected"] is True


@pytest.mark.parametrize("level,grade,label,allowed", [
    ("Low", 0, "Bajo", True),
    ("High", 1, "Alto", False),
    ("Middle", 2, "Medio", False),
    ("Custom", 3, "Personalizado", False),
])
def test_firewall_huawei(level, grade, label, allowed):
    st = security_state(huawei(level))
    assert (st["firewall_grade"], st["firewall_label"], st["wan_activation_allowed"]) == (grade, label, allowed)
    assert st["firewall_writable"] is True


def test_firewall_huawei_se_escribe_como_texto():
    assert firewall_write(huawei(), 0) == (
        "InternetGatewayDevice.X_HW_Security.X_HW_FirewallLevel", "Low", "xsd:string")
    assert firewall_write(huawei(), 1)[1] == "High"


@pytest.fixture
def hw(monkeypatch):
    async def fake_get_device(device_id):
        return huawei()
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)


async def test_no_borra_tr069_huawei(client, hw):
    await login(client, "tecnico")
    r = await client.delete(f"/api/devices/{HW_ID}/wan/2/WANIPConnection/1")
    assert r.status_code == 403


async def test_crear_por_rutas_vsol_sigue_bloqueado_en_huawei(client, hw):
    await login(client, "jefe")
    for path in ("wan/vsol/create-ip", "wan/vsol/create-pppoe"):
        r = await client.post(f"/api/devices/{HW_ID}/{path}", json={"vlan": 999, "username": "u", "password": "p"})
        assert r.status_code == 400, r.text


# --- Traduccion a parametros Huawei -------------------------------------------

from app.services.huawei_wan import create_huawei_wan, lanbind_values, translate  # noqa: E402

CONN = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.WANIPConnection.1"


def test_traduce_vlan_prioridad_servicios_y_descarta_lo_que_no_aplica():
    out = translate([
        [f"{CONN}.X_CT-COM_VLANIDMark", 999, "xsd:unsignedInt"],
        [f"{CONN}.X_CT-COM_802-1pMark", 3, "xsd:unsignedInt"],
        [f"{CONN}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
        [f"{CONN}.X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        [f"{CONN}.vsName", "x", "xsd:string"],
        ["InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.X_CT-COM_WANGponLinkConfig.VLANIDMark", 999, "xsd:unsignedInt"],
        [f"{CONN}.NATEnabled", True, "xsd:boolean"],
    ])
    by = {p.rsplit(".", 1)[1]: v for p, v, _ in out}
    assert by == {"X_HW_VLAN": 999, "X_HW_PRI": 3, "X_HW_SERVICELIST": "INTERNET", "NATEnabled": True}
    assert not [p for p, _, _ in out if "X_CT-COM" in p or "GponLink" in p]


def test_interfaces_a_lanbind():
    out = lanbind_values(CONN, "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.2,InternetGatewayDevice.LANDevice.1.WLANConfiguration.1")
    by = {p.rsplit(".", 1)[1]: v for p, v, _ in out}
    assert by["Lan2Enable"] == 1 and by["SSID1Enable"] == 1
    assert by["Lan1Enable"] == 0 and by["SSID4Enable"] == 0
    assert len(out) == 8


def test_interfaz_no_mapeable_se_rechaza():
    with pytest.raises(ValueError):
        lanbind_values(CONN, "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5")


class FakeClient:
    def __init__(self):
        self.device = huawei()
        self.calls = []

    async def get_device(self, device_id):
        return self.device

    async def add_object(self, device_id, name):
        self.calls.append(("add", name))
        wcds = self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]
        if name.endswith("WANConnectionDevice"):
            wcds["3"] = {}
        else:
            wcds["3"][name.rsplit(".", 1)[1]] = {"1": {}}
        return {"http_status": 200}

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.calls.append(("task", task["name"], task["objectName"]))
        return 200

    async def set_parameter_values(self, device_id, values):
        self.calls.append(("set", values))
        return {"http_status": 200}


@pytest.fixture
def fast(monkeypatch):
    from app.services import x_ctcom_wan_creator as c

    async def no_sleep(_):
        return None
    monkeypatch.setattr(c.asyncio, "sleep", no_sleep)


@pytest.mark.parametrize("mode,container", [("DHCP", "WANIPConnection"), ("STATIC", "WANIPConnection"), ("PPPOE", "WANPPPConnection")])
async def test_crear_wan_huawei(fast, mode, container):
    client = FakeClient()
    data = {"vlan": 999, "priority": 0, "username": "u", "password": "p", "ip": "192.0.2.10",
            "subnet_mask": "255.255.255.0", "gateway": "192.0.2.1", "dns": "8.8.8.8"}
    result = await create_huawei_wan(client, HW_ID, data, mode=mode)
    assert (result["wcd"], result["instance"]) == (3, 1)

    base = f"InternetGatewayDevice.WANDevice.1.WANConnectionDevice.3.{container}.1"
    sets = [c[1] for c in client.calls if c[0] == "set"]
    flat = {p: v for batch in sets for p, v, _ in batch}

    assert flat[f"{base}.X_HW_VLAN"] == 999
    assert flat[f"{base}.X_HW_SERVICELIST"] == "INTERNET"
    assert not [p for p in flat if "X_CT-COM" in p or "GponLink" in p]
    # Se lee la conexion nueva antes de configurarla, y se enciende al final.
    assert ("task", "refreshObject", base) in client.calls
    assert sets[-1] == [[f"{base}.Enable", True, "xsd:boolean"]]
    # Nunca toca las WAN existentes.
    assert not [p for p in flat if ".WANConnectionDevice.1." in p or ".WANConnectionDevice.2." in p]


async def test_editar_vlan_huawei_envia_x_hw(client, hw, monkeypatch):
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
    r = await client.patch(f"/api/devices/{HW_ID}/wan/1/ip/1", json={"vlan": 301, "priority": 3})
    assert r.status_code == 200, r.text
    by = {p.rsplit(".", 1)[1]: v for p, v, _ in sent}
    assert by.get("X_HW_VLAN") == 301 and by.get("X_HW_PRI") == 3
    assert not [p for p, _, _ in sent if "X_CT-COM" in p or "GponLink" in p or p.endswith("WanName")]


def test_ip_0000_no_cuenta_como_conectada():
    d = huawei()
    conn = d["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["1"]["WANIPConnection"]["1"]
    conn["ConnectionStatus"] = v("Connecting")
    conn["ExternalIPAddress"] = v("0.0.0.0")
    wans = {w["wan_connection_device"]: w for w in read_wan(d)}
    assert wans[1]["status"] == "Connecting"


def test_tr069_por_nombre_protege_otras_marcas():
    """ZY704dact, ZC-500W, RX8414CDW: TR-069 sin ServiceList, solo en el nombre."""
    d = huawei()
    conn = d["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["2"]["WANIPConnection"]["1"]
    for k in ("X_HW_SERVICELIST", "X_HW_VLAN", "X_HW_PRI", "X_HW_LANBIND"):
        conn.pop(k)
    conn["Name"] = v("2_TR069_R_VID_46")
    wans = {w["wan_connection_device"]: w for w in read_wan(d)}
    assert wans[2]["protected"] is True


def test_firewall_vsol_nivel_desconocido_no_cambia():
    from app.services.security_module import security_state as st
    vsol = {"InternetGatewayDevice": {"X_HW_Security": {"AclServices": {
        "FireWallGrade": v(2), "HTTPWanEnable": v(False)}}}}
    assert st(vsol)["firewall_label"] == "Desconocido (2)"
