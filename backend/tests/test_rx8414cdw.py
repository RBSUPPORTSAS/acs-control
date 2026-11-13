"""X_CMCC (RX8414CDW fw V02.01.02): WAN, seguridad y proteccion TR-069.

Estructura tomada de una RX8414CDW de laboratorio, anonimizada.
Todas las WAN (tambien la TR-069) son conexiones del mismo WCD 1 y los
booleanos llegan como texto "TRUE"/"FALSE".
"""

import copy

import pytest

from app.services.genieacs import genieacs
from app.services.security_module import firewall_write, security_state, service_changes
from app.services.vendor_wan import create_vendor_wan, translate
from app.services.wan_driver import detect_wan_driver
from app.services.wan_reader import read_wan

from conftest import login

ID = "94026B-RX8414CDW-PRUEBA"
WCD1 = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1"
LAN1 = "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.1"


def v(value, writable=True, t=None):
    out = {"_value": value, "_object": False, "_writable": writable}
    if t:
        out["_type"] = t
    return out


def conn(name, vlan, prio, svc, ip, nat="TRUE", lan=""):
    return {
        "Name": v(name), "Enable": v("TRUE"), "ConnectionStatus": v("Connected", False),
        "AddressingType": v("Static"), "ExternalIPAddress": v(ip), "NATEnabled": v(nat),
        "X_CMCC_VLANIDMark": v(vlan), "X_CMCC_802-1pMark": v(prio), "X_CMCC_ServiceList": v(svc),
        "X_CMCC_LanInterface": v(lan), "X_CMCC_VLANMode": v(2), "X_CMCC_IPMode": v(1),
    }


def rx8414():
    return {
        "_id": ID,
        "_deviceId": {"_Manufacturer": "OPTI", "_ProductClass": "RX8414CDW", "_SerialNumber": "PRUEBA"},
        "InternetGatewayDevice": {
            "ManagementServer": {"ConnectionRequestURL": v("http://10.1.0.204:58000", False)},
            "DeviceInfo": {"X_CMCC_ServiceManage": {
                "TelnetEnable": v("FALSE", t="xsd:boolean"), "TelnetWANEnable": v("FALSE", t="xsd:boolean"),
                "TelnetPort": v(23), "TelnetPassword": v("secreto"), "TelnetUserName": v("admin"),
                "FtpEnable": v("FALSE", t="xsd:boolean"), "FtpPort": v(21), "FtpPassword": v("secreto"),
            }},
            "X_CMCC_Security": {
                "FirewallEnable": v("FALSE", t="xsd:boolean"), "FirewallLevel": v(0),
                "DoSEnable": v("TRUE"), "PortScanEnable": v("FALSE"), "MacFilterEnable": v("FALSE"),
            },
            "WANDevice": {"1": {"WANConnectionDevice": {"1": {"WANIPConnection": {
                "1": conn("1_INTERNET_R_VID_100", 100, 0, "INTERNET", "192.0.2.45", lan=LAN1),
                "2": conn("2_TR069_R_VID_46", 46, 2, "TR069", "10.1.0.204", nat="FALSE"),
            }}}}},
        },
    }


def test_driver_y_lectura():
    d = rx8414()
    assert detect_wan_driver(d) == "cmcc"
    wans = {w["instance"]: w for w in read_wan(d)}
    assert (wans[1]["vlan"], wans[1]["priority_8021p"], wans[1]["services"]) == (100, 0, ["INTERNET"])
    assert wans[1]["enabled"] is True and wans[1]["nat"] is True and LAN1 in wans[1]["lan_binding"]
    assert (wans[2]["vlan"], wans[2]["priority_8021p"], wans[2]["protected"]) == (46, 2, True)
    assert wans[2]["nat"] is False


