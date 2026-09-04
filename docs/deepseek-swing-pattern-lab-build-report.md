# DeepSeek Swing Pattern Lab 구축 완료 보고서

작성일: `2026-05-09T16:06 KST` (v4 — population alignment + code zfill + carryover downgrade)
Owner: `SwingPatternLabDeepSeekBuild`
기반 문서: `docs/archive/workorders/workorder-deepseek-swing-pattern-lab.md`

---

## 1. 판정

Stage 1 독립 lab 구축 완료. `run_all.sh` 인자/무인자 독립 실행 성공. population alignment 구조적 해결, carryover-only blocker downgrade 적용, code zfill(6) 정규화 완료.

---

## 2. 리뷰 Fix 전체 내역 (10건)

| # | 심각도 | 이슈 | 수정 |
|---|:--:|------|------|
| 1 | HIGH | `entered=True`가 block 이벤트를 진입으로 오인 | `ACTUAL_ENTRY_STAGES` 정의, submission·fill만 `entered=True` |
| 2 | HIGH | funnel 분석이 raw counts를 병목 수치로 사용 | `unique_record_counts` 기반 `_unique`/`_raw` 분리 |
| 3 | HIGH | gap block이 gatekeeper cooldown으로 잘못 매핑 | `design_family_candidate`, `mapped_family=None` |
| 4 | HIGH | 모집단 불일치: `blocked=9`와 `selected=5` 동시 표시 | pipeline events와 daily_recommendations_v2.csv 교차참조, `_selection_unique` / `_carryover_unique` 구조적 분리 |
| 5 | HIGH | 종목코드 leading zero 손실 → selection/carryover split 깨짐 | `pd.read_csv(dtype={"code": str})`, 비교 전 `zfill(6)` 정규화 |
| 6 | MEDIUM | data quality warning 분석 결과에서 누락 | `_load_json("data_quality_report.json")` → analysis_result 전파 |
| 7 | MEDIUM | DB `record_id` 항상 빈 값 | SQL SELECT에 `id` 컬럼 추가 |
| 8 | MEDIUM | `stages_seen` raw 무제한 누적 (CSV 2MB → 10KB) | per-stage `{count, first_at, last_at}` 압축 |
| 9 | MEDIUM | `run_all.sh` 인자 무시, env 없으면 타임아웃 | `$1` → TARGET_DATE → env export, 기본값 오늘 |
| 10 | MEDIUM | carryover-only blocker가 family 개선 order로 승격 | `blocked_selection_unique==0` 시 `defer_evidence` 다운그레이드 |

---

## 3. Population Alignment 구조

```
daily_recommendations_v2.csv ──→ _load_today_selected_codes() ──→ selected_codes set (zfill(6))
                                                                        │
pipeline_events_{date}.jsonl ──→ _split_blocker_unique_by_population() ─┤
                                                                        │
  ├── code ∈ selected_codes  ──→ blocked_*_selection_unique
  └── code ∉ selected_codes  ──→ blocked_*_carryover_unique
```

- CSV 읽기: `dtype={"code": str}` → `011210` 유지
- 비교: `code.strip().zfill(6)` → 양측 6자리 정합
- 분류: `blocked_selection_unique` (당일 추천 후보가 막힘) vs `blocked_carryover_unique` (전일 이월 포지션)

---

## 4. Fact Table 산출물

| Fact | 컬럼 수 | 특징 |
|------|--:|------|
| `swing_trade_fact.csv` | 26 | id 보존, DB 연동 |
| `swing_lifecycle_funnel_fact.csv` | 37 | `_unique`/`_raw`/`_selection_unique`/`_carryover_unique` 4계층 |
| `swing_sequence_fact.csv` | 15 | stages_seen 압축, `entered` = submission only |
| `swing_ofi_qi_fact.csv` | 22 | stale_missing_flag 집계 |

---

## 5. 분석 결과 (2026-05-08~09)

### 5.1 Findings (5건)

| # | finding_id | route | blocked_sel | blocked_carry | selected |
|--:|------------|------|--:|--:|--:|
| 1 | `entry_gatekeeper_reject` | `defer_evidence` | 0 | 9 | 5 |
| 2 | `entry_gap_block` | `defer_evidence` | 0 | 2 | 5 |
| 3 | `entry_market_regime_block` | `defer_evidence` | 0 | 1 | 5 |
| 4 | `entry_no_submissions` | `design_family_candidate` | — | — | 5 |
| 5 | `holding_exit_no_trades` | `defer_evidence` | — | — | — |

### 5.2 Code Improvement Orders (1건)

| order_id | route | lifecycle_stage | runtime_effect | allowed_runtime_apply |
|----------|------|:-:|:--:|:--:|
| `order_...entry_no_submissions` | `design_family_candidate` | entry | false | false |

carryover-only blocker는 `defer_evidence`로 분류되어 order 미생성.

---

## 6. 실행 방법

```bash
# 오늘 날짜 단일 실행
bash analysis/deepseek_swing_pattern_lab/run_all.sh

# 특정 날짜
bash analysis/deepseek_swing_pattern_lab/run_all.sh 2026-05-08

# 범위
ANALYSIS_START_DATE=2026-05-01 ANALYSIS_END_DATE=2026-05-09 bash analysis/deepseek_swing_pattern_lab/run_all.sh
```

---

## 7. Acceptance Tests

```
pytest test_deepseek_swing_pattern_lab.py              25 passed
pytest test_swing_model_selection_funnel_repair.py     14 passed
pytest test_build_code_improvement_workorder.py          3 passed
pytest test_threshold_cycle_ev_report.py                 (verified)
compileall -q analysis/deepseek_swing_pattern_lab       OK
git diff --check                                         OK
```

---

## 8. 금지사항 준수

| 규칙 | 확인 |
|------|:--:|
| `runtime_effect=false` | PASS |
| `allowed_runtime_apply=false` | PASS |
| OFI/QI 단독 hard gate 없음 | PASS |
| 스윙 live 로직 변경 없음 | PASS |
| 스캘핑 lab과 혼합 없음 | PASS |
| 패키지 설치 없음 | PASS |
| `run_all.sh` 인자/무인자 작동 | PASS |
| blocker 분리: selection/carryover + zfill(6) | PASS |
| carryover-only → defer_evidence | PASS |

---

## 9. Phase2 연결 전제조건

Phase2 (`docs/archive/workorders/workorder-deepseek-swing-pattern-lab-phase2.md`) 자동화 연결 전:

- code zfill(6) 정규화 닫힘 ✓
- selection/carryover population split 닫힘 ✓
- carryover-only blocker defer_evidence 닫힘 ✓
- freshness guard (date-partitioned output) **미구현** — Phase2에서 `run_manifest.analysis_window` 검증 추가 필요
- Phase2 workorder의 정합성 선해결 → 자동화 연결 순서 강제 **미반영** — 문서 수정은 별도

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
