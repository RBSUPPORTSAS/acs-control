from datetime import datetime, timezone


def get_parameter(device: dict, path: str):
    current = device

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

        if current is None:
            return None

    if isinstance(current, dict) and "_value" in current:
        return current.get("_value")

    return current


def first_value(device: dict, paths: list[str]):
    for path in paths:
        value = get_parameter(device, path)

        if value not in (None, ""):
            return value

    return None


def online_status(last_inform):
    if not last_inform:
        return False

    try:
        parsed = datetime.fromisoformat(
            str(last_inform).replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        seconds = (now - parsed).total_seconds()

        return seconds <= 300

    except Exception:
        return False


def normalize_device(device: dict):

    device_id = device.get("_deviceId", {})

    last_inform = device.get("_lastInform")

    manufacturer = (
        device_id.get("_Manufacturer")
        or first_value(
            device,
            [
                "InternetGatewayDevice.DeviceInfo.Manufacturer",
                "Device.DeviceInfo.Manufacturer",
            ],
        )
    )

    product_class = (
        device_id.get("_ProductClass")
        or first_value(
            device,
            [
                "InternetGatewayDevice.DeviceInfo.ProductClass",
                "Device.DeviceInfo.ProductClass",
            ],
        )
    )

    serial_number = (
        device_id.get("_SerialNumber")
        or first_value(
            device,
            [
                "InternetGatewayDevice.DeviceInfo.SerialNumber",
                "Device.DeviceInfo.SerialNumber",
            ],
        )
    )

    software_version = first_value(
        device,
        [
            "InternetGatewayDevice.DeviceInfo.SoftwareVersion",
            "Device.DeviceInfo.SoftwareVersion",
        ],
    )

    hardware_version = first_value(
        device,
        [
            "InternetGatewayDevice.DeviceInfo.HardwareVersion",
            "Device.DeviceInfo.HardwareVersion",
        ],
    )

    uptime = first_value(
        device,
        [
            "InternetGatewayDevice.DeviceInfo.UpTime",
            "Device.DeviceInfo.UpTime",
        ],
    )

    return {
        "id": device.get("_id"),
        "manufacturer": manufacturer,
        "oui": device_id.get("_OUI"),
        "product_class": product_class,
        "serial_number": serial_number,
        "software_version": software_version,
        "hardware_version": hardware_version,
        "uptime": uptime,
        "last_inform": last_inform,
        "online": online_status(last_inform),
        "tags": device.get("_tags") or [],
    }
