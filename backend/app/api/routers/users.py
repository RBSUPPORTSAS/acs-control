"""Gestion de usuarios (solo staff)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_staff
from app.core.database import get_db
from app.core.security import delete_user_sessions, hash_password, validate_password
from app.models.user import ROLES, User


router = APIRouter()


class UserCreate(BaseModel):
    username: str
    full_name: str | None = None
    role: str = "technical"
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = None


def user_row(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


async def active_staff_count(db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(User).where(User.role == "staff", User.active.is_(True))
        )
    ).scalar_one()


@router.get("/api/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_staff),
):
    rows = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return {"users": [user_row(u) for u in rows]}


@router.post("/api/users", status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_staff),
):
    username = payload.username.strip()

    if not username or len(username) > 64 or " " in username:
        raise HTTPException(400, "Usuario no válido (sin espacios, máximo 64 caracteres)")

    if payload.role not in ROLES:
        raise HTTPException(400, f"Rol no válido. Opciones: {', '.join(ROLES)}")

    error = validate_password(payload.password)
    if error:
        raise HTTPException(400, error)

    exists = (
        await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    ).scalar_one_or_none()

    if exists:
        raise HTTPException(409, "Ya existe un usuario con ese nombre")

    user = User(
        username=username,
        full_name=(payload.full_name or "").strip() or None,
        role=payload.role,
        password_hash=hash_password(payload.password),
        active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"user": user_row(user)}


@router.patch("/api/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    me: User = Depends(require_staff),
):
    user = await db.get(User, user_id)

    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    loses_staff = (
        user.role == "staff" and user.active
        and (payload.role not in (None, "staff") or payload.active is False)
    )

    if loses_staff and await active_staff_count(db) <= 1:
        raise HTTPException(409, "Debe quedar al menos un usuario staff activo")

    if payload.role is not None:
        if payload.role not in ROLES:
            raise HTTPException(400, f"Rol no válido. Opciones: {', '.join(ROLES)}")
        user.role = payload.role

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None

    if payload.active is not None:
        user.active = payload.active

    if payload.password:
        error = validate_password(payload.password)
        if error:
            raise HTTPException(400, error)
        user.password_hash = hash_password(payload.password)

    await db.commit()
    await db.refresh(user)

    # Cambios de rol, estado o contrasena cierran las sesiones abiertas del usuario
    # (salvo la propia sesion de quien cambia su nombre).
    if payload.role is not None or payload.active is not None or payload.password:
        if user.id != me.id or payload.active is False or payload.role not in (None, "staff"):
            await delete_user_sessions(user.id)

    return {"user": user_row(user)}
