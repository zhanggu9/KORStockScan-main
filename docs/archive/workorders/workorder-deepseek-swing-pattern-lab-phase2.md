# 작업지시서: DeepSeek Swing Pattern Lab 2차 자동화 연결

작성일: `2026-05-09 KST`  
Owner: `SwingPatternLabDeepSeekPhase2`
Source: `analysis/deepseek_swing_pattern_lab/`, `docs/deepseek-swing-pattern-lab-build-report.md`

---

## 1. 판정

DeepSeek Swing Pattern Lab Stage 1은 독립 실행 가능한 report-only lab으로 구축됐다. Stage 1 리뷰 과정에서 population alignment (selection/carryover split, code zfill(6) 정규화, carryover-only downgrade)는 이미 구조적으로 해결됐다.

- `blocked_*_selection_unique`: 당일 추천 후보 중 block된 unique record 수
- `blocked_*_carryover_unique`: 전일 이월 포지션 등 다른 모집단에서 block된 unique record 수
- `selected_count`와 `blocked_selection_unique`는 같은 모집단
- carryover-only blocker는 `defer_evidence`로 분류되어 workorder order로 승격되지 않음
- `blocked_ratio > 1.0` 문제 없음 (ratio 자체를 제거하고 split으로 대체)

다음 단계는 lab 결과를 기존 postclose 자동화체인에 연결하는 것이다. §3.1은 Stage 1 완료 확인 및 검증 precheck만 수행하고, §3.2~§3.5가 본 구현 범위다.

---

## 2. 운영 원칙

1. 이 작업은 `report-only / proposal-only`다.
2. 스윙 live 주문, Gatekeeper, market regime hard block, gap/protection guard, 예산/주문 safety, threshold runtime 값은 변경하지 않는다.
3. 생성되는 order는 `runtime_effect=false`, `allowed_runtime_apply=false`를 유지한다.
4. 새 threshold family는 `design_family_candidate` 또는 `auto_family_candidate(allowed_runtime_apply=false)`로만 남긴다.
5. Stage 2 연결 후에도 DeepSeek 결과는 자동 적용하지 않고, `build_code_improvement_workorder`가 사람이 Codex에 넣을 작업지시서 후보로만 변환한다.

---

## 3. 구현 범위

### 3.1 Population Alignment — 완료 (검증 precheck)

Stage 1 (`prepare_dataset.py`, `analyze_swing_patterns.py`)에서 이미 구현 완료. Phase2 시작 시 검증만 수행한다:

- `swing_lifecycle_funnel_fact.csv`에 `_selection_unique` / `_carryover_unique` 컬럼 존재 확인
- `blocked_selection_unique ≤ selected_count` 확인 (없으면 실패)
- `blocked_ratio > 1.0`이 `swing_pattern_analysis_result.json`에 없는지 확인
- `pytest src/tests/test_deepseek_swing_pattern_lab.py -k "population_split"` 통과 확인

구현 참조:
- `prepare_dataset.py:404` — `_load_today_selected_codes` (dtype=str, zfill(6))
- `prepare_dataset.py:416` — `_split_blocker_unique_by_population`
- `analyze_swing_patterns.py:181` — carryover-only → defer_evidence downgrade

이 precheck 통과 전에는 §3.2~§3.5를 진행하지 않는다.

---

### 3.2 Swing Pattern Lab Automation 생성

신규:

- `src/engine/swing_pattern_lab_automation.py`

입력:

- `analysis/deepseek_swing_pattern_lab/outputs/swing_pattern_analysis_result.json`
- `analysis/deepseek_swing_pattern_lab/outputs/data_quality_report.json`
- `analysis/deepseek_swing_pattern_lab/outputs/deepseek_payload_summary.json`

출력:

- `data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_YYYY-MM-DD.json`
- `data/report/swing_pattern_lab_automation/swing_pattern_lab_automation_YYYY-MM-DD.md`

요구사항:

1. DeepSeek lab findings를 기존 workorder schema에 맞는 `code_improvement_orders`로 정규화한다.
2. `source_report_type=swing_pattern_lab_automation`을 명시한다.
3. `runtime_effect=false`, `allowed_runtime_apply=false`를 강제한다.
4. `data_quality.warnings`, `analysis_window`, `source_artifacts`, `denominator_warnings`를 포함한다.
5. 아래 분류 체계를 유지한다.
   - `implement_now`
   - `attach_existing_family`
   - `design_family_candidate`
   - `defer_evidence`
   - `reject`

