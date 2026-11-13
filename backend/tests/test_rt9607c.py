"""RT9607C (OPTICTIMES, fw -1.2.0.30): 802.1p en Layer2Bridging, CATV
X_RZ_Catv y seguridad sin firewall.

Estructura tomada de la una RT9607C de laboratorio (laboratorio), anonimizada.
"""

import copy

import pytest

from app.services import l2_marking
from app.services.catv_reader import read_catv
from app.services.genieacs import genieacs
from app.services.security_module import security_state
from app.services.wan_reader import read_wan

from conftest import login

ID = "94026B-RT9607C-PRUEBA"
WCD = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"
L2 = "InternetGatewayDevice.Layer2Bridging"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def iface(key, ref):
    return {"AvailableInterfaceKey": v(key, False), "InterfaceReference": v(ref, False)}


def mark(interface, vlan, prio, enable=True):
    return {"MarkingInterface": v(interface), "VLANIDMark": v(vlan), "EthernetPriorityMark": v(prio),
            "MarkingEnable": v(enable), "VLANIDMarkOverride": v(True)}


def rt9607c(extra_wcd=False):
    def conn(name, vlan, svc, ip):
        return {"WANIPConnection": {"1": {
            "Name": v(name), "Enable": v(True), "ConnectionStatus": v("Connected", False),
            "AddressingType": v("Static"), "ExternalIPAddress": v(ip),
            "X_RTK_VlanId": v(vlan), "X_RTK_ServiceType": v(svc), "X_RTK_LanInterface": v(""),
        }}}

    wcds = {"2": conn("default wan", 150, 2, "192.0.2.24"), "3": conn("default wan", 46, 1, "10.1.0.255")}
    ifaces = {"14": iface(14, f"{WCD}.2"), "15": iface(15, f"{WCD}.2.WANIPConnection.1"),
              "16": iface(16, f"{WCD}.3"), "17": iface(17, f"{WCD}.3.WANIPConnection.1")}
    marks = {"1": mark("", -1, -1), "13": mark("14", 150, 1)}
    filters = {"14": {"FilterInterface": v("14")}, "15": {"FilterInterface": v("15")}}

    if extra_wcd:
        wcds["4"] = conn("ACS_INTERNET_DHCP_R_VID_999", 999, 2, "")
        ifaces["18"] = iface(18, f"{WCD}.4")
        ifaces["19"] = iface(19, f"{WCD}.4.WANIPConnection.1")
        filters["18"] = {"FilterInterface": v("19")}

    return {
        "_id": ID,
        "_deviceId": {"_Manufacturer": "OPTICTIMES", "_ProductClass": "RT9607C", "_SerialNumber": "PRUEBA"},
        "InternetGatewayDevice": {
            "DeviceInfo": {"X_RZ_WebEnable": v(True)},
            "ManagementServer": {"ConnectionRequestURL": v("http://10.1.0.255:7547/tr069", False)},
            "WANDevice": {"1": {"WANConnectionDevice": wcds}},
            "Layer2Bridging": {"AvailableInterface": ifaces, "Marking": marks, "Filter": filters},
            "X_RZ_Catv": {"RF_Enable": v(True), "PhyStatus": v(True, False), "InputPower": v("-3 dbm", False),
                          "OutputLevel": v("124 dbuV", False), "AGCLow": v("-16.5 dbm", False),
                          "AGCHigh": v("3 dbm", False)},
        },
    }


# --- Lectura -------------------------------------------------------------------

def test_prioridad_desde_layer2bridging():
    wans = {w["wan_connection_device"]: w for w in read_wan(rt9607c())}
    assert wans[2]["vlan"] == 150 and wans[2]["priority_8021p"] == 1
    assert wans[3]["priority_8021p"] is None and wans[3]["protected"] is True


def test_igd_con_x_rz_802_1p_no_usa_marcas():
    from test_realtek import igd

    device = igd()
    assert l2_marking.uses_marking(device) is False
    wans = {w["wan_connection_device"]: w for w in read_wan(device)}
    assert wans[1]["priority_8021p"] == 0 and wans[2]["priority_8021p"] == 2


