# 2026-04-21 튜닝 Plan Rebase 감사보고서

작성일: `2026-04-21`  
작성시각: `2026-04-21 10:40 KST`  
대상: 감사인 / 운영 트레이더 / Codex  
상태: `감사인 재검토 최종 반영본`  
관련 작업지시서: [workorder-0421-tuning-plan-rebase.md](/home/ubuntu/KORStockScan/docs/archive/workorders/workorder-0421-tuning-plan-rebase.md)

---

## 1. 판정

기존 튜닝 plan은 전면 개편이 필요하다.

`2026-04-21 09:45 KST` 이후부터 기존 `partial/rebase`, `split-entry`, `soft_stop`, `latency fallback` 중심의 승격/롤백 판단을 그대로 진행하지 않는다. 현재 단계는 파라미터 튜닝이 아니라 다음 순서의 `Plan Rebase` 단계로 전환한다.

1. `진입/보유/청산` 로직 전수점검
2. `fallback` 오염 표본 격리
3. 관찰축 재정렬
4. 다음 튜닝포인트 1축 재선정
5. 신규 1축은 shadow/counterfactual 선행이 아니라 canary 즉시 적용 + 당일 rollback guard로 검증
6. AI 엔진 A/B 테스트는 `entry_filter` canary 1차 판정 완료 후 재개 여부를 별도 판정한다. 최대 기한은 `2026-04-24 POSTCLOSE`다

감사인에게 요청할 검토 의견도 기존 튜닝축의 승인/반려가 아니라, `로직표`, `오염 코호트`, `다음 튜닝축 우선순위`에 맞춘다.

Plan Rebase 기간의 live 스캘핑 AI 라우팅은 Gemini로 고정한다. OpenAI/Gemini A/B와 dual-persona shadow는 독립변수 오염을 막기 위해 `entry_filter` canary 1차 판정 완료 후 재개 여부를 별도 판정한다. `entry_filter` 판정이 3영업일 내 완료되지 않으면 `2026-04-24 POSTCLOSE`에 A/B 재개 여부를 별도 판정한다. 감사인 검토에 따라 다음 튜닝 1순위는 `position_addition_policy`가 아니라 `entry_filter` canary로 변경한다.

---

## 2. 개편 사유

### 2-1. 기존 분할진입 설계 실패

`fallback_scout/main`은 이름상 scout 구조였지만 실제 구현은 탐색형 분할진입이 아니었다.

정상적인 탐색형 추가진입은 아래 구조여야 한다.

```text
소량 scout 진입
-> 가격/체결강도/호가/AI 재평가
-> 충분히 유리하면 추가진입
-> 너무 달아나면 중단
-> 약화되면 scout만 축소/청산
```

실제 구현은 아래 구조였다.

```text
latency CAUTION 또는 canary override
-> fallback_scout + fallback_main 동시 제출
-> partial fill / rebase 발생
-> soft_stop 손실 노출 확대
```

따라서 `fallback_scout/main`은 개선 후보가 아니라 실패 설계로 폐기한다.

### 2-2. 응급 차단 경과

| 시각 | 조치 | 판정 |
| --- | --- | --- |
| `2026-04-21 09:27 KST` | 기존 봇 프로세스 중단 | 신규 fallback 손실 확대 차단 우선 |
| `2026-04-21 09:29 KST` | `SCALP_LATENCY_FALLBACK_ENABLED=False`, `SCALP_SPLIT_ENTRY_ENABLED=False`, `SCALP_LATENCY_GUARD_CANARY_ENABLED=False` 적용 후 재기동 | `ALLOW_FALLBACK` 경로 차단 |
| `2026-04-21 09:39~09:45 KST` | `FallbackStrategy.build()`를 deprecated null-object로 변경 | `fallback_scout/main`, `fallback_single` 생성 로직 폐기 |
| `2026-04-21 09:45 KST 이후` | fallback 주문 생성 시 빈 주문 -> `latency_fallback_deprecated` reject | 실수로 플래그가 켜져도 주문 생성 불가 |
| `2026-04-21 10:55 KST` | live 스캘핑 AI 라우팅 기본값을 Gemini로 변경 | OpenAI/Gemini A/B 및 dual-persona shadow는 `entry_filter` canary 1차 판정 후 재개 여부 별도 판정 |

관련 구현 위치:

