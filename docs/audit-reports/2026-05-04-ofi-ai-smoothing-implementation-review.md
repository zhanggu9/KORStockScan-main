# OFI 기반 AI 판단 Smoothing 구현 코드리뷰 결과보고서

작성일: `2026-05-04 KST`
대상 계획: [scalping_ai_smoothing_01.md](./scalping_ai_smoothing_01.md), [2026-05-04-ofi-ai-judgment-smoothing-plan.md](./2026-05-04-ofi-ai-judgment-smoothing-plan.md)
대상 구현: [ofi_ai_smoothing.py](/home/ubuntu/KORStockScan/src/engine/ofi_ai_smoothing.py), [sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py), [daily_threshold_cycle_report.py](/home/ubuntu/KORStockScan/src/engine/daily_threshold_cycle_report.py), [threshold_cycle_registry.py](/home/ubuntu/KORStockScan/src/utils/threshold_cycle_registry.py), [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py)

## 1. 판정

코드리뷰 판정은 `조건부 적정`이다. 구현은 OFI를 독립 BUY/EXIT 판단자로 쓰지 않고, 이미 승인된 `dynamic_entry_ai_price_canary_p2`와 `holding_flow_override` 내부의 deterministic 완충 postprocessor로만 사용한다. `shadow` 경로는 새로 열지 않았고, threshold-cycle 산출물도 `ThresholdOpsTransition0506` 전에는 `manifest_only` 후보만 생성하도록 제한했다.

실전 위험 경계도 계획과 대체로 일치한다. Entry는 저신뢰 raw `SKIP` 일부만 P1 방어 제출 경로로 되돌리고, Holding은 hard stop/protect hard stop/주문·잔고 safety/max defer/worsen floor보다 뒤에서만 OFI smoothing을 적용한다.

## 2. OFI 사용 지점과 방식

OFI 원천은 기존 orderbook micro snapshot이다. 런타임은 `ofi_z`, `qi_ewma`, `micro_state`, `observer_healthy`, `ready`, `snapshot_age_ms` 또는 `captured_at_ms`를 읽고, [ofi_ai_smoothing.py](/home/ubuntu/KORStockScan/src/engine/ofi_ai_smoothing.py)에서 공통 score와 regime으로 변환한다.

공통 계산식은 아래와 같다.

```text
micro_score_raw = 0.65 * tanh(ofi_z / 2.0) + 0.35 * clip((qi_ewma - 0.50) / 0.10)
micro_score_smooth = prev * 0.70 + raw * 0.30
stable_bullish >= +0.45, stable_bearish <= -0.45, release = +/-0.15, persistence = 2
```

`observer_healthy != True`, `ready=False`, score input 누락, `snapshot_age_ms > 700`은 usable smoothing으로 보지 않는다. 이 상태들은 `neutral`이나 `bearish`로 오인하지 않고 각각 `observer_unhealthy`, `insufficient`, `stale`로 fail-closed된다.

Entry 적용 지점은 [sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py)의 `dynamic_entry_ai_price_canary_p2` 내부다. Tier2 AI가 raw `SKIP`을 반환했고 confidence가 `80~89`이며, OFI가 usable이고 source `micro_state in {neutral,bullish}`이면 `entry_ai_price_ofi_skip_demoted` stage를 남긴 뒤 P1 `USE_DEFENSIVE` 경로로 demotion한다. confidence `>=90`, `stable_bearish`, stale/unhealthy/insufficient는 기존 `SKIP`을 유지한다. 이 경로는 이미 산출된 P1 planned order를 재사용하므로 pre-submit price guard를 우회하지 않는다.

