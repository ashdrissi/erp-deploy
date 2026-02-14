#!/usr/bin/env bash
set -euo pipefail

BENCH_DIR="/home/frappe/frappe-bench"

raw_site_name="${SITE_NAME:-}"
if [[ -z "$raw_site_name" ]]; then
  echo "SITE_NAME is required" >&2
  exit 1
fi

# Normalize SITE_NAME: strip scheme and any path.
site_name="$raw_site_name"
site_name="${site_name#http://}"
site_name="${site_name#https://}"
site_name="${site_name%%/*}"
site_name="${site_name%%:*}"

db_host="${DB_HOST:-mariadb}"
db_port="${DB_PORT:-3306}"
db_root_password="${DB_PASSWORD:-}"
admin_password="${ADMIN_PASSWORD:-admin}"

redis_cache="${REDIS_CACHE:-redis://redis-cache:6379/0}"
redis_queue="${REDIS_QUEUE:-redis://redis-queue:6379/1}"
redis_socketio="${REDIS_SOCKETIO:-redis://redis-socketio:6379/2}"
socketio_port="${SOCKETIO_PORT:-9000}"

ensure_redis_url() {
  local url="$1"
  local default_db="$2"

  if [[ "$url" != *"://"* ]]; then
    url="redis://${url}"
  fi
  if [[ "$url" != */* ]]; then
    url="${url}/${default_db}"
  fi
  printf '%s' "$url"
}

redis_cache="$(ensure_redis_url "$redis_cache" 0)"
redis_queue="$(ensure_redis_url "$redis_queue" 1)"
redis_socketio="$(ensure_redis_url "$redis_socketio" 2)"

if [[ -z "$db_root_password" ]]; then
  echo "DB_PASSWORD is required (MariaDB root password)" >&2
  exit 1
fi

cd "$BENCH_DIR"

# FORCE REMOVAL of removed custom apps from apps.txt to fix boot loops
if [[ -f "sites/apps.txt" ]]; then
  sed -i '/custom_desk_theme/d' "sites/apps.txt"
fi

# Restore assets from the image backup to the volume
if [[ -d "${BENCH_DIR}/assets-backup" ]]; then
  echo "Restoring assets from image..."
  # Copy assets, overwriting existing ones but keeping extra files
  cp -r "${BENCH_DIR}/assets-backup/"* "${BENCH_DIR}/sites/assets/"
fi

normalize_apps_txt() {
  local apps_txt="/home/frappe/frappe-bench/sites/apps.txt"

  # Normalize to one app per line. This prevents accidental concatenation like "erpnexthrms"
  # when the file is missing a trailing newline.
  python3 - <<'PY'
import os
import re

path = "/home/frappe/frappe-bench/sites/apps.txt"
if not os.path.exists(path):
    # Default minimal set.
    with open(path, "w", encoding="utf-8") as f:
        f.write("frappe\nerpnext\n")
    raise SystemExit(0)

with open(path, "r", encoding="utf-8", errors="ignore") as f:
    raw = f.read().replace("\r", "\n")

tokens = [t for t in re.split(r"\s+", raw) if t]

seen = set()
apps = []
for t in tokens:
    if not re.fullmatch(r"[a-z0-9_]+", t):
        continue
    if t in seen:
        continue
    # Explicitly exclude removed apps
    if t in {"custom_desk_theme"}:
        continue
    seen.add(t)
    apps.append(t)

# Ensure core apps present.
for required in ("frappe", "erpnext"):
    if required not in seen:
        apps.insert(0, required)
        seen.add(required)

with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(apps) + "\n")
PY
}

ensure_site_db_user_access() {
  local site="$1"
  local cfg_path="/home/frappe/frappe-bench/sites/${site}/site_config.json"

  if [[ ! -f "$cfg_path" ]]; then
    return 0
  fi

  local db_name
  local db_pass
  db_name="$(CFG_PATH="$cfg_path" python3 - <<'PY'
import json
import os
cfg_path = os.environ['CFG_PATH']
with open(cfg_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)
print(cfg.get('db_name',''))
PY
  )"
  db_pass="$(CFG_PATH="$cfg_path" python3 - <<'PY'
import json
import os
cfg_path = os.environ['CFG_PATH']
with open(cfg_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)
print(cfg.get('db_password',''))
PY
  )"

  if [[ -z "$db_name" || -z "$db_pass" ]]; then
    return 0
  fi

  # Escape single quotes in password for SQL.
  local db_pass_sql
  db_pass_sql=${db_pass//"'"/"''"}
  mysql -h "$db_host" -P "$db_port" -uroot -p"$db_root_password" --protocol=tcp \
    -e "CREATE USER IF NOT EXISTS \`$db_name\`@'%' IDENTIFIED BY '$db_pass_sql'; \
        ALTER USER \`$db_name\`@'%' IDENTIFIED BY '$db_pass_sql'; \
        GRANT ALL PRIVILEGES ON \`$db_name\`.* TO \`$db_name\`@'%'; \
        FLUSH PRIVILEGES;"
}

repair_orderlift_module_conflicts() {
  local site="$1"
  local cfg_path="/home/frappe/frappe-bench/sites/${site}/site_config.json"

  if [[ ! -f "$cfg_path" ]]; then
    return 0
  fi

  local db_name
  db_name="$(CFG_PATH="$cfg_path" python3 - <<'PY'
import json
import os
cfg_path = os.environ['CFG_PATH']
with open(cfg_path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)
print(cfg.get('db_name',''))
PY
  )"

  if [[ -z "$db_name" ]]; then
    return 0
  fi

  # Cleanup from old orderlift module names that conflicted with ERPNext core modules.
  mysql -h "$db_host" -P "$db_port" -uroot -p"$db_root_password" --protocol=tcp "$db_name" -e "
    UPDATE \
      \`tabModule Def\`
    SET
      app_name = 'erpnext'
    WHERE
      name IN ('CRM', 'Sales', 'HR')
      AND app_name = 'orderlift';

    DELETE FROM \
      \`tabModule Def\`
    WHERE
      app_name = 'orderlift'
      AND name IN ('CRM', 'Sales', 'HR', 'Logistics', 'Portal', 'Client Portal', 'SAV', 'SIG');
  " || true
}

ensure_app_installed() {
  local site="$1"
  local app="$2"

  normalize_apps_txt

  # Ensure app code exists in bench. If the image was built without it for some reason,
  # fetch it at runtime.
  if [[ ! -d "/home/frappe/frappe-bench/apps/${app}" ]]; then
    echo "Fetching app code: ${app}"
    if [[ "$app" == "hrms" ]]; then
      bench get-app --branch version-15 --skip-assets hrms https://github.com/frappe/hrms.git
    elif [[ "$app" == "orderlift" ]]; then
      local app_backup="/opt/erp-deploy/apps/orderlift"
      if [[ -d "$app_backup" ]]; then
        echo "Restoring orderlift app from image backup"
        mkdir -p "/home/frappe/frappe-bench/apps/${app}"
        cp -a "${app_backup}/." "/home/frappe/frappe-bench/apps/${app}/"
        /home/frappe/frappe-bench/env/bin/pip install -e "/home/frappe/frappe-bench/apps/${app}/"
      else
        echo "ERROR: orderlift backup missing at ${app_backup}" >&2
        return 1
      fi
    else
      bench get-app "$app" "https://github.com/frappe/${app}.git"
    fi
  fi

  # Register app in bench apps list (sites/apps.txt lives on the sites volume).
  local apps_txt="/home/frappe/frappe-bench/sites/apps.txt"
  if [[ -f "$apps_txt" ]]; then
    if ! tr -d '\r' <"$apps_txt" | grep -qx "$app"; then
      printf '%s\n' "$app" >>"$apps_txt"
    fi
  else
    printf '%s\n' "$app" >"$apps_txt"
  fi

  # Check if already installed for this site.
  if bench --site "$site" list-apps 2>/dev/null | tr -d '\r' | grep -qx "$app"; then
    echo "App already installed: ${app}"
    return 0
  fi

  echo "Installing app: ${app}"
  if [[ "$app" == "orderlift" ]]; then
    bench --site "$site" install-app "$app" --force || return 1
  else
    bench --site "$site" install-app "$app" || return 1
  fi
  bench --site "$site" migrate || return 1
  # Build just the newly installed app's assets.
  bench build --app "$app" || return 1
}

clear_site_locks() {
  local site="$1"
  local locks_dir="/home/frappe/frappe-bench/sites/${site}/locks"

  if [[ ! -d "$locks_dir" ]]; then
    return 0
  fi

  # During Coolify deployments, create-site runs before other services.
  # If a previous deploy crashed mid-install/migrate, these stale locks can block future deploys.
  rm -f \
    "${locks_dir}/install_app.lock" \
    "${locks_dir}/bench_migrate.lock" \
    "${locks_dir}/bench_build.lock" \
    2>/dev/null || true
}

post_deploy_site_maintenance() {
  local site="$1"

  # Keep runtime state in sync with app code updates shipped in new images.
  clear_site_locks "$site"
  bench --site "$site" migrate || echo "WARN: migrate failed for ${site}; continuing"
  bench --site "$site" clear-cache || true
  bench --site "$site" clear-website-cache || true
}


echo "Waiting for MariaDB at ${db_host}:${db_port} ..."
python3 - <<'PY'
import socket, time, os, sys
host=os.environ.get('DB_HOST','mariadb')
port=int(os.environ.get('DB_PORT','3306'))
for _ in range(120):
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(1)
PY

echo "Waiting for Redis services ..."
python3 - <<'PY'
import socket, time, os, sys
from urllib.parse import urlparse

def host_port(raw: str):
    s = (raw or '').strip()
    if not s:
        raise ValueError('empty redis target')

    # Accept both "redis://host:port/db" and "host:port" formats.
    if '://' not in s:
        s = 'redis://' + s

    u = urlparse(s)
    if not u.hostname or not u.port:
        raise ValueError(f'invalid redis target: {raw!r}')
    return u.hostname, int(u.port)

targets = [
    os.environ.get('REDIS_CACHE', 'redis://redis-cache:6379/0'),
    os.environ.get('REDIS_QUEUE', 'redis://redis-queue:6379/1'),
    os.environ.get('REDIS_SOCKETIO', 'redis://redis-socketio:6379/2'),
]
pending = set(host_port(t) for t in targets)
deadline = time.time() + 120

while pending and time.time() < deadline:
    for hp in list(pending):
        try:
            with socket.create_connection(hp, timeout=2):
                pending.remove(hp)
        except OSError:
            pass
    time.sleep(1)

sys.exit(0 if not pending else 1)
PY

echo "Writing global Frappe config (sites/common_site_config.json) ..."
python3 - <<PY
import json, os, tempfile

bench_dir = os.environ.get('BENCH_DIR', '/home/frappe/frappe-bench')
sites_dir = os.path.join(bench_dir, 'sites')
os.makedirs(sites_dir, exist_ok=True)

cfg = {
  'db_host': os.environ.get('DB_HOST', 'mariadb'),
  'db_port': int(os.environ.get('DB_PORT', '3306')),
  'redis_cache': os.environ.get('REDIS_CACHE', 'redis://redis-cache:6379/0'),
  'redis_queue': os.environ.get('REDIS_QUEUE', 'redis://redis-queue:6379/1'),
  'redis_socketio': os.environ.get('REDIS_SOCKETIO', 'redis://redis-socketio:6379/2'),
  'socketio_port': int(os.environ.get('SOCKETIO_PORT', '9000')),
}

target = os.path.join(sites_dir, 'common_site_config.json')
fd, tmp = tempfile.mkstemp(prefix='common_site_config.', suffix='.json', dir=sites_dir)
try:
  with os.fdopen(fd, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, sort_keys=True)
    f.write('\n')
  os.replace(tmp, target)
finally:
  try:
    os.unlink(tmp)
  except FileNotFoundError:
    pass

print('Wrote', target)
PY

if [[ -f "sites/${site_name}/site_config.json" ]]; then
  echo "Site already exists: ${site_name} (skipping create)"
  clear_site_locks "$site_name"
  ensure_site_db_user_access "$site_name"

  # Install HRMS permanently on this site (idempotent).
  # Do not continue without HRMS: ERPNext website routing references Job Opening.
  ensure_app_installed "$site_name" "hrms"

  # Install orderlift app permanently on this site (idempotent).
  repair_orderlift_module_conflicts "$site_name"
  ensure_app_installed "$site_name" "orderlift" || echo "WARN: orderlift install failed; continuing"

  # Always run maintenance on existing sites to apply pending patches and refresh caches.
  post_deploy_site_maintenance "$site_name"

  exit 0
fi

echo "Creating new site: ${site_name}"
bench new-site "$site_name" \
  --admin-password "$admin_password" \
  --mariadb-root-password "$db_root_password" \
  --db-user-host "%" \
  --install-app erpnext

ensure_site_db_user_access "$site_name"

# Install HRMS on fresh sites.
ensure_app_installed "$site_name" "hrms"

# Install orderlift on fresh sites.
repair_orderlift_module_conflicts "$site_name"
ensure_app_installed "$site_name" "orderlift" || echo "WARN: orderlift install failed; continuing"

# Run one final migrate/cache refresh once all apps are in place.
post_deploy_site_maintenance "$site_name"

echo "Site created: ${site_name}"
