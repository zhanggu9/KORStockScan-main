# 작업지시서: 스캘핑 정체 구간 감지 시 물타기 (Stagnation AVG_DOWN)

> 작성일: 2026-04-15  
> 우선순위: 중  
> 실행 시점: POSTCLOSE 또는 다음 장 전 배포  
> 토글: `SCALP_STAGNATION_AVGDOWN_ENABLED` (기본값 `False`, 카나리 후 활성화)

---

## 1. 배경 및 목적

스캘핑 보유 중 AI 하방카운트 역치(≤35점)와 손절선(-0.7%) **양쪽 모두에 걸리지 않는 사각지대**에서
소폭 손실(-0.05% ~ -0.5%)이 N틱 이상 지속되다가 역전하는 패턴이 반복적으로 관찰됨.

**관측 패턴 (실제 로그)**:
```
수익: -0.08% | AI: 71점 | 하방카운트: 0/3
수익: -0.16% | AI: 68점 | 하방카운트: 0/3
수익: -0.23% | AI: 40점 | 하방카운트: 0/3  ← 정체
수익: -0.23% | AI: 40점 | 하방카운트: 0/3  ← 정체
수익: -0.23% | AI: 40점 | 하방카운트: 0/3  ← 정체
수익: -0.01% | AI: 56점 | 하방카운트: 0/3  ← 역전
수익: -0.01% | AI: 68점 | 하방카운트: 0/3  ← 역전
```

이 구간에서 물타기로 평단을 낮추면 역전 시 수익률이 높아진다.  
기존 두 물타기 경로(가격낙폭 기반 `evaluate_scalping_avg_down`, AI카운트 기반 `scalp_ai_exit_avgdown`)는  
이 구간을 커버하지 않으므로 신규 경로로 추가한다.

---

## 2. 정체 구간 정의

| 조건 | 값 | 비고 |
|---|---|---|
| 수익률 범위 | `[STAGNATION_LOSS_MAX, STAGNATION_LOSS_MIN]` | 기본: -0.5% ~ -0.05% |
| AI 점수 하한 | `SCALP_STAGNATION_MIN_AI_SCORE` | 기본: 36점 (하방카운트 역치 35 초과) |
| 연속 틱 기준 | `SCALP_STAGNATION_HITS_NEEDED` | 기본: 4틱 |
| 하방카운트 | `ai_low_score_hits == 0` 필수 | 하방카운트 시작 시 정체 아님으로 판단 |
| 물타기 미소진 | `scalp_stagnation_avgdown_done == False` | 종목당 1회 제한 |

**리셋 조건** (정체 카운터 초기화):
- `profit_rate > -STAGNATION_LOSS_MIN_PCT` (수익 전환 또는 손실 미미)
- `profit_rate < -STAGNATION_LOSS_MAX_PCT` (손절 구간 진입)
- `ai_low_score_hits > 0` (하방카운트 시작됨)
- `current_ai_score < SCALP_STAGNATION_MIN_AI_SCORE` (AI 본격 하락)

---

## 3. 현재 코드 구조

### 3.1 정체 카운터 업데이트 위치

**파일**: `src/engine/sniper_state_handlers.py`  
**위치**: L3122 (`stock['ai_low_score_loss_hits'] = ai_low_score_hits`) 바로 다음

AI 감시 사이클마다 정체 여부를 판단하여 `scalp_stagnation_hits` 카운터를 누적/초기화한다.

### 3.2 물타기 평가 위치

**파일**: `src/engine/sniper_scale_in.py`  
신규 함수 `evaluate_scalping_stagnation_avgdown(stock, profit_rate)` 추가.

**파일**: `src/engine/sniper_state_handlers.py`  
`_evaluate_add_position()` 내 SCALPING 분기(L4006)에 stagnation 평가 결과를 추가.

### 3.3 기존 세 물타기 경로와의 관계

