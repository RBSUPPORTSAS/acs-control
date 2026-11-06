"""Dependencias de autenticacion y permisos."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import SESSION_COOKIE, current_username, read_session
from app.models.user import User


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    session = await read_session(token)

    if not session:
        return None

    user = await db.get(User, session.get("user_id"))

    if not user or not user.active:
        return None

    # Visible para el filtro de salida y para la auditoria.
    request.state.user_role = user.role
    current_username.set(user.username)
    return user


async def require_user(
    user: User | None = Depends(get_optional_user),
) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Sesión no iniciada o expirada")

    return user


async def require_admin(
    user: User = Depends(require_user),
) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")

    return user


def is_admin(user: User | None) -> bool:
    return bool(user and user.role == "admin")
