# Code Improvement Workorder - 2026-05-08

## 목적

- Pattern lab이 생성한 `code_improvement_order`를 Codex 실행용 작업지시서로 변환한다.
- 이 문서는 repo/runtime을 직접 변경하지 않는다. 사용자가 이 문서를 Codex 세션에 넣고 구현을 요청하는 지점만 사람 개입으로 남긴다.
- 구현 후 자동화체인 재투입은 다음 postclose report, threshold calibration, daily EV report가 담당한다.

## Source

- pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/scalping_pattern_lab_automation/scalping_pattern_lab_automation_2026-05-08.json`
- threshold_cycle_ev: `/home/ubuntu/KORStockScan/data/report/threshold_cycle_ev/threshold_cycle_ev_2026-05-08.json`
- generated_at: `2026-05-08T20:21:42+09:00`

## 운영 원칙

- `runtime_effect=false` order만 구현 대상으로 본다.
- fallback 재개, shadow 재개, safety guard 우회는 구현하지 않는다.
- runtime 영향이 생길 수 있는 변경은 feature flag, threshold family metadata, provenance, safety guard를 같이 닫는다.
- 새 family는 `allowed_runtime_apply=false`에서 시작하고, 구현/테스트/guard 완료 후에만 auto_bounded_live 후보가 될 수 있다.
- 구현 후에는 관련 테스트와 parser 검증을 실행하고, 다음 postclose daily EV에서 metric을 확인한다.

## Summary

- source_order_count: `14`
- selected_order_count: `12`
- decision_counts: `{'implement_now': 1, 'attach_existing_family': 2, 'design_family_candidate': 2, 'defer_evidence': 5, 'reject': 4}`
- gemini_fresh: `True`
- claude_fresh: `True`
- daily_ev_available: `True`

## 실행 결과

- 판정: `1~5번 실행 완료`, `6~10번 evidence 보류 유지`, `11~12번 reject 유지`.
- 근거: runtime 판단값은 변경하지 않고 report/provenance/threshold-cycle source bundle만 보강했다. `latency_guard_miss_ev_recovery`는 `pre_submit_price_guard` calibration source로 연결했고, `blocked_ai_score` 선후행 EV는 `score65_74_recovery_probe` source metric으로 흡수했다. `liquidity_gate_refined_candidate`, `overbought_gate_refined_candidate`는 새 report-only family 후보로 만들되 `allowed_runtime_apply=false`를 유지했다.
- 다음 액션: 다음 postclose 자동화체인에서 `missed_entry_counterfactual`, `performance_tuning`, `threshold_cycle`, `threshold_cycle_ev`가 새 필드를 다시 읽어 EV 리포트에 반영한다. 신규 family 후보가 sample floor와 guard를 통과하더라도 구현/테스트/provenance가 닫히기 전까지 runtime apply 금지다.

검증 결과:

- `PYTHONPATH=. .venv/bin/python -m py_compile src/engine/sniper_missed_entry_counterfactual.py src/engine/sniper_performance_tuning_report.py src/engine/daily_threshold_cycle_report.py`
- `PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_missed_entry_counterfactual.py src/tests/test_performance_tuning_report.py::test_performance_tuning_report_builds_metrics src/tests/test_daily_threshold_cycle_report.py::test_threshold_cycle_report_marks_calibration_sample_and_live_risk_states src/tests/test_daily_threshold_cycle_report.py::test_threshold_cycle_report_routes_entry_filter_ev_sources_to_calibration_families`
- `PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_missed_entry_counterfactual.py src/tests/test_performance_tuning_report.py src/tests/test_daily_threshold_cycle_report.py src/tests/test_build_code_improvement_workorder.py src/tests/test_threshold_cycle_ev_report.py` -> `56 passed`
- `bash -n deploy/run_threshold_cycle_preopen.sh deploy/run_threshold_cycle_calibration.sh deploy/run_threshold_cycle_postclose.sh deploy/install_threshold_cycle_cron.sh`
- `PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500` -> `4`개 backlog 파싱
- `git diff --check`

운영 메모:

- deterministic `daily_threshold_cycle_report`와 `threshold_cycle_ev_report`는 재생성했다.
- OpenAI AI correction provider는 완료까지 대기해 재측정했다. `real 744.78s`가 소요됐고 `OPENAI_API_KEY_2`, `gpt-5.5`, `reasoning_effort=high`, `schema_name=threshold_ai_correction_v1`, `ai_status=parsed`, `runtime_change=false`로 완료됐다. cron timeout/운영 확인 기준은 최소 15분 이상으로 잡는다.

## Codex 실행 지시

아래 order를 위에서부터 순서대로 처리한다. 각 order는 `판정 -> 근거 -> 다음 액션`으로 닫고, 코드 변경 시 관련 문서와 테스트를 함께 갱신한다.

필수 검증:

```bash
PYTHONPATH=. .venv/bin/pytest -q <관련 테스트 파일>
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
git diff --check
```

threshold/postclose 체인 영향 시 추가 검증:

```bash
bash -n deploy/run_threshold_cycle_preopen.sh deploy/run_threshold_cycle_calibration.sh deploy/run_threshold_cycle_postclose.sh
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_daily_threshold_cycle_report.py src/tests/test_threshold_cycle_preopen_apply.py src/tests/test_threshold_cycle_ev_report.py
```

## Implementation Orders

### 1. `order_latency_guard_miss_ev_recovery`

- title: latency guard miss EV recovery
- decision: `implement_now`
- decision_reason: instrumentation/provenance work can improve attribution without direct runtime mutation
- target_subsystem: `runtime_instrumentation`
- route: `instrumentation_order`
- mapped_family: `-`
- confidence: `consensus`
- priority: `3`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/sniper_performance_tuning_report.py`, `src/engine/daily_threshold_cycle_report.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, next postclose report must show source freshness or warning reduction.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 2. `order_ai_threshold_dominance`

- title: AI threshold dominance
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- target_subsystem: `entry_funnel`
- route: `existing_family`
- mapped_family: `score65_74_recovery_probe`
- confidence: `consensus`
- priority: `1`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 3. `order_ai_threshold_miss_ev_recovery`

- title: AI threshold miss EV recovery
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- target_subsystem: `entry_funnel`
- route: `existing_family`
- mapped_family: `score65_74_recovery_probe`
- confidence: `consensus`
- priority: `2`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 4. `order_liquidity_gate_miss_ev_recovery`

- title: liquidity gate miss EV recovery
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- target_subsystem: `entry_filter_quality`
- route: `auto_family_candidate`
- mapped_family: `-`
- confidence: `consensus`
- priority: `4`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

### 5. `order_overbought_gate_miss_ev_recovery`

- title: overbought gate miss EV recovery
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- target_subsystem: `entry_filter_quality`
- route: `auto_family_candidate`
- mapped_family: `-`
- confidence: `consensus`
- priority: `5`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

### 6. `order_latency_canary_tag_완화_1축_canary_승인`

- title: latency canary tag 완화 1축 canary 승인
- decision: `defer_evidence`
- decision_reason: single-lab finding; keep as low-confidence backlog until repeated by fresh lab or EV report
- target_subsystem: `runtime_instrumentation`
- route: `instrumentation_order`
- mapped_family: `-`
- confidence: `solo`
- priority: `6`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/sniper_performance_tuning_report.py`, `src/engine/daily_threshold_cycle_report.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Re-evaluate in the next postclose pattern lab automation and daily EV report.

실행 기준:

- 구현하지 말고 부족한 evidence와 다음 확인 artifact를 명시한다.
- 필요한 경우 report warning 또는 다음 pattern lab 재평가 항목으로만 남긴다.

### 7. `order_ai_threshold_miss_ev_회수_조건_점검`

- title: AI threshold miss EV 회수 조건 점검
- decision: `defer_evidence`
- decision_reason: single-lab finding; keep as low-confidence backlog until repeated by fresh lab or EV report
- target_subsystem: `entry_funnel`
- route: `existing_family`
- mapped_family: `score65_74_recovery_probe`
- confidence: `solo`
- priority: `7`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Re-evaluate in the next postclose pattern lab automation and daily EV report.

실행 기준:

- 구현하지 말고 부족한 evidence와 다음 확인 artifact를 명시한다.
- 필요한 경우 report warning 또는 다음 pattern lab 재평가 항목으로만 남긴다.

### 8. `order_overbought_gate_miss_ev_회수_조건_점검`

- title: overbought gate miss EV 회수 조건 점검
- decision: `defer_evidence`
- decision_reason: single-lab finding; keep as low-confidence backlog until repeated by fresh lab or EV report
- target_subsystem: `entry_filter_quality`
- route: `auto_family_candidate`
- mapped_family: `-`
- confidence: `solo`
- priority: `8`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Re-evaluate in the next postclose pattern lab automation and daily EV report.

실행 기준:

- 구현하지 말고 부족한 evidence와 다음 확인 artifact를 명시한다.
- 필요한 경우 report warning 또는 다음 pattern lab 재평가 항목으로만 남긴다.

### 9. `order_split_entry_scalp_soft_stop_pct_손실패턴_분해`

- title: split-entry / scalp_soft_stop_pct 손실패턴 분해
- decision: `defer_evidence`
- decision_reason: single-lab finding; keep as low-confidence backlog until repeated by fresh lab or EV report
- target_subsystem: `holding_exit`
- route: `existing_family`
- mapped_family: `soft_stop_whipsaw_confirmation`
- confidence: `solo`
- priority: `11`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Re-evaluate in the next postclose pattern lab automation and daily EV report.

실행 기준:

- 구현하지 말고 부족한 evidence와 다음 확인 artifact를 명시한다.
- 필요한 경우 report warning 또는 다음 pattern lab 재평가 항목으로만 남긴다.

### 10. `order_split_entry_ev_누수_분리_점검`

- title: split-entry EV 누수 분리 점검
- decision: `defer_evidence`
- decision_reason: single-lab finding; keep as low-confidence backlog until repeated by fresh lab or EV report
- target_subsystem: `holding_exit`
- route: `existing_family`
- mapped_family: `bad_entry_refined_canary`
- confidence: `solo`
- priority: `12`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Re-evaluate in the next postclose pattern lab automation and daily EV report.

실행 기준:

- 구현하지 말고 부족한 evidence와 다음 확인 artifact를 명시한다.
- 필요한 경우 report warning 또는 다음 pattern lab 재평가 항목으로만 남긴다.

### 11. `order_partial_fallback_확대_직후_즉시_재평가_shadow`

- title: partial → fallback 확대 직후 즉시 재평가 shadow
- decision: `reject`
- decision_reason: fallback revival or shadow reintroduction conflicts with current Plan Rebase policy
- target_subsystem: `holding_exit`
- route: `existing_family`
- mapped_family: `bad_entry_refined_canary`
- confidence: `solo`
- priority: `9`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Keep as rejected finding unless translated into report_only_calibration or bounded canary design.

실행 기준:

- 구현하지 않는다.
- reject 사유를 유지하고, 필요하면 report_only_calibration 또는 bounded canary 설계로 번역 가능한지 별도 판단한다.

### 12. `order_partial_only_표류_전용_timeout_shadow`

- title: partial-only 표류 전용 timeout shadow
- decision: `reject`
- decision_reason: fallback revival or shadow reintroduction conflicts with current Plan Rebase policy
- target_subsystem: `holding_exit`
- route: `existing_family`
- mapped_family: `bad_entry_refined_canary`
- confidence: `solo`
- priority: `10`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Keep as rejected finding unless translated into report_only_calibration or bounded canary design.

실행 기준:

- 구현하지 않는다.
- reject 사유를 유지하고, 필요하면 report_only_calibration 또는 bounded canary 설계로 번역 가능한지 별도 판단한다.

## 자동화체인 재투입

- 구현 결과는 `2026-05-09` 이후 postclose `threshold_cycle`, `scalping_pattern_lab_automation`, `threshold_cycle_ev`가 자동으로 다시 읽는다.
- 구현자가 수동으로 threshold 값을 바꾸는 것이 아니라, source/report/provenance를 닫아 다음 calibration이 판단하게 한다.
- 다음 Codex 세션 입력 문구: `paste generated markdown into a Codex session and request implementation`

## Project/Calendar 동기화

문서/checklist를 수정했으면 parser 검증은 실행하고, Project/Calendar 동기화는 사용자가 아래 명령으로 수동 실행한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
