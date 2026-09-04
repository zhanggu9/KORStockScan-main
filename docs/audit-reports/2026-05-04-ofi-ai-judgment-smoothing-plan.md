# OFI 기반 AI 판단 Smoothing 적용 방안 보고서

**수신:** 시스템 운영담당 / 전략개발담당
**발신:** 수석 감리인
**작성일:** 2026-05-04 KST
**대상:** 스캘핑매매 진입·보유·청산 단계의 연속 AI 판단 안정화
**핵심 주제:** Order Flow Imbalance(OFI)를 활용한 AI 판단 급변 완화 및 상태 전환 smoothing 설계

**검토 근거 문서:**
1. `2026-05-03-order-flow-imbalance-application-audit-report.md`
2. `2026-05-03-order-flow-imbalance-application-audit-review.md`
3. `2026-05-03-ofi-integrated-audit-result-report.md`

---

## 1. Executive Summary

현재 스캘핑매매 시스템은 진입·보유·청산 단계에서 AI 판단이 연속적으로 수행되며, 시장 데이터와 AI 응답 변화에 따라 `BUY`, `WAIT`, `SKIP`, `HOLD`, `REDUCE`, `EXIT` 판단이 짧은 시간 안에 급변할 수 있다.

이 문제를 완화하기 위해 OFI를 사용할 수 있다. 단, OFI를 새로운 매수·청산 판단자로 쓰는 것은 권고하지 않는다. OFI는 AI raw 판단을 대체하는 것이 아니라, AI 판단이 상태 전환으로 반영되기 전에 한 번 더 확인하고 완충하는 **deterministic smoothing layer**로 사용하는 것이 적절하다.

본 보고서의 종합 권고는 다음과 같다.

> **OFI/QI orderbook micro를 이용하여 AI raw 판단의 상태 전환을 smoothing한다.
> 진입 단계에서는 `BUY/SKIP debounce`, 보유 단계에서는 `HOLD ↔ EXIT_WATCH 완충`, 청산 단계에서는 `extreme bearish + 가격 약화` 확인 신호로 사용한다.
> 모든 적용은 shadow mode → entry canary → holding EXIT_WATCH → exit 확정 순서로 단계적으로 진행해야 한다.**

---

## 2. 현황 요약

기존 OFI 적용현황 보고서에 따르면 현재 시스템에는 OFI/QI orderbook micro가 이미 다음 형태로 구현되어 있다.

```text
ofi_instant
ofi_ewma
ofi_norm
ofi_z
qi
qi_ewma
micro_state
```

현재 적용 구조는 다음과 같다.

```text
실시간 websocket 체결/호가 이벤트
  ↓
ORDERBOOK_STABILITY_OBSERVER
  ↓
OFI/QI micro 계산
  ↓
entry latency snapshot
  ↓
price_context.orderbook_micro
  ↓
dynamic_entry_ai_price_canary_p2 AI 판단 컨텍스트
```

현재 적용 범위는 submitted 직전 entry price AI 판단 보조피처에 한정된다. 즉, OFI가 독립 hard gate로 주문을 차단하거나 holding/exit live rule에 직접 반영되는 구조는 아니다.

현재 `micro_state` 분류는 다음과 같다.

| 상태 | 조건 |
|---|---|
| `bullish` | `ofi_z >= +1.2` and `qi_ewma >= 0.55` |
| `bearish` | `ofi_z <= -1.0` and `qi_ewma < 0.48` |
| `neutral` | 위 조건 미충족 |
| `insufficient` | 표본 부족 또는 수량 부재 |

감리 검토에서는 다음 한계가 지적되었다.

| 구분 | 한계 |
|---|---|
| 적용 범위 | entry P2 보조피처 중심 |
| 운영 검증 | OFI ON/OFF cohort 효과 검증 부족 |
| threshold | bullish/bearish 임계값 비대칭 |
| 정책 위치 | OFI → SKIP 정책이 프롬프트에 의존 |
| staleness | snapshot 시점과 AI 응답 시점 간 유효성 관리 부족 |
| health | observer 장애와 insufficient 상태 구분 부족 |
| holding/exit | 직접 적용 미확인 |

따라서 smoothing 적용은 기존 OFI plumbing을 활용하되, 별도 안정화 계층을 설계하는 방식으로 접근해야 한다.

---

## 3. 문제 정의: AI 판단 급변

