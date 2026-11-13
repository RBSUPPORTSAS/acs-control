# Modelos de ONU compatibles con ACS-Control

Esta lista dice qué modelos funcionan con ACS-Control sobre GenieACS y qué se probó en cada uno.
Se actualiza con cada modelo nuevo que se valida.

Última actualización: 2026-11-11.

## Cómo leer esta tabla

| Símbolo | Significado |
|---|---|
| ✅ | Probado en una ONU real con ACS-Control: se escribió, se confirmó leyendo la ONU y se revirtió. |
| 👁 | Se muestra correctamente (solo lectura). |
| ⏳ | Disponible en ACS-Control, pero todavía sin prueba de escritura en una ONU real. |
| ❌ | El firmware no lo expone por TR-069. |
| — | El equipo no tiene esa función. |

**Nivel de soporte**

- **Certificado:** todas las funciones que el modelo expone están probadas en una ONU real.
- **Parcial:** la lectura está validada y parte de la escritura queda pendiente de laboratorio.
- **No certificado:** solo datos y WiFi (SSID y clave). ACS-Control bloquea WAN, CATV y seguridad (`app/api/certified.py`).

Reglas que aplican a todos los modelos:

- La WAN de gestión TR-069 nunca se edita ni se elimina. Se reconoce por servicio, nombre o IP de gestión.
- Las WAN no se activan ni desactivan desde ACS-Control: solo se crean, editan y eliminan.
- ACS-Control no depende de presets ni scripts propios en GenieACS: lee la ONU con `refreshObject` por el NBI.
- Las contraseñas (PPPoE, Telnet, FTP, WiFi) nunca se muestran.

## Resumen

| Fabricante | Modelo | Firmware probado | Nivel | WAN | CATV | Seguridad | WiFi |
|---|---|---|---|---|---|---|---|
| CDTC | FD714GS1-R850 | V4.3.4_P219001 | Certificado | ✅ | ✅ | 👁 | ✅ |
| CDTC | FD714GS3-R851 | V3.3.14_P219001 | Certificado | ✅ | ✅ | 👁 | ✅ |
| HWTC | HG102DWT | V2.4.9 | Certificado | ✅ | — | 👁 | 👁 |
| Huawei | HG8145V5 | V5R019C10S270 | Certificado | ✅ | — | ✅ | ✅ |
| OPTICTIMES / Realtek | IGD | V15.4.7 | Certificado | ✅ | ⏳ | ✅ | ✅ |
| OPTICTIMES / Realtek | RT9607C | -1.2.0.30 | Certificado | ✅ | ✅ | ❌ | ✅ |
| Realtek | RX8102WT | V1.9.2.0-220715 | Certificado | ✅ | ✅ | ❌ | ✅ |
| X_CMCC | RX8414CDW | V02.01.02 | Certificado | ✅ | — | ✅ | 👁 |
| MONU | xPON+1GE+1FE+WIFI+CATV | V3.3.0-210624 | Certificado | ✅ | ❌ | ✅ | ✅ |
| VSOL / Realtek / MONU | XPON+2GE+2WiFi, XPON+2GE+2WiFi+USB+CATV, XPON+2GE+2WIFI+USB+CATV, XPON+4GE+2WiFi+USB+CATV | 8 firmwares (ver detalle) | Parcial | 👁 ⏳ | 👁 ⏳ | 👁 ⏳ | 👁 |
| VSOL | V2802ACT, V2802DAC, V2804ACT, V2804DAC | V2.1.00-250210 y otros | Parcial | 👁 ⏳ | 👁 ⏳ | 👁 ⏳ | 👁 |
| X_CMCC | ZC-500W | — | Parcial | 👁 ⏳ | — | 👁 ⏳ | 👁 |
| Varios | Familia X_CATV: KM1303, SML-702XW-C20/C21/C22, ONT1GE1FE1TVSWR, MUL-XPON-ONT200 | V2.1.14 (KM1303) | No certificado | 👁 | 👁 | — | ✅ SSID |

"WiFi ✅" significa que se reescribió el SSID en una ONU real. La clave WiFi se puede escribir en todos los modelos de la tabla, pero solo se probó donde se indica.

## Detalle por modelo

### CDTC FD714GS1-R850 y FD714GS3-R851

