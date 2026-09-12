import asyncio

from app.services.x_ctcom_wan_builder import (
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
        for k in obj
        if str(k).isdigit()
    }


def connection_numbers(device, wcd, container):
    try:
        obj = (
            device["InternetGatewayDevice"]
            ["WANDevice"]["1"]
            ["WANConnectionDevice"][str(wcd)]
            [container]
        )
    except Exception:
        return set()

    if not isinstance(obj, dict):
        return set()

    return {
        int(k)
        for k in obj
        if str(k).isdigit()
    }


def find_empty_wcd(device):
    for wcd in sorted(wcd_numbers(device)):
        ppp = connection_numbers(
            device,
            wcd,
            "WANPPPConnection",
        )

        ip = connection_numbers(
            device,
            wcd,
            "WANIPConnection",
        )

        if not ppp and not ip:
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


async def wait_new_connection(
    client,
    device_id,
    wcd,
    container,
    previous,
):
    for _ in range(10):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)

        if not device:
            continue

        current = connection_numbers(
            device,
            wcd,
            container,
        )

        new = current - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                f"Se detectaron varias instancias nuevas en {container}"
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
        previous,
    )

    if wcd is None:
        raise RuntimeError(
            "La ONU no confirmó el nuevo WANConnectionDevice"
        )

    return wcd, False


async def create_x_ctcom_pppoe(
    client,
    device_id,
    data,
):
    wcd, reused = await get_or_create_wcd(
        client,
        device_id,
    )

    # Configurar VLAN/802.1p del enlace.
    await client.set_parameter_values(
        device_id,
        build_link_values(wcd, data),
    )

    device = await client.get_device(device_id)

    previous = connection_numbers(
        device,
        wcd,
        "WANPPPConnection",
    )

    # Nunca crear otra PPP si ya existe una instancia.
    if previous:
        raise RuntimeError(
            f"WCD {wcd} ya contiene WANPPPConnection: "
            f"{sorted(previous)}"
        )

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    await client.add_object(
        device_id,
        f"{base}.WANPPPConnection",
    )

    instance = await wait_new_connection(
        client,
        device_id,
        wcd,
        "WANPPPConnection",
        previous,
    )

    if instance is None:
        raise RuntimeError(
            "La ONU no confirmó WANPPPConnection"
        )

    config = build_pppoe_values(
        wcd,
        instance,
        data,
    )

    await client.set_parameter_values(
        device_id,
        config["parameter_values"],
    )

    return {
        "status": 200,
        "driver": "x_ctcom_wan",
        "wcd": wcd,
        "instance": instance,
        "reused_wcd": reused,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }


async def create_x_ctcom_dhcp(
    client,
    device_id,
    data,
):
    wcd, reused = await get_or_create_wcd(
        client,
        device_id,
    )

    await client.set_parameter_values(
        device_id,
        build_link_values(wcd, data),
    )

    device = await client.get_device(device_id)

    previous = connection_numbers(
        device,
        wcd,
        "WANIPConnection",
    )

    if previous:
        raise RuntimeError(
            f"WCD {wcd} ya contiene WANIPConnection: "
            f"{sorted(previous)}"
        )

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    await client.add_object(
        device_id,
        f"{base}.WANIPConnection",
    )

    instance = await wait_new_connection(
        client,
        device_id,
        wcd,
        "WANIPConnection",
        previous,
    )

    if instance is None:
        raise RuntimeError(
            "La ONU no confirmó WANIPConnection"
        )

    config = build_dhcp_values(
        wcd,
        instance,
        data,
    )

    await client.set_parameter_values(
        device_id,
        config["parameter_values"],
    )

    return {
        "status": 200,
        "driver": "x_ctcom_wan",
        "wcd": wcd,
        "instance": instance,
        "reused_wcd": reused,
        "name": config["name"],
        "vlan": int(data["vlan"]),
    }
