# ACS Control - Installation Guide

Instalación manual validada para Debian 13.

## Requisitos

- Debian 13
- 2 vCPU
- 2 GB RAM
- 10 GB de disco
- Acceso de red al NBI de GenieACS
- Acceso root o sudo

Versiones validadas:

```text
Python 3.13
Node.js 20
PostgreSQL 17
Redis 8
Nginx 1.26+
```

## 1. Dependencias del sistema

```bash
apt update

apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  postgresql \
  postgresql-client \
  redis-server \
  nginx \
  nodejs \
  npm \
  curl \
  jq \
  openssl \
  build-essential \
  libpq-dev
```

Verificación:

```bash
python3 --version
node --version
npm --version
psql --version
redis-server --version
nginx -v
```

## 2. Clonar ACS Control

```bash
cd /opt
git clone https://github.com/RBSUPPORTSAS/acs-control.git
cd /opt/acs-control
```

## 3. Activar servicios base

```bash
systemctl enable --now postgresql redis-server nginx
redis-cli ping
```

Redis debe responder:

```text
PONG
```

## 4. Crear PostgreSQL

```bash
DBPASS="$(openssl rand -hex 24)"

runuser -u postgres -- psql \
  -c "CREATE ROLE acs_control_app LOGIN PASSWORD '$DBPASS';"

runuser -u postgres -- createdb \
  -O acs_control_app \
  acs_control
```

Conserve temporalmente `DBPASS` para configurar `.env`.

## 5. Configurar `.env`

```bash
cp .env.example .env
openssl rand -hex 32
nano .env
```

Ejemplo:

```env
APP_NAME="ACS Control"
APP_ENV="production"
APP_HOST="127.0.0.1"
APP_PORT=8000

TIMEZONE="America/Bogota"

APP_SECRET_KEY="CHANGE_WITH_RANDOM_SECRET"

GENIEACS_NBI_URL="http://GENIEACS_SERVER:7557"
GENIEACS_TIMEOUT=15

DATABASE_URL="postgresql+asyncpg://acs_control_app:DATABASE_PASSWORD@127.0.0.1:5432/acs_control"

REDIS_HOST="127.0.0.1"
REDIS_PORT=6379
REDIS_DB=0

LOG_LEVEL="INFO"
```

Proteja el archivo:

```bash
chmod 600 .env
```

Nunca publique el `.env` real.

## 6. Instalar backend

```bash
cd /opt/acs-control

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m pip check
```

## 7. Inicializar base de datos

```bash
cd /opt/acs-control

PYTHONPATH=backend \
  .venv/bin/python -m app.bootstrap_db
```

## 8. Probar backend manualmente

```bash
PYTHONPATH=backend \
  .venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000
```

Desde otra terminal:

```bash
curl -s http://127.0.0.1:8000/api/health | jq .
```

Respuesta esperada:

```json
{
  "api": true,
  "postgresql": true,
  "redis": true,
  "genieacs": true,
  "healthy": true
}
```

Detenga Uvicorn manual antes de continuar.

## 9. Crear servicio systemd

```bash
nano /etc/systemd/system/acs-control.service
```

Contenido:

```ini
[Unit]
Description=ACS Control API
After=network.target postgresql.service redis-server.service

[Service]
WorkingDirectory=/opt/acs-control
Environment=PYTHONPATH=/opt/acs-control/backend
ExecStart=/opt/acs-control/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Activar:

```bash
systemctl daemon-reload
systemctl enable --now acs-control
systemctl status acs-control --no-pager
```

## 10. Compilar frontend

```bash
cd /opt/acs-control/frontend
npm ci
npm run build
```

Publicar:

```bash
rm -rf /var/www/acs-control
mkdir -p /var/www/acs-control

cp -a /opt/acs-control/frontend/dist/. /var/www/acs-control/

chown -R www-data:www-data /var/www/acs-control
```

## 11. Configurar Nginx

```bash
nano /etc/nginx/sites-available/acs-control
```

Contenido:

```nginx
server {
    listen 80 default_server;
    server_name _;

    root /var/www/acs-control;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
    }
}
```

Activar:

```bash
rm -f /etc/nginx/sites-enabled/default

ln -sf \
  /etc/nginx/sites-available/acs-control \
  /etc/nginx/sites-enabled/acs-control

nginx -t
systemctl reload nginx
```

## 12. Validar

```bash
curl -I http://127.0.0.1/
curl -s http://127.0.0.1/api/health | jq .
curl -s "http://127.0.0.1/api/devices?limit=10" | jq .
hostname -I
```

Accesos:

```text
http://SERVER_IP/
http://SERVER_IP/docs
```

## Problemas comunes

### `python3 -m venv` falla

```bash
apt install -y python3-venv
```

En algunos sistemas:

```bash
apt install -y python3.13-venv
```

### `npm: command not found`

```bash
apt install -y nodejs npm
```

### `curl` o `jq` no existen

```bash
apt install -y curl jq
```

### PostgreSQL `InvalidPasswordError`

La contraseña de `DATABASE_URL` debe coincidir con la contraseña del rol `acs_control_app`.

Use:

```text
postgresql+asyncpg://
```

No use:

```text
postgresql://
```

## Actualizar ACS Control

```bash
cd /opt/acs-control
git pull

.venv/bin/pip install -r backend/requirements.txt

cd frontend
npm ci
npm run build

rm -rf /var/www/acs-control/*
cp -a /opt/acs-control/frontend/dist/. /var/www/acs-control/

systemctl restart acs-control
systemctl reload nginx
```
