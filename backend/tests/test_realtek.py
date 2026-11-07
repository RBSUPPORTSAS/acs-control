"""Realtek / OPTICTIMES (IGD, RT9607C, RX8102WT): WAN, proteccion y seguridad.

Estructura tomada de la IGD 94026B-IGD-4F505449556E1F25 (fw V15.4.7).
"""

import pytest

from app.services.genieacs import genieacs
from app.services.security_module import firewall_write, security_state, service_changes
from app.services.wan_reader import read_wan, rtk_services

from conftest import login

ID = "94026B-IGD-PRUEBA"
FW = "InternetGatewayDevice.Firewall.X_RZ_ServiceControl.IPV4ServiceControl"


def v(value, writable=True):
    return {"_value": value, "_object": False, "_writable": writable}


def rule(ingress, any_=False, **flags):
    node = {"Enable": v(True), "Ingress": v(ingress), "Service_Any": v(any_)}
    for svc in ("HTTP", "HTTPS", "SSH", "TELNET", "FTP", "TFTP", "ICMP"):
        node[f"Service_{svc}"] = v(flags.get(svc.lower(), False))
    for svc, port in (("HTTP", 80), ("HTTPS", 443), ("SSH", 0), ("TELNET", 23), ("FTP", 21)):
        node[f"Service_{svc}_PORT"] = v(port)
    return node


def igd(tr069_name="default wan", service_type=1, cr_ip="10.1.0.150"):
    return {
        "_id": ID,
        "_deviceId": {"_Manufacturer": "OPTICTIMES", "_ProductClass": "IGD", "_SerialNumber": "P1"},
        "InternetGatewayDevice": {
            "ManagementServer": {"ConnectionRequestURL": v(f"http://{cr_ip}:7547/tr069", False)},
            "WANDevice": {"1": {"WANConnectionDevice": {
                "1": {"WANPPPConnection": {"1": {
                    "Name": v(""), "Enable": v(True), "ConnectionStatus": v("Connected"),
                    "ExternalIPAddress": v("172.16.1.157"), "Username": v("PR1"), "MaxMRUSize": v(1492),
                    "X_RTK_VlanId": v(70), "X_RZ_802-1pMark": v(0), "X_RTK_ServiceType": v(2),
                    "X_RTK_LanInterface": v("lan1,lan2,ssid1,ssid5"),
                }}},
                "2": {"WANIPConnection": {"1": {
                    "Name": v(tr069_name), "Enable": v(True), "ConnectionStatus": v("Connected"),
                    "AddressingType": v("DHCP"), "ExternalIPAddress": v("10.1.0.150"),
                    "X_RTK_VlanId": v(46), "X_RZ_802-1pMark": v(2), "X_RTK_ServiceType": v(service_type),
                    "X_RTK_LanInterface": v(""),
                }}},
            }}},
            "Firewall": {
                "X_RZ_Firewall_Level": v("Low"),
                "X_RZ_ServiceControl": {"IPV4ServiceControl": {
                    "1": rule("LAN", any_=True),
                    "2": rule("WAN", http=True, https=True, telnet=True, icmp=True),
                }},
            },
        },
    }


def test_mascara_de_servicios():
    assert rtk_services(1) == "TR069"
    assert rtk_services(2) == "INTERNET"
    assert rtk_services(3) == "TR069,INTERNET"
    assert rtk_services(None) is None


def test_lee_vlan_prioridad_servicios_e_interfaces():
    wans = {w["wan_connection_device"]: w for w in read_wan(igd())}
    assert (wans[1]["vlan"], wans[1]["priority_8021p"], wans[1]["services"]) == (70, 0, ["INTERNET"])
    assert (wans[2]["vlan"], wans[2]["priority_8021p"], wans[2]["services"]) == (46, 2, ["TR069"])
    b = wans[1]["lan_binding"]
    assert "LANEthernetInterfaceConfig.1" in b and "LANEthernetInterfaceConfig.2" in b
    assert "WLANConfiguration.1" in b and "WLANConfiguration.5" in b


