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
- Audit log
- REST API with FastAPI/OpenAPI
- Vue 3 web interface
- PostgreSQL and Redis

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contributing

Contributions from developers, network engineers, vendors and AI coding agents are welcome.

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before changing device-management logic.

## Quick start

```bash
git clone https://github.com/RBSUPPORTSAS/acs-control.git
cd acs-control
cp .env.example .env
```

Backend:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Frontend:

```bash
cd frontend
npm ci
npm run build
```

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
