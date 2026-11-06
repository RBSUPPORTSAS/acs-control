"""Inicio y cierre de sesion."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    SESSION_COOKIE,
    clear_login_failures,
    create_session,
    delete_session,
    login_locked,
    register_login_failure,
    session_ttl,
    verify_password,
)
from app.models.user import User


router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }


@router.post("/api/auth/login")
async def login(
    payload: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    username = payload.username.strip()

    if await login_locked(username):
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos fallidos. Intente de nuevo en 15 minutos.",
        )

    user = (
        await db.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
    ).scalar_one_or_none()

    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        await register_login_failure(username)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    await clear_login_failures(username)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = await create_session(user.id)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=session_ttl(),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )

    return {"ok": True, "user": user_public(user)}


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    await delete_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/api/auth/me")
async def me(user: User = Depends(require_user)):
    return {"user": user_public(user)}
