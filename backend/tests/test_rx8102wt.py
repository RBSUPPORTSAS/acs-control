"""RX8102WT (Realtek, fw V1.9.2.0-220715): 802.1p en VlanPriMark.

Estructura tomada de una RX8102WT de laboratorio, anonimizada.
"""

import copy

from app.services.catv_reader import read_catv
from app.services.genieacs import genieacs
from app.services.l2_marking import uses_marking
from app.services.vendor_wan import create_vendor_wan, translate, vendor_for
from app.services.wan_reader import read_wan

from conftest import login

ID = "94026B-RX8102WT-PRUEBA"
WCD = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def conn(vlan, prio, svc, ip, mode="Static"):
    return {"WANIPConnection": {"1": {
        "Name": v(""), "Enable": v(True), "ConnectionStatus": v("Connected", False),
        "AddressingType": v(mode), "ExternalIPAddress": v(ip), "VlanPriMark": v(prio),
        "X_RTK_VlanId": v(vlan), "X_RTK_ServiceType": v(svc), "X_RTK_LanInterface": v("lan1,lan2,ssid1"),
    }}}


def rx8102wt():
    return {
        "_id": ID,
        "_deviceId": {"_Manufacturer": "Realtek", "_ProductClass": "RX8102WT", "_SerialNumber": "PRUEBA"},
        "InternetGatewayDevice": {
            "ManagementServer": {"ConnectionRequestURL": v("http://10.1.0.62:7547/tr069", False)},
            "WANDevice": {"1": {"WANConnectionDevice": {
                "1": conn(150, 0, 2, "192.0.2.252"),
                "2": conn(46, 2, 1, "10.1.0.62", "DHCP"),
            }}},
            "X_RZ_Catv": {"RF_Enable": v(False), "InputPower": v("", False), "OutputLevel": v("", False),
                          "AGCLow": v("", False), "AGCHigh": v("", False)},
        },
    }


def test_prioridad_desde_vlanprimark():
    wans = {w["wan_connection_device"]: w for w in read_wan(rx8102wt())}
    assert (wans[1]["vlan"], wans[1]["priority_8021p"]) == (150, 0)
    assert (wans[2]["vlan"], wans[2]["priority_8021p"], wans[2]["protected"]) == (46, 2, True)


def test_no_usa_layer2bridging():
    assert uses_marking(rx8102wt()) is False


def test_traduce_prioridad_a_vlanprimark():
    assert vendor_for(rx8102wt(), "realtek") == "realtek_vpm"
    base = f"{WCD}.3.WANIPConnection.1"
    out = translate([
        [f"{base}.X_CT-COM_VLANIDMark", 999, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_802-1pMark", 3, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
    ], "realtek_vpm")
    assert out == [
        [f"{base}.X_RTK_VlanId", 999, "xsd:int"],
        [f"{base}.VlanPriMark", 3, "xsd:unsignedInt"],
        [f"{base}.X_RTK_ServiceType", 2, "xsd:int"],
    ]


def test_igd_sigue_usando_x_rz_802_1p():
    from test_realtek import igd
    assert vendor_for(igd(), "realtek") == "realtek"


def test_catv_sin_mediciones_no_muestra_vacios():
    catv = read_catv(rx8102wt())
    assert (catv["supported"], catv["enabled"], catv["driver"]) == (True, False, "x_rz_catv")
    assert catv["metrics"] == []


class FakeClient:
    def __init__(self):
        self.device = rx8102wt()
        self.sets = []

    def wcds(self):
        return self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]

    async def get_device(self, device_id):
        return copy.deepcopy(self.device)

    async def add_object(self, device_id, name):
        if name.endswith("WANConnectionDevice"):
            self.wcds()["3"] = {}
        else:
            self.wcds()["3"][name.rsplit(".", 1)[1]] = {"1": {}}
        return {"http_status": 200}

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        return 200

    async def set_parameter_values(self, device_id, values):
        self.sets.append(values)
        return {"http_status": 200}


async def test_crear_wan_envia_vlanprimark(monkeypatch):
    from app.services import x_ctcom_wan_creator as c

    async def no_sleep(_):
        return None
    monkeypatch.setattr(c.asyncio, "sleep", no_sleep)

    client = FakeClient()
    await create_vendor_wan(client, ID, {"vlan": 999, "priority": 3}, mode="DHCP", vendor="realtek")
    flat = {p: val for batch in client.sets for p, val, _ in batch}
    base = f"{WCD}.3.WANIPConnection.1"
    assert flat[f"{base}.VlanPriMark"] == 3 and flat[f"{base}.X_RTK_VlanId"] == 999
    assert f"{base}.X_RZ_802-1pMark" not in flat


async def test_editar_prioridad_por_api(client, monkeypatch):
    import asyncio
    sent = []

    async def get_device(device_id):
        return rx8102wt()

    async def spv(device_id, values):
        sent.extend(values)
        return {"http_status": 200}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(genieacs, "get_device", get_device)
    monkeypatch.setattr(genieacs, "set_parameter_values", spv)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    await login(client, "jefe")
    r = await client.patch(f"/api/devices/{ID}/wan/1/ip/1", json={"priority": 4})
    assert r.status_code == 200, r.text
    assert [f"{WCD}.1.WANIPConnection.1.VlanPriMark", 4, "xsd:unsignedInt"] in sent
    assert not [p for p, _, _ in sent if "X_RZ_802-1pMark" in p]
