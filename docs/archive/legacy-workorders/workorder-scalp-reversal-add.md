# 작업지시서: 스캘핑 역전 확인 추가매수 (reversal_add)

> 작성일: 2026-04-15  
> 우선순위: 중  
> 실행 시점: POSTCLOSE 또는 다음 장 전 배포  
> 토글: `REVERSAL_ADD_ENABLED` (기본값 `False`, Phase 1 shadow 우선)  
> 대체 범위: `workorder-scalp-stagnation-avgdown.md` 설계를 본 지시서로 대체한다.

---

## 1. 배경 및 목적

스캘핑 보유 중 소폭 손실(-0.45% ~ -0.10%) 정체 구간에서 AI 회복 + 저점 미갱신 + 수급 재개 신호가
동시에 확인될 때 1회 한정으로 추가매수(reversal_add)를 실행한다.

**본 로직의 정의**:
> 하락 중 무조건 물타기가 아닌, 정체 구간에서 저점 미갱신 + AI 회복 + 수급 재개가 확인된 뒤
> 1회 한정으로 실행하는 **역전 확인 추가매수**다.

**기존 stagnation 설계 대비 차이점**:

| 항목 | 폐기된 stagnation 설계 | 본 reversal_add 설계 |
|---|---|---|
| AI 조건 | score ≥ 36 (수준만) | bottom 대비 +15pt 회복 또는 2연속 상승 (방향성) |
| 수급 조건 | 없음 | buy_pressure, tick_accel, large_sell, vwap_bp |
| 저점 확인 | 없음 | reversal_add_profit_floor 대비 미갱신 필수 |
| 고착 저점 차단 | 없음 | `44→41→39→40→40` 패턴 명시적 차단 |
| 실행 후 감시 | 없음 | POST_ADD_EVAL 25초 집중 감시 + 실패 즉시 청산 |

---

## 2. 상태 정의

```
[진입 없음] → STAGNATION → REVERSAL_CANDIDATE → ADD_ARMED → 실행 → POST_ADD_EVAL → 종료
```

| 상태 | 의미 | stock 키 |
|---|---|---|
| `STAGNATION` | 손실 정체 구간 진입, 역전 미확인 | `reversal_add_state = "STAGNATION"` |
| `REVERSAL_CANDIDATE` | 저점 미갱신 + AI 회복 + 수급 재개 조건 충족 | `reversal_add_state = "REVERSAL_CANDIDATE"` |
| `ADD_ARMED` | 최종 실행 직전 대기 (틱 단위) | `reversal_add_state = "ADD_ARMED"` |
| `POST_ADD_EVAL` | 추가매수 후 25초 집중 감시 | `reversal_add_state = "POST_ADD_EVAL"` |
| `DONE` | 소진 또는 비대상 종료 | `reversal_add_used = True` |

---

## 3. 실행 조건 (ALL 충족 필요)

### 3-1. 가격/수익률 조건

| 조건 | 기준값 | 상수 |
|---|---|---|
| 현재 수익률 범위 | `REVERSAL_ADD_PNL_MIN(-0.45%) ≤ profit_rate ≤ REVERSAL_ADD_PNL_MAX(-0.10%)` | 필수 |
| 저점 미갱신 | `profit_rate ≥ reversal_add_profit_floor - 0.05%p` | 필수 |
| 박스 폭 | 최근 6틱 수익률 범위 ≤ 0.20%p | 권장 |

`reversal_add_profit_floor`: STAGNATION 구간 진입 후 관측된 최저 수익률.  
현재 profit이 이 값보다 더 하락하면 저점 갱신으로 판단 → 즉시 상태 리셋.

### 3-2. AI 회복 조건 (둘 중 하나 충족)

| 조건 | 기준값 | 상수 |
|---|---|---|
| 바닥 대비 회복 | `current_ai_score ≥ reversal_add_ai_bottom + REVERSAL_ADD_MIN_AI_RECOVERY_DELTA(15)` | OR |
| 연속 상승 | 최근 2틱 AI 점수 모두 이전 틱보다 상승 | OR |

`reversal_add_ai_bottom`: STAGNATION 진입 후 최저 AI 점수. AI 감시 사이클마다 갱신.

