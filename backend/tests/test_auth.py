import json
from urllib.parse import quote

from sqlalchemy import select

from conftest import DEVICE_ID, GENIE_URL, PASSWORDS, login
from app.models.audit import AuditLog

DID = quote(DEVICE_ID, safe="")


# ---------------------------------------------------------------- sesion

async def test_sin_sesion_la_api_responde_401(client):
    for path in ["/api/devices", f"/api/devices/{DID}", f"/api/devices/{DID}/wan", "/api/audit", "/api/users", "/api/system/config"]:
        assert (await client.get(path)).status_code == 401, path


async def test_login_correcto_y_me(client):
    r = await login(client, "tecnico")
    assert r.json()["user"]["role"] == "technical"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = await client.get("/api/auth/me")
    assert me.json()["user"]["username"] == "tecnico"


async def test_login_no_distingue_mayusculas_en_usuario(client):
    r = await client.post("/api/auth/login", json={"username": "TECNICO", "password": PASSWORDS["tecnico"]})
    assert r.status_code == 200


async def test_login_incorrecto_y_bloqueo_tras_5_intentos(client):
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"username": "tecnico", "password": "mala-clave-xx"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"username": "tecnico", "password": PASSWORDS["tecnico"]})
    assert r.status_code == 429


async def test_logout_invalida_la_sesion(client):
    await login(client, "tecnico")
    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_usuario_desactivado_pierde_acceso_al_instante(client):
    await login(client, "jefe")
    users = (await client.get("/api/users")).json()["users"]
    tid = next(u["id"] for u in users if u["username"] == "tecnico")

    tec = type(client)(transport=client._transport, base_url="http://test")
    r = await tec.post("/api/auth/login", json={"username": "tecnico", "password": PASSWORDS["tecnico"]})
    assert r.status_code == 200
    assert (await tec.get("/api/devices")).status_code == 200

    assert (await client.patch(f"/api/users/{tid}", json={"active": False})).status_code == 200
    assert (await tec.get("/api/devices")).status_code == 401
    r = await tec.post("/api/auth/login", json={"username": "tecnico", "password": PASSWORDS["tecnico"]})
    assert r.status_code == 401
    await tec.aclose()


# ------------------------------------------------------ permisos technical

async def test_technical_gestiona_onus(client):
    await login(client, "tecnico")
    assert (await client.get("/api/devices")).status_code == 200
    assert (await client.get(f"/api/devices/{DID}")).status_code == 200


async def test_technical_no_ve_configuracion_auditoria_usuarios_ni_documento_crudo(client):
    await login(client, "tecnico")
    assert (await client.get("/api/system/config")).status_code == 403
    assert (await client.get("/api/audit")).status_code == 403
    assert (await client.get("/api/users")).status_code == 403
    assert (await client.get(f"/api/devices/{DID}?raw=true")).status_code == 403


async def test_technical_no_ve_la_direccion_de_genie_en_errores(client):
    await login(client, "tecnico")
    r = await client.get("/api/devices/falla")
    assert r.status_code == 502
    assert "10.99.0.5" not in r.text and "7557" not in r.text
    assert "GenieACS" in r.text


async def test_health_sin_detalles_para_technical(client):
    await login(client, "tecnico")
    data = (await client.get("/api/health")).json()
    assert not any(k.endswith("_error") for k in data)
    assert set(data) >= {"api", "postgresql", "redis", "genieacs", "healthy"}


async def test_health_publico_sin_detalles(client):
    data = (await client.get("/api/health")).json()
    assert not any(k.endswith("_error") for k in data)


# ---------------------------------------------------------- permisos admin

async def test_admin_ve_todo(client):
    await login(client, "jefe")
    assert (await client.get("/api/system/config")).json()["genieacs_nbi_url"] == GENIE_URL
    assert (await client.get("/api/audit")).status_code == 200
    assert (await client.get("/api/users")).status_code == 200
    raw = (await client.get(f"/api/devices/{DID}?raw=true")).json()
    assert raw["raw"]["_id"] == DEVICE_ID
    r = await client.get("/api/devices/falla")
    assert "10.99.0.5" in r.text  # admin si ve el error tecnico completo


async def test_health_con_detalles_para_admin(client):
    await login(client, "jefe")
    data = (await client.get("/api/health")).json()
    assert any(k.endswith("_error") for k in data)


# ------------------------------------------------------------- usuarios

async def test_admin_crea_usuario_technical_y_este_inicia_sesion(client):
    await login(client, "jefe")
    r = await client.post("/api/users", json={"username": "nuevo", "role": "technical", "password": "clave-nueva-123"})
    assert r.status_code == 201
    assert "password" not in json.dumps(r.json()).lower().replace("password_hash", "")
    await client.post("/api/auth/logout")
    r = await client.post("/api/auth/login", json={"username": "nuevo", "password": "clave-nueva-123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "technical"


async def test_validaciones_de_usuario(client):
    await login(client, "jefe")
    assert (await client.post("/api/users", json={"username": "x", "password": "corta"})).status_code == 400
    assert (await client.post("/api/users", json={"username": "x", "role": "root", "password": "clave-larga-123"})).status_code == 400
    assert (await client.post("/api/users", json={"username": "TECNICO", "password": "clave-larga-123"})).status_code == 409


async def test_no_se_puede_quedar_sin_admin(client):
    await login(client, "jefe")
    users = (await client.get("/api/users")).json()["users"]
    jid = next(u["id"] for u in users if u["username"] == "jefe")
    assert (await client.patch(f"/api/users/{jid}", json={"role": "technical"})).status_code == 409
    assert (await client.patch(f"/api/users/{jid}", json={"active": False})).status_code == 409


async def test_la_contrasena_no_se_guarda_en_texto_plano(client):
    async with client.session_factory() as db:
        from app.models.user import User
        u = (await db.execute(select(User).where(User.username == "tecnico"))).scalar_one()
        assert PASSWORDS["tecnico"] not in u.password_hash
        assert u.password_hash.startswith("scrypt$")


# ------------------------------------------------------------- auditoria

async def test_auditoria_registra_el_usuario_real(client):
    from app.core.security import current_username
    from app.services.audit_service import add_audit

    token = current_username.set("tecnico")
    try:
        async with client.session_factory() as db:
            await add_audit(db, action="PRUEBA", target_id=DEVICE_ID)
            row = (await db.execute(select(AuditLog).where(AuditLog.action == "PRUEBA"))).scalar_one()
            assert row.username == "tecnico"
    finally:
        current_username.reset(token)
