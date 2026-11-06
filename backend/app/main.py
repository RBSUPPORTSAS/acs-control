"""Punto de entrada de la API de ACS Control.

Cada grupo de endpoints vive en app/api/routers/.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.deps import require_admin, require_user
from app.core.config import settings
from app.core.redaction import RedactGenieForNonAdmin

from app.api.routers import auth
from app.api.routers import system
from app.api.routers import devices
from app.api.routers import wifi
from app.api.routers import catv
from app.api.routers import audit
from app.api.routers import wan
from app.api.routers import security
from app.api.routers import users
from app.services import refresh_sync


@asynccontextmanager
async def lifespan(app):
    # Lectura en segundo plano de ONUs nuevas (REFRESH_SYNC_MINUTES=0 la apaga).
    task = None
    if settings.refresh_sync_minutes > 0:
        task = asyncio.create_task(refresh_sync.run_forever())

    yield

    if task:
        task.cancel()


app = FastAPI(
    title="ACS Control API",
    description="Capa de administración amigable para GenieACS",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RedactGenieForNonAdmin)

# Publico: inicio/cierre de sesion. /, /api/health y /api/system/config
# controlan sus permisos dentro del router system.
app.include_router(auth.router)
app.include_router(system.router)

# Cualquier usuario con sesion (admin y technical): gestion de ONUs.
logged_in = [Depends(require_user)]
app.include_router(devices.router, dependencies=logged_in)
app.include_router(wifi.router, dependencies=logged_in)
app.include_router(catv.router, dependencies=logged_in)
app.include_router(wan.router, dependencies=logged_in)
app.include_router(security.router, dependencies=logged_in)

# Solo admin.
admin_only = [Depends(require_admin)]
app.include_router(audit.router, dependencies=admin_only)
app.include_router(users.router, dependencies=admin_only)