**차단 패턴**: AI가 저점에 **고착**된 경우 (최근 4틱 표준편차 ≤ 2, 점수 < 45) → REVERSAL_CANDIDATE 진입 차단.

### 3-3. 수급 재개 조건 (4개 중 3개 충족)

| 피처 | 조건 | 출처 |
|---|---|---|
| `buy_pressure_10t` | ≥ 55% | recent_ticks 계산 또는 feature_map |
| `tick_acceleration_ratio` | ≥ 0.95 | `_extract_scalping_features()` |
| `large_sell_print_detected` | `== False` | `_extract_scalping_features()` |
| `curr_vs_micro_vwap_bp` | ≥ -5bp | `_extract_scalping_features()` |

`_extract_scalping_features()`가 없는 엔진(표준 ai_engine)의 경우:  
`buy_pressure_10t`만 필수 확인, 나머지 조건 skip → **2/4 충족으로 완화**.

### 3-4. 시간/환경 조건

| 조건 | 기준 |
|---|---|
| 최소 보유 시간 | 진입 후 ≥ 20초 (`REVERSAL_ADD_MIN_HOLD_SEC`) |
| 최대 보유 시간 | ≤ 120초 (`REVERSAL_ADD_MAX_HOLD_SEC`) |
| 허용 시간대 | 09:00~14:30 (`REVERSAL_ADD_SESSION_CUTOFF = "14:30"`) |
| AI 스코어 최소 | 실행 직전 `current_ai_score ≥ REVERSAL_ADD_MIN_AI_SCORE(60)` |

---

## 4. 차단 조건 (하나라도 해당 시 차단)

| 조건 | 이유 |
|---|---|
| `profit_rate < REVERSAL_ADD_PNL_MIN(-0.45%)` | 손실 심화, 정체 아님 |
| `profit_rate > 0` | 이미 수익권, 불필요 |
| `reversal_add_profit_floor` 대비 저점 갱신 | 하락 지속 중 |
| AI 고착 저점 (`std ≤ 2, score < 45, 최근 4틱`) | 방향성 없음 |
| `large_sell_print_detected == True` | 매도 압력 진행 중 |
| `reversal_add_used == True` | 이미 1회 소진 |
| `ai_low_score_hits > 0` | 하방카운트 시작됨 |
| `is_buy_side_paused()` | 매수 일시정지 |
| `14:30` 이후 | 장 마감 근접 |
| `late_entry` 플래그 존재 | 후발 진입 리스크 |
| `SCALP_PARTIAL_FILL_CANARY_ENABLED == True` 이고 partial fill 이력 있음 | 체결 리스크 |

---

## 5. POST_ADD_EVAL (실행 후 25초 집중 감시)

추가매수 체결 확인 후 `reversal_add_executed_at` 기준 **25초간** 기존 HOLDING보다 엄격한 조건으로 감시.

### 실패 조건 (하나라도 해당 시 즉시 청산 신호)

| 조건 | 기준 |
|---|---|
| AI 점수 재하락 | `current_ai_score < 55` |
| 수익률 재침하 | `profit_rate < reversal_add_profit_floor - 0.05%p` |
| 대형 매도 감지 | `large_sell_print_detected == True` |
| tick_acceleration 재하락 | `tick_acceleration_ratio < 0.90` |
| 25초 경과 후 평단 미회복 | 선택적 (운영자 판단) |

실패 청산 시:
- `exit_rule = "reversal_add_post_eval_fail"`
- `sell_reason_type = "LOSS"`

### 성공 조건 (모두 충족 시 일반 HOLDING으로 복귀)

- `current_ai_score ≥ 60` 유지
- `profit_rate > reversal_add_entry_avg_price` (평단 회복)
- `large_sell_print_detected == False`
- 25초 경과

---

## 6. 추가매수 실행 규칙

| 항목 | 값 |
|---|---|
| 포지션당 허용 횟수 | **1회** (`reversal_add_used` 플래그) |
| 수량 비율 | 기존 보유수량의 **33%** (`REVERSAL_ADD_SIZE_RATIO = 0.33`) |
| 가격 | 시장가 (SCALPING 전략: `order_type_code = "00"`) |
| `avg_down_count` 공유 | 체결 후 `avg_down_count += 1` (기존 receipt 처리 경로) |