### 3.1 발생 가능한 급변 패턴

스캘핑매매에서는 다음과 같은 판단 변동이 자주 발생할 수 있다.

```text
BUY → WAIT → BUY → SKIP → BUY
HOLD → EXIT → HOLD → REDUCE → HOLD
EXIT → HOLD → EXIT → HOLD
```

이러한 판단 급변은 다음 문제를 만든다.

| 문제 | 설명 |
|---|---|
| 과잉 진입 회피 | 일시적 bearish 또는 AI 단발 SKIP으로 유효한 진입 기회 상실 |
| 과잉 청산 | 일시적 변동성에 의해 보유 포지션이 조기 청산 |
| 지연 청산 | AI가 HOLD를 반복하는 동안 실제 호가 흐름은 이미 악화 |
| 주문 상태 불안정 | 주문 제출·취소·재판단이 반복되어 슬리피지와 미체결 증가 |
| 로그 해석 어려움 | AI raw 판단과 최종 주문 판단의 인과 추적이 어려움 |

### 3.2 smoothing의 목표

smoothing은 AI 판단을 무시하기 위한 것이 아니다. 목표는 다음과 같다.

```text
1. AI raw 판단은 보존한다.
2. 최종 상태 전환은 OFI regime과 persistence로 완충한다.
3. 단발 신호에 의한 BUY/SKIP/EXIT 급변을 줄인다.
4. 지속적인 bearish 흐름에서는 위험 회피를 강화한다.
5. 지속적인 bullish 흐름에서는 불필요한 SKIP/EXIT를 줄인다.
```

---

## 4. 설계 원칙

### 4.1 OFI는 판단자가 아니라 상태 전환 완충장치다

OFI를 단독으로 매수·청산 판단자로 쓰면 위험하다. OFI는 노이즈가 크고 종목군별 분포 차이도 크다. 따라서 OFI의 역할은 다음으로 제한해야 한다.

```text
AI raw action
  ↓
OFI/QI regime 확인
  ↓
persistence / hysteresis / debounce 적용
  ↓
final action 결정
```

### 4.2 AI raw action과 final action을 분리한다

반드시 다음 두 값을 모두 로그에 남겨야 한다.

```text
ai_raw_action
final_action
```

예를 들어 AI가 `EXIT`을 반환했지만 OFI가 `stable_bullish`라면 최종 상태는 즉시 `EXIT`이 아니라 `EXIT_WATCH`가 될 수 있다.

```text
ai_raw_action = EXIT
ofi_regime = stable_bullish
final_action = EXIT_WATCH
smoothing_reason = EXIT_DEBOUNCED_BY_BULLISH_OFI
```

### 4.3 상태 전환은 hysteresis를 적용한다

진입 임계값과 해제 임계값을 다르게 둔다.

```text
stable_bearish 진입:
  micro_score_smooth <= -0.45 상태가 2~3회 연속

stable_bearish 해제:
  micro_score_smooth >= -0.15 상태가 2회 연속
```

이렇게 하면 상태가 다음처럼 흔들리는 것을 줄일 수 있다.

```text
bearish → neutral → bearish → neutral → bearish
```

### 4.4 holding/exit는 entry보다 더 보수적으로 적용한다

현재 구현은 bearish가 bullish보다 쉽게 발동하는 비대칭 임계값을 가진다.

```text
bullish: ofi_z >= +1.2 and qi_ewma >= 0.55
bearish: ofi_z <= -1.0 and qi_ewma < 0.48
```

entry에서 bearish를 민감하게 쓰는 것은 진입 회피 목적상 허용될 수 있다. 그러나 holding/exit에 그대로 적용하면 과잉청산이 발생할 수 있다. 따라서 holding/exit에는 더 엄격한 bearish 조건을 사용해야 한다.

권고 초기값:

| 용도 | 조건 |
|---|---|
| entry_bearish | `ofi_z <= -1.0 and qi_ewma < 0.48` |
| holding_exit_bearish | `ofi_z <= -1.2 and qi_ewma < 0.46` |
| hard_exit_extreme_bearish | `ofi_z <= -2.0 and qi_ewma < 0.45` |

---

## 5. OFI Regime Smoother 설계

### 5.1 입력값

현재 `orderbook_micro`에서 다음 값을 사용한다.

