# 코드 리뷰: Sniper Engine 핵심 모듈 3종

**대상 파일**
- `src/engine/sniper_execution_receipts.py` (1192 lines)
- `src/engine/sniper_scale_in.py` (348 lines)
- `src/engine/sniper_state_handlers.py` (5400 lines)

**판정**: 기능 정합성은 유지되고 있으나 **구조적 리팩터링이 시급**한 상태. 특히 `handle_watching_state`(1500줄)와 `handle_real_execution`(550줄)의 함수 분해가 최우선 과제이며, 락 정책 및 thread-safety는 잠재적 데이터 레이스 위험이 있어 우선 점검이 필요하다.

---

## 1. `sniper_execution_receipts.py`

### 🔴 Critical

#### 1.1 락 공유로 인한 커플링 (line 38)

```python
RECEIPT_LOCK = ENTRY_LOCK
```

`RECEIPT_LOCK`이 `ENTRY_LOCK`과 동일 객체를 참조하여, receipt 처리와 entry 상태 정리 간에 의도치 않은 lock contention이 발생한다. 두 모듈의 관심사가 다르므로 **별도 락으로 분리**하거나, 의도적 공유임을 명시하는 docstring을 추가해야 한다.

#### 1.2 Thread-safety 결함 (line 1046-1050, 1186-1190)

```python
# main thread에서 target_stock을 mutate한 직후:
threading.Thread(
    target=_update_db_for_buy,
    args=(target_id, exec_price, now, target_stock),  # ← target_stock 참조 전달
    daemon=True
).start()
```

`handle_real_execution`에서 `target_stock` 딕셔너리를 main thread가 수정한 직후 백그라운드 스레드에 **동일 객체 참조**를 넘긴다. 백그라운드 스레드의 `_update_db_for_buy` / `_update_db_for_add` / `_update_db_for_sell` 함수들은 `target_stock.get('buy_qty')`, `target_stock.pop('pending_buy_msg', None)` 등으로 동일 객체를 읽고 쓴다. main thread도 같은 객체를 계속 참조(`ACTIVE_TARGETS` 리스트 내)하므로 **데이터 레이스 가능성**이 존재한다.

**권장**: DB 업데이트에 필요한 값만 snapshot으로 복사하여 인자로 전달할 것.

#### 1.3 중복 로직 (line 356-360)

```python
def weighted_avg_price(old_price, old_qty, exec_price, exec_qty):
    total_qty = old_qty + exec_qty
    if total_qty <= 0:
        return exec_price
    return round(((old_price * old_qty) + (exec_price * exec_qty)) / total_qty, 4)
```

이 함수와 line 35-36에서 의존성 주입으로 받는 `_weighted_avg` 콜러블이 기능적으로 중복된다. 호출 지점(line 727, 823)에서 `_weighted_avg`를 사용하도록 통합하거나, 이 함수를 제거해야 한다.

---

### 🟠 Major

#### 1.4 함수 과대 (line 645-1192)

`handle_real_execution`이 **550줄**의 단일 함수로, BUY 체결 / ADD 체결 / SELL 체결 처리가 하나의 함수에 평면적으로 나열되어 있다. 아래로 분리할 것:

| 함수 | 책임 |
|------|------|
| `_handle_buy_fill()` | 신규 매수 체결 처리 (entry bundle, fill quality, preset TP setup) |
| `_handle_add_fill()` | 추가매수 체결 처리 (AVG_DOWN / PYRAMID, 보호선 보정) |
| `_handle_sell_fill()` | 매도 체결 처리 (일반 매도, 스캘핑 부활) |
| `_handle_fast_state_update()` | fast state 누적 집계 |

#### 1.5 SELL 브랜치 들여쓰기 깨짐 (line 1072-1073)

```python
            if is_scalp_revive:
            # 스캘핑 부활: 동기 DB 업데이트 (새 레코드 삽입 필요)
                revived_position_tag = normalize_position_tag(
```

`if is_scalp_revive:` 이후 주석 라인의 들여쓰기가 블록과 불일치한다. Python 문법상 문제는 없으나, 같은 레벨에서 `# 주석`과 실제 코드의 indent가 달라 의도를 오독할 위험이 있다. 주석을 if 블록 안으로 정렬하거나, 주석 뒤에 `pass` 대신 바로 코드가 오는 구조임을 명확히 할 것.