- [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py): `SCALP_LATENCY_FALLBACK_ENABLED=False`, `SCALP_SPLIT_ENTRY_ENABLED=False`, `SCALP_LATENCY_GUARD_CANARY_ENABLED=False`
- `src/trading/entry/fallback_strategy.py` 당시 deprecated null-object였고, 현재는 코드베이스에서 제거됐다.
- [sniper_entry_latency.py](/home/ubuntu/KORStockScan/src/engine/sniper_entry_latency.py): `latency_fallback_disabled`, `latency_fallback_deprecated`
- [entry_orchestrator.py](/home/ubuntu/KORStockScan/src/trading/entry/entry_orchestrator.py): 빈 fallback 주문 reject
- [runtime_ai_router.py](/home/ubuntu/KORStockScan/src/engine/runtime_ai_router.py): live 스캘핑 AI 라우팅 기본값 Gemini
- [kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py): Gemini 라우팅 기간 OpenAI 스캘핑 엔진 초기화 생략
- [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py): `OPENAI_DUAL_PERSONA_ENABLED=False`

검증 증거:

- `PYTHONPATH=. .venv/bin/python -m py_compile src/utils/constants.py src/engine/runtime_ai_router.py src/engine/kiwoom_sniper_v2.py src/tests/test_runtime_ai_router.py` 통과
- `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_runtime_ai_router.py` 결과 `3 passed`
- `logs/runtime_ai_router_info.log`에서 `role=main scalping_route=gemini scalping_openai=off` 확인
- 런타임 상수 확인: `OPENAI_DUAL_PERSONA_ENABLED=False`, `SCALPING_AI_ROUTE=gemini`

### 2-3. 기존 관찰축 오염

기존 `partial/rebase/soft_stop` 지표에는 아래 표본이 섞여 있다.

1. 정상 `SAFE -> ALLOW_NORMAL` 진입
2. `fallback_scout/main` 동시 주문 표본
3. 1차 응급가드 오류로 생성된 `fallback_single` 표본
4. fallback 폐기 이후 normal-only 표본
5. 불타기/추가진입으로 수익이 확대된 표본

이 상태에서는 `partial_fill_completed_avg_profit_rate`, `soft_stop_count`, `position_rebased_after_fill_events`를 그대로 튜닝 결론에 사용할 수 없다. 오염 코호트 분리 후 재집계가 필요하다.

---

## 3. 감사 기준 변경

### 3-1. 기존 감사 질문

기존 감사 질문은 다음에 가까웠다.

1. `partial fill min_fill_ratio canary` 유지/롤백 여부
2. `split-entry` 승격 여부
3. `latency` 완화/차단 기준 개선 여부
4. `soft_stop` 과다 여부

### 3-2. 변경된 감사 질문

현재 감사 질문은 다음으로 바꾼다.

1. 현재 `진입/보유/청산` 로직표가 실제 운영 상태를 충분히 설명하는가?
2. `fallback_scout/main`, `fallback_single` 오염 표본 격리 기준이 감사 가능한가?
3. `normal_only`와 `post_fallback_deprecation`을 새 baseline으로 삼아도 되는가?
4. 다음 튜닝포인트는 감사인 권고에 따라 `entry_filter`를 1순위로 두고, `holding_exit`, `position_addition_policy`, `EOD/NXT`를 후순위로 둘 때 문제가 없는가?
5. `position_addition_policy`는 후순위 상태머신 설계로 두고, 먼저 불량 진입을 줄이는 `entry_filter` canary를 적용하는 순서가 타당한가?
6. `entry_filter` canary 1차 판정 완료 후, 늦어도 `2026-04-24 POSTCLOSE`에 AI 엔진 A/B 재개 여부를 별도 판정하는 것이 타당한가?

---

## 4. 전수점검 범위

### 4-1. 진입 로직

| 구분 | 현재 상태 | 감사 포인트 | 다음 조치 |
| --- | --- | --- | --- |
| 정상 진입 | `SAFE -> ALLOW_NORMAL -> tag=normal` | 새 baseline 후보로 사용 가능 | `normal_only` 코호트로 분리 |
| latency fallback | `SCALP_LATENCY_FALLBACK_ENABLED=False` | 재개 금지 상태가 코드/로그에 반영됐는지 | 폐기 유지 |
| `fallback_scout/main` | 생성 로직 폐기 | 동시 2-leg 실패 설계로 분류됐는지 | 재도입 금지 |
| `fallback_single` | 1차 응급가드 오류 표본 | normal과 섞이지 않는지 | 오염 표본 격리 |
| BUY 후 미진입 | latency/liquidity/AI threshold/overbought 분리 필요 | 기회비용 측정 가능성 | blocker 4축 재집계 |

