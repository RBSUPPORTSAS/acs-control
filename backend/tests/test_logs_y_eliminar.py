import json
from urllib.parse import quote

from sqlalchemy import select

from conftest import DEVICE_ID, PASSWORDS, login
from app.models.audit import AuditLog
from app.services.genieacs import genieacs

DID = quote(DEVICE_ID, safe="")


async def eventos(client, action=None):
    async with client.session_factory() as db:
        q = select(AuditLog).order_by(AuditLog.id)
        if action:
            q = q.where(AuditLog.action == action)
        return (await db.execute(q)).scalars().all()


# ------------------------------------------------------------------ sesiones

async def test_login_exitoso_queda_registrado_con_ip_y_navegador(client):
    await client.post(
        "/api/auth/login",
        json={"username": "tecnico", "password": PASSWORDS["tecnico"]},
        headers={"User-Agent": "Navegador-Prueba", "X-Forwarded-For": "192.0.2.50"},
    )
    (ev,) = await eventos(client, "SESION_INICIO")
    assert ev.username == "tecnico" and ev.target_type == "SESION" and ev.result == "OK"
    assert ev.after_data["ip"] == "192.0.2.50"
    assert ev.after_data["navegador"] == "Navegador-Prueba"
    assert ev.after_data["rol"] == "technical"


async def test_login_fallido_registra_usuario_intentado_y_motivo_sin_la_clave(client):
    await client.post("/api/auth/login", json={"username": "tecnico", "password": "clave-equivocada"})
    await client.post("/api/auth/login", json={"username": "fantasma", "password": "otra-clave-123"})
    evs = await eventos(client, "SESION_FALLIDA")
    assert [(e.username, e.message, e.result) for e in evs] == [
        ("tecnico", "Contraseña incorrecta", "FALLIDO"),
        ("fantasma", "Usuario inexistente", "FALLIDO"),
    ]
    todo = json.dumps([e.after_data for e in evs])
    assert "clave-equivocada" not in todo and "otra-clave-123" not in todo


async def test_bloqueo_por_intentos_queda_registrado(client):
    for _ in range(5):
        await client.post("/api/auth/login", json={"username": "tecnico", "password": "mala-clave-xx"})
    await client.post("/api/auth/login", json={"username": "tecnico", "password": PASSWORDS["tecnico"]})
    assert len(await eventos(client, "SESION_BLOQUEADA")) == 1


async def test_cierre_de_sesion_queda_registrado(client):
    await login(client, "tecnico")
    await client.post("/api/auth/logout")
    (ev,) = await eventos(client, "SESION_CIERRE")
    assert ev.username == "tecnico"


# --------------------------------------------------------------- usuarios

async def test_crear_editar_y_cambiar_clave_quedan_registrados_sin_la_clave(client):
    await login(client, "jefe")
    r = await client.post("/api/users", json={"username": "ana", "role": "technical", "password": "clave-ana-12345"})
    uid = r.json()["user"]["id"]
    await client.patch(f"/api/users/{uid}", json={"role": "admin"})
    await client.patch(f"/api/users/{uid}", json={"password": "clave-nueva-ana-1"})
    await client.patch(f"/api/users/{uid}", json={"active": False})

    evs = [e for e in await eventos(client) if e.target_type == "USUARIO"]
    assert [e.action for e in evs] == [
        "USUARIO_CREAR", "USUARIO_CAMBIAR_ROL", "USUARIO_CAMBIAR_CONTRASENA", "USUARIO_DESACTIVAR",
    ]
    assert all(e.username == "jefe" and e.target_id == "ana" for e in evs)
    assert evs[1].before_data["rol"] == "technical" and evs[1].after_data["rol"] == "admin"
    todo = json.dumps([[e.before_data, e.after_data] for e in evs])
    assert "clave-ana-12345" not in todo and "clave-nueva-ana-1" not in todo


