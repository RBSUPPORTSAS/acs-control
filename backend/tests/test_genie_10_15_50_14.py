"""Modelos del GenieACS 10.15.50.14: VSOL V2804AX30-H (fw V1.1.00) y
ZTE F6600P (fw V9.0.10P6N44).

- V2804AX30-H: PPPoE con TransportType "L2TP" y sin DefaultGateway;
  DeviceInfo completa da too_many_commits (se lee por partes); una ONU
  nueva llega sin la lista de ramas raiz; FireWallGrade vacio.
- F6600P: VLAN/802.1p/servicios en X_ZTE-COM_*; todas las WAN en el WCD 1
  (addObject de WCD da cwmp.9002); Telnet/FTP propios; nivel de firewall
  en solo lectura. Validado en ZTEGDCEF5AB1 (2026-11-11).
"""

import pytest

from app.core import redis_client
from app.services import device_refresh as dr
from app.services.security_module import security_state
from app.services.wan_driver import certification, detect_wan_driver
from app.services.wan_reader import read_wan

TS = "2026-11-11T22:00:00.000Z"


def v(value, t="xsd:string", writable=True):
    return {"_value": value, "_object": False, "_writable": writable, "_type": t, "_timestamp": TS}


def obj(children, walked=True):
    node = {"_object": True, "_writable": False, **children}
    if walked:
        node["_timestamp"] = TS
    return node


def wan_tree(wcds):
    return obj({"1": obj({"WANConnectionDevice": obj(wcds)})})


def vsol():
    ppp = obj({"1": obj({
        "Name": v("1_TR069_INTERNET_R_VID_70"),
        "ConnectionType": v("PPPoE_Routed"),
        "TransportType": v("L2TP"),
        "ConnectionStatus": v("Connected"),
        "Enable": v(True, "xsd:boolean"),
        "ExternalIPAddress": v("198.51.100.74"),
        "RemoteIPAddress": v("198.51.100.1"),
        "Username": v("cliente"),
        "X_CT-COM_ServiceList": v("INTERNET,TR069"),
        "X_CT-COM_VLANIDMark": v(70, "xsd:unsignedInt"),
        "X_CT-COM_802-1pMark": v(0, "xsd:unsignedInt"),
    })})
    link = obj({"VLANIDMark": v(70, "xsd:unsignedInt"), "802-1pMark": v(0, "xsd:unsignedInt"), "Mode": v(2)})
    acl = obj({
        "FireWallGrade": v("", "xsd:unsignedInt"),
        "HTTPWanEnable": v(True, "xsd:boolean"),
        "HTTPLanEnable": v(True, "xsd:boolean"),
        "TELNETWanEnable": v(False, "xsd:boolean"),
        "TELNETLanEnable": v(False, "xsd:boolean"),
    })
    return {"_id": "80F1A8-V2804AX30%2DH-PRUEBA", "InternetGatewayDevice": obj({
        "DeviceInfo": obj({"ManufacturerOUI": v("80F1A8")}),
        "WANDevice": wan_tree({"1": obj({"WANPPPConnection": ppp, "X_CT-COM_WANGponLinkConfig": link})}),
        "X_HW_Security": obj({"AclServices": acl}),
    })}


