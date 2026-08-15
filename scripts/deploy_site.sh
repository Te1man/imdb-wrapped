#!/usr/bin/env bash
# Build and deploy the static UI without clobbering live data/ from cron.
#
# Usage:
#   bash scripts/deploy_site.sh           # build + UI + sync app code
#   bash scripts/deploy_site.sh --with-data  # also push local public/data
#   bash scripts/deploy_site.sh --skip-build # UI only from existing dist/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/deploy.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/deploy.env"
fi

HOST="${IMDB_DEPLOY_HOST:?Set IMDB_DEPLOY_HOST in deploy.env}"
DOCROOT="${IMDB_DOCROOT:?Set IMDB_DOCROOT in deploy.env}"
APP="${IMDB_APP_PATH:-/opt/imdb-wrapped}"

WITH_DATA=0
SKIP_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --with-data) WITH_DATA=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 1
      ;;
  esac
done

cd "$ROOT"

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  npm run build:imdb
fi

if [[ ! -d dist ]]; then
  echo "Missing dist/ — run without --skip-build first." >&2
  exit 1
fi

echo "Deploying UI to $HOST:$DOCROOT (preserving server data/)"
# Never --delete data/: hourly cron owns live stats/watchlist on the server.
rsync -avz --delete \
  --exclude data/ \
  dist/ "$HOST:$DOCROOT/"

if [[ "$WITH_DATA" -eq 1 ]]; then
  echo "Also publishing local public/data/ (explicit)"
  mkdir -p public/data
  rsync -avz public/data/ "$HOST:$DOCROOT/data/"
  if [[ -d public/og ]]; then
    rsync -avz public/og/ "$HOST:$DOCROOT/og/"
  fi
fi

echo "Syncing app code to $HOST:$APP"
rsync -az --delete \
  --exclude .git \
  --exclude node_modules \
  --exclude dist \
  --exclude deploy.env \
  --exclude .env \
  --exclude 'data/cache' \
  ./ "$HOST:$APP/"

# Durable RU title/poster cache must survive app rsync excludes.
if [[ -f data/cache/ru-locale.json ]]; then
  ssh -o BatchMode=yes "$HOST" "mkdir -p '$APP/data/cache'"
  scp -o BatchMode=yes data/cache/ru-locale.json "$HOST:$APP/data/cache/ru-locale.json"
fi

echo "Deploy done."
echo "  site: $DOCROOT"
echo "  app:  $APP"
echo "  tip:  data refresh is hourly via publish_data.sh on the server"