| 경로 | 파일 | 트리거 | 토글 | 회수 제한 |
|---|---|---|---|---|
| 가격낙폭 기반 | `sniper_scale_in.py` | `profit_rate` 낙폭 구간 | `SCALPING_ENABLE_AVG_DOWN` | `SCALPING_MAX_AVG_DOWN_COUNT` |
| AI카운트 기반 | `sniper_state_handlers.py` | `ai_low_score_hits >= 3` | `SCALP_AI_EXIT_AVGDOWN_ENABLED` | `scalp_ai_exit_avgdown_done` |
| **정체 기반 (신규)** | `sniper_scale_in.py` | stagnation_hits >= N | `SCALP_STAGNATION_AVGDOWN_ENABLED` | `scalp_stagnation_avgdown_done` |

세 경로는 독립 토글과 독립 소진 플래그를 가진다.  
모두 `avg_down_count`를 공유하므로 체결 후 자연스럽게 가격낙폭 경로의 `avg_down_count_limit`에 연동된다.

---

## 4. 구현 상세

### 4.1 상수 추가

**파일**: `src/utils/constants.py`  
위치: `SCALP_AI_EXIT_AVGDOWN_ENABLED` 인근

```python
SCALP_STAGNATION_AVGDOWN_ENABLED: bool = False   # 정체 구간 물타기 활성화 토글
SCALP_STAGNATION_LOSS_MIN_PCT: float = -0.05     # 정체 판단 최소 손실폭 (손실이 이 값 이상이어야 함)
SCALP_STAGNATION_LOSS_MAX_PCT: float = -0.50     # 정체 판단 최대 손실폭 (이 값 초과면 정체 아님)
SCALP_STAGNATION_MIN_AI_SCORE: int = 36          # 정체 판단 최소 AI 점수 (하방카운트 역치 35 초과)
SCALP_STAGNATION_HITS_NEEDED: int = 4            # 물타기 트리거까지 필요한 연속 정체 틱 수
```

### 4.2 stock 딕셔너리 신규 키

| 키 | 타입 | 의미 | 초기값 |
|---|---|---|---|
| `scalp_stagnation_hits` | `int` | 연속 정체 판단 누적 카운터 | `0` |
| `scalp_stagnation_avgdown_done` | `bool` | 정체 기반 물타기 소진 플래그 | `False` |

DB 저장 불필요 (메모리 런타임 상태).

### 4.3 `sniper_state_handlers.py` 수정 — 정체 카운터 업데이트

**위치**: L3122 직후 (AI 감시 사이클 내부)

```python
# 기존 코드
stock['ai_low_score_loss_hits'] = ai_low_score_hits

# 추가할 코드 (L3122 바로 아래)
if getattr(TRADING_RULES, 'SCALP_STAGNATION_AVGDOWN_ENABLED', False):
    stagnation_min = float(getattr(TRADING_RULES, 'SCALP_STAGNATION_LOSS_MIN_PCT', -0.05))
    stagnation_max = float(getattr(TRADING_RULES, 'SCALP_STAGNATION_LOSS_MAX_PCT', -0.50))
    stagnation_min_ai = int(getattr(TRADING_RULES, 'SCALP_STAGNATION_MIN_AI_SCORE', 36))
    stagnation_hits = int(stock.get('scalp_stagnation_hits', 0) or 0)

    in_stagnation_zone = (
        stagnation_max <= profit_rate <= stagnation_min
        and current_ai_score >= stagnation_min_ai
        and ai_low_score_hits == 0
    )
    if in_stagnation_zone:
        stagnation_hits += 1
    else:
        stagnation_hits = 0
    stock['scalp_stagnation_hits'] = stagnation_hits
```

### 4.4 `sniper_scale_in.py` 수정 — 신규 평가 함수 추가

`evaluate_scalping_avg_down()` 함수 **다음**에 신규 함수 추가:

