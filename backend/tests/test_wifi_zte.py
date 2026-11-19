"""Wi-Fi en ZTE F6600P (fw V9.0.10P6N44).

La ONU responde cwmp.9003 a Channel=0 y rechaza todo el setParameterValues,
asi que el formulario (que siempre manda canal automatico) tumbaba tambien
el cambio de SSID y clave sin que la interfaz lo dijera.
"""

from urllib.parse import quote

from conftest import login
from app.services.genieacs import genieacs
from app.services.wifi_writer import build_wifi_changes, drop_unchanged

TS = "2026-11-19T16:00:00.000Z"
ID = "18B0A4-F6600P-PRUEBA"


def v(value, t="xsd:string"):
    return {"_value": value, "_writable": True, "_type": t, "_timestamp": TS, "_object": False}


def wlan(ssid, std, ch, auto=True):
    return {
        "_object": True,
        "Enable": v(True, "xsd:boolean"),
        "SSID": v(ssid),
        "Standard": v(std),
        "Channel": v(ch, "xsd:unsignedInt"),
        "AutoChannelEnable": v(auto, "xsd:boolean"),
        "SSIDAdvertisementEnabled": v(True, "xsd:boolean"),
        "KeyPassphrase": v(""),
        "BeaconType": v("11i"),
    }


def zte():
    return {"_id": ID, "_deviceId": {"_ProductClass": "F6600P"}, "InternetGatewayDevice": {"LANDevice": {"1": {
        "WLANConfiguration": {"1": wlan("ZTE_24", "b,g,n,ax", 2), "5": wlan("ZTE_5G", "a,n,ac,ax", 40)},
    }}}}


FORM = {"enabled": True, "ssid": "Nueva", "auto_channel": True, "hidden": False, "password": "clave-segura-1"}


def paths(values):
    return {p.rsplit(".", 1)[1]: val for p, val, _ in values}


def test_formulario_completo_solo_envia_lo_que_cambia():
    d = zte()
    payload = drop_unchanged(d, 1, FORM)
    assert payload == {"ssid": "Nueva", "password": "clave-segura-1"}
    values, requested = build_wifi_changes(d, 1, payload)
    assert paths(values) == {"SSID": "Nueva", "KeyPassphrase": "clave-segura-1"}
    assert requested == {"ssid": "Nueva"}


def test_pasar_a_automatico_no_envia_channel_cero_si_hay_autochannelenable():
    d = zte()
    d["InternetGatewayDevice"]["LANDevice"]["1"]["WLANConfiguration"]["1"]["AutoChannelEnable"]["_value"] = False
    values, _ = build_wifi_changes(d, 1, drop_unchanged(d, 1, {"auto_channel": True}))
    assert paths(values) == {"AutoChannelEnable": True}


def test_canal_manual():
    d = zte()
    values, requested = build_wifi_changes(d, 5, drop_unchanged(d, 5, {"auto_channel": False, "channel": 149}))
    assert paths(values) == {"AutoChannelEnable": False, "Channel": 149}
    assert requested["channel"] == 149


def test_sin_autochannelenable_sigue_usando_channel_cero():
    d = zte()
    w = d["InternetGatewayDevice"]["LANDevice"]["1"]["WLANConfiguration"]["1"]
    del w["AutoChannelEnable"]
    w["Channel"]["_value"] = 6
    values, _ = build_wifi_changes(d, 1, drop_unchanged(d, 1, {"auto_channel": True}))
    assert paths(values) == {"Channel": 0}


def test_mismo_canal_manual_no_se_reenvia():
    d = zte()
    w = d["InternetGatewayDevice"]["LANDevice"]["1"]["WLANConfiguration"]["5"]
    w["AutoChannelEnable"]["_value"] = False
    assert drop_unchanged(d, 5, {"auto_channel": False, "channel": 40}) == {}


async def _setup(monkeypatch, fault=None):
    deleted = []

    async def get_device(device_id):
        return zte()

    async def spv(device_id, values, wait_ms=None):
        return {"http_status": 202 if fault else 200, "task_id": "abc123"}

    async def get_faults(device_id):
        return [{"_id": f"{ID}:task_abc123", "code": fault, "detail": {"faultString": "Invalid arguments"}}] if fault else []

    async def rm(x):
        deleted.append(x)

    async def nosleep(*a):
        return None

    import asyncio
    monkeypatch.setattr(asyncio, "sleep", nosleep)
    monkeypatch.setattr(genieacs, "get_device", get_device)
    monkeypatch.setattr(genieacs, "set_parameter_values", spv)
    monkeypatch.setattr(genieacs, "get_faults", get_faults)
    monkeypatch.setattr(genieacs, "delete_fault", rm)
    monkeypatch.setattr(genieacs, "delete_task", rm)
    return deleted


async def test_fault_de_la_onu_se_informa_y_se_limpia(client, monkeypatch):
    deleted = await _setup(monkeypatch, fault="cwmp.9003")
    await login(client, "jefe")
    r = await client.patch(f"/api/devices/{quote(ID, safe='')}/wifi/1", json={"ssid": "Nueva"})
    assert r.status_code == 422
    assert "cwmp.9003" in r.json()["detail"] and "No se aplicó" in r.json()["detail"]
    assert deleted == [f"{ID}:task_abc123", "abc123"]


async def test_formulario_sin_cambios(client, monkeypatch):
    await _setup(monkeypatch)
    await login(client, "jefe")
    body = {"enabled": True, "ssid": "ZTE_24", "auto_channel": True, "hidden": False}
    r = await client.patch(f"/api/devices/{quote(ID, safe='')}/wifi/1", json=body)
    assert r.status_code == 200 and r.json()["status"] == "SIN_CAMBIOS"
