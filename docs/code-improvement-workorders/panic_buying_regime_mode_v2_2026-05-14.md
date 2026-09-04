# Panic Buying Regime Mode V2 Workorder - 2026-05-14

## 목적

- `panic_buying` V2 1차 runtime 전환 후보를 `panic_buy_runner_tp_canary`로 고정한다.
- 목표는 패닉바잉 구간에서 고정 TP 전량청산으로 놓치는 upside와 runner giveback을 분리 attribution해 기대값/순이익을 개선하는 것이다.
- 신규 추격매수, 추가매수, hard/protect/emergency stop, provider route, bot restart는 변경하지 않는다.

## 판정

- 후보 상태: `approval_required_candidate`
- 적용 단계: `holding_exit_tp_candidate`
- runtime family: `panic_buy_runner_tp_canary`
- 기본 live 상태: `OFF`
- `allowed_runtime_apply`: `false` until approval artifact and implementation tests exist
- 우선 적용 대상: scalping 기존 보유 포지션의 fixed TP 후보
- 신규 진입 적용: V2.1 이후 별도 `panic_buy_chase_entry_freeze`로 분리 검토한다.

## Panic Buying Mode Policy

`panic_buying`은 신규 매수 alpha signal이 아니라 risk-regime source다. mode 해석은 아래처럼 둔다.

| mode | 입력 | 허용 행동 | 금지선 |
| --- | --- | --- | --- |
| `NORMAL` | `panic_buy_state=NORMAL` | 기존 selected family와 고정 TP 정책 유지 | 없음 |
| `PANIC_BUY_DETECTED` | `PANIC_BUY_WATCH`, 초기 panic-buy signal | 신규 추격매수 금지 후보, 일부 익절 + runner 전환 후보를 report-only로 기록 | approval 없는 TP/trailing 변경, 자동매수 |
| `PANIC_BUY_CONTINUATION` | `PANIC_BUY`, runner 허용 signal, OFI 양수 지속, 고점 갱신 지속 | 잔량 보유, trailing stop 상향, 눌림/재돌파 진입 조건 후보를 attribution에 기록 | 추격매수, 추가매수, hard/protect/emergency override |
| `PANIC_BUY_EXHAUSTION` | `EXHAUSTION_WATCH`, `BUYING_EXHAUSTED`, force runner exit signal | 잔량 cleanup/tight trailing 후보, 신규 진입 금지 후보 | 시장가 전량청산, approval 없는 자동청산 |
| `COOLDOWN` | detector internal `COOLDOWN` | 급등 종료 후 재진입 금지 후보, 과대 되돌림 관찰 | entry gate 즉시 변경 |

V2 roadmap은 owner를 분리한다. V2.0은 이 문서의 `panic_buy_runner_tp_canary`로 기존 보유분 TP/runner만 다룬다. V2.1 `panic_buy_chase_entry_freeze`, V2.2 `panic_buy_continuation_trailing_width`, V2.3 `panic_buy_exhaustion_runner_cleanup`, V2.4 `panic_buy_cooldown_reentry_guard`는 별도 workorder와 approval artifact가 필요하며 V2.0 승인으로 자동 적용하지 않는다.

## Approval Artifact

승인 artifact 후보 경로:

```text
data/threshold_cycle/approvals/panic_buy_runner_tp_canary_YYYY-MM-DD.json
```

필수 필드:

```json
{
  "policy_id": "panic_buy_runner_tp_canary",
  "source_date": "YYYY-MM-DD",
  "approved": true,
  "approved_by": "user",
  "approved_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "approval_scope": "scalping_existing_position_tp_runner_only",
  "partial_take_profit_ratio": 0.5,
  "max_runner_ratio": 0.5,
  "max_slippage_bps": 30,
  "trailing_width_policy": "volatility_adjusted",
  "allow_entry_effect": false,
  "allow_add_buy_effect": false,
  "allow_hard_protect_emergency_override": false,
  "rollback_guard_ack": true
}
```

승인 artifact가 없으면 preopen apply는 env override를 만들 수 없다.

## Runtime Env Keys

초기 env key 후보:

```bash
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_ENABLED=false
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_REQUIRE_APPROVAL_ARTIFACT=true
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_PARTIAL_TP_RATIO=0.5
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_MAX_RUNNER_RATIO=0.5
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_MAX_SLIPPAGE_BPS=30
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_TRAILING_WIDTH_MODE=volatility_adjusted
KORSTOCKSCAN_PANIC_BUY_RUNNER_TP_CANARY_COHORT_TAG=panic_buy_runner_tp_canary_v2
```