```text
ready
reason
qi
qi_ewma
ofi_norm
ofi_z
depth_ewma
micro_state
sample_quote_count
spread_ticks
```

추가 권고 필드:

```text
captured_at_ms
snapshot_age_ms
observer_healthy
observer_last_quote_age_ms
observer_last_trade_age_ms
```

### 5.2 OFI score 계산

OFI와 QI를 하나의 연속 점수로 변환한다.

```python
micro_score_raw = (
    0.65 * tanh(ofi_z / 2.0)
    + 0.35 * clip((qi_ewma - 0.50) / 0.10, -1.0, 1.0)
)
```

의미:

| 항목 | 의미 |
|---|---|
| `tanh(ofi_z / 2.0)` | 극단값을 제한한 OFI 방향성 |
| `(qi_ewma - 0.50) / 0.10` | queue imbalance 방향성 |
| `0.65 / 0.35` | OFI를 주 신호, QI를 보조 신호로 사용 |

### 5.3 EWMA smoothing

```python
micro_score_smooth = (
    0.70 * prev_micro_score_smooth
    + 0.30 * micro_score_raw
)
```

초기값 권고:

| 파라미터 | 값 | 설명 |
|---|---:|---|
| 이전 smooth weight | 0.70 | 기존 regime 유지력 |
| 신규 raw weight | 0.30 | 새 호가 흐름 반영 |
| bullish entry threshold | +0.45 | stable bullish 진입 |
| bearish entry threshold | -0.45 | stable bearish 진입 |
| neutral release threshold | ±0.15 | regime 해제 구간 |
| persistence count | 2~3회 | 단발 노이즈 차단 |

### 5.4 regime 정의

```text
stable_bullish
neutral
stable_bearish
insufficient
stale
observer_unhealthy
```

각 regime의 의미는 다음과 같다.

| regime | 의미 | 사용 정책 |
|---|---|---|
| `stable_bullish` | 지속적인 매수 우위 | BUY/SKIP/EXIT debounce에 사용 |
| `neutral` | 충분한 표본에서 중립 | OFI 단독 판단 금지 |
| `stable_bearish` | 지속적인 매도 우위 | BUY 제한, EXIT_WATCH 승격 |
| `insufficient` | 정상 수신 중 표본 부족 | OFI 판단 금지 |
| `stale` | snapshot 오래됨 | OFI 판단 금지 |
| `observer_unhealthy` | 데이터 경로 이상 | 시스템 health issue |

---

## 6. 단계별 적용 방안

## 6.1 진입 단계: BUY / WAIT / SKIP smoothing

진입 단계에서는 OFI를 “진입 허용/보류 확인 신호”로 사용한다.

### 권고 정책

| AI raw action | OFI regime | final action | 설명 |
|---|---|---|---|
| `BUY` | `stable_bullish` | `BUY` | 진입 허용 |
| `BUY` | `neutral` | `BUY` 또는 `WAIT` | 기존 정책 유지, 보수호가 가능 |
| `BUY` | `stable_bearish` | `WAIT` | 즉시 진입 보류 |
| `BUY` | `stale/insufficient` | 기존 정책 | OFI 근거 사용 금지 |
| `WAIT` | `stable_bullish` | `WAIT` | 다음 cycle BUY 후보 유지 |
| `SKIP` | `stable_bullish` | `WAIT` | 단발 SKIP debounce |
| `SKIP` | `stable_bearish` | `SKIP` | SKIP 허용 |
| `SKIP` | `neutral/insufficient` | 기존 정책 또는 warning | OFI 단독 SKIP 금지 |

### 예시

```text
AI raw sequence:
BUY → WAIT → BUY → SKIP → BUY

OFI regime:
stable_bullish 유지

final action:
BUY_CANDIDATE 유지 → SKIP은 WAIT로 debounce
```

### 진입 단계 권고 사유

진입 단계는 청산보다 위험이 낮기 때문에 smoothing을 가장 먼저 적용하기 적합하다. 실제 주문 확정 전 단계에서 `BUY`를 `WAIT`로 늦추는 것은 보수적이며, `SKIP`을 `WAIT`로 바꾸는 것도 즉시 매수가 아니라 재확인에 가깝다.

---

## 6.2 보유 단계: HOLD / REDUCE / EXIT smoothing

