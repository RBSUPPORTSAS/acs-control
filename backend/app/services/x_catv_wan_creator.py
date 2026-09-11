import asyncio

from app.services.x_catv_wan_builder import (
    build_link_values,
    build_pppoe_values,
    build_dhcp_values,
)


def wcd_numbers(device):
    try:
        obj = (
            device["InternetGatewayDevice"]
            ["WANDevice"]["1"]
            ["WANConnectionDevice"]
        )
    except Exception:
        return set()

    return {
        int(k)
        for k in obj.keys()
        if str(k).isdigit()
    }


def ppp_numbers(device, wcd):
    try:
        obj = (
            device["InternetGatewayDevice"]
            ["WANDevice"]["1"]
            ["WANConnectionDevice"][str(wcd)]
            ["WANPPPConnection"]
        )
    except Exception:
        return set()

    return {
        int(k)
        for k in obj.keys()
        if str(k).isdigit()
    }


def ip_numbers(device, wcd):
    try:
        obj = (
            device["InternetGatewayDevice"]
            ["WANDevice"]["1"]
            ["WANConnectionDevice"][str(wcd)]
            ["WANIPConnection"]
        )
    except Exception:
        return set()

    return {
        int(k)
        for k in obj.keys()
        if str(k).isdigit()
    }


def find_empty_wcd(device):
    """
    Algunos equipos X_CATV mantienen WANConnectionDevice vacíos
    previamente creados. Los reutilizamos antes de crear otro.
    """
    for wcd in sorted(wcd_numbers(device)):
        if not ppp_numbers(device, wcd) and not ip_numbers(device, wcd):
            return wcd

    return None


async def wait_new_wcd(client, device_id, previous):
    for _ in range(10):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)

        if not device:
            continue

        new = wcd_numbers(device) - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                "Se detectaron varios WANConnectionDevice nuevos"
            )

    return None


async def wait_new_ppp(client, device_id, wcd, previous):
    for _ in range(10):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)

        if not device:
            continue

        new = ppp_numbers(device, wcd) - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                "Se detectaron varias WANPPPConnection nuevas"
            )

    return None


async def wait_new_ip(client, device_id, wcd, previous):
    for _ in range(10):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)

        if not device:
            continue

        new = ip_numbers(device, wcd) - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                "Se detectaron varias WANIPConnection nuevas"
            )

    return None


async def get_or_create_wcd(client, device_id):
    device = await client.get_device(device_id)

    if not device:
        raise RuntimeError("ONU no encontrada")

    empty = find_empty_wcd(device)

    if empty is not None:
        return empty, True

    previous = wcd_numbers(device)

    await client.add_object(
        device_id,
        "InternetGatewayDevice."
        "WANDevice.1.WANConnectionDevice"
    )

    wcd = await wait_new_wcd(
        client,
        device_id,
        previous
    )

    if wcd is None:
        raise RuntimeError(
            "La ONU no confirmó el nuevo WANConnectionDevice"
        )

    return wcd, False


async def create_x_catv_pppoe(client, device_id, data):
    wcd, reused = await get_or_create_wcd(
        client,
        device_id
    )

    # 1. Configurar enlace GPON/VLAN
    await client.set_parameter_values(
        device_id,
        build_link_values(wcd, data)
    )

    # 2. Crear PPPoE dentro del WCD
    device = await client.get_device(device_id)
    before_ppp = ppp_numbers(device, wcd)

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    await client.add_object(
        device_id,
        f"{base}.WANPPPConnection"
    )

    instance = await wait_new_ppp(
        client,
        device_id,
        wcd,
        before_ppp
    )

    if instance is None:
        raise RuntimeError(
            "La ONU no confirmó WANPPPConnection"
        )

    # 3. Configurar PPPoE, inicialmente apagada
    config = build_pppoe_values(
        wcd,
        instance,
        data
    )

    await client.set_parameter_values(
        device_id,
        config["parameter_values"]
    )

    return {
        "status": 200,
        "driver": "x_catv_wan",
        "wcd": wcd,
        "instance": instance,
        "reused_wcd": reused,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }


async def create_x_catv_dhcp(client, device_id, data):
    wcd, reused = await get_or_create_wcd(
        client,
        device_id
    )

    # 1. Configurar enlace GPON/VLAN
    await client.set_parameter_values(
        device_id,
        build_link_values(wcd, data)
    )

    # 2. Crear WANIPConnection
    device = await client.get_device(device_id)
    before_ip = ip_numbers(device, wcd)

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    await client.add_object(
        device_id,
        f"{base}.WANIPConnection"
    )

    instance = await wait_new_ip(
        client,
        device_id,
        wcd,
        before_ip
    )

    if instance is None:
        raise RuntimeError(
            "La ONU no confirmó WANIPConnection"
        )

    # 3. Configurar DHCP, inicialmente apagada
    config = build_dhcp_values(
        wcd,
        instance,
        data
    )

    await client.set_parameter_values(
        device_id,
        config["parameter_values"]
    )

    return {
        "status": 200,
        "driver": "x_catv_wan",
        "wcd": wcd,
        "instance": instance,
        "reused_wcd": reused,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }
