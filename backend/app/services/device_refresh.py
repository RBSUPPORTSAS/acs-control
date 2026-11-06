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
                stack.append(child)

    return {
        # El _timestamp de un objeto indica cuando se leyeron sus nombres.
        # Sin el, GenieACS nunca recorrio esa rama.
        "structure": bool(node.get("_timestamp")),
        "params": params,
        "values": values,
        "newest": newest,
    }


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


def plan_refresh(device, max_age=None, light=False, now=None):
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

    for name in BRANCHES[root]:
        node = tree.get(name)
        if not isinstance(node, dict):
            continue

        state = branch_state(node)
        # max_age=0 (forzar) relee siempre, aunque los relojes de ACS-Control
        # y GenieACS no coincidan y las fechas parezcan del futuro.
        stale = max_age is not None and (
            max_age == 0
            or state["newest"] is None
            or now - state["newest"] >= max_age
        )

        if not (_incomplete(state) or stale):
            continue

        parts = _light_parts(root, name, node) if light and name in SPLITTABLE else []
        plan.extend(parts or [f"{root}.{name}"])

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
        state = branch_state(node)
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

    No duplica: si ya hay lecturas pendientes para la ONU, no agrega mas.
    """

    pending = _pending_refreshes(await genieacs.get_tasks(device_id))
    if pending:
        return {
            "status": "pending",
            "branches": [t.get("objectName") for t in pending],
        }

    light = bool(await get_redis().exists(LIGHT_KEY.format(device_id)))
    branches = plan_refresh(device, max_age=max_age, light=light)

    if not branches:
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
        await get_redis().set(LIGHT_KEY.format(device_id), "1", ex=LIGHT_TTL)

    return {
        "pending": len(by_id),
        "branches": [t.get("objectName") for t in by_id.values()],
        "failed": failed,
        "light": bool(await get_redis().exists(LIGHT_KEY.format(device_id))),
    }
