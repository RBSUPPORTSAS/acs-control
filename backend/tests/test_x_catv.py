"""X_CATV (KM1303, SML-702XW, ONT1GE1FE1TV...): crear, editar y borrar WAN.

Estructura tomada de la KM1303 70A56A54155F (fw V2.1.14), anonimizada.
Lo validado en la ONU real:
- La WAN TR-069 (VLAN 46) no se publica: solo en X_CATV_WANIndex.
- Lista un WCD "fantasma" (enlace con "" y conexiones sin valores);
  al crear un WCD, la ONU devuelve ese mismo numero.
- VLAN y 802.1p van en X_CATV_WANGponLinkConfig del WCD.
"""

import copy

import pytest

from app.services.genieacs import genieacs
from app.services.vendor_wan import translate, vendor_of
from app.services.wan_reader import read_wan
from app.services import x_catv_wan_creator as xc

from conftest import login

ID = "p%C2%A5j-KM1303-PRUEBA"
WCD = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"
LAN1 = "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.1"
WLAN4 = "InternetGatewayDevice.LANDevice.1.WLANConfiguration.4"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def blank(writable=True):
    """Parametro listado por la ONU pero sin valor (fantasma)."""
    return {"_object": False, "_writable": writable}


def link(vlan, prio=0):
    return {"Enable": v(True), "Mode": v(2), "VLANIDMark": v(vlan), "802-1pMark": v(prio)}


def km1303(ghost_conn=False):
    ghost = {
        "X_CATV_WANGponLinkConfig": {k: v("") for k in ("Enable", "Mode", "VLANIDMark", "802-1pMark")},
        "WANIPConnection": {},
        "WANPPPConnection": {},
    }
    if ghost_conn:
        ghost["WANIPConnection"]["1"] = {"Name": blank(), "Enable": blank(), "ExternalIPAddress": blank()}

    return {
        "_id": ID,
        "_deviceId": {"_Manufacturer": "CDT", "_ProductClass": "KM1303", "_SerialNumber": "PRUEBA"},
        "InternetGatewayDevice": {
            "ManagementServer": {"ConnectionRequestURL": v("http://10.1.0.28:7547/tr069", False)},
            "WANDevice": {"1": {
                "X_CATV_WANIndex": v('"1.1;STATIC_Routed;150;INTERNET","0.1;DHCP_Routed;46;TR069"', False),
                "WANConnectionDevice": {
                    "1": {
                        "X_CATV_WANGponLinkConfig": link(150),
                        "WANIPConnection": {"1": {
                            "Name": v("1_INTERNET_R_VID_150"), "Enable": v(True),
                            "ConnectionStatus": v("Connected", False), "AddressingType": v("Static"),
                            "ExternalIPAddress": v("192.0.2.170"), "SubnetMask": v("255.255.255.0"),
                            "DefaultGateway": v("192.0.2.1"), "DNSServers": v("8.8.8.8"),
                            "NATEnabled": v(True), "MaxMTUSize": v(1500),
                            "X_CATV_ServiceList": v("INTERNET"), "X_CATV_LanInterface": v(LAN1),
                        }},
                        "WANPPPConnection": {},
                    },
                    "2": ghost,
                },
            }},
        },
    }


# --- Lectura -------------------------------------------------------------------

def test_wan_tr069_oculta_se_muestra_y_queda_protegida():
    wans = {w["wan_connection_device"]: w for w in read_wan(km1303())}
    assert wans[0]["vlan"] == 46 and wans[0]["services"] == ["TR069"]
    assert wans[0]["ip"] == "10.1.0.28" and wans[0]["protected"] is True
    assert wans[1]["vlan"] == 150 and wans[1]["protected"] is False
    assert 2 not in wans


def test_conexion_fantasma_no_se_lista():
    wans = read_wan(km1303(ghost_conn=True))
    assert sorted(w["wan_connection_device"] for w in wans) == [0, 1]


def test_wcd_fantasma_no_cuenta_como_real():
    assert xc.real_wcds(km1303()) == {1}
    assert xc.real_wcds(km1303(ghost_conn=True)) == {1}


# --- Traduccion (editar) ---------------------------------------------------------

