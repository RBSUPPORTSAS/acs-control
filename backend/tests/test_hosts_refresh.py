"""POST /api/devices/{id}/hosts/refresh: relee solo equipos y señal Wi-Fi."""

from urllib.parse import quote

from conftest import DEVICE_ID, login
from app.services.genieacs import genieacs

DID = quote(DEVICE_ID, safe="")


def device():
    return {"_id": DEVICE_ID, "InternetGatewayDevice": {"LANDevice": {"1": {
        "Hosts": {"_object": True},
        "WLANConfiguration": {"1": {"_object": True}, "5": {"_object": True}},
    }}}}


async def test_pide_hosts_y_asociaciones_en_una_sesion(client, monkeypatch):
    posted = []

    async def get_device(_):
        return device()

    async def post_task(device_id, task, connection_request=False, wait_ms=3000):
        posted.append((task["objectName"], connection_request))
        return 200

    monkeypatch.setattr(genieacs, "get_device", get_device)
    monkeypatch.setattr(genieacs, "post_task", post_task)

    await login(client, "soporte")
    r = await client.post(f"/api/devices/{DID}/hosts/refresh")
    assert r.status_code == 200 and r.json()["status"] == "actualizado"
    assert [p for p, _ in posted] == [
        "InternetGatewayDevice.LANDevice.1.Hosts",
        "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.AssociatedDevice",
        "InternetGatewayDevice.LANDevice.1.WLANConfiguration.5.AssociatedDevice",
    ]
    # Solo la ultima tarea despierta a la ONU.
    assert [cr for _, cr in posted] == [False, False, True]


async def test_onu_que_no_responde_no_deja_tareas(client, monkeypatch):
    tasks = []
    deleted = []

    async def get_device(_):
        return device()

    async def post_task(device_id, task, connection_request=False, wait_ms=3000):
        tasks.append({"_id": str(len(tasks)), "name": "refreshObject", "objectName": task["objectName"]})
        return 202

    async def get_tasks(_):
        return tasks

    async def delete_task(task_id):
        deleted.append(task_id)

    monkeypatch.setattr(genieacs, "get_device", get_device)
    monkeypatch.setattr(genieacs, "post_task", post_task)
    monkeypatch.setattr(genieacs, "get_tasks", get_tasks)
    monkeypatch.setattr(genieacs, "delete_task", delete_task)

    await login(client, "tecnico")
    r = await client.post(f"/api/devices/{DID}/hosts/refresh")
    assert r.json()["status"] == "en_cola" and sorted(deleted) == ["0", "1", "2"]
