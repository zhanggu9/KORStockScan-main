# `ai_engine.py` 스캘핑 로직 감리보고서

작성일: `2026-05-02 KST`  
대상: [`src/engine/ai_engine.py`](../../src/engine/ai_engine.py)  
목적: `ai_engine.py` 내 스캘핑 관련 개선작업 꼬임 및 정상화  
기준 문서:

- [`plan-korStockScanPerformanceOptimization.rebase.md`](../plan-korStockScanPerformanceOptimization.rebase.md)
- [`2026-05-02-stage2-todo-checklist.md`](../2026-05-02-stage2-todo-checklist.md)
- [`2026-05-04-stage2-todo-checklist.md`](../2026-05-04-stage2-todo-checklist.md)
- [`2026-05-06-stage2-todo-checklist.md`](../2026-05-06-stage2-todo-checklist.md)
- [`workorder_gemini_engine_review.md`](../archive/workorders/workorder_gemini_engine_review.md)

---

## 1. 판정

1. 현재 `ai_engine.py`의 스캘핑 실전 표면은 크게 `진입 판단`, `제출 직전 가격 재판정`, `보유 흐름 재판정`, `오버나이트 판정`, `조건검색 어댑터`로 나뉜다.
2. 실전 기본 라우팅은 여전히 Gemini다. [`runtime_ai_router.py`](../../src/engine/runtime_ai_router.py)는 OpenAI/DeepSeek 교체 경로를 갖고 있지만, Plan Rebase 기본값은 `gemini` 고정이다.
3. 현재 정상화 owner는 legacy `buy_recovery_canary`나 fallback 경로가 아니라 `dynamic_entry_price_resolver_p1`, `dynamic_entry_ai_price_canary_p2`, `holding_flow_override`다.
4. `ai_engine.py`는 프롬프트, 스키마, 캐시, 모델 호출, 실패 상태, 락을 한 클래스가 같이 소유한다. 따라서 스캘핑 개선작업이 꼬이는 주된 원인은 "함수 수가 많다"보다 "shared lock/shared state/shared contract가 넓게 공유된다"는 점이다.

---

## 2. 범위

### 2.1 이번 보고서의 포함 범위

- `SCALPING_*` 프롬프트와 정규화 함수
- `GeminiSniperEngine`의 스캘핑 관련 퍼블릭 메서드
- 스캘핑 feature packet 추출과 감사 필드 주입
- 스캘핑 진입/보유/오버나이트 호출부
- 현재 문서상 남아 있는 AI 엔진 후속 계획

### 2.2 이번 보고서의 제외 범위

- 스윙 전용 프롬프트와 스윙 분석 로직
- 텔레그램 실시간 리포트 문구 품질 자체
- 장마감 후 `TOP5` 리포트 품질 자체
- OpenAI/DeepSeek 파일 내부 구현 상세

단, 제외 범위라도 스캘핑 경로와 같은 락/라우터/스키마를 공유하는 경우에는 연계 지점으로만 언급한다.

---

## 3. 구조 요약

### 3.1 런타임 배치

`ai_engine.py`는 현재 Gemini 기본 엔진 구현이다. 스캘핑 실전 호출은 보통 다음 경로를 따른다.

```text
RuntimeAIEngineRouter
  -> GeminiSniperEngine (기본 live route)
     -> analyze_target()
     -> evaluate_scalping_entry_price()
     -> evaluate_scalping_holding_flow()
     -> evaluate_scalping_overnight_decision()
```

### 3.2 주요 호출 그래프

