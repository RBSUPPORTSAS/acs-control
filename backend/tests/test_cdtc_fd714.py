"""CDTC FD714GS3-R851 (fw V3.3.14) y FD714GS1-R850 (fw V4.3.4).

Vistos en el GenieACS 10.15.50.6:
- Su preset solo declara la IP de la WAN: la rama WANDevice existe con
  _timestamp en la raiz pero sus sub-objetos nunca se recorrieron, y
  ACS-Control la daba por completa (WAN sin VLAN, sin nombre, driver generic).
- CATV en X_CMS_Services.CatvService.Enable (booleano) + Status.
- Seguridad en X_CT-COM_Security.ACL (reglas WAN/LAN con lista de servicios).
"""

from app.services import device_refresh as dr
from app.services.catv_reader import read_catv
from app.services.security_module import security_state, access_table
from app.services.wan_driver import detect_wan_driver
from app.services.wan_reader import read_wan

TS = "2026-11-11T03:00:00.000Z"


def v(value, t="xsd:string", writable=True):
    return {"_value": value, "_object": False, "_writable": writable, "_type": t, "_timestamp": TS}


def obj(children, walked=True):
    node = {"_object": True, "_writable": False, **children}
    if walked:
        node["_timestamp"] = TS
    return node


def wan_only_inform():
    """Como queda tras el preset del GenieACS: solo la IP de cada WAN."""
    wcd = lambda ip: obj({"WANIPConnection": obj({"1": obj({"ExternalIPAddress": v(ip)}, False)}, False)}, False)
    return obj({"1": obj({"WANConnectionDevice": obj({"2": wcd("172.17.4.22"), "3": wcd("10.20.24.137")}, False)}, False)})


def wcd_full(index, vlan, prio, name, service, addressing):
    return obj({
        "X_CT-COM_WANGponLinkConfig": obj({
            "Enable": v(True, "xsd:boolean"),
            "Mode": v(2, "xsd:unsignedInt"),
            "VLANIDMark": v(vlan, "xsd:unsignedInt"),
            "802-1pMark": v(prio, "xsd:unsignedInt"),
        }),
        "WANIPConnection": obj({"1": obj({
            "Name": v(name),
            "AddressingType": v(addressing),
            "ConnectionType": v("IP_Routed"),
            "ConnectionStatus": v("Connected"),
            "Enable": v(True, "xsd:boolean"),
            "ExternalIPAddress": v("192.0.2.%d" % index),
            "DefaultGateway": v("192.0.2.1"),
            "X_CT-COM_ServiceList": v(service),
            "X_CT-COM_LanInterface": v(""),
        })}),
    })


def device(wan=None, acl=True):
    igd = {
        "DeviceInfo": obj({
            "Manufacturer": v("CDTC"),
            "ProductClass": v("FD714GS3-R851"),
            "SoftwareVersion": v("V3.3.14_P219001"),
        }),
        "WANDevice": wan or obj({"1": obj({"WANConnectionDevice": obj({
            "2": wcd_full(2, 160, 1, "2_INTERNET_R_VID_160", "INTERNET", "Static"),
            "3": wcd_full(3, 46, 2, "1_TR069_R_VID_46_O", "TR069", "DHCP"),
        })})}),
        "X_CMS_Services": obj({
            "CatvOfCapabilities": v(2, "xsd:unsignedInt", False),
            "CatvService": obj({
                "Enable": v(True, "xsd:boolean"),
                "Status": v("Up", writable=False),
            }),
        }),
    }
    if acl:
        rule = lambda iface, svcs, en=True, start="0.0.0.0", end="255.255.255.255": obj({
            "Enable": v(en, "xsd:boolean"), "Interface": v(iface), "Mode": v("Permit"),
            "Servics": v(svcs), "StartIP": v(start), "EndIP": v(end),
        })
        igd["X_CT-COM_Security"] = obj({"ACL": obj({
            "1": rule("LAN", "WEB"),
            "4": rule("WAN", "PING"),
            "5": rule("WAN", "HTTPS", start="10.0.0.1", end="10.0.0.9"),
            "6": rule("WAN", "WEB", en=False),
            "7": rule("LAN", "WEB,HTTPS"),
        })})
    return {"_id": "C4CD50-FD714GS3%2DR851-PRUEBA", "InternetGatewayDevice": igd}