---

## 7. 구현 상세

### 7-1. 상수 추가 (`src/utils/constants.py`)

```python
# ── reversal_add ────────────────────────────────────────
REVERSAL_ADD_ENABLED: bool = False             # 역전 확인 추가매수 토글
REVERSAL_ADD_PNL_MIN: float = -0.45            # 허용 손실 하한 (%)
REVERSAL_ADD_PNL_MAX: float = -0.10            # 허용 손실 상한 (%)
REVERSAL_ADD_MIN_HOLD_SEC: int = 20            # 최소 보유시간(초)
REVERSAL_ADD_MAX_HOLD_SEC: int = 120           # 최대 보유시간(초)
REVERSAL_ADD_MIN_AI_SCORE: int = 60            # 실행 직전 최소 AI 점수
REVERSAL_ADD_MIN_AI_RECOVERY_DELTA: int = 15   # AI bottom 대비 최소 회복폭
REVERSAL_ADD_MIN_BUY_PRESSURE: float = 55.0    # 최소 매수 압도율(%)
REVERSAL_ADD_MIN_TICK_ACCEL: float = 0.95      # 최소 틱 가속도 비율
REVERSAL_ADD_VWAP_BP_MIN: float = -5.0         # 최소 Micro-VWAP 대비 (bp)
REVERSAL_ADD_SIZE_RATIO: float = 0.33          # 추가매수 수량 비율 (기존 보유 대비)
REVERSAL_ADD_POST_EVAL_SEC: int = 25           # POST_ADD_EVAL 감시 시간(초)
REVERSAL_ADD_SESSION_CUTOFF: str = "14:30"     # 허용 시간대 상한
REVERSAL_ADD_BOX_RANGE_MAX_PCT: float = 0.20   # 박스 폭 허용 최대치 (%p)
REVERSAL_ADD_STAGNATION_LOW_FLOOR_MARGIN: float = 0.05  # 저점 미갱신 허용 마진 (%p)
```

### 7-2. stock 딕셔너리 신규 키

| 키 | 타입 | 의미 | 초기값 |
|---|---|---|---|
| `reversal_add_state` | `str` | 현재 상태 (`""` / `"STAGNATION"` / `"REVERSAL_CANDIDATE"` / `"ADD_ARMED"` / `"POST_ADD_EVAL"`) | `""` |
| `reversal_add_used` | `bool` | 1회 소진 플래그 | `False` |
| `reversal_add_profit_floor` | `float` | STAGNATION 진입 후 최저 수익률 | `0.0` |
| `reversal_add_ai_bottom` | `int` | STAGNATION 진입 후 최저 AI 점수 | `100` |
| `reversal_add_ai_history` | `list[int]` | 최근 4틱 AI 점수 (고착 판단용) | `[]` |
| `reversal_add_executed_at` | `float` | 추가매수 실행 timestamp | `0.0` |
| `reversal_add_entry_avg_price` | `float` | 추가매수 후 예상 평단가 | `0.0` |
| `last_reversal_features` | `dict` | 마지막 수급 피처 스냅샷 | `{}` |

DB 저장 불필요 (메모리 런타임).

### 7-3. `sniper_state_handlers.py` 수정 — 피처 저장 (AI 감시 사이클)

**위치**: L3122~3127 (`stock['ai_low_score_loss_hits']` 저장 직후)

```python
# 수급 피처 저장 (reversal_add 조건 평가용)
if getattr(TRADING_RULES, 'REVERSAL_ADD_ENABLED', False):
    if hasattr(ai_engine, '_extract_scalping_features') and recent_ticks:
        try:
            feat = ai_engine._extract_scalping_features(ws_data, recent_ticks, recent_candles)
            stock['last_reversal_features'] = {
                'buy_pressure_10t': feat.get('buy_pressure_10t', 50.0),
                'tick_acceleration_ratio': feat.get('tick_acceleration_ratio', 0.0),
                'large_sell_print_detected': feat.get('large_sell_print_detected', False),
                'curr_vs_micro_vwap_bp': feat.get('curr_vs_micro_vwap_bp', 0.0),
            }
        except Exception:
            pass

    # AI bottom/history 갱신 (STAGNATION 구간에서만)
    if stock.get('reversal_add_state') in ('STAGNATION', 'REVERSAL_CANDIDATE'):
        ai_hist = list(stock.get('reversal_add_ai_history', []))
        ai_hist.append(current_ai_score)
        stock['reversal_add_ai_history'] = ai_hist[-4:]
        stock['reversal_add_ai_bottom'] = min(
            int(stock.get('reversal_add_ai_bottom', 100)),
            current_ai_score
        )
        stock['reversal_add_profit_floor'] = min(
            float(stock.get('reversal_add_profit_floor', 0.0)),
            profit_rate
        )
```