| 실전 단계 | 호출부 | `ai_engine.py` 진입점 | 목적 |
| --- | --- | --- | --- |
| WATCHING 진입 판단 | [`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) | `analyze_target(..., prompt_profile="watching")` | BUY/WAIT/DROP 진입 분류 |
| 제출 직전 가격 조정 | [`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) `_apply_entry_ai_price_canary()` | `evaluate_scalping_entry_price()` | `USE_DEFENSIVE/USE_REFERENCE/IMPROVE_LIMIT/SKIP` 가격 재판정 |
| HOLDING 점수 refresh | [`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) | `analyze_target(..., cache_profile="holding", prompt_profile="holding")` | 보유 중 AI 점수 갱신 |
| HOLDING 흐름 override | [`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) `_evaluate_holding_flow_override()` | `evaluate_scalping_holding_flow()` | 조급한 전량청산 보류 여부 재판정 |
| 오버나이트 선행 판정 | [`sniper_overnight_gatekeeper.py`](../../src/engine/sniper_overnight_gatekeeper.py) | `evaluate_scalping_overnight_decision()` | `SELL_TODAY/HOLD_OVERNIGHT` 1차 판정 |
| 오버나이트 flow 재검문 | [`sniper_overnight_gatekeeper.py`](../../src/engine/sniper_overnight_gatekeeper.py) | `evaluate_scalping_holding_flow(..., decision_kind="overnight_sell_today")` | `SELL_TODAY` 재검문 |
| 조건검색 진입/청산 | `evaluate_condition_entry()`, `evaluate_condition_exit()` | 내부적으로 `analyze_target()` 재사용 | legacy caller 호환 |
| 운영/감사 보조 | [`sniper_analysis.py`](../../src/engine/sniper_analysis.py) | `analyze_target()` | 설명용/진단용 AI 점수 표시 |

---

## 4. 공통 입력 계약

### 4.1 `ws_data`

`ws_data`는 웹소켓 기준의 실시간 스냅샷 dict다. 스캘핑 경로에서 주로 쓰는 키는 아래와 같다.

| 키 | 의미 | 사용 지점 |
| --- | --- | --- |
| `curr` | 현재가 | 전 경로 공통 |
| `fluctuation` | 등락률 | 진입/보유/오버나이트 |
| `v_pw` | 체결강도 | 진입/보유/흐름 |
| `buy_ratio` | 매수비율 | 보유 흐름/holding refresh |
| `ask_tot`, `bid_tot` | 총매도/매수 잔량 | 진입/보유 흐름 |
| `net_ask_depth`, `ask_depth_ratio` | 매도잔량 변화/비율 | feature packet |
| `buy_exec_volume`, `sell_exec_volume` | 체결량 | 보유 흐름/holding refresh |
| `orderbook.asks/bids` | 최우선 호가 및 depth | 진입 판단, entry price, feature packet |
| `latency_state`, `ws_age_ms`, `ws_jitter_ms`, `quote_stale` | 제출 직전 품질 컨텍스트 | entry price canary |

### 4.2 `recent_ticks`

`recent_ticks`는 최근 체결 리스트다. 스캘핑 경로에서 기대하는 핵심 키는 아래와 같다.

| 키 | 의미 |
| --- | --- |
| `time` | 체결시각 (`HHMMSS` 또는 `HH:MM:SS`) |
| `price` | 체결가 |
| `volume` | 체결량 |
| `dir` | `BUY` 또는 `SELL` |
| `strength` | 체결강도 |

### 4.3 `recent_candles`

`recent_candles`는 최근 1분봉 리스트다. 스캘핑 경로에서는 아래 키를 주로 사용한다.

| 키 | 의미 |
| --- | --- |
| `체결시간` 또는 `close/open` 계열 | 캔들 시각 |
| `현재가` 또는 `close` | 종가 |
| `고가`, `저가` | 고저 |
| `거래량` 또는 `volume` | 분봉 거래량 |

### 4.4 `price_ctx`