현재 holding/exit에는 OFI가 직접 적용되어 있지 않으므로, 이 영역은 신규 확장이다. 보유 단계에서는 OFI를 “포지션 thesis 유지 여부” 판단에 사용한다.

### 권고 정책

| AI raw action | OFI regime | final action | 설명 |
|---|---|---|---|
| `HOLD` | `stable_bullish` | `HOLD` | 보유 유지 |
| `HOLD` | `neutral` | `HOLD` | 기존 정책 유지 |
| `HOLD` | `stable_bearish` | `EXIT_WATCH` | 청산 감시로 승격 |
| `REDUCE` | `stable_bullish` | `HOLD` 또는 `REDUCE_WATCH` | 일부 축소 보류 가능 |
| `REDUCE` | `stable_bearish` | `REDUCE` | 축소 허용 |
| `EXIT` | `stable_bullish` | `EXIT_WATCH` | 즉시 청산 debounce |
| `EXIT` | `stable_bearish` | `EXIT` 또는 `REDUCE` | 청산 허용 |
| `EXIT` | `insufficient/stale` | 기존 리스크 정책 | OFI 근거 사용 금지 |

### 보유 상태 전환

```text
HOLD
  ↓ stable_bearish 2회 연속
EXIT_WATCH
  ↓ stable_bearish 지속 + 가격 약화
REDUCE 또는 EXIT
  ↓ stable_bullish 회복 + 가격 회복
HOLD 복귀
```

### 보유 단계의 핵심

AI가 한 번 `EXIT`을 말해도 OFI가 여전히 매수 우위이면 즉시 청산하지 않고 `EXIT_WATCH`로 완충한다. 반대로 AI가 계속 `HOLD`를 말하더라도 OFI가 지속적으로 bearish이고 가격도 약화되면 청산 감시로 승격한다.

---

## 6.3 청산 단계: 급청산과 지연청산 동시 방지

청산 단계에서는 OFI를 단독 청산 조건으로 쓰지 않는다. 청산은 다음 두 조건 중 하나를 만족할 때만 확정한다.

```text
1. AI EXIT 재확인
2. OFI extreme_bearish + 가격 약화 + 리스크 조건 악화
```

### soft exit trigger

```text
AI가 EXIT 또는 REDUCE
또는 OFI stable_bearish가 2~3회 지속
```

### hard exit trigger

```text
OFI extreme_bearish
AND 가격 약화
AND 체결/호가 지지 약화
AND snapshot not stale
```

### 권고 hard exit 조건 예시

```text
ofi_z <= -2.0
AND qi_ewma < 0.45
AND price_state.weakening = true
AND snapshot_age_ms <= MICRO_STALE_THRESHOLD_MS
AND observer_healthy = true
```

### 청산 단계 금지사항

```text
- OFI 단독 EXIT 금지
- stale OFI 기반 EXIT 금지
- insufficient 상태를 bearish로 간주 금지
- observer 장애 상태를 neutral로 간주 금지
```

---

## 7. 상태기계 설계

AI 판단을 직접 평균내는 방식은 권고하지 않는다. 예를 들어 `BUY=+1`, `WAIT=0`, `EXIT=-1`로 두고 평균내면 서로 의미가 다른 상태를 수학적으로 섞게 된다. 스캘핑에서는 action 평균보다 상태기계가 안전하다.

권고 상태기계:

```text
WATCHING
  ↓ AI BUY and OFI not stable_bearish
ENTRY_READY
  ↓ order submitted
ENTERED
  ↓ fill confirmed
HOLDING
  ↓ AI EXIT/REDUCE or OFI stable_bearish
EXIT_WATCH
  ↓ AI EXIT 재확인 or extreme_bearish + price weakening
EXIT
```

상태 전환 조건:

```text
WATCHING → ENTRY_READY:
  AI BUY
  AND OFI not stable_bearish
  AND orderbook_micro not stale

ENTRY_READY → SKIP:
  AI SKIP
  AND OFI stable_bearish
  AND snapshot not stale

ENTRY_READY → WAIT:
  AI BUY
  AND OFI stable_bearish

HOLDING → EXIT_WATCH:
  AI REDUCE/EXIT
  OR OFI stable_bearish 지속

EXIT_WATCH → EXIT:
  AI EXIT 재확인
  OR hard stop
  OR stable_bearish 지속 + 가격 약화

EXIT_WATCH → HOLDING:
  OFI stable_bullish 회복
  AND 가격 회복
```