def test_branch_with_unwalked_subobjects_is_incomplete():
    d = device(wan=wan_only_inform())
    state = dr.branch_state(d["InternetGatewayDevice"]["WANDevice"])
    assert state["values"] == state["params"] == 2
    assert state["structure"] is False
    assert "WANDevice" in dr.data_status(d)["missing"]
    assert "InternetGatewayDevice.WANDevice" in dr.plan_refresh(d)


def test_fully_walked_branch_is_complete():
    d = device()
    assert dr.branch_state(d["InternetGatewayDevice"]["WANDevice"])["structure"] is True
    assert "WANDevice" not in dr.data_status(d)["missing"]


def test_new_branches_are_read():
    names = dr.BRANCHES["InternetGatewayDevice"]
    assert "X_CT-COM_Security" in names and "X_CMS_Services" in names


def test_wan_after_full_read():
    d = device()
    assert detect_wan_driver(d) == "x_ctcom_wan"
    wans = {w["wan_connection_device"]: w for w in read_wan(d)}
    assert wans[2]["vlan"] == 160 and wans[2]["priority_8021p"] == 1
    assert wans[2]["name"] == "2_INTERNET_R_VID_160" and wans[2]["services"] == ["INTERNET"]
    assert wans[3]["protected"] is True and wans[3]["vlan"] == 46


def test_catv_x_cms_services():
    c = read_catv(device())
    assert c["supported"] and c["driver"] == "x_cms_services"
    assert c["enabled"] is True and c["writable"] is True
    assert {"label": "Estado del servicio", "value": "Up"} in c["metrics"]


def test_security_acl_read_only():
    d = device()
    s = security_state(d)
    assert s["supported"] is True and s["firewall_kind"] is None
    svc = {x["id"]: x for x in s["services"]}
    assert svc["icmp"]["wan_enabled"] is True
    assert svc["https"]["wan_enabled"] is True and svc["https"]["specific_ip"] == "10.0.0.1-10.0.0.9"
    # Regla 6 (HTTP por WAN) desactivada: HTTP solo por LAN.
    assert svc["http"]["wan_enabled"] is False and svc["http"]["lan_enabled"] is True
    assert not any(x["wan_writable"] or x["lan_writable"] for x in s["services"])
    assert access_table(d)[1] == {}
    assert any("Solo lectura" in n["value"] for n in s["notes"])


def test_without_acl_security_unsupported():
    assert security_state(device(acl=False))["supported"] is False


def test_wifi_band_by_standard_not_substring():
    from app.services.wifi_writer import detect_band
    # WiFi 6 en 2.4 GHz: "ax" contiene "a" pero no es 5 GHz.
    assert detect_band({"Standard": v("b,g,n,ax")}) == "2.4 GHz"
    assert detect_band({"Standard": v("a,n,ac,ax")}) == "5 GHz"
    # CDTC: X_CT-COM_RFBand 0 = 5 GHz (al reves que VSOL); no se usa.
    assert detect_band({"Standard": v("a,n,ac,ax"), "X_CT-COM_RFBand": v(0)}) == "5 GHz"
    # Sin Standard (XPON+4GE): decide el canal en uso.
    assert detect_band({"Standard": v(""), "ChannelsInUse": v("108")}) == "5 GHz"
    assert detect_band({"Standard": v("n"), "ChannelsInUse": v("5")}) == "2.4 GHz"


def test_read_wifi_cdtc_both_bands():
    from app.services.wifi_reader import read_wifi
    wlan = obj({
        "1": obj({"Standard": v("b,g,n,ax"), "SSID": v("RED"), "Enable": v(True, "xsd:boolean")}),
        "5": obj({"Standard": v("a,n,ac,ax"), "SSID": v("RED-5G"), "Enable": v(True, "xsd:boolean")}),
    })
    d = device()
    d["InternetGatewayDevice"]["LANDevice"] = obj({"1": obj({"WLANConfiguration": wlan})})
    w = read_wifi(d)
    assert w["2_4ghz"]["index"] == 1 and w["5ghz"]["index"] == 5
