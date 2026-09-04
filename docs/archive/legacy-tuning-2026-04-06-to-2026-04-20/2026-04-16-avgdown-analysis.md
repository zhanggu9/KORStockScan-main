# 2026-04-16 스캘핑 물타기 배제 구조 및 실적 분석

작성일: 2026-04-16  
분석 범위: 당일 완료 거래 9건 중 손실 6건

---

## 1. 현재 물타기 파라미터 상태

```
SCALPING_ENABLE_AVG_DOWN      = False   ← 일반 물타기 OFF
SCALP_AI_EXIT_AVGDOWN_ENABLED = False   ← 하방카운트 3회 도달 시 물타기 OFF
REVERSAL_ADD_ENABLED          = False   ← reversal_add OFF
ENABLE_SCALE_IN               = True    ← 공통 게이트는 열려 있음
```

물타기 관련 3개 스위치가 모두 비활성화된 상태로 운용 중.

---

## 2. 물타기가 완전 배제되는 조건 전체 맵

### 레이어 1 — 공통 게이트 (`_check_scale_in_allowed`)

| 차단 reason | 조건 |
|-------------|------|
| `scale_in_disabled` | `ENABLE_SCALE_IN = False` |
| `scalping_scale_in_disabled` | `SCALPING_ENABLE_AVG_DOWN=False` AND `SCALPING_MAX_PYRAMID_COUNT=0` 동시 |
| `scale_in_locked` | `stock['scale_in_locked'] = True` (주문번호 미확보·보호선 재설정 실패 등) |
| `buy_side_paused` | 매수 일시정지 플래그 ON |
| `not_holding` | status ≠ `HOLDING` |
| `sell_ordered` | status = `SELL_ORDERED` |
| `position_at_cap` | 현재 보유금액 ≥ `MAX_POSITION_PCT × 예수금 × 0.98` |
| `pending_add_order` | 미체결 추가매수 주문 존재 |
| `scale_in_cooldown` | 마지막 추가매수 후 `SCALE_IN_COOLDOWN_SEC`(기본 180s) 미경과 |
| `add_judgment_locked` | 직전 판단 후 `ADD_JUDGMENT_LOCK_SEC`(기본 20s) 미경과 |
| `near_market_close` | 장 마감 5분 전 이후 |
| `scalping_cutoff` | `SCALPING_NEW_BUY_CUTOFF`(기본 15:00) 이후 |
| `history_table_required` | `SCALE_IN_REQUIRE_HISTORY_TABLE = True` |

### 레이어 2 — `evaluate_scalping_avg_down()` 자체 조건

| 차단 reason | 조건 |
|-------------|------|
| `avg_down_disabled` | `SCALPING_ENABLE_AVG_DOWN = False` |
| `avg_down_count_limit` | `avg_down_count ≥ SCALPING_MAX_AVG_DOWN_COUNT` |
| `drop_range_not_met` | 수익률 ∉ `[MIN_DROP_PCT(-3%), MAX_DROP_PCT(-6%)]` |
| `held_too_long` | 보유시간 > `SCALP_TIME_LIMIT_MIN`(기본 60분) |

### 레이어 3 — `scale_in_locked` 세워지는 시점

물타기 주문 처리 중 아래 상황 발생 시 영구 잠금 (재시작 전까지 해제 불가):

1. **보호선 재설정 실패** — 추가매수 체결 후 preset 손절/익절 주문 재발행 실패
2. **주문번호 없이 미체결** — 추가매수 주문 발행 후 ordno 미확보
3. **KIWOOM 토큰/코드 없음** — 취소 API 호출 불가 상태
4. **취소 응답 불확실** — 응답에 `주문없음/취소가능수량/체결/원주문` 키워드 포함
5. **DB 복구 중 ordno 없음** — 재시작 후 동기화 과정에서 ordno 확보 실패

### 레이어 4 — 1회 소진 후 영구 차단

| 물타기 종류 | 플래그 | 조건 |
|------------|--------|------|
| `reversal_add` | `reversal_add_used = True` | 1회 실행 후 영구 차단 |
| `scalp_ai_exit_avgdown` | `scalp_ai_exit_avgdown_done = True` | 하방카운트 3회 도달 시 1회만 허용 |
| `reversal_add` 진입 | `ai_low_score_hits > 0` | 하방카운트 발동 중 STAGNATION 진입 자체 불가 |

---

## 3. 오늘 손실 종목 물타기 효과 분석

### 3.1 손실 6건 개요