---

## 8. 구현 예시

### 8.1 OFI smoothing state

```python
from dataclasses import dataclass
from math import tanh
from time import time


@dataclass
class OfiSmoothingState:
    micro_score_smooth: float = 0.0
    regime: str = "neutral"
    bullish_count: int = 0
    bearish_count: int = 0
    last_transition_ms: int = 0


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def now_ms() -> int:
    return int(time() * 1000)
```

### 8.2 OFI regime update

```python
def update_ofi_regime(
    prev: OfiSmoothingState,
    micro: dict | None,
    *,
    stale_threshold_ms: int = 700,
    raw_weight: float = 0.30,
    bullish_threshold: float = 0.45,
    bearish_threshold: float = -0.45,
    release_threshold: float = 0.15,
    persistence_required: int = 2,
) -> OfiSmoothingState:
    if not micro:
        return OfiSmoothingState(
            micro_score_smooth=prev.micro_score_smooth,
            regime="observer_unhealthy",
            bullish_count=0,
            bearish_count=0,
            last_transition_ms=now_ms(),
        )

    if not micro.get("ready"):
        return OfiSmoothingState(
            micro_score_smooth=prev.micro_score_smooth,
            regime="insufficient",
            bullish_count=0,
            bearish_count=0,
            last_transition_ms=now_ms(),
        )

    snapshot_age_ms = micro.get("snapshot_age_ms")
    if snapshot_age_ms is not None and snapshot_age_ms > stale_threshold_ms:
        return OfiSmoothingState(
            micro_score_smooth=prev.micro_score_smooth,
            regime="stale",
            bullish_count=0,
            bearish_count=0,
            last_transition_ms=now_ms(),
        )

    ofi_z = float(micro.get("ofi_z") or 0.0)
    qi_ewma = float(micro.get("qi_ewma") or 0.50)

    micro_score_raw = (
        0.65 * tanh(ofi_z / 2.0)
        + 0.35 * clip((qi_ewma - 0.50) / 0.10, -1.0, 1.0)
    )

    smooth = (1.0 - raw_weight) * prev.micro_score_smooth + raw_weight * micro_score_raw

    bullish_count = prev.bullish_count + 1 if smooth >= bullish_threshold else 0
    bearish_count = prev.bearish_count + 1 if smooth <= bearish_threshold else 0

    regime = prev.regime

    if bearish_count >= persistence_required:
        regime = "stable_bearish"
    elif bullish_count >= persistence_required:
        regime = "stable_bullish"
    elif abs(smooth) <= release_threshold:
        regime = "neutral"

    return OfiSmoothingState(
        micro_score_smooth=smooth,
        regime=regime,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        last_transition_ms=now_ms(),
    )
```

### 8.3 AI action smoothing

```python
def smooth_ai_action(
    *,
    stage: str,
    ai_action: str,
    ofi_regime: str,
    pnl_state: dict | None = None,
    price_state: dict | None = None,
) -> tuple[str, str]:
    pnl_state = pnl_state or {}
    price_state = price_state or {}

    hard_stop = bool(pnl_state.get("hard_stop", False))
    price_weakening = bool(price_state.get("weakening", False))
    price_recovering = bool(price_state.get("recovering", False))

    if stage == "ENTRY":
        if ai_action == "BUY" and ofi_regime == "stable_bearish":
            return "WAIT", "BUY_BLOCKED_BY_STABLE_BEARISH_OFI"

        if ai_action == "SKIP" and ofi_regime == "stable_bullish":
            return "WAIT", "SKIP_DEBOUNCED_BY_BULLISH_OFI"

        return ai_action, "AI_ACTION_ACCEPTED"

    if stage == "HOLDING":
        if ai_action == "EXIT" and ofi_regime == "stable_bullish" and not hard_stop:
            return "EXIT_WATCH", "EXIT_DEBOUNCED_BY_BULLISH_OFI"

        if ai_action == "HOLD" and ofi_regime == "stable_bearish" and price_weakening:
            return "EXIT_WATCH", "HOLD_ESCALATED_BY_BEARISH_OFI"

        if ai_action == "REDUCE" and ofi_regime == "stable_bullish" and not hard_stop:
            return "REDUCE_WATCH", "REDUCE_DEBOUNCED_BY_BULLISH_OFI"

        return ai_action, "AI_ACTION_ACCEPTED"

    if stage == "EXIT_WATCH":
        if hard_stop:
            return "EXIT", "EXIT_CONFIRMED_BY_HARD_STOP"

        if ofi_regime == "stable_bearish" and price_weakening:
            return "EXIT", "EXIT_CONFIRMED_BY_STABLE_BEARISH_OFI"

        if ofi_regime == "stable_bullish" and price_recovering:
            return "HOLD", "EXIT_CANCELLED_BY_OFI_RECOVERY"

        return ai_action, "EXIT_WATCH_MAINTAINED"

    return ai_action, "UNKNOWN_STAGE_ACTION_ACCEPTED"
```