Acceptance:

- 낮은 표본, OFI/QI 없음, denominator mismatch가 warning으로 전파된다.
- generated order가 runtime 변경을 요구하지 않는다.
- Markdown에 source artifact와 next postclose metric이 포함된다.

---

### 3.3 Code Improvement Workorder Intake 확장

대상:

- `src/engine/build_code_improvement_workorder.py`
- `src/tests/test_build_code_improvement_workorder.py`

요구사항:

1. 기존 입력을 유지한다.
   - `scalping_pattern_lab_automation`
   - `swing_improvement_automation`
2. 신규 입력을 추가한다.
   - `swing_pattern_lab_automation`
3. 같은 Markdown에 병합하되 source를 섞지 않는다.
   - `source_report_type=swing_pattern_lab_automation`
   - `source_report_type=swing_improvement_automation`
4. 동일 order id 충돌 시 source와 lifecycle stage를 포함해 stable dedupe key를 만든다.
5. `threshold_family`, `lifecycle_stage`, `runtime_effect`, `allowed_runtime_apply`, `next_postclose_metric`을 필수 필드로 검증한다.

Acceptance:

- scalping order와 swing lifecycle order, swing pattern lab order가 같은 workorder에 병합된다.
- 각 order의 source/stage/family가 유지된다.
- `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_build_code_improvement_workorder.py`

---

### 3.4 Postclose Wrapper 연결

대상:

- `deploy/run_threshold_cycle_postclose.sh`
- `docs/time-based-operations-runbook.md`
- 필요 시 `deploy/run_swing_live_dry_run_report.sh`

요구사항:

1. postclose 체인에서 DeepSeek swing pattern lab을 선택적으로 실행한다.
2. 기본은 report-only이며 실패해도 threshold deterministic calibration을 깨지 않는다.
3. 실행 순서:
   - swing lifecycle audit / swing improvement automation 생성
   - DeepSeek swing pattern lab 실행
   - swing pattern lab automation 생성
   - build code improvement workorder 병합
   - daily EV report 요약
4. 대형 pipeline file로 인한 timeout을 피하기 위해 기본 target date는 단일 영업일로 고정한다.
5. range 실행은 env override로만 허용한다.

Acceptance:

- `bash -n deploy/run_threshold_cycle_postclose.sh`
- target date 단일 실행이 60초 내 완료된다.
- 실패 시 status/warning만 남기고 runtime threshold 값은 변경하지 않는다.

---

### 3.5 Daily EV Report 요약 연결

대상:

- `src/engine/threshold_cycle_ev_report.py`
- 관련 테스트

요구사항:

1. daily EV report에 DeepSeek swing pattern lab automation 요약을 추가한다.
2. 최소 필드:
   - freshness
   - warning count
   - findings count
   - code improvement order count
   - top lifecycle stages
   - denominator warning 여부
3. daily EV report는 상세 lab 결과를 재해석하지 않고 artifact link와 summary만 표시한다.

Acceptance:

- `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_threshold_cycle_ev_report.py`
- Markdown에 swing pattern lab artifact 경로가 표시된다.

---

## 4. 금지 사항

- 스윙 Gatekeeper threshold 완화 금지
- `floor=0.35` 자동 변경 금지
- gap/protection guard 완화 금지
- OFI/QI 단독 BUY/EXIT hard gate 생성 금지
- DeepSeek 결과를 runtime env에 직접 반영 금지
- range default 실행으로 대형 pipeline event 전체를 매번 스캔하는 동작 금지

---

## 5. 검증 명령

```bash
timeout 60 bash analysis/deepseek_swing_pattern_lab/run_all.sh 2026-05-08
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_deepseek_swing_pattern_lab.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_build_code_improvement_workorder.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_threshold_cycle_ev_report.py
bash -n deploy/run_threshold_cycle_postclose.sh
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
git diff --check
```

---

## 6. 완료 기준

1. `blocked_ratio > 1.0` 문제가 사라진다.
2. DeepSeek swing pattern lab 결과가 `data/report/swing_pattern_lab_automation/`에 자동화 산출물로 생성된다.
3. `build_code_improvement_workorder`가 scalping, swing lifecycle, swing pattern lab order를 같은 Markdown에 병합한다.
4. daily EV report가 swing pattern lab summary와 artifact link를 표시한다.
5. 모든 변경은 `runtime_effect=false`, `allowed_runtime_apply=false` 경계를 유지한다.

