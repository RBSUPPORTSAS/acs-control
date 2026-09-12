from app.services.device_normalizer import get_parameter


CATV_PROFILES = (
    {
        "driver": "deviceinfo_catv",
        "parameter": "InternetGatewayDevice.DeviceInfo.Catv.Enable",
        "support_parameter": "InternetGatewayDevice.DeviceInfo.Catv.Support",
        "value_type": "xsd:string",
        "on_value": "1",
        "off_value": "0",
    },
    {
        "driver": "x_catv_rfdevice",
        "parameter": "InternetGatewayDevice.X_CATV_RFDevice.CATVEnable",
        "support_parameter": None,
        "value_type": "xsd:int",
        "on_value": 1,
        "off_value": 0,
    },
)


def _get_node(device, path):
    current = device

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

        if current is None:
            return None

    return current if isinstance(current, dict) else None


def _as_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on", "enable", "enabled")

    return False


def resolve_catv_profile(device):
    candidates = []

    for profile in CATV_PROFILES:
        node = _get_node(device, profile["parameter"])

        if node is None:
            continue

        support_parameter = profile.get("support_parameter")

        if support_parameter:
            support_value = get_parameter(device, support_parameter)

            if support_value is not None and not _as_bool(support_value):
                continue

        candidate = {
            **profile,
            "enabled": get_parameter(device, profile["parameter"]),
            "writable": _as_bool(node.get("_writable")),
        }

        candidates.append(candidate)

    if not candidates:
        return None

    # Preferir un parámetro realmente escribible.
    for candidate in candidates:
        if candidate["writable"]:
            return candidate

    return candidates[0]


def read_catv(device):
    profile = resolve_catv_profile(device)

    if not profile:
        return {
            "supported": False,
            "enabled": None,
            "writable": False,
            "driver": None,
        }

    return {
        "supported": True,
        "enabled": profile["enabled"],
        "writable": profile["writable"],
        "driver": profile["driver"],
    }