---

## 9. 필수 안전장치

### 9.1 snapshot staleness

OFI는 초단기 신호이므로 AI 호출 지연 중 상태가 바뀔 수 있다. 따라서 snapshot timestamp가 필요하다.

필수 필드:

```text
captured_at_ms
snapshot_age_ms
stale_reason
```

권고 정책:

```text
snapshot_age_ms > 700ms:
  OFI smoothing 입력으로 사용 금지

snapshot_age_ms > 1500ms:
  orderbook_micro = stale
  AI 판단에서 OFI 근거 제거
```

위 수치는 초기값이며 실제 AI latency p50/p90/p99 기준으로 조정해야 한다.

### 9.2 observer health 분리

`insufficient`와 장애 상태를 구분해야 한다.

```text
micro_state = None
  → observer 장애 또는 데이터 경로 이상

micro_state = insufficient
  → 정상 수신 중이나 표본 부족

micro_state = neutral
  → 충분한 표본에서 중립

micro_state = bearish / bullish
  → 유효 신호
```

`None`이나 observer 장애 상태를 neutral처럼 취급해서는 안 된다.

### 9.3 OFI 단독 청산 금지

청산 단계에서는 OFI 단독 판단을 금지한다.

```text
금지:
  stable_bearish만으로 EXIT 확정

허용:
  stable_bearish 지속
  AND 가격 약화
  AND AI 재확인 또는 hard risk 조건
```

### 9.4 threshold 비대칭 명문화

현재 bearish threshold가 bullish threshold보다 쉽게 발동한다. smoothing 적용 전 다음 중 하나를 결정해야 한다.

| 선택지 | 설명 |
|---|---|
| 보수적 bearish bias 유지 | entry 방어용으로 명문화 |
| holding/exit 별도 threshold | 청산 과민 방지를 위해 더 엄격한 bearish 사용 |
| 데이터 기반 재calibration | 종목군·시간대별 발동률 비교 후 조정 |

---

## 10. 로그 설계

OFI smoothing 도입 시 다음 로그 필드를 남겨야 한다.

```text
ai_raw_action
ai_raw_confidence
stage_before
stage_after
orderbook_micro_ready
orderbook_micro_state
ofi_z
ofi_norm
qi_ewma
ofi_score_raw
ofi_score_smooth
ofi_regime
ofi_bullish_persistence_count
ofi_bearish_persistence_count
snapshot_age_ms
observer_healthy
smoothing_action
smoothing_reason
final_action
```

운영 검증 핵심 집계:

```text
raw_ai_flip_count
smoothed_flip_count
exit_debounced_count
skip_debounced_count
buy_blocked_count
bearish_escalation_count
stale_ofi_ignored_count
observer_unhealthy_count
```

---

## 11. 검증 KPI

### 11.1 판단 안정성 KPI

| KPI | 목적 |
|---|---|
| raw_ai_flip_rate | 기존 AI 판단 급변률 |
| smoothed_flip_rate | smoothing 후 급변률 |
| flip_reduction_ratio | 안정화 효과 |
| debounce_count | 단발 판단 완충 횟수 |
| stage_transition_count | 상태 전환 감소 여부 |

### 11.2 매매 품질 KPI

| KPI | 목적 |
|---|---|
| fill_rate | 진입 체결 품질 |
| partial_fill_rate | 부분체결 감소 여부 |
| unfilled_rate | 미체결 증가 여부 |
| entry_slippage_bps | 진입가격 개선 여부 |
| exit_slippage_bps | 청산가격 악화 여부 |
| soft_stop_rate | 손실 회피 여부 |
| missed_upside_bps | 과잉 SKIP 또는 과잉 EXIT 여부 |

