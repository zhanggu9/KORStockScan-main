# NXT 스캘핑 로직 최종 정리안 v2.0

작성일: 2026-05-14 KST
대상 시스템: KORStockScan / SCALPING / PYRAMID 연동
대상 구간: NXT 단독 세션 중심 — 08:00~08:50, 16:00~20:00
문서 성격: 시스템 설계·구현 지시서 / 리스크 가드 설계안

> 주의: 본 문서는 자동매매 시스템의 구조 설계와 리스크 제어를 위한 기술 문서이며, 특정 종목의 매수·매도 추천이 아니다.

---

## 1. 최종 결론

NXT 스캘핑은 기존 KRX 정규장 SCALPING 로직을 단순 확장하면 안 된다.
프리마켓과 애프터마켓은 체결 빈도, 호가 두께, 참여자 구성, 가격 기준, VI 리스크가 정규장과 다르므로 **NXT 전용 세션 레짐과 하드 게이트**가 필요하다.

최종 운용 방향은 다음과 같다.

```text
08:00~08:50:
  가격발견 + 선별 scout 중심
  08:03 이후 제한적 진입
  08:40 이후 리스크 오프
  08:45 이후 신규 매수 차단
  08:48 전후 NXT 스캘핑 진입분 정리

16:00~20:00:
  16:00~17:00만 제한적 실전 스캘핑 후보
  17:00~18:30은 선별 진입
  18:30~19:00은 예외적 scout only
  19:00 이후는 원칙적으로 reduce-only
  19:30 이후 신규 매수 금지 및 청산 우선

공통:
  AI BUY는 주문 조건이 아니라 후보 신호
  OFI는 독립 매수 조건이 아니라 debounce/smoothing 계층
  스프레드, 호가 깊이, 체결 공백, VI, 상하한가 거리, 일일 손실 한도를 AI보다 우선 적용
```

---

## 2. 제도·운영 전제

### 2.1 NXT 거래 시간

NXT 공식 안내 기준으로 NXT는 08:00~20:00까지 운영되며, 프리마켓은 08:00~08:50, 애프터마켓은 정규장 이후 20:00까지 운영된다.
다만 자료와 증권사 안내에 따라 애프터마켓의 주문 접수·거래 시작 표기가 15:30 또는 15:40으로 다르게 안내되는 경우가 있다.

본 설계안은 사용자가 지정한 **16:00~20:00**을 애프터마켓 운용 대상으로 삼으므로, 15:30/15:40 표기 차이는 설계상 큰 영향을 주지 않는다.

### 2.2 KRX 기준가 사용 원칙

NXT 단독 세션에서는 KRX의 실시간 체결가가 멈춰 있으므로, **KRX last를 NXT 체결 검증 기준으로 사용하면 안 된다.**

그러나 다음 값은 반드시 유지해야 한다.

```text
유지해야 할 KRX 기준값:
  KRX close
  KRX 기준가
  NXT vs KRX close premium/discount
  가격제한폭 거리
  전일 종가 대비 변동률
```

이유는 NXT 가격제한폭과 과열·갭·프리미엄 판단이 KRX 종가 또는 기준가와 연결되기 때문이다.

### 2.3 VI 정책

현재 NXT VI 구조와 향후 제도 개선안은 코드에 하드코딩하지 말고 feature flag로 분리한다.
2026년 9월 이후 정적 VI 및 단일가 전환 제도 도입 추진 보도가 있으므로, `NXT_VI_POLICY_VERSION`을 둔다.

```yaml
nxt_vi_policy:
  current:
    version: "pre_2026_09_14"
    dynamic_vi_enabled: true
    static_vi_enabled: false
    call_auction_on_vi: false

  future_candidate:
    version: "post_2026_09_14"
    dynamic_vi_enabled: true
    static_vi_enabled: true
    call_auction_on_vi: true
```

---

## 3. 다른 설계자 제안 검토 결과

### 3.1 채택할 부분

```text
채택:
  strategy == "SCALPING" and venue == "NXT" 분기
  NXT 전용 파라미터 테이블
  시간대별 레짐 분리
  PYRAMID 축소
  스프레드 가드
  호가 깊이 가드
  체결 빈도 가드
  종목 단위 NXT 일일 손실 한도
  AI task_type 분리
  MAX_POSITION_PCT NXT 별도 캡
```

### 3.2 수정이 필요한 부분

```text
수정 필요:
  1. 프리마켓 갭 ±2% 고정 필터는 너무 단순하다.
  2. 16:00~17:30을 표준 SCALPING 파라미터로 처리하면 위험하다.
  3. KRX last 제거는 맞지만 KRX close/reference는 유지해야 한다.
  4. 08:48 강제청산은 전체 보유분이 아니라 NXT 스캘핑 진입분 한정이어야 한다.
  5. 19:00 이후 신규진입은 AI confidence가 아니라 탈출 가능성 기준으로 제한해야 한다.
  6. VI 정책은 현행/변경 후를 feature flag로 분리해야 한다.
```

