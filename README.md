# ACS Control

Open-source management and automation layer for GenieACS and TR-069 devices.

ACS Control provides a normalized API and web interface for managing heterogeneous ONU/CPE devices while keeping vendor-specific TR-069 logic inside the backend.

## Features

- Device inventory and Online/Offline status
- Search by serial, manufacturer, model, firmware, OUI and Tags
- Tag management
- Wi-Fi management
- CATV control
- PPPoE, DHCP and Static WAN management
- VLAN, NAT, MTU and interface bindings
- Protected TR-069 WAN detection
- Device firewall and remote-management controls
- Audit log (con el usuario que hizo cada cambio)
- Login con roles: admin (administración) y technical (gestión de ONUs)
- REST API with FastAPI/OpenAPI
- Vue 3 web interface
- PostgreSQL and Redis

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

Contributions from developers, network engineers, vendors and AI coding agents are welcome.

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before changing device-management logic.

## Installation

Guías por plataforma: [docs/INSTALL.md](docs/INSTALL.md)

- [Linux (Debian 12/13, Ubuntu 22.04/24.04)](docs/install/linux.md): producción con systemd y Nginx.
- [Proxmox VE (contenedor LXC)](docs/install/proxmox-lxc.md): producción.
- [macOS](docs/install/macos.md): desarrollo y pruebas locales.

## Inicio rápido

Requisitos: Python 3.10+, Node.js 20.19+ o 22.12+, PostgreSQL, Redis y acceso de red
al NBI de GenieACS (puerto 7557). El detalle está en [docs/INSTALL.md](docs/INSTALL.md).

**macOS** (desarrollo y pruebas, instalación automática con Homebrew):

```bash
git clone https://github.com/RBSUPPORTSAS/acs-control.git ~/acs-control
cd ~/acs-control
GENIE_NBI=http://IP_DE_GENIEACS:7557 bash scripts/install-macos.sh
```

Al terminar, abra http://127.0.0.1:4173. Más detalles en [docs/install/macos.md](docs/install/macos.md).

**Linux (Debian / Ubuntu)** para producción, con systemd y Nginx:
siga [docs/install/linux.md](docs/install/linux.md).

**Proxmox VE** (contenedor LXC): siga [docs/install/proxmox-lxc.md](docs/install/proxmox-lxc.md).

> ACS Control exige iniciar sesión, con roles `admin` y `technical`. El instalador pide
> crear el primer usuario administrador. No lo exponga directamente a Internet.

## API documentation

When the FastAPI backend is running:

```text
/docs
/openapi.json
```

## Security

Do not expose ACS Control write APIs to untrusted networks without authentication, TLS and access controls.

Never commit real .env files, device exports, credentials or customer data.

## License

MIT
