# Code Improvement Workorder - 2026-05-13

## 목적

- Postclose 자동화가 생성한 `code_improvement_order`를 Codex 실행용 작업지시서로 변환한다.
- 입력은 scalping pattern lab automation, swing lifecycle improvement automation, swing pattern lab automation을 함께 포함할 수 있다.
- 이 문서는 repo/runtime을 직접 변경하지 않는다. 사용자가 이 문서를 Codex 세션에 넣고 구현을 요청하는 지점만 사람 개입으로 남긴다.
- 구현 후 자동화체인 재투입은 다음 postclose report, threshold calibration, daily EV report가 담당한다.

## Source

- pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/scalping_pattern_lab_automation/scalping_pattern_lab_automation_2026-05-13.json`
- swing_improvement_automation: `/home/ubuntu/KORStockScan/data/report/swing_improvement_automation/swing_improvement_automation_2026-05-13.json`
- swing_pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_2026-05-13.json`
- threshold_cycle_ev: `/home/ubuntu/KORStockScan/data/report/threshold_cycle_ev/threshold_cycle_ev_2026-05-13.json`
- threshold_cycle_calibration: `/home/ubuntu/KORStockScan/data/report/threshold_cycle_calibration/threshold_cycle_calibration_2026-05-13_postclose.json`
- generated_at: `2026-05-13T22:17:10+09:00`
- generation_id: `2026-05-13-24e8c17157ed`
- source_hash: `24e8c17157edc007caeb2868858eab74a28f33076f94f25ac67541d3c22b35a7`

## 운영 원칙

- `runtime_effect=false` order만 구현 대상으로 본다.
- fallback 재개, shadow 재개, safety guard 우회는 구현하지 않는다.
- runtime 영향이 생길 수 있는 변경은 feature flag, threshold family metadata, provenance, safety guard를 같이 닫는다.
- 새 family는 `allowed_runtime_apply=false`에서 시작하고, 구현/테스트/guard 완료 후에만 auto_bounded_live 후보가 될 수 있다.
- 구현 후에는 관련 테스트와 parser 검증을 실행하고, 다음 postclose daily EV에서 metric을 확인한다.
- 같은 날짜 workorder를 재생성하면 `generation_id`와 `lineage` diff로 신규/삭제/판정변경 order를 먼저 확인한다.

## 2-Pass 실행 기준

- Pass 1: `implement_now` 중 instrumentation/report/provenance 구현만 먼저 수행한다.
- Regeneration: 관련 postclose report와 이 workorder를 재생성하고 `lineage` diff를 확인한다.
- Pass 2: 재생성 후 새로 생긴 `runtime_effect=false` order만 추가 구현한다.
- Final freeze: `generation_id`, `source_hash`, 신규/삭제/판정변경 order를 최종 보고에 남긴다.
- 권장 지시문: `implement_now를 2-pass로 처리: Pass1 instrumentation/report/provenance 구현, 관련 리포트 재생성 후 workorder diff 확인, 신규 runtime_effect=false 항목만 Pass2 구현, 마지막에 generation_id/source_hash 기준으로 final freeze 보고`

## Snapshot Lineage

- previous_exists: `True`
- previous_generation_id: `2026-05-13-855236ba6498`
- previous_source_hash: `855236ba6498b54c19239499d02e45a1719ea93c24cadb2294ef9e275e0aded7`
- new_order_ids: `[]`
- removed_order_ids: `[]`
- decision_changed_order_ids: `[]`

## Summary

- source_order_count: `23`
- scalping_source_order_count: `15`
- swing_source_order_count: `4`
- swing_lab_source_order_count: `2`
- threshold_ev_source_order_count: `2`
- panic_lifecycle_source_order_count: `2`
- selected_order_count: `12`
- decision_counts: `{'attach_existing_family': 7, 'design_family_candidate': 7, 'defer_evidence': 5, 'reject': 4}`
- gemini_fresh: `True`
- claude_fresh: `True`
- swing_lifecycle_audit_available: `True`
- swing_pattern_lab_automation_available: `True`
- swing_pattern_lab_fresh: `True`
- swing_threshold_ai_status: `parsed`
- daily_ev_available: `True`

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

