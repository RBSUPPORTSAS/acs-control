from app.services.device_normalizer import get_parameter
from app.services.interface_inventory import inventory


def val(device, index, name):
    return get_parameter(
        device,
        f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{index}.{name}"
    )


def wifi(device, index, band):
    if index is None:
        return {
            "band": band,
            "index": None,
            "supported": False,
            "enabled": None,
            "ssid": None,
            "channel": None,
            "current_channel": None,
            "auto_channel": None,
            "standard": None,
            "bssid": None,
            "hidden": None,
            "encryption": None,
        }

    return {
        "band": band,
        "index": index,
        "supported": True,
        "enabled": val(device, index, "Enable"),
        "ssid": val(device, index, "SSID"),
        "channel": val(device, index, "Channel"),
        "current_channel": val(device, index, "ChannelsInUse"),
        "auto_channel": val(device, index, "AutoChannelEnable"),
        "standard": val(device, index, "Standard"),
        "bssid": val(device, index, "BSSID"),
        "hidden": val(device, index, "X_CT-COM_SSIDHide"),
        "encryption": val(device, index, "IEEE11iEncryptionModes"),
    }


def primary_wifi_index(device, band):
    candidates = [
        item
        for item in inventory(device)
        if item.get("type") == "wifi"
        and item.get("band") == band
    ]

    if not candidates:
        return None

    # Preferir WLAN habilitada; después, menor índice.
    candidates.sort(
        key=lambda item: (
            not bool(item.get("enabled")),
            item.get("index", 9999),
        )
    )

    return candidates[0]["index"]


def read_wifi(device):
    index_24 = primary_wifi_index(device, "2.4 GHz")
    index_5 = primary_wifi_index(device, "5 GHz")

    return {
        "2_4ghz": wifi(device, index_24, "2.4 GHz"),
        "5ghz": wifi(device, index_5, "5 GHz"),
    }
