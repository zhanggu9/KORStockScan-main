#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RUNNER="$PROJECT_DIR/deploy/run_ipo_listing_day_autorun.sh"
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null > "$TMP_CRON" || true
awk '!/IPO listing-day YAML-gated autorun/ && !/IPO_LISTING_DAY_AUTORUN_PREOPEN/' "$TMP_CRON" > "$TMP_CRON.filtered"
mv "$TMP_CRON.filtered" "$TMP_CRON"

cat >> "$TMP_CRON" <<EOF
# IPO listing-day YAML-gated autorun
59 8 * * 1-5 $RUNNER \$(TZ=Asia/Seoul date +\\%F) >> $PROJECT_DIR/logs/ipo_listing_day_autorun_cron.log 2>&1 # IPO_LISTING_DAY_AUTORUN_PREOPEN
EOF

crontab "$TMP_CRON"
crontab -l | sed -n '1,260p'
