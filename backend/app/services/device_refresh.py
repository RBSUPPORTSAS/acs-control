"""Lectura de datos de la ONU bajo demanda.

ACS-Control no depende de scripts propios instalados en GenieACS: pide a la
ONU las ramas que usa con la tarea estandar ``refreshObject`` del NBI, que
existe en cualquier GenieACS. Es de solo lectura: no cambia nada en la ONU.

Reglas:

- Solo se piden las ramas que ACS-Control lee. Nunca la raiz completa:
  arrastraria ``DeviceConfig.ConfigFile``, que trae la configuracion del
  equipo con contrasenas en texto plano.
- Solo se piden ramas que GenieACS ya sabe que existen: pedir una rama
  inexistente genera un fault (9005). La primera lectura descubre tambien
  los nombres de las ramas raiz, asi que una segunda ronda pide las que
  faltaban (por ejemplo ``X_HW_Security``).
- Si la ONU corta la lectura (sesion terminada, timeout), se borra la tarea
  fallida para que GenieACS no la reintente en cada reporte, y la proxima
  lectura de esa ONU se hace por partes mas pequenas (modo liviano).
"""

from datetime import datetime, timezone

from app.core.redis_client import get_redis
from app.services.genieacs import genieacs


# Ramas que ACS-Control lee, por modelo de datos.
BRANCHES = {
    "InternetGatewayDevice": (
        "DeviceInfo",
        "WANDevice",
        "LANDevice",
        "X_CATV_RFDevice",
        "X_HW_Security",
        # Gateway de la ruta por defecto (MONU xPON) y 802.1p (RT9607C).
        "Layer3Forwarding",
        "Layer2Bridging",
        # CATV Realtek y seguridad Realtek IGD / X_CMCC.
        "X_RZ_Catv",
        "Firewall",
        "X_CMCC_Security",
        # CDTC FD714 (GS1-R850, GS3-R851): ACL de servicios y CATV.
        "X_CT-COM_Security",
        "X_CMS_Services",
    ),
    "Device": (
        "DeviceInfo",
        "WiFi",
        "Hosts",
        "IP",
        "PPP",
    ),
}

# Ramas grandes que en modo liviano se piden por sub-objetos.
SPLITTABLE = {"WANDevice", "LANDevice", "WiFi", "Hosts", "IP", "PPP"}

# Una rama se considera completa si al menos este porcentaje de sus
# parametros tiene valor.
COMPLETE_RATIO = 0.95

TASK_NAME = "refreshObject"

LIGHT_KEY = "acs:refresh_light:{}"
LIGHT_TTL = 7 * 24 * 3600

# Partes que cortan la sesion aun en modo liviano (p. ej. LANDevice.1.Hosts
# en XPON+2GE+2WIFI+USB+CATV fw V2.1.00-230825): se dejan de pedir por un
# tiempo para que no arrastren al resto de las lecturas.
SKIP_KEY = "acs:refresh_skip:{}"
SKIP_TTL = 7 * 24 * 3600
SESSION_CUT = {"session_terminated", "timeout", "session_timeout"}

# Firmwares que ya se sabe que cortan sesiones largas: se leen por partes
# desde el primer intento y se omiten las partes que nunca responden.
# Validado en XPON+2GE+2WIFI+USB+CATV 1234574546B0A4AC0 (2026-11-11).
KNOWN_HEAVY = {
    "V2.1.00-230825": ("InternetGatewayDevice.LANDevice.1.Hosts",),
}


def known_heavy(device):
    """(leer por partes, partes que se omiten) segun el firmware."""

    root = data_root(device)
    version = (
        ((device or {}).get(root or "", {}).get("DeviceInfo") or {})
        .get("SoftwareVersion", {}) or {}
    )
    version = version.get("_value") if isinstance(version, dict) else None
    skip = KNOWN_HEAVY.get(version)

    return (skip is not None), tuple(skip or ())