---

## 4. 최종 세션 레짐

```yaml
nxt_sessions:
  pre_discovery:
    time: "08:00:00-08:03:00"
    allow_new_entry: false
    allow_scout: false
    purpose: "가격발견, 첫 체결가, 호가 안정성, 체결 빈도 관찰"

  pre_active:
    time: "08:03:00-08:30:00"
    allow_new_entry: true
    allow_scout: true
    max_position_ratio_vs_krx: 0.20
    pyramid_enabled: false
    main_patterns:
      - NXT_PRE_GAP_CONTINUATION
      - NXT_PRE_PULLBACK_RECLAIM

  pre_auction_aware:
    time: "08:30:00-08:40:00"
    allow_new_entry: "selective"
    max_position_ratio_vs_krx: 0.15
    pyramid_enabled: false
    note: "KRX 개장 동시호가 접수 이후 NXT 호가 변화 감시"

  pre_risk_off:
    time: "08:40:00-08:45:00"
    allow_new_entry: "high_quality_scout_only"
    max_position_ratio_vs_krx: 0.10
    pyramid_enabled: false

  pre_closeout:
    time: "08:45:00-08:50:00"
    allow_new_entry: false
    cancel_unfilled_buy_orders: true
    reduce_scalping_positions: true
    flatten_scalping_positions_by: "08:48:00~08:49:30"

  after_early:
    time: "16:00:00-17:00:00"
    allow_new_entry: true
    use_nxt_params: true
    max_position_ratio_vs_krx: 0.30
    pyramid_max_add_count: 1
    main_patterns:
      - NXT_AFTER_CLOSE_CONTINUATION
      - NXT_AFTER_PREMIUM_EXIT

  after_selective:
    time: "17:00:00-18:30:00"
    allow_new_entry: "selective"
    max_position_ratio_vs_krx: 0.20
    pyramid_enabled: false
    require_news_or_theme_if_premium_gte_pct: 3.0

  after_thin:
    time: "18:30:00-19:00:00"
    allow_new_entry: "exceptional_scout_only"
    max_position_ratio_vs_krx: 0.05
    pyramid_enabled: false

  after_reduce_only:
    time: "19:00:00-19:30:00"
    allow_new_entry: false
    reduce_only: true
    allow_exceptional_scout: false

  after_closeout:
    time: "19:30:00-20:00:00"
    allow_new_entry: false
    cancel_unfilled_buy_orders: true
    flatten_scalping_positions: true
```

---

## 5. NXT 공통 하드 게이트

AI 판단보다 먼저 아래 게이트를 통과해야 한다.
이 중 하나라도 실패하면 AI가 BUY를 반환해도 주문하지 않는다.

```python
def nxt_common_hard_gate(ctx):
    if ctx.venue != "NXT":
        return "NOT_NXT"

    if not ctx.is_nxt_eligible:
        return "BLOCK_NOT_NXT_ELIGIBLE"

    if ctx.session_state in ["pre_closeout", "after_reduce_only", "after_closeout"]:
        return "REDUCE_ONLY"

    if ctx.quote_age_ms > ctx.max_quote_age_ms:
        return "BLOCK_STALE_QUOTE"

    if ctx.spread_ticks > ctx.max_spread_ticks:
        return "BLOCK_WIDE_SPREAD_TICKS"

    if ctx.spread_pct > ctx.max_spread_pct:
        return "BLOCK_WIDE_SPREAD_PCT"

    if ctx.trade_gap_sec > ctx.max_trade_gap_sec:
        return "BLOCK_TRADE_GAP"

    if ctx.trade_count_60s < ctx.min_trade_count_60s:
        return "BLOCK_LOW_TRADE_COUNT"

    if ctx.top5_bid_value < ctx.order_notional * ctx.min_bid_depth_mult:
        return "BLOCK_THIN_BID_DEPTH"

    if ctx.top5_ask_value < ctx.order_notional * ctx.min_ask_depth_mult:
        return "BLOCK_THIN_ASK_DEPTH"

    if ctx.impact_buy_price_pct > ctx.max_impact_buy_pct:
        return "BLOCK_BUY_IMPACT"

    if ctx.vi_status in ["VI_ACTIVE", "VI_IMMINENT"]:
        return "BLOCK_VI_RISK"

    if ctx.distance_to_dynamic_vi_pct < ctx.min_dynamic_vi_distance_pct:
        return "BLOCK_NEAR_DYNAMIC_VI"

    if ctx.distance_to_upper_limit_pct < ctx.min_limit_distance_pct:
        return "BLOCK_NEAR_UPPER_LIMIT"

    if ctx.distance_to_lower_limit_pct < ctx.min_limit_distance_pct:
        return "BLOCK_NEAR_LOWER_LIMIT"

    if ctx.symbol_daily_nxt_loss_pct <= -ctx.max_symbol_daily_nxt_loss_pct:
        return "BLOCK_SYMBOL_NXT_DAILY_LOSS"

    return "PASS"
```

