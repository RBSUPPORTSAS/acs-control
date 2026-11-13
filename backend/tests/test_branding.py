"""Logo del operador: lo sube admin, lo ve cualquiera (tambien el login)."""

import base64

from conftest import login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>'


def body(raw, kind="image/png"):
    return {"content_type": kind, "data": base64.b64encode(raw).decode()}


async def test_sin_logo_por_defecto_y_publico(client):
    r = await client.get("/api/branding")
    assert r.status_code == 200 and r.json()["logo"] is False
    assert (await client.get("/api/branding/logo")).status_code == 404


async def test_admin_sube_cambia_y_quita_el_logo(client):
    await login(client, "jefe")
    r = await client.put("/api/branding/logo", json=body(PNG))
    assert r.status_code == 200 and r.json()["logo"] is True
    version = r.json()["logo_version"]

    # El login (sin sesion) lo puede descargar.
    await client.post("/api/auth/logout")
    img = await client.get("/api/branding/logo")
    assert img.status_code == 200 and img.content == PNG
    assert img.headers["content-type"] == "image/png"
    assert (await client.get("/api/branding/logo", headers={"If-None-Match": img.headers["etag"]})).status_code == 304
    assert (await client.get("/api/branding")).json()["logo_version"] == version

    await login(client, "jefe")
    assert (await client.delete("/api/branding/logo")).json()["logo"] is False
    assert (await client.get("/api/branding")).json()["logo"] is False

    audits = (await client.get("/api/audit?tipo=SISTEMA")).json()["audits"]
    assert [a["action"] for a in audits].count("MARCA_LOGO") == 2


async def test_solo_admin_cambia_el_logo(client):
    for user in ("tecnico", "soporte"):
        await login(client, user)
        assert (await client.put("/api/branding/logo", json=body(PNG))).status_code == 403
        assert (await client.delete("/api/branding/logo")).status_code == 403
    await client.post("/api/auth/logout")
    assert (await client.put("/api/branding/logo", json=body(PNG))).status_code == 401


async def test_validaciones(client):
    await login(client, "jefe")
    assert (await client.put("/api/branding/logo", json=body(PNG, "image/gif"))).status_code == 400
    assert (await client.put("/api/branding/logo", json=body(b"no es png"))).status_code == 400
    assert (await client.put("/api/branding/logo", json=body(PNG + b"\x00" * 600_000))).status_code == 400
    assert (await client.put("/api/branding/logo", json={"content_type": "image/png", "data": "%%%"})).status_code == 400


async def test_svg_se_sirve_aislado(client):
    await login(client, "jefe")
    assert (await client.put("/api/branding/logo", json=body(SVG, "image/svg+xml"))).status_code == 200
    img = await client.get("/api/branding/logo")
    assert img.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in img.headers["content-security-policy"]
    assert img.headers["x-content-type-options"] == "nosniff"
