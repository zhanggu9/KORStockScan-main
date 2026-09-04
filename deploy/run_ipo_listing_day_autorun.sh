#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
VENV_PY="${VENV_PY:-$PROJECT_DIR/.venv/bin/python}"
TARGET_DATE="${1:-$(TZ=Asia/Seoul date +%F)}"
CONFIG_PATH="${IPO_LISTING_DAY_CONFIG_PATH:-$PROJECT_DIR/configs/ipo_listing_day_${TARGET_DATE}.yaml}"
POLL_SEC="${IPO_LISTING_DAY_POLL_SEC:-0.2}"

cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs/ipo_listing_day"
STATUS_DIR="$PROJECT_DIR/data/ipo_listing_day/status"
LOCK_ROOT="$PROJECT_DIR/tmp"
LOG_PATH="$LOG_DIR/ipo_listing_day_${TARGET_DATE}.log"
STATUS_PATH="$STATUS_DIR/ipo_listing_day_${TARGET_DATE}.status.json"
LOCK_DIR="$LOCK_ROOT/ipo_listing_day_${TARGET_DATE}.lock"
DRY_SELECT_PATH="$STATUS_DIR/ipo_listing_day_${TARGET_DATE}.dry_select.json"
STARTED_AT="$(TZ=Asia/Seoul date --iso-8601=seconds)"
RUNNER_INVOKED=false

mkdir -p "$LOG_DIR" "$STATUS_DIR" "$LOCK_ROOT"
exec > >(tee -a "$LOG_PATH") 2>&1

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

write_status() {
  local status="$1"
  local exit_code="$2"
  local reason="$3"
  local finished_at
  finished_at="$(TZ=Asia/Seoul date --iso-8601=seconds)"
  printf '{\n' > "$STATUS_PATH"
  printf '  "schema_version": 1,\n' >> "$STATUS_PATH"
  printf '  "runner": "ipo_listing_day_autorun",\n' >> "$STATUS_PATH"
  printf '  "target_date": "%s",\n' "$(json_escape "$TARGET_DATE")" >> "$STATUS_PATH"
  printf '  "status": "%s",\n' "$(json_escape "$status")" >> "$STATUS_PATH"
  printf '  "reason": "%s",\n' "$(json_escape "$reason")" >> "$STATUS_PATH"
  printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")" >> "$STATUS_PATH"
  printf '  "finished_at": "%s",\n' "$(json_escape "$finished_at")" >> "$STATUS_PATH"
  printf '  "exit_code": %s,\n' "$exit_code" >> "$STATUS_PATH"
  printf '  "config_path": "%s",\n' "$(json_escape "$CONFIG_PATH")" >> "$STATUS_PATH"
  printf '  "log_path": "%s",\n' "$(json_escape "$LOG_PATH")" >> "$STATUS_PATH"
  printf '  "dry_select_path": "%s",\n' "$(json_escape "$DRY_SELECT_PATH")" >> "$STATUS_PATH"
  printf '  "summary_artifact": "%s",\n' "$(json_escape "$PROJECT_DIR/data/ipo_listing_day/${TARGET_DATE}/summary.md")" >> "$STATUS_PATH"
  printf '  "runtime_change": false,\n' >> "$STATUS_PATH"
  printf '  "runner_invoked": %s\n' "$([[ "$RUNNER_INVOKED" == "true" ]] && printf true || printf false)" >> "$STATUS_PATH"
  printf '}\n' >> "$STATUS_PATH"
}

if [[ ! -x "$VENV_PY" ]]; then
  write_status "failed" 127 "venv_python_missing"
  echo "venv python missing: $VENV_PY"
  exit 127
fi

weekday="$(TZ=Asia/Seoul date -d "$TARGET_DATE" +%u 2>/dev/null || TZ=Asia/Seoul date +%u)"
if [[ "$weekday" -ge 6 ]]; then
  write_status "skipped" 0 "weekend"
  echo "IPO listing-day autorun skipped: weekend target_date=$TARGET_DATE"
  exit 0
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
  write_status "skipped" 0 "config_missing"
  echo "IPO listing-day autorun skipped: config not found: $CONFIG_PATH"
  exit 0
fi

if [[ -f "$PROJECT_DIR/data/ipo_listing_day/STOP" ]]; then
  write_status "skipped" 0 "manual_stop_file"
  echo "IPO listing-day autorun skipped: STOP file exists"
  exit 0
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  write_status "skipped" 75 "lock_exists"
  echo "IPO listing-day autorun already running for ${TARGET_DATE}: ${LOCK_DIR}"
  exit 75
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

set +e
PYTHONPATH=. "$VENV_PY" -m src.engine.ipo_listing_day_runner \
  --config "$CONFIG_PATH" \
  --dry-select > "$DRY_SELECT_PATH"
dry_rc=$?
set -e

if [[ "$dry_rc" -ne 0 ]]; then
  if [[ -s "$DRY_SELECT_PATH" ]] && PYTHONPATH=. "$VENV_PY" - "$DRY_SELECT_PATH" <<'PY'
import json
import sys
text = open(sys.argv[1], encoding="utf-8").read()
start = text.find("{")
if start < 0:
    raise SystemExit(2)
data = json.loads(text[start:])
raise SystemExit(0 if not data.get("targets") else 1)
PY
  then
    write_status "skipped" 0 "no_enabled_target_for_trade_date"
    echo "IPO listing-day autorun skipped: no enabled target for trade_date in $CONFIG_PATH"
    exit 0
  fi
  write_status "failed" "$dry_rc" "dry_select_failed"
  echo "IPO listing-day autorun failed: dry-select failed rc=$dry_rc"
  exit "$dry_rc"
fi

target_count="$(PYTHONPATH=. "$VENV_PY" - "$DRY_SELECT_PATH" <<'PY'
import json
import sys
text = open(sys.argv[1], encoding="utf-8").read()
start = text.find("{")
if start < 0:
    raise SystemExit(2)
data = json.loads(text[start:])
print(len(data.get("targets") or []))
PY
)"
if [[ "$target_count" -le 0 ]]; then
  write_status "skipped" 0 "no_enabled_target_for_trade_date"
  echo "IPO listing-day autorun skipped: no enabled target for trade_date in $CONFIG_PATH"
  exit 0
fi

echo "IPO listing-day autorun starting: target_date=$TARGET_DATE config=$CONFIG_PATH targets=$target_count"
RUNNER_INVOKED=true
set +e
PYTHONPATH=. "$VENV_PY" -m src.engine.ipo_listing_day_runner \
  --config "$CONFIG_PATH" \
  --poll-sec "$POLL_SEC"
run_rc=$?
set -e

if [[ "$run_rc" -eq 0 ]]; then
  write_status "succeeded" 0 "completed"
else
  write_status "failed" "$run_rc" "runner_failed"
fi
exit "$run_rc"
