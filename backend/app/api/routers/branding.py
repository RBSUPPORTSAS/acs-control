"""Marca del operador: logo que reemplaza la "A" del login y de la barra lateral.

GET es publico (el login lo necesita antes de iniciar sesion); subir y quitar
el logo es solo para admin. El logo se guarda en la base de datos, asi que
sobrevive a actualizaciones y reinstalaciones del frontend.
"""

import base64
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.app_setting import AppSetting
from app.models.user import User
from app.services.audit_service import add_audit

router = APIRouter()

LOGO_KEY = "logo"
MAX_BYTES = 512 * 1024

# Firma de cada formato aceptado (se valida el contenido, no solo el nombre).
FORMATS = {
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    "image/svg+xml": lambda b: b"<svg" in b[:2048].lower(),
}

# Un SVG puede llevar scripts: se sirve aislado (sin scripts ni recursos externos).
SAFE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-cache",
}


class LogoIn(BaseModel):
    content_type: str
    data: str  # base64, sin el prefijo "data:...;base64,"


def _etag(setting):
    return '"' + hashlib.sha1(setting.value.encode()).hexdigest()[:16] + '"'


@router.get("/api/branding")
async def branding(db: AsyncSession = Depends(get_db)):
    logo = await db.get(AppSetting, LOGO_KEY)
    return {
        "logo": bool(logo),
        "logo_version": _etag(logo).strip('"') if logo else None,
    }


@router.get("/api/branding/logo")
async def branding_logo(request: Request, db: AsyncSession = Depends(get_db)):
    logo = await db.get(AppSetting, LOGO_KEY)

    if not logo:
        raise HTTPException(status_code=404, detail="Sin logo")

    etag = _etag(logo)
    headers = {**SAFE_HEADERS, "ETag": etag}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return Response(
        content=base64.b64decode(logo.value),
        media_type=logo.content_type,
        headers=headers,
    )


@router.put("/api/branding/logo")
async def upload_logo(
    payload: LogoIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    content_type = payload.content_type.split(";")[0].strip().lower()

    if content_type not in FORMATS:
        raise HTTPException(400, "Formato no permitido. Use PNG, JPG, WEBP o SVG.")

    try:
        raw = base64.b64decode(payload.data, validate=True)
    except Exception:
        raise HTTPException(400, "El archivo no se pudo leer.")

    if not raw:
        raise HTTPException(400, "El archivo está vacío.")

    if len(raw) > MAX_BYTES:
        raise HTTPException(400, "El logo pesa más de 512 KB.")

    if not FORMATS[content_type](raw):
        raise HTTPException(400, "El contenido no corresponde al formato de la imagen.")

    logo = await db.get(AppSetting, LOGO_KEY)
    before = {"logo": bool(logo)}

    if logo:
        logo.content_type = content_type
        logo.value = base64.b64encode(raw).decode()
    else:
        logo = AppSetting(key=LOGO_KEY, content_type=content_type, value=base64.b64encode(raw).decode())
        db.add(logo)

    await db.commit()

    await add_audit(
        db,
        action="MARCA_LOGO",
        target_id="sistema",
        target_type="SISTEMA",
        before=before,
        after={"logo": True, "tipo": content_type, "bytes": len(raw)},
        result="CONFIRMADO",
        message="Logo del operador actualizado",
    )

    return {"ok": True, "logo": True, "logo_version": _etag(logo).strip('"')}


@router.delete("/api/branding/logo")
async def delete_logo(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    logo = await db.get(AppSetting, LOGO_KEY)

    if logo:
        await db.delete(logo)
        await db.commit()

        await add_audit(
            db,
            action="MARCA_LOGO",
            target_id="sistema",
        target_type="SISTEMA",
            before={"logo": True},
            after={"logo": False},
            result="CONFIRMADO",
            message="Logo del operador eliminado (vuelve el de ACS Control)",
        )

    return {"ok": True, "logo": False, "logo_version": None}
