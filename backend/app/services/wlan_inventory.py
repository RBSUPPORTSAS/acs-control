def unwrap(value):
    if isinstance(value, dict) and "_value" in value:
        return value.get("_value")
    return value


def read_wlan_interfaces(device):
    root = (
        device
        .get("InternetGatewayDevice", {})
        .get("LANDevice", {})
        .get("1", {})
        .get("WLANConfiguration", {})
    )

    result = []

    for index, obj in root.items():
        if not str(index).isdigit() or not isinstance(obj, dict):
            continue

        hints = {}

        for key, value in obj.items():
            if any(word.lower() in key.lower() for word in [
                "ssid",
                "band",
                "radio",
                "channel",
                "standard",
                "bssid",
                "enable",
                "name"
            ]):
                v = unwrap(value)

                if not isinstance(v, dict):
                    hints[key] = v

        result.append({
            "index": int(index),
            "enable": unwrap(obj.get("Enable")),
            "ssid": unwrap(obj.get("SSID")),
            "bssid": unwrap(obj.get("BSSID")),
            "channel": unwrap(obj.get("Channel")),
            "channels_in_use": unwrap(obj.get("ChannelsInUse")),
            "standard": unwrap(obj.get("Standard")),
            "hidden": unwrap(obj.get("X_CT-COM_SSIDHide")),
            "hints": hints,
        })

    return sorted(result, key=lambda x: x["index"])
