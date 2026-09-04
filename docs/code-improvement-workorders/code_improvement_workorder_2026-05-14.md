# Code Improvement Workorder - 2026-05-14

## 목적

- Postclose 자동화가 생성한 `code_improvement_order`를 Codex 실행용 작업지시서로 변환한다.
- 입력은 scalping pattern lab automation, swing lifecycle improvement automation, swing pattern lab automation을 함께 포함할 수 있다.
- 이 문서는 repo/runtime을 직접 변경하지 않는다. 사용자가 이 문서를 Codex 세션에 넣고 구현을 요청하는 지점만 사람 개입으로 남긴다.
- 구현 후 자동화체인 재투입은 다음 postclose report, threshold calibration, daily EV report가 담당한다.

## Source

- pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/scalping_pattern_lab_automation/scalping_pattern_lab_automation_2026-05-14.json`
- swing_improvement_automation: `/home/ubuntu/KORStockScan/data/report/swing_improvement_automation/swing_improvement_automation_2026-05-14.json`
- swing_pattern_lab_automation: `/home/ubuntu/KORStockScan/data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_2026-05-14.json`
- threshold_cycle_ev: `/home/ubuntu/KORStockScan/data/report/threshold_cycle_ev/threshold_cycle_ev_2026-05-14.json`
- threshold_cycle_calibration: `/home/ubuntu/KORStockScan/data/report/threshold_cycle_calibration/threshold_cycle_calibration_2026-05-14_postclose.json`
- pipeline_event_verbosity: `/home/ubuntu/KORStockScan/data/report/pipeline_event_verbosity/pipeline_event_verbosity_2026-05-14.json`
- codebase_performance_workorder: `/home/ubuntu/KORStockScan/data/report/codebase_performance_workorder/codebase_performance_workorder_2026-05-14.json`
- generated_at: `2026-05-14T18:49:14+09:00`
- generation_id: `2026-05-14-3924b7a14fb5`
- source_hash: `3924b7a14fb5bfc4bd663322295af214920fbc08fd117eb6e8c743a4eb81c8a8`

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
- previous_generation_id: `2026-05-14-4a6ef2164d8e`
- previous_source_hash: `4a6ef2164d8e1d3366ac6d132f61eb939780585116522109153e88bf69565437`
- new_order_ids: `[]`
- removed_order_ids: `[]`
- decision_changed_order_ids: `[]`

## Summary

- source_order_count: `38`
- scalping_source_order_count: `14`
- swing_source_order_count: `5`
- swing_lab_source_order_count: `3`
- threshold_ev_source_order_count: `16`
- pipeline_event_verbosity_source_order_count: `1`
- codebase_performance_source_order_count: `12`
- panic_lifecycle_source_order_count: `2`
- selected_order_count: `12`
- decision_counts: `{'implement_now': 9, 'attach_existing_family': 7, 'design_family_candidate': 6, 'defer_evidence': 10, 'reject': 6}`
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

### 1. `order_perf_buy_funnel_json_scan`

- title: BUY funnel sentinel field scan without repeated json.dumps
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `buy_funnel_sentinel`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `1`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=low`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=classification, blocker counts, unique submitted count, actual_order_submitted split, source-quality/provenance fields exact match`
- parity_contract: classification, blocker counts, unique submitted count, actual_order_submitted split, source-quality/provenance fields exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/engine/buy_funnel_sentinel.py`
- acceptance_tests: `pytest src/tests/test_buy_funnel_sentinel.py`, `BUY Sentinel classification parity on same raw/cache input`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 2. `order_pipeline_event_compaction_v2_shadow`

- title: Pipeline event compaction V2 shadow producer summary
- decision: `implement_now`
- decision_reason: pipeline event compaction V2 is report-only instrumentation; shadow means producer-summary observe mode, not trading shadow
- source_report_type: `pipeline_event_verbosity`
- lifecycle_stage: `ops_volume_diagnostic`
- target_subsystem: `runtime_instrumentation`
- route: `instrumentation_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `1`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `state=v2_shadow_missing`, `recommended_workorder_state=open_shadow_order`, `raw_size_bytes=1296047796`, `high_volume_line_count=1342730`, `high_volume_byte_share_pct=95.39`, `producer_summary_exists=False`, `parity_ok=False`, `raw_derived_event_count=1342310`, `producer_event_count=0`
- parity_contract: -
- next_postclose_metric: pipeline_event_verbosity.parity.ok
- files_likely_touched: `src/utils/pipeline_event_logger.py`, `src/engine/pipeline_event_summary.py`, `src/engine/pipeline_event_verbosity_report.py`
- acceptance_tests: `pytest src/tests/test_pipeline_event_logger.py src/tests/test_pipeline_event_verbosity_report.py`
- automation_reentry: Next postclose pipeline_event_verbosity report must show producer summary freshness and parity status.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 3. `order_perf_daily_report_bulk_history`

- title: Daily report market snapshot bulk history query
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `daily_report`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `2`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=medium`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=per-stock history window, feature columns, model input row count, and report JSON exact match`
- parity_contract: per-stock history window, feature columns, model input row count, and report JSON exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/engine/daily_report_service.py`
- acceptance_tests: `pytest src/tests/test_daily_report_service.py src/tests/test_daily_report.py`, `daily report output parity on injected DB/model fixture`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 4. `order_perf_daily_report_engine_singleton`