#### 1.6 키 정리 하드코딩 중복 (line 363-375, 86-94, 1162-1182)

`_clear_pending_add_meta()`, `_clear_split_entry_shadow_state()`, 그리고 line 1162-1170 / 1178-1182의 인라인 `pop()` 루프가 각각 다른 키 집합을 관리한다. 키 리스트를 모듈 상수로 정의하고 재사용하면:

- 어떤 키가 어디서 정리되는지 추적 가능
- 키 추가/제거 시 누락 방지

```python
_PENDING_ADD_META_KEYS = frozenset({
    'pending_add_order', 'pending_add_type', 'pending_add_qty',
    'pending_add_ord_no', 'pending_add_requested_at', 'pending_add_counted',
    'pending_add_filled_qty', 'add_order_time', 'add_odno',
})
```

---

### 🟡 Minor

#### 1.7 `print()` 디버그 출력 잔존

`print()`가 line 491, 545, 701, 706 등에 사용되고 있다. 프로덕션 코드에서는 `log_info()` / `log_error()`로 통일해야 로그 레벨 필터링, 파일 출력, 구조화 로깅이 가능하다.

#### 1.8 `_find_execution_target` 매칭 우선순위 불명확 (line 226-273)

`status_key='BUY_ORDERED'` 검색이 `pending_add_order` 검색보다 더 넓은 범위이고, `pending_add_candidates` 검색이 `status_candidates` 검색과 순서 경합이 있다. `ACTIVE_TARGETS`에 동일 코드의 여러 stock이 존재할 경우 어떤 것이 반환될지 보장되지 않는다. 매칭 순서와 우선순위에 대한 테스트 필요.

---

## 2. `sniper_scale_in.py`

### 🟠 Major

#### 2.1 취약한 datetime 파싱 (line 16-34)

```python
def _calc_held_minutes(stock):
    if stock.get('order_time'):
        return (datetime.now().timestamp() - float(stock['order_time'])) / 60.0
    if stock.get('buy_time'):
        try:
            bt = stock['buy_time']
            if isinstance(bt, datetime):
                b_dt = bt
            else:
                bt_str = str(bt)
                try:
                    b_dt = datetime.fromisoformat(bt_str)
                except Exception:
                    b_time = datetime.strptime(bt_str, '%H:%M:%S').time()
                    b_dt = datetime.combine(datetime.now().date(), b_time)
            return (datetime.now() - b_dt).total_seconds() / 60.0
```

`buy_time`이 `datetime.time` 객체일 경우 `str(bt)` → `strptime('%H:%M:%S')` → `.time()` → `.combine()`까지 가는 fallback chain이 지나치게 길다. 또한 `datetime.time` 객체가 `isinstance(bt, datetime)` 체크에서 False가 되어 else 분기로 빠지면서 `.fromisoformat()`에서 실패 → Exception → `strptime` 경로를 타는데, `datetime.time.strptime()`은 존재하지 않아 **두 번째 Exception에서도 실패하면 `_calc_held_minutes`가 0을 반환**한다.

**권장**: `buy_time`의 타입을 `datetime`으로 통일하거나, 타입별 분기를 최상위에서 명시적으로 처리할 것.

#### 2.2 `describe_scale_in_qty` 조건 분기 과다 (line 263-348)

4중첩 조건 분기(SCALPING vs non-SCALPING, AVG_DOWN vs PYRAMID, reversal_add vs normal, floor 적용 여부)가 단일 함수에 평면적으로 나열되어 가독성이 낮다. Strategy pattern이나 lookup table로 단순화 가능:

```python
_QTY_RULES = {
    ('SCALPING', 'AVG_DOWN', 'reversal_add_ok'): {'ratio': 0.33, 'floor_fn': ...},
    ('SCALPING', 'AVG_DOWN', 'default'):          {'ratio': 0.50, 'floor_fn': ...},
    ('SCALPING', 'PYRAMID',  'default'):          {'ratio': 0.50, 'floor_fn': ...},
}
```

#### 2.3 `evaluate_scalping_reversal_add` 과도한 복잡도 (line 158-243)

단일 함수가 85줄에 걸쳐 20개 이상의 조건을 체크한다:

- pnl_range 체크
- hold_sec_range 체크
- 저점 미갱신 확인
- AI 점수 최소 기준
- AI 회복 방향성 (delta 또는 2연속 상승)
- AI 고착 저점 차단 (std <= 2 and avg < 45)
- 수급 조건 4개 중 3개 충족