```python
def evaluate_scalping_stagnation_avgdown(stock, profit_rate):
    """
    스캘핑 정체 구간 물타기 평가.
    AI 하방카운트 미트리거 + 손절선 미트리거인 소폭 손실 정체 구간에서
    연속 N틱 정체 감지 시 1회 AVG_DOWN을 트리거한다.
    """
    result = _base_result()

    if not getattr(TRADING_RULES, 'SCALP_STAGNATION_AVGDOWN_ENABLED', False):
        result["reason"] = "stagnation_avgdown_disabled"
        return result

    if bool(stock.get('scalp_stagnation_avgdown_done', False)):
        result["reason"] = "stagnation_avgdown_done"
        return result

    hits_needed = int(getattr(TRADING_RULES, 'SCALP_STAGNATION_HITS_NEEDED', 4))
    stagnation_hits = int(stock.get('scalp_stagnation_hits', 0) or 0)
    if stagnation_hits < hits_needed:
        result["reason"] = f"stagnation_hits_not_met({stagnation_hits}/{hits_needed})"
        return result

    result["should_add"] = True
    result["add_type"] = "AVG_DOWN"
    result["reason"] = "scalping_stagnation_avgdown_ok"
    return result
```

### 4.5 `sniper_state_handlers.py` 수정 — `_evaluate_add_position()` 연동

**위치**: L4006 (`avg_down = evaluate_scalping_avg_down(stock, profit_rate)`) 다음

```python
# 기존
avg_down = evaluate_scalping_avg_down(stock, profit_rate)
pyramid = evaluate_scalping_pyramid(stock, profit_rate, peak_profit, is_new_high)

# 수정 후
avg_down = evaluate_scalping_avg_down(stock, profit_rate)
pyramid = evaluate_scalping_pyramid(stock, profit_rate, peak_profit, is_new_high)

# 정체 기반: 가격낙폭/불타기 모두 미트리거인 경우에만 검토
if not avg_down.get("should_add") and not pyramid.get("should_add"):
    stagnation_down = evaluate_scalping_stagnation_avgdown(stock, profit_rate)
    if stagnation_down.get("should_add"):
        avg_down = stagnation_down
```

그리고 `execute_scale_in_order` 성공 후 소진 플래그 설정은 `_process_scale_in_action` 호출부에서  
`reason == "scalping_stagnation_avgdown_ok"`인 경우 처리:

**위치**: `_process_scale_in_action` 호출 직후 (add_result 체크 지점)

```python
add_result = _process_scale_in_action(stock, code, ws_data, action, admin_id)
if add_result:
    reason = action.get("reason", "")
    if reason == "scalping_stagnation_avgdown_ok":
        stock['scalp_stagnation_avgdown_done'] = True
        stock['scalp_stagnation_hits'] = 0
```

이 처리는 `_evaluate_add_position` 결과를 처리하는 기존 호출부에 추가한다.

---

## 5. 실행 흐름 다이어그램

```
[AI 감시 사이클 — L3122 직후]
    ↓
stagnation_zone 판단
(stagnation_max <= profit_rate <= stagnation_min
 AND ai_score >= min_ai AND ai_low_hits == 0)
    ├─ True  → scalp_stagnation_hits += 1
    └─ False → scalp_stagnation_hits = 0

[Add Position 평가 — _evaluate_add_position()]
    ↓
가격낙폭/불타기 모두 미트리거?
    └─ Yes → evaluate_scalping_stagnation_avgdown()
                ↓
          stagnation_hits >= HITS_NEEDED?
          AND scalp_stagnation_avgdown_done == False?
                ├─ Yes → should_add = True
                │         → execute_scale_in_order()
                │           성공: scalp_stagnation_avgdown_done = True
                │                 scalp_stagnation_hits = 0
                └─ No  → 물타기 없음, 보유 유지
```

---

## 6. 수정 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `src/utils/constants.py` | 상수 5개 추가 |
| `src/engine/sniper_scale_in.py` | `evaluate_scalping_stagnation_avgdown()` 신규 함수 추가, import 추가 불필요 |
| `src/engine/sniper_state_handlers.py` | (1) L3122 직후 stagnation 카운터 업데이트, (2) `_evaluate_add_position()` stagnation 연동, (3) `sniper_scale_in.py` import에 `evaluate_scalping_stagnation_avgdown` 추가 |
| `src/tests/test_sniper_scale_in.py` | 신규 TC 추가 (아래 7항) |

---

## 7. 테스트 케이스

### TC-1: 토글 OFF → 카운터 업데이트 안 됨, 물타기 미트리거
```python
TRADING_RULES.SCALP_STAGNATION_AVGDOWN_ENABLED = False
# 결과: scalp_stagnation_hits 변화 없음, should_add = False
```