---

## 6. 가격 기준 분리

NXT 단독 세션에서는 실행 기준과 리스크 기준을 분리한다.

```python
price_refs = {
    "execution_ref": "NXT_LAST_OR_MID",
    "quote_ref": "NXT_BID_ASK",
    "microstructure_ref": "NXT_MICRO_VWAP",
    "risk_ref": "KRX_CLOSE",
    "premium_ref": "KRX_CLOSE",
    "limit_ref": "KRX_CLOSE"
}
```

### 금지

```text
NXT 프리/애프터에서 KRX last를 실시간 체결 검증값으로 사용하는 것
```

### 허용·필수

```text
NXT bid/ask/last/mid/micro_vwap으로 체결 가능성 판단
KRX close/reference로 갭, 프리미엄, 가격제한폭, 과열 여부 판단
```

---

## 7. 스프레드·호가 깊이 가드

스프레드 필터는 pct만으로 부족하다.
NXT 스캘핑에서는 아래 네 가지를 함께 사용한다.

```text
spread_ticks
spread_pct
top5_depth_notional
impact_price_for_order
```

```python
def spread_depth_gate(ctx):
    if ctx.spread_ticks > ctx.max_spread_ticks:
        return "BLOCK_SPREAD_TICKS"

    if ctx.spread_pct > ctx.max_spread_pct:
        return "BLOCK_SPREAD_PCT"

    if ctx.impact_buy_price_pct > ctx.max_impact_buy_pct:
        return "BLOCK_MARKET_IMPACT"

    if ctx.top5_bid_value < ctx.order_notional * ctx.min_bid_depth_mult:
        return "BLOCK_THIN_BID"

    if ctx.top5_ask_value < ctx.order_notional * ctx.min_ask_depth_mult:
        return "BLOCK_THIN_ASK"

    return "PASS"
```

초기 권장값은 다음과 같다.

```yaml
spread_depth_params:
  pre_active:
    max_spread_ticks: 2
    min_bid_depth_mult: 8
    min_ask_depth_mult: 5
    max_impact_buy_pct: 0.30

  pre_auction_aware:
    max_spread_ticks: 2
    min_bid_depth_mult: 10
    min_ask_depth_mult: 6
    max_impact_buy_pct: 0.25

  after_early:
    max_spread_ticks: 2
    min_bid_depth_mult: 8
    min_ask_depth_mult: 5
    max_impact_buy_pct: 0.30

  after_selective:
    max_spread_ticks: 1
    min_bid_depth_mult: 10
    min_ask_depth_mult: 7
    max_impact_buy_pct: 0.20

  after_thin:
    max_spread_ticks: 1
    min_bid_depth_mult: 12
    min_ask_depth_mult: 8
    max_impact_buy_pct: 0.15
```

---

## 8. 체결 빈도·체결 공백 가드

최근 1분 체결 건수만 보면 부족하다.
NXT에서는 체결이 갑자기 끊기는 경우가 많으므로 `trade_gap_sec`를 반드시 추가한다.

```python
if ctx.trade_count_60s < ctx.min_trade_count_60s:
    return "BLOCK_LOW_TRADE_COUNT"

if ctx.trade_gap_sec > ctx.max_trade_gap_sec:
    return "BLOCK_TRADE_GAP"
```

초기 권장값은 고정값보다 종목별 분위수 기반으로 설정한다.

```yaml
trade_flow_guard:
  pre_active:
    min_trade_count_60s: "symbol_quantile_q60"
    max_trade_gap_sec: 5

  pre_auction_aware:
    min_trade_count_60s: "symbol_quantile_q70"
    max_trade_gap_sec: 4

  after_early:
    min_trade_count_60s: "symbol_quantile_q50"
    max_trade_gap_sec: 5

  after_selective:
    min_trade_count_60s: "symbol_quantile_q70"
    max_trade_gap_sec: 7

  after_thin:
    min_trade_count_60s: "symbol_quantile_q80"
    max_trade_gap_sec: 3
```

---

## 9. 프리마켓 갭 필터 수정안

기존 제안의 “전일 KRX 종가 대비 갭 ±2% 이내”는 초기 안전장치로는 가능하지만, 실전 로직에는 너무 단순하다.