이 중 어느 하나라도 실패하면 다른 조건이 평가되지 않는다. 개별 gate를 명명된 함수(`_check_pnl_range()`, `_check_ai_recovery()`, `_check_supply_conditions()`)로 분리하고, `all([...])` 또는 pipeline pattern으로 조합하는 것이 테스트와 디버깅에 유리하다.

---

### 🟡 Minor

#### 2.4 변수명 혼동 가능성 (line 54-56)

```python
min_drop = float(getattr(TRADING_RULES, 'SCALPING_AVG_DOWN_MIN_DROP_PCT', -3.0))
max_drop = float(getattr(TRADING_RULES, 'SCALPING_AVG_DOWN_MAX_DROP_PCT', -6.0))
if not (profit_rate <= min_drop and profit_rate >= max_drop):
```

`min_drop` = -3.0, `max_drop` = -6.0일 때, 실제로는 "손실률이 -3.0% 이하이고 -6.0% 이상"이라는 범위 조건이다. `min_drop < max_drop`인 점(절댓값 기준으로 이름이 붙은 듯)이 혼동을 준다. `min_loss_pct` / `max_loss_pct`나 `upper_bound_pct` / `lower_bound_pct` 권장.

#### 2.5 TRADING_RULES `getattr` 반복

각 evaluation 함수에서 동일한 `getattr(TRADING_RULES, '...')` 패턴이 반복된다. 공통 threshold resolver 도입 검토.

---

## 3. `sniper_state_handlers.py`

### 🔴 Critical

#### 3.1 파일 크기 과대 (5400 lines)

파일 하나에 **4개의 public handler, 87개의 private 함수**가 혼재되어 있다. 관심사별 분할을 강력히 권장:

| 신규 파일 | 내용 |
|-----------|------|
| `sniper_watching_handler.py` | `handle_watching_state`, AI 분석, Gatekeeper, 진입 신호 |
| `sniper_holding_handler.py` | `handle_holding_state`, AI review, exit logic, scale-in |
| `sniper_order_handlers.py` | `handle_buy_ordered_state`, `handle_sell_ordered_state`, entry reconciliation |
| `sniper_state_utils.py` | 공통 유틸리티: bucketing, pipeline logging, marcap cache, entry arm, entry order 관리 |
| `sniper_state_shadows.py` | Shadow 로깅 함수들: `_emit_*_shadow_*`, `_observe_*`, dual persona |

#### 3.2 전역 상태 과의존 (line 107-117, 120-173)

`KIWOOM_TOKEN`, `DB`, `EVENT_BUS`, `ACTIVE_TARGETS`, `COOLDOWNS`, `ALERTED_STOCKS`, `HIGHEST_PRICES`, `LAST_AI_CALL_TIMES`, `LAST_LOG_TIMES`, `TRADING_RULES`, 그리고 여러 콜러블 참조까지 20개 이상의 모듈 레벨 전역 변수가 `bind_state_dependencies()`로 주입된다.

- 실행 중 변경되지 않는 값들은 `bind` 이후 재할당을 막아야 한다 (`_frozen` 컨벤션).
- 함수 인자로 명시적 전달이 가능한 값은 전역 대신 인자로 넘기는 것이 테스트 용이성을 높인다.

#### 3.3 `handle_watching_state` 과도한 길이 (line 1894-3380, 약 1500 lines)

WATCHING 상태의 모든 진입 로직 — VPW 체크, Big-Bite, AI 호출, Gatekeeper, orderbook stability, latency guard, entry arm, buy order submission, telegram notification — 이 단일 함수에 포함되어 있다.

**함수는 orchestration만 담당**하고, 각 gatekeeper/guard는 아래처럼 분리할 것:

```
handle_watching_state()
  ├── _check_trading_pause()
  ├── _check_cooldowns()
  ├── _check_overbought()
  ├── _evaluate_big_bite()
  ├── _evaluate_strength_momentum()
  ├── _run_ai_analysis()
  │     ├── _run_primary_ai()
  │     ├── _run_buy_recovery_canary()
  │     └── _run_dual_persona_shadow()
  ├── _run_gatekeeper()
  ├── _check_orderbook_stability()
  ├── _check_latency_guard()
  └── _submit_buy_orders()
```

