#!/usr/bin/env bash
# One-shot: push sync pipeline to your VPS and install hourly cron there.
# Requires deploy.env (see deploy.example.env).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/deploy.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/deploy.env"
fi

HOST="${IMDB_DEPLOY_HOST:?Set IMDB_DEPLOY_HOST in deploy.env (e.g. root@your.server)}"
REMOTE_APP="${IMDB_APP_PATH:-/opt/imdb-wrapped}"
DOCROOT="${IMDB_DOCROOT:?Set IMDB_DOCROOT in deploy.env (web root of the built site)}"
SYNC_LOG="${IMDB_SYNC_LOG:-/var/log/imdb-wrapped-sync.log}"

echo "Installing python3-pil on $HOST..."
ssh "$HOST" 'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq python3-pil curl >/dev/null'

echo "Syncing app to $HOST:$REMOTE_APP ..."
ssh "$HOST" "mkdir -p '$REMOTE_APP'"
rsync -az --delete \
  --exclude node_modules \
  --exclude dist \
  --exclude .git \
  --exclude .vite \
  --exclude deploy.env \
  --exclude 'public/og/*.jpg' \
  --exclude 'data/raw' \
  --exclude 'data/cache' \
  "$ROOT/" "$HOST:$REMOTE_APP/"

# Keep durable RU title/poster cache on the server across syncs.
if [[ -f "$ROOT/data/cache/ru-locale.json" ]]; then
  ssh "$HOST" "mkdir -p '$REMOTE_APP/data/cache'"
  scp -q "$ROOT/data/cache/ru-locale.json" "$HOST:$REMOTE_APP/data/cache/ru-locale.json"
fi

# Keep server-side deploy.env so cron knows the docroot
ssh "$HOST" "cat > '$REMOTE_APP/deploy.env' <<EOF
IMDB_DOCROOT=$DOCROOT
IMDB_SYNC_LOG=$SYNC_LOG
IMDB_APP_PATH=$REMOTE_APP
EOF"

echo "Installing VPS cron..."
ssh "$HOST" "chmod +x '$REMOTE_APP'/scripts/*.sh '$REMOTE_APP'/scripts/*.py && IMDB_DOCROOT='$DOCROOT' IMDB_SYNC_LOG='$SYNC_LOG' bash '$REMOTE_APP'/scripts/install_cron.sh"

echo "Done. Hourly sync runs on $HOST at $REMOTE_APP → $DOCROOT"
