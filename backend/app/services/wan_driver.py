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


def huawei_wan(device):
    """True si las WAN usan el modelo Huawei (X_HW_VLAN / X_HW_SERVICELIST).

    En Huawei la VLAN va en X_HW_VLAN de la conexion. Los creadores y
    editores de VLAN de ACS-Control escriben X_CT-COM_*, que Huawei no
    tiene: GenieACS los omitiria sin error y la WAN quedaria sin VLAN.
    Mientras no se valide en laboratorio, esas operaciones se bloquean.
    """

    try:
        wcds = device["InternetGatewayDevice"]["WANDevice"]["1"]["WANConnectionDevice"]
    except Exception:
        return False

    if not isinstance(wcds, dict):
        return False

    for index, wcd in wcds.items():
        if not str(index).isdigit() or not isinstance(wcd, dict):
            continue
        for kind in ("WANIPConnection", "WANPPPConnection"):
            for inst, conn in (wcd.get(kind) or {}).items():
                if str(inst).isdigit() and isinstance(conn, dict) and (
                    "X_HW_VLAN" in conn or "X_HW_SERVICELIST" in conn
                ):
                    return True

    return False


HUAWEI_CREATE_MSG = "Crear WAN aún no está validado en ONUs Huawei"
HUAWEI_VLAN_MSG = "Cambiar VLAN o prioridad aún no está validado en ONUs Huawei"
