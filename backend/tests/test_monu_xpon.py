"""MONU xPON+1GE+1FE+WIFI+CATV (fw V3.3.0-210624): gateway, seguridad y
ONU lenta (~22 s por sesion).

Estructura tomada de una ONU de laboratorio, anonimizada.
No expone CATV por TR-069 pese al nombre del modelo.
"""

import httpx
import pytest

from app.services.catv_reader import read_catv
from app.services.genieacs import GenieACSClient
from app.services.security_module import security_state, service_changes
from app.services.wan_reader import read_wan

WCD = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def link(vlan, prio):
    return {"Enable": v(True), "Mode": v(2), "VLANIDMark": v(vlan), "802-1pMark": v(prio)}


def monu():
    return {
        "_id": "70B64F-xPON%2B1GE%2B1FE%2BWIFI%2BCATV-PRUEBA",
        "_deviceId": {"_Manufacturer": "MONU", "_ProductClass": "xPON+1GE+1FE+WIFI+CATV", "_SerialNumber": "PRUEBA"},
        "InternetGatewayDevice": {
            "ManagementServer": {"ConnectionRequestURL": v("http://10.1.0.72:7547/tr69", False)},
            "DeviceInfo": {"X_CT-COM_ServiceManage": {
                "TelnetEnable": v(False), "TelnetPort": v(23), "TelnetPassword": v("secreto"),
                "FtpEnable": v(False), "FtpPort": v(21),
            }},
            "Layer3Forwarding": {"Forwarding": {
                "1": {"DestIPAddress": v("0.0.0.0"), "GatewayIPAddress": v("192.0.2.1"), "Type": v("Default"),
                      "Interface": v(f"{WCD}.1.WANIPConnection.1")},
                "2": {"DestIPAddress": v("10.1.0.0"), "GatewayIPAddress": v("0.0.0.0"), "Type": v("Network"),
                      "Interface": v(f"{WCD}.2.WANIPConnection.1")},
            }},
            "WANDevice": {"1": {"WANConnectionDevice": {
                "1": {"X_CT-COM_WANGponLinkConfig": link(150, 0), "WANIPConnection": {"1": {
                    "Name": v("1_INTERNET_R_VID_150"), "Enable": v(True), "ConnectionStatus": v("Connected", False),
                    "AddressingType": v("Static"), "ExternalIPAddress": v("192.0.2.96"), "DefaultGateway": v(""),
                    "X_CT-COM_ServiceList": v("INTERNET"), "X_CT-COM_LanInterface": v(""),
                }}},
                "2": {"X_CT-COM_WANGponLinkConfig": link(46, 1), "WANIPConnection": {"1": {
                    "Name": v("2_TR069_R_VID_46"), "Enable": v(True), "ConnectionStatus": v("Connected", False),
                    "AddressingType": v("DHCP"), "ExternalIPAddress": v("10.1.0.72"), "DefaultGateway": v("10.1.0.1"),
                    "X_CT-COM_ServiceList": v("TR069"), "X_CT-COM_LanInterface": v(""),
                }}},
            }}},
        },
    }


def test_gateway_desde_la_ruta_por_defecto():
    wans = {w["wan_connection_device"]: w for w in read_wan(monu())}
    assert wans[1]["gateway"] == "192.0.2.1"
    assert wans[2]["gateway"] == "10.1.0.1"
    assert (wans[1]["vlan"], wans[2]["vlan"], wans[2]["priority_8021p"], wans[2]["protected"]) == (150, 46, 1, True)


def test_gateway_reportado_no_se_cambia():
    d = monu()
    d["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["1"]["WANIPConnection"]["1"]["DefaultGateway"] = v("192.0.2.254")
    assert read_wan(d)[0]["gateway"] == "192.0.2.254"


def test_sin_catv():
    assert read_catv(monu())["supported"] is False


def test_seguridad_telnet_ftp_sin_firewall():
    st = security_state(monu())
    assert st["supported"] is True and st["firewall_kind"] is None and st["firewall_label"] is None
    svc = {s["id"]: s for s in st["services"]}
    assert set(svc) == {"telnet", "ftp"}
    assert svc["telnet"]["lan_writable"] and not svc["telnet"]["wan_writable"]
    assert "secreto" not in str(st)
    values, _ = service_changes(monu(), "telnet", {"lan_enabled": True})
    assert values == [["InternetGatewayDevice.DeviceInfo.X_CT-COM_ServiceManage.TelnetEnable", True, "xsd:boolean"]]


@pytest.mark.parametrize("method,args", [
    ("set_parameter_values", ([["a.b", 1, "xsd:int"]],)),
    ("add_object", ("a.b",)),
    ("delete_object", ("a.b.1",)),
])
async def test_onu_lenta_queda_en_cola(monkeypatch, method, args):
    async def slow_post(self, *a, **k):
        raise httpx.ReadTimeout("")

    monkeypatch.setattr(httpx.AsyncClient, "post", slow_post)
    r = await getattr(GenieACSClient(), method)("ID", *args)
    assert r["http_status"] == 202