`evaluate_scalping_entry_price()`는 `price_ctx`를 추가 입력으로 받는다. 이 값은 [`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) `_build_entry_ai_price_context()`가 만든다.

| 키 | 의미 |
| --- | --- |
| `reference_target_price` | 휴리스틱 기준가 |
| `defensive_order_price` | latency/호가 기반 방어 제출가 |
| `resolved_order_price` | P1 resolver가 결정한 현재 주문가 |
| `price_below_bid_bps` | 현재 주문가의 best bid 대비 괴리 |
| `latency_state`, `ws_age_ms`, `ws_jitter_ms`, `spread_ratio`, `quote_stale` | 제출 직전 품질 맥락 |
| `signal_score` | 현재 종목의 실시간 AI score |
| `orderbook_micro` | OFI/QI 기반 micro snapshot |

### 4.5 `position_ctx` / `realtime_ctx`

`evaluate_scalping_holding_flow()`와 `evaluate_scalping_overnight_decision()`은 별도 포지션 컨텍스트를 받는다.

| 함수 | 주요 키 |
| --- | --- |
| `evaluate_scalping_holding_flow()` | `exit_rule`, `buy_price`, `curr_price`, `profit_rate`, `peak_profit`, `drawdown`, `held_sec`, `current_ai_score`, `worsen_pct` |
| `evaluate_scalping_overnight_decision()` | `position_status`, `avg_price`, `curr_price`, `pnl_pct`, `held_minutes`, `vwap_price`, `prog_net_qty`, `daily_setup_desc`, `score`, `conclusion` |

---

## 5. 스캘핑 feature packet 상세

스캘핑 진입/보유 판단의 정량 입력은 [`scalping_feature_packet.py`](../../src/engine/scalping_feature_packet.py) `extract_scalping_feature_packet()`에서 계산된다.

### 5.1 호가 기반 피처

| 피처 | 계산 의미 |
| --- | --- |
| `spread_krw`, `spread_bp` | 최우선 매도/매수 호가 차이 |
| `top1_depth_ratio`, `top3_depth_ratio` | 상위 호가 매도/매수 depth 비율 |
| `orderbook_total_ratio` | 총매도/총매수 잔량 비율 |
| `micro_price`, `microprice_edge_bp` | 최우선 bid/ask 잔량 가중 micro price |

### 5.2 체결 기반 피처

| 피처 | 계산 의미 |
| --- | --- |
| `buy_pressure_10t` | 최근 10틱 매수 체결 비중 |
| `net_aggressive_delta_10t` | 최근 10틱 순매수 체결량 |
| `price_change_10t_pct` | 최근 10틱 가격 변화율 |
| `recent_5tick_seconds`, `prev_5tick_seconds` | 최근/직전 5틱 소요 시간 |
| `tick_acceleration_ratio` | 최근 5틱 체결속도 가속도 |
| `same_price_buy_absorption` | 동일 가격 BUY 반복 흡수 횟수 |
| `large_sell_print_detected`, `large_buy_print_detected` | 평균 대비 대형 SELL/BUY print 여부 |

### 5.3 분봉 기반 피처

| 피처 | 계산 의미 |
| --- | --- |
| `distance_from_day_high_pct` | 당일 고점 대비 현재 위치 |
| `intraday_range_pct` | 당일 변동폭 |
| `volume_ratio_pct` | 직전 분봉 평균 대비 거래량 배율 |
| `curr_vs_micro_vwap_bp` | 현재가의 micro VWAP 대비 위치 |
| `curr_vs_ma5_bp` | 현재가의 MA5 대비 위치 |
| `micro_vwap_value`, `ma5_value` | 기준값 원본 |

### 5.4 감사 필드

`build_scalping_feature_audit_fields()`는 AI 응답에 아래 필드를 덧붙인다.

- `scalp_feature_packet_version`
- `tick_acceleration_ratio_sent`
- `same_price_buy_absorption_sent`
- `large_sell_print_detected_sent`
- `ask_depth_ratio_sent`

즉, 현재 구현은 "어떤 feature를 계산했는가"뿐 아니라 "그 feature가 실제 AI 호출 payload에 포함되었는가"를 같이 남긴다.

---

## 6. 함수별 상세

### 6.1 `analyze_target()`

**역할**

- 스캘핑 진입/보유 라벨링의 기본 엔트리 포인트다.
- `prompt_profile`에 따라 진입 전용, 보유 전용, 공용(shared) 프롬프트를 분기한다.

**입력**

| 인자 | 설명 |
| --- | --- |
| `target_name` | 종목명 |
| `ws_data` | 실시간 스냅샷 |
| `recent_ticks` | 최근 체결 리스트 |
| `recent_candles` | 최근 분봉 리스트 |
| `strategy` | `SCALPING` 또는 스윙 계열 |
| `program_net_qty` | 스윙 경로에서 쓰는 프로그램 순매수 |
| `cache_profile` | `default`, `holding`, `condition_*`, `shadow` 등 |
| `prompt_profile` | `shared`, `watching`, `holding`, `exit` |

**프롬프트 분기**

| `prompt_profile` | 실제 프롬프트 | `prompt_type` | schema |
| --- | --- | --- | --- |
| `shared` | `SCALPING_SYSTEM_PROMPT` | `scalping_shared` | `entry_v1` |
| `watching` | `SCALPING_WATCHING_SYSTEM_PROMPT` | `scalping_entry` | `entry_v1` |
| `holding` / `exit` | `SCALPING_HOLDING_SYSTEM_PROMPT` | `scalping_holding` | `holding_exit_v1` |

**핵심 로직**

1. 분석 캐시를 먼저 조회한다.
2. 캐시 미스면 클래스 단일 락을 non-blocking으로 획득한다.
3. `ai_disabled`면 `DROP 0` 또는 보수 fallback을 반환한다.
4. `min_interval` 쿨타임 미충족 시 `WAIT 50`을 반환한다.
5. 스캘핑이면 `_format_market_data()`로 정량 피처, 분봉, 호가, 최근 틱을 텍스트 payload로 조합한다.
6. Tier1 Gemini 모델로 JSON 호출을 수행한다.
7. 진입 경로이면 `_apply_remote_entry_guard()`로 과도한 BUY를 `WAIT`로 낮출 수 있다.
8. `_normalize_scalping_action_schema()`로 entry/holding 액션 스키마를 정규화한다.
9. feature audit fields와 AI 메타를 붙여 반환한다.

**출력**

| 필드 | 설명 |
| --- | --- |
| `action` | entry 경로: `BUY/WAIT/DROP`, holding 경로: legacy 호환값 `WAIT/SELL/DROP` |
| `action_v2` | entry 경로: `BUY/WAIT/DROP`, holding 경로: `HOLD/TRIM/EXIT` |
| `score` | 0~100 |
| `reason` | 한 줄 근거 |
| `action_schema` | `entry_v1` 또는 `holding_exit_v1` |
| 감사 필드 | feature packet sent 여부 |
| AI 메타 | `ai_parse_ok`, `ai_parse_fail`, `ai_response_ms`, `ai_prompt_type`, `ai_prompt_version`, `ai_result_source`, `cache_hit`, `cache_mode` |

**호출 주기**

- WATCHING 경로에서는 `AI_WATCHING_COOLDOWN` 기본 `60초`가 지난 VIP target에 대해 호출된다.
- HOLDING refresh 경로에서는 손익/시간대에 따라 `3~15초` 최소 간격, `20~60초` 최대 간격, 가격 변화폭 조건을 만족할 때 호출된다.
- `cache_profile="holding"`일 때는 미세한 WS 잡음을 버킷화한 캐시 키를 사용한다.

**사용상 주의**

- 진입과 보유는 같은 함수지만 `prompt_profile`과 `schema`가 다르다.
- holding 경로는 `action_v2`를 표준으로 보고, `action`은 기존 호출부 호환용이다.
- shared lock을 사용하므로, 다른 장문의 AI 호출과 같은 시점에 경합이 생기면 즉시 `WAIT 50` 보수 응답으로 빠질 수 있다.

### 6.2 `evaluate_scalping_entry_price()`

**역할**

- BUY/submitted 후보가 이미 통과한 뒤, 제출 직전 실제 주문가를 재판정한다.
- 매수 여부를 다시 고르는 함수가 아니라 `가격 결정` 함수다.

**입력**

| 인자 | 설명 |
| --- | --- |
| `stock_name`, `stock_code` | 종목 식별자 |
| `ws_data` | 제출 직전 실시간 스냅샷 |
| `recent_ticks`, `recent_candles` | 최근 체결/분봉 |
| `price_ctx` | P1 resolver 결과 + latency + orderbook micro 컨텍스트 |

**핵심 로직**

1. shared lock을 non-blocking으로 획득한다.
2. 실패하거나 `ai_disabled`면 `USE_DEFENSIVE` 폴백을 즉시 반환한다.
3. `ws_data`, 최근 20틱, 최근 20분봉, `price_context`를 JSON으로 직렬화한다.
4. Tier2 Gemini 모델로 `entry_price_v1` schema 호출을 수행한다.
5. `normalize_scalping_entry_price_result()`로 `action/order_price/confidence/reason/max_wait_sec`를 정규화한다.

**출력**

| 필드 | 설명 |
| --- | --- |
| `action` | `USE_DEFENSIVE`, `USE_REFERENCE`, `IMPROVE_LIMIT`, `SKIP` |
| `order_price` | 실제 제출가 후보 |
| `confidence` | 0~100 |
| `reason` | 가격결정 근거 |
| `max_wait_sec` | 주문 유지 허용 시간 |
| AI 메타 | `ai_parse_ok`, `ai_parse_fail`, `ai_response_ms`, `ai_result_source` 등 |

**실전 사용법**

- 직접 주문 전에만 호출해야 한다.
- shadow-only로 돌리는 경로는 현재 운영 규칙상 허용되지 않는다.
- `SKIP`도 low-confidence이면 채택하지 않고 P1 가격으로 fail-closed 해야 한다.

**실제 호출부 후처리**

[`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) `_apply_entry_ai_price_canary()`는 반환값을 받아 아래 순서로 후처리한다.

