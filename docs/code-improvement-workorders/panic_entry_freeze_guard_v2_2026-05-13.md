# Panic Entry Freeze Guard V2 Workorder - 2026-05-13

## 목적

- `panic_sell_defense` V2 1차 runtime 전환 후보를 `panic_entry_freeze_guard`로 고정한다.
- 목표는 패닉셀 구간에서 신규 위험 증가를 제한하고, avoided loss와 missed upside를 분리 attribution해 기대값/순이익을 개선하는 것이다.
- 기존 보유 청산, hard/protect/emergency stop, stop-loss threshold, 자동매도, bot restart는 변경하지 않는다.

## 판정

- 후보 상태: `approval_required_candidate`
- 적용 단계: `entry_pre_submit`
- runtime family: `panic_entry_freeze_guard`
- 기본 live 상태: `OFF`
- `allowed_runtime_apply`: `false` until approval artifact and implementation tests exist
- 우선 적용 대상: scalping 신규 BUY 및 recovery/probe 신규 진입 후보
- 스윙 적용: V2.1 이후 별도 `swing_panic_entry_freeze_guard`로 분리 검토한다. 현재 스윙은 `panic_context`를 source/approval 입력으로만 읽고, 단독 gate 완화/차단/실주문 전환 권한은 없다.

## Panic Lifecycle Mode Policy

`panic_sell_defense`는 매매 로직을 즉시 대체하는 alpha signal이 아니라 risk-regime source다. mode 해석은 아래처럼 둔다.

| mode | 입력 | 허용 행동 | 금지선 |
| --- | --- | --- | --- |
| `NORMAL` | `panic_state=NORMAL` | 기존 selected family 유지 | 없음 |
| `PANIC_DETECTED` | `PANIC_SELL`, confirmed risk-off, stop-loss cluster | 신규 BUY pre-submit freeze 후보, 미체결 진입 주문 cancel 후보, scale-in 금지 후보 | 자동 전량 청산, stop-loss 완화, threshold 완화 |
| `STABILIZING` | `RECOVERY_WATCH`, OFI/스프레드/저점 재이탈 실패 관찰 | sim/probe 기반 회복 관찰과 missed upside attribution | 정상 수량 즉시 복구, approval 없는 실주문 탐색 |
| `RECOVERY_CONFIRMED` | `RECOVERY_CONFIRMED`, 2~3회 회복 evidence | 일부 복구 후보를 장후 attribution에 기록 | 다음 장전 bounded guard 전 broker order 제출 |

V2 roadmap은 owner를 분리한다. V2.0은 이 문서의 `panic_entry_freeze_guard`로 scalping 신규 BUY pre-submit 차단만 다룬다. V2.1 미체결 진입 주문 cancel guard, V2.2 holding/exit `panic_context`, V2.3 강제 축소/청산 guard는 별도 workorder와 approval artifact가 필요하며 V2.0 승인으로 자동 적용하지 않는다.

## Approval Artifact

승인 artifact 후보 경로:

```text
data/threshold_cycle/approvals/panic_entry_freeze_guard_YYYY-MM-DD.json
```

필수 필드:

```json
{
  "policy_id": "panic_entry_freeze_guard",
  "source_date": "YYYY-MM-DD",
  "approved": true,
  "approved_by": "user",
  "approved_at": "YYYY-MM-DDTHH:MM:SS+09:00",
  "approval_scope": "scalping_entry_pre_submit_only",
  "max_freeze_sec": 180,
  "max_daily_freeze_triggers": 5,
  "allow_swing_effect": false,
  "allow_exit_effect": false,
  "rollback_guard_ack": true
}
```

승인 artifact가 없으면 preopen apply는 env override를 만들 수 없다.

## Runtime Env Keys

초기 env key 후보:

```bash
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_ENABLED=false
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_REQUIRE_APPROVAL_ARTIFACT=true
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_MAX_FREEZE_SEC=180
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_MAX_DAILY_TRIGGERS=5
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_MIN_PANIC_SCORE=0.70
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_MIN_STOP_LOSS_CLUSTER=2
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_ALLOW_RECOVERY_STATE=false
KORSTOCKSCAN_PANIC_ENTRY_FREEZE_GUARD_COHORT_TAG=panic_entry_freeze_guard_v2
```

