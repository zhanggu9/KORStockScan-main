# 작업지시서: DeepSeek Swing Pattern Lab 구축

작성일: `2026-05-09 KST`
대상: DeepSeek coding/analysis agent
Owner: `SwingPatternLabDeepSeekBuild`

---

## 1. 판정

현재 코드베이스에는 스캘핑과 동일한 의미의 스윙 전용 pattern lab이 없다.

- 스캘핑은 `analysis/gemini_scalping_pattern_lab/`, `analysis/claude_scalping_pattern_lab/`, `src/engine/scalping_pattern_lab_automation.py`로 독립 분석 랩과 자동화 정규화 체인을 갖고 있다.
- 스윙은 `src/engine/swing_lifecycle_audit.py`, `swing_threshold_ai_review`, `swing_improvement_automation`으로 lifecycle audit과 workorder 후보 생성은 갖고 있으나, 누적 스윙 데이터를 별도 fact table로 구성하고 DeepSeek가 패턴/EV 개선 후보를 분석하는 독립 lab은 아직 없다.

따라서 DeepSeek에는 스윙 로직 직접 변경이 아니라 `analysis/deepseek_swing_pattern_lab/` 신규 구축을 지시한다.

---

## 2. 운영 원칙

1. 이 작업은 `report-only / proposal-only`다.
2. 스윙 live 주문, Gatekeeper, market regime hard block, gap/protection guard, 예산/주문 safety, threshold runtime 값은 변경하지 않는다.
3. 산출되는 개선 후보는 `runtime_effect=false`, `allowed_runtime_apply=false`로 시작한다.
4. 새 threshold family가 필요하면 `design_family_candidate`로만 남긴다. sample floor, bounds, max step, rollback guard, source metrics가 닫히기 전에는 적용 후보가 될 수 없다.
5. DeepSeek 결과는 자동 적용하지 않고, `swing_pattern_lab_automation` 또는 `build_code_improvement_workorder`를 통해 사람이 Codex에 넣을 수 있는 작업지시서 후보로만 변환한다.
6. 기존 스캘핑 pattern lab 산출물과 섞지 않는다. 스윙은 `selection -> db_load -> entry -> holding -> scale_in -> exit -> attribution` lifecycle 기준으로 분리한다.

---

## 3. 구축 범위

### 3.1 신규 디렉터리

`analysis/deepseek_swing_pattern_lab/`를 생성한다.

권장 구조:

```text
analysis/deepseek_swing_pattern_lab/
├── README.md
├── config.py
├── prepare_dataset.py
├── analyze_swing_patterns.py
├── build_deepseek_payload.py
├── run_all.sh
├── prompts/
│   ├── prompt_swing_lifecycle_patterns.md
│   ├── prompt_swing_entry_patterns.md
│   ├── prompt_swing_holding_exit_patterns.md
│   └── prompt_swing_scale_in_patterns.md
└── outputs/
    ├── swing_trade_fact.csv
    ├── swing_lifecycle_funnel_fact.csv
    ├── swing_sequence_fact.csv
    ├── swing_ofi_qi_fact.csv
    ├── data_quality_report.md
    ├── swing_pattern_analysis_result.json
    ├── swing_ev_improvement_backlog_for_ops.md
    ├── deepseek_payload_summary.json
    ├── deepseek_payload_cases.json
    ├── final_review_report_for_lead_ai.md
    └── run_manifest.json
```

### 3.2 입력 데이터

우선순위는 local canonical report와 pipeline event를 먼저 사용한다.

필수 입력:

- `data/report/swing_lifecycle_audit/swing_lifecycle_audit_YYYY-MM-DD.json`
- `data/report/swing_selection_funnel/swing_selection_funnel_YYYY-MM-DD.json`
- `data/report/swing_improvement_automation/swing_improvement_automation_YYYY-MM-DD.json`
- `data/pipeline_events/pipeline_events_YYYY-MM-DD.jsonl`
- `data/daily_recommendations_v2.csv`
- `recommendation_history` DB rows, DB 접근 실패 시 report/file fallback

선택 입력:

- `data/report/swing_threshold_ai_review/swing_threshold_ai_review_YYYY-MM-DD.json`
- `data/report/threshold_cycle_ev/threshold_cycle_ev_YYYY-MM-DD.json`
- `data/report/code_improvement_workorder/code_improvement_workorder_YYYY-MM-DD.json`

