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
  exit 0
fi

echo "Creating new site: ${site_name}"
bench new-site "$site_name" \
  --admin-password "$admin_password" \
  --mariadb-root-password "$db_root_password" \
  --install-app erpnext

echo "Site created: ${site_name}"
