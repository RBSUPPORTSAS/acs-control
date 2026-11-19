"""Catalogo de etiquetas: admin las define; technical solo asigna/quita esas."""

from urllib.parse import quote

import pytest

from conftest import DEVICE_ID, login
from app.services.genieacs import genieacs

DID = quote(DEVICE_ID, safe="")


@pytest.fixture
def tags_ok(monkeypatch):
    calls = []

    async def add(device_id, tag):
        calls.append(("add", tag))

    async def remove(device_id, tag):
        calls.append(("remove", tag))

    monkeypatch.setattr(genieacs, "add_tag", add)
    monkeypatch.setattr(genieacs, "remove_tag", remove)
    return calls


async def test_admin_crea_edita_y_borra(client):
    await login(client, "jefe")
    r = await client.post("/api/tags", json={"name": "Cliente VIP", "color": "#FF8800", "description": "Atención prioritaria"})
    assert r.status_code == 201
    tag = r.json()
    assert tag["color"] == "#ff8800"

    # Duplicado sin importar mayúsculas.
    assert (await client.post("/api/tags", json={"name": "cliente vip"})).status_code == 409

    r = await client.patch(f"/api/tags/{tag['id']}", json={"color": "#00aa55", "description": ""})
    assert r.json()["color"] == "#00aa55" and r.json()["description"] is None

    assert [t["name"] for t in (await client.get("/api/tags")).json()["tags"]] == ["Cliente VIP"]
    assert (await client.delete(f"/api/tags/{tag['id']}")).status_code == 200
    assert (await client.get("/api/tags")).json()["tags"] == []

    audits = (await client.get("/api/audit?tipo=SISTEMA")).json()["audits"]
    acciones = {a["action"] for a in audits}
    assert {"ETIQUETA_CATALOGO_CREAR", "ETIQUETA_CATALOGO_EDITAR", "ETIQUETA_CATALOGO_ELIMINAR"} <= acciones


async def test_validaciones(client):
    await login(client, "jefe")
    assert (await client.post("/api/tags", json={"name": "a/b"})).status_code == 400
    assert (await client.post("/api/tags", json={"name": "  "})).status_code == 400
    assert (await client.post("/api/tags", json={"name": "x" * 65})).status_code == 400
    assert (await client.post("/api/tags", json={"name": "ok", "color": "rojo"})).status_code == 400
    assert (await client.post("/api/tags", json={"name": "ok", "description": "d" * 161})).status_code == 400
    assert (await client.patch("/api/tags/999", json={"color": "#000000"})).status_code == 404


async def test_solo_admin_administra_el_catalogo_pero_todos_lo_ven(client):
    await login(client, "jefe")
    tid = (await client.post("/api/tags", json={"name": "Mantenimiento"})).json()["id"]
    for user in ("tecnico", "soporte"):
        await login(client, user)
        assert (await client.get("/api/tags")).status_code == 200
        assert (await client.post("/api/tags", json={"name": "otra"})).status_code == 403
        assert (await client.patch(f"/api/tags/{tid}", json={"color": "#000000"})).status_code == 403
        assert (await client.delete(f"/api/tags/{tid}")).status_code == 403
    await client.post("/api/auth/logout")
    assert (await client.get("/api/tags")).status_code == 401


async def test_tecnico_solo_asigna_del_catalogo(client, tags_ok):
    await login(client, "jefe")
    await client.post("/api/tags", json={"name": "Cliente VIP"})

    await login(client, "tecnico")
    assert (await client.post(f"/api/devices/{DID}/tags/{quote('Cliente VIP')}")).status_code == 200
    r = await client.post(f"/api/devices/{DID}/tags/inventada")
    assert r.status_code == 403 and "catálogo" in r.json()["detail"]
    assert (await client.delete(f"/api/devices/{DID}/tags/{quote('Cliente VIP')}")).status_code == 200
    # Una etiqueta fuera del catálogo (p. ej. de un preset de GenieACS) no la quita.
    assert (await client.delete(f"/api/devices/{DID}/tags/preset-genie")).status_code == 403
    assert tags_ok == [("add", "Cliente VIP"), ("remove", "Cliente VIP")]


async def test_admin_puede_usar_etiquetas_libres(client, tags_ok):
    await login(client, "jefe")
    assert (await client.post(f"/api/devices/{DID}/tags/libre")).status_code == 200
    assert (await client.delete(f"/api/devices/{DID}/tags/preset-genie")).status_code == 200
    assert tags_ok == [("add", "libre"), ("remove", "preset-genie")]
