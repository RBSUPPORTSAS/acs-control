"""Rol "wifi" (Soporte Wi-Fi): ve inventario, informacion, equipos y Wi-Fi."""

from urllib.parse import quote

from conftest import DEVICE_ID, login

DID = quote(DEVICE_ID, safe="")


async def test_soporte_ve_la_onu_sus_equipos_y_el_wifi(client):
    r = await login(client, "soporte")
    assert r.json()["user"]["role"] == "wifi"
    assert (await client.get("/api/devices")).status_code == 200
    assert (await client.get(f"/api/devices/{DID}")).status_code == 200
    assert (await client.get(f"/api/devices/{DID}/hosts")).status_code == 200
    assert (await client.get(f"/api/devices/{DID}/wifi")).status_code == 200


async def test_soporte_no_gestiona_wan_catv_seguridad_ni_etiquetas(client):
    await login(client, "soporte")
    for method, path in [
        ("GET", f"/api/devices/{DID}/wan"),
        ("POST", f"/api/devices/{DID}/wan/create-dhcp"),
        ("DELETE", f"/api/devices/{DID}/wan/2/WANIPConnection/1"),
        ("GET", f"/api/devices/{DID}/catv"),
        ("POST", f"/api/devices/{DID}/catv/off"),
        ("GET", f"/api/devices/{DID}/security-module"),
        ("PATCH", f"/api/devices/{DID}/security-module/service/telnet"),
        ("POST", f"/api/devices/{DID}/tags/prueba"),
        ("DELETE", f"/api/devices/{DID}/tags/prueba"),
    ]:
        r = await client.request(method, path, json={})
        assert r.status_code == 403, (method, path, r.status_code)
        assert "Wi-Fi" in r.json()["detail"]


async def test_soporte_no_administra(client):
    await login(client, "soporte")
    for path in ["/api/users", "/api/audit", "/api/system/config", f"/api/devices/{DID}?raw=true"]:
        assert (await client.get(path)).status_code == 403, path


async def test_tecnico_sigue_gestionando_red(client):
    await login(client, "tecnico")
    assert (await client.get(f"/api/devices/{DID}/wan")).status_code != 403
    assert (await client.get(f"/api/devices/{DID}/catv")).status_code != 403


async def test_admin_crea_usuario_soporte(client):
    await login(client, "jefe")
    r = await client.post("/api/users", json={"username": "soporte2", "role": "wifi", "password": "clave-soporte-456"})
    assert r.status_code in (200, 201) and r.json()["user"]["role"] == "wifi"
