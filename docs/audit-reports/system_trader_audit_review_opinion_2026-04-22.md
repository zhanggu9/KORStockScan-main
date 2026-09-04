# 시스템 트레이더 검토의견서

- **문서명**: 2026-04-22 감리보고서 검토의견
- **검토자 관점**: 시스템 트레이더 / 실거래 운영 리스크 관점
- **검토대상**: `2026-04-22 Auditor Performance Result Report`
- **검토일**: 2026-04-22
- **종합의견**: **조건부 보류 유지 / 부분 수용**

---

## 1. 종합 검토의견

본 감리보고서의 핵심 판정인 **조건부 보류 유지**는 타당하다.  
`main-only buy_recovery_canary`는 유지할 수 있으나, 금일 표본만으로는 **BUY 후보 회복**과 **실제 주문 회복**을 동일한 성공으로 해석할 수 없다.

시스템 트레이딩 관점에서 금일 데이터는 다음과 같이 해석한다.

1. `buy_recovery_canary prompt` 재교정은 **상류 후보 생성 측면에서 부분 개선 신호**를 보였다.
2. 그러나 `submitted_candidates=0`, `order_bundle_submitted_events=1`, `budget_pass_to_submitted_rate=0.1%`로 인해 **실거래 주문 경로 회복은 아직 입증되지 않았다**.
3. `blocked_ai_score_share=84.6%`는 AI threshold 병목이 여전히 크다는 점을 보여주지만, 동시에 `latency_block_events=1,187`, `quote_fresh_latency_blocks=947`이 존재하므로 문제를 threshold 단일 병목으로 단정해서는 안 된다.
4. `completed_trades=0`, `full_fill_events=0`, `partial_fill_events=0` 상태에서는 손익, 체결 품질, 실전 EV를 판정할 수 없다.

따라서 본 검토의견은 **“후보 회복 조짐은 인정하되, 주문·체결·손익 회복은 미입증”**으로 정리한다.

---

## 2. 운영 판정

| 구분 | 검토의견 | 판정 |
| --- | --- | --- |
| `main-only buy_recovery_canary` | 후보 회복 조짐이 있으므로 제한적 유지 가능 | **유지** |
| `buy_recovery_canary prompt` 재교정 | `recovery_check=40`, `promoted=6`으로 부분 효과 확인 | **부분 수용** |
| `entry_filter_quality` live 전환 | 주문·체결 표본이 없어 품질 검증 불가 | **보류** |
| `AI threshold score/promote` 승격 | threshold 병목은 있으나 latency/quote freshness 병목과 혼재 | **보류** |
| AI 엔진 A/B 재개 | 현재 주문 경로가 회복되지 않아 비교 실험 신뢰도 낮음 | **보류** |
| HOLDING hybrid 확대 | `post_sell evaluated_candidates=0`, `completed_trades=0`로 근거 부족 | **금지/보류** |
| `TUNING_MONITORING_POSTCLOSE` 자동실행 | 로그 및 산출물 증적은 확인되나 전략/튜닝 판정과는 분리 | **운영 정상화 인정(전략판정 분리)** |

---

## 3. 트레이딩 관점 핵심 해석

### 3.1 BUY 후보 회복과 주문 회복은 분리해서 봐야 한다

금일 `recovery_promoted_candidates=6`은 canary prompt 재교정이 완전히 실패한 것은 아님을 보여준다.  
다만 `submitted_candidates=0`이므로 이 개선은 아직 **실제 매수 주문**, **체결**, **손익 기여**로 이어졌다고 볼 수 없다.

트레이더 관점에서 이는 다음 의미를 가진다.

- 알파 후보 생성 로직은 일부 살아나는 조짐이 있다.
- 하지만 주문 라우팅 또는 제출 직전 경로에서 병목이 발생하고 있다.
- 따라서 현재 상태를 “전략 회복”이 아니라 “후보 생성 회복 초기 신호”로만 취급해야 한다.

### 3.2 AI threshold 완화는 즉시 승격하지 않는 것이 맞다

`blocked_ai_score=208`, `blocked_ai_score_share=84.6%`는 threshold가 과도하게 보수적일 가능성을 시사한다.  
특히 blocker 코호트의 기대 EV와 fill rate가 양호하게 제시된 점은, 기대값이 남아 있는 후보가 threshold에서 소실되고 있을 가능성을 열어둔다.

그러나 금일 `budget_pass_events=1,188` 대비 `order_bundle_submitted_events=1`에 불과하고, `latency_block_events=1,187`, `quote_fresh_latency_blocks=947`이 확인되었다.  
이는 threshold를 낮추더라도 실제 제출 경로가 회복되지 않으면 후보 수만 늘고 체결 가능성은 개선되지 않을 수 있음을 의미한다.

