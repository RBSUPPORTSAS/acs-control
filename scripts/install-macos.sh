#!/usr/bin/env bash
# ==========================================================
# ACS Control - instalacion local en macOS (Apple Silicon o Intel)
# Uso:  bash scripts/install-macos.sh            (desde la raiz del repo clonado)
#   o:  GENIE_NBI=http://IP:7557 bash scripts/install-macos.sh
# Se puede ejecutar varias veces: lo ya instalado se omite.
# Log:  ~/acs-control-install.log
# ==========================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/acs-control-install.log"
APP="$(cd "$SCRIPT_DIR/.." && pwd)"
GENIE_NBI="${GENIE_NBI:-http://GENIEACS_SERVER:7557}"
PG_VER="16"
PY_VER="3.12"

exec > >(tee -a "$LOG") 2>&1
echo
echo "=== ACS Control macOS $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "macOS $(sw_vers -productVersion) | $(uname -m)"

paso() { echo; echo ">>> $*"; }

if [ "$GENIE_NBI" = "http://GENIEACS_SERVER:7557" ]; then
  echo "Defina la URL del NBI: GENIE_NBI=http://IP_DE_GENIEACS:7557 bash scripts/install-macos.sh"
  exit 1
fi

# 1. Homebrew --------------------------------------------------------
paso "1/9 Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)" && break
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew no esta instalado. Instalalo con el comando de https://brew.sh"
  echo "(te pedira tu clave de macOS) y vuelve a ejecutar este script."
  exit 1
fi
brew --version | head -1

# 2. Paquetes --------------------------------------------------------
paso "2/9 Paquetes: python@$PY_VER postgresql@$PG_VER redis node git"
for f in "python@$PY_VER" "postgresql@$PG_VER" redis node git; do
  if brew list --versions "$f" >/dev/null 2>&1; then echo "ya instalado: $f"
  else brew install "$f"; fi
done
PG_BIN="$(brew --prefix "postgresql@$PG_VER")/bin"
PY="$(brew --prefix "python@$PY_VER")/bin/python$PY_VER"

# 3. Servicios -------------------------------------------------------
paso "3/9 Servicios PostgreSQL y Redis"
brew services start "postgresql@$PG_VER" || true
brew services start redis || true
for i in $(seq 1 30); do "$PG_BIN/pg_isready" -q -h 127.0.0.1 && break; sleep 1; done
"$PG_BIN/pg_isready" -h 127.0.0.1
redis-cli ping

# 4. Codigo ----------------------------------------------------------
paso "4/9 Codigo en $APP"
cd "$APP"
git log --oneline -1

# 5. Base de datos ---------------------------------------------------
paso "5/9 Base de datos acs_control"
if [ -f "$APP/.env" ] && grep -q '^DATABASE_URL=' "$APP/.env"; then
  echo ".env ya existe; se conserva la clave de la base de datos"
  DB_PASS="$(grep '^DATABASE_URL=' "$APP/.env" | sed -E 's#.*://[^:]+:([^@]+)@.*#\1#')"
else
  DB_PASS="$(openssl rand -hex 16)"
fi
if ! "$PG_BIN/psql" -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='acs_control_app'" | grep -q 1; then
  "$PG_BIN/psql" -h 127.0.0.1 -d postgres -c "CREATE ROLE acs_control_app LOGIN PASSWORD '$DB_PASS'"
else
  "$PG_BIN/psql" -h 127.0.0.1 -d postgres -c "ALTER ROLE acs_control_app PASSWORD '$DB_PASS'" >/dev/null
fi
if ! "$PG_BIN/psql" -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='acs_control'" | grep -q 1; then
  "$PG_BIN/createdb" -h 127.0.0.1 -O acs_control_app acs_control
fi
echo "rol y base listos"

# 6. .env ------------------------------------------------------------
paso "6/9 Configuracion .env"
if [ ! -f "$APP/.env" ]; then
  cat > "$APP/.env" <<ENV
APP_NAME="ACS Control"
APP_ENV="development"
APP_HOST="127.0.0.1"
APP_PORT=8000
TIMEZONE="America/Bogota"
APP_SECRET_KEY="$(openssl rand -hex 32)"
GENIEACS_NBI_URL="$GENIE_NBI"
GENIEACS_TIMEOUT=30
DATABASE_URL="postgresql+asyncpg://acs_control_app:$DB_PASS@127.0.0.1:5432/acs_control"
REDIS_HOST="127.0.0.1"
REDIS_PORT=6379
REDIS_DB=0
LOG_LEVEL="INFO"
ENV
  chmod 600 "$APP/.env"
fi
grep -E '^(APP_HOST|GENIEACS_NBI_URL)=' "$APP/.env"

# 7. Backend ---------------------------------------------------------
paso "7/9 Backend (Python $PY_VER)"
[ -x "$APP/.venv/bin/python" ] || "$PY" -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/backend/requirements.txt"
(cd "$APP" && PYTHONPATH=backend .venv/bin/python -m app.bootstrap_db)

# 8. Frontend --------------------------------------------------------
paso "8/9 Frontend"
(cd "$APP/frontend" && npm ci --no-audit --no-fund && npm run build)

# 9. Scripts de inicio y parada -------------------------------------
paso "9/9 Scripts iniciar/detener"
mkdir -p "$APP/.run"
cat > "$APP/.run/iniciar.sh" <<'RUN'
#!/usr/bin/env bash
cd "$(dirname "$0")/.."; mkdir -p .run
PYTHONPATH=backend nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > .run/backend.log 2>&1 &
echo $! > .run/backend.pid
(cd frontend; nohup npm run preview > ../.run/frontend.log 2>&1 & echo $! > ../.run/frontend.pid)
sleep 4
echo "ACS Control:  http://127.0.0.1:4173"
echo "API (docs):   http://127.0.0.1:8000/docs"
curl -s http://127.0.0.1:8000/api/health; echo
RUN
cat > "$APP/.run/detener.sh" <<'RUN'
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
for p in backend frontend; do [ -f .run/$p.pid ] && kill "$(cat .run/$p.pid)" 2>/dev/null && echo "detenido: $p"; rm -f .run/$p.pid; done
pkill -f "vite preview" 2>/dev/null || true
RUN
chmod +x "$APP/.run/iniciar.sh" "$APP/.run/detener.sh"
"$APP/.run/detener.sh" >/dev/null 2>&1 || true
"$APP/.run/iniciar.sh"

echo
echo "=== Instalacion terminada ==="
echo "Abrir: http://127.0.0.1:4173"
echo "Detener: $APP/.run/detener.sh   Iniciar: $APP/.run/iniciar.sh"