1. parse fail 또는 low confidence면 P1 resolver로 폴백
2. `SKIP`이면 주문 자체를 비우고 skip follow-up 상태를 기록
3. `USE_REFERENCE/IMPROVE_LIMIT/USE_DEFENSIVE`면 후보 가격을 검증
4. best ask 초과, pre-submit guard 위반이면 폴백
5. 최종 주문가와 `max_wait_sec`를 실제 주문 metadata에 반영

**호출 주기**

- latency gate와 P1 resolver가 모두 지나간 뒤, 주문 번들 제출 직전 1회 호출된다.
- 내부 캐시는 없고, 호출될 때마다 실제 Gemini API를 탄다.

### 6.3 `evaluate_scalping_holding_flow()`

**역할**

- 기존 청산 후보를 즉시 실행할지, 일시 보류할지, 흐름상 EXIT가 맞는지 재판정한다.
- score cutoff가 아니라 `flow_state/thesis/evidence` 중심 판정을 담당한다.

**입력**

| 인자 | 설명 |
| --- | --- |
| `stock_name`, `stock_code` | 종목 식별자 |
| `ws_data` | 실시간 스냅샷 |
| `recent_ticks`, `recent_candles` | 긴 입력 윈도 |
| `position_ctx` | 손익/보유시간/현재 AI 점수/후보 exit_rule |
| `flow_history` | 최근 5개 review history |
| `decision_kind` | `intraday_exit`, `overnight_sell_today` 등 |

