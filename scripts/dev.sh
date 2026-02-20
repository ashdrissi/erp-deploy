#!/bin/bash
# ============================================================
# dev.sh — Fast developer commands for the ERP dev environment
# Usage: ./scripts/dev.sh <command>
# ============================================================

APP_CONTAINER="erp-deploy-app-1"   # adjust if your container name differs
BENCH="/home/frappe/frappe-bench"

case "$1" in

  # Rebuild CSS/JS assets for the theme (~30 seconds)
  build-theme)
    echo "🎨 Building custom_desk_theme assets..."
    docker exec -it $APP_CONTAINER bash -c "cd $BENCH && bench build --app custom_desk_theme"
    echo "✅ Done! Refresh your browser."
    ;;

  # Rebuild all app assets
  build-all)
    echo "🔨 Building all app assets..."
    docker exec -it $APP_CONTAINER bash -c "cd $BENCH && bench build"
    echo "✅ Done!"
    ;;

  # Restart the web app (Python changes)
  restart)
    echo "♻️  Restarting app container (~10s)..."
    docker compose -f docker-compose.dev.yml restart app
    echo "✅ Done!"
    ;;

  # Run database migrations (schema changes)
  migrate)
    echo "🗄️  Running migrations..."
    docker exec -it $APP_CONTAINER bash -c "cd $BENCH && bench --site \$SITE_NAME migrate"
    echo "✅ Done!"
    ;;

  # Pull latest code and restart
  pull)
    echo "⬇️  Pulling latest code from git..."
    git pull origin main
    echo "♻️  Restarting..."
    docker compose -f docker-compose.dev.yml restart app
    echo "✅ Done!"
    ;;

  # Open a shell inside the app container
  shell)
    docker exec -it $APP_CONTAINER bash
    ;;

  # Show logs
  logs)
    docker compose -f docker-compose.dev.yml logs -f app
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