def test_catv_x_rz():
    catv = read_catv(rt9607c())
    assert (catv["supported"], catv["enabled"], catv["writable"], catv["driver"]) == (True, True, True, "x_rz_catv")
    labels = {m["label"]: m["value"] for m in catv["metrics"]}
    assert labels["Potencia de entrada"] == "-3 dbm" and labels["Señal óptica RF"] == "Presente"


def test_seguridad_sin_firewall_explica_y_muestra_web():
    st = security_state(rt9607c())
    assert st["supported"] is False and "firewall" in st["reason"]
    assert st["notes"] == [{"label": "Interfaz web de la ONU", "value": "Habilitada"}]


# --- Escritura de marcas -----------------------------------------------------------

class FakeONU:
    def __init__(self, device):
        self.device = device
        self.tasks = []

    async def get_device(self, device_id):
        return copy.deepcopy(self.device)

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.tasks.append((task["name"], task.get("objectName"), task.get("parameterValues"), connection_request))
        if task["name"] == "addObject" and task["objectName"] == f"{L2}.Marking":
            self.device["InternetGatewayDevice"]["Layer2Bridging"]["Marking"]["14"] = mark("", -1, -1, enable=False)
        return 200


async def test_editar_actualiza_la_marca_existente():
    onu = FakeONU(rt9607c())
    number = await l2_marking.apply(onu, ID, 2, vlan=151, priority=5)
    assert number == "13"
    (name, _, values, cr), = onu.tasks
    assert name == "setParameterValues" and cr is True
    assert {p: val for p, val, _ in values} == {f"{L2}.Marking.13.VLANIDMark": 151,
                                               f"{L2}.Marking.13.EthernetPriorityMark": 5}


async def test_crea_marca_si_no_existe():
    onu = FakeONU(rt9607c(extra_wcd=True))
    number = await l2_marking.apply(onu, ID, 4, vlan=999, priority=3)
    assert number == "14"
    assert [t[0] for t in onu.tasks] == ["addObject", "refreshObject", "setParameterValues"]
    by = {p.rsplit(".", 1)[1]: val for p, val, _ in onu.tasks[-1][2]}
    assert by == {"MarkingBridgeReference": 0, "MarkingInterface": "18", "VLANIDMarkOverride": True,
                  "VLANIDUntag": False, "VLANIDMark": 999, "EthernetPriorityMark": 3, "MarkingEnable": True}


async def test_sin_prioridad_no_crea_marca():
    onu = FakeONU(rt9607c(extra_wcd=True))
    assert await l2_marking.apply(onu, ID, 4, vlan=998) is None
    assert onu.tasks == []


async def test_borrar_quita_marca_y_filtros_solo_de_ese_wcd():
    device = rt9607c(extra_wcd=True)
    device["InternetGatewayDevice"]["Layer2Bridging"]["Marking"]["14"] = mark("18", 999, 3)
    onu = FakeONU(device)
    removed = await l2_marking.remove(onu, ID, device, 4)
    assert removed == ["Marking.14", "Filter.18"]
    assert onu.tasks[0][:2] == ("refreshObject", L2)
    assert [t[1] for t in onu.tasks[1:]] == [f"{L2}.Marking.14", f"{L2}.Filter.18"]


# --- Endpoint -----------------------------------------------------------------------

async def test_editar_prioridad_por_api(client, monkeypatch):
    import asyncio

    state = {"device": rt9607c()}
    sent = []

    async def get_device(device_id):
        return copy.deepcopy(state["device"])

    async def spv(device_id, values):
        sent.extend(values)
        return {"http_status": 200}

    async def post_task(device_id, task, connection_request=False, wait_ms=3000):
        sent.extend(task.get("parameterValues") or [])
        state["device"]["InternetGatewayDevice"]["Layer2Bridging"]["Marking"]["13"]["EthernetPriorityMark"] = v(4)
        return 200

    async def no_sleep(_):
        return None

    monkeypatch.setattr(genieacs, "get_device", get_device)
    monkeypatch.setattr(genieacs, "set_parameter_values", spv)
    monkeypatch.setattr(genieacs, "post_task", post_task)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    await login(client, "jefe")
    r = await client.patch(f"/api/devices/{ID}/wan/2/ip/1", json={"priority": 4})
    assert r.status_code == 200, r.text
    assert [f"{L2}.Marking.13.EthernetPriorityMark", 4, "xsd:int"] in sent
    assert r.json()["status"] == "CONFIRMADO"
