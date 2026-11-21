"""Dependencias de autenticacion y permisos."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import SESSION_COOKIE, current_username, read_session
from app.models.user import NETWORK_ROLES, User


# Tokens API: "Authorization: Bearer acs_..." (agentes, scripts). auto_error
# en False: sin cabecera se sigue con la sesion del navegador. Declararlo
# aqui hace que la documentacion (OpenAPI) muestre el esquema Bearer.
bearer = HTTPBearer(auto_error=False, description="Token API de ACS-Control (acs_...)")

TOKEN_TOUCH_SECONDS = 60


async def _token_user(request: Request, db: AsyncSession, credentials) -> User | None:
    from datetime import datetime, timezone

    from app.core.api_tokens import find_token

    row = await find_token(db, credentials.credentials)
    if not row:
        raise HTTPException(status_code=401, detail="Token API no válido, vencido o revocado")

    now = datetime.now(timezone.utc)
    last = row.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last is None or (now - last).total_seconds() >= TOKEN_TOUCH_SECONDS:
        row.last_used_at = now
        await db.commit()

    # Usuario en memoria (no se guarda): mismo rol que el token; la
    # auditoria lo registra como "api:<nombre>".
    user = User(id=-row.id, username=f"api:{row.name}", full_name=f"Token API {row.name}", role=row.role, active=True)
    request.state.user_role = user.role
    request.state.auth = "token"
    current_username.set(user.username)
    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return await _token_user(request, db, credentials)

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


async def require_network(
    user: User = Depends(require_user),
) -> User:
    """WAN, CATV, seguridad y etiquetas: admin y technical (no el rol wifi)."""

    if user.role not in NETWORK_ROLES:
        raise HTTPException(status_code=403, detail="Su perfil solo permite ver la ONU y cambiar el Wi-Fi")

    return user


def is_admin(user: User | None) -> bool:
    return bool(user and user.role == "admin")


async def require_admin_session(
    request: Request,
    user: User = Depends(require_admin),
) -> User:
    """Admin con sesion de navegador: los tokens no crean ni revocan tokens."""

    if getattr(request.state, "auth", None) == "token":
        raise HTTPException(status_code=403, detail="Los tokens se administran desde una sesión de admin, no con otro token")

    return user
