"""Familia XPON (VSOL): XPON+2GE+2WiFi, XPON+2GE+2WiFi+USB+CATV,
XPON+2GE+2WIFI+USB+CATV y XPON+4GE+2WiFi+USB+CATV.

Hallazgos sobre el parque real (99 ONUs, 8 firmwares):
- 230825 corta la sesion con LANDevice (y aun con LANDevice.1.Hosts sola).
- 802.1p "sin marcar" llega como 4294967295.
- DeviceInfo.Catv.Enable es booleano en 240807 y texto ("" hasta que se
  escribe) en 250107/250210/250214/250415/230825.
"""

import pytest

from app.core import redis_client
from app.services import device_refresh as dr
from app.services.catv_reader import read_catv, resolve_catv_profile
from app.services.wan_reader import read_wan

WCD = "InternetGatewayDevice.WANDevice.1.WANConnectionDevice"


def v(value, t=None, writable=True):
    out = {"_value": value, "_object": False, "_writable": writable}
    if t:
        out["_type"] = t
    return out


def xpon(prio=4294967295, catv=("", "xsd:string")):
    return {
        "_id": "74546B-XPON%2B2GE%2B2WIFI%2BUSB%2BCATV-PRUEBA",
        "InternetGatewayDevice": {
            "DeviceInfo": {"Catv": {"Enable": v(catv[0], catv[1]), "Support": v(True, "xsd:boolean", False)}},
            "WANDevice": {"1": {"WANConnectionDevice": {"2": {
                "X_CT-COM_WANGponLinkConfig": {"VLANIDMark": v(150), "802-1pMark": v(prio)},
                "WANIPConnection": {"1": {
                    "Name": v("1_INTERNET_R_VID_150"), "Enable": v(True), "AddressingType": v("Static"),
                    "ExternalIPAddress": v("192.0.2.146"), "ConnectionStatus": v("Connected"),
                    "X_CT-COM_VLANIDMark": v(150), "X_CT-COM_802-1pMark": v(prio),
                    "X_CT-COM_ServiceList": v("INTERNET"),
                }},
            }}}},
        },
    }


@pytest.mark.parametrize("raw,shown", [(4294967295, None), (-1, None), (8, None), (0, 0), (7, 7)])
def test_prioridad_sin_marcar_no_se_muestra(raw, shown):
    assert read_wan(xpon(prio=raw))[0]["priority_8021p"] == shown


def test_catv_texto_vacio_es_desconocido_y_se_escribe_como_texto():
    p = resolve_catv_profile(xpon())
    assert read_catv(xpon())["enabled"] is None
    assert (p["value_type"], p["on_value"], p["off_value"]) == ("xsd:string", "1", "0")


def test_catv_booleano_se_escribe_como_booleano():
    d = xpon(catv=(True, "xsd:boolean"))
    p = resolve_catv_profile(d)
    assert read_catv(d)["enabled"] is True
    assert (p["value_type"], p["on_value"], p["off_value"]) == ("xsd:boolean", True, False)


def test_lectura_incluye_ramas_nuevas():
    for name in ("Layer3Forwarding", "Layer2Bridging", "X_RZ_Catv", "Firewall", "X_CMCC_Security"):
        assert name in dr.BRANCHES["InternetGatewayDevice"]
    assert "DeviceConfig" not in dr.BRANCHES["InternetGatewayDevice"]


class FakeGenie:
    def __init__(self, tasks=(), faults=()):
        self.tasks = list(tasks)
        self.faults = list(faults)
        self.posted = []

    async def get_tasks(self, device_id):
        return self.tasks

    async def get_faults(self, device_id):
        return self.faults

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        self.posted.append((task["objectName"], connection_request))
        return 202

    async def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["_id"] != task_id]

    async def delete_fault(self, fault_id):
        self.faults = [f for f in self.faults if f["_id"] != fault_id]