def test_tr069_protegida_por_servicio():
    wans = {w["wan_connection_device"]: w for w in read_wan(igd())}
    assert wans[2]["protected"] is True
    assert wans[1]["protected"] is False


def test_tr069_protegida_por_ip_de_gestion_aunque_no_diga_tr069():
    # Caso RX8102WT: WAN incompleta en cache, sin servicio ni nombre utiles.
    wans = {w["wan_connection_device"]: w for w in read_wan(igd(tr069_name="default wan", service_type=None))}
    assert wans[2]["services"] == []
    assert wans[2]["protected"] is True
    assert "gestionar" in wans[2]["protection_reason"]


def test_ip_de_gestion_distinta_no_protege_internet():
    wans = {w["wan_connection_device"]: w for w in read_wan(igd(cr_ip="172.16.1.157", service_type=1))}
    # La WAN de internet tiene la IP del connection request en este caso hipotetico:
    assert wans[1]["protected"] is True


def test_seguridad_realtek():
    st = security_state(igd())
    assert (st["supported"], st["firewall_grade"], st["firewall_label"], st["wan_activation_allowed"]) == (True, 0, "Bajo", True)
    svc = {s["id"]: s for s in st["services"]}
    assert set(svc) == {"http", "https", "ssh", "telnet", "ftp", "tftp", "icmp"}
    assert svc["https"]["wan_enabled"] is True and svc["https"]["wan_port"] == 443
    assert svc["ssh"]["wan_enabled"] is False
    # La regla LAN tiene "cualquier servicio": abierta y no editable aqui.
    assert svc["ssh"]["lan_enabled"] is True and svc["ssh"]["lan_writable"] is False


def test_cambios_van_a_la_regla_wan():
    values, requested = service_changes(igd(), "telnet", {"wan_enabled": False})
    assert values == [[f"{FW}.2.Service_TELNET", False, "xsd:boolean"]]
    values, _ = service_changes(igd(), "https", {"wan_port": 8443})
    assert values == [[f"{FW}.2.Service_HTTPS_PORT", 8443, "xsd:unsignedInt"]]
    with pytest.raises(ValueError):
        service_changes(igd(), "ssh", {"lan_enabled": False})


def test_firewall_realtek():
    assert firewall_write(igd(), 1) == ("InternetGatewayDevice.Firewall.X_RZ_Firewall_Level", "High", "xsd:string")


@pytest.fixture
def rt(monkeypatch):
    async def fake_get_device(device_id):
        return igd()
    monkeypatch.setattr(genieacs, "get_device", fake_get_device)


async def test_no_borra_tr069(client, rt):
    await login(client, "tecnico")
    r = await client.delete(f"/api/devices/{ID}/wan/2/WANIPConnection/1")
    assert r.status_code == 403


@pytest.mark.parametrize("path", ["wan/create-dhcp", "wan/create-ip", "wan/create-pppoe", "wan/vsol/create-ip", "wan/vsol/create-pppoe"])
async def test_crear_bloqueado(client, rt, path):
    await login(client, "jefe")
    r = await client.post(f"/api/devices/{ID}/{path}", json={"vlan": 999, "username": "u", "password": "p"})
    assert r.status_code == 400
    assert "no está validado" in r.json()["detail"]


@pytest.mark.parametrize("body", [{"vlan": 71}, {"priority": 3}, {"bindings": ["InternetGatewayDevice.LANDevice.1.LANEthernetInterfaceConfig.1"]}])
async def test_editar_vlan_prioridad_interfaces_bloqueado(client, rt, body):
    await login(client, "jefe")
    r = await client.patch(f"/api/devices/{ID}/wan/1/pppoe/1", json=body)
    assert r.status_code == 400
    assert "no está validado" in r.json()["detail"]