**핵심 로직**

1. shared lock을 non-blocking으로 획득한다.
2. lock 실패 또는 `ai_disabled`면 보수적으로 `EXIT`를 반환한다.
3. `_format_scalping_holding_flow_context()`로 흐름 요약 텍스트를 만든다.
4. Tier2 Gemini 모델로 `holding_exit_flow_v1` schema 호출을 수행한다.
5. `_normalize_holding_flow_result()`로 `action/score/flow_state/thesis/evidence/reason/next_review_sec`를 정규화한다.

**출력**

| 필드 | 설명 |
| --- | --- |
| `action` | `HOLD`, `TRIM`, `EXIT` |
| `score` | 0~100 |
| `flow_state` | 흡수/회복/분배/붕괴/소강 계열 |
| `thesis` | 현재 포지션 thesis |
| `evidence` | 근거 리스트 |
| `reason` | 최종 판단 근거 |
| `next_review_sec` | 다음 재검문 권장 간격 |

**실전 사용법**

- 일반 HOLDING score refresh와 별개다.
- 이미 `exit_rule` 후보가 잡혔을 때만 override 호출부에서 사용한다.
- `TRIM`은 현재 v1에서 부분청산 실행 지시가 아니라 "전량청산 보류 + 리스크 축소 선호" 라벨이다.

**호출 주기**

- `holding_flow_override`에서는 `30~90초` review cadence와 `0.35%p` 가격 변화 트리거를 만족할 때 재호출된다.
- `90초` 최대 보류, `0.80%p` 추가악화, WS stale, context fetch 실패, no recent ticks는 override를 강제 종료한다.

### 6.4 `evaluate_scalping_overnight_decision()`

**역할**

- `15:20 KST` 기준 스캘핑 포지션을 `SELL_TODAY` 또는 `HOLD_OVERNIGHT`로 선행 판정한다.

