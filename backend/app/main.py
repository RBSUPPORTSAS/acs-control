"""Punto de entrada de la API de ACS Control.

Cada grupo de endpoints vive en app/api/routers/.
"""

from fastapi import FastAPI

from app.api.routers import system
from app.api.routers import devices
from app.api.routers import wifi
from app.api.routers import catv
from app.api.routers import audit
from app.api.routers import wan
from app.api.routers import security


app = FastAPI(
    title="ACS Control API",
    description="Capa de administración amigable para GenieACS",
    version="0.1.0",
)

app.include_router(system.router)
app.include_router(devices.router)
app.include_router(wifi.router)
app.include_router(catv.router)
app.include_router(audit.router)
app.include_router(wan.router)
app.include_router(security.router)