- title: Daily report SQLAlchemy engine singleton
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `daily_report`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `3`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=low`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=query result and rendered daily report exact match`
- parity_contract: query result and rendered daily report exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/engine/daily_report_service.py`
- acceptance_tests: `pytest src/tests/test_daily_report_service.py src/tests/test_daily_report.py`, `engine creation count regression test`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 5. `order_threshold_window_policy_source_snapshot_alignment`

- title: threshold window policy source snapshot alignment
- decision: `implement_now`
- decision_reason: instrumentation/provenance work can improve attribution without direct runtime mutation
- source_report_type: `threshold_cycle_calibration`
- lifecycle_stage: `threshold_cycle`
- target_subsystem: `threshold_cycle_report`
- route: `instrumentation_order`
- mapped_family: `-`
- threshold_family: `window_policy_registry`
- improvement_type: `source_quality_alignment`
- confidence: `consensus`
- priority: `3`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: Prevent daily-only or snapshot-only calibration blind spots by aligning rolling/cumulative source metrics, snapshot denominators, AI correction context, and EV/workorder rendering.
- evidence: `issue_counts={"rolling_source_snapshot_mismatch": 4}`, `affected_families=trailing_continuation,score65_74_recovery_probe,liquidity_gate_refined_candidate,overbought_gate_refined_candidate`, `family=trailing_continuation primary=rolling_10d state=freeze primary_sample=84 snapshot_sample=12 source_sample=84 issues=rolling_source_snapshot_mismatch`, `family=score65_74_recovery_probe primary=rolling_5d state=hold primary_sample=177 snapshot_sample=0 source_sample=177 issues=rolling_source_snapshot_mismatch`, `family=liquidity_gate_refined_candidate primary=rolling_5d state=hold primary_sample=22940 snapshot_sample=0 source_sample=22940 issues=rolling_source_snapshot_mismatch`, `family=overbought_gate_refined_candidate primary=rolling_5d state=hold primary_sample=456860 snapshot_sample=0 source_sample=456860 issues=rolling_source_snapshot_mismatch`
- parity_contract: -
- next_postclose_metric: window_policy_audit should have no daily_only_leak or rolling_consumer_gap; rolling_source_snapshot_mismatch must be explained as rendering-only or eliminated.
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/threshold_cycle_ev_report.py`, `src/engine/build_code_improvement_workorder.py`, `data/threshold_cycle/README.md`
- acceptance_tests: `PYTHONPATH=. .venv/bin/pytest src/tests/test_daily_threshold_cycle_report.py src/tests/test_build_code_improvement_workorder.py`, `threshold_cycle_YYYY-MM-DD.json includes window_policy_audit and calibration_source_bundle_by_window lineage`
- automation_reentry: After implementation, next postclose report must show source freshness or warning reduction.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 6. `order_perf_recommend_update_vectorization`

- title: Recommendation and update_kospi vectorized membership checks
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `swing_daily_recommendation`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `4`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=low`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=selected keys, diagnostics rows, CSV row order, and update_kospi inserted-row set exact match`
- parity_contract: selected keys, diagnostics rows, CSV row order, and update_kospi inserted-row set exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/model/recommend_daily_v2.py`, `src/utils/update_kospi.py`
- acceptance_tests: `pytest src/tests/test_swing_retrain_automation.py src/tests/test_swing_feature_ssot.py`, `recommendation CSV and diagnostics parity`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 7. `order_perf_swing_simulation_iteration`

- title: Swing simulation iteration and quote grouping
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `swing_daily_simulation`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `5`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=medium`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=selection funnel, lifecycle arms, gate counterfactuals, and runtime funnel summary exact match`
- parity_contract: selection funnel, lifecycle arms, gate counterfactuals, and runtime funnel summary exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/engine/swing_daily_simulation_report.py`
- acceptance_tests: `pytest src/tests/test_swing_model_selection_funnel_repair.py`, `swing simulation JSON parity on injected sources`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 8. `order_perf_monitor_snapshot_stream_tail`

