#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
VENV_PY="${VENV_PY:-$PROJECT_DIR/.venv/bin/python}"
TARGET_DATE="${1:-$(TZ=Asia/Seoul date +%F)}"
RUN_RECOMMEND_DAILY_V2="${RUN_RECOMMEND_DAILY_V2:-false}"

cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs/swing_daily_simulation"
STATUS_DIR="$PROJECT_DIR/data/report/swing_daily_simulation/status"
LOCK_ROOT="$PROJECT_DIR/tmp"
LOG_PATH="$LOG_DIR/swing_daily_simulation_${TARGET_DATE}.log"
STATUS_PATH="$STATUS_DIR/swing_daily_simulation_${TARGET_DATE}.status.json"
LOCK_DIR="$LOCK_ROOT/swing_daily_simulation_${TARGET_DATE}.lock"
STARTED_AT="$(TZ=Asia/Seoul date --iso-8601=seconds)"

mkdir -p "$LOG_DIR" "$STATUS_DIR" "$LOCK_ROOT"
exec > >(tee -a "$LOG_PATH") 2>&1

write_status() {
  local status="$1"
  local exit_code="$2"
  local reason="$3"
  local finished_at
  finished_at="$(TZ=Asia/Seoul date --iso-8601=seconds)"
  printf '{\n' > "$STATUS_PATH"
  printf '  "schema_version": 1,\n' >> "$STATUS_PATH"
  printf '  "report_type": "swing_daily_simulation_status",\n' >> "$STATUS_PATH"
  printf '  "target_date": "%s",\n' "$TARGET_DATE" >> "$STATUS_PATH"
  printf '  "status": "%s",\n' "$status" >> "$STATUS_PATH"
  printf '  "reason": "%s",\n' "$reason" >> "$STATUS_PATH"
  printf '  "started_at": "%s",\n' "$STARTED_AT" >> "$STATUS_PATH"
  printf '  "finished_at": "%s",\n' "$finished_at" >> "$STATUS_PATH"
  printf '  "exit_code": %s,\n' "$exit_code" >> "$STATUS_PATH"
  printf '  "log_path": "%s",\n' "$LOG_PATH" >> "$STATUS_PATH"
  printf '  "json_artifact": "%s",\n' "$PROJECT_DIR/data/report/swing_daily_simulation/swing_daily_simulation_${TARGET_DATE}.json" >> "$STATUS_PATH"
  printf '  "markdown_artifact": "%s",\n' "$PROJECT_DIR/data/report/swing_daily_simulation/swing_daily_simulation_${TARGET_DATE}.md" >> "$STATUS_PATH"
  printf '  "funnel_json_artifact": "%s",\n' "$PROJECT_DIR/data/report/swing_selection_funnel/swing_selection_funnel_${TARGET_DATE}.json" >> "$STATUS_PATH"
  printf '  "runtime_change": false\n' >> "$STATUS_PATH"
  printf '}\n' >> "$STATUS_PATH"
}

if [[ ! -x "$VENV_PY" ]]; then
  write_status "failed" 127 "venv_python_missing"
  echo "venv python missing: $VENV_PY"
  exit 127
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  write_status "skipped" 75 "lock_exists"
  echo "swing daily simulation already running for ${TARGET_DATE}: ${LOCK_DIR}"
  exit 75
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

set +e
if [[ "$RUN_RECOMMEND_DAILY_V2" = "true" || "$RUN_RECOMMEND_DAILY_V2" = "1" ]]; then
  PYTHONPATH=. "$VENV_PY" -m src.model.recommend_daily_v2
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    write_status "failed" "$rc" "recommend_daily_v2_failed"
    exit "$rc"
  fi
fi

PYTHONPATH=. "$VENV_PY" -m src.engine.swing_daily_simulation_report --date "$TARGET_DATE"
rc=$?
if [[ "$rc" -eq 0 ]]; then
  PYTHONPATH=. "$VENV_PY" -m src.engine.swing_selection_funnel_report "$TARGET_DATE"
  rc=$?
fi
set -e

if [[ "$rc" -eq 0 ]]; then
  write_status "succeeded" 0 "completed"
else
  write_status "failed" "$rc" "report_command_failed"
fi
exit "$rc"