초기 구현에서는 env parser와 apply manifest만 정의하고, 실제 TP/runner path 연결은 별도 구현 PR/workorder에서 연결한다.

## Trigger Candidate

`panic_buying_YYYY-MM-DD.json` 기준:

- `panic_buy_regime_mode in {PANIC_BUY_DETECTED, PANIC_BUY_CONTINUATION}`
- `panic_buy_metrics.panic_buy_active_count > 0`
- `tp_counterfactual_summary.candidate_context_count > 0`
- `panic_buy_metrics.avg_confidence >= 0.55`
- real/sim/probe split과 TP counterfactual provenance가 통과

`PANIC_BUY_EXHAUSTION`과 `COOLDOWN`은 V2.0에서 runner 신규 생성 trigger가 아니라 V2.3/V2.4 설계 후보로만 남긴다.

## Runtime Behavior

- fixed TP 전량청산 후보에서 승인된 비율만 일부 익절 후보로 남기고 잔량은 runner trailing 후보로 분리한다.
- 익절 주문 후보는 시장가 전량 매도가 아니라 분할 지정가 또는 시장성 지정가와 slippage cap을 우선한다.
- 잔량 trailing은 VI/급등 구간에서 변동성 기반 폭 확대 후보를 쓰고, OFI 둔화/체결강도 하락/고점 갱신 실패는 V2.3 cleanup 후보로 분리한다.
- hard/protect/emergency stop은 항상 우선하며 canary가 지연하거나 덮어쓰지 않는다.
- 신규 매수, 추가매수, score threshold, AI provider route, quantity cap은 변경하지 않는다.

## Rollback Guard

즉시 OFF 후보:

- approval artifact 밖에서 TP/runner canary가 1회라도 켜짐
- hard/protect/emergency stop 또는 sell safety path에 영향 발생
- 시장가 전량 매도 주문이 canary 경로로 제출됨
- slippage cap 초과, receipt/order number/provenance 누락
- runner giveback이 avoided missed upside보다 커지는 상태가 rolling window에서 반복
- panic buying source freshness가 2분 이상 stale인데 canary trigger 발생
- same-stage owner conflict: `soft_stop_whipsaw_confirmation`, `protect_trailing_smoothing`, `trailing_continuation`, `holding_flow_override` 중 최종 exit owner가 불명확함
- provenance 필드 누락: `panic_buy_regime_mode`, `panic_buy_state`, `source_report`, `cohort_tag`, `actual_order_submitted`

장후 OFF/hold 판정:

- TP counterfactual 표본이 없으면 hold_sample
- false-positive panic-buy day로 판정되면 hold/freeze
- runner giveback과 sell-failure risk가 missed upside 개선보다 크면 partial ratio 또는 trailing width 축소

## Implementation Scope

1. threshold-cycle metadata에 `panic_buy_runner_tp_canary`를 `human_approval_required=true`, `allowed_runtime_apply=false`로 추가한다.
2. `threshold_cycle_preopen_apply`에 approval artifact loader와 env key mapping을 추가하되, artifact 없이는 env를 쓰지 않는다.
3. holding/exit TP 후보 경로에 feature flag OFF 기본의 partial TP + runner hook을 추가한다.
4. `panic_buy_runner_tp_canary` provenance와 daily EV attribution을 추가한다.
5. `runtime_approval_summary`에 approval request/blocked state를 표시한다.

## Acceptance Tests

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  src/tests/test_panic_buying_report.py \
  src/tests/test_daily_threshold_cycle_report.py \
  src/tests/test_threshold_cycle_preopen_apply.py \
  src/tests/test_runtime_approval_summary.py
```

추가 테스트 기준:

- approval artifact 없이는 env override가 생성되지 않는다.
- env가 OFF이면 TP/runner decision이 바뀌지 않는다.
- panic-buy trigger + approval artifact가 있어도 신규 진입/추가매수에는 영향이 없다.
- stale panic-buy report에서는 canary trigger가 발생하지 않는다.
- canary event는 `panic_buy_regime_mode`, `cohort_tag`, `actual_order_submitted` provenance를 남긴다.

## 금지선

- 신규 추격매수 금지
- 추가매수 금지
- hard/protect/emergency stop override 금지
- 시장가 전량청산 금지
- score threshold 완화 금지
- provider route 변경 금지
- bot restart 금지
