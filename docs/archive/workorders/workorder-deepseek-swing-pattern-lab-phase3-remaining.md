# 작업지시서: DeepSeek Swing Pattern Lab Phase 3 잔여 작업

작성일: `2026-05-09 KST`  
Owner: `SwingPatternLabDeepSeekPhase3Remaining`  
Source:
- `docs/archive/workorders/workorder-deepseek-swing-pattern-lab-phase2.md`
- `docs/deepseek-swing-pattern-lab-phase2-build-report.md`
- `data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_2026-05-09.json`
- `docs/code-improvement-workorders/code_improvement_workorder_2026-05-09.md`

---

## 1. 판정

Phase 2 자동화 연결은 진행 가능 상태다. 남은 작업은 live 매매 로직 변경이 아니라 다음 네 묶음으로 분리한다.

| 우선순위 | 묶음 | 판정 |
|---|---|---|
| P0 | Phase2 artifact consistency hardening | stale/range 산출물이 workorder에 남지 않도록 최종 정합성 고정 |
| P1 | Swing lifecycle instrumentation | 선정 이후 DB 적재, 장중 진입, 보유/청산 attribution 누락 축 보강 |
| P2 | Swing report-only family design | AI contract, AVG_DOWN/PYRAMID 관찰축을 runtime 적용 없이 family 후보로 설계 |
| P3 | Fresh DeepSeek re-entry | 단일 target date fresh lab이 다시 생성될 때만 DeepSeek finding을 workorder로 재진입 |

현재 `deepseek_lab_available=false`인 산출물은 개선 order를 생성하면 안 된다. DeepSeek pattern lab order는 fresh single-day run이 닫힌 이후에만 재진입한다.

---

## 2. 운영 원칙

1. 이 작업은 `report-only / proposal-only / instrumentation-first`다.
2. 스윙 live 주문, Gatekeeper, market regime hard block, gap/protection guard, 예산/주문 safety, model floor, threshold runtime 값은 변경하지 않는다.
3. 모든 신규 order와 family candidate는 `runtime_effect=false`, `allowed_runtime_apply=false`를 유지한다.
4. DeepSeek 결과를 runtime env, threshold value, live guard에 직접 반영하지 않는다.
5. range 산출물은 daily workorder 입력으로 쓰지 않는다. daily workorder 입력은 `analysis_window.start == target_date == end`인 단일일 산출물만 허용한다.
6. `COMPLETED + valid profit_rate` 이외의 손익 값으로 성과 결론을 만들지 않는다.

---

## 3. 작업 묶음

### 3.1 P0 — Phase2 Artifact Consistency Hardening

대상:
- `src/engine/swing_pattern_lab_automation.py`
- `src/engine/threshold_cycle_ev_report.py`
- `src/engine/build_code_improvement_workorder.py`
- `docs/deepseek-swing-pattern-lab-phase2-build-report.md`
- `data/report/swing_pattern_lab_automation/`
- `docs/code-improvement-workorders/`
- `data/report/threshold_cycle_ev/`

요구사항:

1. stale 상태에서는 `consensus_findings`, `auto_family_candidates`, `code_improvement_orders`를 모두 빈 배열로 유지한다.
2. stale 상태에서는 `population_split_available=false`를 유지한다.
3. stale 상태에서는 carryover-only warnings를 참고 warning으로만 남기고, `ev_report_summary.carryover_warning_count`를 workorder 승격 신호로 쓰지 않는다. 가능하면 stale일 때 count는 `0`으로 맞추고 원본 warnings는 `data_quality.carryover_warnings_raw`처럼 별도 보관한다.
4. `_automation_report_paths` private import는 public helper로 정리한다.
   - 권장: `automation_report_paths(target_date)` 또는 `swing_pattern_lab_automation_report_paths(target_date)`로 export.
   - `threshold_cycle_ev_report.py`는 private symbol을 import하지 않는다.
5. Phase2 build report의 검증 결과를 최종 산출물과 맞춘다.
   - fresh single-day output이면 실제 finding/order count를 명시한다.
   - stale/range output이면 `deepseek_lab_available=false`, `code_improvement_order_count=0`, `population_split_available=false`를 명시한다.
6. stale guard 적용 후 canonical 산출물을 재생성한다.

