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


@pytest.mark.parametrize("path,body", [
    ("wan/create-dhcp", {"vlan": 999}),
    ("wan/create-ip", {"vlan": 999, "addressing_type": "DHCP"}),
    ("wan/create-pppoe", {"vlan": 999, "username": "u", "password": "p"}),
    ("wan/vsol/create-ip", {"vlan": 999, "addressing_type": "DHCP"}),
    ("wan/vsol/create-pppoe", {"vlan": 999, "username": "u", "password": "p"}),
])
async def test_crear_wan_bloqueado_en_huawei(client, hw, path, body):
    await login(client, "jefe")
    r = await client.post(f"/api/devices/{HW_ID}/{path}", json=body)
    assert r.status_code == 400, r.text
    assert "Huawei" in r.json()["detail"]


async def test_cambiar_vlan_bloqueado_en_huawei(client, hw):
    await login(client, "jefe")
    r = await client.patch(f"/api/devices/{HW_ID}/wan/1/ip/1", json={"vlan": 301})
    assert r.status_code == 400
    assert "Huawei" in r.json()["detail"]