---

### 🟠 Major

#### 3.4 TRADING_RULES `getattr` 폭증

`getattr(TRADING_RULES, '...', default)` 호출이 파일 전역에서 **수백 번** 반복된다. Rule resolution을 중앙 접근자로 대체하면 이점이 크다:

```python
def _rule(key: str, default=None):
    """TRADING_RULES 중앙 접근자. key typo 방지와 default 관리를 일원화."""
    return getattr(TRADING_RULES, key, default)
```

또는 Enum/Literal 기반 key 정의로 typo를 방지할 수 있다.

#### 3.5 중복된 시간 계산 로직 (line 1288-1312)

`_resolve_holding_elapsed_sec`이 `sniper_scale_in.py`의 `_calc_held_minutes`와 거의 동일한 `buy_time` 파싱 로직을 갖고 있다. 공통 유틸리티 `sniper_time.holding_elapsed_sec()` 또는 `sniper_utils.resolve_buy_time_as_datetime()`으로 추출해야 한다.

#### 3.6 락 일관성 부족

- `_clear_pending_entry_meta()`(line 1509): `ENTRY_LOCK` 사용
- `_stage_buy_order_submission()`(line 1697): `ENTRY_LOCK` 사용
- `handle_watching_state` 내 stock 상태 수정: **락 없음**
- `handle_holding_state` 내 scale-in 처리: **락 없음**

`ACTIVE_TARGETS` 리스트 전체에 대한 일관된 락 정책이 없다. 어떤 연산이 atomic해야 하는지 정의하고, 데드락이 발생하지 않는 락 계층 구조를 설계해야 한다.

---

### 🟡 Minor

#### 3.7 `_sanitize_pending_add_states` 부작용 위치 (line 151)

```python
if active_targets is not None:
    ACTIVE_TARGETS = active_targets
    _sanitize_pending_add_states(ACTIVE_TARGETS)  # ← 부작용이 명시적이지 않음
```

의존성 바인딩 함수 내에서 상태 정리(sanitize)가 일어나는 것은 부작용이 숨겨지는 패턴이다. `bind`와 `sanitize`를 별도 호출로 분리하는 것이 `bind_state_dependencies`의 순수성을 유지하는 방법이다.

#### 3.8 `_build_holding_ai_fast_signature` 용도 불명확 (line 1455-1457)

```python
def _build_holding_ai_fast_signature(ws_data):
    snapshot = _build_holding_ai_fast_snapshot(ws_data)
    return tuple(snapshot.values())
```

`snapshot`은 dict인데 `tuple(snapshot.values())`로 변환한 결과가 fast signature의 목적을 달성하는지 불분명하다. dict는 hashable하지 않으므로 cache key로 사용할 수 없어 `tuple` 변환이 이루어진 것으로 추정되나, `snapshot`에 필드가 추가/제거/순서 변경되면 의도치 않게 signature가 바뀔 위험이 있다. ordered field list 기반의 명시적 튜플 생성 권장.

#### 3.9 pipeline event의 stock 타입 불일치

`_log_entry_pipeline`(line 326-335)과 `_log_holding_pipeline`(line 338-347)에서 `stock` 파라미터가 `dict`라고 가정하고 `stock.get("name")`, `stock.get("id")`를 호출한다. 그러나 `_log_entry_pipeline`에서는 `isinstance(stock, dict)` 체크로 방어하고, `_log_holding_pipeline`은 체크 없이 바로 접근한다. `stock`의 타입 계약을 통일할 것.

#### 3.10 `_log_watching_shared_prompt_shadow_result` - strategy 하드코딩 (line 793-830)

`_log_watching_shared_prompt_shadow_result`와 `_log_dual_persona_shadow_result`에서 `strategy="SCALPING"`이 하드코딩되어 있다. 향후 SWING 전략에도 shadow가 도입될 경우 확장이 어렵다.

---

## 공통 우려사항

