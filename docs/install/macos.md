# ACS Control en macOS

Instalación local para **desarrollo y pruebas** en macOS (Apple Silicon o Intel).
Para producción use [Linux](linux.md) o [Proxmox CT](proxmox-lxc.md).

> Estado: **validado en Apple Silicon** (instalación automática completa, conectada a un
> GenieACS real). En Mac con Intel está por validar: si la sigue, reporte el resultado
> para actualizar [la tabla de plataformas](../INSTALL.md).

## Requisitos

- macOS 13 (Ventura) o superior.
- [Homebrew](https://brew.sh). Su instalación pide la clave de macOS.
- Acceso de red al NBI de GenieACS (por ejemplo, con la VPN conectada).

## Instalación automática

```bash
git clone https://github.com/RBSUPPORTSAS/acs-control.git ~/acs-control
cd ~/acs-control
GENIE_NBI=http://IP_DE_GENIEACS:7557 bash scripts/install-macos.sh
```

El script:

1. Instala con Homebrew `python@3.12`, `postgresql@16`, `redis`, `node` y `git`
   (omite lo que ya esté instalado).
2. Inicia PostgreSQL y Redis como servicios (`brew services`).
3. Crea el rol y la base `acs_control` con una clave aleatoria.
4. Genera `.env` (permisos `600`) apuntando a su GenieACS.
5. Instala el backend en `.venv` y crea las tablas.
   Si no hay usuarios, **pide crear el primer administrador** (`admin`, rol `admin`).
6. Compila el frontend y arranca todo.

Se puede ejecutar varias veces: lo ya instalado se omite y el `.env` existente se conserva.
El registro completo queda en `~/acs-control-install.log`.

Al terminar:

| Servicio | URL |
|---|---|
| Interfaz | http://127.0.0.1:4173 |
| API (documentación) | http://127.0.0.1:8000/docs |

## Usuarios (Staff)

ACS Control tiene dos roles:

| Rol | Acceso |
|---|---|
| `admin` | Todo: gestión de ONUs, auditoría, configuración y usuarios (sección Staff) |
| `technical` | Gestión de ONUs (WAN, Wi-Fi, CATV, etiquetas). No ve datos del servidor GenieACS, ni la auditoría, ni la configuración |
| `wifi` | Soporte Wi-Fi: ve el inventario, la información de la ONU y sus equipos conectados, y cambia el Wi-Fi (SSID y clave). Sin WAN, CATV, seguridad ni etiquetas |

Los usuarios se crean desde la interfaz (**Sistema → Staff**, solo admin) o desde la terminal:

```bash
cd ~/acs-control
PYTHONPATH=backend .venv/bin/python -m app.manage_users create --username juan --role technical
PYTHONPATH=backend .venv/bin/python -m app.manage_users reset-password --username admin
PYTHONPATH=backend .venv/bin/python -m app.manage_users list
```

## Iniciar y detener

```bash
~/acs-control/.run/iniciar.sh
~/acs-control/.run/detener.sh
```

Los registros quedan en `~/acs-control/.run/backend.log` y `frontend.log`.

## Instalación manual

Si prefiere hacerlo paso a paso:

```bash
brew install python@3.12 postgresql@16 redis node git
brew services start postgresql@16
brew services start redis

PG="$(brew --prefix postgresql@16)/bin"
DBPASS="$(openssl rand -hex 16)"
"$PG/psql" -h 127.0.0.1 -d postgres -c "CREATE ROLE acs_control_app LOGIN PASSWORD '$DBPASS'"
"$PG/createdb" -h 127.0.0.1 -O acs_control_app acs_control

cd ~/acs-control
cp .env.example .env      # edite GENIEACS_NBI_URL, DATABASE_URL (con $DBPASS) y APP_SECRET_KEY
chmod 600 .env

"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/python -m app.bootstrap_db
PYTHONPATH=backend .venv/bin/python -m app.manage_users create --username admin --role admin

(cd frontend && npm ci && npm run build)

PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
(cd frontend && npm run preview)
```

`npm run preview` sirve el frontend compilado y reenvía `/api` al backend
(configurado en `frontend/vite.config.js`; para otro backend use `ACS_API_URL`).
Para desarrollo con recarga automática use `npm run dev` (http://127.0.0.1:5173).

## Seguridad

- La instalación de macOS escucha solo en `127.0.0.1`: es para uso local.
- Si apunta a un GenieACS de producción, **los cambios que haga en la interfaz se
  aplican de verdad a las ONUs**.

## Desinstalar

```bash
~/acs-control/.run/detener.sh
PG="$(brew --prefix postgresql@16)/bin"
"$PG/dropdb" -h 127.0.0.1 acs_control
"$PG/psql" -h 127.0.0.1 -d postgres -c "DROP ROLE acs_control_app"
rm -rf ~/acs-control
# Opcional: brew services stop postgresql@16 redis
```