def lan_unknown():
    """LANDevice con estructura conocida y sin valores (230825 recien leida)."""
    leaf = {"_object": False}
    return {
        "_id": "X",
        "InternetGatewayDevice": {
            "_timestamp": "2026-11-11T00:00:00Z",
            "LANDevice": {"_object": True, "_timestamp": "2026-11-11T00:00:00Z", "1": {
                "_object": True,
                "Hosts": {"_object": True, "HostNumberOfEntries": leaf},
                "WLANConfiguration": {"_object": True, "1": {"_object": True, "SSID": leaf}},
            }},
            "Layer3Forwarding": {"_object": True, "_timestamp": "2026-11-11T00:00:00Z", "DefaultConnectionService": leaf},
        },
    }


@pytest.fixture
def redis(monkeypatch):
    import fakeredis
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_client", r)
    return r


async def test_tarea_pendiente_no_bloquea_las_demas_ramas(redis, monkeypatch):
    g = FakeGenie(tasks=[{"_id": "t1", "name": "refreshObject", "objectName": "InternetGatewayDevice.Layer3Forwarding"}])
    monkeypatch.setattr(dr, "genieacs", g)
    await redis.set(dr.LIGHT_KEY.format("X"), "1")
    r = await dr.request_refresh("X", lan_unknown())
    assert [b for b, _ in g.posted] == [
        "InternetGatewayDevice.LANDevice.1.Hosts",
        "InternetGatewayDevice.LANDevice.1.WLANConfiguration",
    ]
    assert "InternetGatewayDevice.Layer3Forwarding" not in [b for b, _ in g.posted]
    assert g.posted[-1][1] is True and r["status"] == "queued"


async def test_parte_que_corta_la_sesion_se_omite(redis, monkeypatch):
    g = FakeGenie(
        tasks=[{"_id": "t9", "name": "refreshObject", "objectName": "InternetGatewayDevice.LANDevice.1.Hosts"}],
        faults=[{"_id": "f9", "channel": "task_t9", "code": "session_terminated", "message": ""}],
    )
    monkeypatch.setattr(dr, "genieacs", g)
    await redis.set(dr.LIGHT_KEY.format("X"), "1")

    st = await dr.refresh_status("X")
    assert st["failed"][0]["branch"].endswith("Hosts") and g.tasks == [] and g.faults == []

    await dr.request_refresh("X", lan_unknown())
    posted = [b for b, _ in g.posted]
    assert "InternetGatewayDevice.LANDevice.1.Hosts" not in posted
    assert "InternetGatewayDevice.LANDevice.1.WLANConfiguration" in posted


async def test_primer_corte_solo_activa_modo_liviano(redis, monkeypatch):
    g = FakeGenie(
        tasks=[{"_id": "t1", "name": "refreshObject", "objectName": "InternetGatewayDevice.LANDevice"}],
        faults=[{"_id": "f1", "channel": "task_t1", "code": "session_terminated", "message": ""}],
    )
    monkeypatch.setattr(dr, "genieacs", g)
    await dr.refresh_status("X")
    assert await redis.exists(dr.LIGHT_KEY.format("X"))
    assert not await redis.exists(dr.SKIP_KEY.format("X"))


async def test_firmware_230825_lee_por_partes_desde_el_inicio(redis, monkeypatch):
    g = FakeGenie()
    monkeypatch.setattr(dr, "genieacs", g)
    d = lan_unknown()
    d["InternetGatewayDevice"]["DeviceInfo"] = {"SoftwareVersion": {"_value": "V2.1.00-230825", "_object": False}}
    await dr.request_refresh("X", d)
    posted = [b for b, _ in g.posted]
    assert "InternetGatewayDevice.LANDevice" not in posted
    assert "InternetGatewayDevice.LANDevice.1.Hosts" not in posted
    assert "InternetGatewayDevice.LANDevice.1.WLANConfiguration" in posted
