"""Tokens API (Bearer) para agentes y documentacion protegida."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from conftest import DEVICE_ID, login
from app.models.api_token import ApiToken
from app.services.genieacs import genieacs

DID = quote(DEVICE_ID, safe="")


async def crear(client, name="agente", role="technical", days=90):
    await login(client, "jefe")
    r = await client.post("/api/tokens", json={"name": name, "role": role, "expires_days": days})
    assert r.status_code == 201, r.text
    client.cookies.clear()  # desde aqui, solo el token
    return r.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def test_crear_listar_y_usar(client):
    t = await crear(client)
    assert t["token"].startswith("acs_") and len(t["token"]) > 40 and t["prefix"] == t["token"][:10]

    r = await client.get("/api/devices", headers=bearer(t["token"]))
    assert r.status_code == 200 and r.json()["devices"]
    assert (await client.get("/api/auth/me", headers=bearer(t["token"]))).json()["user"]["username"] == "api:agente"

    await login(client, "jefe")
    listed = (await client.get("/api/tokens")).json()["tokens"]
    assert [x["name"] for x in listed] == ["agente"]
    assert "token" not in listed[0] and "token_hash" not in listed[0]
    assert listed[0]["last_used_at"] is not None


async def test_permisos_del_rol_del_token(client):
    wifi = (await crear(client, "soporte-bot", role="wifi"))["token"]
    tec = (await crear(client, "noc-bot", role="technical"))["token"]

    assert (await client.get(f"/api/devices/{DID}", headers=bearer(wifi))).status_code == 200
    assert (await client.get(f"/api/devices/{DID}/wan", headers=bearer(wifi))).status_code == 403
    assert (await client.get("/api/audit", headers=bearer(tec))).status_code == 403
    assert (await client.get("/api/users", headers=bearer(tec))).status_code == 403


async def test_un_token_no_administra_tokens(client):
    adm = (await crear(client, "admin-bot", role="admin"))["token"]
    assert (await client.get("/api/audit", headers=bearer(adm))).status_code == 200
    r = await client.post("/api/tokens", json={"name": "otro"}, headers=bearer(adm))
    assert r.status_code == 403 and "sesión" in r.json()["detail"]
    assert (await client.get("/api/tokens", headers=bearer(adm))).status_code == 403


async def test_revocado_vencido_e_invalido(client):
    t = await crear(client)
    await login(client, "jefe")
    assert (await client.delete(f"/api/tokens/{t['id']}")).json()["revoked"] is True
    client.cookies.clear()
    assert (await client.get("/api/devices", headers=bearer(t["token"]))).status_code == 401

    v = await crear(client, "viejo")
    async with client.session_factory() as db:
        row = await db.get(ApiToken, v["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()
    assert (await client.get("/api/devices", headers=bearer(v["token"]))).status_code == 401

    assert (await client.get("/api/devices", headers=bearer("acs_inventado"))).status_code == 401
    assert (await client.get("/api/devices", headers=bearer("x"))).status_code == 401
    assert (await client.get("/api/devices")).status_code == 401


async def test_validaciones(client):
    await login(client, "jefe")
    assert (await client.post("/api/tokens", json={"name": "a b"})).status_code == 400
    assert (await client.post("/api/tokens", json={"name": "ok", "role": "root"})).status_code == 400
    assert (await client.post("/api/tokens", json={"name": "ok", "expires_days": 0})).status_code == 400
    assert (await client.post("/api/tokens", json={"name": "ok", "expires_days": None})).json()["expires_at"] is None
    assert (await client.post("/api/tokens", json={"name": "ok"})).status_code == 409
    await login(client, "tecnico")
    assert (await client.post("/api/tokens", json={"name": "mio"})).status_code == 403


async def test_auditoria_registra_el_token(client, monkeypatch):
    async def ok(*a, **k):
        return None
    monkeypatch.setattr(genieacs, "add_tag", ok)
    t = await crear(client, "etiquetador", role="admin")
    assert (await client.post(f"/api/devices/{DID}/tags/libre", headers=bearer(t["token"]))).status_code == 200
    await login(client, "jefe")
    audits = (await client.get("/api/audit")).json()["audits"]
    assert any(a["action"] == "ETIQUETA_AGREGAR" and a["username"] == "api:etiquetador" for a in audits)
    assert any(a["action"] == "TOKEN_API_CREAR" for a in audits)


async def test_documentacion_protegida_en_json(client):
    assert (await client.get("/api/openapi.json")).status_code == 401
    assert (await client.get("/api/docs")).status_code == 401
    assert (await client.get("/openapi.json")).status_code == 404
    assert (await client.get("/docs")).status_code == 404

    t = await crear(client)
    spec = (await client.get("/api/openapi.json", headers=bearer(t["token"]))).json()
    assert spec["openapi"].startswith("3.")
    assert "HTTPBearer" in spec["components"]["securitySchemes"]
    assert "/api/devices/{device_id}/wifi/{index}" in spec["paths"]
    tags = {tag for p in spec["paths"].values() for op in p.values() for tag in op.get("tags", [])}
    assert {"Dispositivos", "Wi-Fi", "WAN", "Seguridad", "Tokens API"} <= tags
    html = await client.get("/api/docs", headers=bearer(t["token"]))
    assert html.status_code == 200 and "swagger" in html.text.lower()


async def test_health_sin_sesion_solo_dice_que_responde(client):
    assert (await client.get("/api/health")).json() == {"api": True}
