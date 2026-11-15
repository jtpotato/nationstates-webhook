#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DB="$ROOT/.state/announcements.sqlite3"
if [ -f "$DB" ]; then
  rm "$DB"
  rm -f "$DB-wal" "$DB-shm"
  echo "Cleared announcement storage. The next run will post all current announcements again."
else
  echo "No persisted storage found."
fi
