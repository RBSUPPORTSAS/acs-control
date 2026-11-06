# ACS Control - Instalación

ACS Control tiene dos partes: un backend en FastAPI (Python) y un frontend en Vue 3.
Necesita PostgreSQL, Redis y acceso de red al **NBI de GenieACS** (puerto 7557 por defecto).

## Elija su plataforma

| Plataforma | Uso recomendado | Guía | Estado |
|---|---|---|---|
| Debian 13 | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Validado |
| Debian 12 | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Por validar |
| Ubuntu 24.04 LTS | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Por validar |
| Ubuntu 22.04 LTS | Producción | [Linux (Debian / Ubuntu)](install/linux.md) | Backend y frontend validados contra GenieACS; systemd/Nginx por validar |
| Proxmox VE (contenedor LXC) | Producción | [Proxmox CT](install/proxmox-lxc.md) | Por validar |
| macOS (Apple Silicon / Intel) | Desarrollo y pruebas locales | [macOS](install/macos.md) | Por validar |

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

- ACS Control **todavía no tiene autenticación**. No lo exponga a Internet ni a redes
  donde haya usuarios no autorizados: cualquier persona que alcance la interfaz puede
  cambiar WAN, Wi-Fi y CATV de las ONUs.
- El backend escucha en `127.0.0.1`; en Linux, Nginx publica el frontend y reenvía `/api`.
- Nunca publique el archivo `.env` real.