### 3.3 Fact Table

최소 4개 fact를 생성한다.

1. `swing_trade_fact.csv`
   - `date`, `record_id`, `stock_code`, `stock_name`, `strategy`, `position_tag`
   - `selection_mode`, `hybrid_mean`, `meta_score`, `floor_used`, `score_rank`
   - `status`, `buy_qty`, `buy_price`, `sell_qty`, `sell_price`
   - `completed`, `valid_profit_rate`, `profit_rate`, `profit`
   - `actual_order_submitted`, `simulation_owner`

2. `swing_lifecycle_funnel_fact.csv`
   - stage별 raw/unique counts
   - `selected_count`, `csv_rows`, `db_rows`
   - `blocked_swing_gap`, `blocked_gatekeeper_reject`, `market_regime_block/pass`
   - `submitted_unique_records`, `simulated_order_unique_records`
   - `missed_entry`, `blocked_reason`, `gatekeeper_action`

3. `swing_sequence_fact.csv`
   - record 단위 event sequence
   - `selection -> db_load -> entry -> holding -> scale_in -> exit` stage order
   - `entered`, `held`, `scale_in_observed`, `exited`, `completed`
   - `exit_source`, `sell_reason_type`, `holding_flow_action`

4. `swing_ofi_qi_fact.csv`
   - `orderbook_micro_ready`, `orderbook_micro_state`
   - `orderbook_micro_qi`, `orderbook_micro_qi_ewma`
   - `orderbook_micro_ofi_norm`, `orderbook_micro_ofi_z`
   - `orderbook_micro_snapshot_age_ms`, `orderbook_micro_observer_healthy`
   - `orderbook_micro_ofi_threshold_source`, `orderbook_micro_ofi_bucket_key`
   - `swing_micro_advice`, `swing_micro_runtime_effect`
   - `smoothing_action`, `stale_missing_flag`

---

## 4. DeepSeek 분석 과제

DeepSeek는 아래 질문에 JSON과 Markdown으로 답한다.

1. 선정 병목
   - 추천 후보가 0건 또는 소수일 때 원인이 model floor, safe pool, fallback 분리, score distribution 중 어디인지 분리한다.
   - `floor=0.35`는 조정 가능한 threshold family 후보로만 본다.

2. 진입 병목
   - 추천 이후 DB 적재, Gatekeeper reject, market regime block, gap/protection, budget/price/latency guard 중 어디서 스윙 후보가 막히는지 분해한다.
   - 단독 OFI/QI BUY hard gate 제안은 금지한다.

3. 보유/청산 병목
   - MFE/MAE, peak drawdown, time stop, trailing, holding-flow defer cost, post-sell rebound를 기준으로 청산 품질을 분해한다.
   - holding-flow OFI smoothing은 기존 postprocessor 범위에서만 평가한다.

4. PYRAMID/AVG_DOWN 병목
   - `PYRAMID`, `AVG_DOWN`, `NONE` 후보를 분리한다.
   - OFI/QI는 confirmation/provenance로만 평가한다. 수량/가격/주문 여부를 바꾸는 제안은 금지한다.

5. OFI/QI 관찰 품질
   - stale/missing ratio, observer health, threshold source, bucket coverage를 평가한다.
   - stale/missing이 크면 runtime logic 변경이 아니라 instrumentation/orderbook observer 보강 후보로 분류한다.

6. 개선 후보 분류
   - 각 후보를 아래 중 하나로 분류한다.
     - `implement_now`
     - `attach_existing_family`
     - `design_family_candidate`
     - `defer_evidence`
     - `reject`

---

## 5. 출력 Schema

`outputs/swing_pattern_analysis_result.json`은 최소 아래 구조를 가진다.

