# DeepSeek Swing Pattern Lab — Phase 2 Build Report v5

작성일: `2026-05-09T17:12 KST`  
Owner: `SwingPatternLabDeepSeekPhase2`  
Status: **Phase 2 완료 + P0 Hardening 완료**  
Canonical artifacts: `2026-05-09`

---

## 1. 개요

Phase 2 목표는 Stage 1 DeepSeek Swing Pattern Lab을 postclose 자동화 체인에 연결하는 것이다. 모든 order는 `runtime_effect=false`, `allowed_runtime_apply=false`를 유지하며, live 매매 판단(주문, Gatekeeper, threshold, budget guard)을 변경하지 않는다.

---

## 2. Phase 2 연결 아키텍처

```
analysis/deepseek_swing_pattern_lab/
  └── run_all.sh 2026-05-09
        │
        ▼
src/engine/swing_pattern_lab_automation.py
  └── build_swing_pattern_lab_automation_report()
        │
        ├──► data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_*.json
        │
        ▼
src/engine/build_code_improvement_workorder.py
  └── build_code_improvement_workorder()
        │  (scalping + swing_improvement + swing_pattern_lab merge)
        │
        ├──► docs/code-improvement-workorders/code_improvement_workorder_*.md
        │
        ▼
src/engine/threshold_cycle_ev_report.py
  └── build_threshold_cycle_ev_report()
        │
        └──► data/report/threshold_cycle_ev/threshold_cycle_ev_*.json
             data/report/threshold_cycle_ev/threshold_cycle_ev_*.md
```

---

## 3. 구현 완료 항목

### 3.1 Phase 2 Baseline (§3.2–§3.5)

| 파일 | 상태 | 설명 |
|------|------|------|
| `src/engine/swing_pattern_lab_automation.py` | 완료 | DeepSeek lab output → automation report 변환. stale guard, required output check, allowed_runtime_apply 포함 |
| `src/engine/build_code_improvement_workorder.py` | 완료 | scalping + swing_improvement + swing_lab 3 source merge. dedupe by `(source_report_type, lifecycle_stage, order_id)` 및 collision warning |
| `deploy/run_threshold_cycle_postclose.sh` | 완료 | `RUN_DEEPSEEK_SWING_LAB` step, swing_pattern_lab_automation 실행 step 추가 |
| `src/engine/threshold_cycle_ev_report.py` | 완료 | `_swing_pattern_lab_automation_summary()`, EV JSON/Markdown에 swing section render |

### 3.2 1차 리뷰 대응 (4 fixes)

| # | Severity | 파일 | 변경 |
|---|----------|------|------|
| 1 | High | `swing_pattern_lab_automation.py` | `_lab_freshness()`에 `analysis_window.start == target_date == end` 검증 추가. `fresh=false`일 때 findings/orders 차단 |
| 2 | Medium | `threshold_cycle_ev_report.py` | Markdown renderer에 `## Swing Pattern Lab Automation` 섹션 추가 |
| 3 | Medium | `build_code_improvement_workorder.py` | `(source_report_type, lifecycle_stage, order_id)` 기준 dedup. collision warning을 summary와 markdown에 출력 |
| 4 | Medium | `swing_pattern_lab_automation.py` | `code_improvement_orders`에 `allowed_runtime_apply: false` 추가 |

### 3.3 2차 리뷰 대응 (2 fixes) + P0 Hardening

| # | Severity | 항목 | 변경 |
|---|----------|------|------|
| 1 | Medium | required output check | `_lab_freshness()`가 `analysis_result`, `data_quality_report`, `deepseek_payload_summary` 3종 모두 존재 확인. 누락 시 `missing_required_output:*`로 stale 처리 |
| 2 | Low | `population_split_available` | hardcoded `True` → `freshness["fresh"]` 동적 판정 |
| P0-3 | — | carryover count 분리 | stale 시 `ev_report_summary.carryover_warning_count=0`, raw warnings는 `data_quality.carryover_warnings_raw`에 보존 |
| P0-4 | — | public API export | `_automation_report_paths` → `swing_pattern_lab_automation_report_paths`. `threshold_cycle_ev_report.py`에서 private import 제거 |

---

## 4. Acceptance 검증

### 4.1 Canonical Artifact — `2026-05-09`

```json
// swing_pattern_lab_automation_2026-05-09.json
{
  "ev_report_summary": {
    "deepseek_lab_available": false,
    "stale_reason": "analysis_start_mismatch(expected=2026-05-09, actual=2026-05-08)",
    "findings_count": 0,
    "code_improvement_order_count": 0,
    "carryover_warning_count": 0,
    "population_split_available": false
  },
  "consensus_findings": [],
  "auto_family_candidates": [],
  "code_improvement_orders": [],
  "data_quality": {
    "carryover_warnings": [],
    "carryover_warnings_raw": [
      "swing_pattern_lab_deepseek_entry_gatekeeper_reject: carryover-only blocker (9 events)",
      "swing_pattern_lab_deepseek_entry_gap_block: carryover-only blocker (2 events)",
      "swing_pattern_lab_deepseek_entry_market_regime_block: carryover-only blocker (1 events)"
    ]
  }
}
```

