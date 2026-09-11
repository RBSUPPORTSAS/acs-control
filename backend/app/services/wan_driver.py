def detect_wan_driver(device):
    """
    Detecta la arquitectura WAN por capacidades reales del CPE,
    no por fabricante ni modelo.
    """

    try:
        wcds = (
            device["InternetGatewayDevice"]
            ["WANDevice"]["1"]
            ["WANConnectionDevice"]
        )
    except Exception:
        return "generic"

    if not isinstance(wcds, dict):
        return "generic"

    # 1. Arquitectura X_CATV
    # VLAN/802.1p viven en X_CATV_WANGponLinkConfig.
    for index, wcd in wcds.items():
        if not str(index).isdigit():
            continue

        if not isinstance(wcd, dict):
            continue

        if isinstance(
            wcd.get("X_CATV_WANGponLinkConfig"),
            dict
        ):
            return "x_catv_wan"

    # 2. Arquitectura X_CT-COM con WCD independiente
    # VLAN/802.1p viven en X_CT-COM_WANGponLinkConfig.
    for index, wcd in wcds.items():
        if not str(index).isdigit():
            continue

        if not isinstance(wcd, dict):
            continue

        if isinstance(
            wcd.get("X_CT-COM_WANGponLinkConfig"),
            dict
        ):
            return "x_ctcom_wan"

    # 3. Constructor antiguo
    return "generic"
