"""ZTE F6600P: acceso remoto por WAN con reglas IPV4ServiceControl."""

import pytest

from app.services import zte_service_control as zsc
from app.services.security_module import security_state, service_changes

TS = "2026-11-19T17:00:00.000Z"


def v(value, t="xsd:string"):
    return {"_value": value, "_type": t, "_writable": True, "_timestamp": TS, "_object": False}


def rule(services, enabled=True, start="0.0.0.0", end="0.0.0.0", name="FWSC1"):
    return {"_object": True, "Enable": v(enabled, "xsd:boolean"), "ServiceType": v(services),
            "Ingress": v("WAN_ALL"), "Mode": v("Accept"), "IPStart": v(start), "IPEnd": v(end), "Name": v(name)}


def port(name, number):
    return {"_object": True, "Name": {**v(name), "_writable": False}, "Port": v(number, "xsd:int")}


def device(table):
    return {"_id": "18B0A4-F6600P-PRUEBA", "InternetGatewayDevice": {
        "Firewall": {
            "Enable": v(True, "xsd:boolean"), "Config": v("Middle"),
            "X_ZTE-COM_ALG": {"FTPEnable": v(True, "xsd:boolean")},
            "X_ZTE-COM_ServiceControl": {
                "IPV4ServiceControl": {"_object": True, "_writable": True, "_timestamp": TS, **table},
                "IPV4RemoteServicePortControl": {"1": port("HTTP", 80), "2": port("FTP", 21),
                                                 "4": port("TELNET", 23), "5": port("HTTPS", 443)},
            },
        },
        "X_ZTE-COM_Telnet": {"Enable": v(False, "xsd:boolean")},
        "X_ZTE-COM_FTP": {"Enable": v(True, "xsd:boolean")},
    }}


class Fake:
    def __init__(self, table):
        self.t = {int(k): {f: x["_value"] for f, x in r.items() if not f.startswith("_")} for k, r in table.items()}
        self.faults = []

    def dev(self):
        return device({str(k): rule(r["ServiceType"], r["Enable"], r["IPStart"], r["IPEnd"], r["Name"])
                       for k, r in self.t.items()})

    async def get_device(self, _id):
        return self.dev()

    async def post_task(self, _id, task, connection_request=False, wait_ms=0):
        if task["name"] == "addObject":
            n = max(self.t, default=0) + 1
            self.t[n] = {"Enable": False, "ServiceType": "", "Ingress": "WAN_ALL", "Mode": "Accept",
                         "IPStart": "0.0.0.0", "IPEnd": "0.0.0.0", "Name": f"FWSC{n}"}
        elif task["name"] == "deleteObject":
            self.t.pop(int(task["objectName"].rsplit(".", 1)[1]))
        return 200

    async def set_parameter_values(self, _id, values, wait_ms=None):
        for path, val, _ in values:
            if "SSH" in str(val):
                self.faults.append({"_id": "x:task_t1", "code": "cwmp.9003", "detail": {"faultString": "Invalid arguments"}})
                return {"task_id": "t1"}
        for path, val, _ in values:
            n, field = path.split(".")[-2:]
            self.t[int(n)][field] = val
        return {"task_id": "t0"}

    async def get_faults(self, _id):
        return self.faults

    async def delete_fault(self, _):
        self.faults = []

    async def delete_task(self, _):
        pass


def svc(state, sid):
    return next(s for s in state["services"] if s["id"] == sid)


def test_lectura_regla_compartida():
    st = security_state(device({"1": rule("HTTP,HTTPS,PING")}))
    assert st["supported"] and st["wan_activation_allowed"] is True
    assert svc(st, "http")["wan_enabled"] and svc(st, "https")["wan_enabled"] and svc(st, "icmp")["wan_enabled"]
    assert not svc(st, "telnet")["wan_enabled"] and svc(st, "telnet")["wan_writable"]
    assert svc(st, "http")["wan_port"] == 80 and svc(st, "http")["specific_ip"] == ""
    assert not any(s["id"] in ("ssh", "tftp") for s in st["services"])
    # Telnet/FTP por LAN siguen como antes.
    assert svc(st, "ftp")["lan_enabled"] is True