```json
{
  "schema_version": 1,
  "report_type": "deepseek_swing_pattern_lab",
  "analysis_start": "YYYY-MM-DD",
  "analysis_end": "YYYY-MM-DD",
  "runtime_change": false,
  "data_quality": {
    "trade_rows": 0,
    "lifecycle_event_rows": 0,
    "completed_valid_profit_rows": 0,
    "ofi_qi_rows": 0,
    "warnings": []
  },
  "stage_findings": [
    {
      "finding_id": "string",
      "title": "string",
      "lifecycle_stage": "selection|db_load|entry|holding|scale_in|exit|attribution|ofi_qi",
      "route": "implement_now|attach_existing_family|design_family_candidate|defer_evidence|reject",
      "mapped_family": "string|null",
      "confidence": "consensus|solo|low_sample",
      "evidence": {},
      "runtime_effect": false
    }
  ],
  "code_improvement_orders": [
    {
      "order_id": "order_string",
      "title": "string",
      "lifecycle_stage": "string",
      "target_subsystem": "string",
      "priority": 1,
      "route": "string",
      "mapped_family": "string|null",
      "threshold_family": "string|null",
      "intent": "string",
      "expected_ev_effect": "string",
      "files_likely_touched": [],
      "acceptance_tests": [],
      "evidence": [],
      "improvement_type": "string",
      "runtime_effect": false,
      "allowed_runtime_apply": false,
      "next_postclose_metric": "string"
    }
  ]
}
```

Markdown 출력:

- `outputs/final_review_report_for_lead_ai.md`
- `outputs/swing_ev_improvement_backlog_for_ops.md`
- `outputs/data_quality_report.md`

---

## 6. 자동화 연결

### 6.1 1차 구현

DeepSeek는 우선 독립 lab만 구현한다.

필수 명령:

```bash
PYTHONPATH=. .venv/bin/python analysis/deepseek_swing_pattern_lab/prepare_dataset.py
PYTHONPATH=. .venv/bin/python analysis/deepseek_swing_pattern_lab/analyze_swing_patterns.py
PYTHONPATH=. .venv/bin/python analysis/deepseek_swing_pattern_lab/build_deepseek_payload.py
bash analysis/deepseek_swing_pattern_lab/run_all.sh
```

### 6.2 2차 연결 후보

1차 산출물이 안정화된 뒤에만 아래 연결을 별도 change set으로 검토한다.

- `src/engine/swing_pattern_lab_automation.py`
- `data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_YYYY-MM-DD.{json,md}`
- `src/engine/build_code_improvement_workorder.py`에 `swing_pattern_lab_automation` source 추가
- `deploy/run_threshold_cycle_postclose.sh`에서 swing lifecycle automation 이후 실행
- `src/engine/threshold_cycle_ev_report.py`에 summary/warning 연결

2차 연결에서도 runtime 변경은 금지한다.

---

## 7. Acceptance Tests

필수 테스트:

```bash
PYTHONPATH=. .venv/bin/python -m compileall -q analysis/deepseek_swing_pattern_lab
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_swing_model_selection_funnel_repair.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_build_code_improvement_workorder.py
git diff --check
```

신규 테스트 권장:

- `src/tests/test_deepseek_swing_pattern_lab.py`
  - fixture 기반 `prepare_dataset` fact 생성
  - 후보 0건, DB 적재 0건, gatekeeper 전량 reject, market regime block, scale-in 없음, exit 없음 케이스
  - OFI/QI stale/missing 집계
  - 모든 order가 `runtime_effect=false`, `allowed_runtime_apply=false`인지 확인

문서/checklist를 수정했다면 parser 검증:

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
```

Project/Calendar 동기화는 사용자가 수동으로 실행한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```

---

## 8. 금지 사항

- 스윙 실제 주문 활성화 또는 `SWING_LIVE_ORDER_DRY_RUN_ENABLED` 기본값 변경 금지
- Gatekeeper, gap guard, market regime hard block, protection guard 완화 금지
- OFI/QI 단독 BUY/EXIT hard gate 추가 금지
- DeepSeek 분석 결과를 runtime env나 threshold value에 직접 반영 금지
- 스캘핑 pattern lab 산출물과 스윙 산출물을 같은 fact table에서 혼합 금지
- 패키지 설치/업그레이드/제거 금지

---

## 9. 완료 기준

1. `analysis/deepseek_swing_pattern_lab/run_all.sh`가 독립 실행된다.
2. `outputs/`에 fact CSV, JSON, Markdown, manifest가 생성된다.
3. 스윙 lifecycle stage별 병목과 OFI/QI stale/missing 품질이 분리 집계된다.
4. `code_improvement_orders`는 모두 `runtime_effect=false`, `allowed_runtime_apply=false`다.
5. 신규 후보는 기존 threshold family에 붙거나 `design_family_candidate`로만 남는다.
6. 테스트와 `git diff --check`가 통과한다.