def test_traduce_a_x_catv():
    conn = f"{WCD}.2.WANIPConnection.1"
    out = translate([
        [f"{conn}.X_CT-COM_VLANIDMark", 998, "xsd:unsignedInt"],
        [f"{conn}.X_CT-COM_802-1pMark", 3, "xsd:unsignedInt"],
        [f"{WCD}.2.X_CT-COM_WANGponLinkConfig.VLANIDMark", 998, "xsd:unsignedInt"],
        [f"{WCD}.2.X_CT-COM_WANGponLinkConfig.802-1pMark", 3, "xsd:unsignedInt"],
        [f"{WCD}.2.WanName", "2_INTERNET_R_VID_998", "xsd:string"],
        [f"{conn}.vsName", "x", "xsd:string"],
        [f"{conn}.X_CT-COM_LanInterface", WLAN4, "xsd:string"],
        [f"{conn}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
        [f"{conn}.X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        [f"{conn}.X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        [f"{conn}.Name", "2_INTERNET_R_VID_998", "xsd:string"],
    ], vendor_of("x_catv_wan"))
    by = {p: val for p, val, _ in out}
    assert by == {
        f"{WCD}.2.X_CATV_WANGponLinkConfig.VLANIDMark": 998,
        f"{WCD}.2.X_CATV_WANGponLinkConfig.802-1pMark": 3,
        f"{conn}.X_CATV_LanInterface": WLAN4,
        f"{conn}.X_CATV_ServiceList": "INTERNET",
        f"{conn}.X_CATV_IPMode": 1,
        f"{conn}.Name": "2_INTERNET_R_VID_998",
    }


def test_huawei_y_realtek_no_cambian():
    conn = f"{WCD}.3.WANIPConnection.1"
    values = [
        [f"{conn}.X_CT-COM_VLANIDMark", 999, "xsd:unsignedInt"],
        [f"{conn}.X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
        [f"{conn}.X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        [f"{WCD}.3.X_CT-COM_WANGponLinkConfig.Mode", 2, "xsd:unsignedInt"],
    ]
    assert translate(values, "huawei") == [
        [f"{conn}.X_HW_VLAN", 999, "xsd:unsignedInt"],
        [f"{conn}.X_HW_SERVICELIST", "INTERNET", "xsd:string"],
    ]
    assert translate(values, "realtek") == [
        [f"{conn}.X_RTK_VlanId", 999, "xsd:int"],
        [f"{conn}.X_RTK_ServiceType", 2, "xsd:int"],
    ]


# --- Crear (simulacion de la ONU) -------------------------------------------------

def _set(tree, path, value):
    node = tree
    parts = path.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = v(value)


class FakeONU:
    """Encola tareas; la connection request ejecuta toda la cola en una
    sesion, como GenieACS. addObject de WCD devuelve el numero fantasma."""

    def __init__(self, conn_ok=True):
        self.device = km1303()
        self.queue = []
        self.sessions = []
        self.conn_ok = conn_ok
        self.deleted_tasks = []

    def wcds(self):
        return self.device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]

    async def get_device(self, device_id):
        return copy.deepcopy(self.device)

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.queue.append(task)
        if not connection_request:
            return 202
        self.sessions.append([t["name"] for t in self.queue])
        for t in self.queue:
            name = t["name"]
            if name == "addObject" and t["objectName"] == WCD:
                self.wcds()["2"] = {"X_CATV_WANGponLinkConfig": {"Enable": v(True), "Mode": v(1), "VLANIDMark": v(0), "802-1pMark": v(4294967295)},
                                    "WANIPConnection": {}, "WANPPPConnection": {}}
            elif name == "addObject" and self.conn_ok:
                self.wcds()["2"]["WANIPConnection"]["1"] = {"Name": v("4_INTERNET_B_VID_0"), "Enable": v(False)}
            elif name == "setParameterValues":
                for path, value, _ in t["parameterValues"]:
                    _set(self.device, path, value)
        self.queue = []
        return 200

    async def get_tasks(self, device_id):
        return [{"_id": "t1", "timestamp": "2999-01-01T00:00:00Z"}]

    async def get_faults(self, device_id):
        return []

    async def delete_task(self, task_id):
        self.deleted_tasks.append(task_id)

    async def delete_fault(self, fault_id):
        pass


@pytest.fixture
def fast(monkeypatch):
    async def no_sleep(_):
        return None
    monkeypatch.setattr(xc.asyncio, "sleep", no_sleep)


@pytest.mark.parametrize("mode", ["DHCP", "STATIC"])
async def test_crear_wan_x_catv(fast, mode):
    onu = FakeONU()
    data = {"vlan": 999, "priority": 0, "mtu": 1500, "nat": True, "bindings": [WLAN4],
            "ip": "192.0.2.10", "subnet_mask": "255.255.255.0", "gateway": "192.0.2.1", "dns": "8.8.8.8"}
    result = await xc.create_x_catv_wan(onu, ID, data, mode=mode)

    # Reconoce el WCD nuevo aunque tenga el numero del fantasma.
    assert (result["wcd"], result["instance"]) == (2, 1)
    # 3 sesiones; la connection request solo en la ultima tarea de cada una.
    assert onu.sessions == [
        ["addObject", "refreshObject"],
        ["setParameterValues", "addObject", "refreshObject"],
        ["setParameterValues", "setParameterValues", "refreshObject"],
    ]

    w2 = onu.wcds()["2"]
    assert w2["X_CATV_WANGponLinkConfig"]["VLANIDMark"]["_value"] == 999
    assert w2["X_CATV_WANGponLinkConfig"]["Mode"]["_value"] == 2
    conn = w2["WANIPConnection"]["1"]
    assert conn["Enable"]["_value"] is True
    assert conn["X_CATV_ServiceList"]["_value"] == "INTERNET"
    assert conn["X_CATV_LanInterface"]["_value"] == WLAN4
    assert not [k for k in conn if "X_CT-COM" in k]
    assert conn["AddressingType"]["_value"] == ("Static" if mode == "STATIC" else "DHCP")
    if mode == "STATIC":
        assert conn["ExternalIPAddress"]["_value"] == "192.0.2.10"

    # La WAN de internet existente no se toco.
    assert onu.wcds()["1"] == km1303()["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]["1"]


async def test_si_falla_limpia_las_tareas(fast):
    onu = FakeONU(conn_ok=False)
    with pytest.raises(RuntimeError, match="WANIPConnection"):
        await xc.create_x_catv_wan(onu, ID, {"vlan": 999}, mode="DHCP")
    assert onu.deleted_tasks == ["t1"]


async def test_ip_fija_incompleta_no_toca_la_onu(fast):
    onu = FakeONU()
    with pytest.raises(ValueError):
        await xc.create_x_catv_wan(onu, ID, {"vlan": 999, "ip": "192.0.2.10"}, mode="STATIC")
    assert onu.sessions == []


async def test_pppoe_bloqueado():
    with pytest.raises(RuntimeError, match="PPPoE"):
        await xc.create_x_catv_wan(FakeONU(), ID, {"vlan": 999}, mode="PPPOE")


async def test_limpia_solo_fallos_del_wcd_borrado():
    deleted = []

    class C:
        async def get_faults(self, device_id):
            return [
                {"_id": "a", "timestamp": "2026-11-07T16:28:18Z", "message": f"{WCD}.2.WANIPConnection.1.ExternalIPAddress"},
                {"_id": "b", "timestamp": "2026-11-07T16:28:18Z", "message": f"{WCD}.1.WANIPConnection.1.ExternalIPAddress"},
                {"_id": "c", "timestamp": "2026-11-07T10:00:00Z", "message": f"{WCD}.2.Algo"},
            ]

        async def delete_fault(self, fault_id):
            deleted.append(fault_id)

    await xc.clean_ghost_faults(C(), ID, f"{WCD}.2", "2026-11-07T16:27:00")
    assert deleted == ["a"]


# --- Endpoints -----------------------------------------------------------------

@pytest.fixture
def km(monkeypatch):
    async def fake_get_device(device_id):
        return km1303()
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)


async def test_no_borra_wan_tr069_oculta(client, km):
    await login(client, "tecnico")
    r = await client.delete(f"/api/devices/{ID}/wan/0/WANIPConnection/1")
    assert r.status_code in (403, 404)


async def test_lectura_indica_modelo_no_certificado(client, km):
    await login(client, "tecnico")
    r = await client.get(f"/api/devices/{ID}/wan")
    assert r.status_code == 200
    cert = r.json()["certification"]
    assert cert["certified"] is False and "no certificado" in cert["message"]
    assert len(r.json()["wan"]) == 2


@pytest.mark.parametrize("method,path,body", [
    ("post", "wan/create-dhcp", {"vlan": 999}),
    ("post", "wan/create-ip", {"vlan": 999, "addressing_type": "STATIC"}),
    ("post", "wan/create-pppoe", {"vlan": 996, "username": "u", "password": "p"}),
    ("patch", "wan/1/ip/1", {"vlan": 151}),
    ("post", "wan/1/ip/1/disable", None),
    ("delete", "wan/1/WANIPConnection/1", None),
    ("patch", "wifi/1", {"ssid": "x"}),
    ("post", "catv/off", None),
])
async def test_escrituras_bloqueadas(client, km, monkeypatch, method, path, body):
    sent = []

    async def capture(*a, **k):
        sent.append(a)
        return {"http_status": 200}

    for name in ("set_parameter_values", "add_object", "delete_object", "post_task"):
        monkeypatch.setattr(genieacs, name, capture)

    await login(client, "jefe")
    kwargs = {"json": body} if body is not None else {}
    r = await getattr(client, method)(f"/api/devices/{ID}/{path}", **kwargs)
    assert r.status_code == 403, r.text
    assert "no certificado" in r.json()["detail"]
    assert sent == []


def test_otras_marcas_siguen_certificadas():
    from app.services.wan_driver import certification
    from test_realtek import igd

    assert certification(igd())["certified"] is True
