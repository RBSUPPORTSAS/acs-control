import re


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


def node(obj, path):
    current = obj

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

        if current is None:
            return None

    return current if isinstance(current, dict) else None


def writable(obj, path):
    n = node(obj, path)
    return isinstance(n, dict) and bool(n.get("_writable"))


def detect_band(obj):
    standard = str(
        unwrap(obj.get("Standard")) or ""
    ).lower()

    tokens = {
        x
        for x in re.split(r"[^a-z0-9]+", standard)
        if x
    }

    # b/g identifican claramente 2.4 GHz.
    if "b" in tokens or "g" in tokens:
        return "2.4 GHz"

    # a/ac identifican claramente 5 GHz.
    if "a" in tokens or "ac" in tokens:
        return "5 GHz"

    for name in ("ChannelsInUse", "Channel"):
        try:
            channel = int(str(unwrap(obj.get(name))).split(",")[0])
        except Exception:
            continue

        if channel > 14:
            return "5 GHz"

        if channel > 0:
            return "2.4 GHz"

    band = str(unwrap(obj.get("OperatingFrequencyBand")) or "").lower()

    if band.startswith("5"):
        return "5 GHz"

    # X_CT-COM_RFBand no sirve: VSOL usa 0 = 2.4 GHz y CDTC FD714 0 = 5 GHz.
    return "2.4 GHz"


def hidden_state(obj):
    value = unwrap(obj.get("X_CT-COM_SSIDHide"))

    if value is None:
        value = unwrap(obj.get("X_CATV_SSIDHide"))

    if value is not None:
        return bool(value)

    advertised = unwrap(
        obj.get("SSIDAdvertisementEnabled")
    )

    if advertised is not None:
        return not bool(advertised)

    return None


def wifi_state(device, index):
    obj = wlan_object(device, index)

    if not obj:
        return None

    channel = unwrap(obj.get("Channel"))

    auto_channel = unwrap(
        obj.get("AutoChannelEnable")
    )

    # Algunos CPE, como X_CATV, usan Channel=0
    # para representar selección automática.
    if auto_channel is None and channel is not None:
        try:
            auto_channel = int(channel) == 0
        except Exception:
            pass

    return {
        "index": index,
        "band": detect_band(obj),
        "enabled": unwrap(obj.get("Enable")),
        "ssid": unwrap(obj.get("SSID")),
        "auto_channel": auto_channel,
        "channel": channel,
        "current_channel": unwrap(
            obj.get("ChannelsInUse")
        ),
        "hidden": hidden_state(obj),
    }


def drop_unchanged(device, index, payload):
    """Quita del pedido lo que ya esta igual en la ONU.

    La interfaz envia el formulario completo; mandar solo lo que cambia evita
    que un campo que la ONU no acepta (p. ej. el canal) tumbe el cambio de
    SSID o clave, que van en el mismo setParameterValues.
    """

    state = wifi_state(device, index) or {}
    payload = dict(payload)

    for key in ("enabled", "ssid", "hidden"):
        if key in payload and state.get(key) is not None:
            current = state[key]
            wanted = str(payload[key]).strip() if key == "ssid" else bool(payload[key])
            if wanted == current:
                payload.pop(key)

    auto = payload.get("auto_channel")
    if auto is not None and state.get("auto_channel") is not None:
        same_mode = bool(auto) == bool(state["auto_channel"])
        same_channel = (
            "channel" not in payload
            or str(payload.get("channel")) == str(state.get("channel"))
        )
        if same_mode and (auto or same_channel):
            payload.pop("auto_channel")
            payload.pop("channel", None)

    return payload


