from app.services.device_normalizer import get_parameter

def read_catv(device):
    base = "InternetGatewayDevice.DeviceInfo.Catv."

    return {
        "supported": get_parameter(device, base + "Support"),
        "enabled": get_parameter(device, base + "Enable"),
    }
