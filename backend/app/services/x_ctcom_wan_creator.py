import asyncio

from app.services.x_ctcom_wan_builder import (
    build_enable_values,
    build_link_values,
    build_pppoe_values,
    build_dhcp_values,
)


async def finish_connection(client, device_id, wcd, container, instance, data):
    """Ultimos pasos, comunes a todas las WAN nuevas.

    1. Reescribe la VLAN del enlace (WCD). En algunas ONUs (p. ej.
       HG102DWT) X_CT-COM_VLANMode de la conexion y el Mode del enlace son
       el mismo campo: escribir VLANMode=1 en la conexion deja el enlace en
       Mode 1 y la VLAN no se etiqueta. El enlace se escribe al final para
       que quede en Mode 2, como las WAN que funcionan. En VSOL son campos
       independientes y esto no cambia nada.
       Antes se relee el enlace desde la ONU: GenieACS no envia un valor
       que su cache ya tiene, y su cache aun dice Mode 2 aunque la ONU lo
       haya cambiado sola.
    2. Enciende la conexion. Se crea apagada para configurarla completa
       antes de que levante.
    """

    await client.post_task(
        device_id,
        {
            "name": "refreshObject",
            "objectName": (
                "InternetGatewayDevice.WANDevice.1."
                f"WANConnectionDevice.{wcd}.X_CT-COM_WANGponLinkConfig"
            ),
        },
        connection_request=True,
        wait_ms=10000,
    )

    await client.set_parameter_values(
        device_id,
        build_link_values(wcd, data),
    )

    await client.set_parameter_values(
        device_id,
        build_enable_values(wcd, container, instance),
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

    await finish_connection(
        client, device_id, wcd, "WANPPPConnection", instance, data,
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
    mode="DHCP",
):
    mode = str(mode).upper()

    if mode not in ("DHCP", "STATIC"):
        raise ValueError("Tipo valido: DHCP o STATIC")

    # Validar antes de crear objetos en la ONU.
    build_dhcp_values(0, 0, data, mode=mode)

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
        mode=mode,
    )

    await client.set_parameter_values(
        device_id,
        config["parameter_values"],
    )

    await finish_connection(
        client, device_id, wcd, "WANIPConnection", instance, data,
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