def test_tabla_vacia_todo_cerrado():
    st = security_state(device({}))
    assert not any(s["wan_enabled"] for s in st["services"])


def test_regla_apagada_o_de_rechazo_no_abre():
    st = security_state(device({"1": rule("HTTP", enabled=False)}))
    assert not svc(st, "http")["wan_enabled"]


def test_ip_especifica():
    st = security_state(device({"1": rule("TELNET", start="203.0.113.5", end="203.0.113.5")}))
    assert svc(st, "telnet")["wan_enabled"] and svc(st, "telnet")["specific_ip"] == "203.0.113.5"


def test_activar_con_firewall_middle_esta_permitido():
    values, req = service_changes(device({}), "telnet", {"wan_enabled": True})
    assert values == [["zte-sc:TELNET:enable", True, "xsd:boolean"]]


def test_puerto_con_el_tipo_de_la_onu():
    values, _ = service_changes(device({}), "http", {"wan_port": 8080})
    assert values == [["InternetGatewayDevice.Firewall.X_ZTE-COM_ServiceControl.IPV4RemoteServicePortControl.1.Port", 8080, "xsd:int"]]


def test_ip_invalida():
    with pytest.raises(ValueError):
        service_changes(device({}), "http", {"specific_ip": "300.1.1.1"})


async def test_activar_crea_regla_propia():
    f = Fake({})
    await zsc.apply(f, "id", f.dev(), [["zte-sc:TELNET:enable", True, "xsd:boolean"], ["zte-sc:TELNET:ip", "203.0.113.5", "xsd:string"]])
    assert f.t[1]["Name"] == "ACS_TELNET" and f.t[1]["ServiceType"] == "TELNET" and f.t[1]["Enable"] is True
    assert f.t[1]["IPStart"] == f.t[1]["IPEnd"] == "203.0.113.5"
    assert svc(security_state(f.dev()), "telnet")["wan_enabled"]


async def test_apagar_uno_de_una_regla_compartida():
    f = Fake({"1": rule("HTTP,HTTPS,PING")})
    await zsc.apply(f, "id", f.dev(), [["zte-sc:HTTP:enable", False, "xsd:boolean"]])
    assert f.t[1]["ServiceType"] == "HTTPS,PING" and f.t[1]["Enable"] is True
    st = security_state(f.dev())
    assert not svc(st, "http")["wan_enabled"] and svc(st, "https")["wan_enabled"]


async def test_ip_para_un_servicio_de_regla_compartida_lo_separa():
    f = Fake({"1": rule("HTTP,HTTPS,PING")})
    await zsc.apply(f, "id", f.dev(), [["zte-sc:HTTPS:ip", "198.51.100.7", "xsd:string"]])
    assert f.t[1]["ServiceType"] == "HTTP,PING"
    assert f.t[2]["Name"] == "ACS_HTTPS" and f.t[2]["IPStart"] == "198.51.100.7"
    st = security_state(f.dev())
    assert svc(st, "https")["specific_ip"] == "198.51.100.7" and svc(st, "http")["specific_ip"] == ""


async def test_apagar_el_ultimo_de_una_regla_la_desactiva():
    f = Fake({"1": rule("PING")})
    await zsc.apply(f, "id", f.dev(), [["zte-sc:PING:enable", False, "xsd:boolean"]])
    assert f.t[1]["Enable"] is False


async def test_reactivar_reusa_su_regla():
    f = Fake({"3": rule("HTTP", enabled=False, name="ACS_HTTP")})
    await zsc.apply(f, "id", f.dev(), [["zte-sc:HTTP:enable", True, "xsd:boolean"]])
    assert list(f.t) == [3] and f.t[3]["Enable"] is True