### 7-4. `sniper_scale_in.py` 수정 — 신규 평가 함수

```python
def evaluate_scalping_reversal_add(stock, profit_rate, current_ai_score, held_sec):
    """
    역전 확인 추가매수(reversal_add) 평가.
    저점 미갱신 + AI 회복 + 수급 재개가 동시 확인될 때 1회 실행.
    """
    result = _base_result()

    if not getattr(TRADING_RULES, 'REVERSAL_ADD_ENABLED', False):
        result["reason"] = "reversal_add_disabled"
        return result

    if stock.get('reversal_add_used'):
        result["reason"] = "reversal_add_used"
        return result

    pnl_min = float(getattr(TRADING_RULES, 'REVERSAL_ADD_PNL_MIN', -0.45))
    pnl_max = float(getattr(TRADING_RULES, 'REVERSAL_ADD_PNL_MAX', -0.10))
    if not (pnl_min <= profit_rate <= pnl_max):
        result["reason"] = f"pnl_out_of_range({profit_rate:.2f})"
        return result

    min_hold = int(getattr(TRADING_RULES, 'REVERSAL_ADD_MIN_HOLD_SEC', 20))
    max_hold = int(getattr(TRADING_RULES, 'REVERSAL_ADD_MAX_HOLD_SEC', 120))
    if not (min_hold <= held_sec <= max_hold):
        result["reason"] = f"hold_sec_out_of_range({held_sec}s)"
        return result

    # 저점 미갱신 확인
    floor = float(stock.get('reversal_add_profit_floor', 0.0))
    margin = float(getattr(TRADING_RULES, 'REVERSAL_ADD_STAGNATION_LOW_FLOOR_MARGIN', 0.05))
    if profit_rate < floor - margin:
        result["reason"] = "low_broken"
        return result

    # AI 점수 최소 기준
    min_ai = int(getattr(TRADING_RULES, 'REVERSAL_ADD_MIN_AI_SCORE', 60))
    if current_ai_score < min_ai:
        result["reason"] = f"ai_score_too_low({current_ai_score})"
        return result

    # AI 회복 방향성 (바닥 대비 +15pt OR 2연속 상승)
    ai_bottom = int(stock.get('reversal_add_ai_bottom', 100))
    recovery_delta = int(getattr(TRADING_RULES, 'REVERSAL_ADD_MIN_AI_RECOVERY_DELTA', 15))
    ai_hist = list(stock.get('reversal_add_ai_history', []))
    recovering_delta = (current_ai_score >= ai_bottom + recovery_delta)
    recovering_consec = (len(ai_hist) >= 2 and ai_hist[-1] > ai_hist[-2] and current_ai_score > ai_hist[-1])
    if not (recovering_delta or recovering_consec):
        result["reason"] = "ai_not_recovering"
        return result

    # AI 고착 저점 차단
    if len(ai_hist) >= 4:
        import statistics
        try:
            std = statistics.stdev(ai_hist)
            avg = sum(ai_hist) / len(ai_hist)
            if std <= 2 and avg < 45:
                result["reason"] = "ai_stuck_at_bottom"
                return result
        except Exception:
            pass

    # 수급 재개 조건 (4개 중 3개, 피처 없으면 1/1 완화)
    feat = stock.get('last_reversal_features', {})
    if feat:
        checks = [
            feat.get('buy_pressure_10t', 0) >= getattr(TRADING_RULES, 'REVERSAL_ADD_MIN_BUY_PRESSURE', 55),
            feat.get('tick_acceleration_ratio', 0) >= getattr(TRADING_RULES, 'REVERSAL_ADD_MIN_TICK_ACCEL', 0.95),
            not feat.get('large_sell_print_detected', True),
            feat.get('curr_vs_micro_vwap_bp', -999) >= getattr(TRADING_RULES, 'REVERSAL_ADD_VWAP_BP_MIN', -5.0),
        ]
        if sum(checks) < 3:
            result["reason"] = f"supply_conditions_not_met({sum(checks)}/4)"
            return result
    else:
        # 피처 미사용 엔진: buy_pressure만 확인
        bp = float(stock.get('last_reversal_features', {}).get('buy_pressure_10t', 50.0))
        if bp < getattr(TRADING_RULES, 'REVERSAL_ADD_MIN_BUY_PRESSURE', 55):
            result["reason"] = "buy_pressure_not_met(no_features)"
            return result

    result["should_add"] = True
    result["add_type"] = "AVG_DOWN"
    result["reason"] = "reversal_add_ok"
    return result
```

