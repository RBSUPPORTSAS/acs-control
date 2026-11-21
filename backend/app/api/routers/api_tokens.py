"""Tokens API para agentes y scripts (solo admin, desde su sesion)."""

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_session
from app.core.api_tokens import new_token, token_hash
from app.core.database import get_db
from app.models.api_token import ApiToken
from app.models.user import ROLES, User
from app.services.audit_service import add_audit

router = APIRouter(dependencies=[Depends(require_admin_session)])

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")


class TokenIn(BaseModel):
    name: str
    role: str = "technical"
    # Dias de vigencia; null = sin vencimiento.
    expires_days: int | None = 90


def as_dict(t: ApiToken) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "role": t.role,
        "prefix": t.prefix,
        "created_by": t.created_by,
        "created_at": t.created_at,
        "expires_at": t.expires_at,
        "last_used_at": t.last_used_at,
        "revoked": t.revoked,
    }


@router.get("/api/tokens", summary="Listar tokens API")
async def list_tokens(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ApiToken).order_by(ApiToken.created_at.desc()))).scalars()
    return {"tokens": [as_dict(t) for t in rows]}


@router.post("/api/tokens", status_code=201, summary="Crear token API (se muestra una sola vez)")
async def create_token(body: TokenIn, user: User = Depends(require_admin_session), db: AsyncSession = Depends(get_db)):
    name = body.name.strip()
    if not NAME.match(name):
        raise HTTPException(400, "Nombre de 2 a 64 caracteres: letras, números, guion, punto o guion bajo")
    if body.role not in ROLES:
        raise HTTPException(400, f"Rol no válido ({', '.join(ROLES)})")
    if body.expires_days is not None and not 1 <= body.expires_days <= 3650:
        raise HTTPException(400, "Vigencia de 1 a 3650 días, o sin vencimiento")
    if await db.scalar(select(ApiToken).where(ApiToken.name == name)):
        raise HTTPException(409, f'Ya existe un token llamado "{name}"')

    token = new_token()
    row = ApiToken(
        name=name,
        role=body.role,
        prefix=token[:10],
        token_hash=token_hash(token),
        created_by=user.username,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=body.expires_days)) if body.expires_days else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    await add_audit(db, action="TOKEN_API_CREAR", target_id=name, after={"rol": row.role, "vence": str(row.expires_at)},
                    result="CONFIRMADO", target_type="SISTEMA")

    return {**as_dict(row), "token": token}


@router.delete("/api/tokens/{token_id}", summary="Revocar token API")
async def revoke_token(token_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(ApiToken, token_id)
    if not row:
        raise HTTPException(404, "Token no encontrado")
    if not row.revoked:
        row.revoked = True
        await db.commit()
        await add_audit(db, action="TOKEN_API_REVOCAR", target_id=row.name, before={"rol": row.role},
                        result="CONFIRMADO", target_type="SISTEMA")
    return as_dict(row)