최종안은 패턴별 갭 레짐을 사용한다.

```yaml
premarket_gap_policy:
  normal_continuation:
    gap_pct_min: 0.3
    gap_pct_max: 4.0
    require_trade_flow: true
    require_micro_vwap_hold: true
    scout_only: false

  pullback_reclaim:
    initial_gap_pct_min: 0.5
    initial_gap_pct_max: 6.0
    require_pullback_pct: "1.0~2.5"
    require_reclaim_micro_vwap: true
    scout_only: false

  panic_recovery:
    gap_pct_min: -6.0
    gap_pct_max: -0.5
    require_recovery_state: "RECOVERY_CONFIRMED"
    scout_only: true

  block_extreme:
    abs_gap_pct_gte: 10.0
    action: "BLOCK_OR_EXIT_ONLY"
```

---

## 10. 주요 진입 패턴

### 10.1 NXT_PRE_GAP_CONTINUATION

```text
시간:
  08:03~08:30

목적:
  전일 KRX 종가 대비 강한 갭이 실제 매수세로 유지되는지 확인

진입 조건:
  NXT vs KRX close +0.3%~+4.0%
  spread_ticks <= 2
  trade_count_60s 충분
  trade_gap_sec <= 5
  price_above_nxt_micro_vwap
  bid_replenishment_score >= 0.6
  OFI debounce CONFIRMED
  AI BUY 또는 WATCH_BUY

청산 조건:
  +3~8틱
  또는 +0.3%~+0.8%
  또는 OFI 반전
  또는 bid depth 50% 이상 증발
  또는 08:45 이후 리스크 오프
```

### 10.2 NXT_PRE_PULLBACK_RECLAIM

```text
시간:
  08:10~08:40

목적:
  첫 급등 추격 대신 눌림 후 재돌파만 매수

진입 조건:
  초기 갭 +0.5%~+6.0%
  고점 대비 -1.0%~-2.5% 눌림
  micro_vwap 재상향
  매도 압력 감소
  QI/OFI 개선
  AI BUY 또는 WATCH_BUY

청산 조건:
  직전 고점 근처
  +0.3%~+0.8%
  micro_vwap 재이탈
  spread_ticks 급확대
```

### 10.3 NXT_AFTER_CLOSE_CONTINUATION

```text
시간:
  16:00~17:00

목적:
  KRX 종가 이후 강한 종목의 짧은 연속성 포착

진입 조건:
  NXT vs KRX close +0.3%~+2.5%
  spread_ticks <= 2
  trade_gap_sec <= 5
  price_above_after_micro_vwap
  bid_replenishment_score >= 0.6
  OFI debounce CONFIRMED
  AI BUY 또는 WATCH_BUY

청산 조건:
  +3~6틱
  또는 +0.25%~+0.6%
  KRX close 재이탈
  체결 공백 확대
  bid depth 급감
```

### 10.4 NXT_AFTER_PREMIUM_EXIT

```text
시간:
  16:00~19:30

목적:
  기존 보유 종목이 NXT에서 과도한 프리미엄을 받을 때 분할 익절

조건:
  보유 중
  NXT 가격이 KRX close 대비 +2% 이상
  OFI 약화
  매도호가 증가
  체결강도 둔화

행동:
  신규 매수 금지
  분할 익절
  프리미엄 축소 시 전량 청산 후보
```

### 10.5 NXT_PANIC_RECOVERY_SCOUT

```text
시간:
  08:10~08:40
  16:00~18:30

목적:
  급락 후 회복이 확인된 경우만 소액 scout

진입 금지:
  PANIC_DETECTED 직후
  하락 체결 연속
  bid depth 붕괴
  VI 근접

진입 허용:
  PANIC_DETECTED -> STABILIZING -> RECOVERY_CONFIRMED 전환
  저점 대비 +0.5% 이상 회복
  매도 체결 감소
  bid replenishment 확인
  AI BUY 또는 WATCH_BUY 2회 이상 연속
```

---

## 11. 진입 점수 모델

```python
def nxt_entry_score(ctx):
    score = 0

    # 가격 위치
    if ctx.price_above_nxt_micro_vwap:
        score += 10

    if 0.3 <= ctx.nxt_vs_krx_close_pct <= 4.0:
        score += 10

    # 체결 흐름
    if ctx.trade_intensity_60s_z >= 1.0:
        score += 15

    if ctx.trade_gap_sec <= 3:
        score += 10

    # 호가 안정성
    if ctx.spread_ticks <= 1:
        score += 10

    if ctx.bid_replenishment_score >= 0.6:
        score += 15

    if ctx.impact_buy_price_pct <= ctx.max_impact_buy_pct * 0.7:
        score += 10

    # OFI smoothing
    if ctx.ofi_debounce_state == "CONFIRMED":
        score += 10

    if ctx.ofi_flip_rate_high:
        score -= 15

    # AI 판단
    if ctx.ai_decision == "BUY":
        score += 20
    elif ctx.ai_decision == "WATCH_BUY":
        score += 10
    elif ctx.ai_decision in ["SELL", "AVOID"]:
        score -= 30

    # 세션 위험도
    if ctx.session_state in ["pre_risk_off", "after_thin"]:
        score -= 15

    return score
```

