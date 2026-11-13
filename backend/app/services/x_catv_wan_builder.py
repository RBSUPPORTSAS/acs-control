"""Enlace GPON/VLAN de las ONU X_CATV (X_CATV_WANGponLinkConfig).

La conexion se arma con x_ctcom_wan_builder y vendor_wan.translate('x_catv').
"""


def build_link_values(wcd, data):
    vlan = int(data["vlan"])
    priority = int(data.get("priority", 0))

    base = (
        "InternetGatewayDevice."
        "WANDevice.1."
        f"WANConnectionDevice.{wcd}"
    )

    link = f"{base}.X_CATV_WANGponLinkConfig"

    return [
        [f"{link}.Enable", True, "xsd:boolean"],
        [f"{link}.Mode", 2, "xsd:unsignedInt"],
        [f"{link}.VLANIDMark", vlan, "xsd:unsignedInt"],
        [f"{link}.802-1pMark", priority, "xsd:unsignedInt"],
    ]
