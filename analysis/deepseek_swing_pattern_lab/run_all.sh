#!/usr/bin/env bash
# DeepSeek Swing Pattern Lab — unattended run-all pipeline
#
# Usage: bash analysis/deepseek_swing_pattern_lab/run_all.sh [target_date]
#
# If target_date is given (YYYY-MM-DD), it sets both ANALYSIS_START_DATE and
# ANALYSIS_END_DATE to that single date.  Without arguments, today is used.
# Set both env vars explicitly to scan a range:
#   ANALYSIS_START_DATE=... ANALYSIS_END_DATE=... bash .../run_all.sh
#
# This script runs the full pattern lab pipeline:
# 1. prepare_dataset.py  — generate fact tables and data quality report
# 2. analyze_swing_patterns.py  — analyze patterns and produce findings
# 3. build_deepseek_payload.py  — build DeepSeek LLM payload and final reports

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

TARGET_DATE="${1:-$(date '+%Y-%m-%d')}"

if [[ -z "${ANALYSIS_START_DATE:-}" ]]; then
    export ANALYSIS_START_DATE="$TARGET_DATE"
fi
if [[ -z "${ANALYSIS_END_DATE:-}" ]]; then
    export ANALYSIS_END_DATE="$TARGET_DATE"
fi

echo "=== DeepSeek Swing Pattern Lab — Run All ==="
echo "Project root: $PROJECT_ROOT"
echo "Target date: $TARGET_DATE"
echo "Range: ${ANALYSIS_START_DATE} ~ ${ANALYSIS_END_DATE}"
echo "Start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""

# Step 1: Prepare fact tables
echo ">>> Step 1/3: prepare_dataset.py"
PYTHONPATH=. .venv/bin/python analysis/deepseek_swing_pattern_lab/prepare_dataset.py
echo ""

# Step 2: Analyze swing patterns
echo ">>> Step 2/3: analyze_swing_patterns.py"
PYTHONPATH=. .venv/bin/python analysis/deepseek_swing_pattern_lab/analyze_swing_patterns.py
echo ""

# Step 3: Build DeepSeek payload and final reports
echo ">>> Step 3/3: build_deepseek_payload.py"
PYTHONPATH=. .venv/bin/python analysis/deepseek_swing_pattern_lab/build_deepseek_payload.py
echo ""

echo "=== DeepSeek Swing Pattern Lab — Complete ==="
echo "End: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Outputs: analysis/deepseek_swing_pattern_lab/outputs/"

ls -la analysis/deepseek_swing_pattern_lab/outputs/