### 4.2 Workorder — `code_improvement_workorder_2026-05-09`

| metric | value |
|--------|-------|
| `swing_lab_source_order_count` | `0` |
| `swing_pattern_lab_fresh` | `false` |
| `deepseek_lab_available` | `false` |
| `duplicate_order_warnings` | `[]` |
| stale DeepSeek order in workorder | 없음 |

### 4.3 EV Report — `threshold_cycle_ev_2026-05-09`

| metric | value |
|--------|-------|
| `swing_pattern_lab_automation.available` | `true` |
| `swing_pattern_lab_automation.deepseek_lab_available` | `false` |
| `swing_pattern_lab_automation.code_improvement_order_count` | `0` |
| `swing_pattern_lab_automation.carryover_warning_count` | `0` |
| `swing_pattern_lab_automation.population_split_available` | `false` |
| Markdown `## Swing Pattern Lab Automation` section | 렌더링됨 |

---

## 5. Test Results

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  src/tests/test_deepseek_swing_pattern_lab.py \
  src/tests/test_swing_model_selection_funnel_repair.py \
  src/tests/test_build_code_improvement_workorder.py \
  src/tests/test_threshold_cycle_ev_report.py
# 50 passed in 2.85s
```

| test file | count | highlights |
|-----------|-------|------------|
| `test_deepseek_swing_pattern_lab.py` | 29 | Stage 1 fact tables + population split + stale guard + missing output guard + allowed_runtime_apply |
| `test_swing_model_selection_funnel_repair.py` | 14 | live repair, funnel report, lifecycle audit, improvement automation |
| `test_build_code_improvement_workorder.py` | 4 | classification, limit, swing merge, dedupe |
| `test_threshold_cycle_ev_report.py` | 3 | EV report build, missing artifact warning, swing lab markdown section |

Static checks: `compileall -q src/engine src/scanners` pass, `bash -n deploy/run_threshold_cycle_postclose.sh` pass, `git diff --check` pass.

---

## 6. Phase 3 Readiness

### 6.1 현재 workorder (2026-05-09)

| order_id | decision | source |
|----------|----------|--------|
| `order_swing_lifecycle_observation_coverage` | `implement_now` | swing_improvement_automation |
| `order_swing_recommendation_db_load_gap` | `implement_now` | swing_improvement_automation |
| `order_swing_ai_contract_structured_output_eval` | `design_family_candidate` | swing_improvement_automation |
| `order_swing_scale_in_avg_down_pyramid_observation` | `design_family_candidate` | swing_improvement_automation |

모든 order는 `runtime_effect=false`, `allowed_runtime_apply=false`.

### 6.2 Fresh DeepSeek Re-entry 조건

DeepSeek lab이 workorder에 재진입하려면:
1. run_manifest.json `analysis_window.start == target_date == end`
2. outputs/ 아래 3종 (analysis_result, data_quality_report, deepseek_payload_summary) 모두 존재
3. 위 조건 충족 전까지는 `deepseek_lab_available=false` → `swing_lab_source_order_count=0`

---

## 7. 변경 파일 목록

| 파일 | 변경 종류 |
|------|-----------|
| `src/engine/swing_pattern_lab_automation.py` | 신규 + hardening |
| `src/engine/build_code_improvement_workorder.py` | swing_lab source merge + dedup |
| `src/engine/threshold_cycle_ev_report.py` | swing_lab summary + markdown section |
| `deploy/run_threshold_cycle_postclose.sh` | deepseek lab + automation step |
| `src/tests/test_deepseek_swing_pattern_lab.py` | +4 tests (stale guard, missing output, allowed_runtime_apply) |
| `src/tests/test_build_code_improvement_workorder.py` | +1 test (dedup) |
| `src/tests/test_threshold_cycle_ev_report.py` | +1 test (swing lab markdown) |
| `data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_2026-05-09.json` | canonical artifact |
| `data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_2026-05-09.md` | canonical artifact |
| `docs/code-improvement-workorders/code_improvement_workorder_2026-05-09.md` | canonical artifact |
| `data/report/threshold_cycle_ev/threshold_cycle_ev_2026-05-09.json` | canonical artifact |
| `data/report/threshold_cycle_ev/threshold_cycle_ev_2026-05-09.md` | canonical artifact |

---

## 8. Project/Calendar 동기화

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
