# Code Improvement Workorder - 2026-05-09

## 목적

- Postclose 자동화가 생성한 `code_improvement_order`를 Codex 실행용 작업지시서로 변환한다.
- 입력은 scalping pattern lab automation, swing lifecycle improvement automation, swing pattern lab automation을 함께 포함할 수 있다.
- 이 문서는 repo/runtime을 직접 변경하지 않는다. 사용자가 이 문서를 Codex 세션에 넣고 구현을 요청하는 지점만 사람 개입으로 남긴다.
- 구현 후 자동화체인 재투입은 다음 postclose report, threshold calibration, daily EV report가 담당한다.

## Source

- pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/scalping_pattern_lab_automation/scalping_pattern_lab_automation_2026-05-09.json`
- swing_improvement_automation: `/home/ubuntu/KORStockScan/data/report/swing_improvement_automation/swing_improvement_automation_2026-05-09.json`
- swing_pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_2026-05-09.json`
- threshold_cycle_ev: `/home/ubuntu/KORStockScan/data/report/threshold_cycle_ev/threshold_cycle_ev_2026-05-09.json`
- generated_at: `2026-05-09T17:10:20+09:00`

## 운영 원칙

- `runtime_effect=false` order만 구현 대상으로 본다.
- fallback 재개, shadow 재개, safety guard 우회는 구현하지 않는다.
- runtime 영향이 생길 수 있는 변경은 feature flag, threshold family metadata, provenance, safety guard를 같이 닫는다.
- 새 family는 `allowed_runtime_apply=false`에서 시작하고, 구현/테스트/guard 완료 후에만 auto_bounded_live 후보가 될 수 있다.
- 구현 후에는 관련 테스트와 parser 검증을 실행하고, 다음 postclose daily EV에서 metric을 확인한다.

## Summary

- source_order_count: `4`
- scalping_source_order_count: `0`
- swing_source_order_count: `4`
- swing_lab_source_order_count: `0`
- selected_order_count: `4`
- decision_counts: `{'implement_now': 2, 'design_family_candidate': 2}`
- gemini_fresh: `None`
- claude_fresh: `None`
- swing_lifecycle_audit_available: `True`
- swing_pattern_lab_automation_available: `True`
- swing_pattern_lab_fresh: `False`
- swing_threshold_ai_status: `unavailable`
- daily_ev_available: `True`

## 적용 이력 확인

- 판정: `1~2번 적용 완료`, `3~4번 report-only 설계/관찰축 반영 완료`, `runtime live 전환 없음`.
- 근거:
  - `order_swing_lifecycle_observation_coverage`와 `order_swing_recommendation_db_load_gap`는 `2026-05-09 17:38 KST` 커밋 `a4e5f37 Add DeepSeek swing pattern lab automation, Phase 3 P1/P2 instrumentation, and Phase 2 hardening`에서 `swing_lifecycle_audit`, `swing_selection_funnel_report`, `swing_improvement_automation`, `threshold_cycle_ev_report`에 반영됐다.
  - `swing_lifecycle_audit_2026-05-09`에는 stage별 raw/unique count, field coverage, `swing_recommendation_db_load` axis가 생성됐다. `2026-05-11` 후속 산출물에는 `recommendation_db_load.db_load_gap`, `db_load_skip_reason`, `db_load_error`, `selection_modes`가 machine-readable로 남는다.
  - `order_swing_ai_contract_structured_output_eval`와 `order_swing_scale_in_avg_down_pyramid_observation`은 `ai_contract_metrics`, `scale_in_observation`, `AVG_DOWN/PYRAMID/NONE`, add trigger/price policy/post-add outcome을 report-only로 남기는 쪽까지 반영됐다. 이후 `2026-05-11` `SwingSimScaleInArms0511`/`SwingScaleInRealCanaryPhase0Policy0511`에서 dry-run/probe scale-in 수량 provenance와 별도 real canary approval-required guard가 보강됐다.
  - 테스트 흔적은 `src/tests/test_swing_model_selection_funnel_repair.py`의 `recommendation_db_load`, `scale_in_observation`, `swing_scale_in_real_canary_phase0` 검증과 `src/tests/test_threshold_cycle_ev_report.py`의 workorder/daily EV 반영 검증으로 확인한다.