def zte():
    ip = obj({"1": obj({
        "Name": v("omci_ipv4_dhcp_2"),
        "AddressingType": v("DHCP"),
        "ConnectionType": v("IP_Routed"),
        "ConnectionStatus": v("Connected"),
        "Enable": v(True, "xsd:boolean"),
        "ExternalIPAddress": v("192.0.2.38"),
        "DefaultGateway": v("192.0.2.1"),
        "X_ZTE-COM_ServiceList": v("TR069_VoIP"),
        "X_ZTE-COM_VLANEnable": v(True, "xsd:boolean"),
        "X_ZTE-COM_VLANID": v(46, "xsd:unsignedInt"),
        "X_ZTE-COM_8021P": v(2, "xsd:unsignedInt"),
    })})
    ppp = obj({"1": obj({
        "Name": v("1"),
        "ConnectionType": v("IP_Routed"),
        "TransportType": v("PPPoE"),
        "ConnectionStatus": v("Connected"),
        "Enable": v(True, "xsd:boolean"),
        "ExternalIPAddress": v("198.51.100.79"),
        "DefaultGateway": v("198.51.100.1"),
        "X_ZTE-COM_ServiceList": v("INTERNET"),
        "X_ZTE-COM_VLANEnable": v(True, "xsd:boolean"),
        "X_ZTE-COM_VLANID": v(70, "xsd:unsignedInt"),
        "X_ZTE-COM_8021P": v(0, "xsd:unsignedInt"),
    })})
    return {"_id": "18B0A4-F6600P-PRUEBA", "InternetGatewayDevice": obj({
        "WANDevice": wan_tree({"1": obj({"WANIPConnection": ip, "WANPPPConnection": ppp})}),
        "Firewall": obj({
            "Enable": v(True, "xsd:boolean"),
            "Config": v("Middle"),
            "X_ZTE-COM_ALG": obj({"FTPEnable": v(True, "xsd:boolean")}),
            "X_ZTE-COM_DoS": obj({"Anti-PortScan": obj({"Enable": v(True, "xsd:boolean")})}),
        }),
        "X_ZTE-COM_Telnet": obj({"Enable": v(False, "xsd:boolean"), "Port": v(23), "UserName": v("root")}),
        "X_ZTE-COM_FTP": obj({"Enable": v(True, "xsd:boolean"), "UserName": v("admin")}),
    })}


def test_vsol_pppoe_con_transport_l2tp_y_gateway_remoto():
    d = vsol()
    assert detect_wan_driver(d) == "x_ctcom_wan"
    w = read_wan(d)[0]
    assert w["type"] == "PPPoE" and w["vlan"] == 70 and w["gateway"] == "198.51.100.1"
    assert w["protected"] is True


def test_vsol_firewall_vacio_no_reportado():
    s = security_state(vsol())
    assert s["firewall_label"] == "No reportado"
    http = next(x for x in s["services"] if x["id"] == "http")
    assert http["wan_enabled"] is True


def test_zte_wan():
    d = zte()
    assert detect_wan_driver(d) == "zte"
    wans = {w["object_type"]: w for w in read_wan(d)}
    tr = wans["WANIPConnection"]
    assert tr["vlan"] == 46 and tr["priority_8021p"] == 2
    assert tr["services"] == ["TR069", "VOIP"] and tr["protected"] is True
    inet = wans["WANPPPConnection"]
    assert inet["type"] == "PPPoE" and inet["vlan"] == 70 and inet["services"] == ["INTERNET"]


def test_zte_certificado_y_seguridad():
    d = zte()
    assert certification(d)["certified"] is True
    s = security_state(d)
    assert s["firewall_kind"] == "zte" and s["firewall_label"] == "Medio"
    assert s["firewall_writable"] is False
    svc = {x["id"]: x for x in s["services"]}
    assert svc["telnet"]["lan_enabled"] is False and svc["ftp"]["lan_enabled"] is True
    assert svc["telnet"]["lan_writable"] is True
    text = str(s)
    assert "root" not in text and "admin" not in text


def test_zte_servicio_telnet_escribe_su_rama():
    from app.services.security_module import service_changes
    values, requested = service_changes(zte(), "telnet", {"lan_enabled": True})
    assert values == [["InternetGatewayDevice.X_ZTE-COM_Telnet.Enable", True, "xsd:boolean"]]


def test_zte_traduccion_wan():
    from app.services.vendor_wan import translate
    from app.services.x_ctcom_wan_builder import build_dhcp_values
    vals = translate(build_dhcp_values(1, 2, {"vlan": 999, "priority": 3})["parameter_values"], "zte")
    by = {p.rsplit(".", 1)[1]: v for p, v, _ in vals}
    assert by["X_ZTE-COM_VLANID"] == 999 and by["X_ZTE-COM_VLANEnable"] is True
    assert by["X_ZTE-COM_8021P"] == 3 and by["X_ZTE-COM_ServiceList"] == "INTERNET"
    assert not any("X_CT-COM" in p for p, _, _ in vals)
    with pytest.raises(ValueError):
        translate(build_dhcp_values(1, 2, {"vlan": 999, "bindings": [
            "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.1"]})["parameter_values"], "zte")