재생성 명령:

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.swing_pattern_lab_automation --date 2026-05-09
PYTHONPATH=. .venv/bin/python -m src.engine.build_code_improvement_workorder --date 2026-05-09 --max-orders 12
PYTHONPATH=. .venv/bin/python -m src.engine.threshold_cycle_ev_report --date 2026-05-09
```

Acceptance:

- `deepseek_lab_available=false`이면 `swing_lab_source_order_count=0`.
- `docs/code-improvement-workorders/code_improvement_workorder_2026-05-09.md`에 stale DeepSeek order가 남지 않는다.
- `threshold_cycle_ev_2026-05-09.md`에 swing pattern lab artifact와 stale 상태가 표시된다.

---

### 3.2 P1 — `order_swing_lifecycle_observation_coverage`

목표:

스윙 전체 lifecycle audit에서 선정, DB 적재, 장중 진입 판단, 주문/시뮬레이션, 보유, 추가매수, 청산 단계의 observation gap을 줄인다.

대상:
- `src/engine/swing_lifecycle_audit.py`
- `src/engine/sniper_state_handlers.py`
- `src/engine/sniper_scale_in.py`
- 필요 시 `src/engine/swing_selection_funnel_report.py`

요구사항:

1. stage별 unique record count와 raw event count를 분리한다.
2. 누락된 stage field는 `instrumentation_gap`으로 분류하되 손익 결론에 쓰지 않는다.
3. `swing_sim_buy_order_assumed_filled`, `swing_sim_scale_in_order_assumed_filled`, `swing_sim_sell_order_assumed_filled`가 실제 주문 stage와 섞이지 않도록 source를 고정한다.
4. stale/missing source는 추정값으로 채우지 않고 warning으로 남긴다.

Acceptance:

- 다음 postclose `swing_lifecycle_audit`에서 `instrumentation_gap_count`가 줄거나, 남은 gap의 source/stage가 명확해진다.
- 실제 주문 여부, 수량, 가격 로직은 변경되지 않는다.

---

### 3.3 P1 — `order_swing_recommendation_db_load_gap`

목표:

추천 CSV와 DB 적재 사이의 gap을 정식 funnel 단계로 고정한다. 현재 자동화 order 기준 `csv_rows=5`, `db_rows=0` divergence가 관찰됐다.

대상:
- `src/scanners/final_ensemble_scanner.py`
- `src/engine/swing_lifecycle_audit.py`
- 필요 시 DB 적재 helper와 관련 테스트

요구사항:

1. `daily_recommendation_v2.csv` row count, final scanner selected count, DB inserted count를 같은 date/source 기준으로 집계한다.
2. DB insert skip/fail 사유를 `db_load_skip_reason` 또는 동등한 provenance로 남긴다.
3. 후보 0건 fallback diagnostic은 실전 후보와 섞지 않는다.
4. DB load gap은 주문 guard 완화 근거가 아니라 선정-적재 병목 진단 근거로만 쓴다.

Acceptance:

- `csv_rows`와 `db_rows`가 다르면 reason이 반드시 남는다.
- `final_ensemble_scanner`의 `META_V2/META_FALLBACK/EOD_TOP5/EMPTY` 구분이 유지된다.
- high-confidence 후보와 diagnostic fallback이 분리된다.

---

### 3.4 P2 — `order_swing_ai_contract_structured_output_eval`

목표:

스윙 AI 판단을 OpenAI/DeepSeek/Gemini runtime live routing 변경 없이 contract 평가 대상으로 분리한다.

대상:
- `src/engine/ai_engine.py`
- `src/engine/ai_engine_openai.py`
- `src/engine/ai_response_contracts.py`
- swing gatekeeper / holding flow / scale-in AI call site

요구사항:

1. 기존 prompt와 입출력 형식을 inventory로 남긴다.
2. free-text label, schema parse fail, fallback label, model latency, cost를 report-only metric으로 집계한다.
3. OpenAI 적용 후보는 Responses API + Structured Outputs 우선으로 설계하되, live routing 승격은 하지 않는다.
4. 프롬프트 영문화는 후보로만 남기고, 적용 전/후 disagreement를 비교할 수 있는 fixture를 만든다.

Acceptance:

- `schema_valid_rate`, `decision_disagreement_rate`, `model_call_ms_p95`, `cost_estimate`가 report에 남는다.
- `runtime_effect=false`, `allowed_runtime_apply=false`가 유지된다.

---

### 3.5 P2 — `order_swing_scale_in_avg_down_pyramid_observation`

목표:

스윙 `AVG_DOWN/PYRAMID` 관찰축을 추가하되 주문 여부, 수량, 가격은 변경하지 않는다.

대상:
- `src/engine/sniper_scale_in.py`
- `src/engine/sniper_state_handlers.py`
- `src/engine/swing_lifecycle_audit.py`

요구사항:

1. `AVG_DOWN/PYRAMID/NONE` action group을 lifecycle audit에 남긴다.
2. add trigger, add price policy, add ratio, post-add outcome, cooldown/pending/protection blocker를 분리한다.
3. OFI/QI context가 있으면 `micro_support`, `micro_risk`, `recovery_support_observed`를 report-only로 남긴다.
4. 수량/가격/주문 제출 판단은 기존 로직 그대로 유지한다.

Acceptance:

- scale-in group coverage가 report에 표시된다.
- `scale_in_unique_records=0`일 때도 원인이 `no_candidate`, `missing_stage`, `blocked_guard`, `not_loaded` 중 하나로 남는다.

---

### 3.6 P3 — Fresh DeepSeek Re-entry 조건

목표:

DeepSeek entry-no-submission finding은 stale/range 결과가 아니라 fresh single-day 결과로 다시 확인된 경우에만 workorder 후보로 재진입한다.

요구사항:

1. 다음 영업일 장후 단일 target date로 lab을 실행한다.
2. `run_manifest.json`의 `analysis_window.start == target_date == end`를 확인한다.
3. 필수 output 3종이 모두 있어야 한다.
   - `swing_pattern_analysis_result.json`
   - `data_quality_report.json`
   - `deepseek_payload_summary.json`
4. fresh 조건이 닫히지 않으면 DeepSeek finding은 warning만 남기고 order는 생성하지 않는다.

실행 예:

```bash
timeout 60 bash analysis/deepseek_swing_pattern_lab/run_all.sh 2026-05-11
PYTHONPATH=. .venv/bin/python -m src.engine.swing_pattern_lab_automation --date 2026-05-11
PYTHONPATH=. .venv/bin/python -m src.engine.build_code_improvement_workorder --date 2026-05-11 --max-orders 12
PYTHONPATH=. .venv/bin/python -m src.engine.threshold_cycle_ev_report --date 2026-05-11
```

Acceptance:

- fresh가 아니면 `code_improvement_order_count=0`.
- fresh이고 entry bottleneck이 반복되면 `design_family_candidate`로만 생성된다.
- 생성 order는 `allowed_runtime_apply=false`다.

---

## 4. 검증 명령

기본 검증:

```bash
PYTHONPATH=. .venv/bin/python -m compileall -q src/engine src/scanners
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_deepseek_swing_pattern_lab.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_build_code_improvement_workorder.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_threshold_cycle_ev_report.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_swing_model_selection_funnel_repair.py
bash -n deploy/run_threshold_cycle_postclose.sh
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
git diff --check
```

스윙 lifecycle/DB load 변경 시 추가 검증:

```bash
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_swing_model_selection_funnel_repair.py
PYTHONPATH=. .venv/bin/python -m src.engine.swing_lifecycle_audit --date 2026-05-09
PYTHONPATH=. .venv/bin/python -m src.engine.swing_selection_funnel_report --date 2026-05-09
```

---

## 5. 완료 기준

1. stale/range DeepSeek output이 workorder order로 승격되지 않는다.
2. current date workorder가 fresh source만 반영한다.
3. 스윙 CSV → DB 적재 gap이 reason과 함께 집계된다.
4. lifecycle audit의 stage coverage와 raw/unique count가 개선된다.
5. AI contract와 scale-in family는 report-only 후보로만 남고 runtime 값을 바꾸지 않는다.
6. 다음 postclose daily EV report에서 source artifact, warning, order count가 일관되게 표시된다.

---

## 6. Project/Calendar 동기화

문서/checklist를 수정했으면 parser 검증은 AI가 실행하고, Project/Calendar 동기화는 사용자가 아래 명령으로 수동 실행한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
