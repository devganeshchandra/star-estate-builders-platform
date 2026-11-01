#!/usr/bin/env bash
# Set up the builder websites platform on a new machine.
#
#   ./scripts/setup.sh                                   # development (your laptop)
#   ./scripts/setup.sh --production --domain m3mhome.in
#
# Works on Ubuntu/Debian (installs what it needs with apt), other Linux and
# macOS with Python 3.12+, and Git Bash on Windows. Safe to run again: it
# never overwrites an existing .env or your content.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
MODE="development"
DOMAIN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --production) MODE="production" ;;
    --domain) DOMAIN="${2:?--domain needs a value, e.g. www.m3mindia.com}"; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ "$MODE" == "production" && -z "$DOMAIN" ]]; then
  echo "Production setup needs --domain, e.g. --domain www.m3mindia.com" >&2
  exit 1
fi

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$1"; }

python_ok() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

find_python() {
  local candidate
  for candidate in python3.14 python3.13 python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && python_ok "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# 1. Python 3.12 or newer -----------------------------------------------------
step "Checking Python (3.12 or newer is required)"
if ! PYTHON="$(find_python)"; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing Python 3.12 with apt (needs sudo)…"
    sudo apt-get update
    if ! sudo apt-get install -y python3.12 python3.12-venv; then
      # Ubuntu 22.04 and older ship Python 3.10: use the deadsnakes PPA.
      sudo apt-get install -y software-properties-common
      sudo add-apt-repository -y ppa:deadsnakes/ppa
      sudo apt-get update
      sudo apt-get install -y python3.12 python3.12-venv
    fi
    PYTHON="python3.12"
  else
    echo "Please install Python 3.12 or newer, then run this script again." >&2
    exit 1
  fi
fi
echo "Using $($PYTHON --version) ($PYTHON)"

# Debian/Ubuntu split venv support into a separate package.
if ! "$PYTHON" -c 'import ensurepip, venv' >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    version="$("$PYTHON" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
    sudo apt-get install -y "python${version}-venv" || sudo apt-get install -y python3-venv
  else
    echo "Python's venv module is missing. Install it, then run again." >&2
    exit 1
  fi
fi

# 2. Virtual environment and packages ----------------------------------------
step "Installing Python packages into .venv"
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
if [[ -x .venv/bin/python ]]; then VENV_PY=".venv/bin/python"; else VENV_PY=".venv/Scripts/python"; fi
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r requirements.txt

# 3. .env ---------------------------------------------------------------------
set_env() {
  # set_env KEY VALUE: replace the line KEY=... in .env
  local key="$1" value="$2"
  "$VENV_PY" - "$key" "$value" <<'PY'
import pathlib, sys
key, value = sys.argv[1], sys.argv[2]
path = pathlib.Path(".env")
lines = path.read_text(encoding="utf-8").splitlines()
for i, line in enumerate(lines):
    if line.startswith(key + "="):
        lines[i] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

step "Preparing .env settings"
if [[ -f .env ]]; then
  echo ".env already exists, leaving it unchanged."
else
  cp .env.example .env
  set_env DJANGO_SECRET_KEY "$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(50))')"
  if [[ "$MODE" == "production" ]]; then
    bare="${DOMAIN#www.}"
    set_env DJANGO_DEBUG 0
    # Add every further builder domain to these two lines (see docs/ENVIRONMENT_SETUP.md).
    set_env DJANGO_ALLOWED_HOSTS "$bare,www.$bare,localhost,127.0.0.1"
    set_env DJANGO_CSRF_TRUSTED_ORIGINS "https://$bare,https://www.$bare"
    set_env PLATFORM_ADMIN_HOSTS ""
  else
    set_env DJANGO_DEBUG 1
  fi
  chmod 600 .env 2>/dev/null || true
  echo "Created .env ($MODE). Review it later for email settings."
fi

# 3b. PostgreSQL ---------------------------------------------------------------
env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }

if [[ "$(env_value DB_ENGINE)" =~ ^postgres && -z "$(env_value DB_PASSWORD)" ]]; then
  step "Setting up PostgreSQL"
  if command -v apt-get >/dev/null 2>&1; then
    if ! command -v psql >/dev/null 2>&1; then
      echo "Installing PostgreSQL with apt (needs sudo)…"
      sudo apt-get update
      sudo apt-get install -y postgresql
    fi
    db_name="$(env_value DB_NAME)"; db_name="${db_name:-m3m}"
    db_user="$(env_value DB_USER)"; db_user="${db_user:-m3m}"
    db_password="$("$VENV_PY" -c 'import secrets, string; a = string.ascii_letters + string.digits; print("".join(secrets.choice(a) for _ in range(32)))')"
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$db_user'" | grep -q 1; then
      sudo -u postgres psql -qc "ALTER ROLE \"$db_user\" WITH LOGIN PASSWORD '$db_password';"
    else
      sudo -u postgres psql -qc "CREATE ROLE \"$db_user\" LOGIN PASSWORD '$db_password';"
    fi
    if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$db_name'" | grep -q 1; then
      sudo -u postgres psql -qc "CREATE DATABASE \"$db_name\" OWNER \"$db_user\" ENCODING 'UTF8' TEMPLATE template0;"
    fi
    set_env DB_PASSWORD "$db_password"
    echo "PostgreSQL database “$db_name” and login “$db_user” are ready (password saved in .env)."
  elif [[ "$MODE" == "production" ]]; then
    echo "Install PostgreSQL, create a database and login (see docs/DATABASE.md), put them in .env, then run this script again." >&2
    exit 1
  else
    echo "PostgreSQL is not set up on this machine. Install PostgreSQL (or run: docker compose up -d), put" >&2
    echo "its database and login in .env (DB_* lines), then run this script again. See docs/LOCAL_SETUP.md." >&2
    exit 1
  fi
fi

# 4. Database, static files, content -----------------------------------------
step "Setting up the database"
"$VENV_PY" manage.py migrate --noinput

if [[ "$MODE" == "production" ]]; then
  step "Collecting static files"
  "$VENV_PY" manage.py collectstatic --noinput -v0
fi

if "$VENV_PY" manage.py shell -v0 -c "import sys; from projects.models import Project; sys.exit(0 if Project.objects.exists() else 1)"; then
  echo "Content already present, skipping the starter content."
else
  step "Loading the starter website content"
  "$VENV_PY" manage.py seed_content
fi

if [[ "$MODE" != "production" ]]; then
  step "Local addresses for each builder (localhost, m3m.localhost …)"
  "$VENV_PY" manage.py add_local_domains
fi

# 5. Admin account ------------------------------------------------------------
if "$VENV_PY" manage.py shell -v0 -c "import sys; from django.contrib.auth.models import User; sys.exit(0 if User.objects.filter(is_superuser=True).exists() else 1)"; then
  echo "An admin account already exists."
elif [[ -t 0 ]]; then
  step "Create the first admin account"
  "$VENV_PY" manage.py createsuperuser
else
  echo "No admin account yet. Create one with: $VENV_PY manage.py createsuperuser"
fi

# 6. Done ---------------------------------------------------------------------
step "Setup complete"
if [[ "$MODE" == "production" ]]; then
  cat <<EOF
Next, put the site online with a background service and Nginx:
  sudo ./scripts/install_server.sh $DOMAIN
EOF
else
  cat <<EOF
Start the site with:
  $VENV_PY manage.py runserver
Then open http://localhost:8000/ or http://m3m.localhost:8000/ (admin: http://localhost:8000/admin/).
Other builders: http://<builder>.localhost:8000/ (sample builders: manage.py add_local_domains --demo).
EOF
fi
