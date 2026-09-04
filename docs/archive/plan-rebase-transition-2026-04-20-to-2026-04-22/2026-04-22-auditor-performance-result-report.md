# 2026-04-22 Auditor Performance Result Report

## 판정

- 종합 등급: 조건부 보류 유지. `main-only buy_recovery_canary`는 유지하되, 오늘 표본은 `BUY 후보 회복`과 `실제 주문 회복`을 같은 성공으로 묶을 수 없다.
- canary 유지축 1개: `buy_recovery_canary prompt` 재교정 축.
- 보류축: `entry_filter_quality` 신규 live 전환, `AI threshold score/promote` 승격, AI 엔진 A/B 재개, HOLDING hybrid 확대.
- 운영 판정: `TUNING_MONITORING_POSTCLOSE` 자동실행은 정상화 완료로 본다.

## 지표표

| 지표 | 기준선/해석축 | 2026-04-22 값 | 판정 |
| --- | --- | ---: | --- |
| WAIT65~79 total_candidates | 관찰 | 246 | 후보군 관측 충분 |
| recovery_check_candidates | 관찰 | 40 | 재평가 진입 발생 |
| recovery_promoted_candidates | 관찰 | 6 | noon 대비 개선 신호 |
| submitted_candidates | 제출 연결 확인 | 0 | 미달 |
| blocked_ai_score | 감소 필요 | 208 | 병목 지속 |
| blocked_ai_score_share | 감소 필요 | 84.6% | 심각 |
| gatekeeper_decisions | hard guard 발동 N | 37 | 표본 부족 |
| gatekeeper_eval_ms_p95 | <= 15,900ms | 16,637ms | 경고 |
| budget_pass_events | 관찰 | 1,188 | 후보 존재 |
| order_bundle_submitted_events | 회복 필요 | 1 | 제출 빈약 |
| budget_pass_to_submitted_rate | 회복 필요 | 0.1% | 심각 |
| latency_block_events | 감소 필요 | 1,187 | 제출 전 병목 |
| quote_fresh_latency_blocks | 원인 분해 필요 | 947 | 주 병목 후보 |
| full_fill_events | 관찰 | 0 | 표본 없음 |
| partial_fill_events | 관찰 | 0 | 표본 없음 |
| completed_trades | 손익 판단 최소 표본 | 0 | 판정 유예 |
| post_sell evaluated_candidates | HOLDING 판정 표본 | 0 | 확대 금지 |

## 분석