### 4-2. 보유 로직

| 구분 | 현재 상태 | 감사 포인트 | 다음 조치 |
| --- | --- | --- | --- |
| HOLDING 판단 | AI score, peak profit, elapsed time, near-exit 사용 | 승자 보유 품질이 손실 억제와 섞이지 않는지 | `MISSED_UPSIDE`, `GOOD_EXIT`, `capture_efficiency` 재정렬 |
| 불타기 | 오늘 수익 확대 관찰 | 기대값 개선 후보로 분리 가능한지 | `scale_in_profit_expansion` 코호트 생성 |
| 물타기 | 실행 거의 없음 | 미실행 후보의 기대값 평가가 가능한지 | `avg_down_candidate` 코호트 생성 |
| 추가진입 중단 | 명시 상태머신 없음 | 달아난 종목 중단 규칙이 있는지 | `position_addition_policy`에 포함 |

### 4-3. 청산 로직

| 구분 | 현재 상태 | 감사 포인트 | 다음 조치 |
| --- | --- | --- | --- |
| soft stop | 과다 손절 지적 존재 | fallback 오염 제거 후에도 과다한지 | 오염 제거 후 재판정 |
| hard stop | 최종 안전장치 | 추가진입 상태와 충돌 여부 | 상태머신 연계 필요 |
| AI early exit | 하방 리스크 반영 | 물타기/불타기 후보와 충돌 여부 | 보유 판단표에 포함 |
| preset exit | 일부 실전 적용 | entry_mode별 성과 분리 필요 | normal/fallback 분리 |
| overnight/EOD | 판단 시간이 늦다는 운영 지적 | KRX/NXT 분리 필요 | `EOD/NXT` 후보축 유지 |

---

## 5. 코호트 재정렬 기준

| 코호트 | 정의 | 사용 여부 | 해석 |
| --- | --- | --- | --- |
| `normal_only` | `entry_mode=normal`, `tag=normal`, `SAFE -> ALLOW_NORMAL` | 새 baseline 후보 | 정상 진입 성과판정 |
| `fallback_scout_main_contaminated` | `fallback_scout` 또는 `fallback_main` 포함 | 튜닝 baseline 제외 | 실패 설계 영향 분석 전용 |
| `fallback_single_contaminated` | `fallback_single` 포함 | 튜닝 baseline 제외 | 1차 응급가드 오류 표본 |
| `post_fallback_deprecation` | `2026-04-21 09:45 KST` 이후 표본 | 새 운영 표본 | fallback 폐기 후 상태 확인 |
| `scale_in_profit_expansion` | 불타기/추가진입으로 수익 확대 | 신규 후보 | 기대값 확대축 후보 |
| `avg_down_candidate` | 물타기 후보였으나 미실행 | 신규 후보 | 손실 회복 기대값 후보 |

손익 계산은 기존 원칙대로 `COMPLETED + valid profit_rate`만 사용한다. NULL, 미완료 상태, fallback 정규화 값은 손익 기준에서 제외한다.

---

## 6. 튜닝 중단/재개 규칙

### 6-1. 중단

1. 신규 live canary는 전수점검 완료 전까지 금지한다.
2. `fallback_scout/main`, `fallback_single`은 재개 금지한다.
3. 기존 `partial/rebase/soft_stop` 통합 지표는 오염 제거 전까지 승격/롤백 판단에 사용하지 않는다.
4. 기존 `split-entry` 관련 승격 후보는 폐기 또는 신규 설계 후보로 재분류한다.

### 6-2. 재개

튜닝 재개는 아래 조건을 모두 만족한 뒤 진행한다.

1. `진입/보유/청산` 로직표 작성 완료
2. `normal_only`와 fallback 오염 코호트 분리 완료
3. `post_fallback_deprecation` 표본 기준선 확보
4. 다음 튜닝포인트 1축 선정
5. 해당 축은 canary 즉시 적용 + 당일 rollback guard로 검증한다. shadow/counterfactual 선행 원칙은 철회한다.

### 6-3. entry_filter canary 정식 rollback guard

04-22 PREOPEN canary 적용 전 아래 guard를 문서와 운영 로그에 고정한다. 모든 조건은 `normal_only` 및 `post_fallback_deprecation` 코호트를 기준으로 평가하며, 손익은 `COMPLETED + valid profit_rate`만 사용한다.