def _parse_ts(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def data_root(device):
    for root in ("InternetGatewayDevice", "Device"):
        node = device.get(root)
        if isinstance(node, dict) and any(not k.startswith("_") for k in node):
            return root
    return None


def _children(node):
    return {
        k: v
        for k, v in node.items()
        if not k.startswith("_") and isinstance(v, dict)
    }


def _is_param(node):
    return node.get("_object") is False or "_value" in node


def branch_state(node):
    """Cuantos parametros tiene la rama, cuantos con valor y el mas reciente."""

    params = values = 0
    unwalked = 0
    newest = None
    stack = [node]

    while stack:
        current = stack.pop()
        for child in _children(current).values():
            if _is_param(child):
                params += 1
                if "_value" in child:
                    values += 1
                    ts = _parse_ts(child.get("_timestamp"))
                    if ts and (newest is None or ts > newest):
                        newest = ts
            else:
                if not child.get("_timestamp"):
                    unwalked += 1
                stack.append(child)

    return {
        # El _timestamp de un objeto indica cuando se leyeron sus nombres.
        # Sin el, GenieACS nunca recorrio esa rama. Basta un sub-objeto
        # sin recorrer: un preset que declara rutas sueltas (p. ej. la IP
        # de la WAN en el inform) crea la rama con solo esos valores y
        # parece completa (CDTC FD714 en el GenieACS 10.15.50.6).
        "structure": bool(node.get("_timestamp")) and unwalked == 0,
        "params": params,
        "values": values,
        "newest": newest,
    }


def _without(node, prefix, skip):
    """Copia superficial de la rama sin las partes omitidas (rutas completas)."""

    inside = [x[len(prefix) + 1:] for x in skip if x.startswith(prefix + ".")]
    if not inside:
        return node

    def strip(current, rels):
        out = dict(current)
        for rel in rels:
            head, _, tail = rel.partition(".")
            if head not in out:
                continue
            if tail:
                if isinstance(out[head], dict):
                    out[head] = strip(out[head], [tail])
            else:
                out.pop(head, None)
        return out

    return strip(node, inside)


def _incomplete(state):
    if not state["structure"] or state["params"] == 0:
        return True
    return state["values"] / state["params"] < COMPLETE_RATIO


def _light_parts(root, name, node):
    """Sub-objetos de una rama grande, para leerla por partes."""

    parts = []
    for key, child in _children(node).items():
        if _is_param(child):
            continue
        if key.isdigit():
            for sub, subnode in _children(child).items():
                if not _is_param(subnode):
                    parts.append(f"{root}.{name}.{key}.{sub}")
        else:
            parts.append(f"{root}.{name}.{key}")
    return parts


def plan_refresh(device, max_age=None, light=False, now=None, skip=()):
    """Ramas que hay que pedir a la ONU.

    max_age: segundos. None ignora la antiguedad (solo datos incompletos);
    0 pide todas las ramas aunque esten al dia.
    """

    root = data_root(device)
    if not root:
        return []

    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    tree = device[root]
    plan = []

    def needs(state):
        # max_age=0 (forzar) relee siempre, aunque los relojes de ACS-Control
        # y GenieACS no coincidan y las fechas parezcan del futuro.
        stale = max_age is not None and (
            max_age == 0
            or state["newest"] is None
            or now - state["newest"] >= max_age
        )
        return _incomplete(state) or stale

    for name in BRANCHES[root]:
        node = tree.get(name)
        if not isinstance(node, dict):
            continue

        prefix = f"{root}.{name}"
        if not needs(branch_state(_without(node, prefix, skip))):
            continue

        parts = _light_parts(root, name, node) if light and name in SPLITTABLE else []

        if parts:
            # Solo las partes que faltan o estan viejas (y no omitidas).
            chosen = []
            for part in parts:
                if any(part == x or part.startswith(x + ".") for x in skip):
                    continue
                sub = tree
                for key in part.split(".")[1:]:
                    sub = sub.get(key, {}) if isinstance(sub, dict) else {}
                if not isinstance(sub, dict) or needs(branch_state(_without(sub, part, skip))):
                    chosen.append(part)
            plan.extend(chosen)
        else:
            plan.append(prefix)

    return plan


def data_status(device, max_age=None, now=None):
    """Resumen para la interfaz: si los datos estan completos y al dia."""

    root = data_root(device)
    if not root:
        return {"complete": False, "stale": True, "missing": [], "updated_at": None}

    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    tree = device[root]
    missing = []
    stale = False
    oldest = None

    for name in BRANCHES[root]:
        node = tree.get(name)
        if not isinstance(node, dict):
            continue
        state = branch_state(_without(node, f"{root}.{name}", known_heavy(device)[1]))
        if _incomplete(state):
            missing.append(name)
        # La fecha que se muestra es la de la rama mas vieja: asi
        # "actualizado hace X" nunca es mas optimista que los datos.
        if state["newest"] is None:
            stale = max_age is not None
        elif oldest is None or state["newest"] < oldest:
            oldest = state["newest"]

    if max_age is not None and oldest is not None and now - oldest >= max_age:
        stale = True
    newest = oldest

    return {
        "complete": not missing,
        "stale": bool(stale),
        "missing": missing,
        "updated_at": (
            datetime.fromtimestamp(newest, timezone.utc).isoformat().replace("+00:00", "Z")
            if newest
            else None
        ),
    }


def _pending_refreshes(tasks):
    return [t for t in tasks if t.get("name") == TASK_NAME]


async def request_refresh(device_id, device, max_age=None, connection_request=True):
    """Encola la lectura de las ramas que hacen falta.

    No duplica: una rama que ya tiene una lectura pendiente (ella o una rama
    que la contiene) no se vuelve a pedir. Las demas si: si la ONU corto la
    sesion, quedan pendientes las otras ramas, y las partes del modo liviano
    deben encolarse igual.
    """

    pending = _pending_refreshes(await genieacs.get_tasks(device_id))
    pending_names = [str(t.get("objectName") or "").rstrip(".") for t in pending]

    def covered(branch):
        return any(branch == p or branch.startswith(p + ".") for p in pending_names)

    heavy, heavy_skip = known_heavy(device)
    light = heavy or bool(await get_redis().exists(LIGHT_KEY.format(device_id)))
    skipped = [str(x) for x in (await get_redis().smembers(SKIP_KEY.format(device_id)) or ())]
    skipped += list(heavy_skip)

    def is_skipped(branch):
        return any(branch == x or branch.startswith(x + ".") for x in skipped)

    branches = [
        b for b in plan_refresh(device, max_age=max_age, light=light, skip=tuple(skipped))
        if not covered(b) and not is_skipped(b)
    ]

    if not branches:
        if pending:
            return {
                "status": "pending",
                "branches": [t.get("objectName") for t in pending],
            }
        return {"status": "fresh", "branches": [], "light": light}

    # Se encolan todas y solo la ultima despierta a la ONU: GenieACS procesa
    # en esa misma sesion todas las tareas pendientes, en orden.
    answered = False
    for i, branch in enumerate(branches):
        last = i == len(branches) - 1
        code = await genieacs.post_task(
            device_id,
            {"name": TASK_NAME, "objectName": branch},
            connection_request=connection_request and last,
        )
        if last and code == 200:
            answered = True

    return {
        "status": "done" if answered else "queued",
        "branches": branches,
        "light": light,
    }


async def refresh_status(device_id):
    """Estado de las lecturas pendientes. Limpia las que fallaron."""

    pending = _pending_refreshes(await genieacs.get_tasks(device_id))
    by_id = {t.get("_id"): t for t in pending}
    failed = []

    if pending:
        for fault in await genieacs.get_faults(device_id):
            channel = fault.get("channel") or ""
            task_id = channel[5:] if channel.startswith("task_") else None
            task = by_id.get(task_id)
            if not task:
                continue

            # Sin esto GenieACS reintentaria la lectura en cada reporte.
            await genieacs.delete_task(task_id)
            await genieacs.delete_fault(fault.get("_id"))
            by_id.pop(task_id, None)

            failed.append(
                {
                    "branch": task.get("objectName"),
                    "code": fault.get("code"),
                    "message": (fault.get("message") or "")[:300],
                }
            )

    if failed:
        redis = get_redis()
        was_light = bool(await redis.exists(LIGHT_KEY.format(device_id)))
        await redis.set(LIGHT_KEY.format(device_id), "1", ex=LIGHT_TTL)

        # Si ya se leia por partes y una parte vuelve a cortar la sesion,
        # esa parte no se pide mas por un tiempo.
        if was_light:
            key = SKIP_KEY.format(device_id)
            for item in failed:
                if item.get("branch") and str(item.get("code") or "") in SESSION_CUT:
                    await redis.sadd(key, item["branch"])
            await redis.expire(key, SKIP_TTL)

    return {
        "pending": len(by_id),
        "branches": [t.get("objectName") for t in by_id.values()],
        "failed": failed,
        "light": bool(await get_redis().exists(LIGHT_KEY.format(device_id))),
    }
