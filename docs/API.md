# API de ACS-Control para agentes y scripts

ACS-Control expone una API REST en JSON. Es la misma que usa la interfaz web:
todo lo que un técnico hace en pantalla se puede hacer por API, con los mismos
permisos y la misma auditoría.

## 1. Crear un token

1. Inicie sesión como **admin**.
2. Vaya a **Sistema → Tokens API**.
3. Escriba un nombre (por ejemplo `agente-noc`), elija el **rol** y la **vigencia**, y pulse **Crear**.
4. Copie el token (`acs_…`). **Se muestra una sola vez**; ACS-Control solo guarda su huella.

| Rol del token | Puede |
|---|---|
| `wifi` | Ver inventario, ficha de la ONU, equipos conectados; cambiar el Wi-Fi |
| `technical` | Lo anterior + WAN, CATV, seguridad, etiquetas del catálogo, lecturas |
| `admin` | Todo, incluidos auditoría, usuarios y configuración |

- Un token **no** puede crear ni revocar tokens: eso se hace desde una sesión de admin.
- Lo que haga un token queda en **Auditoría** con el usuario `api:<nombre>`.
- **Revocar** lo desactiva al instante. Use un token por agente o integración, con el rol mínimo necesario.

## 2. Usar el token

Envíelo en cada petición:

```bash
TOKEN="acs_..."
API="https://acs-control.su-dominio"      # o http://127.0.0.1:8000

curl -s -H "Authorization: Bearer $TOKEN" "$API/api/devices?limit=20" | jq .
```

Sin token (ni sesión) la API responde `401`. Con un rol sin permiso, `403`.
Solo son públicos el inicio de sesión, el logo del operador y `/api/health`
(que sin token solo responde `{"api": true}`).

## 3. La especificación JSON (para el agente)

La API está descrita en **OpenAPI 3** (JSON): rutas, parámetros, cuerpos y
respuestas, agrupadas por tema (Dispositivos, Wi-Fi, WAN, CATV, Seguridad,
Etiquetas, Auditoría, Usuarios, Tokens API).

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$API/api/openapi.json" -o acs-control-openapi.json
```

También se descarga desde **Sistema → Tokens API → Descargar especificación JSON**.
Ese archivo es el que se le entrega a un agente (como definición de herramientas
o de un conector OpenAPI). La documentación navegable está en `/api/docs`
(requiere sesión o token; la página carga Swagger UI desde cdn.jsdelivr.net).

## 4. Operaciones frecuentes

Los `device_id` de GenieACS contienen caracteres especiales (`%`, `-`): codifíquelos
en la URL (`encodeURIComponent` / `urllib.parse.quote(id, safe="")`).

| Para | Método y ruta |
|---|---|
| Buscar ONUs | `GET /api/devices?q=<serial, modelo, IP…>&limit=100` |
| Ficha de una ONU (estado de datos y avisos de GenieACS) | `GET /api/devices/{id}` |
| Pedir datos frescos a la ONU | `POST /api/devices/{id}/refresh` (`?force=true` relee todo) |
| Ver el avance de esa lectura | `GET /api/devices/{id}/refresh` |
| WAN | `GET /api/devices/{id}/wan` |
| Wi-Fi | `GET /api/devices/{id}/wifi` · `PATCH /api/devices/{id}/wifi/{index}` |
| Equipos conectados (señal, consumo) | `GET /api/devices/{id}/hosts` · `POST /api/devices/{id}/hosts/refresh` |
| Seguridad / acceso remoto | `GET /api/devices/{id}/security-module` |
| Destrabar una ONU detenida en GenieACS | `POST /api/devices/{id}/genieacs/unblock` |
| Auditoría (admin) | `GET /api/audit` |

Ejemplo: leer el Wi-Fi de una ONU.

```bash
ID=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "4C46D1-V2802ACT-XXXX")
curl -s -H "Authorization: Bearer $TOKEN" "$API/api/devices/$ID/wifi" | jq .
```

Ejemplo: cambiar el nombre de la red 2.4 GHz (escritura en la ONU).

```bash
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ssid": "MiRed"}' "$API/api/devices/$ID/wifi/1" | jq .
```

La respuesta trae `status`: `CONFIRMADO` (la ONU lo aplicó), `PENDIENTE` (enviado,
esperando el próximo reporte de la ONU) o `SIN_CAMBIOS`. Si la ONU lo rechaza,
la API responde `422` con el código de la ONU y no se aplica nada.

## 5. Recomendaciones para agentes

- **Lea antes de escribir.** Las rutas `PATCH`, `POST` de creación y `DELETE` cambian
  la configuración de una ONU real de un cliente. Pida confirmación a una persona
  antes de usarlas, y use un token `wifi` o `technical` según lo que necesite.
- **Los datos pueden estar viejos.** Si la ficha trae `data_status.complete = false`
  o `stale = true`, pida una lectura (`POST …/refresh`) y consulte el avance
  (`GET …/refresh`) hasta `pending = 0`.
- **ONU detenida en GenieACS.** Si la ficha trae `genieacs.blocked = true`, GenieACS
  no está procesando las tareas de esa ONU; `POST …/genieacs/unblock` lo destraba.
- **La WAN de gestión (TR-069) nunca se edita ni se elimina**: la API lo rechaza.
