"""ZTE F6600P: puertos LAN/SSID de una WAN en X_ZTE-COM_PortBinding."""

from app.services import zte_port_binding as zpb
from app.services.wan_reader import read_wan

TS = "2026-11-19T16:30:00.000Z"
CONN = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.2"
OTRA = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1"
LAN = "InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig."
WLAN = "InternetGatewayDevice.LANDevice.1.WLANConfiguration."


def v(value, t="xsd:string"):
    return {"_value": value, "_type": t, "_writable": True, "_timestamp": TS, "_object": False}


def entry(wan, lan):
    return {"_object": True, "WANInterface": v(wan), "LANInterface": v(lan)}


def device(table):
    ip = {"_object": True, "_timestamp": TS, "2": {
        "_object": True, "_timestamp": TS,
        "Name": v("ACS_INTERNET_DHCP_R_VID_999"), "AddressingType": v("DHCP"),
        "ConnectionType": v("IP_Routed"), "ConnectionStatus": v("Connecting"),
        "Enable": v(True, "xsd:boolean"), "X_ZTE-COM_ServiceList": v("INTERNET"),
        "X_ZTE-COM_VLANEnable": v(True, "xsd:boolean"), "X_ZTE-COM_VLANID": v(999, "xsd:unsignedInt"),
    }}
    return {"_id": "18B0A4-F6600P-PRUEBA", "InternetGatewayDevice": {
        "WANDevice": {"1": {"WANConnectionDevice": {"1": {"WANIPConnection": ip}}}},
        "X_ZTE-COM_PortBinding": {"_object": True, "_writable": True, "_timestamp": TS, **table},
    }}


class Fake:
    """Simula la ONU: aplica tareas sobre la tabla y responde faults."""

    def __init__(self, table, reject=None):
        self.table = {int(k): [x["WANInterface"]["_value"], x["LANInterface"]["_value"]] for k, x in table.items()}
        self.reject = reject
        self.ops = []
        self.faults = []

    def dev(self):
        return device({str(k): entry(w, l) for k, (w, l) in self.table.items()})

    async def get_device(self, _id):
        return self.dev()

    async def post_task(self, _id, task, connection_request=False, wait_ms=0):
        name = task["name"]
        if name == "addObject":
            n = max(self.table, default=0) + 1
            self.table[n] = ["", ""]
            self.ops.append(("add", n))
        elif name == "deleteObject":
            n = int(task["objectName"].rsplit(".", 1)[1])
            self.table.pop(n)
            self.ops.append(("del", n))
        return 200

    async def set_parameter_values(self, _id, values, wait_ms=None):
        if self.reject and any(self.reject in str(val) for _, val, _ in values):
            self.faults.append({"_id": "x:task_t1", "code": "cwmp.9003", "detail": {"faultString": "Invalid arguments"}})
            return {"task_id": "t1"}
        for path, val, _ in values:
            n, field = path.split(".")[-2:]
            self.table[int(n)][0 if field == "WANInterface" else 1] = val
        self.ops.append(("set", tuple(p.split("PortBinding.")[1] for p, _, _ in values)))
        return {"task_id": "t0"}

    async def get_faults(self, _id):
        return self.faults

    async def delete_fault(self, fid):
        self.faults = []

    async def delete_task(self, tid):
        pass


def test_lectura_por_wan():
    d = device({"1": entry(CONN, f"{LAN}4,{WLAN}5")})
    w = [x for x in read_wan(d) if x["instance"] == 2][0]
    assert w["lan_binding"] == f"{LAN}4,{WLAN}5"


async def test_crea_entrada_nueva():
    f = Fake({})
    await zpb.apply(f, "id", CONN + ".", f"{LAN}4,{WLAN}5")
    assert f.table == {1: [CONN, f"{LAN}4,{WLAN}5"]}


async def test_actualiza_la_suya_y_quita_el_puerto_de_otra_wan():
    f = Fake({"1": entry(OTRA, f"{LAN}1,{LAN}2"), "2": entry(CONN, f"{LAN}4")})
    await zpb.apply(f, "id", CONN, f"{LAN}2,{LAN}4")
    assert f.table == {1: [OTRA, f"{LAN}1"], 2: [CONN, f"{LAN}2,{LAN}4"]}


async def test_otra_wan_sin_puertos_se_borra():
    f = Fake({"1": entry(OTRA, f"{LAN}1"), "2": entry(CONN, f"{LAN}4")})
    await zpb.apply(f, "id", CONN, f"{LAN}1")
    assert f.table == {2: [CONN, f"{LAN}1"]}


async def test_sin_puertos_borra_la_entrada():
    f = Fake({"1": entry(CONN, f"{LAN}4")})
    await zpb.apply(f, "id", CONN, "")
    assert f.table == {}


async def test_rechazo_no_deja_entrada_vacia():
    f = Fake({}, reject=f"{LAN}9")
    try:
        await zpb.apply(f, "id", CONN, f"{LAN}9")
        assert False
    except zpb.PortBindingError as exc:
        assert "cwmp.9003" in str(exc)
    assert f.table == {}


async def test_borrar_wan_quita_su_entrada():
    f = Fake({"1": entry(OTRA, f"{LAN}1"), "2": entry(CONN, f"{LAN}4")})
    await zpb.remove_for(f, "id", f.dev(), CONN)
    assert f.table == {1: [OTRA, f"{LAN}1"]}


def test_traduccion_ya_no_rechaza_puertos():
    from app.services.vendor_wan import translate
    out = translate([[OTRA + ".X_CT-COM_LanInterface", f"{LAN}1", "xsd:string"]], "zte")
    assert out == []


def test_etiqueta_de_banda_con_wifi6():
    from app.services.wan_reader import friendly_bindings
    d = {"InternetGatewayDevice": {"LANDevice": {"1": {"WLANConfiguration": {
        "1": {"SSID": v("Red24"), "Standard": v("b,g,n,ax")},
        "5": {"SSID": v("Red5"), "Standard": v("a,n,ac,ax")},
    }}}}}
    labels = [b["label"] for b in friendly_bindings(d, f"{WLAN}1,{WLAN}5")]
    assert labels == ["2.4 GHz · Red24", "5 GHz · Red5"]
