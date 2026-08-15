#!/usr/bin/env bash
# Install hourly cron on this machine for IMDb Wrapped data publish.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/deploy.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/deploy.env"
fi

LOG="${IMDB_SYNC_LOG:-$ROOT/data/cache/sync.log}"
MARKER="# imdb-wrapped-publish-data"
ENV_PREFIX=""
if [[ -n "${IMDB_DOCROOT:-}" ]]; then
  ENV_PREFIX+="IMDB_DOCROOT=\"$IMDB_DOCROOT\" "
fi
if [[ -n "${IMDB_DEPLOY_HOST:-}" ]]; then
  ENV_PREFIX+="IMDB_DEPLOY_HOST=\"$IMDB_DEPLOY_HOST\" "
fi
if [[ -n "${IMDB_DEPLOY_PATH:-}" ]]; then
  ENV_PREFIX+="IMDB_DEPLOY_PATH=\"$IMDB_DEPLOY_PATH\" "
fi

LINE="0 * * * * cd \"$ROOT\" && ${ENV_PREFIX}/usr/bin/env bash \"$ROOT/scripts/publish_data.sh\" >> \"$LOG\" 2>&1 $MARKER"

mkdir -p "$(dirname "$LOG")"
touch "$LOG"

existing="$(crontab -l 2>/dev/null || true)"
filtered="$(printf '%s\n' "$existing" | grep -v 'imdb-wrapped-publish-data' || true)"
{
  printf '%s\n' "$filtered"
  printf '%s\n' "$LINE"
} | crontab -

echo "Installed hourly cron:"
echo "  $LINE"
echo "Log: $LOG"
crontab -l | grep 'imdb-wrapped-publish-data' || true
