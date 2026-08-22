from app.services.device_normalizer import get_parameter

def val(device, index, name):
    return get_parameter(
        device,
        f"InternetGatewayDevice.LANDevice.1.WLANConfiguration.{index}.{name}"
    )

def wifi(device, index, band):
    return {
        "band": band,
        "enabled": val(device,index,"Enable"),
        "ssid": val(device,index,"SSID"),
        "channel": val(device,index,"Channel"),
        "current_channel": val(device,index,"ChannelsInUse"),
        "auto_channel": val(device,index,"AutoChannelEnable"),
        "standard": val(device,index,"Standard"),
        "bssid": val(device,index,"BSSID"),
        "hidden": val(device,index,"X_CT-COM_SSIDHide"),
        "encryption": val(device,index,"IEEE11iEncryptionModes"),
    }

def read_wifi(device):
    return {
        "2_4ghz": wifi(device,5,"2.4 GHz"),
        "5ghz": wifi(device,1,"5 GHz")
    }