### 11.3 OFI 품질 KPI

| KPI | 목적 |
|---|---|
| stable_bullish_hit_rate | bullish regime 발동률 |
| stable_bearish_hit_rate | bearish regime 발동률 |
| stale_snapshot_rate | 오래된 OFI 사용 위험 |
| observer_unhealthy_rate | 데이터 경로 장애율 |
| insufficient_rate | 표본 부족 비율 |
| regime_persistence_p50/p90 | regime 지속성 |

---

## 12. 운영 도입 순서

### 12.1 1단계: shadow mode

실제 주문에는 반영하지 않고 로그만 남긴다.

```text
AI raw action
OFI smoothed action
기존 final action
```

측정 항목:

```text
raw_ai_flip_rate
smoothed_ai_flip_rate
would_block_buy_count
would_delay_exit_count
would_escalate_exit_count
would_skip_debounce_count
```

### 12.2 2단계: entry smoothing canary

먼저 진입 단계에만 적용한다.

```text
BUY + stable_bearish → WAIT
SKIP + stable_bullish → WAIT 재확인
```

이 단계에서는 실제 청산 로직에는 반영하지 않는다.

### 12.3 3단계: holding EXIT_WATCH 적용

보유 단계에서는 바로 EXIT하지 않고 중간 상태만 둔다.

```text
HOLD + stable_bearish → EXIT_WATCH
EXIT + stable_bullish → EXIT_WATCH
```

### 12.4 4단계: exit 확정 조건 확장

청산 확정은 별도 검증 이후 적용한다.

```text
EXIT 확정 조건:
  AI EXIT 재확인
  OR hard stop
  OR stable_bearish 지속 + 가격 약화
```

---

## 13. P0 / P1 / P2 작업계획

### P0 — 즉시

| 항목 | 조치 |
|---|---|
| OFI smoothing shadow log 설계 | raw/final action, ofi_regime, smoothing_reason 기록 |
| threshold 비대칭 정책 결정 | entry/holding/exit별 threshold 분리 |
| staleness 필드 추가 | `captured_at_ms`, `snapshot_age_ms` |
| observer 상태 분리 | `None`, `insufficient`, `neutral` 분리 |
| 상태기계 초안 작성 | WATCHING→ENTRY_READY→HOLDING→EXIT_WATCH→EXIT |

### P1 — 다음 스프린트

| 항목 | 조치 |
|---|---|
| entry smoothing canary | BUY/SKIP debounce 적용 |
| post-validation 추가 | OFI 근거 SKIP/EXIT 정책 위반 검증 |
| 테스트 추가 | threshold boundary, regime transition, stale handling |
| KPI dashboard | raw vs smoothed flip rate 비교 |
| holding EXIT_WATCH shadow | 보유 단계 영향도 로그 산출 |

### P2 — 운영 검증 후

| 항목 | 조치 |
|---|---|
| holding EXIT_WATCH live 적용 | 청산 전 완충 상태 도입 |
| hard_exit_extreme_bearish 검토 | OFI + 가격 약화 결합 청산 |
| 종목군별 calibration | 대형주/소형주/테마주 threshold 분리 |
| watching 단계 OFI 주입 | BUY/WAIT/DROP 판단 전단 적용 |
| non-AI guard shadow | AI 장애 시 극단 bearish만 방어 |

---

## 14. 테스트 케이스

권고 테스트 목록:

```text
test_ofi_smoother_raw_score_bounds
test_ofi_smoother_ewma_update
test_ofi_regime_bullish_persistence
test_ofi_regime_bearish_persistence
test_ofi_regime_hysteresis_release
test_ofi_regime_stale_snapshot_ignored
test_ofi_regime_observer_unhealthy_not_neutral
test_entry_buy_blocked_by_stable_bearish
test_entry_skip_debounced_by_stable_bullish
test_holding_exit_debounced_by_stable_bullish
test_holding_hold_escalated_by_stable_bearish
test_exit_watch_exit_confirmed_by_bearish_and_price_weakening
test_exit_watch_cancelled_by_bullish_recovery
test_ofi_does_not_force_exit_when_insufficient
test_ofi_does_not_force_exit_when_stale
```

---

## 15. 감리상 금지사항

P0/P1 조치 전까지 다음을 금지한다.