| 항목 | 설명 |
|------|------|
| **Mutable dict 상태 전파** | 세 파일 모두 종목 상태를 `dict`로 전달하고 in-place mutation한다. 타입 안전성과 IDE 지원(자동완성)을 위해 `TypedDict` 또는 `dataclass` 도입을 검토할 시점. |
| **print() 잔존** | 프로덕션 코드에 `print()`가 10곳 이상 사용됨. 로그 레벨 필터링, 파일 출력을 위해 `log_info()` / `log_error()`로 통일 필요. |
| **silent exception** | 핫패스에서 `except Exception: pass` 패턴이 사용되어 디버깅이 어려운 지점이 존재. 최소한 `log_error`로 traceback을 남길 것. |
| **함수 시그니처 일관성** | `stock`이 `dict`인지, `RecommendationHistory` ORM 객체인지, 코드 경로에 따라 다르게 사용됨. mypy strict 모드 도입 검토. |
| **pipeline event 필드 누락 위험** | `**fields`로 전달되는 pipeline event 필드가 ad-hoc하게 구성되어 있어, stage별 필드 스키마가 암묵적이다. stage별 TypedDict 정의 권장. |

---

## 우선순위 액션 아이템

1. **`handle_watching_state` 분해** — 가장 긴 함수. gatekeeper/guard를 개별 함수로 추출.
2. **`handle_real_execution` 분해** — BUY / ADD / SELL 브랜치를 독립 함수로.
3. **Thread-safety 점검** — DB 업데이트 스레드에 `target_stock` 참조 대신 snapshot 전달.
4. **`RECEIPT_LOCK` 분리** — `ENTRY_LOCK`과의 커플링 해소.
5. **`sniper_state_handlers.py` 파일 분할** — 5400줄 → 4~5개 모듈.
6. **시간 계산 로직 통합** — `_calc_held_minutes`와 `_resolve_holding_elapsed_sec` 중복 제거.
7. **`TRADING_RULES` 접근 중앙화** — `getattr` 반복을 resolver 함수로 대체.

## 실행 추적 (2026-04-30)

- [x] `src/engine/sniper_execution_receipts.py`: `target_stock` 참조 전달을 제거하고, DB/알림 처리에 snapshot 전달 적용.
- [x] `src/engine/sniper_execution_receipts.py`: `weighted_avg_price` 호출 경로를 `_avg_from_totals` 중심으로 정합화.
- [x] `src/engine/sniper_execution_receipts.py`: `handle_real_execution` 내부 처리를 BUY/ADD/SELL 하위 루틴으로 분리.
- [x] `src/engine/sniper_scale_in.py`: `buy_time` 타입별 파서 정리 및 `evaluate_scalping_reversal_add` 게이트 분해.
- [x] `src/engine/sniper_state_handlers.py`: TRADING_RULES 조회를 `_rule*` 헬퍼 기반으로 통일.
- [x] `src/engine/sniper_state_handlers.py`: `handle_holding_state`의 `_dispatch_scalp_preset_exit` 중첩 함수를 모듈 레벨 함수로 이관.
- [x] `src/engine/sniper_execution_receipts.py`: `RECEIPT_LOCK`을 `ENTRY_LOCK`과 분리하고, `state_lock` 주입으로 동기화 소유권 계약화.
- [x] `src/engine/sniper_state_handlers.py`: `bind_state_dependencies`에서 `_sanitize_pending_add_states` 부작용 제거.
- [x] `src/engine/kiwoom_sniper_v2.py`: startup 시 `sanitize_pending_add_states` 명시 호출로 정합성 정리 경로 분리.
- [x] `src/engine/sniper_scale_in.py` / `src/engine/sniper_state_handlers.py`: 보유시간 계산을 `resolve_holding_elapsed_sec` 공용 헬퍼로 통일.
- [x] `src/engine/sniper_scale_in.py`: `describe_scale_in_qty`를 규칙 테이블 기반으로 단순화하고 `reversal_add`/`pyramid` floor 정책을 한 경로로 통합.
- [x] `src/engine/sniper_state_handlers.py`: `handle_watching_state`에서 전략 분기와 주문 제출 tail을 `_handle_watching_strategy_branch` / `_submit_watching_triggered_entry`로 1차 추출.
- [x] `src/engine/sniper_execution_receipts.py`: 체결 평균가 canonical을 receipt 모듈 내부 정밀 평균(`round(..., 4)`)으로 고정해 `buy_price`/split-entry fallback 평균가 절사 문제 제거.
- [x] `src/engine/sniper_execution_receipts.py` / `src/tests/test_sniper_scale_in.py`: `_find_execution_target` 우선순위를 `bundle -> terminal -> BUY_ORDERED exact -> pending_add exact -> single candidate`로 명문화하고 exact/ambiguous 케이스 테스트를 추가.
- [x] `src/engine/sniper_state_handlers.py` / `src/engine/sniper_execution_receipts.py`: `ENTRY_LOCK`/`state_lock`/`RECEIPT_LOCK fallback` ownership 주석과 helper docstring을 추가해 runtime truth 변경 규칙을 코드에 고정.