세션별 진입 threshold 초안:

```yaml
entry_threshold:
  pre_active: 65
  pre_auction_aware: 72
  pre_risk_off: 80
  after_early: 65
  after_selective: 75
  after_thin: 85
```

최종 주문 결정:

```python
hard_gate = nxt_common_hard_gate(ctx)
score = nxt_entry_score(ctx)

if hard_gate == "PASS" and score >= ctx.entry_threshold:
    action = "SCOUT_BUY"
elif hard_gate == "REDUCE_ONLY":
    action = "REDUCE_OR_WAIT"
else:
    action = "WAIT"
```

---

## 12. 주문·체결 정책

NXT 프리·애프터에서는 가격을 맞히는 것보다 **체결 후 빠져나올 수 있는지**가 더 중요하다.

```yaml
order_policy:
  default:
    order_type: "limit_or_broker_supported_best_limit"
    ttl_ms: 700-1500
    max_chase_ticks: 1
    cancel_if_unfilled: true
    retry_limit: 2
    cooldown_after_retry_fail_sec: 60

  strong_momentum:
    allow_one_tick_improvement: true
    condition:
      - spread_ticks <= 2
      - trade_gap_sec <= 3
      - top5_depth_sufficient: true

  forbidden:
    - unlimited_chasing
    - averaging_down_after_loss
    - repeated_modify_loop
    - pyramid_while_unrealized_loss
    - market_like_order_when_spread_wide
```

### 포지션 크기

```yaml
position_sizing:
  pre_discovery:
    ratio: 0

  pre_active:
    scout_ratio: 0.10-0.20
    max_total_ratio_vs_krx: 0.20
    pyramid_enabled: false

  pre_auction_aware:
    scout_ratio: 0.10
    max_total_ratio_vs_krx: 0.15
    pyramid_enabled: false

  pre_risk_off:
    scout_ratio: 0.05-0.10
    max_total_ratio_vs_krx: 0.10
    pyramid_enabled: false

  after_early:
    scout_ratio: 0.10-0.20
    max_total_ratio_vs_krx: 0.30
    pyramid_max_add_count: 1

  after_selective:
    scout_ratio: 0.05-0.10
    max_total_ratio_vs_krx: 0.20
    pyramid_enabled: false

  after_thin:
    scout_ratio: 0.03-0.05
    max_total_ratio_vs_krx: 0.05
    pyramid_enabled: false

  after_reduce_only:
    new_buy_ratio: 0

  after_closeout:
    new_buy_ratio: 0
```

---

## 13. PYRAMID 정책

NXT에서는 PYRAMID를 공격적 수익 극대화 도구가 아니라, **강한 흐름에서만 제한적으로 허용되는 보조 진입**으로 본다.

```yaml
pyramid_policy:
  nxt_premarket:
    enabled: false
    max_add_count: 0
    reason: "세션 짧음 + 08:50 단절 리스크"

  nxt_after_early:
    enabled: "selective"
    max_add_count: 1
    add_only_if_unrealized_profit: true
    require_ofi_confirmed: true
    require_bid_replenishment: true
    max_total_ratio_vs_krx: 0.30

  nxt_after_selective:
    enabled: false
    max_add_count: 0

  nxt_after_late:
    enabled: false
    max_add_count: 0
```

Stage 1 `math.ceil` 패치는 기존과 동일하게 적용하되, NXT 전용 ratio 자체를 낮춰 명목 노출을 제한한다.

---

## 14. 08:45~08:50 프리마켓 종료 정책

기존 제안의 “08:48까지 강제청산”은 방향은 맞지만, 전체 보유분 청산으로 해석하면 안 된다.

```yaml
nxt_premarket_closeout:
  "08:40:00":
    new_entry: "high_quality_scout_only"
    max_position_ratio: 0.10

  "08:45:00":
    new_entry: false
    cancel_unfilled_buy_orders: true
    no_pyramid: true

  "08:47:00":
    reduce_if:
      - spread_ticks_gte: 3
      - bid_depth_drop_pct_gte: 50
      - trade_gap_sec_gte: 8
      - price_below_micro_vwap: true

  "08:48:00":
    flatten_scalping_positions: true
    target_scope: "NXT intraday scalping entries only"
    but_do_not_cross_if:
      - spread_ticks_gte: 5
      - top5_bid_value_lt_order_notional_x: 3

  "08:49:30":
    cancel_all_unfilled_orders: true
```