```text
1. OFI 단독 EXIT 확정 금지
2. stale OFI 기반 smoothing 금지
3. observer 장애를 neutral로 처리 금지
4. insufficient를 bearish 또는 bullish로 보정 금지
5. 현재 bearish threshold를 holding/exit에 그대로 적용 금지
6. shadow 검증 없이 live 청산 로직 변경 금지
7. AI raw action 로그 없이 final action만 기록 금지
```

---

## 16. 최종 권고

OFI는 AI 판단 급변을 smoothing하는 데 사용할 수 있다. 다만 적용 방식은 다음 원칙을 따라야 한다.

```text
- OFI는 AI 판단 대체물이 아니다.
- OFI는 상태 전환 완충장치다.
- entry에서는 BUY/SKIP debounce에 우선 적용한다.
- holding에서는 EXIT_WATCH 승격/해제에 사용한다.
- exit 확정은 OFI 단독이 아니라 가격 약화와 결합한다.
- snapshot staleness와 observer health를 반드시 관리한다.
- shadow mode에서 raw vs smoothed action 차이를 먼저 측정한다.
```

수석 감리인 최종 의견:

> **OFI 기반 smoothing은 현재 시스템의 AI 판단 급변 문제를 완화할 수 있는 실용적 방안이다.
> 단, OFI를 새로운 매매판단 엔진으로 승격해서는 안 되며, AI raw 판단의 상태 전환을 지연·확인·완충하는 deterministic smoothing layer로 제한해야 한다.
> 가장 안전한 적용 순서는 shadow mode → entry smoothing canary → holding EXIT_WATCH → exit 확정 조건 확장이다.**

---

## 17. 결재용 한 줄 요약

> **OFI는 스캘핑 AI 판단의 급변을 완화하기 위한 smoothing layer로 활용 가능하다. 우선 entry 단계의 BUY/SKIP debounce에 적용하고, holding/exit는 EXIT_WATCH 완충 상태를 거쳐 단계적으로 확장해야 한다.**

---

## 부록 A. 권고 초기 설정값

| 파라미터 | 권고 초기값 |
|---|---:|
| `raw_weight` | 0.30 |
| `prev_smooth_weight` | 0.70 |
| `bullish_threshold` | +0.45 |
| `bearish_threshold` | -0.45 |
| `release_threshold` | ±0.15 |
| `persistence_required` | 2 |
| `entry_stale_threshold_ms` | 700 |
| `hard_stale_threshold_ms` | 1500 |
| `holding_exit_bearish_ofi_z` | -1.2 |
| `holding_exit_bearish_qi` | 0.46 |
| `hard_exit_extreme_ofi_z` | -2.0 |
| `hard_exit_extreme_qi` | 0.45 |

---

## 부록 B. 운영 로그 예시

```json
{
  "code": "005930",
  "stage_before": "HOLDING",
  "ai_raw_action": "EXIT",
  "ai_raw_confidence": 0.61,
  "orderbook_micro_ready": true,
  "orderbook_micro_state": "bullish",
  "ofi_z": 1.38,
  "qi_ewma": 0.57,
  "ofi_score_raw": 0.52,
  "ofi_score_smooth": 0.48,
  "ofi_regime": "stable_bullish",
  "snapshot_age_ms": 312,
  "observer_healthy": true,
  "smoothing_action": "DEBOUNCE_EXIT",
  "smoothing_reason": "EXIT_DEBOUNCED_BY_BULLISH_OFI",
  "final_action": "EXIT_WATCH"
}
```

---

## 부록 C. Shadow Mode 판정 예시

```text
case_id: 2026-05-04-ENTRY-001
AI raw: SKIP
OFI regime: stable_bullish
Shadow smoothed action: WAIT
Actual final action: SKIP
Post 5m mid price: +0.42%

해석:
기존 AI SKIP은 missed upside 가능성이 있음.
단, 표본 확대 후 통계적으로 판단.
```

```text
case_id: 2026-05-04-HOLD-007
AI raw: HOLD
OFI regime: stable_bearish
Price state: weakening
Shadow smoothed action: EXIT_WATCH
Actual final action: HOLD
Post 5m mid price: -0.35%

해석:
OFI smoothing이 지연청산 방지에 기여할 가능성 있음.
단, EXIT 확정이 아니라 EXIT_WATCH 승격부터 적용 권고.
```

---

**문서 끝**
