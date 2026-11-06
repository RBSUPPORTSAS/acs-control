"""Creacion de WAN en la familia x_ctcom (p. ej. HG102DWT).

Validado en una HG102DWT real: la VLAN vive en X_CT-COM_WANGponLinkConfig;
en PPPoE, X_CT-COM_VLANMode de la conexion y el Mode del enlace son el mismo
campo; las WAN se crean apagadas y hay que encenderlas al final.
"""

import pytest

from app.services import x_ctcom_wan_creator as creator
from app.services.genieacs import genieacs
from app.services.wan_reader import read_wan
from app.services.x_ctcom_wan_builder import build_dhcp_values

from conftest import login

WCD = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"
HG_ID = "80F7A6-HG102DWT-PRUEBA"


def v(value):
    return {"_value": value, "_object": False}


def hg_device(extra_wcd=None):
    wcds = {
        "1": {
            "X_CT-COM_WANGponLinkConfig": {"VLANIDMark": v(200), "802-1pMark": v(0), "Mode": v(2)},
            "WANIPConnection": {"1": {
                "Name": v("Internet_R_0_0"), "AddressingType": v("Static"),
                "ConnectionType": v("IP_Routed"), "Enable": v(True),
                "X_CT-COM_ServiceList": v("INTERNET"),
            }},
        },
        "2": {
            "X_CT-COM_WANGponLinkConfig": {"VLANIDMark": v(46), "802-1pMark": v(2), "Mode": v(2)},
            "WANIPConnection": {"1": {
                "Name": v("TR069_Internet_R_0_0"), "AddressingType": v("DHCP"),
                "ConnectionType": v("IP_Routed"), "Enable": v(True),
                "X_CT-COM_ServiceList": v("TR069,INTERNET"),
            }},
        },
    }
    if extra_wcd:
        wcds.update(extra_wcd)
    return {
        "_id": HG_ID,
        "_deviceId": {"_Manufacturer": "HGU", "_ProductClass": "HG102DWT", "_SerialNumber": "P1"},
        "InternetGatewayDevice": {"WANDevice": {"1": {"WANConnectionDevice": wcds}}},
    }


def test_lee_vlan_del_enlace_x_ctcom():
    wans = {w["wan_connection_device"]: w for w in read_wan(hg_device())}
    assert (wans[1]["vlan"], wans[1]["priority_8021p"]) == (200, 0)
    assert (wans[2]["vlan"], wans[2]["priority_8021p"]) == (46, 2)


def test_ip_fija_exige_todos_los_datos():
    with pytest.raises(ValueError):
        build_dhcp_values(3, 1, {"vlan": 999, "ip": "192.0.2.10"}, mode="STATIC")

    values = build_dhcp_values(
        3, 1,
        {"vlan": 999, "ip": "192.0.2.10", "subnet_mask": "255.255.255.0",
         "gateway": "192.0.2.1", "dns": "8.8.8.8"},
        mode="STATIC",
    )["parameter_values"]
    by_name = {p.rsplit(".", 1)[1]: val for p, val, _ in values}
    assert by_name["AddressingType"] == "Static"
    assert by_name["ExternalIPAddress"] == "192.0.2.10"


class FakeClient:
    """ONU simulada: registra cada setParameterValues en orden."""

    def __init__(self):
        self.device = hg_device()
        self.sets = []

    async def get_device(self, device_id):
        return self.device

    async def add_object(self, device_id, name):
        if name.endswith("WANConnectionDevice"):
            self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["3"] = {}
        else:
            container = name.rsplit(".", 1)[1]
            self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["3"][container] = {"1": {}}
        return {"http_status": 200}

    async def set_parameter_values(self, device_id, values):
        self.sets.append(values)
        return {"http_status": 200}

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        # Se registra para comprobar que el enlace se relee antes de reescribirlo.
        self.sets.append([[task["objectName"], "refreshObject", task["name"]]])
        return 200


@pytest.fixture
def fast(monkeypatch):
    async def no_sleep(_):
        return None
    monkeypatch.setattr(creator.asyncio, "sleep", no_sleep)


@pytest.mark.parametrize("kind", ["pppoe", "dhcp", "static"])
async def test_crea_y_termina_con_enlace_en_mode_2_y_encendida(fast, kind):
    client = FakeClient()
    data = {"vlan": 999, "priority": 0, "username": "u", "password": "p",
            "ip": "192.0.2.10", "subnet_mask": "255.255.255.0", "gateway": "192.0.2.1", "dns": "8.8.8.8"}

    if kind == "pppoe":
        result = await creator.create_x_ctcom_pppoe(client, HG_ID, data)
        container = "WANPPPConnection"
    else:
        result = await creator.create_x_ctcom_dhcp(client, HG_ID, data, mode="STATIC" if kind == "static" else "DHCP")
        container = "WANIPConnection"

    assert result["wcd"] == 3

    flat = [(p, val) for batch in client.sets for p, val, _ in batch]
    paths = [p for p, _ in flat]

    # La conexion se configura apagada...
    assert (f"{WCD}.3.{container}.1.Enable", False) in flat
    # ...el ultimo paso la enciende...
    assert client.sets[-1] == [[f"{WCD}.3.{container}.1.Enable", True, "xsd:boolean"]]
    # ...y justo antes se reescribe el enlace con Mode 2, despues de la conexion.
    last_mode = max(i for i, p in enumerate(paths) if p.endswith("WANGponLinkConfig.Mode"))
    last_conn = max(i for i, p in enumerate(paths) if f".{container}.1." in p and not p.endswith(".Enable"))
    assert last_mode > last_conn
    assert flat[last_mode][1] == 2
    # El enlace se relee de la ONU justo antes (GenieACS no reenvia valores de su cache).
    refresh = max(i for i, (p, val) in enumerate(flat) if val == "refreshObject")
    assert last_conn < refresh < last_mode
    assert paths[refresh].endswith(".3.X_CT-COM_WANGponLinkConfig")
    # Nunca toca las WAN existentes (1 y la TR-069 en 2).
    assert not [p for p in paths if f"{WCD}.1." in p or f"{WCD}.2." in p]


async def test_ip_fija_rechaza_modelos_no_validados(client, monkeypatch):
    from conftest import DEVICE, DEVICE_ID
    await login(client, "jefe")
    r = await client.post(f"/api/devices/{DEVICE_ID}/wan/create-ip", json={
        "addressing_type": "STATIC", "vlan": 999, "ip": "192.0.2.10",
        "subnet_mask": "255.255.255.0", "gateway": "192.0.2.1", "dns": "8.8.8.8",
    })
    assert r.status_code == 400
    assert "no está validada" in r.json()["detail"]


async def test_ip_fija_valida_direcciones(client, monkeypatch):
    async def fake_get_device(device_id):
        return hg_device()
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)
    await login(client, "jefe")
    r = await client.post(f"/api/devices/{HG_ID}/wan/create-ip", json={
        "addressing_type": "STATIC", "vlan": 999, "ip": "192.0.2.300",
        "subnet_mask": "255.255.255.0", "gateway": "192.0.2.1", "dns": "8.8.8.8",
    })
    assert r.status_code == 400
    assert "inválidos" in r.json()["detail"]