**입력**

| 인자 | 설명 |
| --- | --- |
| `stock_name`, `stock_code` | 종목 식별자 |
| `realtime_ctx` | 포지션 상태, 손익, VWAP, 프로그램 수급, 일봉 구조 등 |

**핵심 로직**

1. shared lock 안에서 실행된다.
2. Tier2 Gemini 모델로 `overnight_v1` schema 호출을 수행한다.
3. 허용 action이 아니면 `SELL_TODAY`로 강제 보정한다.
4. 예외 시 `SELL_TODAY` 보수 폴백을 반환한다.

**출력**

| 필드 | 설명 |
| --- | --- |
| `action` | `SELL_TODAY`, `HOLD_OVERNIGHT` |
| `confidence` | 0~100 |
| `reason` | 판단 근거 |
| `risk_note` | 핵심 리스크 |

**호출 주기**

- [`sniper_overnight_gatekeeper.py`](../../src/engine/sniper_overnight_gatekeeper.py) `run_scalping_overnight_gatekeeper()`에서 `SCALPING_OVERNIGHT_DECISION_TIME=15:20:00` 기준 1회 실행된다.
- 결과가 `SELL_TODAY`이면 같은 함수에서 `evaluate_scalping_holding_flow(..., decision_kind="overnight_sell_today")` 재검문이 이어질 수 있다.

### 6.5 `evaluate_condition_entry()` / `evaluate_condition_exit()`

**역할**

- 조건검색 전용 프롬프트를 유지하지 않고, 스캘핑 진입/보유 경로를 재사용해 legacy 응답 형태로 변환한다.

**의미**

- 조건검색도 더 이상 `ai_engine.py` 안에서 별도 AI 계약을 가지지 않는다.
- normalization 관점에서는 "조건검색 꼬임"을 줄이는 대신, 스캘핑 공용 경로에 의존성을 몰아넣는 구조다.

---

## 7. 호출 주기 및 운용 cadence

| 경로 | 트리거 | 기본 cadence | 비고 |
| --- | --- | --- | --- |
| WATCHING `analyze_target()` | VIP target + AI cooldown 경과 | 종목당 대략 `60초` 간격 | orderbook + recent ticks 필요 |
| HOLDING `analyze_target()` | 손익/시간/가격 변화 충족 | critical zone `3~20초`, normal `15~60초` | fast signature로 skip 가능 |
| `evaluate_scalping_entry_price()` | latency pass 이후 제출 직전 | 주문 후보당 1회 | 캐시 없음 |
| `evaluate_scalping_holding_flow()` intraday | 기존 청산 후보 발생 후 | `30~90초` 재검문 | `0.80%p` 추가악화 또는 `90초` 상한 |
| `evaluate_scalping_overnight_decision()` | 장마감 선행 판정 | `15:20 KST` 1회 | 결과에 따라 flow 재검문 연쇄 |
| `evaluate_scalping_holding_flow()` overnight | `SELL_TODAY` 판정 후 | 같은 슬롯 내 1회 | `HOLD_OVERNIGHT` override 가능 |
| `sniper_analysis.py` 진단용 `analyze_target()` | 운영자 질의/진단 | 수동/보조 | 실주문 경로 아님 |

---

## 8. 공유 인프라와 꼬임 지점

### 8.1 단일 클래스 락

`GeminiSniperEngine`은 `self.lock` 하나를 아래 경로가 같이 쓴다.

- `analyze_target()`
- `evaluate_scalping_entry_price()`
- `evaluate_scalping_holding_flow()`
- `evaluate_scalping_overnight_decision()`
- `generate_realtime_report()`
- `analyze_scanner_results()`
- `generate_eod_tomorrow_bundle()`

즉, 스캘핑 진입/청산 판단과 텔레그램 보고서/브리핑 생성이 같은 락을 공유한다. 이 구조는 "스캘핑 로직 자체"보다 "이질적 AI 작업 간 경합"이 꼬임을 만드는 지점이다.

### 8.2 공용 실패 상태

공용 상태는 아래와 같다.

| 상태 | 의미 |
| --- | --- |
| `consecutive_failures` | 누적 실패 횟수 |
| `ai_disabled` | 실전 분석 엔진 비활성화 스위치 |
| `last_call_time` / `min_interval` | 최소 호출 간격 제어 |

