import httpx
from urllib.parse import quote

from app.core.config import settings


async def create_pppoe(device_id, data):

    vlan = int(data["vlan"])
    priority = int(data.get("priority", 0))

    name = f"ACS_INTERNET_R_VID_{vlan}"

    bindings = ",".join(
        data.get("bindings", [])
    )

    values = [
        ["Enable", False, "xsd:boolean"],
        ["ConnectionType", "IP_Routed", "xsd:string"],
        ["NATEnabled", bool(data.get("nat", True)), "xsd:boolean"],

        ["Username", data["username"], "xsd:string"],
        ["Password", data["password"], "xsd:string"],

        ["MaxMRUSize", int(data.get("mtu", 1492)), "xsd:unsignedInt"],

        ["X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        ["X_CT-COM_VLANIDMark", vlan, "xsd:unsignedInt"],
        ["X_CT-COM_802-1pMark", priority, "xsd:unsignedInt"],

        ["X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        ["X_CT-COM_ServiceList", "INTERNET", "xsd:string"],

        ["Name", name, "xsd:string"],
    ]

    if bindings:
        values.append([
            "X_CT-COM_LanInterface",
            bindings,
            "xsd:string"
        ])

    task = {
        "name": "addObject",
        "objectName": (
            "InternetGatewayDevice."
            "WANDevice.1."
            "WANConnectionDevice.1."
            "WANPPPConnection"
        ),
        "parameterValues": values,
    }

    did = quote(device_id, safe="")

    async with httpx.AsyncClient(timeout=30) as client:

        r = await client.post(
            f"{settings.genieacs_nbi_url}/devices/{did}/tasks",
            params={
                "connection_request": "",
                "timeout": 10000,
            },
            json=task,
        )

        r.raise_for_status()

        return {
            "status": r.status_code,
            "task": r.json(),
            "name": name,
        }


async def create_dhcp(device_id, data):
    vlan = int(data["vlan"])
    priority = int(data.get("priority", 0))
    mtu = int(data.get("mtu", 1500))

    name = f"ACS_INTERNET_DHCP_R_VID_{vlan}"
    bindings = ",".join(data.get("bindings", []))

    values = [
        ["Enable", False, "xsd:boolean"],
        ["ConnectionType", "IP_Routed", "xsd:string"],
        ["AddressingType", "DHCP", "xsd:string"],
        ["NATEnabled", bool(data.get("nat", True)), "xsd:boolean"],
        ["MaxMTUSize", mtu, "xsd:unsignedInt"],

        ["X_CT-COM_VLANMode", 1, "xsd:unsignedInt"],
        ["X_CT-COM_VLANIDMark", vlan, "xsd:unsignedInt"],
        ["X_CT-COM_802-1pMark", priority, "xsd:unsignedInt"],

        ["X_CT-COM_IPMode", 1, "xsd:unsignedInt"],
        ["X_CT-COM_ServiceList", "INTERNET", "xsd:string"],
        ["Name", name, "xsd:string"],
    ]

    if bindings:
        values.append([
            "X_CT-COM_LanInterface",
            bindings,
            "xsd:string"
        ])

    task = {
        "name": "addObject",
        "objectName": (
            "InternetGatewayDevice."
            "WANDevice.1."
            "WANConnectionDevice.1."
            "WANIPConnection"
        ),
        "parameterValues": values,
    }

    from urllib.parse import quote
    did = quote(device_id, safe="")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.genieacs_nbi_url}/devices/{did}/tasks",
            params={
                "connection_request": "",
                "timeout": 10000,
            },
            json=task,
        )

        r.raise_for_status()

        return {
            "status": r.status_code,
            "task": r.json(),
            "name": name,
        }
