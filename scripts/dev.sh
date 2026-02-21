#!/bin/bash
set -euo pipefail
# ============================================================
# dev.sh — Fast developer commands for the ERP dev environment
# Usage: ./scripts/dev.sh <command>
# ============================================================

APP_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E '(^app-|-app-[0-9]+$)' | head -n 1 || true)
BENCH="/home/frappe/frappe-bench"

if [[ -z "${APP_CONTAINER}" ]]; then
  echo "❌ Could not find a running app container." >&2
  echo "   Start the dev stack first, then retry." >&2
  exit 1
fi

case "$1" in

  # Rebuild CSS/JS assets for the theme (~30 seconds)
  build-theme)
    echo "🎨 Building custom_desk_theme assets..."
    docker exec "$APP_CONTAINER" bash -lc "cd $BENCH && bench build --app custom_desk_theme && bench --site \$SITE_NAME clear-cache"
    echo "✅ Done! Refresh your browser."
    ;;

  # Rebuild all app assets
  build-all)
    echo "🔨 Building all app assets..."
    docker exec "$APP_CONTAINER" bash -lc "cd $BENCH && bench build && bench --site \$SITE_NAME clear-cache"
    echo "✅ Done!"
    ;;

  # Restart the web app (Python changes)
  restart)
    echo "♻️  Restarting app container (~10s)..."
    docker restart "$APP_CONTAINER" >/dev/null
    echo "✅ Done!"
    ;;

  # Run database migrations (schema changes)
  migrate)
    echo "🗄️  Running migrations..."
    docker exec "$APP_CONTAINER" bash -lc "cd $BENCH && bench --site \$SITE_NAME migrate"
    echo "✅ Done!"
    ;;

  # Pull latest code and restart
  pull)
    echo "⬇️  Pulling latest code from git..."
    git pull origin main
    echo "♻️  Restarting..."
    docker restart "$APP_CONTAINER" >/dev/null
    echo "✅ Done!"
    ;;

  # Open a shell inside the app container
  shell)
    docker exec -it "$APP_CONTAINER" bash
    ;;

  # Show logs
  logs)
    docker logs -f "$APP_CONTAINER"
    ;;

  *)
    echo ""
    echo "Usage: ./scripts/dev.sh <command>"
    echo ""
    echo "Commands:"
    echo "  build-theme  — Recompile CSS/JS for custom_desk_theme (~30s)"
    echo "  build-all    — Recompile all app assets"
    echo "  restart      — Restart gunicorn (Python changes, ~10s)"
    echo "  migrate      — Run DB migrations (schema changes)"
    echo "  pull         — git pull + restart"
    echo "  shell        — Open bash inside app container"
    echo "  logs         — Tail app logs"
    echo ""
    ;;
esac