- buy_recovery_canary: `recovery_check=40`, `promoted=6`으로 오늘 오후 적용한 recovery prompt 재교정이 `BUY 후보를 전혀 못 만든다` 단계는 일부 벗어났다. 다만 `submitted=0`이라 실제 주문 회복으로 이어졌다는 증거는 없다. 즉 이 축의 현재 의미는 `prompt upstream 개선 신호`이지 `실전 EV 회복 완료`가 아니다.
- why 1: `blocked_ai_score=208건(84.6%)`은 WAIT65~79 표본 대부분이 여전히 AI threshold에서 끝난다는 뜻이다. 게다가 이 blocker 코호트의 `avg_expected_ev_pct=+2.0399%`, `avg_expected_fill_rate_pct=96.6358%`라 단순히 "나쁜 후보를 많이 막았다"로 해석하기 어렵다. 기대값이 남아 있는 표본이 threshold에서 소실되고 있을 가능성이 높다.
- why 2: 다만 threshold를 바로 더 완화하지 않는 이유도 명확하다. 오늘 제출 경로는 `budget_pass_events=1,188`인데 `submitted_events=1`, `latency_block_events=1,187`, `quote_fresh_latency_blocks=947`다. 즉 지금의 1차 병목은 `후보 부족`만이 아니라 `제출 직전 latency/quote freshness 단절`이다. threshold를 더 낮추면 후보 수만 늘고 제출 단절이 유지될 위험이 크다.
- latency: `gatekeeper_eval_ms_p95=16,637ms`는 경고 구간이다. 그러나 `gatekeeper_decisions=37 < N_min(50)`이라 hard OFF 근거로는 아직 부족하다. 오늘 추가한 경로 분해 계측(`lock_wait_ms`, `model_call_ms`, `total_internal_ms`)은 내일 장전부터 누적 관찰이 가능하고, 오늘 snapshot에는 `lock_wait/model_call p95=0`으로 아직 유효 관측이 쌓이지 않았다.
- HOLDING: `post_sell evaluated_candidates=0`, `completed_trades=0`라 성과 최종판정과 hybrid 확대는 모두 유예가 맞다. 표본 없이 확대하면 기대값 개선이 아니라 해석 왜곡이 된다.
- 자동화/증적: `logs/tuning_monitoring_postclose_cron.log` 기준 `2026-04-22 18:00:03 KST` 자동실행이 시작됐고, `pipeline_events_20260422.parquet=442,652 rows`, `system_metric_samples_20260422.parquet=641 rows`, `shadow_diff all_match=true`가 확인됐다. 이후 오늘 재생성한 Claude/Gemini 랩도 각각 [`analysis/claude_scalping_pattern_lab/outputs/final_review_report_for_lead_ai.md`](/home/ubuntu/KORStockScan/analysis/claude_scalping_pattern_lab/outputs/final_review_report_for_lead_ai.md), [`analysis/gemini_scalping_pattern_lab/outputs/final_review_report_for_lead_ai.md`](/home/ubuntu/KORStockScan/analysis/gemini_scalping_pattern_lab/outputs/final_review_report_for_lead_ai.md)와 `tuning_observability_summary.*`를 생성했고, 두 manifest 모두 `history_coverage_ok=true`다.

## 감사인 응답

- Q1 `buy_recovery_canary prompt` 재교정은 유효했나: 부분 유효다. `promoted=6`이 이를 뒷받침하지만 `submitted=0`이므로 "BUY 회복 완료"가 아니라 "후보 회복 조짐"으로만 판정한다.
- Q2 여전히 BUY 신호 자체가 적다고 봐야 하나: 그렇다. `blocked_ai_score_share=84.6%`가 이를 보여준다. 다만 문제를 `AI threshold 단일 병목`으로만 닫으면 안 된다. 같은 날 `budget_pass=1,188`, `latency_block=1,187`이므로 제출 경로 병목이 동시 존재한다.
- Q3 왜 threshold 완화축을 오늘 바로 승격하지 않나: 현재는 `promoted 증가`가 `submitted 증가`로 이어지지 않는다. 이 상태에서 더 완화하면 원인 귀속이 `threshold`, `latency`, `quote freshness` 중 무엇인지 더 흐려진다.
- Q4 gatekeeper latency는 성능 문제인가: 오늘 수치만 보면 "성능 경고"는 맞지만, 아직 어느 경로가 원인인지는 분해 전이다. 그래서 오늘 코드는 `lock_wait/model_call/total_internal`을 남기도록 보강했고, 내일 장전 스냅샷부터 성능 병목인지 외부 대기인지 판단 가능하다.

## 다음 액션

- `2026-04-23 PREOPEN 08:30~08:40`: `gatekeeper lock_wait/model_call/total_internal p95`와 `quote_fresh_latency_blocks`를 같이 확인한다.
- `2026-04-23 PREOPEN 08:30~08:40`: `WAIT65~79 -> recovery_check -> promoted -> submitted` 연결이 실제로 1건 이상 생겼는지 재판정한다.
- `2026-04-23 POSTCLOSE 15:20~15:35`: `entry_filter_quality` 전환 가능성은 `submitted/completed` 표본과 latency 분해 결과를 본 뒤 단일축으로만 결정한다.
- Project/Calendar 동기화 재실행은 토큰이 있는 환경에서 아래 1개 명령으로 정리한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