def test_traduccion_x_cmcc():
    base = f"{WCD1}.WANIPConnection.3"
    out = translate([
        [f"{base}.X_CT-COM_VLANIDMark", 999, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_802-1pMark", 3, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        [f"{base}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
        [f"{base}.X_CT-COM_LanInterface", LAN1, "xsd:string"],
        [f"{WCD1}.X_CT-COM_WANGponLinkConfig.VLANIDMark", 999, "xsd:unsignedInt"],
    ], "cmcc")
    by = {p.rsplit(".", 1)[1]: val for p, val, _ in out}
    assert by == {"X_CMCC_VLANIDMark": 999, "X_CMCC_802-1pMark": 3, "X_CMCC_VLANMode": 2,
                  "X_CMCC_ServiceList": "INTERNET", "X_CMCC_LanInterface": LAN1}


class FakeONU:
    def __init__(self):
        self.device = rx8414()
        self.tasks = []
        self.sets = []

    def conns(self):
        return self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["1"]["WANIPConnection"]

    async def get_device(self, device_id):
        return copy.deepcopy(self.device)

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.tasks.append((task["name"], task.get("objectName")))
        if task["name"] == "addObject":
            self.conns()["3"] = {"Name": v(""), "Enable": v("FALSE")}
        return 200

    async def add_object(self, device_id, name):
        raise AssertionError("En X_CMCC no se crea un WCD nuevo")

    async def set_parameter_values(self, device_id, values):
        self.sets.append(values)
        return {"http_status": 200}


async def test_crear_wan_en_el_mismo_wcd(monkeypatch):
    from app.services import x_ctcom_wan_creator as c

    async def no_sleep(_):
        return None
    monkeypatch.setattr(c.asyncio, "sleep", no_sleep)
    monkeypatch.setattr("asyncio.sleep", no_sleep)

    onu = FakeONU()
    r = await create_vendor_wan(onu, ID, {"vlan": 999, "priority": 3}, mode="DHCP", vendor="cmcc")
    assert (r["wcd"], r["instance"]) == (1, 3)
    assert onu.tasks[0] == ("addObject", f"{WCD1}.WANIPConnection")
    flat = {p: val for batch in onu.sets for p, val, _ in batch}
    base = f"{WCD1}.WANIPConnection.3"
    assert flat[f"{base}.X_CMCC_VLANIDMark"] == 999 and flat[f"{base}.X_CMCC_802-1pMark"] == 3
    assert flat[f"{base}.X_CMCC_VLANMode"] == 2 and flat[f"{base}.Enable"] is True
    assert not [p for p in flat if "X_CT-COM" in p or ".WANIPConnection.1." in p or ".WANIPConnection.2." in p]


@pytest.fixture
def cm(monkeypatch):
    async def fake_get_device(device_id):
        return rx8414()
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)


async def test_tr069_no_se_borra_ni_edita(client, cm):
    await login(client, "jefe")
    assert (await client.delete(f"/api/devices/{ID}/wan/1/WANIPConnection/2")).status_code == 403
    assert (await client.patch(f"/api/devices/{ID}/wan/1/ip/2", json={"vlan": 47})).status_code == 403


async def test_borrar_internet_borra_solo_la_conexion(client, cm, monkeypatch):
    sent = []

    async def post_task(device_id, task, connection_request=False, wait_ms=3000):
        sent.append(task)
        return 200

    async def no_sleep(_):
        return None

    monkeypatch.setattr(genieacs, "post_task", post_task)
    monkeypatch.setattr("asyncio.sleep", no_sleep)
    await login(client, "jefe")
    await client.delete(f"/api/devices/{ID}/wan/1/WANIPConnection/1")
    assert sent and sent[0] == {"name": "deleteObject", "objectName": f"{WCD1}.WANIPConnection.1"}


def test_seguridad_x_cmcc():
    st = security_state(rx8414())
    assert st["supported"] is True and st["firewall_kind"] == "cmcc"
    assert (st["firewall_grade"], st["firewall_label"]) == (0, "Apagado")
    svc = {s["id"]: s for s in st["services"]}
    assert set(svc) == {"telnet", "ftp"}
    assert svc["telnet"]["wan_writable"] and svc["telnet"]["lan_writable"] and svc["telnet"]["wan_port"] == 23
    assert svc["ftp"]["lan_writable"] and not svc["ftp"]["wan_writable"]
    assert {"label": "Protección contra DoS", "value": "Activado"} in st["notes"]
    assert "secreto" not in str(st)


def test_escrituras_seguridad_x_cmcc():
    d = rx8414()
    assert firewall_write(d, 1) == ("InternetGatewayDevice.X_CMCC_Security.FirewallEnable", True, "xsd:boolean")
    values, _ = service_changes(d, "telnet", {"lan_enabled": True})
    assert values == [["InternetGatewayDevice.DeviceInfo.X_CMCC_ServiceManage.TelnetEnable", True, "xsd:boolean"]]
