"""Filtro de salida: oculta la direccion del servidor GenieACS a usuarios no admin.

Muchos mensajes de error incluyen el error tecnico del cliente HTTP, que trae la
URL completa del NBI. En lugar de revisar cada mensaje, se limpia la respuesta
completa para el rol technical. Tambien cubre fugas futuras.
"""

import json
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings

PLACEHOLDER = "GenieACS"


def secret_strings() -> list[str]:
    url = str(settings.genieacs_nbi_url).rstrip("/")
    parts = urlsplit(url)
    values = {url, url + "/"}

    if parts.netloc:
        values.add(parts.netloc)
    if parts.hostname:
        values.add(parts.hostname)

    # Las mas largas primero para no dejar restos.
    return sorted((v for v in values if v), key=len, reverse=True)


def redact_text(text: str) -> str:
    for value in secret_strings():
        text = text.replace(value, PLACEHOLDER)
        # Tambien la forma escapada dentro de JSON (por ejemplo "\\/").
        text = text.replace(json.dumps(value)[1:-1], PLACEHOLDER)
    return text


class RedactGenieForNonAdmin(BaseHTTPMiddleware):

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        role = getattr(request.state, "user_role", None)
        content_type = response.headers.get("content-type", "")

        if role == "admin" or not request.url.path.startswith("/api/"):
            return response

        if "json" not in content_type and "text" not in content_type:
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        clean = redact_text(body.decode("utf-8", errors="replace")).encode()

        new = Response(content=clean, status_code=response.status_code)
        new.raw_headers = [
            (k, v) for k, v in response.raw_headers if k.lower() != b"content-length"
        ] + [(b"content-length", str(len(clean)).encode())]
        return new
