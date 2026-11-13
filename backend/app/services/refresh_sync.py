"""Lectura en segundo plano de ONUs nuevas.

Cada ``REFRESH_SYNC_MINUTES`` revisa las ONUs registradas en las ultimas
``REFRESH_SYNC_NEW_HOURS`` horas y, si les faltan datos, encola su lectura
(``refreshObject``, solo lectura). No despierta a la ONU: las tareas se
procesan en su siguiente reporte periodico, asi no hay rafagas de
connection requests.

Solo encola para ONUs que reportaron en la ultima hora: a una ONU apagada no
se le dejan tareas esperando en GenieACS. Se vuelve a revisar en las rondas
siguientes, mientras siga dentro de la ventana de ONUs nuevas.

Funciona con cualquier GenieACS: solo usa el NBI estandar. Con varios
procesos de ACS-Control, un candado en Redis evita que corran a la vez.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.redis_client import get_redis
from app.services import device_refresh
from app.services.genieacs import genieacs

log = logging.getLogger("acs.refresh_sync")

LOCK_KEY = "acs:refresh_sync:lock"
DONE_KEY = "acs:refresh_sync:done:{}"
TRY_KEY = "acs:refresh_sync:try:{}"

DONE_TTL = 7 * 24 * 3600
TRY_TTL = 30 * 60

# Solo ONUs que reportaron hace menos de esto.
ONLINE_SECONDS = 3600


async def sync_new_devices(now=None):
    """Una ronda. Devuelve un resumen (usado por las pruebas y el log)."""

    redis = get_redis()
    interval = max(1, settings.refresh_sync_minutes) * 60

    if not await redis.set(LOCK_KEY, "1", nx=True, ex=max(30, interval - 10)):
        return {"skipped": "lock"}

    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=settings.refresh_sync_new_hours)

    online_since = now - timedelta(seconds=ONLINE_SECONDS)

    devices = await genieacs.find_devices(
        {
            "_registered": {"$gt": since.isoformat().replace("+00:00", "Z")},
            "_lastInform": {"$gt": online_since.isoformat().replace("+00:00", "Z")},
        },
        projection=["_id", "_registered", "_lastInform"],
    )
    devices.sort(key=lambda d: d.get("_registered") or "", reverse=True)

    summary = {"checked": 0, "queued": [], "complete": [], "waiting": []}

    for item in devices:
        if len(summary["queued"]) >= settings.refresh_sync_batch:
            break

        device_id = item.get("_id")
        if not device_id or await redis.exists(DONE_KEY.format(device_id)):
            continue

        summary["checked"] += 1

        if await redis.exists(TRY_KEY.format(device_id)):
            # Ya se encolo: solo revisar si fallo (y limpiar el fault).
            state = await device_refresh.refresh_status(device_id)
            if state["pending"]:
                summary["waiting"].append(device_id)
                continue
            await redis.delete(TRY_KEY.format(device_id))

        device = await genieacs.get_device(device_id)
        if not device:
            continue

        result = await device_refresh.request_refresh(
            device_id,
            device,
            max_age=None,
            connection_request=False,
        )

        if result["status"] == "fresh":
            await redis.set(DONE_KEY.format(device_id), "1", ex=DONE_TTL)
            summary["complete"].append(device_id)
        else:
            await redis.set(TRY_KEY.format(device_id), "1", ex=TRY_TTL)
            summary["queued"].append(device_id)

    return summary


async def run_forever():
    interval = settings.refresh_sync_minutes * 60
    log.info("Lectura de ONUs nuevas cada %s min", settings.refresh_sync_minutes)

    while True:
        try:
            summary = await sync_new_devices()
            if summary.get("queued"):
                log.info("ONUs nuevas en lectura: %s", ", ".join(summary["queued"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Fallo la revision de ONUs nuevas")

        await asyncio.sleep(interval)