따라서 threshold 완화는 다음 조건을 확인한 뒤 단일축 실험으로 진행해야 한다.

- `quote_fresh_latency_blocks` 감소 여부
- `budget_pass -> submitted` 전환율 회복 여부
- `recovery_promoted -> submitted` 연결 발생 여부
- gatekeeper 내부 지연 원인 분해 결과

### 3.3 현재 1차 리스크는 “신호 부재”만이 아니라 “제출 전 단절”이다

감리보고서상 주요 병목은 두 축으로 나뉜다.

| 병목 축 | 근거 지표 | 해석 |
| --- | ---: | --- |
| AI threshold 병목 | `blocked_ai_score_share=84.6%` | 후보가 AI score 단계에서 대량 차단 |
| 제출 전 latency/quote 병목 | `latency_block_events=1,187`, `quote_fresh_latency_blocks=947` | 주문 직전 quote freshness 또는 latency 조건에서 대량 차단 |

따라서 금일 장애를 단순히 “BUY 신호가 적다”로만 표현하는 것은 불충분하다.  
정확한 표현은 **“BUY 후보 회복은 일부 관측되나, AI threshold와 제출 전 latency/quote freshness 병목이 동시에 존재한다”**이다.

### 3.4 손익 판단은 유예해야 한다

금일 `completed_trades=0`, `full_fill_events=0`, `partial_fill_events=0`이므로 다음 항목은 판정할 수 없다.

- 실현 손익
- 기대 EV 대비 실제 EV
- fill quality
- slippage
- holding 로직 성과
- post-sell 판단 품질

성과 표본이 없는 상태에서 HOLDING hybrid를 확대하거나 entry filter를 live 전환하면, 이는 개선 실험이 아니라 **해석 불가능한 운영 리스크 확대**가 된다.

---

## 4. 리스크 평가

| 리스크 | 수준 | 설명 | 대응 |
| --- | --- | --- | --- |
| 주문 제출 단절 리스크 | 높음 | `budget_pass` 이후 대부분이 submitted로 연결되지 않음 | latency/quote freshness 원인 분해 우선 |
| threshold 과차단 리스크 | 높음 | WAIT65~79 후보의 84.6%가 AI score에서 차단 | 즉시 완화 금지, 단일축 재검증 |
| latency 리스크 | 중간~높음 | `gatekeeper_eval_ms_p95=16,637ms`로 경고 구간 | `lock_wait/model_call/total_internal` p95 누적 확인 |
| 체결 표본 부족 리스크 | 높음 | full/partial fill 모두 0 | 손익 판단 유예 |
| 실험 오염 리스크 | 높음 | threshold, latency, quote 병목이 혼재 | 다중 변경 금지, 한 번에 한 축만 변경 |
| 자동화 증적 리스크 | 낮음 | postclose cron 및 산출물 확인 | 현 상태 유지 |

---

## 5. 승인 가능 항목과 운영 증적 분리

다음 항목은 제한적으로 승인 가능하다.

### 5.1 `main-only buy_recovery_canary` 유지

- 목적: BUY 후보 회복 여부 관찰
- 조건: live 확대 없이 canary 범위 유지
- 판정 기준: `recovery_promoted -> submitted` 연결이 실제로 발생하는지 확인

### 5.2 `buy_recovery_canary prompt` 재교정 지속 관찰

- `recovery_check=40`, `promoted=6`은 부분 개선 신호로 인정
- 단, 이는 주문 회복이 아니라 후보 회복 신호로만 분류
- 장전에는 계측/로그 반영 여부만 확인하고, 장중/장후 표본에서 submitted 연결 여부를 필수 확인

### 5.3 `TUNING_MONITORING_POSTCLOSE` 자동실행 정상화는 운영 증적으로만 인정

- 자동실행 로그 및 산출물 증적이 존재하므로 운영 자동화 측면은 정상화 완료로 본다.
- 단, 자동화 정상화는 전략 성과 정상화나 Plan Rebase 튜닝 승인 근거를 의미하지 않는다.

---

## 6. 비승인 또는 보류 항목

다음 항목은 금일 기준 승인하지 않는다.

### 6.1 `entry_filter_quality` 신규 live 전환 보류

주문 제출과 체결 표본이 부족하므로 entry filter 품질을 live 환경에서 검증할 수 없다.  
submitted/completed 표본 확보 전 live 전환은 금지한다.