### 7-5. `sniper_state_handlers.py` 수정 — `_evaluate_add_position()` 연동

**위치**: L4006 SCALPING 분기 내, `avg_down`과 `pyramid` 평가 이후

```python
avg_down = evaluate_scalping_avg_down(stock, profit_rate)
pyramid = evaluate_scalping_pyramid(stock, profit_rate, peak_profit, is_new_high)

# reversal_add: 가격낙폭/불타기 모두 미트리거인 경우에만 검토
if not avg_down.get("should_add") and not pyramid.get("should_add"):
    reversal = evaluate_scalping_reversal_add(
        stock, profit_rate, current_ai_score, held_sec
    )
    if reversal.get("should_add"):
        avg_down = reversal
```

추가매수 체결 성공 후 `reversal_add_used = True` 설정:

```python
# _process_scale_in_action 호출부 이후
if add_result and action.get("reason") == "reversal_add_ok":
    stock['reversal_add_used'] = True
    stock['reversal_add_state'] = "POST_ADD_EVAL"
    stock['reversal_add_executed_at'] = time.time()
```

### 7-6. POST_ADD_EVAL 처리

**위치**: 기존 HOLDING 루프 내, AI 감시 사이클 직후

```python
# POST_ADD_EVAL 집중 감시
if stock.get('reversal_add_state') == 'POST_ADD_EVAL':
    executed_at = float(stock.get('reversal_add_executed_at', 0))
    eval_sec = int(getattr(TRADING_RULES, 'REVERSAL_ADD_POST_EVAL_SEC', 25))
    feat = stock.get('last_reversal_features', {})
    elapsed = time.time() - executed_at

    post_fail = (
        current_ai_score < 55
        or profit_rate < float(stock.get('reversal_add_profit_floor', -1)) - 0.05
        or feat.get('large_sell_print_detected', False)
        or feat.get('tick_acceleration_ratio', 1.0) < 0.90
    )

    if post_fail and elapsed < eval_sec:
        is_sell_signal = True
        sell_reason_type = "LOSS"
        reason = (
            f"🚨 reversal_add POST_EVAL 실패 "
            f"(AI:{current_ai_score:.0f}, profit:{profit_rate:.2f}%, "
            f"elapsed:{elapsed:.0f}s)"
        )
        exit_rule = "reversal_add_post_eval_fail"
    elif elapsed >= eval_sec:
        stock['reversal_add_state'] = ""  # 일반 HOLDING 복귀
```

### 7-7. STAGNATION 상태 진입/리셋

**위치**: AI 감시 사이클 내 피처 저장 직후

```python
# STAGNATION 진입 판단 (reversal_add_state 미설정 시)
if (getattr(TRADING_RULES, 'REVERSAL_ADD_ENABLED', False)
        and not stock.get('reversal_add_used')
        and not stock.get('reversal_add_state')):
    pnl_min = float(getattr(TRADING_RULES, 'REVERSAL_ADD_PNL_MIN', -0.45))
    pnl_max = float(getattr(TRADING_RULES, 'REVERSAL_ADD_PNL_MAX', -0.10))
    if pnl_min <= profit_rate <= pnl_max and ai_low_score_hits == 0:
        stock['reversal_add_state'] = 'STAGNATION'
        stock['reversal_add_profit_floor'] = profit_rate
        stock['reversal_add_ai_bottom'] = current_ai_score
        stock['reversal_add_ai_history'] = [current_ai_score]

# STAGNATION 리셋 조건
elif stock.get('reversal_add_state') == 'STAGNATION':
    pnl_min = float(getattr(TRADING_RULES, 'REVERSAL_ADD_PNL_MIN', -0.45))
    pnl_max = float(getattr(TRADING_RULES, 'REVERSAL_ADD_PNL_MAX', -0.10))
    if profit_rate < pnl_min or profit_rate > 0 or ai_low_score_hits > 0:
        stock['reversal_add_state'] = ''
        stock['reversal_add_profit_floor'] = 0.0
        stock['reversal_add_ai_bottom'] = 100
        stock['reversal_add_ai_history'] = []
```

