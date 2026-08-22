import asyncio

from app.services.vsol_wan_builder import (
    build_vsol_ip,
    build_vsol_wanip,
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


async def wait_new_wcd(client, device_id, previous):
    for _ in range(8):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)
        current = wcd_numbers(device)

        new = current - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                "Se detectaron varios WCD nuevos simultáneamente"
            )

    return None


async def wait_new_ip(client, device_id, wcd, previous):
    for _ in range(8):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)
        current = ip_numbers(device, wcd)

        new = current - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                "Se detectaron varias WANIP nuevas"
            )

    return None


async def create_vsol_ip(client, device_id, data, state):
    device = await client.get_device(device_id)

    before_wcd = wcd_numbers(device)

    # PASO 1: nuevo WANConnectionDevice
    await client.add_object(
        device_id,
        "InternetGatewayDevice."
        "WANDevice.1.WANConnectionDevice"
    )

    wcd = await wait_new_wcd(
        client,
        device_id,
        before_wcd
    )

    if wcd is None:
        raise RuntimeError(
            "VSOL no confirmó el nuevo WANConnectionDevice"
        )

    state["wcd"] = wcd

    common = build_vsol_ip(wcd, data)

    # PASO 2: configurar enlace GPON/VLAN
    await client.set_parameter_values(
        device_id,
        common["link_values"]
    )

    device = await client.get_device(device_id)
    before_ip = ip_numbers(device, wcd)

    # PASO 3: crear WANIPConnection dentro del nuevo WCD
    await client.add_object(
        device_id,
        f'{common["base"]}.WANIPConnection'
    )

    instance = await wait_new_ip(
        client,
        device_id,
        wcd,
        before_ip
    )

    if instance is None:
        raise RuntimeError(
            "VSOL no confirmó WANIPConnection"
        )

    state["instance"] = instance

    wan_base = (
        f'{common["base"]}.'
        f'WANIPConnection.{instance}'
    )

    # PASO 4: apagar inmediatamente
    await client.set_parameter_values(
        device_id,
        [[
            f"{wan_base}.Enable",
            False,
            "xsd:boolean"
        ]]
    )

    # PASO 5: configurar WAN completa
    config = build_vsol_wanip(
        wcd,
        instance,
        data
    )

    await client.set_parameter_values(
        device_id,
        config["parameter_values"]
    )

    return {
        "wcd": wcd,
        "instance": instance,
        "name": config["name"],
        "mode": config["mode"],
        "vlan": config["vlan"],
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


async def wait_new_ppp(client, device_id, wcd, previous):
    for _ in range(10):
        await asyncio.sleep(1)

        device = await client.get_device(device_id)
        current = ppp_numbers(device, wcd)

        new = current - previous

        if len(new) == 1:
            return next(iter(new))

        if len(new) > 1:
            raise RuntimeError(
                "Se detectaron varias WANPPPConnection nuevas"
            )

    return None


async def create_vsol_pppoe(client, device_id, data, state):
    from app.services.vsol_wan_builder import build_vsol_pppoe

    device = await client.get_device(device_id)
    before_wcd = wcd_numbers(device)

    # 1. Nuevo WANConnectionDevice exclusivo
    await client.add_object(
        device_id,
        "InternetGatewayDevice."
        "WANDevice.1.WANConnectionDevice"
    )

    wcd = await wait_new_wcd(
        client,
        device_id,
        before_wcd
    )

    if wcd is None:
        raise RuntimeError(
            "VSOL no confirmó WANConnectionDevice"
        )

    state["wcd"] = wcd

    # 2. Crear WANPPPConnection dentro del WCD nuevo
    device = await client.get_device(device_id)
    before_ppp = ppp_numbers(device, wcd)

    wcd_base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    await client.add_object(
        device_id,
        f"{wcd_base}.WANPPPConnection"
    )

    instance = await wait_new_ppp(
        client,
        device_id,
        wcd,
        before_ppp
    )

    if instance is None:
        raise RuntimeError(
            "VSOL no confirmó WANPPPConnection"
        )

    state["instance"] = instance

    config = build_vsol_pppoe(
        wcd,
        instance,
        data
    )

    # 3. Configurar enlace GPON/VLAN
    await client.set_parameter_values(
        device_id,
        config["link_values"]
    )

    # 4. Configurar PPPoE, siempre apagada
    await client.set_parameter_values(
        device_id,
        config["parameter_values"]
    )

    return {
        "wcd": wcd,
        "instance": instance,
        "name": config["name"],
        "vlan": config["vlan"],
    }