`analyze_target()`는 연속 실패가 `max_consecutive_failures`를 넘으면 엔진 전체를 비활성화한다. 반면 `evaluate_scalping_entry_price()`와 `evaluate_scalping_holding_flow()`는 실패 횟수는 올리지만 직접 disable까지는 하지 않는다. 즉, 실패 집계와 비활성화 정책이 surface별로 완전히 대칭적이지 않다.

### 8.3 캐시 정책 분리

| 캐시 | 목적 | 기본 TTL |
| --- | --- | --- |
| `_analysis_cache` | entry/holding/condition/shadow 분석 캐시 | `8초` |
| `_analysis_cache` + `holding` profile | holding refresh 전용 coarsened cache | 최소 `30초` |
| `_gatekeeper_cache` | 텍스트 리포트 기반 gatekeeper 캐시 | `12초` |

`evaluate_scalping_entry_price()`와 `evaluate_scalping_holding_flow()`는 캐시를 쓰지 않는다. 따라서 이 두 경로는 실제 live API 의존성이 더 크다.

### 8.4 계약과 스키마

`_call_gemini_safe()`는 현재 다음 schema name을 직접 받는다.

- `entry_v1`
- `holding_exit_v1`
- `entry_price_v1`
- `holding_exit_flow_v1`
- `overnight_v1`
- `eod_top5_v1`

즉, `ai_engine.py`는 단순 프롬프트 파일이 아니라 endpoint별 JSON 계약의 중앙 허브다.

---

## 9. 연계 코드베이스

| 파일 | 역할 |
| --- | --- |
| [`runtime_ai_router.py`](../../src/engine/runtime_ai_router.py) | Gemini/OpenAI/DeepSeek 라우팅 선택. 기본 live route는 `gemini` |
| [`scalping_feature_packet.py`](../../src/engine/scalping_feature_packet.py) | 스캘핑 정량 피처 계산 |
| [`sniper_state_handlers.py`](../../src/engine/sniper_state_handlers.py) | WATCHING/HOLDING 상태머신, entry price canary, holding flow override |
| [`sniper_overnight_gatekeeper.py`](../../src/engine/sniper_overnight_gatekeeper.py) | `15:20 KST` 오버나이트 판정과 `SELL_TODAY` 재검문 |
| [`ai_response_contracts.py`](../../src/engine/ai_response_contracts.py) | response schema registry |
| [`ai_engine_openai.py`](../../src/engine/ai_engine_openai.py) | OpenAI parity 구현체 |
| [`ai_engine_deepseek.py`](../../src/engine/ai_engine_deepseek.py) | DeepSeek parity 구현체 |
| [`src/tests/test_ai_engine_cache.py`](../../src/tests/test_ai_engine_cache.py) | 캐시/프롬프트 프로파일 회귀 검증 |
| [`src/tests/test_orderbook_stability_observer.py`](../../src/tests/test_orderbook_stability_observer.py) | OFI/QI orderbook micro 기초 검증 |
| [`src/trading/entry/orderbook_stability_observer.py`](../../src/trading/entry/orderbook_stability_observer.py) | entry price P2의 orderbook micro upstream |

---

## 10. 현재 작업 계획

기준 시점은 `2026-05-02 KST`이며, 현재 open owner는 Plan Rebase와 `2026-05-04`, `2026-05-06` checklist 기준으로 정리한다.

### 10.1 현재 active 또는 다음 운영일 확인 대상

| 축 | 현재 상태 | owner / 다음 판정 |
| --- | --- | --- |
| `dynamic_entry_price_resolver_p1` | active baseline 경로 | `2026-05-04 PREOPEN/INTRADAY` health check |
| `dynamic_entry_ai_price_canary_p2` | active canary | `2026-05-04 PREOPEN` 로드 확인, `2026-05-04 POSTCLOSE` keep/OFF 판정 |
| `SCALPING_ENTRY_PRICE_ORDERBOOK_MICRO_ENABLED` | P2 내부 입력으로만 ON | `2026-05-02` 설계/적용 완료, `2026-05-04 POSTCLOSE` direction/hard 판정 |
| `holding_flow_override` | `2026-05-04` 장전부터 운영 override | `2026-05-04 PREOPEN`, `INTRADAY`, `15:20`, `POSTCLOSE` 판정 |
| `evaluate_scalping_overnight_decision` 경로 | `15:20 KST` 오버나이트 선행 판정 경로 | `2026-05-04` 오버나이트 슬롯에서 실제 실행 확인 |

