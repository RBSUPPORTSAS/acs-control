def value(obj, key):
    v = obj.get(key)

    if isinstance(v, dict):
        return v.get("_value")

    return v


def inventory(device):

    lan = (
        device
        .get("InternetGatewayDevice", {})
        .get("LANDevice", {})
        .get("1", {})
    )

    result = []

    # Ethernet
    eth = lan.get(
        "LANEthernetInterfaceConfig",
        {}
    )

    for index, obj in eth.items():

        if not str(index).isdigit():
            continue

        result.append({
            "type": "lan",
            "index": int(index),
            "label": f"LAN {index}",
            "enabled": value(obj, "Enable"),
            "path": (
                "InternetGatewayDevice."
                "LANDevice.1."
                f"LANEthernetInterfaceConfig.{index}"
            )
        })

    # Wi-Fi
    wifi = lan.get(
        "WLANConfiguration",
        {}
    )

    for index, obj in wifi.items():

        if not str(index).isdigit():
            continue

        standard = value(
            obj,
            "Standard"
        )

        band = (
            "5 GHz"
            if standard and "a" in str(standard)
            else "2.4 GHz"
        )

        ssid = value(
            obj,
            "SSID"
        )

        result.append({
            "type": "wifi",
            "index": int(index),
            "band": band,
            "ssid": ssid,
            "enabled": value(obj, "Enable"),
            "label": (
                f"{band} · {ssid}"
                if ssid
                else f"{band} · WLAN {index}"
            ),
            "path": (
                "InternetGatewayDevice."
                "LANDevice.1."
                f"WLANConfiguration.{index}"
            )
        })

    return result