Holding/Exit 적용 지점은 같은 파일의 `holding_flow_override` 내부다. flow AI가 `EXIT`을 냈는데 OFI가 `stable_bullish`면 기존 max defer/worsen guard 범위 안에서 `DEBOUNCE_EXIT`으로 청산을 보류한다. 반대로 flow action이 `HOLD` 또는 `TRIM`이고 OFI가 `stable_bearish`이며 최초 후보 이후 손익 추가악화가 `>=0.30%p`면 `CONFIRM_EXIT`으로 기존 청산을 확정한다. hard stop, protect hard stop, 주문·잔고 safety, `max_defer_sec`, 기존 `worsen_floor=0.80%p`는 항상 OFI보다 우선한다.

Threshold-cycle 적용 지점은 [threshold_cycle_registry.py](/home/ubuntu/KORStockScan/src/utils/threshold_cycle_registry.py)와 [daily_threshold_cycle_report.py](/home/ubuntu/KORStockScan/src/engine/daily_threshold_cycle_report.py)다. `entry_ai_price_ofi_skip_demoted`는 `entry_ofi_ai_smoothing`, `holding_flow_ofi_smoothing_applied`와 `holding_flow_override_force_exit`은 `holding_flow_ofi_smoothing` family로 수집된다. 추천 후보는 sample floor와 방향성 조건을 만족해도 `manifest_only`로만 생성되며 runtime env/code 자동 변경은 열지 않는다.

## 3. 구현 확인 포인트

Entry override는 raw `SKIP` 전체를 완화하지 않는다. confidence 상한 `90`을 기준으로 강한 SKIP은 유지하고, OFI가 bearish 또는 invalid인 경우도 유지한다. 따라서 AI 가격축의 실패/위험 신호를 OFI가 단독으로 뒤집는 구조가 아니다.

Holding override는 flow 결과 후처리이며 기존 force-exit 조건보다 앞서지 않는다. 특히 AI/parse/stale/context 실패, max defer 초과, 추가악화 `0.80%p`, 주문·잔고 safety가 있으면 OFI bullish여도 청산 허용 경로가 우선한다.

Smoother 상태는 stock state에 저장되는 이전 regime/count를 사용한다. invalid snapshot이 들어오면 이전 smooth state를 계속 누적하지 않고 unusable state로 전환해 stale feed가 persistence를 만드는 위험을 줄였다.

Threshold-cycle family는 새 stage를 compact/report 대상으로 편입하지만 apply candidate의 `owner_rule`을 `manifest_only_no_runtime_mutation`으로 고정한다. 이는 `ThresholdOpsTransition0506` 전 runtime threshold 자동 변경 금지 원칙과 일치한다.

## 4. 잔여 리스크

첫째, OFI smoothing은 orderbook observer snapshot 품질에 의존한다. 실시간 quote/trade feed가 부분적으로 비거나 지연되면 smoothing은 적용되지 않고 기존 판단으로 fail-closed된다. 이는 안전하지만 표본 수가 부족할 수 있다.

둘째, Entry demotion은 source `micro_state`의 coarse label과 smoother regime을 함께 본다. `micro_state` 산출 기준 자체가 바뀌면 demotion 표본 분포도 바뀌므로 threshold-cycle report에서 `snapshot_age_ms`, `micro_state`, `ofi_smoothing_regime` 분포를 같이 확인해야 한다.

셋째, Holding bearish confirm은 최초 후보 이후 추가악화 `0.30%p`를 사용한다. 이 값은 runtime 자동 변경 대상이 아니며, daily/rolling 방향 일치와 sample floor가 쌓이기 전까지는 현행값을 운영 기본값으로 단정하지 않는다.

넷째, 성과 판정은 아직 구현 검증 단계다. live 효과 판정은 `COMPLETED + valid profit_rate`, full/partial 분리, blocker/체결품질, `GOOD_EXIT/MISSED_UPSIDE`를 포함한 5/6 이후 보고서에서 닫아야 한다.

## 5. Wide-Window 후속 적용