def test_rama_leida_por_partes_esta_completa():
    # DeviceInfo sin _timestamp en la raiz (la lectura completa fallo) pero
    # con todos sus sub-objetos recorridos.
    node = {"_object": True, "UpTime": v(5), "MemoryStatus": obj({"Total": v(1)})}
    assert dr.branch_state(node)["structure"] is True
    assert "DeviceInfo" in dr.SPLITTABLE


class FakeGenie:
    def __init__(self, after=None):
        self.posted = []
        self.after = after

    async def get_tasks(self, device_id):
        return []

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.posted.append(task)
        return 200

    async def get_device(self, device_id):
        return self.after


@pytest.fixture
def redis(monkeypatch):
    import fakeredis
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_client", r)
    return r


async def test_onu_sin_ramas_raiz_conocidas_las_descubre(redis, monkeypatch):
    before = {"_id": "X", "InternetGatewayDevice": {
        "DeviceInfo": obj({"UpTime": v(1)}),
    }}
    after = {"_id": "X", "InternetGatewayDevice": obj({
        "DeviceInfo": obj({"UpTime": v(1)}),
        "Layer3Forwarding": {"_object": True},
    })}
    g = FakeGenie(after=after)
    monkeypatch.setattr(dr, "genieacs", g)
    await dr.request_refresh("X", before)
    assert g.posted[0] == {
        "name": "getParameterValues",
        "parameterNames": ["InternetGatewayDevice.Layer3Forwarding.DefaultConnectionService"],
    }
    assert {"name": "refreshObject", "objectName": "InternetGatewayDevice.Layer3Forwarding"} in g.posted


class FakeDeleteGenie:
    """Primer deleteObject da cwmp.9002 (VSOL justo despues de editar)."""

    def __init__(self):
        self.deletes = 0
        self.faults = []
        self.tasks = []

    async def delete_object(self, device_id, name):
        self.deletes += 1
        if self.deletes == 1:
            self.tasks = [{"_id": "t1", "name": "deleteObject", "objectName": name}]
            self.faults = [{"_id": "f1", "code": "cwmp.9002",
                            "provisions": f'[["instances","{name}",0]]'}]
        return 200

    async def get_faults(self, device_id):
        return self.faults

    async def delete_fault(self, fault_id):
        self.faults = [f for f in self.faults if f["_id"] != fault_id]

    async def get_tasks(self, device_id):
        return self.tasks

    async def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["_id"] != task_id]


async def test_borrar_reintenta_tras_9002(monkeypatch):
    import asyncio
    from app.api.routers import wan

    g = FakeDeleteGenie()
    monkeypatch.setattr(wan, "genieacs", g)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    await wan._delete_retrying("X", "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.2")
    assert g.deletes == 2 and g.faults == [] and g.tasks == []


async def test_vsol_crea_la_wan_encendida(monkeypatch):
    from app.services import vsol_wan_creator as vc

    writes = []

    class G:
        def __init__(self):
            self.wcds = {"1"}
            self.conns = set()

        async def get_device(self, device_id):
            wcd = {k: {"WANPPPConnection": {i: {} for i in self.conns}} for k in self.wcds}
            return {"InternetGatewayDevice": {"WANDevice": {"1": {"WANConnectionDevice": wcd}}}}

        async def add_object(self, device_id, name):
            if name.endswith("WANConnectionDevice"):
                self.wcds.add("2")
            else:
                self.conns.add("1")

        async def set_parameter_values(self, device_id, values):
            writes.extend(values)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(vc.asyncio, "sleep", no_sleep)
    await vc.create_vsol_pppoe(G(), "X", {"vlan": 999, "priority": 0, "username": "u", "password": "p"}, {})
    enable = [v for p, v, _ in writes if p.endswith("WANPPPConnection.1.Enable")]
    assert enable[-1] is True
