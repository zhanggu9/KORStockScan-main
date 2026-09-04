#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/KORStockScan"
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null > "$TMP_CRON" || true

awk '!/SHADOW_CANARY_PREOPEN/ && !/SHADOW_CANARY_OPEN_CHECK/ && !/SHADOW_CANARY_MIDMORNING/ && !/SHADOW_CANARY_POSTCLOSE/' "$TMP_CRON" > "$TMP_CRON.filtered"
mv "$TMP_CRON.filtered" "$TMP_CRON"

crontab "$TMP_CRON"
crontab -l | sed -n '1,220p'