## 재검증 결과 (2026-04-30 06:31, 07:02 보정)

15개 완료 항목을 소스 코드 대조 검증했고, 초안 검증에서 확인된 `ADD` 경로 snapshot 누락을 같은 날 보정했다. 현재 기준 **15/15 항목 정합하게 반영됨**.

### 완료 항목별 검증

| # | 항목 | 상태 | 근거 |
|---|------|------|------|
| 1 | `target_stock` → snapshot 전달 | ✅ 완료 | `_update_db_for_buy`, `_update_db_for_add`, `_update_db_for_sell` 모두 snapshot dict 기반으로 정리됐다. `ADD` 경로도 `_ADD_RECEIPT_SNAPSHOT_KEYS` + `_receipt_snapshot()`을 통해 필요한 필드만 잘라 전달한다. |
| 2 | `weighted_avg_price` 정합화 | ✅ 완료 | `_avg_from_totals()` (`receipts.py:639`) 로 canonical 정밀도 통일. `weighted_avg_price`는 delegate wrapper로 유지. |
| 3 | `handle_real_execution` 분해 | ✅ 완료 | `_handle_add_buy_execution` / `_handle_entry_buy_execution` / `_resolve_sell_execution_context` / `_handle_scalp_revive_sell_execution` / `_finalize_standard_sell_execution` 으로 위임 (`receipts.py:1378-1431`). |
| 4 | `buy_time` 파서 정리 + reversal_add 분해 | ✅ 완료 | `_resolve_buy_time_as_datetime()` (`scale_in.py:42-60`), `_check_reversal_add_*` 5개 gate (`scale_in.py:228-294`), 게이트 순차 평가 loop (`scale_in.py:312-321`). |
| 5 | TRADING_RULES `_rule*` 통일 | ✅ 완료 | `_rule()` / `_rule_bool()` / `_rule_int()` / `_rule_float()` (`state_handlers.py:139-160`), 파일 내 204회 사용. |
| 6 | `_dispatch_scalp_preset_exit` 이관 | ✅ 완료 | 모듈 레벨 함수로 전환 (`state_handlers.py:986`), 호출 3곳에서 사용. |
| 7 | `RECEIPT_LOCK` 분리 + `state_lock` 주입 | ✅ 완료 | `RECEIPT_LOCK = threading.RLock()` (`receipts.py:42`), `state_lock` 주입 경로 (`receipts.py:131, 160-161`), ownership 주석 (`receipts.py:39-41, 135-139`). |
| 8 | `_sanitize_pending_add_states` 부작용 제거 | ✅ 완료 | `bind_state_dependencies`에서 제거, `sanitize_pending_add_states()` public 함수로 분리 (`state_handlers.py:218-221`). |
| 9 | `kiwoom_sniper_v2.py` startup 호출 | ✅ 완료 | `sniper_state_handlers.sanitize_pending_add_states(ACTIVE_TARGETS)` (`kiwoom_sniper_v2.py:1156`). |
| 10 | `resolve_holding_elapsed_sec` 통일 | ✅ 완료 | `sniper_scale_in.py:85-104` 에 공용 구현, `state_handlers.py:1432-1433` 에서 wrapper. |
| 11 | `describe_scale_in_qty` 규칙 테이블화 | ✅ 완료 | `_SCALE_IN_RULES` dict (`scale_in.py:8-29`), `_resolve_scale_in_rule()` / `_resolve_scale_in_ratio()` / `_apply_scale_in_template_floor()` 분리. |
| 12 | `handle_watching_state` 1차 추출 | ✅ 완료 | `_handle_watching_strategy_branch()` (`state_handlers.py:1455`), `_submit_watching_triggered_entry()` (`state_handlers.py:2368`). |
| 13 | 체결 평균가 `round(..., 4)` 고정 | ✅ 완료 | `_avg_from_totals()` (`receipts.py:642`), 모든 체결/누적 경로에서 사용. |
| 14 | `_find_execution_target` 우선순위 명문화 + 테스트 | ✅ 완료 | docstring (`receipts.py:513-527`), `_find_buy_bundle_match` / `_find_terminal_entry_target` / `_find_add_order_match` 분해, 94개 테스트 중 해당 케이스 보강. |
| 15 | ownership 주석 추가 | ✅ 완료 | `receipts.py:39-48, 135-140`, `state_handlers.py` 내 `bind_state_dependencies` docstring. |