| Guard 지표 | 발동 조건 | 기준 | 발동 시 조치 |
| --- | --- | --- | --- |
| `N_min` | 판정 시점 `trade_count < 50`이고 `submitted_orders < 20` | 절대값 | hard pass/fail 금지, 방향성 판정으로 전환, 승격 금지 |
| `loss_cap` | canary cohort의 일간 합산 실현손익이 당일 스캘핑 배정 NAV 대비 `<= -0.35%` | 당일 NAV 대비 일간 합산, 종목별이 아님 | canary OFF + 전일 설정 복귀 + 원인 코호트 기록 |
| `reject_rate` | canary 적용 후 `entry_reject_rate`가 `normal_only` baseline 대비 `+15.0%p` 이상 증가 | `normal_only` baseline | canary OFF. 단, blocker 품질 개선이 동반되었는지는 사후 분석으로만 기록 |
| `latency_p95` | canary 적용 후 `gatekeeper_eval_ms_p95 > 15,900ms` | 절대값, `gatekeeper_eval_samples >= 50` | canary OFF + latency 경로 재점검 |
| `partial_fill_ratio` | baseline 대비 `+10.0%p` 이상 증가 | `normal_only` baseline | 단독 rollback은 하지 않고 경고로 기록. 동시에 `loss_cap` 또는 `soft_stop_count/completed_trades >= 35.0%`이면 canary OFF |
| `fallback_regression` | `fallback_scout/main` 또는 `fallback_single` 신규 1건 이상 발생 | 절대값 0건 | 즉시 canary OFF + fallback 차단 회귀 조사 |

부호 규칙: `reject_rate`, `partial_fill_ratio`, `latency_p95`는 **증가**가 위험 방향이다. 문서와 로그에는 음수 %p 표기를 쓰지 않는다.


---

## 7. 다음 튜닝 후보

| 후보 | 기대효과 | 리스크 | 현재 판정 |
| --- | --- | --- | --- |
| `entry_filter` | 불량 진입 감소, blocker 품질 개선, fallback 폐기 후 축소된 퍼널의 품질 회복 | missed winner 증가 가능 | 1순위 canary 후보 |
| `holding_exit` | `MISSED_UPSIDE` 감소, capture efficiency 개선 | 청산 지연 시 손실 확대 | 2순위 후보 |
| `position_addition_policy` | 불타기 수익 확대, 제한적 물타기, 추가진입 중단을 하나의 상태머신으로 정리 | 설계가 복잡하고 soft stop/HOLDING/청산과 충돌 가능 | 3순위 후순위 설계 후보 |
| `EOD/NXT` | 청산 실패 반복 감소 | NXT 가능/불가능 종목 분기 필요 | 운영 리스크 후보 |

감사인 검토 반영 후 현재 1순위는 `entry_filter`다. `position_addition_policy`는 기대값 개선 후보로 유지하지만, 단일축 canary 격리가 어렵기 때문에 `entry_filter -> holding_exit -> position_addition_policy -> EOD/NXT` 순서로 재정렬한다.

---

## 8. 감사인 검토 요청

감사인에게 아래 질문에 대한 의견을 요청한다.

1. `fallback_scout/main`을 실패 설계로 폐기하고 baseline에서 제외하는 판단이 타당한가?
2. `fallback_single`을 1차 응급가드 오류 표본으로 별도 격리하는 기준이 충분한가?
3. `normal_only`와 `post_fallback_deprecation`을 새 baseline으로 삼는 것이 타당한가?
4. `entry_filter`를 다음 튜닝 1순위 canary로 두는 것이 기대값/순이익 극대화 관점에서 타당한가?
5. §6-3의 `entry_filter` canary rollback guard가 자동 판정에 충분하며, `reject_rate +15.0%p` 및 `partial_fill_ratio` 복합 guard 구조가 타당한가?
6. `position_addition_policy`를 `entry_filter` 이후 후순위로 미루는 것이 물타기/불타기 기대값 개선을 과도하게 지연시키지 않는가?

---

## 9. 다음 액션

1. `[PlanRebase0421] 진입/보유/청산 로직표 확정`
   - Due: `2026-04-21`
   - Slot: `INTRADAY`
   - TimeWindow: `10:50~11:30`
   - Track: `ScalpingLogic`

2. `[PlanRebase0421] fallback 오염 코호트 재집계`
   - Due: `2026-04-21`
   - Slot: `INTRADAY`
   - TimeWindow: `11:30~11:50`
   - Track: `Plan`

