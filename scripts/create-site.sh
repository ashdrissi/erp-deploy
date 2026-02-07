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

def host_port(s: str):
    if '://' in s:
        s = s.split('://', 1)[1]
    host, port = s.rsplit(':', 1)
    return host, int(port)

targets = [
    os.environ.get('REDIS_CACHE', 'redis-cache:6379'),
    os.environ.get('REDIS_QUEUE', 'redis-queue:6379'),
    os.environ.get('REDIS_SOCKETIO', 'redis-socketio:6379'),
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

echo "Writing global Frappe config (common_site_config.json) ..."
bench set-config -g db_host "$db_host"
bench set-config -g db_port "$db_port"
bench set-config -g redis_cache "$redis_cache"
bench set-config -g redis_queue "$redis_queue"
bench set-config -g redis_socketio "$redis_socketio"
bench set-config -g socketio_port "$socketio_port"

if [[ -f "sites/${site_name}/site_config.json" ]]; then
  echo "Site already exists: ${site_name} (skipping create)"
  exit 0
fi

echo "Creating new site: ${site_name}"
bench new-site "$site_name" \
  --admin-password "$admin_password" \
  --mariadb-root-password "$db_root_password" \
  --install-app erpnext

echo "Site created: ${site_name}"