def build_wifi_changes(device, index, payload):
    obj = wlan_object(device, index)

    if not obj:
        raise ValueError(
            "Interfaz Wi-Fi no encontrada"
        )

    band = detect_band(obj)

    base = (
        "InternetGatewayDevice."
        "LANDevice.1."
        f"WLANConfiguration.{index}."
    )

    values = []
    requested = {}

    if "enabled" in payload:
        enabled = bool(payload["enabled"])

        if not writable(obj, "Enable"):
            raise ValueError(
                "El estado Wi-Fi no es modificable"
            )

        values.append([
            base + "Enable",
            enabled,
            "xsd:boolean"
        ])

        requested["enabled"] = enabled

    if "ssid" in payload:
        ssid = str(payload["ssid"]).strip()

        if not ssid:
            raise ValueError(
                "SSID no puede estar vacío"
            )

        if len(ssid) > 32:
            raise ValueError(
                "SSID máximo 32 caracteres"
            )

        if not writable(obj, "SSID"):
            raise ValueError(
                "El SSID no es modificable"
            )

        values.append([
            base + "SSID",
            ssid,
            "xsd:string"
        ])

        requested["ssid"] = ssid

    if payload.get("password"):
        password = str(payload["password"])

        if len(password) < 8 or len(password) > 63:
            raise ValueError(
                "La contraseña Wi-Fi debe tener entre 8 y 63 caracteres"
            )

        if writable(obj, "KeyPassphrase"):
            password_path = "KeyPassphrase"

        elif writable(
            obj,
            "PreSharedKey.1.KeyPassphrase"
        ):
            password_path = (
                "PreSharedKey.1.KeyPassphrase"
            )

        else:
            raise ValueError(
                "La contraseña Wi-Fi no es modificable en esta interfaz"
            )

        values.append([
            base + password_path,
            password,
            "xsd:string"
        ])

    if "auto_channel" in payload:
        auto = bool(payload["auto_channel"])

        # Si existe AutoChannelEnable lo utilizamos.
        if writable(obj, "AutoChannelEnable"):
            values.append([
                base + "AutoChannelEnable",
                auto,
                "xsd:boolean"
            ])

            requested["auto_channel"] = auto

        # Sin AutoChannelEnable, muchos CPE usan Channel=0 como automatico.
        # Con AutoChannelEnable no se envia: ZTE F6600P responde cwmp.9003
        # a Channel=0 y rechaza todo el paquete (SSID y clave incluidos).
        elif auto:
            if writable(obj, "Channel"):
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
            and not payload.get(
                "auto_channel",
                False
            )
        )
    ):
        channel = int(
            payload.get("channel", 0)
        )

        if band == "2.4 GHz":
            allowed = set(range(1, 12))
        else:
            allowed = {
                36, 40, 44, 48,
                52, 56, 60, 64,
                100, 104, 108, 112,
                116, 136, 140,
                149, 153, 157, 161
            }

        if channel not in allowed:
            raise ValueError(
                f"Canal no permitido para {band}"
            )

        if not writable(obj, "Channel"):
            raise ValueError(
                "El canal no es modificable"
            )

        values.append([
            base + "Channel",
            channel,
            "xsd:unsignedInt"
        ])

        requested["channel"] = channel

    if "hidden" in payload:
        hidden = bool(payload["hidden"])
        hidden_written = False

        if writable(
            obj,
            "X_CT-COM_SSIDHide"
        ):
            values.append([
                base + "X_CT-COM_SSIDHide",
                hidden,
                "xsd:boolean"
            ])
            hidden_written = True

        if writable(
            obj,
            "X_CATV_SSIDHide"
        ):
            values.append([
                base + "X_CATV_SSIDHide",
                hidden,
                "xsd:boolean"
            ])
            hidden_written = True

        if writable(
            obj,
            "SSIDAdvertisementEnabled"
        ):
            values.append([
                base + "SSIDAdvertisementEnabled",
                not hidden,
                "xsd:boolean"
            ])
            hidden_written = True

        if hidden_written:
            requested["hidden"] = hidden

    if not values:
        raise ValueError(
            "No hay cambios compatibles para aplicar"
        )

    return values, requested