---

## 8. 수정 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `src/utils/constants.py` | 상수 14개 추가 |
| `src/engine/sniper_scale_in.py` | `evaluate_scalping_reversal_add()` 신규 함수 추가 |
| `src/engine/sniper_state_handlers.py` | (1) AI 감시 사이클 내 피처 저장 + STAGNATION 상태 관리, (2) `_evaluate_add_position()` reversal 연동, (3) add 성공 후 플래그 설정, (4) POST_ADD_EVAL 집중 감시, (5) import에 `evaluate_scalping_reversal_add` 추가 |
| `src/tests/test_sniper_scale_in.py` | TC 추가 (아래 9항) |

`workorder-scalp-stagnation-avgdown.md` 설계는 **폐기**한다.

---

## 9. 테스트 케이스

### TC-1: 토글 OFF → 미트리거
### TC-2: PnL 범위 이탈 → 미트리거
### TC-3: AI 고착 저점 (`std ≤ 2, avg < 45`) → 차단
### TC-4: AI 회복 없음 (바닥 대비 +14pt) → 차단
### TC-5: 수급 조건 2/4 충족 → 차단
### TC-6: 정상 조건 모두 충족 → 트리거, `reversal_add_used = True`
### TC-7: POST_ADD_EVAL 내 AI 재하락 → 즉시 청산
### TC-8: POST_ADD_EVAL 25초 경과 + 성공 조건 → 일반 HOLDING 복귀
### TC-9: reversal_add_used = True → 재트리거 없음
### TC-10: _extract_scalping_features 없는 엔진 → buy_pressure만으로 판단

---

## 10. 카나리 배포 계획

### Phase 1 — Shadow (실행 없이 로그만)
```
REVERSAL_ADD_ENABLED = False
→ evaluate_scalping_reversal_add() 호출하되 should_add 무시
→ "reversal_add_candidate" 로그만 기록
→ 후보 발생 빈도, 실제 역전 성공률 확인
```

### Phase 2 — Limited Canary
```
REVERSAL_ADD_ENABLED = True
REVERSAL_ADD_SIZE_RATIO = 0.25  (33% → 25% 축소)
→ 하루 최대 N건 제한 (운영자 판단)
→ POST_ADD_EVAL 실패율 모니터링
```

### Phase 3 — Full Deploy
```
REVERSAL_ADD_SIZE_RATIO = 0.33
→ 성공률/실패율/평단 회복률 기준 파라미터 조정
```

---

## 11. 관측 로그 항목 (필수)

```
reversal_add_candidate       # REVERSAL_CANDIDATE 진입 시
reversal_add_armed           # ADD_ARMED 진입 시
reversal_add_executed        # 추가매수 실행 시
reversal_add_blocked_reason  # 차단 시 reason 코드
reversal_add_post_eval_fail  # POST_EVAL 실패 청산
ai_recovery_delta            # AI bottom 대비 회복폭
holding_box_range_pct        # 박스 폭 (%p)
buy_pressure_10t_at_add      # 실행 시점 매수압
large_sell_print_at_add      # 실행 시점 대형매도 여부
```

---

## 12. 확정된 파라미터

| 항목 | 값 | 확정 근거 |
|---|---|---|
| 포지션당 최대 사용 횟수 | 1회 | 오퍼레이터 확인 (2026-04-15) |
| 정체 + AI카운트 기반 동시 허용 (최대 2회 물타기) | 허용 | 오퍼레이터 확인 (2026-04-15) |
| stagnation 설계 대체 | reversal_add로 대체 | 본 지시서 |
