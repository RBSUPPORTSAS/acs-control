"""Destrabar una ONU cuando un preset de GenieACS falla y bloquea la cola."""

from urllib.parse import quote

import pytest

from conftest import DEVICE_ID, login
from app.services import genie_health
from app.services.genieacs import genieacs

DID = quote(DEVICE_ID, safe="")
P = "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.PossibleChannels"

BOOT = {"_id": f"{DEVICE_ID}:bootstrap", "channel": "bootstrap", "code": "cwmp.9002", "message": P,
        "timestamp": "2026-11-21T15:28:45Z", "retries": 1}
INFORM = {"_id": f"{DEVICE_ID}:inform", "channel": "inform", "code": "cwmp.9003", "message": "Invalid arguments",
          "detail": {"setParameterValuesFault": [{"parameterName": "InternetGatewayDevice.ManagementServer.PeriodicInformTime"}]}}
TASK = {"_id": f"{DEVICE_ID}:task_abc", "channel": "task_abc", "code": "cwmp.9002", "message": "x"}


def test_solo_faults_de_presets_con_texto():
    out = genie_health.preset_faults([BOOT, INFORM, TASK])
    assert [f["channel"] for f in out] == ["bootstrap", "inform"]
    assert "reset" in out[0]["message"] and "WLANConfiguration.1.PossibleChannels" in out[0]["message"]
    assert "ManagementServer.PeriodicInformTime" in out[1]["message"]


@pytest.fixture
def genie(monkeypatch):
    state = {"faults": [BOOT, TASK], "tasks": [{"_id": "t1", "name": "refreshObject"}] * 61, "deleted": [], "posted": []}

    async def get_faults(_id):
        return list(state["faults"])

    async def get_tasks(_id):
        return list(state["tasks"])

    async def delete_fault(fid):
        state["deleted"].append(fid)
        state["faults"] = [f for f in state["faults"] if f["_id"] != fid]

    async def post_task(_id, task, connection_request=False, wait_ms=3000):
        state["posted"].append(task)
        state["tasks"] = []  # la ONU procesa la cola
        return 200

    monkeypatch.setattr(genieacs, "get_faults", get_faults)
    monkeypatch.setattr(genieacs, "get_tasks", get_tasks)
    monkeypatch.setattr(genieacs, "delete_fault", delete_fault)
    monkeypatch.setattr(genieacs, "post_task", post_task)
    return state


async def test_ficha_avisa_y_tecnico_destraba(client, genie):
    await login(client, "tecnico")
    detail = (await client.get(f"/api/devices/{DID}")).json()
    assert detail["genieacs"]["blocked"] is True and detail["genieacs"]["pending_tasks"] == 61
    assert detail["genieacs"]["faults"][0]["channel"] == "bootstrap"

    r = await client.post(f"/api/devices/{DID}/genieacs/unblock")
    assert r.status_code == 200
    body = r.json()
    assert body["cleared"] == ["bootstrap"] and body["answered"] is True
    assert body["blocked"] is False and body["pending_tasks"] == 0
    # El fault de una tarea no es de un preset: no se toca aqui.
    assert genie["deleted"] == [BOOT["_id"]]
    # Relee usuario/clave de connection request (reset de fabrica) y despierta.
    assert genie["posted"][0]["parameterNames"][0].endswith("ConnectionRequestUsername")
    assert genie["posted"][-1]["parameterNames"] == ["InternetGatewayDevice.DeviceInfo.UpTime"]

    await login(client, "jefe")
    audits = (await client.get("/api/audit")).json()["audits"]
    assert any(a["action"] == "GENIEACS_DESTRABAR" for a in audits)


async def test_rol_wifi_no_destraba(client, genie):
    await login(client, "soporte")
    assert (await client.post(f"/api/devices/{DID}/genieacs/unblock")).status_code == 403
