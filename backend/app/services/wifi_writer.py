def unwrap(v):
    if isinstance(v, dict):
        return v.get("_value")
    return v


def wlan_object(device, index):
    try:
        return (
            device["InternetGatewayDevice"]
            ["LANDevice"]["1"]
            ["WLANConfiguration"][str(index)]
        )
    except Exception:
        return None


def wifi_state(device, index):
    obj = wlan_object(device, index)

    if not obj:
        return None

    return {
        "index": index,
        "enabled": unwrap(obj.get("Enable")),
        "ssid": unwrap(obj.get("SSID")),
        "auto_channel": unwrap(obj.get("AutoChannelEnable")),
        "channel": unwrap(obj.get("Channel")),
        "current_channel": unwrap(obj.get("ChannelsInUse")),
        "hidden": unwrap(obj.get("X_CT-COM_SSIDHide")),
    }


def build_wifi_changes(index, payload):
    if index not in (1, 5):
        raise ValueError(
            "Por ahora solo se permiten WLAN principales 1 y 5"
        )

    base = (
        "InternetGatewayDevice."
        "LANDevice.1."
        f"WLANConfiguration.{index}."
    )

    values = []
    requested = {}

    if "enabled" in payload:
        enabled = bool(payload["enabled"])

        values.append([
            base + "Enable",
            enabled,
            "xsd:boolean"
        ])

        requested["enabled"] = enabled

    if "ssid" in payload:
        ssid = str(payload["ssid"]).strip()

        if not ssid:
            raise ValueError("SSID no puede estar vacío")

        if len(ssid) > 32:
            raise ValueError("SSID máximo 32 caracteres")

        values.append([
            base + "SSID",
            ssid,
            "xsd:string"
        ])

        requested["ssid"] = ssid

    # Contraseña actual nunca se lee.
    if payload.get("password"):
        password = str(payload["password"])

        if len(password) < 8 or len(password) > 63:
            raise ValueError(
                "La contraseña Wi-Fi debe tener entre 8 y 63 caracteres"
            )

        values.append([
            base + "KeyPassphrase",
            password,
            "xsd:string"
        ])

    if "auto_channel" in payload:
        auto = bool(payload["auto_channel"])

        values.append([
            base + "AutoChannelEnable",
            auto,
            "xsd:boolean"
        ])

        requested["auto_channel"] = auto

        # VSOL usa Channel=0 cuando está automático.
        if auto:
            values.append([
                base + "Channel",
                0,
                "xsd:unsignedInt"
            ])

            requested["channel"] = 0

    if (
        payload.get("auto_channel") is False
        or (
            "channel" in payload
            and not payload.get("auto_channel", False)
        )
    ):
        channel = int(payload.get("channel", 0))

        if index == 5:
            allowed = set(range(1, 12))
        else:
            allowed = {
                36,40,44,48,
                52,56,60,64,
                100,104,108,112,116,
                136,140,
                149,153,157,161
            }

        if channel not in allowed:
            raise ValueError(
                f"Canal no permitido para WLAN {index}"
            )

        values.append([
            base + "Channel",
            channel,
            "xsd:unsignedInt"
        ])

        requested["channel"] = channel

    if "hidden" in payload:
        hidden = bool(payload["hidden"])

        # Mantenemos ambos parámetros coherentes.
        values.extend([
            [
                base + "X_CT-COM_SSIDHide",
                hidden,
                "xsd:boolean"
            ],
            [
                base + "SSIDAdvertisementEnabled",
                not hidden,
                "xsd:boolean"
            ]
        ])

        requested["hidden"] = hidden

    if not values:
        raise ValueError("No hay cambios para aplicar")

    return values, requested