### 1. `order_ai_threshold_dominance`

- title: AI threshold dominance
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- source_report_type: `scalping_pattern_lab_automation`
- lifecycle_stage: `-`
- target_subsystem: `entry_funnel`
- route: `existing_family`
- mapped_family: `score65_74_recovery_probe`
- threshold_family: `score65_74_recovery_probe`
- improvement_type: `-`
- confidence: `consensus`
- priority: `1`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'judgment': '경고', 'why': '`blocked_ai_score_share=100.0%`로 WAIT/BLOCK 비중이 높아 BUY drought 해석을 지지한다.'}`, `{'judgment': '경고', 'why': '`blocked_ai_score_share=100.0%`로 WAIT/BLOCK 비중이 높아 BUY drought 해석을 지지한다.'}`
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 2. `order_ai_threshold_miss_ev_recovery`

- title: AI threshold miss EV recovery
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- source_report_type: `scalping_pattern_lab_automation`
- lifecycle_stage: `-`
- target_subsystem: `entry_funnel`
- route: `existing_family`
- mapped_family: `score65_74_recovery_probe`
- threshold_family: `score65_74_recovery_probe`
- improvement_type: `-`
- confidence: `consensus`
- priority: `2`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'total_blocked': 3370010, 'block_ratio': 100.0, 'days': 21}`, `{'total_blocked': 4230900, 'block_ratio': 100.0, 'days': 22}`
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 3. `order_swing_gatekeeper_reject_threshold_review`

- title: swing gatekeeper reject threshold review
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `entry`
- target_subsystem: `swing_entry`
- route: `existing_family`
- mapped_family: `swing_gatekeeper_accept_reject`
- threshold_family: `swing_gatekeeper_accept_reject`
- improvement_type: `threshold_family_input`
- confidence: `consensus`
- priority: `3`
- runtime_effect: `False`
- expected_ev_effect: gatekeeper reject/pass, submitted/simulated, and post-entry outcomes are attributable by family.
- evidence: `blocked_gatekeeper_reject_unique=18`
- next_postclose_metric: gatekeeper reject/pass, submitted/simulated, and post-entry outcomes are attributable by family.
- files_likely_touched: `src/engine/sniper_state_handlers.py`, `src/engine/swing_lifecycle_audit.py`
- acceptance_tests: `pytest swing lifecycle audit tests`, `pytest state handler fast signatures`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 4. `order_swing_pattern_lab_deepseek_scale_in_events_observed`

- title: Scale-in events observed for swing positions
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- source_report_type: `swing_pattern_lab_automation`
- lifecycle_stage: `scale_in`
- target_subsystem: `swing_scale_in`
- route: `attach_existing_family`
- mapped_family: `swing_scale_in_ofi_qi_confirmation`
- threshold_family: `swing_scale_in_ofi_qi_confirmation`
- improvement_type: `pattern_lab_observation`
- confidence: `consensus`
- priority: `3`
- runtime_effect: `False`
- expected_ev_effect: Evaluate PYRAMID/AVG_DOWN outcome quality with OFI/QI confirmation.
- evidence: `{'scale_in_events': 9}`
- next_postclose_metric: swing_scale_in_quality_score
- files_likely_touched: `src/engine/swing_lifecycle_audit.py`, `src/engine/swing_selection_funnel_report.py`, `src/model/common_v2.py`
- acceptance_tests: `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_swing_model_selection_funnel_repair.py`, `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_deepseek_swing_pattern_lab.py`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 5. `order_latency_guard_miss_ev_recovery`

- title: latency guard miss EV recovery
- decision: `attach_existing_family`
- decision_reason: instrumentation/provenance contract is already implemented; keep as report source for the existing family
- source_report_type: `scalping_pattern_lab_automation`
- lifecycle_stage: `-`
- target_subsystem: `runtime_instrumentation`
- route: `existing_family`
- mapped_family: `pre_submit_price_guard`
- threshold_family: `pre_submit_price_guard`
- improvement_type: `-`
- confidence: `consensus`
- priority: `4`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'total_blocked': 60275, 'block_ratio': 99.5, 'days': 21}`, `{'total_blocked': 51521, 'block_ratio': 99.5, 'days': 22}`
- next_postclose_metric: -
- files_likely_touched: `src/engine/sniper_performance_tuning_report.py`, `src/engine/daily_threshold_cycle_report.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Next postclose calibration consumes the implemented report/provenance fields; no runtime mutation.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 6. `order_swing_ofi_qi_stale_or_missing_context`

