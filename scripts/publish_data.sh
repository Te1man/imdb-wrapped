#!/usr/bin/env bash
# Refresh IMDb data and publish JSON + OG cards.
# Prefer IMDB_DOCROOT (on the server). Otherwise rsync via IMDB_DEPLOY_HOST + IMDB_DEPLOY_PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/deploy.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/deploy.env"
fi

HOST="${IMDB_DEPLOY_HOST:-}"
REMOTE="${IMDB_DEPLOY_PATH:-}"
DOCROOT="${IMDB_DOCROOT:-}"

cd "$ROOT"
python3 scripts/sync_live.py

if [[ -n "$DOCROOT" ]]; then
  mkdir -p "$DOCROOT/data" "$DOCROOT/og"
  rsync -a --delete "$ROOT/public/data/" "$DOCROOT/data/"
  if [[ -d "$ROOT/public/og" ]]; then
    rsync -a "$ROOT/public/og/" "$DOCROOT/og/"
  fi
  echo "Published data locally to $DOCROOT"
  exit 0
fi

if [[ -z "$HOST" || -z "$REMOTE" ]]; then
  echo "Set IMDB_DOCROOT (on the server), or IMDB_DEPLOY_HOST + IMDB_DEPLOY_PATH." >&2
  echo "Copy deploy.example.env → deploy.env and edit it." >&2
  exit 1
fi

rsync -avz --delete "$ROOT/public/data/" "$HOST:$REMOTE/data/"
if [[ -d "$ROOT/public/og" ]]; then
  rsync -avz "$ROOT/public/og/" "$HOST:$REMOTE/og/"
fi
echo "Published data to $HOST:$REMOTE"