정의:

```text
08:48 강제청산 대상:
  당일 NXT 스캘핑 진입분

08:48 강제청산 제외 또는 별도 판단:
  기존 보유분
  스윙 포지션
  장기 포지션
  유동성 부족으로 즉시 청산 시 손실이 과도한 잔량
```

---

## 15. 19:00~20:00 애프터마켓 종료 정책

19:00 이후는 신규 진입 시간이 아니라 청산·리스크 축소 시간으로 본다.

```yaml
nxt_after_late_policy:
  "19:00:00":
    allow_new_entry: false
    reduce_only: true
    cancel_unfilled_buy_orders: true

  "19:30:00":
    allow_new_entry: false
    flatten_scalping_positions: true
    no_new_scout: true

  "19:45:00":
    force_reduce_scalping_positions: true

  "19:55:00":
    flatten_all_scalping_positions: true
    cancel_all_unfilled_orders: true
```

예외적 scout를 허용해야 한다면 아래 조건을 모두 만족해야 한다.
단, 기본 운영값은 `allow_exceptional_scout: false`를 권장한다.

```python
def allow_nxt_after_late_exceptional_scout(ctx):
    if ctx.now < "19:00:00":
        return False

    return (
        ctx.confirmed_news_or_theme
        and ctx.ai_confidence >= 85
        and ctx.spread_ticks <= 1
        and ctx.trade_gap_sec <= 3
        and ctx.top5_bid_value >= ctx.order_notional * 12
        and ctx.top5_ask_value >= ctx.order_notional * 8
        and ctx.ttl_ms <= 700
        and ctx.position_ratio <= 0.05
        and not ctx.vi_imminent
    )
```

---

## 16. AI 라우팅 및 task_type

NXT는 정규장과 다른 프롬프트를 사용하는 것이 좋다.
`session` 필드 추가만으로는 부족할 수 있으므로 별도 task_type을 신설한다.

```json
{
  "task_type": "nxt_scalping_entry",
  "venue": "NXT",
  "session": "after_early",
  "strategy": "SCALPING",
  "pyramid_enabled": false,
  "hard_gate": "PASS",
  "nxt_vs_krx_close_pct": 1.2,
  "spread_ticks": 1,
  "trade_gap_sec": 2.1,
  "ofi_debounce_state": "CONFIRMED"
}
```

신설 task_type:

```text
nxt_scalping_entry
nxt_scalping_exit
nxt_panic_recovery_entry
nxt_premium_exit
```

AI 응답 스키마 예시:

```json
{
  "session": "after_early",
  "symbol_state": "WATCHING",
  "hard_gate": "PASS",
  "ai_action": "BUY",
  "final_action": "SCOUT_BUY",
  "confidence": 72,
  "position_size_ratio": 0.15,
  "max_chase_ticks": 1,
  "ttl_ms": 1200,
  "reason": [
    "spread_ok",
    "trade_flow_expanding",
    "micro_vwap_reclaim",
    "ofi_debounce_confirmed"
  ],
  "risk_flags": [
    "nxt_thin_liquidity"
  ]
}
```

---

## 17. 구현용 핵심 feature 목록

```python
NXT_FEATURES = {
    "venue": str,
    "session_state": str,
    "is_nxt_eligible": bool,

    "nxt_last": float,
    "nxt_bid1": float,
    "nxt_ask1": float,
    "nxt_mid": float,
    "nxt_micro_vwap": float,
    "price_above_nxt_micro_vwap": bool,

    "krx_close": float,
    "krx_reference_price": float,
    "nxt_vs_krx_close_pct": float,

    "spread_ticks": int,
    "spread_pct": float,
    "quote_age_ms": int,

    "trade_count_10s": int,
    "trade_count_60s": int,
    "trade_value_60s": int,
    "trade_gap_sec": float,
    "trade_intensity_60s_z": float,

    "top5_bid_value": int,
    "top5_ask_value": int,
    "impact_buy_price_pct": float,
    "impact_sell_price_pct": float,

    "depth_imbalance": float,
    "bid_replenishment_score": float,
    "ask_wall_score": float,

    "ofi_ewma": float,
    "ofi_z": float,
    "ofi_flip_rate": float,
    "ofi_flip_rate_high": bool,
    "ofi_debounce_state": str,

    "vi_status": str,
    "vi_imminent": bool,
    "distance_to_dynamic_vi_pct": float,
    "distance_to_static_vi_pct": float,
    "distance_to_upper_limit_pct": float,
    "distance_to_lower_limit_pct": float,

    "confirmed_news_or_theme": bool,
    "ai_decision": str,
    "ai_confidence": int,
    "ai_score": int,

    "symbol_daily_nxt_loss_pct": float,
    "order_notional": int,
    "position_ratio": float
}
```

