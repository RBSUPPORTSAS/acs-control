"""Errores de presets de GenieACS que dejan a una ONU sin gestion.

GenieACS corre sus presets (bootstrap, inform, default...) al inicio de cada
sesion. Si uno termina en fault, GenieACS lo reintenta en las sesiones
siguientes y la sesion se corta antes de procesar las tareas: las lecturas y
cambios que pide ACS-Control quedan en cola y nunca se ejecutan.

Casos vistos:
- bootstrap tras un reset de fabrica de una VSOL V2802ACT fw V2.1.00-260205:
  relee todo el arbol y falla en WLANConfiguration.1.PossibleChannels (9002).
- inform en ZTE F6600P / HG102WT: la ONU rechaza PeriodicInformTime (9003) y
  con el el usuario/clave de connection request.

"Destrabar" borra esos faults (GenieACS deja de reintentar) y despierta la
ONU para que procese la cola. No cambia nada en la ONU ni en los presets.
"""

from app.services.genieacs import genieacs

WAKE_PARAM = {
    "InternetGatewayDevice": "InternetGatewayDevice.DeviceInfo.UpTime",
    "Device": "Device.DeviceInfo.UpTime",
}

EXPLAIN = {
    "bootstrap": (
        "GenieACS no pudo volver a leer la ONU después de un reset o de "
        "conectarse por primera vez"
    ),
    "inform": (
        "GenieACS no pudo aplicar su configuración de gestión (usuario y clave "
        "para despertar la ONU, intervalo de reporte)"
    ),
    "default": "GenieACS no pudo hacer su lectura periódica de la ONU",
}


def _param(fault):
    detail = fault.get("detail") or {}
    names = [x.get("parameterName") for x in (detail.get("setParameterValuesFault") or []) if x.get("parameterName")]
    if names:
        return names[0]
    message = str(fault.get("message") or "")
    if message.startswith(("InternetGatewayDevice.", "Device.")) and " " not in message:
        return message
    return None


def preset_faults(faults):
    """Faults de presets (no de tareas) con un texto para el tecnico."""

    out = []

    for fault in faults or []:
        channel = str(fault.get("channel") or "")
        if not channel or channel.startswith("task_"):
            continue

        param = _param(fault)
        text = EXPLAIN.get(channel, f"Falló el preset «{channel}» de GenieACS")
        if param:
            text += f" (la ONU no acepta {'.'.join(param.split('.')[-3:])})"

        out.append({
            "id": fault.get("_id"),
            "channel": channel,
            "code": fault.get("code"),
            "parameter": param,
            "message": text,
            "timestamp": fault.get("timestamp"),
            "retries": fault.get("retries"),
        })

    return out


async def health(device_id):
    faults = preset_faults(await genieacs.get_faults(device_id))
    pending = len(await genieacs.get_tasks(device_id))

    return {
        "blocked": bool(faults),
        "faults": [{k: v for k, v in f.items() if k != "id"} for f in faults],
        "pending_tasks": pending,
    }


async def unblock(device_id, device):
    """Borra los faults de presets y despierta la ONU."""

    faults = preset_faults(await genieacs.get_faults(device_id))

    for fault in faults:
        await genieacs.delete_fault(fault["id"])

    root = "Device" if isinstance((device or {}).get("Device"), dict) and not (device or {}).get("InternetGatewayDevice") else "InternetGatewayDevice"
    task = {"name": "getParameterValues", "parameterNames": [WAKE_PARAM[root]]}
    code = await genieacs.post_task(device_id, task, connection_request=True, wait_ms=30000)

    # Si la ONU no respondio, no dejar esta lectura de prueba en la cola.
    if code != 200:
        for pending in await genieacs.get_tasks(device_id):
            if pending.get("name") == task["name"] and pending.get("parameterNames") == task["parameterNames"]:
                await genieacs.delete_task(pending["_id"])

    after = await health(device_id)

    return {
        "cleared": [f["channel"] for f in faults],
        "answered": code == 200,
        **after,
    }
