#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="$ROOT/.state/announcements.sqlite3"
if [[ -f "$DB" ]]; then
  rm -- "$DB"
  rm -f -- "$DB-wal" "$DB-shm"
  echo "Cleared announcement storage. The next run will post all current announcements again."
else
  echo "No persisted storage found."
fi