---

## 18. KORStockScan 통합 포인트

### 18.1 전략 분기

```python
if strategy == "SCALPING" and venue == "NXT":
    params = NXT_SCALPING_PARAMS[session_state]
    task_type = resolve_nxt_task_type(ctx)
else:
    params = KRX_SCALPING_PARAMS[session_state]
```

### 18.2 MAX_POSITION_PCT

```yaml
max_position_pct:
  krx_scalping: 1.00
  nxt_premarket: 0.20
  nxt_after_early: 0.30
  nxt_after_selective: 0.20
  nxt_after_thin: 0.05
  nxt_after_reduce_only: 0.00
```

### 18.3 손실 한도

NXT 세션은 손실 발생 시 회복 기회가 정규장보다 적으므로 더 타이트하게 둔다.

```yaml
loss_limits:
  symbol_daily_nxt_loss_pct: 0.50
  session_daily_nxt_loss_pct: 1.00
  stop_trading_after_consecutive_losses: 2
  cooldown_after_loss_sec: 300
```

### 18.4 로그 필수 항목

```text
session_state
hard_gate_result
entry_score
ai_decision
final_action
spread_ticks
spread_pct
trade_gap_sec
trade_count_60s
top5_bid_value
top5_ask_value
impact_buy_price_pct
nxt_vs_krx_close_pct
ofi_debounce_state
vi_status
order_ttl_ms
fill_ratio
slippage_ticks
exit_reason
```

---

## 19. 리플레이 검증 시나리오

실전 적용 전 다음 시나리오를 리플레이로 검증한다.

```text
1. 08:00 직후 첫 체결 급등/급락 종목
2. 08:30 이후 KRX 동시호가 진입으로 NXT 호가가 얇아지는 종목
3. 08:45 이후 미체결 주문 취소 및 포지션 축소
4. 16:00 직후 종가 대비 프리미엄 형성 종목
5. 17:00 이후 체결 공백이 길어지는 종목
6. 18:30 이후 얇은 호가에서 1~2건 체결로 급등하는 종목
7. 19:00 이후 신규 진입 차단 검증
8. VI 근접 또는 VI 발동 종목
9. 패닉셀 후 RECOVERY_CONFIRMED 전환 종목
10. 보유 종목 NXT 프리미엄 익절 케이스
```

성과 평가는 단순 승률보다 아래 항목을 우선한다.

```text
평균 슬리피지
부분체결 후 손실률
체결 공백 중 진입 차단률
VI 근접 진입 차단률
08:45 이후 미체결 주문 제거율
19:00 이후 신규진입 차단 준수율
스프레드 확대 시 청산 성공률
```

---

## 20. 개발 우선순위

```text
P0 - 즉시 구현:
  NXT 세션 분류
  venue == NXT 분기
  KRX last 제거 / KRX close 유지
  공통 하드 게이트
  08:45 이후 신규 매수 차단
  19:00 이후 reduce-only
  주문 TTL 및 미체결 취소
  로그 필드 확장

P1 - 1차 전략 구현:
  NXT_AFTER_CLOSE_CONTINUATION
  NXT_PRE_GAP_CONTINUATION
  NXT_PRE_PULLBACK_RECLAIM
  NXT_AFTER_PREMIUM_EXIT

P2 - 안정화:
  OFI debounce 연동
  bid_replenishment_score
  impact_buy_price_pct 계산
  종목별 분위수 기반 체결 빈도 가드
  패닉셀 회복 scout

P3 - 고도화:
  NXT_VI_POLICY_VERSION feature flag
  세션별 threshold 자동 튜닝
  리플레이 기반 파라미터 보정
  실시간 뉴스/테마 확인 연동
```

---

## 21. 작업자 전달용 핵심 지시서

