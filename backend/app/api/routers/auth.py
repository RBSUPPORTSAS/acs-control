"""Inicio y cierre de sesion."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user, require_user
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
from app.services.audit_service import log_event


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
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    username = payload.username.strip()

    if await login_locked(username):
        await log_event(
            db, "SESION_BLOQUEADA", "SESION", username, request,
            result="FALLIDO", message="Login bloqueado por intentos fallidos",
            username=username,
        )
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
        motivo = (
            "Usuario inexistente" if not user
            else "Usuario inactivo" if not user.active
            else "Contraseña incorrecta"
        )
        await log_event(
            db, "SESION_FALLIDA", "SESION", username, request,
            result="FALLIDO", message=motivo, username=username,
        )
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    await clear_login_failures(username)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    await log_event(
        db, "SESION_INICIO", "SESION", user.username, request,
        after={"rol": user.role}, username=user.username,
    )

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
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if user:
        await log_event(
            db, "SESION_CIERRE", "SESION", user.username, request,
            username=user.username,
        )

    await delete_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/api/auth/me")
async def me(user: User = Depends(require_user)):
    return {"user": user_public(user)}
