# ACS Control - Instalación

ACS Control tiene dos partes: un backend en FastAPI (Python) y un frontend en Vue 3.
Necesita PostgreSQL, Redis y acceso de red al **NBI de GenieACS** (puerto 7557 por defecto).

## Paso a paso (resumen)

1. **Prepare el servidor**: Debian 13 (recomendado), Debian 12 o Ubuntu 22.04/24.04,
   con 2 vCPU, 2 GB de RAM y 10 GB de disco. En Proxmox, cree antes un contenedor LXC
   ([Proxmox CT](install/proxmox-lxc.md)).
2. **Compruebe que llega a GenieACS**: el servidor debe alcanzar el NBI (puerto 7557).
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' "http://GENIEACS_SERVER:7557/devices/?projection=_id&limit=1"
   ```
   Debe responder `200`.
3. **Instale dependencias**: Python 3.10+, Node.js 20.19+/22.12+, PostgreSQL, Redis y Nginx.
4. **Clone el repositorio** en `/opt/acs-control`.
5. **Cree la base de datos** PostgreSQL y el archivo `.env` (dirección de GenieACS,
   base de datos y una clave secreta aleatoria).
6. **Instale el backend** (`.venv`) y **cree las tablas** (`app.bootstrap_db`).
7. **Cree el usuario administrador** (`app.manage_users create --role admin`).
8. **Deje el backend como servicio** (systemd).
9. **Compile el frontend** (`npm ci && npm run build`) y **publíquelo con Nginx**.
10. **Entre a `http://IP_DEL_SERVIDOR/`**, inicie sesión y siga
    [Primeros pasos](#primeros-pasos-después-de-instalar).

Cada paso, con sus comandos, está en la [guía de Linux](install/linux.md).

## Elija su plataforma

| Plataforma | Uso recomendado | Guía | Estado |
|---|---|---|---|
| Debian 13 | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Validado |
| Debian 12 | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Por validar |
| Ubuntu 24.04 LTS | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Por validar |
| Ubuntu 22.04 LTS | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Backend y frontend validados contra GenieACS; systemd/Nginx por validar |
| Proxmox VE (contenedor LXC) | Producción | [Proxmox CT](install/proxmox-lxc.md) | Por validar |
| macOS (Apple Silicon / Intel) | Desarrollo y pruebas locales | [macOS](install/macos.md) | Validado en Apple Silicon; Intel por validar |

"Validado" significa que la guía se siguió completa en esa plataforma y ACS Control
funcionó contra un GenieACS real. Si la sigue en una plataforma "por validar", reporte el
resultado en un issue para actualizar esta tabla.

## Requisitos mínimos

| Componente | Versión |
|---|---|
| Python | 3.10 o superior |
| Node.js | 20.19+ o 22.12+ (lo exige Vite 8) |
| PostgreSQL | 13 o superior |
| Redis | 6 o superior |
| GenieACS | NBI accesible por HTTP desde el servidor de ACS Control |

Recursos: 2 vCPU, 2 GB de RAM y 10 GB de disco.

### Versión de Node.js según el sistema

| Sistema | Node.js del repositorio oficial | ¿Sirve? |
|---|---|---|
| Debian 13 | 20.19 | Sí |
| Debian 12 | 18.x | No: instale Node 22 (ver guía Linux) |
| Ubuntu 24.04 | 18.x | No: instale Node 22 |
| Ubuntu 22.04 | 12.x | No: instale Node 22 |

Compruébelo siempre con `node --version` antes de compilar el frontend.

## Seguridad

- ACS Control exige iniciar sesión, con tres roles: `admin` (administración completa),
  `technical` (gestión de ONUs sin acceso a datos del servidor GenieACS) y `wifi`
  (soporte: ver la ONU y sus equipos conectados, y cambiar el Wi-Fi). Cada guía
  explica cómo crear el primer usuario.
- Aun así, no lo exponga directamente a Internet: publíquelo solo en la red de operación
  o detrás de una VPN, y use HTTPS si sale de una red de confianza.
- El backend escucha en `127.0.0.1`; en Linux, Nginx publica el frontend y reenvía `/api`.
- Nunca publique el archivo `.env` real.

## Primeros pasos después de instalar

1. **Inicie sesión** con el usuario `admin` que creó en la instalación.
2. **Revise la conexión**: en **Sistema → Configuración** deben aparecer API,
   PostgreSQL, Redis y GenieACS como operativos.
3. **Suba el logo del operador** (opcional): **Configuración → Logo del operador**.
   PNG, JPG, WEBP o SVG de hasta 512 KB; reemplaza la "A" en el inicio de sesión y en
   la barra lateral.
4. **Cree los usuarios** en **Sistema → Staff** con el rol que corresponda:

   | Rol | Para quién | Puede |
   |---|---|---|
   | `admin` | Supervisión | Todo, incluidos Staff, Auditoría y Configuración |
   | `technical` | Técnicos de red / NOC | Gestionar ONUs: WAN, Wi-Fi, CATV, seguridad y etiquetas |
   | `wifi` | Soporte de primer nivel | Ver la ONU y sus equipos conectados, y cambiar el Wi-Fi |

5. **Abra una ONU** desde **Dispositivos**. La primera vez ACS Control lee sus datos de
   la ONU (botón **Leer de la ONU**); según el modelo toma de 10 a 60 segundos.
6. Consulte qué está probado en cada modelo en [Modelos compatibles](MODELOS.md).

Cada usuario puede cambiar entre **modo oscuro y modo claro** con el botón de la barra
lateral; la preferencia se recuerda en su navegador.

## GenieACS: qué necesita ACS Control

- Solo el **NBI** (puerto 7557) accesible desde el servidor de ACS Control. No hace
  falta instalar presets, provisions ni scripts en GenieACS: ACS Control lee las ONUs
  con tareas estándar (`refreshObject`).
- Que GenieACS pueda despertar a las ONUs (*connection request*); si no, los cambios
  quedan en cola hasta el siguiente *inform* de la ONU.
- No publique el NBI a Internet: no tiene autenticación. Permítalo solo desde el
  servidor de ACS Control.
- Si un firmware corta las sesiones TR-069 con el preset `default` de GenieACS (visto en
  XPON fw V2.1.00-230825), se puede excluir ese firmware del preset con una
  precondición. ACS Control ya lee esas ONUs por partes.

## Actualizar

Antes de actualizar en producción, haga un respaldo de la base de datos:

```bash
runuser -u postgres -- pg_dump acs_control > /root/acs_control_$(date +%F).sql
```

Después siga **Actualizar ACS Control** al final de la [guía de Linux](install/linux.md)
o de la [guía de macOS](install/macos.md). La actualización conserva el `.env`, los
usuarios, la auditoría y el logo.