- title: Monitor snapshot runtime streaming tail read
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `monitor_snapshot`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `6`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=low`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=latest parsed snapshot payload and missing/malformed fallback behavior exact match`
- parity_contract: latest parsed snapshot payload and missing/malformed fallback behavior exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/engine/monitor_snapshot_runtime.py`
- acceptance_tests: `pytest src/tests/test_log_archive_service.py`, `last valid JSON line parity`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 9. `order_perf_final_ensemble_records`

- title: Final ensemble scanner records conversion without iterrows
- decision: `implement_now`
- decision_reason: accepted codebase performance order is logic-preserving and report/workorder-only; implementation still requires parity tests
- source_report_type: `codebase_performance_workorder`
- lifecycle_stage: `ops_performance`
- target_subsystem: `final_ensemble_scanner`
- route: `performance_optimization_order`
- mapped_family: `-`
- threshold_family: `-`
- improvement_type: `-`
- confidence: `consensus`
- priority: `7`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: none_direct_ops_cpu_io_reduction_only
- evidence: `source_doc_hash=6bc37e5b3d13f356392d83e4ec1ecdcd2f57a05a0f9bc58f6329a1ea20fbed88`, `candidate_state=accepted`, `risk_tier=low`, `runtime_effect=false`, `strategy_effect=false`, `data_quality_effect=false`, `tuning_axis_effect=false`, `parity_contract=Code/Name record list, selection count, and diagnostics output exact match`
- parity_contract: Code/Name record list, selection count, and diagnostics output exact match
- next_postclose_metric: same report/output parity with lower runtime or CPU/IO overhead
- files_likely_touched: `src/scanners/final_ensemble_scanner.py`
- acceptance_tests: `pytest src/tests/test_swing_model_selection_funnel_repair.py`, `V2 CSV pick list parity`
- automation_reentry: After implementation, rerun the same artifact/report parity tests before postclose workorder refresh.

실행 기준:

- instrumentation/provenance/report source 보강을 우선 구현한다.
- runtime 판단값을 직접 바꾸지 않는다.
- 다음 postclose report에서 source freshness, warning 감소, sample count가 확인되어야 한다.

### 10. `order_ai_threshold_dominance`

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
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'judgment': '경고', 'why': '`blocked_ai_score_share=94.7%`로 WAIT/BLOCK 비중이 높아 BUY drought 해석을 지지한다.'}`, `{'judgment': '경고', 'why': '`blocked_ai_score_share=94.7%`로 WAIT/BLOCK 비중이 높아 BUY drought 해석을 지지한다.'}`
- parity_contract: -
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 11. `order_ai_threshold_miss_ev_recovery`

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
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'total_blocked': 3692917, 'block_ratio': 100.0, 'days': 22}`, `{'total_blocked': 4649735, 'block_ratio': 100.0, 'days': 23}`
- parity_contract: -
- next_postclose_metric: -
- files_likely_touched: `src/engine/daily_threshold_cycle_report.py`, `src/engine/sniper_missed_entry_counterfactual.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: After implementation, intraday/postclose calibration should include the updated family input.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

### 12. `order_latency_guard_miss_ev_recovery`

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
- priority: `3`
- runtime_effect: `False`
- strategy_effect: `False`
- data_quality_effect: `False`
- tuning_axis_effect: `False`
- expected_ev_effect: Improve EV attribution and prepare bounded calibration input.
- evidence: `{'total_blocked': 60275, 'block_ratio': 99.5, 'days': 22}`, `{'total_blocked': 51521, 'block_ratio': 99.5, 'days': 23}`
- parity_contract: -
- next_postclose_metric: -
- files_likely_touched: `src/engine/sniper_performance_tuning_report.py`, `src/engine/daily_threshold_cycle_report.py`
- acceptance_tests: `pytest relevant report/threshold tests`, `runtime_effect remains false until a separate implementation order is completed`, `daily EV report includes the order summary`
- automation_reentry: Next postclose calibration consumes the implemented report/provenance fields; no runtime mutation.

실행 기준:

- 기존 threshold family의 source metric/provenance를 보강한다.
- 다음 intraday/postclose calibration에서 해당 family 입력으로 소비되어야 한다.
- family state/value 변경은 deterministic guard와 auto_bounded_live 체인을 통해서만 가능하다.

## 자동화체인 재투입

- 구현 결과는 `2026-05-15` 이후 postclose `threshold_cycle`, `scalping_pattern_lab_automation`, `threshold_cycle_ev`가 자동으로 다시 읽는다.
- 구현자가 수동으로 threshold 값을 바꾸는 것이 아니라, source/report/provenance를 닫아 다음 calibration이 판단하게 한다.
- 다음 Codex 세션 입력 문구: `paste generated markdown into a Codex session and request implementation`

## Project/Calendar 동기화

문서/checklist를 수정했으면 parser 검증은 실행하고, Project/Calendar 동기화는 사용자가 아래 명령으로 수동 실행한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