### 잔여 gap (ADD path thread-safety)

```python
# receipts.py:818 — 여전히 target_stock 참조를 전달
def _update_db_for_add(target_id, exec_price, exec_qty, now, target_stock, add_type, count_increment):
    ...
    new_avg = float(target_stock.get('buy_price') or exec_price or 0)  # race 가능
    new_qty = int(target_stock.get('buy_qty') or 0)                     # race 가능
```

`_update_db_for_buy`와 `_update_db_for_sell`은 snapshot으로 전환되었으나 `_update_db_for_add`만 누락. `_PENDING_ADD_META_KEYS` (`receipts.py:72-82`)를 활용한 snapshot key 집합을 정의하고 ADD 경로도 snapshot 전달로 통일할 것.

### 리뷰 본문 항목들의 현재 상태

원본 리뷰(1-310행)의 지적 항목 중 완료 작업으로 해소된 것:

| 원본 항목 | 현재 상태 |
|-----------|-----------|
| 1.1 락 공유 커플링 | → 해소. `RECEIPT_LOCK = threading.RLock()` 독립, `state_lock` 주입 |
| 1.2 Thread-safety 결함 | → 부분 해소. BUY/SELL snapshot 전환 완료, **ADD 누락 (상기)** |
| 1.3 중복 로직 | → 해소. `_avg_from_totals()` canonical |
| 1.4 함수 과대 | → 해소. 5개 하위 루틴으로 분해 |
| 1.5 SELL 들여쓰기 깨짐 | → 해소. `_handle_scalp_revive_sell_execution` / `_finalize_standard_sell_execution` 분리 |
| 1.6 키 정리 하드코딩 | → 해소. `_PENDING_ADD_META_KEYS` 등 상수화 (`receipts.py:50-118`) |
| 1.7 print() 잔존 | → 해소. `log_info()` / `log_error()` 로 전환 |
| 1.8 매칭 우선순위 불명확 | → 해소. docstring 명문화 + helper 분해 |
| 2.1 datetime 파싱 취약 | → 해소. `_resolve_buy_time_as_datetime()` |
| 2.2 describe_scale_in_qty 분기 과다 | → 해소. 규칙 테이블 기반 |
| 2.3 reversal_add 복잡도 | → 해소. 5개 gate 함수 분해 |
| 2.4 변수명 혼동 | → 해소. `max_loss_pct` / `min_loss_pct` 로 rename |
| 3.4 TRADING_RULES getattr | → 해소 (state_handlers.py). **단, `sniper_scale_in.py`는 `_rule*` 접근 불가로 `getattr` 직접 호출 잔존** |
| 3.5 시간 계산 중복 | → 해소. `resolve_holding_elapsed_sec` 공용 |
| 3.7 sanitize 부작용 | → 해소. public 함수로 분리 |

**`sniper_scale_in.py`의 `getattr(TRADING_RULES, ...)` 직접 호출 (review 2.5)** 과 **minor 항목 3.8~3.10** 은 1차 완료 범위에 포함되지 않았으며, 원본 리뷰 평가가 여전히 유효하다.

### 잔여 항목

- [ ] `sniper_state_handlers.py`: `handle_watching_state` 2차 분해 및 전략별 세부 handler(`SCALPING`/`KOSDAQ_ML`/`KOSPI_ML`) 독립.
- [ ] `sniper_state_handlers.py`: `LOCK` 사용 범위 정합성 2차 정리(remaining direct mutation 경로를 helper/collection 규칙으로 추가 축소하고 race 재검토).
- [ ] `sniper_execution_receipts.py`/`sniper_state_handlers.py`: `RECEIPT_LOCK`/`ENTRY_LOCK` 소유권 정책의 운영상 롤아웃 가이드(임계 동시성/rollback 기준) 문서 고도화.
- [ ] `sniper_execution_receipts.py`: `_update_db_for_add` 도 snapshot 전달로 전환하여 ADD 경로 thread-safety 완결.
