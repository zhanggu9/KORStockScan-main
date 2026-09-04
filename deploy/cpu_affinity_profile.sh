#!/usr/bin/env bash

korstockscan_nproc() {
  local detected
  detected="${KORSTOCKSCAN_NPROC_OVERRIDE:-}"
  if [[ -z "$detected" ]]; then
    detected="$(nproc 2>/dev/null || echo 1)"
  fi
  if [[ "$detected" =~ ^[0-9]+$ ]] && [[ "$detected" -gt 0 ]]; then
    echo "$detected"
  else
    echo 1
  fi
}

korstockscan_default_cpu_affinity() {
  local role="${1:-background}"
  local cpu_count
  cpu_count="$(korstockscan_nproc)"

  if [[ "$cpu_count" -le 1 ]]; then
    echo ""
    return 0
  fi

  case "$role" in
    bot)
      if [[ "$cpu_count" -ge 4 ]]; then
        echo "0-1"
      else
        echo "0"
      fi
      ;;
    monitor|panic|threshold|sentinel|background)
      if [[ "$cpu_count" -ge 4 ]]; then
        echo "2-3"
      elif [[ "$cpu_count" -eq 3 ]]; then
        echo "1-2"
      else
        echo "1"
      fi
      ;;
    health|sampler)
      if [[ "$cpu_count" -ge 4 ]]; then
        echo "3"
      elif [[ "$cpu_count" -eq 3 ]]; then
        echo "2"
      else
        echo "1"
      fi
      ;;
    *)
      if [[ "$cpu_count" -ge 4 ]]; then
        echo "2-3"
      elif [[ "$cpu_count" -eq 3 ]]; then
        echo "1-2"
      else
        echo "1"
      fi
      ;;
  esac
}

korstockscan_apply_taskset() {
  local affinity="$1"
  shift
  if command -v taskset >/dev/null 2>&1 && [[ -n "$affinity" ]] && [[ "$(korstockscan_nproc)" -gt 1 ]]; then
    taskset -c "$affinity" "$@"
  else
    "$@"
  fi
}
