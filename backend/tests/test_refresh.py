"""Lectura de datos bajo demanda (refreshObject) y sincronizacion de ONUs nuevas."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core import redis_client
from app.services import device_refresh, refresh_sync
from app.services.device_refresh import data_status, plan_refresh
from app.services.genieacs import genieacs

from conftest import login

# Hora real: los endpoints comparan con el reloj del sistema.
NOW = datetime.now(timezone.utc).replace(microsecond=0)
NEW_ID = "80F1A8-V2802DAC-NUEVA"


def ts(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")


def p(value, minutes_ago=1):
    return {"_value": value, "_object": False, "_timestamp": ts(minutes_ago)}


def unknown():
    # Parametro cuya existencia se conoce pero sin valor leido.
    return {"_object": False}


def obj(children, minutes_ago=1, structure=True):
    node = {"_object": True, **children}
    if structure:
        node["_timestamp"] = ts(minutes_ago)
    return node


def complete_device(age=1):
    return {
        "_id": "COMPLETA",
        "_deviceId": {"_Manufacturer": "VSOL", "_ProductClass": "V2802DAC", "_SerialNumber": "C1"},
        "_lastInform": ts(1),
        "InternetGatewayDevice": obj({
            "DeviceInfo": obj({"SoftwareVersion": p("V3", age), "UpTime": p(10, age)}, age),
            "WANDevice": obj({"1": obj({"WANConnectionDevice": obj({"1": obj({"Name": p("wan", age)}, age)}, age)}, age)}, age),
            "LANDevice": obj({"1": obj({
                "WLANConfiguration": obj({"1": obj({"SSID": p("red", age)}, age)}, age),
                "Hosts": obj({"HostNumberOfEntries": p(2, age)}, age),
            }, age)}, age),
            "X_HW_Security": obj({"AclServices": obj({"FireWallGrade": p(0, age)}, age)}, age),
            # Nunca se debe pedir: trae la configuracion con contrasenas.
            "DeviceConfig": obj({"ConfigFile": unknown()}, age),
            "ManagementServer": obj({"URL": unknown()}, age),
        }),
    }


def new_device():
    """Como llega una ONU recien registrada: casi sin valores."""
    return {
        "_id": NEW_ID,
        "_deviceId": {"_Manufacturer": "VSOL", "_ProductClass": "V2802DAC", "_SerialNumber": "N1"},
        "_lastInform": ts(1),
        "InternetGatewayDevice": obj({
            "DeviceInfo": obj({"SoftwareVersion": p("V3")}, structure=False),
            "WANDevice": obj({"1": obj({"WANConnectionDevice": obj({})})}),
            "LANDevice": obj({"1": obj({
                "WLANConfiguration": obj({"1": obj({"SSID": p("red"), "KeyPassphrase": unknown(), "Channel": unknown()})}),
                "Hosts": obj({"HostNumberOfEntries": unknown()}),
            })}),
            "DeviceConfig": obj({"ConfigFile": unknown()}),
        }),
    }


# --- Plan de lectura --------------------------------------------------------

def test_onu_completa_y_al_dia_no_pide_nada():
    assert plan_refresh(complete_device(), max_age=None, now=NOW.timestamp()) == []
    assert plan_refresh(complete_device(), max_age=900, now=NOW.timestamp()) == []


def test_onu_nueva_pide_solo_ramas_que_existen_y_usa_acs_control():
    plan = plan_refresh(new_device(), max_age=None, now=NOW.timestamp())
    assert plan == [
        "InternetGatewayDevice.DeviceInfo",
        "InternetGatewayDevice.WANDevice",
        "InternetGatewayDevice.LANDevice",
    ]
    # X_HW_Security aun no se conoce: pedirla generaria un fault 9005.
    assert "InternetGatewayDevice.X_HW_Security" not in plan


def test_nunca_pide_la_raiz_ni_deviceconfig():
    for light in (False, True):
        for device in (new_device(), complete_device(age=600)):
            plan = plan_refresh(device, max_age=0, light=light, now=NOW.timestamp())
            assert plan
            assert "InternetGatewayDevice" not in plan
            assert not [b for b in plan if "DeviceConfig" in b or "ManagementServer" in b]


def test_datos_viejos_se_vuelven_a_pedir():
    plan = plan_refresh(complete_device(age=30), max_age=900, now=NOW.timestamp())
    assert "InternetGatewayDevice.LANDevice" in plan
    status = data_status(complete_device(age=30), max_age=900, now=NOW.timestamp())
    assert status["complete"] is True and status["stale"] is True


def test_modo_liviano_pide_por_partes():
    plan = plan_refresh(new_device(), max_age=None, light=True, now=NOW.timestamp())
    assert "InternetGatewayDevice.LANDevice.1.WLANConfiguration" in plan
    assert "InternetGatewayDevice.LANDevice.1.Hosts" in plan
    assert "InternetGatewayDevice.LANDevice" not in plan


def test_estado_de_onu_nueva():
    status = data_status(new_device(), max_age=900, now=NOW.timestamp())
    assert status["complete"] is False
    assert set(status["missing"]) == {"DeviceInfo", "WANDevice", "LANDevice"}


# --- GenieACS simulado (tareas y faults) --------------------------------------

class FakeGenie:
    def __init__(self, devices):
        self.devices = {d["_id"]: d for d in devices}
        self.tasks = []
        self.faults = []
        self.posted = []
        self.deleted_tasks = []
        self.deleted_faults = []
        self.answer = 202

    async def get_device(self, device_id):
        return self.devices.get(device_id)

    async def find_devices(self, query, projection=None, limit=500):
        self.last_query = query
        return [{"_id": d["_id"], "_registered": ts(60), "_lastInform": d["_lastInform"]} for d in self.devices.values()]

    async def get_tasks(self, device_id):
        return [t for t in self.tasks if t["device"] == device_id]

    async def get_faults(self, device_id):
        return [f for f in self.faults if f["device"] == device_id]

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        tid = f"t{len(self.posted) + 1}"
        self.posted.append((device_id, task["objectName"], connection_request))
        self.tasks.append({"_id": tid, "device": device_id, **task})
        return self.answer if connection_request else 202

    async def delete_task(self, task_id):
        self.deleted_tasks.append(task_id)
        self.tasks = [t for t in self.tasks if t["_id"] != task_id]

    async def delete_fault(self, fault_id):
        self.deleted_faults.append(fault_id)
        self.faults = [f for f in self.faults if f["_id"] != fault_id]


@pytest.fixture
def genie(monkeypatch):
    fake = FakeGenie([new_device(), complete_device()])
    for name in ("get_device", "find_devices", "get_tasks", "get_faults", "post_task", "delete_task", "delete_fault"):
        monkeypatch.setattr(genieacs, name, getattr(fake, name))
    return fake


# --- Endpoints ----------------------------------------------------------------

async def test_detalle_incluye_estado_de_datos(client, genie):
    await login(client, "tecnico")
    r = await client.get(f"/api/devices/{NEW_ID}")
    assert r.status_code == 200
    assert r.json()["data_status"]["complete"] is False


async def test_refresh_requiere_sesion(client, genie):
    r = await client.post(f"/api/devices/{NEW_ID}/refresh")
    assert r.status_code == 401
    assert genie.posted == []


async def test_tecnico_pide_lectura_y_solo_la_ultima_despierta_a_la_onu(client, genie):
    await login(client, "tecnico")
    r = await client.post(f"/api/devices/{NEW_ID}/refresh")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert len(body["branches"]) == 3
    assert [cr for _, _, cr in genie.posted] == [False, False, True]


async def test_respuesta_inmediata_de_la_onu(client, genie):
    genie.answer = 200
    await login(client, "tecnico")
    r = await client.post(f"/api/devices/{NEW_ID}/refresh")
    assert r.json()["status"] == "done"


async def test_no_duplica_lecturas_pendientes(client, genie):
    await login(client, "tecnico")
    await client.post(f"/api/devices/{NEW_ID}/refresh")
    r = await client.post(f"/api/devices/{NEW_ID}/refresh")
    assert r.json()["status"] == "pending"
    assert len(genie.posted) == 3


async def test_onu_completa_no_encola_nada(client, genie):
    await login(client, "tecnico")
    r = await client.post("/api/devices/COMPLETA/refresh")
    assert r.json()["status"] == "fresh"
    assert genie.posted == []


async def test_force_relee_aunque_este_al_dia(client, genie):
    await login(client, "tecnico")
    r = await client.post("/api/devices/COMPLETA/refresh?force=true")
    assert r.json()["status"] == "queued"
    assert genie.posted


async def test_onu_inexistente(client, genie):
    await login(client, "tecnico")
    assert (await client.post("/api/devices/NO-EXISTE/refresh")).status_code == 404


async def test_lectura_fallida_se_limpia_y_activa_modo_liviano(client, genie):
    await login(client, "tecnico")
    await client.post(f"/api/devices/{NEW_ID}/refresh")
    lan = next(t for t in genie.tasks if t["objectName"].endswith("LANDevice"))
    genie.faults.append({
        "_id": f"{NEW_ID}:task_{lan['_id']}", "device": NEW_ID, "channel": f"task_{lan['_id']}",
        "code": "session_terminated", "message": "The TR-069 session was unsuccessfully terminated",
    })
    # Un fault ajeno (de otra tarea o provision) no se toca.
    genie.faults.append({"_id": f"{NEW_ID}:default", "device": NEW_ID, "channel": "default", "code": "x"})

    r = await client.get(f"/api/devices/{NEW_ID}/refresh")
    body = r.json()
    assert body["failed"][0]["branch"] == "InternetGatewayDevice.LANDevice"
    assert body["pending"] == 2
    assert body["light"] is True
    assert genie.deleted_tasks == [lan["_id"]]
    assert genie.deleted_faults == [f"{NEW_ID}:task_{lan['_id']}"]

    # Cuando terminan las demas, la siguiente lectura va por partes.
    genie.tasks.clear()
    r = await client.post(f"/api/devices/{NEW_ID}/refresh")
    assert "InternetGatewayDevice.LANDevice.1.WLANConfiguration" in r.json()["branches"]


# --- Sincronizacion de ONUs nuevas ---------------------------------------------

async def test_sync_encola_sin_despertar_y_marca_completas(client, genie):
    summary = await refresh_sync.sync_new_devices(now=NOW)
    assert summary["queued"] == [NEW_ID]
    assert summary["complete"] == ["COMPLETA"]
    assert genie.posted and all(cr is False for _, _, cr in genie.posted)
    # Solo ONUs nuevas y que reportaron hace poco.
    assert "_registered" in genie.last_query and "_lastInform" in genie.last_query


async def test_sync_usa_candado_y_no_repite(client, genie):
    await refresh_sync.sync_new_devices(now=NOW)
    assert (await refresh_sync.sync_new_devices(now=NOW)) == {"skipped": "lock"}

    await redis_client.get_redis().delete(refresh_sync.LOCK_KEY)
    posted = len(genie.posted)
    summary = await refresh_sync.sync_new_devices(now=NOW)
    assert summary["waiting"] == [NEW_ID]
    assert "COMPLETA" not in summary["complete"]
    assert len(genie.posted) == posted