| 종목 | 손실률 | 손실(원) | 체결수량 | 보유시간 | peak수익 | 청산규칙 |
|------|--------|----------|----------|----------|----------|----------|
| 지투파워(388050) | -1.56% | -20,646 | 84주 | 56초 | **-0.10%** | scalp_soft_stop_pct |
| 티에스이(131290) | -0.63% | -943 | **1주** | 168초 | -0.23% | scalp_preset_hard_stop_pct |
| 한화오션(042660) | -0.62% | -8,211 | **10주** | 40분 | **+0.21%** | scalp_preset_hard_stop_pct |
| 이마트(139480) 1차 | -0.62% | -636 | **1주** | 26분 | +0.16% | scalp_preset_hard_stop_pct |
| 이마트(139480) 2차 | -0.71% | -736 | **1주** | 17분 | +0.06% | scalp_preset_hard_stop_pct |
| 덕산하이메탈(077360) | -1.33% | -193 | **1주** | 70초 | +0.25% | scalp_soft_stop_pct |

**총 손실: -31,365원**

---

### 3.2 종목별 물타기 효과 판정

#### 지투파워(388050) — ❌ 물타기 무의미, 오히려 위험

- SCANNER 포지션, fallback 진입 직후 56초 만에 -1.56%
- peak 자체가 -0.10%로 단 한 번도 평단 이상 회복 없음
- AI 점수: 86 → 75 → 65 → 59 → 56점으로 일방 하락
- 손절 직전 `loss_fallback_probe` 발동했으나 `gate_reason: add_judgment_locked`, `min_ai: 65` (현재 58점 미달)로 차단
- **판정**: 방향성이 완전히 하락 일방향. 물타기 시 손실 확대.

#### 티에스이(131290) — ❌ 물타기 효과 없음 (포지션 부족)

- 요청 8주 → **1주만 체결** (PARTIAL_FILL)
- `template_qty = int(1 × 0.50) = 0` → 물타기 수량 계산 자체 불가
- peak도 -0.23%로 회복 없이 preset 손절선(-0.70%) 도달
- **판정**: 부분체결 1주 포지션에서 물타기 무의미.

#### 한화오션(042660) — ✅ 물타기 효과 있었을 유일한 케이스

- 10주 전량 체결, 40분 보유, peak **+0.21%** 달성 후 하락 손절
- 보유 10~20분 시점에 -0.3%~-0.4% 구간 통과 → reversal_add 조건 범위 내

**물타기 시뮬레이션 (reversal_add 기준):**

```
실제:
  매수 131,420원 × 10주
  매도 130,900원
  수익률: -0.62% | 손실: -8,211원

물타기 가정 (-0.35% 구간, 131,000원에서 5주 추가):
  평단: (131,420×10 + 131,000×5) / 15 = 131,280원
  최종 매도 130,900원
  수익률: -0.29%  →  손실: 약 -4,200원

손실 개선: -8,211원 → -4,200원 (약 49% 감소)
```

- REVERSAL_ADD_PNL_MIN=-0.45 ~ MAX=-0.10 범위에 해당
- 보유시간 40분이나 초반 10~20분 시점 적용 시 REVERSAL_ADD_MAX_HOLD_SEC(120초) 초과 → 현재 파라미터로는 차단됨
- `SCALP_TIME_LIMIT_MIN=60`이므로 일반 avg_down 범위(-3%~-6%)엔 전혀 진입 못 함

#### 이마트(139480) 1차·2차 — ❌ 물타기 효과 없음 (포지션 부족)

- 요청 9~13주 → **각 1주만 체결**
- 티에스이와 동일하게 `template_qty = 0`
- **판정**: 진입 부분체결이 근본 원인.

#### 덕산하이메탈(077360) — ❌ 물타기 효과 없음 (AI 급락)

- 70초 내 AI 62 → 44 → 33 → 31 → 43 → 37점으로 급락
- -0.02%에서 시작해 70초 만에 -1.53% 도달 (급격한 단방향 낙폭)
- `ai_low_score_hits`가 하방카운트 조건(hold≥180s, pnl≤-0.7%, ai≤35) 중 hold_sec 미달로 카운트 자체 미축적
- peak +0.25%가 있었으나 10초 내 반전
- **판정**: 1주 체결 + AI 신뢰도 붕괴. 물타기 시도해도 손실 확대.

---

## 4. 근본 원인 분석

### 4.1 물타기 효과가 제한되는 실질 원인

오늘 손실 6건 중 5건의 공통 문제는 물타기 비활성화가 아니라 **진입 부분체결**:

```
티에스이:   요청 8주  → 체결 1주  (체결률 12.5%)
이마트 1차: 요청 13주 → 체결 1주  (체결률  7.7%)
이마트 2차: 요청 9주  → 체결 1주  (체결률 11.1%)
덕산하이메탈: 요청 91주 → 체결 1주  (체결률  1.1%)
```

`buy_qty=1`이면 `calc_scale_in_qty()`에서:
```python
template_qty = int(1 × 0.50) = 0  →  물타기 수량 0, 실행 불가
```

물타기 활성화 전에 **진입 체결률 개선**이 선행되어야 실질 효과 발생.

### 4.2 물타기가 실효성 있는 조건

오늘 데이터 기준, 아래 조건을 동시 충족할 때만 물타기가 의미 있음:

