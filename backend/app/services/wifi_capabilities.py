def unwrap(v):
    if isinstance(v, dict):
        return v.get("_value")
    return v


def walk(obj, prefix=""):
    result = []

    if not isinstance(obj, dict):
        return result

    for key, value in obj.items():

        if str(key).startswith("_"):
            continue

        path = f"{prefix}.{key}" if prefix else str(key)

        if not isinstance(value, dict):
            continue

        if value.get("_object") is False:
            if value.get("_writable") is True:

                result.append({
                    "path": path,
                    "type": value.get("_type"),
                })

        else:
            result.extend(
                walk(value, path)
            )

    return result


def wifi_capabilities(device):

    wlan = (
        device
        .get("InternetGatewayDevice", {})
        .get("LANDevice", {})
        .get("1", {})
        .get("WLANConfiguration", {})
    )

    result = []

    for index, obj in wlan.items():

        if not str(index).isdigit():
            continue

        standard = unwrap(
            obj.get("Standard")
        )

        rfband = unwrap(
            obj.get("RFBand")
        )

        if str(rfband) == "1":
            band = "5 GHz"
        elif str(rfband) == "0":
            band = "2.4 GHz"
        elif standard and (
            "a" in str(standard).lower()
            or "ac" in str(standard).lower()
        ):
            band = "5 GHz"
        else:
            band = "2.4 GHz"

        writable = walk(obj)

        # Nunca devolvemos valores de claves.
        for item in writable:
            lower = item["path"].lower()

            if any(x in lower for x in (
                "password",
                "passphrase",
                "presharedkey",
                "wepkey",
            )):
                item["secret"] = True

        result.append({
            "index": int(index),
            "band": band,
            "enabled": unwrap(
                obj.get("Enable")
            ),
            "ssid": unwrap(
                obj.get("SSID")
            ),
            "standard": standard,
            "channel": unwrap(
                obj.get("Channel")
            ),
            "current_channel": unwrap(
                obj.get("ChannelsInUse")
            ),
            "hidden": unwrap(
                obj.get("X_CT-COM_SSIDHide")
            ),
            "writable_parameters": writable,
        })

    return sorted(
        result,
        key=lambda x: x["index"]
    )
