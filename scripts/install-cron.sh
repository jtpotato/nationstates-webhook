#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
[[ -f .env ]] || { echo "Missing $ROOT/.env (copy .env.example and add your webhook URL)" >&2; exit 1; }
uv sync
uv run playwright install chromium
mkdir -p "$ROOT/.state"

UV="$(command -v uv)"
JOB="0 9 * * * cd '$ROOT' && '$UV' run --project '$ROOT' python '$ROOT/ns_news_webhook.py' >> '$ROOT/.state/cron.log' 2>&1 # ns-news-webhook"
CURRENT="$(crontab -l 2>/dev/null || true)"
if grep -Fq '# ns-news-webhook' <<< "$CURRENT"; then
  CURRENT="$(grep -Fv '# ns-news-webhook' <<< "$CURRENT")"
fi
{ [[ -z "$CURRENT" ]] || printf '%s\n' "$CURRENT"; printf '%s\n' "$JOB"; } | crontab -
echo "Installed daily 09:00 cron job (system local time)."