- 다음 액션: 남은 이슈는 미적용이 아니라 다음 postclose 품질 확인이다. `db_load_gap`, `instrumentation_gap_count`, `ai_contract_schema_valid_rate`, `scale_in_action_groups`, `post_add_outcome` coverage가 다음 산출물에서 개선되는지 본다. 사용자 approval artifact 없이 스윙 live 주문, 숫자 floor, scale-in real canary는 열지 않는다.

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

### 1. `order_swing_lifecycle_observation_coverage`

- title: swing lifecycle observation coverage
- decision: `implement_now`
- decision_reason: instrumentation/provenance work can improve attribution without direct runtime mutation
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `full_lifecycle`
- target_subsystem: `runtime_instrumentation`
- route: `instrumentation_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `instrumentation`
- confidence: `consensus`
- priority: `1`
- runtime_effect: `False`
- expected_ev_effect: instrumentation_gap_count decreases and stage field coverage increases.
- evidence: `instrumentation_gap_count=1`
- next_postclose_metric: instrumentation_gap_count decreases and stage field coverage increases.
- files_likely_touched: `src/engine/swing_lifecycle_audit.py`, `src/engine/sniper_state_handlers.py`, `src/engine/sniper_scale_in.py`
- acceptance_tests: `pytest swing lifecycle audit tests`, `pipeline event field coverage smoke`
- automation_reentry: After implementation, next postclose report must show source freshness or warning reduction.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 2. `order_swing_recommendation_db_load_gap`

- title: swing recommendation DB load gap
- decision: `implement_now`
- decision_reason: instrumentation/provenance work can improve attribution without direct runtime mutation
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `db_load`
- target_subsystem: `runtime_instrumentation`
- route: `instrumentation_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `instrumentation`
- confidence: `consensus`
- priority: `2`
- runtime_effect: `False`
- expected_ev_effect: csv_rows and db_rows no longer diverge without a warning.
- evidence: `csv_rows=5`, `db_rows=0`
- next_postclose_metric: csv_rows and db_rows no longer diverge without a warning.
- files_likely_touched: `src/scanners/final_ensemble_scanner.py`, `src/engine/swing_lifecycle_audit.py`
- acceptance_tests: `pytest swing funnel/report tests`
- automation_reentry: After implementation, next postclose report must show source freshness or warning reduction.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 3. `order_swing_ai_contract_structured_output_eval`

- title: swing AI contract structured output eval
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `ai_contract`
- target_subsystem: `swing_ai_contract`
- route: `auto_family_candidate`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `ai_contract_eval`
- confidence: `consensus`
- priority: `5`
- runtime_effect: `False`
- expected_ev_effect: schema_valid_rate, decision disagreement, latency, and cost are reported before model/prompt change.
- evidence: `swing_gatekeeper_free_text_label`, `swing_holding_flow_scalping_prompt_reuse`, `swing_scale_in_ai_contract_missing`
- next_postclose_metric: schema_valid_rate, decision disagreement, latency, and cost are reported before model/prompt change.
- files_likely_touched: `src/engine/ai_engine.py`, `src/engine/ai_engine_openai.py`, `src/engine/ai_response_contracts.py`
- acceptance_tests: `pytest OpenAI transport/schema tests`, `pytest swing lifecycle audit tests`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

### 4. `order_swing_scale_in_avg_down_pyramid_observation`

- title: swing scale-in AVG_DOWN/PYRAMID observation
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `scale_in`
- target_subsystem: `swing_scale_in`
- route: `auto_family_candidate`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `lifecycle_logic_observation`
- confidence: `-`
- priority: `6`
- runtime_effect: `False`
- expected_ev_effect: scale_in group coverage and add_type/post_add outcome fields appear in lifecycle audit.
- evidence: `scale_in_unique_records=0`
- next_postclose_metric: scale_in group coverage and add_type/post_add outcome fields appear in lifecycle audit.
- files_likely_touched: `src/engine/sniper_scale_in.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest sniper scale-in tests`, `pytest swing lifecycle audit tests`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

## 자동화체인 재투입

- 구현 결과는 `2026-05-10` 이후 postclose `threshold_cycle`, `scalping_pattern_lab_automation`, `threshold_cycle_ev`가 자동으로 다시 읽는다.
- 구현자가 수동으로 threshold 값을 바꾸는 것이 아니라, source/report/provenance를 닫아 다음 calibration이 판단하게 한다.
- 다음 Codex 세션 입력 문구: `paste generated markdown into a Codex session and request implementation`

## Project/Calendar 동기화

문서/checklist를 수정했으면 parser 검증은 실행하고, Project/Calendar 동기화는 사용자가 아래 명령으로 수동 실행한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
