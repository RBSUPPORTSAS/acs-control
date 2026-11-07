"""Compatibilidad: la logica vive en app.services.vendor_wan."""

from app.services.vendor_wan import (  # noqa: F401
    create_vendor_wan,
    lanbind_values,
    translate,
)


async def create_huawei_wan(client, device_id, data, mode="DHCP"):
    return await create_vendor_wan(client, device_id, data, mode=mode, vendor="huawei")
