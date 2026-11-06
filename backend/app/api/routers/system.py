"""Estado del servicio y configuracion publica.

Movido desde app/main.py sin cambios de comportamiento (fase 1 del refactor).
"""

from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
import redis.asyncio as redis
from app.core.config import settings
from app.core.database import engine
from app.services.genieacs import genieacs

from app.api.deps import get_optional_user, is_admin, require_admin
from app.models.user import User


router = APIRouter()


@router.get("/")
async def root():
    return {
        "name": "ACS Control",
        "status": "running",
        "mode": "read-only",
    }


@router.get("/api/health")
async def health(user: User | None = Depends(get_optional_user)):

    result = {
        "api": True,
        "postgresql": False,
        "redis": False,
        "genieacs": False,
    }

    # PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        result["postgresql"] = True

    except Exception as exc:
        result["postgresql_error"] = str(exc)

    # Redis
    try:
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )

        result["redis"] = bool(await r.ping())
        await r.aclose()

    except Exception as exc:
        result["redis_error"] = str(exc)

    # GenieACS
    try:
        await genieacs.get_devices(limit=1, projection=["_id"])
        result["genieacs"] = True

    except Exception as exc:
        result["genieacs_error"] = str(exc)

    result["healthy"] = all(
        [
            result["api"],
            result["postgresql"],
            result["redis"],
            result["genieacs"],
        ]
    )

    status_code = 200 if result["healthy"] else 503

    # Los mensajes de error pueden incluir direcciones internas:
    # solo se muestran a admin.
    if not is_admin(user):
        result = {
            key: value
            for key, value in result.items()
            if not key.endswith("_error")
        }

    return JSONResponse(
        status_code=status_code,
        content=result,
    )


# ACS_SYSTEM_CONFIG_17A2
@router.get("/api/system/config")
async def system_configuration(_: User = Depends(require_admin)):

    # No exponemos APP_SECRET_KEY,
    # DATABASE_URL ni ninguna credencial.
    return {
        "app_name": settings.app_name,
        "genieacs_nbi_url":
            str(settings.genieacs_nbi_url),
    }