### 6.2 `AI threshold score/promote` 승격 보류

threshold 병목은 명확하지만, latency 및 quote freshness 병목이 동시에 존재한다.  
현 시점에서 threshold를 완화하면 원인 귀속이 불명확해지고, 후보 증가가 주문 회복으로 이어지는지 판단하기 어렵다.

### 6.3 AI 엔진 A/B 재개 보류

현재 주문 제출 경로가 안정화되지 않았으므로 A/B 결과가 모델 성능 차이인지, latency/quote freshness 차이인지 구분하기 어렵다.

### 6.4 HOLDING hybrid 확대 금지

`post_sell evaluated_candidates=0`, `completed_trades=0` 상태에서는 HOLDING 품질을 검증할 수 없다.  
체결 및 청산 표본이 확보되기 전 확대하지 않는다.

---

## 7. 다음 거래일 확인 기준

### 7.1 PREOPEN 확인 항목

`2026-04-23 08:30~08:40 KST` 구간에서 다음 항목을 우선 확인한다.

| 확인 항목 | 목표/판정 기준 |
| --- | --- |
| `gatekeeper lock_wait_ms p95` | 내부 lock 대기 병목 여부 판단 |
| `gatekeeper model_call_ms p95` | 모델 호출 지연 여부 판단 |
| `gatekeeper total_internal_ms p95` | 전체 내부 처리 병목 판단 |
| `quote_fresh_latency_blocks` | quote freshness 단절이 지속되는지 확인 |
| `WAIT65~79 계측 체인 + 신규 필드 반영 여부` | 전일 기준 `recovery_check/promoted` 체인이 남아 있고, 금일 장전 raw log/snapshot에서 신규 계측 필드가 확인되면 통과. same-day `submitted` 확인은 `INTRADAY/POSTCLOSE`로 이월 |

### 7.2 POSTCLOSE 확인 항목

`2026-04-23 15:20~15:35 KST` 구간에서 다음 항목을 확인한다.

| 확인 항목 | 판정 방향 |
| --- | --- |
| `submitted_candidates` | 후보 회복이 주문 회복으로 이어졌는지 판단 |
| `order_bundle_submitted_events` | 제출 경로 회복 여부 판단 |
| `budget_pass_to_submitted_rate` | latency/quote 병목 완화 여부 판단 |
| `full_fill_events`, `partial_fill_events` | 체결 표본 발생 여부 판단 |
| `completed_trades` | 손익 및 holding 평가 가능 여부 판단 |

---

## 8. 의사결정 규칙

향후 변경은 다음 원칙을 적용한다.

1. **다중 변경 금지**  
   threshold, prompt, latency, quote freshness 관련 변경을 동시에 적용하지 않는다.

2. **후보 회복과 주문 회복 분리 판정**  
   `promoted` 증가는 후보 회복으로만 보고, `submitted` 또는 `fill` 증가 없이는 실전 회복으로 판정하지 않는다.

3. **체결 표본 없는 손익 판단 금지**  
   `completed_trades=0` 상태에서 EV, holding, post-sell 성과를 결론 내리지 않는다.

4. **latency/quote freshness 우선 분해**  
   `budget_pass` 이후 대부분이 제출되지 않는 현 상태에서는 threshold보다 제출 전 단절 원인 분해를 우선한다.

5. **canary 범위 유지**  
   `main-only buy_recovery_canary`는 유지하되, live 확대 또는 자본 배분 확대는 금지한다.

---

## 9. 최종 의견

시스템 트레이더 관점에서 본 감리보고서는 **보수적이고 타당한 판정**으로 판단된다.  
금일의 핵심은 `buy_recovery_canary`의 후보 회복 가능성이 일부 관측되었다는 점이지만, 주문 제출·체결·손익으로 이어지는 실전 경로는 아직 회복되지 않았다.

따라서 최종 검토의견은 다음과 같다.

> **`buy_recovery_canary prompt` 재교정은 부분 유효로 인정하되, 전략 회복으로 승격하지 않는다.**  
> **AI threshold 완화, entry filter live 전환, AI A/B 재개, HOLDING hybrid 확대는 모두 보류한다.**  
> **다음 거래일에는 threshold 조정보다 latency/quote freshness 병목 분해와 `promoted -> submitted` 연결 확인을 최우선으로 한다.**

---

## 10. 실행 메모

Project/Calendar 동기화 재실행은 토큰이 있는 운영 환경에서 아래 명령으로 정리한다.

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project && \
PYTHONPATH=. .venv/bin/python -m src.engine.sync_github_project_calendar
```
