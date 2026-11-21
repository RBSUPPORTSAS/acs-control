"""Tokens API: se muestran una sola vez y solo se guarda su SHA-256.

Formato: "acs_" + 43 caracteres aleatorios (256 bits). Con esa entropia un
hash rapido es suficiente (no hace falta scrypt como en las contrasenas).
"""

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.api_token import ApiToken

PREFIX = "acs_"


def new_token() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def find_token(db, token: str) -> ApiToken | None:
    if not token or not token.startswith(PREFIX) or len(token) > 128:
        return None

    row = await db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(token)))

    if not row or row.revoked:
        return None

    if row.expires_at is not None:
        expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return None

    return row