3. `[PlanRebase0421] 다음 튜닝포인트 1축 재선정`
   - Due: `2026-04-21`
   - Slot: `POSTCLOSE`
   - TimeWindow: `15:20~15:40`
   - Track: `Plan`

4. `[PlanRebase0421] entry_filter canary 설계 + rollback guard 고정`
   - Due: `2026-04-21`
   - Slot: `POSTCLOSE`
   - TimeWindow: `15:40~16:10`
   - Track: `ScalpingLogic`

5. `[PlanRebase0422] entry_filter canary 장전 적용`
   - Due: `2026-04-22`
   - Slot: `PREOPEN`
   - TimeWindow: `08:00~08:10`
   - Track: `ScalpingLogic`

6. `[AIPrompt0424] AI 엔진 A/B 재개 여부 판정`
   - Due: `2026-04-24`
   - Slot: `POSTCLOSE`
   - TimeWindow: `16:00~16:20`
   - Track: `AIPrompt`

---


## 9-1. 감사인 검토 반영 내역

| 권고 | 반영 상태 | 문서 반영 |
| --- | --- | --- |
| R-1 shadow/counterfactual 원칙 철회 | 반영 | canary 즉시 적용 + 당일 rollback guard로 변경 |
| R-2 불필요 관찰축 제거 | 반영 | split-entry 재평가/leakage, 에이럭스 별도 4분해, legacy shadow 2건, 범위확정 실패 분리항목 제거/흡수 |
| R-3 일정 압축 | 반영 | 04-21 15:20~16:10에 1축 선정과 guard 설계 완료, 04-22 08:00~08:10 적용 판단 |
| R-4 entry_filter 1순위 | 반영 | `entry_filter -> holding_exit -> position_addition_policy -> EOD/NXT` 순서로 재정렬 |
| R-5 GPT 금지패턴 | 후속 반영 | 04-22 `[Governance0422]` 항목으로 등록 |
| R-6 remote_error 표기 | 반영 | 체크리스트 자동 비교 결론을 `비교 불가 - 원격 정합성 미확인`으로 수정 |
| R-7 AI 생성 코드 체크게이트 | 후속 반영 | 04-22 `[Governance0422]` 항목으로 등록 |
| R-8 방향성 판정 유효기간 | 반영 | 방향성 판정은 2영업일 이내 재판정, 미재판정 시 자동 보류 |
| A A/B 연기 종료조건 | 반영 | `entry_filter` canary 1차 판정 완료 또는 `2026-04-24 POSTCLOSE`에 재개 여부 별도 판정 |
| B rollback guard 정식 정의 | 반영 | §6-3에 발동 조건/기준/방향/조치 표로 승격 |
| C Q5 질문 순서 | 반영 | §6-3 guard 정의 후 §8 Q5를 재질의 형태로 유지 |
| 확인1 Gemini 라우팅 검증 증거 | 반영 | py_compile, runtime router pytest, 라우터 로그, 런타임 상수 확인 증거 추가 |
| 확인2 A/B 질문 구체화 | 반영 | §3-2 Q6을 `2026-04-24 POSTCLOSE` 재개 판정 질문으로 변경 |

문의/확인: `entry_filter` rollback guard는 §6-3을 정식 기준으로 삼는다. `reject_rate`는 감사인 보완 의견을 반영해 baseline 대비 `+15.0%p` 증가로 완화했고, `partial_fill_ratio`는 entry_filter와 직접 연관성이 낮아 단독 rollback이 아닌 복합 guard로 격하했다.

## 10. 결론

기존 튜닝 plan은 유지할 수 없다. 다만 코드 전체를 제로베이스로 버릴 단계는 아니다.

정확한 결론은 다음과 같다.

```text
코드 전체 제로베이스: 아님
튜닝 기준선 제로베이스: 맞음
fallback 분할진입: 폐기
기존 partial/rebase/soft_stop 결론: 오염 제거 전까지 보류
다음 설계축: entry_filter canary 우선, position_addition_policy는 후순위 상태머신 후보
감사 검토 초점: 로직표 + 오염 코호트 + 다음 튜닝축
```

이번 개편의 목적은 손실 억제형 임시 튜닝을 계속하는 것이 아니라, 기대값/순이익 극대화를 위해 `진입 -> 보유 -> 추가진입/중단 -> 청산` 전체 상태전이를 다시 정렬하는 것이다.
