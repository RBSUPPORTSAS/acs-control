"""Bloqueo de escrituras en modelos de ONU no certificados."""

from fastapi import HTTPException

from app.services.wan_driver import certification


def ensure_certified(device):
    """Modelos no certificados: ACS-Control solo muestra sus datos."""

    info = certification(device) if device else None

    if info and not info["certified"]:
        raise HTTPException(status_code=403, detail=info["message"])
