"""Contrasenas, sesiones y usuario actual.

- Contrasenas: scrypt de la libreria estandar (sin dependencias nuevas).
- Sesiones: token aleatorio en una cookie HttpOnly; el estado vive en Redis,
  asi una sesion se puede revocar al instante.
"""

import base64
import hashlib
import hmac
import json
import secrets
from contextvars import ContextVar

from app.core.config import settings
from app.core.redis_client import get_redis


SESSION_COOKIE = "acs_session"
SESSION_PREFIX = "acs:session:"
LOGIN_FAIL_PREFIX = "acs:login_fail:"

MIN_PASSWORD_LENGTH = 10
MAX_LOGIN_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


# Usuario de la peticion en curso (lo usa la auditoria).
current_username: ContextVar[str | None] = ContextVar(
    "current_username",
    default=None,
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(base64.b64decode(digest)),
        )
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except Exception:
        return False


def validate_password(password: str) -> str | None:
    """Devuelve un mensaje de error o None si la contrasena es aceptable."""

    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"

    return None


def session_ttl() -> int:
    return settings.session_hours * 3600


async def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    await get_redis().set(
        SESSION_PREFIX + token,
        json.dumps({"user_id": user_id}),
        ex=session_ttl(),
    )
    return token


async def read_session(token: str) -> dict | None:
    if not token:
        return None

    key = SESSION_PREFIX + token
    raw = await get_redis().get(key)

    if not raw:
        return None

    # Expiracion deslizante: cada uso renueva la sesion.
    await get_redis().expire(key, session_ttl())
    return json.loads(raw)


async def delete_session(token: str):
    if token:
        await get_redis().delete(SESSION_PREFIX + token)


async def delete_user_sessions(user_id: int):
    """Cierra todas las sesiones de un usuario (al desactivarlo o cambiar su rol)."""

    r = get_redis()
    async for key in r.scan_iter(match=SESSION_PREFIX + "*"):
        raw = await r.get(key)
        if raw and json.loads(raw).get("user_id") == user_id:
            await r.delete(key)


async def login_locked(username: str) -> bool:
    count = await get_redis().get(LOGIN_FAIL_PREFIX + username.lower())
    return int(count or 0) >= MAX_LOGIN_FAILURES


async def register_login_failure(username: str):
    key = LOGIN_FAIL_PREFIX + username.lower()
    r = get_redis()
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, LOGIN_LOCK_SECONDS)


async def clear_login_failures(username: str):
    await get_redis().delete(LOGIN_FAIL_PREFIX + username.lower())