async def test_etiquetas_de_onu_quedan_registradas(client, monkeypatch):
    async def ok(*args, **kwargs):
        return None
    monkeypatch.setattr(genieacs, "add_tag", ok)
    monkeypatch.setattr(genieacs, "remove_tag", ok)

    await login(client, "tecnico")
    assert (await client.post(f"/api/devices/{DID}/tags/cliente-vip")).status_code == 200
    assert (await client.delete(f"/api/devices/{DID}/tags/cliente-vip")).status_code == 200
    evs = [e for e in await eventos(client) if e.action.startswith("ETIQUETA_")]
    assert [(e.action, e.username, e.target_id) for e in evs] == [
        ("ETIQUETA_AGREGAR", "tecnico", DEVICE_ID),
        ("ETIQUETA_QUITAR", "tecnico", DEVICE_ID),
    ]


async def test_filtro_de_auditoria_por_tipo(client):
    await login(client, "jefe")
    await client.post("/api/users", json={"username": "luis", "password": "clave-luis-1234"})
    sesiones = (await client.get("/api/audit?tipo=SESION")).json()["audits"]
    usuarios = (await client.get("/api/audit?tipo=USUARIO")).json()["audits"]
    assert sesiones and all(a["target_type"] == "SESION" for a in sesiones)
    assert [a["action"] for a in usuarios] == ["USUARIO_CREAR"]


# --------------------------------------------------------- eliminar usuarios

async def ids(client):
    return {u["username"]: u["id"] for u in (await client.get("/api/users")).json()["users"]}


async def test_admin_elimina_un_usuario_y_su_sesion_se_corta(client):
    await login(client, "jefe")
    tec = type(client)(transport=client._transport, base_url="http://test")
    await tec.post("/api/auth/login", json={"username": "tecnico", "password": PASSWORDS["tecnico"]})
    assert (await tec.get("/api/devices")).status_code == 200

    r = await client.delete(f"/api/users/{(await ids(client))['tecnico']}")
    assert r.status_code == 200 and r.json()["deleted"] == "tecnico"
    assert "tecnico" not in await ids(client)
    assert (await tec.get("/api/devices")).status_code == 401
    r = await tec.post("/api/auth/login", json={"username": "tecnico", "password": PASSWORDS["tecnico"]})
    assert r.status_code == 401
    await tec.aclose()

    (ev,) = await eventos(client, "USUARIO_ELIMINAR")
    assert ev.username == "jefe" and ev.target_id == "tecnico" and ev.before_data["rol"] == "technical"


async def test_el_historial_del_usuario_eliminado_se_conserva(client):
    await login(client, "tecnico")
    await client.post("/api/auth/logout")
    await login(client, "jefe")
    await client.delete(f"/api/users/{(await ids(client))['tecnico']}")
    acciones = [e.action for e in await eventos(client) if e.username == "tecnico"]
    assert "SESION_INICIO" in acciones and "SESION_CIERRE" in acciones


async def test_no_puede_eliminarse_a_si_mismo(client):
    await login(client, "jefe")
    # Con otro admin activo, la regla del ultimo admin no aplica: solo bloquea la de si mismo.
    await client.post("/api/users", json={"username": "otro", "role": "admin", "password": "clave-otro-1234"})
    r = await client.delete(f"/api/users/{(await ids(client))['jefe']}")
    assert r.status_code == 409
    assert "propio usuario" in r.json()["detail"]


async def test_no_se_puede_eliminar_al_ultimo_admin(client):
    await login(client, "jefe")
    await client.post("/api/users", json={"username": "otro", "role": "admin", "password": "clave-otro-1234"})
    await client.post("/api/auth/logout")
    r = await client.post("/api/auth/login", json={"username": "otro", "password": "clave-otro-1234"})
    assert r.status_code == 200
    u = await ids(client)
    assert (await client.delete(f"/api/users/{u['jefe']}")).status_code == 200
    # "otro" es ahora el unico admin y no puede eliminarse a si mismo; nadie mas puede eliminarlo.
    assert (await client.delete(f"/api/users/{u['otro']}")).status_code == 409


async def test_technical_no_puede_eliminar_usuarios(client):
    await login(client, "tecnico")
    assert (await client.delete("/api/users/1")).status_code == 403


async def test_eliminar_usuario_inexistente(client):
    await login(client, "jefe")
    assert (await client.delete("/api/users/9999")).status_code == 404