```markdown
# NXT 스캘핑 로직 보완 지시서

## 목적
기존 KRX 정규장 SCALPING 로직을 NXT 단독 세션에 단순 확장하지 않고, NXT 프리마켓/애프터마켓의 유동성, 호가 공백, KRX 기준가, VI 리스크를 반영한 별도 레짐으로 분리한다.

## 필수 수정사항

### 1. NXT 세션 분리
`strategy == "SCALPING" and venue == "NXT"` 조건에서 NXT 전용 파라미터 테이블을 사용한다.

세션은 아래로 구분한다.

- pre_discovery: 08:00~08:03
- pre_active: 08:03~08:30
- pre_auction_aware: 08:30~08:40
- pre_risk_off: 08:40~08:45
- pre_closeout: 08:45~08:50
- after_early: 16:00~17:00
- after_selective: 17:00~18:30
- after_thin: 18:30~19:00
- after_reduce_only: 19:00~19:30
- after_closeout: 19:30~20:00

### 2. 프리마켓 갭 필터 수정
전일 KRX 종가 대비 ±2% 고정 필터를 제거하고, 패턴별 갭 범위를 사용한다.

- normal_continuation: +0.3%~+4.0%
- pullback_reclaim: 초기 갭 +0.5%~+6.0%, 눌림 후 회복
- panic_recovery: -6.0%~-0.5%, RECOVERY_CONFIRMED일 때만 scout
- abs(gap) >= 10%는 신규 매수 차단 또는 청산 전용

### 3. KRX last 참조 수정
NXT 프리/애프터 체결 판단에서 KRX last를 실시간 체결 기준으로 사용하지 않는다.

단, 아래 기준값은 유지한다.

- KRX close
- KRX 기준가
- NXT vs KRX close premium
- 가격제한폭 거리
- 전일 종가 대비 변동률

### 4. NXT 공통 하드 게이트 추가
아래 조건 중 하나라도 위반하면 AI BUY여도 주문하지 않는다.

- stale quote
- spread_ticks 초과
- spread_pct 초과
- trade_gap_sec 초과
- trade_count_60s 부족
- top5 bid/ask depth 부족
- impact_buy_price_pct 초과
- VI_ACTIVE 또는 VI_IMMINENT
- 상하한가 근접
- 종목 단위 NXT 일일 손실 한도 초과

### 5. PYRAMID 제한
NXT 프리마켓은 PYRAMID 비활성화한다.
NXT after_early에서만 제한적으로 1회 추가 진입을 허용한다.
추가 진입은 반드시 미실현 이익 상태에서만 허용한다.

### 6. 08:48 강제청산 범위 명확화
08:48 강제청산은 당일 NXT 스캘핑 진입분에 한정한다.
기존 보유분 또는 스윙 포지션은 별도 exit policy로 처리한다.
유동성이 지나치게 부족한 경우 무리한 시장가성 청산을 금지한다.

### 7. 19:00 이후 신규진입 차단
19:00 이후는 기본적으로 reduce-only로 전환한다.
예외적 scout는 confirmed_news_or_theme, spread_ticks <= 1, trade_gap_sec <= 3, 충분한 top5 depth 조건을 모두 만족할 때만 허용한다.
기본 운영값은 예외적 scout도 비활성화한다.

### 8. AI task_type 분리
아래 task_type을 신설한다.

- nxt_scalping_entry
- nxt_scalping_exit
- nxt_panic_recovery_entry
- nxt_premium_exit

### 9. VI 정책 feature flag
NXT VI 제도 변경에 대비하여 `NXT_VI_POLICY_VERSION`을 둔다.

- pre_2026_09_14
- post_2026_09_14
```

---

## 22. 최종 운영 순서

```text
1단계:
  16:00~17:00 NXT_AFTER_EARLY만 제한적으로 실전 검증

2단계:
  08:03~08:30 PRE_ACTIVE scout 검증

3단계:
  17:00~18:30 AFTER_SELECTIVE 확장

4단계:
  08:30 이후, 18:30 이후는 충분한 리플레이 데이터 확보 후 확장

5단계:
  19:00 이후 신규진입은 원칙적으로 비활성화 유지
```

---

## 23. 최종 한 줄 요약

```text
NXT 스캘핑은 “빠른 진입”보다 “진입 전 차단, 체결 후 탈출 가능성, 세션 종료 리스크 관리”가 우선이다.
```

---

## 참고 자료

1. Nextrade 공식 Market Overview — Extended trading hours, pre-market 08:00~08:50, after-market 안내
   https://nextrade.co.kr/en/marketOverview/content.do

2. FSC Press Release — ATS/Nextrade 제도, pre-market/after-market, 가격제한폭 ±30% KRX closing price, 통합 시장관리
   https://www.fsc.go.kr/eng/pr010101/83967

3. KCMI — NXT offers pre-market 08:00~08:50 and after-market 15:40~20:00; extended-hour liquidity analysis
   https://www.kcmi.re.kr/en/publications/pub_detail_view?cno=6573&syear=2025&zcd=002001017&zno=1857

4. 언론 보도 — NXT VI 제도 개선 추진, 정적 VI 및 단일가 전환 관련 보도
   https://en.sedaily.com/finance/2026/04/22/samsung-sdi-surges-27-percent-in-pre-market-on-nxt