### TC-2: 정체 4틱 미만 → 물타기 미트리거
```python
TRADING_RULES.SCALP_STAGNATION_AVGDOWN_ENABLED = True
stock = {"scalp_stagnation_hits": 3, "scalp_stagnation_avgdown_done": False}
# 결과: should_add = False, reason = "stagnation_hits_not_met(3/4)"
```

### TC-3: 정체 4틱 달성 → 물타기 트리거
```python
TRADING_RULES.SCALP_STAGNATION_AVGDOWN_ENABLED = True
stock = {"scalp_stagnation_hits": 4, "scalp_stagnation_avgdown_done": False}
profit_rate = -0.23
# 결과: should_add = True, reason = "scalping_stagnation_avgdown_ok"
```

### TC-4: 소진 플래그 True → 재트리거 없음
```python
stock = {"scalp_stagnation_hits": 10, "scalp_stagnation_avgdown_done": True}
# 결과: should_add = False, reason = "stagnation_avgdown_done"
```

### TC-5: ai_low_hits > 0 → 카운터 리셋
```python
# AI 감시 사이클에서 ai_low_score_hits = 1이면
# → in_stagnation_zone = False → stagnation_hits = 0
```

### TC-6: 수익률 범위 이탈 → 카운터 리셋
```python
profit_rate = +0.10  # 수익 전환
# → in_stagnation_zone = False → stagnation_hits = 0
profit_rate = -0.80  # 손절 구간 진입
# → in_stagnation_zone = False → stagnation_hits = 0
```

---

## 8. 배포 절차 (토글 기반 카나리)

```
1단계 (기본값 유지)
  SCALP_STAGNATION_AVGDOWN_ENABLED = False
  → 기존 동작 100% 유지

2단계 (카나리 활성화)
  config_prod.json: "SCALP_STAGNATION_AVGDOWN_ENABLED": true
  → 장중 정체 구간 물타기 트리거 여부 및 이후 수익률 추이 모니터링

카나리 관측 지표:
  - 트리거 횟수
  - 트리거 후 수익률 역전율
  - 트리거 후 하방카운트로 이어진 비율 (악화 케이스)

롤백: config_prod.json에서 false 또는 키 제거 → 봇 재시작
```

---

## 9. 주의사항

1. **가격낙폭 기반과 충돌 없음**: `_evaluate_add_position()`에서 가격낙폭/불타기가 먼저 평가되고  
   **둘 다 미트리거인 경우에만** 정체 기반이 검토된다. 동시 물타기 없음.

2. **AI카운트 기반(`scalp_ai_exit_avgdown`)과의 관계**:  
   AI카운트 기반은 `is_sell_signal` 분기에서 처리되고, 정체 기반은 `_evaluate_add_position()` 분기에서 처리된다.  
   따라서 두 경로는 실행 분기가 달라 동시 발동 없음.  
   단, 정체 기반 물타기 후 AI카운트가 3회 도달하면 AI카운트 기반이 추가로 트리거 가능 (의도된 동작).

3. **`avg_down_count` 공유**:  
   정체 기반 체결 후 `avg_down_count`가 증가(receipt 처리 시점)하므로,  
   가격낙폭 기반의 `SCALPING_MAX_AVG_DOWN_COUNT` 한도가 자연히 적용된다.

---

## 10. 미결 확인 항목 (구현 전 오퍼레이터 확인 필요)

| 항목 | 질문 | 기본 가정 |
|---|---|---|
| A | `SCALP_STAGNATION_HITS_NEEDED = 4` — 10초 간격이면 40초. 적정한가? | 관측 로그 기준 충분, 조정 가능 |
| B | `SCALP_STAGNATION_LOSS_MAX_PCT = -0.50` — 손실 0.5% 초과 시 정체 아님으로 처리. 적정한가? | 하방카운트 발동 손실선 -0.7%보다 보수적으로 설정 |
| C | 정체 물타기 + AI카운트 물타기 연속 발동 허용하는가? | ✅ **확정: 허용** — 최대 2회 물타기 허용 (2026-04-15 오퍼레이터 확인) |