- title: swing OFI/QI stale or missing context
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `entry`
- target_subsystem: `swing_orderbook_micro_context`
- route: `existing_family`
- mapped_family: `swing_entry_ofi_qi_execution_quality`
- threshold_family: `swing_entry_ofi_qi_execution_quality`
- improvement_type: `instrumentation`
- confidence: `consensus`
- priority: `4`
- runtime_effect: `False`
- expected_ev_effect: stale_missing_ratio decreases while submitted/simulated entry quality remains attributable.
- evidence: `stale_missing_count=1`, `stale_missing_ratio=0.0062`, `stale_missing_unique_record_count=1`, `stale_missing_reason_counts={'micro_missing': 1, 'micro_not_ready': 1, 'state_insufficient': 1}`, `stale_missing_reason_combination_counts={'micro_missing+micro_not_ready+state_insufficient': 1}`, `stale_missing_reason_combination_unique_record_counts={'micro_missing+micro_not_ready+state_insufficient': 1}`, `observer_unhealthy_overlap={'observer_unhealthy_total': 0, 'observer_unhealthy_with_other_reason': 0, 'observer_unhealthy_only': 0}`, `scale_in_source_quality={'group': 'scale_in', 'sample_count': 145, 'valid_micro_context_count': 145, 'invalid_micro_context_count': 0, 'invalid_micro_context_unique_record_count': 0, 'invalid_reason_combination_counts': {'micro_missing+micro_not_ready+state_insufficient': 1}, 'invalid_reason_combination_unique_record_counts': {'micro_missing+micro_not_ready+state_insufficient': 1}, 'observer_unhealthy_overlap': {'observer_unhealthy_total': 0, 'observer_unhealthy_with_other_reason': 0, 'observer_unhealthy_only': 0}, 'source_quality_blockers': []}`, `entry_source_quality={'group': 'entry', 'sample_count': 0, 'valid_micro_context_count': 0, 'invalid_micro_context_count': 0, 'invalid_micro_context_unique_record_count': 0, 'invalid_reason_combination_counts': {'micro_missing+micro_not_ready+state_insufficient': 1}, 'invalid_reason_combination_unique_record_counts': {'micro_missing+micro_not_ready+state_insufficient': 1}, 'observer_unhealthy_overlap': {'observer_unhealthy_total': 0, 'observer_unhealthy_with_other_reason': 0, 'observer_unhealthy_only': 0}, 'source_quality_blockers': []}`
- next_postclose_metric: stale_missing_ratio decreases while submitted/simulated entry quality remains attributable.
- files_likely_touched: `src/engine/sniper_state_handlers.py`, `src/engine/orderbook_stability.py`, `src/engine/swing_lifecycle_audit.py`
- acceptance_tests: `pytest orderbook stability tests`, `pytest swing lifecycle audit tests`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 7. `order_swing_scale_in_ofi_qi_bearish_risk_review`

- title: swing scale-in OFI/QI bearish risk review
- decision: `attach_existing_family`
- decision_reason: finding maps to an existing threshold family and should strengthen source metrics/provenance
- source_report_type: `swing_improvement_automation`
- lifecycle_stage: `scale_in`
- target_subsystem: `swing_scale_in`
- route: `existing_family`
- mapped_family: `swing_scale_in_ofi_qi_confirmation`
- threshold_family: `swing_scale_in_ofi_qi_confirmation`
- improvement_type: `lifecycle_logic_observation`
- confidence: `-`
- priority: `5`
- runtime_effect: `False`
- expected_ev_effect: post-add outcome and micro_risk attribution are visible for future guarded threshold design.
- evidence: `scale_in_RISK_BEARISH=6`, `valid_micro_context_count=145`, `invalid_micro_context_unique_record_count=0`, `source_quality_blockers=[]`
- next_postclose_metric: post-add outcome and micro_risk attribution are visible for future guarded threshold design.
- files_likely_touched: `src/engine/sniper_state_handlers.py`, `src/engine/swing_lifecycle_audit.py`
- acceptance_tests: `pytest sniper scale-in tests`, `pytest swing lifecycle audit tests`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 8. `order_swing_pattern_lab_deepseek_entry_no_submissions`