현재 `orderbook_micro`의 `ofi_z`는 기본 `60초` micro sample window에서 계산된다. 단, `ofi_ewma`, `qi_ewma`, `depth_ewma`는 EWMA 상태라 60초 바깥의 흐름도 감쇠된 형태로 일부 남는다. 따라서 현재 smoother는 급변동 완충에는 충분히 민감하지만, 스윙 전환을 단독 판단하기에는 짧다.

후속 적용은 live 판단 변경이 아니라 report-only wide-window feature로 시작한다. [orderbook_stability_observer.py](/home/ubuntu/KORStockScan/src/trading/entry/orderbook_stability_observer.py)는 `3분/5분/10분` wide OFI sample을 별도 보관하고, 각 window별 `persistent_bullish`, `persistent_bearish`, `mixed`, `neutral`, `insufficient` 상태와 bullish/bearish ratio, 평균 `ofi_z`, 평균 `qi_ewma`를 산출한다.

이 wide-window 값은 스윙 전환의 단독 gate가 아니다. `winner_wide_window_candidate`, trailing 유지 후보, 스윙 보유 승격 보류/검토 같은 report-only feature의 미시구조 보조 증거로만 사용한다. live 청산 변경은 `SwingTrailingPolicy0506`에서 단일 조작점, cohort tag, rollback guard, sample floor를 별도로 잠근 뒤에만 검토한다.

## 6. Prompt-Level Consistency

`scalping_ai_smoothing_01.md`의 prompt-level smoothing 제안은 `holding_flow_override`에 제한 적용했다. 기존 flow prompt는 최근 판단 history를 이미 주입했지만, 직전 판단을 뒤집을 때 필요한 근거 기준은 명시하지 않았다. 이번 보강은 최근 flow review의 직전 action을 뒤집으려면 가격/수급/호가/분봉/손익 중 최소 2개 이상에서 새롭고 명확한 변화 근거가 필요하다는 제약을 추가한다.

이 규칙은 hard stop, protect hard stop, 주문/잔고 safety, 후보 이후 추가악화, stale/parse/context 실패보다 우선하지 않는다. 즉 prompt inertia는 조급한 AI 판단 급변을 줄이는 비용으로만 쓰고, 시스템 guard나 기존 runtime fail-closed 경로를 막지 않는다. Entry price P2에는 같은 규칙을 직접 넣지 않는다. 제출 직전 가격결정은 단발성이 강하고, 불리한 호가 변화에는 빠르게 `SKIP` 또는 방어 가격을 선택해야 하므로 holding flow보다 약한 consistency가 적절하다.

## 7. 검증 결과

구현 검증은 아래 targeted test로 통과했다.

```text
PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_ofi_ai_smoothing.py src/tests/test_holding_flow_override.py src/tests/test_daily_threshold_cycle_report.py
결과: 25 passed

PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_sniper_scale_in.py -k "entry_ai_price"
결과: 8 passed, 118 deselected

PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_constants.py src/tests/test_backfill_threshold_cycle_events.py src/tests/test_pipeline_event_logger.py
결과: 16 passed

PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_orderbook_stability_observer.py
결과: 11 passed

PYTHONPATH=. .venv/bin/python -m pytest -q src/tests/test_ai_engine_cache.py -k "holding_flow"
결과: 1 passed, 22 deselected
```

문서/체크리스트 parser 검증 대상 명령은 다음과 같다.

```text
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
```

## 8. 코드리뷰 요청 포커스

리뷰에서는 다음 네 가지를 우선 확인하면 된다.

- `entry_ai_price_ofi_skip_demoted`가 pre-submit price guard나 AI confidence `>=90` SKIP을 우회하지 않는지.
- `holding_flow_ofi_smoothing_applied`가 hard/protect/order safety, `max_defer_sec`, `worsen_floor`보다 앞서 실행되지 않는지.
- stale/unhealthy/insufficient OFI snapshot이 `neutral` 또는 `bearish`처럼 사용되지 않는지.
- threshold-cycle apply candidate가 `manifest_only` 밖으로 runtime mutation을 열지 않는지.