Probado el 2026-11-11 en una ONU de cada modelo, con autorización del supervisor (PR #15).

| Función | Resultado |
|---|---|
| Lectura completa | ✅ 8 de 8 ONUs, entre 7 y 28 s |
| Crear / editar / eliminar WAN DHCP | ✅ (16–28 s / 4 s / 5 s) |
| Crear / editar / eliminar WAN PPPoE | ✅ (14–29 s / 4 s / 4–6 s) |
| Crear / editar / eliminar WAN IP fija | ✅ con la ruta VSOL (13–18 s). Con la ruta que usa la interfaz para CDTC no se probó, porque la WAN queda encendida con un gateway y podría tomar la ruta por defecto del cliente. |
| La ruta por defecto del cliente no cambia al crear WAN | ✅ |
| CATV encender / apagar | ✅ `X_CMS_Services.CatvService.Enable` |
| WiFi 2.4 y 5 GHz | ✅ (reescritura del SSID) |
| Seguridad | 👁 Reglas `X_CT-COM_Security.ACL` (servicio, WAN/LAN, rango IP), solo lectura. No tiene nivel de firewall. |
| Potencia óptica | Disponible en `X_ALU_OntOpticalParam`, todavía no se muestra. |

Detalles técnicos:

- VLAN y 802.1p en `WANConnectionDevice.X_CT-COM_WANGponLinkConfig` (driver `x_ctcom_wan`).
- La banda WiFi se decide por el estándar y el canal: `X_CT-COM_RFBand` tiene el significado inverso al de VSOL (0 = 5 GHz).
- Si el preset de GenieACS solo declara la IP de la WAN, la rama queda creada pero sin recorrer. ACS-Control detecta sub-objetos sin `_timestamp` y la vuelve a leer.

Detalles que se ven en la pantalla:

- Al editar una WAN PPPoE, la ONU no actualiza el nombre (sigue con la VLAN anterior). Es solo cosmético.
- Después de apagar el CATV, el estado del servicio sigue diciendo "Up" hasta la siguiente lectura.

### HWTC HG102DWT

Probado en fw V2.4.9 (PR #6).

- ✅ Crear (encendida), editar y eliminar WAN DHCP, PPPoE e IP fija. ACS-Control reescribe el enlace en Mode 2 al final, porque en este modelo `X_CT-COM_VLANMode` y el `Mode` del enlace son el mismo campo.
- 👁 Seguridad: reglas `X_CT-COM_Security.ACL`, como la FD714.

### Huawei HG8145V5

Probado en fw V5R019C10S270 (PR #7).

- ✅ WAN DHCP, PPPoE e IP fija: crear, editar (VLAN, prioridad, MTU, IP, DNS, credenciales, interfaces) y eliminar. Usa `X_HW_VLAN`, `X_HW_PRI`, `X_HW_SERVICELIST` y `X_HW_LANBIND`.
- ✅ Nivel de firewall: Bajo, Alto, Medio y Personalizado.
- ❌ HTTPS por WAN: en este firmware la ONU descarta las reglas creadas por TR-069.
- La red de 5 GHz no se puede asociar a una WAN por TR-069; ACS-Control lo rechaza con un mensaje.
- La HG8546M usa el mismo código, pero solo se probó la escritura de SSID. Con el preset `acs_discovery` da `too_many_commits`.

### OPTICTIMES / Realtek IGD

Probado en fw V15.4.7 (PR #8).

- ✅ WAN DHCP, PPPoE e IP fija: crear, editar y eliminar (`X_RTK_VlanId`, `X_RZ_802-1pMark`, `X_RTK_ServiceType`).
- ✅ Seguridad: nivel (`Firewall.X_RZ_Firewall_Level`) y servicios por WAN/LAN, incluido HTTPS.
- ⏳ CATV: usa el mismo parámetro que la RT9607C, sin prueba propia.

### OPTICTIMES RT9607C

Probado en fw -1.2.0.30 (PR #10).

- ✅ WAN con prioridad 802.1p en `Layer2Bridging.Marking`: al crear se crea la marca, al editar se actualiza y al borrar se eliminan la marca y sus filtros.
- ✅ CATV (`X_RZ_Catv.RF_Enable`) con mediciones de RF.
- ❌ Seguridad: el firmware no tiene rama Firewall. Se muestra si la interfaz web está habilitada.

### Realtek RX8102WT

Probado en fw V1.9.2.0-220715 (PR #11).

- ✅ WAN con prioridad en `VlanPriMark` (variante `realtek_vpm`).
- ✅ CATV encender/apagar. El firmware no reporta mediciones de RF.
- ❌ Seguridad: sin rama Firewall.

### X_CMCC RX8414CDW

Probado en fw V02.01.02 (PR #12).

- ✅ WAN: todas las conexiones van dentro del WCD 1 (la ONU no acepta WCD nuevos). Crear agrega una conexión y borrar quita solo esa conexión.
- ✅ Firewall encendido/apagado (`X_CMCC_Security.FirewallEnable`). Con el firewall encendido, la gestión TR-069 sigue funcionando.
- ✅ Telnet LAN. 👁 Protecciones DoS, escaneo de puertos y filtros (solo lectura).
- Las sesiones tardan unos 45 s; ACS-Control espera más en las confirmaciones.

### MONU xPON+1GE+1FE+WIFI+CATV

Probado en fw V3.3.0-210624 (PR #13).

- ✅ WAN: crear tarda unos 2,7 min, porque la ONU tarda unos 22 s por sesión. ACS-Control trata la espera como "en cola" y confirma leyendo después.
- ✅ Telnet LAN y FTP (`X_CT-COM_ServiceManage`).
- El gateway de una WAN estática se toma de la ruta por defecto cuando la conexión no lo reporta.
- ❌ CATV: pese al nombre del modelo, el firmware no expone ningún parámetro de CATV.

### Familia XPON (VSOL, Realtek y MONU)

XPON+2GE+2WiFi, XPON+2GE+2WiFi+USB+CATV, XPON+2GE+2WIFI+USB+CATV y XPON+4GE+2WiFi+USB+CATV (PR #14). Lectura revisada en 99 ONUs y 8 firmwares; la escritura está pendiente de una ONU de laboratorio.

| Firmware | Notas |
|---|---|
| V2.1.00-230825 | Corta la sesión al pedir `LANDevice.1.Hosts`: ACS-Control la lee por partes y omite los equipos conectados. Conviene excluirlo del preset `default` de GenieACS. |
| V2.1.00-230711, 250107, 250210, 250214, 250415 | `Catv.Enable` llega vacío: el estado del CATV se muestra como desconocido. |
| V3.2.01-240807, V1.1.00-241014 | CATV con estado real (booleano). |
| V3.2.00-260114 | Lectura correcta (1 ONU). |
| 230310, 230111 | Sin reportar; no se pudieron leer. |

- La prioridad 802.1p 4294967295 se muestra como "Sin marcar".
- Un nivel de firewall 2 (fw 250415) se muestra como "Desconocido (2)" hasta confirmar su significado.

### VSOL V2802ACT, V2802DAC, V2804ACT y V2804DAC

- 👁 Lectura completa (árbol, IPv6 `X_CT-COM`, VLAN y prioridad).
- ⏳ La interfaz usa los creadores propios de VSOL (`/wan/vsol/*`), que crean la WAN apagada. Falta validarlo en laboratorio.
- V2802ACT fw 260205: da `cwmp.9002` en consultas grandes.

### Familia X_CATV (no certificada, prioridad baja)

KM1303, SML-702XW-C20/C21/C22, SML-702XW-AGC-C20/C21, ONT1GE1FE1TVSWR y MUL-XPON-ONT200-T-WR.

Se muestran sus datos y se puede cambiar el WiFi. ACS-Control bloquea WAN, CATV y seguridad porque, en la KM1303 (fw V2.1.14):

- La WAN de gestión no se publica por TR-069.
- Cada sesión tarda unos 30 s.
- Crear una WAN PPPoE dejó el cliente TR-069 sin responder hasta reiniciar la ONU.

## Modelos vistos sin validar

| Modelo | Estado |
|---|---|
| Huawei HG8546M y HG8145V5 S110A (TR-181) | Escritura de SSID validada; WAN sin probar. |
| ZY704dact-M-h23 / h24 | Escritura de SSID validada. No acepta crear WCD nuevos; `Enable` llega como texto. |
| WGP3200-T-W | Lectura de Telnet/FTP; WAN sin probar. |
| GLC-ONU-GE3200 | Sin reportar al ACS. |

## Cómo se valida un modelo nuevo

1. **Lectura:** abrir la ONU en ACS-Control y comparar WAN, CATV, seguridad y WiFi con la interfaz web de la ONU.
2. **Escritura:** solo con autorización y, si es posible, en una ONU de laboratorio.
   - WAN de prueba en VLAN 999 (y 998 al editar), sin puertos asociados: DHCP, PPPoE e IP fija. Crear, editar y eliminar.
   - CATV apagar y encender solo en laboratorio, porque corta la TV del cliente.
   - Seguridad: un servicio LAN (por ejemplo Telnet) encender y apagar.
3. **Comprobar el resultado:** la ONU queda idéntica a la foto inicial, sigue reportando y no quedan tareas ni faults en GenieACS.
4. **Regresión:** comparar lo que ACS-Control muestra en todas las ONUs del GenieACS con el código antes y después.
5. Registrar el resultado en este documento y en el PR.
