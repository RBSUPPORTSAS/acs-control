import httpx
from urllib.parse import quote

from app.core.config import settings


class GenieACSClient:

    def __init__(self):
        self.base_url = settings.genieacs_nbi_url.rstrip("/")
        self.timeout = settings.genieacs_timeout

    async def get_devices(self, limit=100):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(
                f"{self.base_url}/devices/",
                params={"limit": limit},
            )
            r.raise_for_status()
            return r.json()

    async def get_device(self, device_id):
        devices = await self.get_devices(limit=10000)

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


genieacs = GenieACSClient()
