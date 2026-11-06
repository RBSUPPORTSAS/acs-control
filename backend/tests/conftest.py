"""Entorno de pruebas: SQLite en memoria, Redis simulado y GenieACS simulado."""

import os

GENIE_URL = "http://10.99.0.5:7557"

os.environ.update(
    {
        "ACS_CONTROL_ENV_FILE": "/dev/null",
        "APP_SECRET_KEY": "pruebas",
        "GENIEACS_NBI_URL": GENIE_URL,
        "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:1/db",
        "REDIS_HOST": "127.0.0.1",
        "REDIS_PORT": "1",
    }
)

import fakeredis  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import BigInteger  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


# Tipos de PostgreSQL traducidos a SQLite solo para las pruebas.
@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(BigInteger, "sqlite")
def _bigint_sqlite(type_, compiler, **kw):
    return "INTEGER"


from app.core import redis_client  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models import audit as _audit  # noqa: E402,F401
from app.services.genieacs import genieacs  # noqa: E402

DEVICE_ID = "4C46D1-V2802ACT-SN0001"

DEVICE = {
    "_id": DEVICE_ID,
    "_deviceId": {"_Manufacturer": "VSOL", "_OUI": "4C46D1", "_ProductClass": "V2802ACT", "_SerialNumber": "SN0001"},
    "_lastInform": "2026-11-06T00:00:00.000Z",
    "InternetGatewayDevice": {
        "ManagementServer": {
            "URL": {"_value": GENIE_URL.replace("7557", "7547"), "_writable": True},
            "ConnectionRequestPassword": {"_value": "secreto-cr", "_writable": True},
        },
        "DeviceInfo": {"SoftwareVersion": {"_value": "V2.1.00"}},
    },
}

PASSWORDS = {"jefe": "clave-admin-123", "tecnico": "clave-tecnico-123"}


@pytest.fixture
async def client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(redis_client, "_client", fakeredis.aioredis.FakeRedis(decode_responses=True))

    async def fake_get_devices(limit=100, projection=None):
        return [DEVICE]

    async def fake_get_device(device_id):
        if device_id == "falla":
            request = httpx.Request("GET", f"{GENIE_URL}/devices/?query=x")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError(
                f"Server error '500' for url '{GENIE_URL}/devices/?query=x'",
                request=request,
                response=response,
            )
        return DEVICE if device_id == DEVICE_ID else None

    monkeypatch.setattr(genieacs, "get_devices", fake_get_devices)
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)

    async with Session() as db:
        db.add(User(username="jefe", role="admin", password_hash=hash_password(PASSWORDS["jefe"])))
        db.add(User(username="tecnico", role="technical", password_hash=hash_password(PASSWORDS["tecnico"])))
        await db.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.session_factory = Session
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


async def login(client, username):
    r = await client.post("/api/auth/login", json={"username": username, "password": PASSWORDS[username]})
    assert r.status_code == 200, r.text
    return r