### 10.2 현재 flag-off / observe / backlog 대상

| 축 | 현재 상태 | owner / 다음 판정 |
| --- | --- | --- |
| Gemini `system_instruction` 분리 | flag-off/backlog | `2026-05-06 AIEngineFlagOffBacklog0506` |
| Gemini deterministic JSON config | flag-off/backlog | `2026-05-06 AIEngineFlagOffBacklog0506` |
| Gemini schema registry live enable | flag-off observe | `2026-05-06 AIEngineFlagOffBacklog0506` |
| DeepSeek retry/gatekeeper structured-output/holding cache/Tool Calling | backlog 또는 flag-off observe | `2026-05-06 AIEngineFlagOffBacklog0506` |
| OpenAI schema/deterministic config | flag-off observe | `2026-05-04` parity 확인 후 `2026-05-06` 재분류 |
| OpenAI Responses WS | shadow-only observe | `2026-05-04 INTRADAY/POSTCLOSE` |
| OpenAI/DeepSeek live scalping routing | 미승인 | 별도 checklist 없이는 enable 금지 |

### 10.3 decision-support 후속

| 축 | 현재 상태 | owner / 다음 판정 |
| --- | --- | --- |
| `holding_exit_decision_matrix` ADM-1 | report-only | `2026-05-06 AIDecisionMatrix0506` |
| `statistical_action_weight` | report-only | `2026-05-06` 이후 markdown/advanced axes |

### 10.4 현재 계획에 포함되지 않는 항목

아래 항목은 현재 open owner가 아니다.

- legacy fallback/scout/split-entry 재개
- Gemini/OpenAI live A/B 재개
- `buy_recovery_canary` 재승격
- standalone 신규 entry shadow

즉, 정상화의 현재 방향은 "AI 라우팅 확대"가 아니라 "기존 Gemini 기본 경로 위에서 entry price/holding flow 축을 정리하고, 나머지 AI infra 변경은 flag-off로 분리"하는 쪽이다.

---

## 11. 정상화 해석 포인트

1. `analyze_target()`와 `evaluate_scalping_entry_price()`는 같은 AI 엔진 파일에 있지만, 전자는 `판단`, 후자는 `가격결정`이다. 두 축을 같은 성과 표본으로 합치면 원인귀속이 깨진다.
2. `analyze_target()`의 holding refresh와 `evaluate_scalping_holding_flow()`는 둘 다 HOLDING에서 쓰이지만 역할이 다르다. 전자는 점수 refresh, 후자는 기존 청산 후보 override다.
3. `evaluate_scalping_overnight_decision()`과 `evaluate_scalping_holding_flow(... overnight_sell_today)`는 2단 구조다. 오버나이트는 단일 AI 판정으로 끝나지 않는다.
4. condition entry/exit는 더 이상 독립 AI 경로가 아니라 스캘핑 공용 경로 어댑터다. 조건검색 이슈도 결국 스캘핑 공용 계약을 점검해야 풀린다.
5. `ai_engine.py`의 스캘핑 정상화는 "프롬프트 문구 수정"만으로 닫히지 않는다. 호출주기, 캐시 profile, shared lock, fail-closed 정책, schema contract를 함께 봐야 한다.

---

## 12. 참고 테스트

현재 스캘핑 관련 회귀 확인에 직접 연결되는 테스트는 최소 아래와 같다.

- [`src/tests/test_ai_engine_cache.py`](../../src/tests/test_ai_engine_cache.py)
- [`src/tests/test_orderbook_stability_observer.py`](../../src/tests/test_orderbook_stability_observer.py)
- [`src/tests/test_sniper_scale_in.py`](../../src/tests/test_sniper_scale_in.py)

이 중 `test_ai_engine_cache.py`는 entry/holding prompt profile, analysis cache, gatekeeper cache의 버킷화와 TTL 가정을 검증한다.

