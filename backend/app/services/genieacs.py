import json

import httpx
from urllib.parse import quote

from app.core.config import settings


def _queued_on_timeout(func):
    """La tarea queda guardada en GenieACS antes de que la ONU responda.
    Si la ONU tarda mas que el cliente (p. ej. ~20-45 s por sesion en MONU
    xPON, X_CATV o X_CMCC), no es un error: queda en cola (202) y la
    confirmacion se hace leyendo despues, como en post_task."""

    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.TimeoutException:
            return {"http_status": 202, "response": None}

    return wrapper


class GenieACSClient:

    def __init__(self):
        self.base_url = settings.genieacs_nbi_url.rstrip("/")
        self.timeout = settings.genieacs_timeout

    async def get_devices(self, limit=100, projection=None):
        params = {"limit": limit}

        if projection:
            params["projection"] = ",".join(projection)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(
                f"{self.base_url}/devices/",
                params=params,
            )
            r.raise_for_status()
            return r.json()

    async def get_device(self, device_id):
        # Consulta solo esta ONU por su _id. Antes se descargaban todas las
        # ONUs completas (decenas de MB) para filtrar una en Python.
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(
                f"{self.base_url}/devices/",
                params={"query": json.dumps({"_id": device_id})},
            )
            r.raise_for_status()
            devices = r.json()

        for device in devices:
            if device.get("_id") == device_id:
                return device

        return None

    async def add_tag(self, device_id, tag):
        did = quote(device_id, safe="")
        tag = quote(tag, safe="")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/devices/{did}/tags/{tag}"
            )
            r.raise_for_status()

    async def remove_tag(self, device_id, tag):
        did = quote(device_id, safe="")
        tag = quote(tag, safe="")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.delete(
                f"{self.base_url}/devices/{did}/tags/{tag}"
            )
            r.raise_for_status()

    async def set_parameter_value(self, device_id, path, value, value_type="xsd:string"):
        from urllib.parse import quote

        did = quote(device_id, safe="")

        task = {
            "name": "setParameterValues",
            "parameterValues": [
                [path, value, value_type]
            ]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/devices/{did}/tasks",
                params={"connection_request": ""},
                json=task,
            )

            r.raise_for_status()

            try:
                body = r.json()
            except Exception:
                body = None

            return {
                "http_status": r.status_code,
                "response": body,
            }

    @_queued_on_timeout
    async def delete_object(self, device_id, object_name):
        from urllib.parse import quote

        did = quote(device_id, safe="")

        task = {
            "name": "deleteObject",
            "objectName": object_name
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/devices/{did}/tasks",
                params={"connection_request": ""},
                json=task,
            )

            r.raise_for_status()

            try:
                body = r.json()
            except Exception:
                body = None

            return {
                "http_status": r.status_code,
                "response": body,
            }

    @_queued_on_timeout
    async def set_parameter_values(self, device_id, values):
        from urllib.parse import quote

        did = quote(device_id, safe="")

        task = {
            "name": "setParameterValues",
            "parameterValues": values,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/devices/{did}/tasks",
                params={"connection_request": ""},
                json=task,
            )

            r.raise_for_status()

            return {"http_status": r.status_code}

    @_queued_on_timeout
    async def add_object(self, device_id, object_name):
        import httpx
        from urllib.parse import quote

        did = quote(device_id, safe="")

        task = {
            "name": "addObject",
            "objectName": object_name,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/devices/{did}/tasks",
                params={
                    "connection_request": "",
                    "timeout": 10000,
                },
                json=task,
            )

            r.raise_for_status()

            try:
                body = r.json()
            except Exception:
                body = None

            return {
                "http_status": r.status_code,
                "response": body,
            }

    # --- Tareas y faults (lectura bajo demanda) ---------------------------

    async def find_devices(self, query, projection=None, limit=500):
        params = {"query": json.dumps(query), "limit": limit}

        if projection:
            params["projection"] = ",".join(projection)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(f"{self.base_url}/devices/", params=params)
            r.raise_for_status()
            return r.json()

    async def get_tasks(self, device_id):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(
                f"{self.base_url}/tasks/",
                params={"query": json.dumps({"device": device_id})},
            )
            r.raise_for_status()
            return r.json()

    async def get_faults(self, device_id):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(
                f"{self.base_url}/faults/",
                params={"query": json.dumps({"device": device_id})},
            )
            r.raise_for_status()
            return r.json()

    async def post_task(self, device_id, task, connection_request=False, wait_ms=3000):
        """Encola una tarea. Con connection_request despierta a la ONU y
        espera hasta wait_ms: 200 = la ONU ya la proceso, 202 = en cola."""

        did = quote(device_id, safe="")
        params = {}

        if connection_request:
            params = {"connection_request": "", "timeout": wait_ms}

        # GenieACS puede mantener la peticion abierta hasta que la ONU
        # termine toda la sesion (en Huawei, decenas de segundos). La tarea
        # ya quedo guardada: si se agota la espera, se trata como "en cola"
        # y el estado se consulta despues.
        wait = (wait_ms / 1000 + 5) if connection_request else self.timeout

        try:
            async with httpx.AsyncClient(timeout=wait) as client:
                r = await client.post(
                    f"{self.base_url}/devices/{did}/tasks",
                    params=params,
                    json=task,
                )
                r.raise_for_status()
                return r.status_code

        except httpx.TimeoutException:
            if connection_request:
                return 202
            raise

    async def delete_task(self, task_id):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.delete(f"{self.base_url}/tasks/{quote(task_id, safe='')}")
            if r.status_code != 404:
                r.raise_for_status()

    async def delete_fault(self, fault_id):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.delete(f"{self.base_url}/faults/{quote(fault_id, safe='')}")
            if r.status_code != 404:
                r.raise_for_status()


genieacs = GenieACSClient()