- title: All selected candidates failed to reach order submission
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- source_report_type: `swing_pattern_lab_automation`
- lifecycle_stage: `entry`
- target_subsystem: `swing_entry_funnel`
- route: `design_family_candidate`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `pattern_lab_observation`
- confidence: `consensus`
- priority: `1`
- runtime_effect: `False`
- expected_ev_effect: Investigate the entry funnel for swing-specific bottlenecks.
- evidence: `{'selected_count': 3, 'submitted_count': 0, 'blocked_gatekeeper_selection': 0, 'blocked_gatekeeper_carryover': 0, 'blocked_gap_selection': 0, 'blocked_gap_carryover': 0, 'blocked_market_selection': 0, 'blocked_market_carryover': 0}`
- next_postclose_metric: swing_entry_quality_score
- files_likely_touched: `src/engine/swing_lifecycle_audit.py`, `src/engine/swing_selection_funnel_report.py`, `src/model/common_v2.py`
- acceptance_tests: `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_swing_model_selection_funnel_repair.py`, `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_deepseek_swing_pattern_lab.py`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

### 9. `order_budget_pass_without_submit`

- title: Budget pass without submit
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- source_report_type: `scalping_pattern_lab_automation`
- lifecycle_stage: `-`
- target_subsystem: `scalping_logic`
- route: `auto_family_candidate`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `3`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'judgment': '경고', 'why': '`budget_pass=642`인데 `submitted=0`라 제출 전 병목이 기대값 회복을 끊고 있다.'}`, `{'judgment': '경고', 'why': '`budget_pass=642`인데 `submitted=0`라 제출 전 병목이 기대값 회복을 끊고 있다.'}`
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

### 10. `order_liquidity_gate_miss_ev_recovery`

- title: liquidity gate miss EV recovery
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- source_report_type: `scalping_pattern_lab_automation`
- lifecycle_stage: `-`
- target_subsystem: `entry_filter_quality`
- route: `auto_family_candidate`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `5`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'total_blocked': 61256, 'block_ratio': 99.5, 'days': 21}`, `{'total_blocked': 0, 'block_ratio': 0.0, 'days': 22}`
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

### 11. `order_swing_ai_contract_structured_output_eval`

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

### 12. `order_overbought_gate_miss_ev_recovery`

- title: overbought gate miss EV recovery
- decision: `design_family_candidate`
- decision_reason: finding needs family design; allowed_runtime_apply remains false until metadata/tests/guards are closed
- source_report_type: `scalping_pattern_lab_automation`
- lifecycle_stage: `-`
- target_subsystem: `entry_filter_quality`
- route: `auto_family_candidate`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `6`
- runtime_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'total_blocked': 1179279, 'block_ratio': 100.0, 'days': 21}`, `{'total_blocked': 1108742, 'block_ratio': 100.0, 'days': 22}`
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_state_handlers.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Create report-only family metadata first; only later can auto_bounded_live consider it.

실행 기준:

- 새 family 후보 metadata와 report-only source를 설계한다.
- `allowed_runtime_apply=false`를 유지한다.
- sample floor, safety guard, target env key, tests가 닫히기 전 runtime 적용 금지.

## 자동화체인 재투입

- 구현 결과는 `2026-05-14` 이후 postclose `threshold_cycle`, `scalping_pattern_lab_automation`, `threshold_cycle_ev`가 자동으로 다시 읽는다.
- 구현자가 수동으로 threshold 값을 바꾸는 것이 아니라, source/report/provenance를 닫아 다음 calibration이 판단하게 한다.
- 다음 Codex 세션 입력 문구: `paste generated markdown into a Codex session and request implementation`

## Project/Calendar 동기화

문서/checklist를 수정했으면 parser 검증은 실행하고, Project/Calendar 동기화는 사용자가 아래 명령으로 수동 실행한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
