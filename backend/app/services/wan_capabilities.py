def node(device, path):
    current = device

    for part in path.split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(part)

        if current is None:
            return None

    return current


def metadata(device, path):
    n = node(device, path)

    if not isinstance(n, dict):
        return {
            "exists": False,
            "writable": False,
            "type": None
        }

    return {
        "exists": True,
        "writable": bool(n.get("_writable")),
        "type": n.get("_type")
    }


def parameters(device, prefix):

    names = [
        "Enable",
        "ConnectionType",
        "AddressingType",
        "Name",
        "NATEnabled",
        "Username",
        "Password",
        "MaxMRUSize",
        "MaxMTUSize",
        "DNSServers",
        "ExternalIPAddress",
        "SubnetMask",
        "DefaultGateway",
        "X_CT-COM_ServiceList",
        "X_CT-COM_VLANIDMark",
        "X_CT-COM_802-1pMark",
        "X_CT-COM_LanInterface",
        "X_CT-COM_IPMode",
        "X_CT-COM_VLANMode",
    ]

    result = {}

    for name in names:

        n = node(
            device,
            f"{prefix}.{name}"
        )

        if isinstance(n, dict):

            result[name] = {
                "exists": True,
                "writable": bool(
                    n.get("_writable")
                ),
                "type": n.get("_type"),
                "value": n.get("_value")
            }

    return result


def read_capabilities(device):

    root = (
        "InternetGatewayDevice."
        "WANDevice.1."
        "WANConnectionDevice.1"
    )

    ppp_container = (
        root + ".WANPPPConnection"
    )

    ip_container = (
        root + ".WANIPConnection"
    )

    return {
        "wan_connection_device": metadata(
            device,
            "InternetGatewayDevice."
            "WANDevice.1."
            "WANConnectionDevice"
        ),

        "pppoe": {
            "container": metadata(
                device,
                ppp_container
            ),
            "existing_instance": metadata(
                device,
                ppp_container + ".1"
            ),
            "parameters": parameters(
                device,
                ppp_container + ".1"
            )
        },

        "ip": {
            "container": metadata(
                device,
                ip_container
            ),
            "existing_instance": metadata(
                device,
                ip_container + ".1"
            ),
            "parameters": parameters(
                device,
                ip_container + ".1"
            )
        }
    }
