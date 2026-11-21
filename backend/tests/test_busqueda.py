"""Busqueda de ONUs: no depende de que la ONU este entre las primeras `limit`."""

import copy

from conftest import DEVICE, login
from app.services.genieacs import genieacs


def onu(serial, model="V2802ACT", ip="10.0.0.1"):
    d = copy.deepcopy(DEVICE)
    d["_id"] = f"4C46D1-{model}-{serial}"
    d["_deviceId"] = {**d.get("_deviceId", {}), "_SerialNumber": serial, "_ProductClass": model}
    return d


async def test_busca_por_ultimos_digitos_fuera_del_limite(client, monkeypatch):
    todas = [onu(f"12345{i:012d}") for i in range(60)] + [onu("123454C46D1BC9782")]
    pedidas = []

    async def get_devices(limit=100, projection=None, query=None):
        pedidas.append((limit, query))
        if query:
            import re
            rx = query["$or"][1]["_deviceId._SerialNumber"]["$regex"]
            return [d for d in todas if re.search(rx, d["_deviceId"]["_SerialNumber"])][:limit]
        return todas[:limit]

    monkeypatch.setattr(genieacs, "get_devices", get_devices)
    await login(client, "tecnico")

    r = (await client.get("/api/devices?q=BC9782&limit=20")).json()
    assert [d["serial_number"] for d in r["devices"]] == ["123454C46D1BC9782"]
    # La busqueda va a GenieACS (no solo dentro de las primeras 20).
    assert pedidas[0][1] and "$or" in pedidas[0][1]

    # Sin q sigue igual: las primeras `limit`.
    assert len((await client.get("/api/devices?limit=5")).json()["devices"]) == 5


async def test_texto_con_caracteres_especiales_no_rompe_la_consulta(client, monkeypatch):
    vistos = []

    async def get_devices(limit=100, projection=None, query=None):
        vistos.append(query)
        return []

    monkeypatch.setattr(genieacs, "get_devices", get_devices)
    await login(client, "tecnico")
    assert (await client.get("/api/devices?q=V2804AX30%2DH(")).status_code == 200
    rx = vistos[0]["$or"][0]["_id"]
    assert "$options" not in rx and rx["$regex"] == r"(?:[vV]2804[aA][xX]30\-[hH]\()"


def test_expresion_segura_para_genieacs():
    import re
    from app.api.routers.devices import search_regex
    assert search_regex("260205") == "(?:260205)"
    assert re.search(search_regex("bc9782"), "123454C46D1BC9782")
    assert re.search(search_regex("10.20.24"), "10.20.24.217") and not re.search(search_regex("10.20.24"), "10a20b24")