1. `buy_qty >= 5` (평단 희석 효과가 있을 최소 수량)
2. peak > 0% (한 번이라도 양전 경험 → 회복 가능성 존재)
3. AI 점수가 급락하지 않음 (40점 이상 유지)
4. 낙폭이 완만 (-0.1% ~ -0.5% 구간)

오늘 이 조건을 충족한 종목: **한화오션 1건뿐**.

---

## 5. 보정 방안

### 5.1 즉시 적용 가능 — reversal_add 활성화

가장 보수적이고 조건이 엄격한 물타기. 현재 파라미터가 적절하게 설정되어 있음.

```python
REVERSAL_ADD_ENABLED = True
```

단, 한화오션 케이스에서 보유 10~20분 시점은 `REVERSAL_ADD_MAX_HOLD_SEC=120초`를 초과.  
실제 스캘핑 초반 구간을 커버하려면:

```python
REVERSAL_ADD_MAX_HOLD_SEC = 300   # 120초 → 5분으로 확장 검토
```

### 5.2 단기 검토 — SCANNER 포지션 손절 기준 강화

지투파워(-1.56%), 덕산하이메탈(-1.33%)은 SCANNER 포지션으로 진입 직후 급락.  
소프트손절 기준(-1.5%)이 너무 넓어 손실이 과대.

```python
# SCANNER 포지션 전용 소프트손절 강화
SCANNER_SOFT_STOP_PCT = -0.8    # 현재 -1.5%에서 강화
```

### 5.3 중기 개선 — 진입 부분체결 처리 로직 점검

| 현재 동작 | 문제점 | 개선 방향 |
|-----------|--------|-----------|
| 1주 체결 후 fallback 재진입 시도 | fallback도 실패하면 1주 상태로 손절 대기 | 잔량 포기 기준 명시화 |
| buy_qty=1에서 물타기 수량=0 | 물타기 활성화해도 효과 없음 | 부분체결 임계 수량 미만 시 즉시 정리 고려 |

### 5.4 검토 보류 — 일반 AVG_DOWN 활성화

```python
SCALPING_ENABLE_AVG_DOWN = True
SCALPING_AVG_DOWN_MIN_DROP_PCT = -3.0   # 낙폭 -3% 이상에서만 적용
```

낙폭 -3% 이하는 스캘핑 손절선(-0.7%)보다 훨씬 깊은 구간.  
오늘 데이터에서 이 구간에 진입한 종목 없음 → 실효성 낮고 리스크 대비 이득 불명확. **보류 권장**.

---

## 6. 결론

| 항목 | 내용 |
|------|------|
| 물타기가 도움됐을 종목 | **한화오션 1건** (10주 전량 체결, peak +0.21%) |
| 시뮬레이션 효과 | 손실 -8,211원 → 약 -4,200원 (49% 감소) |
| 나머지 5건 판정 | 물타기 무의미 (부분체결 1주 × 4건, AI급락 × 1건) |
| 실질 선행 과제 | 진입 부분체결 처리 개선 (물타기 효과의 전제 조건) |
| 권장 1안 | `REVERSAL_ADD_ENABLED = True` + `MAX_HOLD_SEC = 300` |
| 권장 2안 | SCANNER 포지션 소프트손절 기준 강화 (-1.5% → -0.8%) |

---

## 7. 관찰축 승격 (5번 축)

### 7.1 판정

- `add_judgment_locked` 반복 차단을 기존 4축(`dynstr/partial/shadow/expired`) 외 **5번 관찰축**으로 승격한다.
- 단독 기대효과는 제한적일 수 있으나, `reversal_add`/진입체결률/soft-stop 보정과 결합 시 기대값 개선 여지가 있어 지속 모니터링한다.

### 7.2 집계 기준

- 로그 소스: `logs/sniper_state_handlers_info.log`
- 집계 키: `[ADD_BLOCKED] ... reason=add_judgment_locked`
- 기본 뷰:
  1. 종목별 발생건수 (`add_blocked_lock_count_by_stock`)
  2. 시간대별 발생건수 (`add_blocked_lock_count_by_timebucket`)
  3. HOLDING 정체 코호트(예: `held_sec >= 600`) 교차분포

### 7.3 2026-04-16 관측 스냅샷

- 종목별 누적:
  - `올릭스(226950)`: 56
  - `롯데쇼핑(023530)`: 56
  - `파미셀(005690)`: 38
  - `지투파워(388050)`: 17
- 합계(상기 4종목): 167
- 최근 고빈도 구간(12:30~12:36): 52건

### 7.4 다음 액션

1. 장중/장후 보고에 5번 축 지표를 고정 포함한다.
2. `lock 완화/분리 canary`는 한 축만 적용하고, 퍼널·체결품질·기회비용 동시 비교로 판정한다.
3. 사용자 공유 모니터링 결과를 동일 포맷으로 합산해 다음 판정에 반영한다.
