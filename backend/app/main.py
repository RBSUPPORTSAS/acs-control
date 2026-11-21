"""Punto de entrada de la API de ACS Control.

Cada grupo de endpoints vive en app/api/routers/.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.deps import require_admin, require_network, require_user
from app.core.config import settings
from app.core.redaction import RedactGenieForNonAdmin

from app.api.routers import auth
from app.api.routers import system
from app.api.routers import branding
from app.api.routers import devices
from app.api.routers import wifi
from app.api.routers import catv
from app.api.routers import audit
from app.api.routers import wan
from app.api.routers import security
from app.api.routers import users
from app.api.routers import tags
from app.api.routers import api_tokens
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


API_DESCRIPTION = """
API de ACS-Control: gestión de ONUs sobre GenieACS (inventario, WAN, Wi-Fi,
CATV, seguridad, equipos conectados, etiquetas y auditoría).

**Autenticación.** Todas las rutas exigen sesión o token, salvo el inicio de
sesión y el logo del operador. Para agentes y scripts use un token API
(Sistema → Tokens API, solo admin):

    Authorization: Bearer acs_...

El token tiene un rol (admin, technical o wifi) con los mismos permisos que un
usuario de ese rol, y lo que haga queda en la auditoría como `api:<nombre>`.

**Lecturas.** Los datos vienen de GenieACS. Si están incompletos o viejos,
`POST /api/devices/{id}/refresh` los pide a la ONU y
`GET /api/devices/{id}/refresh` informa el avance.

**Escrituras.** Cambian la configuración de una ONU real (WAN, Wi-Fi, CATV,
seguridad): confirme con una persona antes de usarlas desde un agente.

Los `{device_id}` de GenieACS llevan caracteres como `%` o `-`: van
codificados en la URL (encodeURIComponent).
"""

# Documentacion y especificacion propias, protegidas (ver mas abajo).
app = FastAPI(
    title="ACS Control API",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(RedactGenieForNonAdmin)

# Publico: inicio/cierre de sesion. /, /api/health y /api/system/config
# controlan sus permisos dentro del router system.
app.include_router(auth.router, tags=["Sesión"])
app.include_router(system.router, tags=["Sistema"])
# Logo del operador: ver es publico (login); cambiarlo, solo admin.
app.include_router(branding.router, tags=["Marca"])

# Cualquier usuario con sesion (admin, technical y wifi): inventario,
# informacion de la ONU, equipos conectados y Wi-Fi. Las etiquetas exigen
# require_network dentro del router de dispositivos.
logged_in = [Depends(require_user)]
app.include_router(devices.router, dependencies=logged_in, tags=["Dispositivos"])
app.include_router(tags.router, dependencies=logged_in, tags=["Etiquetas"])
app.include_router(wifi.router, dependencies=logged_in, tags=["Wi-Fi"])

# WAN, CATV y seguridad: admin y technical.
network = [Depends(require_network)]
app.include_router(catv.router, dependencies=network, tags=["CATV"])
app.include_router(wan.router, dependencies=network, tags=["WAN"])
app.include_router(security.router, dependencies=network, tags=["Seguridad"])

# Solo admin.
admin_only = [Depends(require_admin)]
app.include_router(audit.router, dependencies=admin_only, tags=["Auditoría"])
app.include_router(users.router, dependencies=admin_only, tags=["Usuarios"])

# Tokens API: admin desde su sesion (un token no crea otros tokens).
app.include_router(api_tokens.router, tags=["Tokens API"])


# Documentacion de la API: solo con sesion o token (antes /docs y
# /openapi.json eran publicos). Bajo /api/ para que pase por el mismo proxy.
@app.get("/api/openapi.json", include_in_schema=False, dependencies=logged_in)
async def openapi_json():
    from fastapi.responses import JSONResponse

    schema = app.openapi()
    # Todas las rutas aceptan el token Bearer (o la cookie de sesion).
    schema.setdefault("security", [{"HTTPBearer": []}])
    return JSONResponse(schema)


@app.get("/api/docs", include_in_schema=False, dependencies=logged_in)
async def swagger_ui():
    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(openapi_url="/api/openapi.json", title="ACS Control API")