초기 구현에서는 env parser와 apply manifest만 정의하고, 실제 entry block 코드는 별도 구현 PR/workorder에서 연결한다.

## Trigger Candidate

`panic_sell_defense_YYYY-MM-DD.json` 기준:

- `panic_state == PANIC_SELL`
- 또는 `microstructure_detector.risk_off_advisory_count > 0`
- 또는 `panic_metrics.stop_loss_exit_count >= 2`
- 그리고 `microstructure_max_panic_score >= 0.70` 또는 stop-loss cluster가 rolling 30분 내 확인됨

`RECOVERY_CONFIRMED`에서는 기본적으로 freeze를 해제한다. `RECOVERY_WATCH`는 V2 초기값에서 freeze 유지가 아니라 신규 trigger 금지로 둔다.

## Runtime Behavior

- 신규 BUY 후보가 pre-submit 직전에 guard를 통과해야 한다.
- guard 발동 시 주문을 만들지 않고 `entry_submit_revalidation_block` 또는 별도 stage `panic_entry_freeze_block`으로 provenance를 남긴다.
- `actual_order_submitted=false`, `blocker=panic_entry_freeze_guard`, `panic_state`, `panic_score`, `source_report`, `cohort_tag`를 필수 기록한다.
- score threshold, AI provider route, spread cap, quantity cap은 변경하지 않는다.
- 기존 보유 포지션의 청산/stop/trailing 판단에는 개입하지 않는다.

## Rollback Guard

즉시 OFF 후보:

- approval artifact 밖에서 guard가 1회라도 켜짐
- hard/protect/emergency stop, sell path, trailing path에 영향 발생
- `actual_order_submitted=true` 주문에 freeze stage가 잘못 붙음
- daily freeze trigger count가 `max_daily_freeze_triggers` 초과
- freeze cohort의 10분 missed winner rate가 avoided loser rate보다 `+20%p` 이상 높음
- panic source freshness가 5분 이상 stale인데 block 발생
- same-stage owner conflict: `score65_74_recovery_probe`, `pre_submit_price_guard`, `buy_pause_guard` 중 동일 후보 최종 owner가 불명확함
- provenance 필드 누락: `panic_state`, `panic_score`, `source_report`, `actual_order_submitted`

장후 OFF/hold 판정:

- `panic_state`가 없거나 false-positive panic day로 판정되면 hold/freeze
- freeze block 표본이 없으면 hold_sample
- 신규 진입 손실 회피보다 missed upside가 커지면 max_freeze_sec 또는 trigger 조건 축소

## Implementation Scope

1. threshold-cycle metadata에 `panic_entry_freeze_guard`를 `human_approval_required=true`, `allowed_runtime_apply=false`로 추가한다.
2. `threshold_cycle_preopen_apply`에 approval artifact loader와 env key mapping을 추가하되, artifact 없이는 env를 쓰지 않는다.
3. entry pre-submit 경로에 feature flag OFF 기본의 guard hook을 추가한다.
4. `panic_entry_freeze_block` provenance와 daily EV attribution을 추가한다.
5. `runtime_approval_summary`에 approval request/blocked state를 표시한다.

## Acceptance Tests

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  src/tests/test_daily_threshold_cycle_report.py \
  src/tests/test_threshold_cycle_preopen_apply.py \
  src/tests/test_runtime_approval_summary.py
```

추가 테스트 기준:

- approval artifact 없이는 env override가 생성되지 않는다.
- env가 OFF이면 entry decision이 바뀌지 않는다.
- panic trigger + approval artifact가 있어도 exit path에는 영향이 없다.
- stale panic report에서는 신규 block이 발생하지 않는다.
- block event는 `actual_order_submitted=false` provenance를 남긴다.

## 금지선

- stop-loss 완화 또는 지연 금지
- 자동매도 생성 금지
- score threshold 완화 금지
- provider route 변경 금지
- bot restart 금지
- 스윙 실주문 전환 금지
