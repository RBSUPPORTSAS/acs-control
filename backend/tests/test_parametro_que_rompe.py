"""Un parametro que la ONU no puede leer (cwmp.9002) no tumba toda la rama.

VSOL V2802ACT fw V2.1.00-260205: getParameterValues de
WLANConfiguration.{1-4}.PossibleChannels (redes de 5 GHz) da cwmp.9002 y con
el cae la lectura de LANDevice / WLANConfiguration completa.
"""

import pytest

from app.core import redis_client
from app.services import device_refresh as dr
from app.services.device_normalizer import get_parameter
from app.services.genieacs import genieacs

TS = "2026-11-21T13:00:00.000Z"
W = "InternetGatewayDevice.LANDevice.1.WLANConfiguration"


def leaf(value=None):
    node = {"_object": False, "_writable": True, "_timestamp": TS}
    if value is not None:
        node["_value"] = value
    return node


def obj(children):
    return {"_object": True, "_timestamp": TS, **children}


def device(fw="V2.1.00-260205"):
    def wlan():
        return obj({"SSID": leaf(), "Enable": leaf(), "PossibleChannels": leaf(),
                    "AssociatedDevice": obj({}), "WPS": obj({"Enable": leaf()})})
    return {"_id": "68229F-V2802ACT-PRUEBA", "InternetGatewayDevice": obj({
        "DeviceInfo": obj({"SoftwareVersion": leaf(fw)}),
        "LANDevice": obj({"1": obj({
            "Hosts": obj({"HostNumberOfEntries": leaf()}),
            "WLANConfiguration": obj({"1": wlan(), "5": wlan()}),
        })}),
    })}


def test_firmware_conocido():
    assert f"{W}.1.PossibleChannels" in dr.known_bad(device())
    assert dr.known_bad(device("V2.1.00-250210")) == ()


def test_tareas_que_esquivan_el_parametro():
    bad = {f"{W}.1.PossibleChannels"}
    tasks = dr.avoid_tasks(device(), "InternetGatewayDevice.LANDevice", bad)
    refreshed = [t["objectName"] for t in tasks if t["name"] == "refreshObject"]
    gpv = [p for t in tasks if t["name"] == "getParameterValues" for p in t["parameterNames"]]
    # Lo que no contiene el parametro malo se lee entero.
    assert "InternetGatewayDevice.LANDevice.1.Hosts" in refreshed
    assert f"{W}.5" in refreshed
    assert f"{W}.1.WPS" in refreshed and f"{W}.1.AssociatedDevice" in refreshed
    # La red con el parametro malo se lee valor por valor, sin el.
    assert sorted(gpv) == [f"{W}.1.Enable", f"{W}.1.SSID"]
    assert not any("PossibleChannels" in x for x in refreshed + gpv)


def test_rama_de_una_tarea():
    assert dr.task_branch({"objectName": "A.B."}) == "A.B"
    assert dr.task_branch({"parameterNames": [f"{W}.1.SSID", f"{W}.1.Enable"]}) == f"{W}.1"
    assert dr.task_branch({"parameterNames": [f"{W}.1.SSID"]}) == f"{W}.1"


def test_parametro_sin_valor_es_none():
    assert get_parameter(device(), f"{W}.1.Enable") is None
    assert isinstance(get_parameter(device(), f"{W}.1"), dict)


@pytest.fixture
def redis(monkeypatch):
    import fakeredis
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_client", r, raising=False)
    monkeypatch.setattr(dr, "get_redis", lambda: r)
    return r


async def test_aprende_el_parametro_del_fault_y_lo_esquiva(redis, monkeypatch):
    d = device("V9.9")  # firmware no listado: hay que aprenderlo
    posted = []
    tasks = [{"_id": "t1", "name": "refreshObject", "objectName": f"{W}"}]

    async def get_tasks(_id):
        return tasks

    async def get_faults(_id):
        return [{"_id": "x:task_t1", "channel": "task_t1", "code": "cwmp.9002",
                 "message": f"{W}.1.PossibleChannels"}]

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(genieacs, "get_tasks", get_tasks)
    monkeypatch.setattr(genieacs, "get_faults", get_faults)
    monkeypatch.setattr(genieacs, "delete_task", noop)
    monkeypatch.setattr(genieacs, "delete_fault", noop)

    state = await dr.refresh_status("id")
    assert state["failed"][0]["code"] == "cwmp.9002"
    assert await redis.smembers(dr.BAD_KEY.format("id")) == {f"{W}.1.PossibleChannels"}

    tasks.clear()

    async def post_task(_id, task, connection_request=False, wait_ms=3000):
        posted.append(task)
        return 200

    monkeypatch.setattr(genieacs, "post_task", post_task)
    result = await dr.request_refresh("id", d, max_age=0)
    assert result["status"] == "done"
    names = [t.get("objectName") or t["name"] for t in posted]
    assert f"{W}.5" in names
    assert not any("PossibleChannels" in str(t) for t in posted)
    assert any(t["name"] == "getParameterValues" for t in posted)
