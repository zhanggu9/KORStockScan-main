# Closed Observation Axes Archive (`2026-05-01 KST`)

Source: [Plan Rebase](../plan-korStockScanPerformanceOptimization.rebase.md), [2026-04-29 checklist](../2026-04-29-stage2-todo-checklist.md), [2026-04-30 checklist](../2026-04-30-stage2-todo-checklist.md), [workorder-shadow-canary-runtime-classification](../workorder-shadow-canary-runtime-classification.md)

이 문서는 중심 rebase에서 내려온 종료/폐기/역사참조 축을 보관한다. 현재 live owner, 다음 canary, Project/Calendar 작업항목은 날짜별 checklist가 소유한다.

## 1. 판정

1. 아래 축은 현재 active/open 후보가 아니다.
2. 재개하려면 기존 축을 그대로 켜지 않고 새 workorder, 단일 조작점, rollback guard, cohort, checklist Due/Slot/TimeWindow를 다시 만든다.
3. historical/reference 수치는 직접 손익 결론에 합산하지 않고, 신규 축의 baseline 오염 여부나 회귀 탐지에만 쓴다.

## 2. Archived Entry / Latency Axes

| 축 | 종료 시점/근거 | archive 판정 | 재개 조건 |
| --- | --- | --- | --- |
| `buy_recovery_canary` | `2026-04-23` 이후 `entry_armed -> submitted` downstream 병목이 주병목으로 확정되며 live owner에서 내려감 | guarded-off historical entry axis | WAIT65~79가 다시 주병목이고 현 entry owner와 충돌하지 않을 때 새 checklist로 재승인 |
| `entry_filter_quality` parking 판정 | `2026-04-23~2026-04-24` submitted 병목 해소 전까지 착수 금지로 닫힘 | parking/reference | submitted 회복 후 불량 진입/체결품질 악화가 주병목일 때 |
| `fallback_scout/main` | `2026-04-21 09:45 KST` fallback 폐기 이후 신규 사용 금지 | 영구 폐기. live/observe/replacement 후보 아님 | 새 fallback 계열 workorder, 기대값 근거, rollback guard 없이는 재개 금지 |
| `fallback_single` | `fallback_scout/main`과 같은 fallback 폐기 묶음 | 영구 폐기. normal_only 기준선과 분리 | 위와 동일 |
| `latency fallback split-entry` | latency 상태에서 fallback 허용으로 분할진입하던 경로 | 영구 폐기. latency bugfix/entry canary와 분리 | 기존 split-entry 복구 금지. 신규 경로로만 재정의 |
| `gatekeeper_fast_reuse signature/window` | `2026-04-27~2026-04-30` 제출 회복 근거 부족, 보조 진단축으로 격하 | closed auxiliary diagnostic | submitted/full/partial 회복과 연결되는 새 증거가 생길 때만 진단 항목으로 재개 |
| `other_danger` 단일 relief | `2026-04-27` residual pivot 후 제출 회복 실패 | historical-only | danger reason별 단일축으로 새로 분해하고 현 entry owner와 충돌하지 않을 때 |
| `ws_jitter` 단일 relief | quote freshness family와 독립 개선 근거 부족 | historical-only | `ws_jitter`가 terminal miss 주원인으로 재확인될 때 |
| `spread` 단일 relief | 단독 완화가 broad relax로 번질 위험이 큼 | historical/reference | spread-only blocker가 주병목이고 rollback guard가 닫힐 때 |
| `latency_quote_fresh_composite` | `2026-04-29 08:29 KST` OFF + restart 완료 | standby/reference. active canary 아님 | 현 entry owner OFF, 새 bundle 목표/rollback/baseline 확정 필요 |
| `latency_signal_quality_quote_composite` | `2026-04-29 12:50 KST` post-restart `budget_pass=972`, `submitted=0`, 후보 통과 0건 | closed ineffective replacement | signal-quality 후보가 실제 pass sample을 만들고 새 checklist 승인 필요 |

## 3. Archived Holding / Exit Axes

| 축 | 종료 시점/근거 | archive 판정 | 재개 조건 |
| --- | --- | --- | --- |
| `soft_stop_expert_defense v2` | `2026-04-30 12:00~15:30 KST` same-day 수집 후 기본 OFF | closed collection axis. v2 그대로 재가동 금지 | `absorption`, `thesis veto`, `arbitration` 중 하나를 단일 조작점으로 재정의 |
| `soft_stop_micro_grace_extend` | blanket extend는 buy 기준 회복 부족으로 보류 | standby/off. archive에는 종료된 blanket-extend 논리만 보관 | 20초 micro grace 비악화 + rebound capture 부족이 rolling 표본으로 확인될 때 |
| `scalp_ai_early_exit`/하방카운트 historical 축 | `2026-04-27` 기준 historical-only로 정리 | active holding owner 아님 | 현 보유/청산 owner와 별도인 새 exit-rule workorder 필요 |
| `hard_stop_whipsaw_aux` | severe-loss guard라 완화 우선순위 낮음 | parking/reference | hard stop missed upside가 독립 주병목으로 확인될 때 |
| `trailing_continuation_micro_canary` 4/30 승격 검토 | `2026-04-30` trailing 표본 `MISSED_UPSIDE=5/19`로 active 승격 보류 | 2순위 candidate 유지. archive에는 4/30 승격 보류 판단만 보관 | rolling `MISSED_UPSIDE + same_symbol_reentry` 강화 시 새 checklist에서 재검토 |

## 4. Archived AI / Contract Observation Items

| 축 | 종료 시점/근거 | archive 판정 | 재개 조건 |
| --- | --- | --- | --- |
| Gemini schema ingress 4/30 관찰 | `GEMINI_RESPONSE_SCHEMA_REGISTRY_ENABLED=False`, 6 endpoint schema_name 연결 및 tests 확인 | flag-off load 관찰 종료. live enable 아님 | Gemini live enable이 필요하면 별도 flag-off -> canary checklist로 재등록 |
| DeepSeek interface gap 4/30 점검 | 공통 caller gap 증상 없음 | closed low-priority interface check | 신규 공통 caller가 생길 때만 adapter 항목 재등록 |
| DeepSeek retry acceptance 4/30 관찰 | `DEEPSEEK_CONTEXT_AWARE_BACKOFF_ENABLED=False`, retry 실표본 부족 | flag-off observability 유지. 해당 일자 항목은 종료 | 다음 retry 실표본에서 `retry_acceptance` 필드만 확인 |
| `shared` prompt 혼입 의심 | 신규 행동 canary 근거 없음 | code-cleanup/reference | shared가 실주문/보유/청산 의사결정에 다시 연결될 때만 재조사 |

## 5. 중심 문서 복귀 금지 기준

1. 위 항목은 현재 rebase §8 `Open 상태 요약`에 상세 서술로 복귀하지 않는다.
2. active/open 상태로 되돌리려면 날짜별 checklist에 자동 파싱 가능한 `- [ ]` 항목이 먼저 있어야 한다.
3. `Done` 처리는 source checklist 기준으로 유지하고, Project/Calendar 동기화는 checklist parser 결과를 따른다.
