# Latency-Aware Entry System 작업 요약

## 목표
웹소켓과 API latency 때문에 신호 시점 가격보다 늦게 진입해 휩소를 맞는 문제를 줄이기 위해, 기존 스나이퍼 엔진에 latency-aware 진입 제어를 추가했다.

핵심 목표는 아래와 같다.

- 신호 발생 시점의 가격과 시간을 고정한다.
- 주문 직전 현재가 재조회 API를 반복 호출하지 않는다.
- 내부 최신 websocket 캐시만으로 진입 유효성을 판단한다.
- 늦었으면 진입하지 않는다.
- 상태가 애매하면 fallback 진입을 허용한다.
- 위험 상태면 신규 진입을 전면 차단한다.
- 모든 판단/주문/체결을 운영 로그와 텔레그램에서 추적 가능하게 한다.

## 핵심 정책

### 상태 분류
- `SAFE`
- `CAUTION`
- `DANGER`

### 정책
- `SAFE`: 일반 진입 허용
- `CAUTION`: `scout + main` fallback 진입 허용
- `DANGER`: 신규 진입 차단

### 운영 원칙
- 신호 시점 가격/시간은 freeze 한다.
- 주문 직전 API 재조회는 하지 않는다.
- fallback은 늦은 진입을 억지로 살리는 장치가 아니라, 애매한 latency 구간을 분해하는 장치로 쓴다.
- DANGER에서는 fallback도 허용하지 않는다.
- 미체결 후 같은 신호 기준 상향 정정/재추격은 하지 않는다.

## 신규 구현 계층

### 독립 진입 계층
`src/trading/...` 아래에 latency-aware 진입 계층을 추가했다.

- `src/trading/entry/entry_types.py`
- `src/trading/config/entry_config.py`
- `src/trading/order/tick_utils.py`
- `src/trading/market/market_data_cache.py`
- `src/trading/entry/latency_monitor.py`
- `src/trading/entry/entry_policy.py`
- `src/trading/entry/normal_entry_builder.py`
- `src/trading/entry/fallback_strategy.py`
- `src/trading/order/order_manager.py`
- `src/trading/entry/state_machine.py`
- `src/trading/logging/trade_logger.py`
- `src/trading/logging/metrics_recorder.py`
- `src/trading/entry/entry_orchestrator.py`

### 엔진 브리지
기존 엔진에 붙이기 위한 브리지 모듈:

- `src/engine/sniper_entry_latency.py`

역할:
- 신호 시점 가격/시간 freeze
- websocket cache 기반 quote health 계산
- latency 상태 판정
- entry policy 평가
- SAFE면 normal order plan 생성
- CAUTION이면 fallback order plan 생성
- 기존 엔진이 이해할 수 있는 형태로 order bundle 반환

## 기존 엔진 반영 사항

### WATCHING 신규 진입
수정 파일:
- `src/engine/sniper_state_handlers.py`

반영 내용:
- 신규 BUY 직전에 latency-aware gate 적용
- `SAFE`면 일반 진입
- `CAUTION`이면 fallback `scout + main` 진입
- `DANGER`, timeout, slippage 초과면 진입 차단
- SCALPING 지정가 BUY는 더 방어적인 가격으로 조정

### S15 fast-track
수정 파일:
- `src/engine/sniper_s15_fast_track.py`

반영 내용:
- 기존 `+2틱` 공격 진입 제거
- latency-aware gate 편입
- pause 상태에서 정책 차단
- latency 차단 시 `FAILED/EXPIRED`가 아니라 정책 차단으로 기록

### 체결 영수증 처리 확장
수정 파일:
- `src/engine/sniper_execution_receipts.py`

반영 내용:
- 종목당 단일 BUY_ORDERED 가정에서 복수 entry order bundle 추적으로 확장
- `pending_entry_orders` 메타 도입
- scout/main 복수 fill 누적 처리
- 평균 체결가 / 누적 수량 계산
- fallback bundle 완료 여부 추적

### BUY timeout / 취소 / SELL 전 정리
수정 파일:
- `src/engine/sniper_state_handlers.py`

반영 내용:
- 미해결 entry BUY 묶음 timeout 시 정리
- HOLDING 중 SELL 신호가 나오면 남은 entry BUY 먼저 취소
- partial fill이면 HOLDING 유지
- no fill이면 WATCHING 복귀

## 브로커 주문 표현 보강
수정 파일:
- `src/engine/kiwoom_orders.py`

반영 내용:
- BUY 주문에 `tif` 개념 추가
- 프로젝트 기존 컨벤션에 맞춰 `IOC` BUY를 `16`으로 매핑
- DAY 지정가는 `00` 유지

현재 live fallback BUY 타입은 다음과 같다.

- `fallback_scout`: `16` (`IOC -> 최유리 IOC`)
- `fallback_main`: `00` (`DAY 지정가`)

## pause 기능과의 정합성
기존 긴급 매매중단 기능과 충돌하지 않도록 유지했다.

원칙:
- pause는 신규 BUY / 추가매수만 차단
- SELL / 청산은 계속 허용
- latency-aware 진입도 pause 상태에서는 차단
- S15도 pause 정책에 편입

관련 파일:
- `src/utils/runtime_flags.py`
- `src/engine/trade_pause_control.py`
- `src/notify/telegram_manager.py`

## 운영 로그 보강
추가 로그 예:

- `[LATENCY_ENTRY_DECISION]`
- `[LATENCY_ENTRY_BLOCK]`
- `[LATENCY_ENTRY_ORDER_SENT]`
- `[ENTRY_SUBMISSION_BUNDLE]`
- `[ENTRY_FILL]`
- `[ENTRY_BUNDLE_FILLED]`
- `[ENTRY_TIF_MAP]`

운영자는 장중 로그만으로 아래를 추적할 수 있다.

- 어떤 종목이 SAFE / CAUTION / DANGER였는지
- fallback이 언제 발동했는지
- scout / main이 어떤 타입과 TIF로 나갔는지
- scout만 체결됐는지, bundle 전체가 다 찼는지
- IOC 요청이 실제로 `16`으로 승격됐는지

## 관리자 텔레그램 UI
수정 파일:
- `src/notify/telegram_manager.py`
- `src/engine/sniper_entry_metrics.py`

추가 기능:
- `📊 진입 지표` 버튼
- `/entry_metrics`
- `/진입지표`

조회 가능한 항목:
- SAFE / CAUTION / DANGER 수
- normal / fallback 진입 수
- fallback scout / main 전송 수
- fallback scout / main 체결 수
- fallback bundle 완료 수
- `IOC -> 16` 승격 수

## 장 마감 자동 요약
수정 파일:
- `src/bot_main.py`

반영 내용:
- 장 마감 후 관리자에게 진입 지표 요약을 1회 자동 발송
- 자정 이후 다음 영업일을 위해 발송 플래그 초기화

운영 흐름:
- 장중: 관리자 텔레그램에서 `📊 진입 지표`로 수동 조회
- 장 마감 후: 관리자에게 자동 요약 브로드캐스트

## 테스트
추가/보강 테스트:
- `src/tests/test_sniper_entry_latency.py`
- `src/tests/test_sniper_entry_metrics.py`
- `src/tests/test_sniper_scale_in.py`
- `src/trading/tests/*`

검증 결과:
- `src/tests/test_sniper_entry_metrics.py`
- `src/tests/test_sniper_scale_in.py`
- `src/tests/test_sniper_entry_latency.py`
  - `32 passed`

- `src/trading/tests`
  - `13 passed`

## 현재 운영 상태 요약
현재 시스템은 아래처럼 동작한다.

1. 신호 발생 시점 가격/시간을 고정한다.
2. websocket 캐시로 quote health를 계산한다.
3. latency 상태를 SAFE / CAUTION / DANGER로 분류한다.
4. policy로 timeout / slippage / danger를 판단한다.
5. SAFE면 일반 진입한다.
6. CAUTION이면 scout + main fallback 진입한다.
7. DANGER면 신규 진입을 스킵한다.
8. 체결은 복수 주문까지 누적 추적한다.
9. 남은 entry BUY는 timeout 또는 SELL 전에 정리한다.
10. 운영자는 텔레그램에서 장중/장마감 진입 지표를 바로 확인할 수 있다.

## 남은 TODO
- 장 마감 요약을 `data/report` JSON과 연결
- 웹 리포트에서 latency entry metrics 조회 지원
- broker API 문서 기준 `IOC/cond_uv` 정식 검증
- 장중 metrics를 파일/DB에 구조화 저장
- fallback 성과 분석 리포트 자동화

## 주요 수정 파일
- `src/engine/sniper_entry_latency.py`
- `src/engine/sniper_entry_metrics.py`
- `src/engine/sniper_state_handlers.py`
- `src/engine/sniper_execution_receipts.py`
- `src/engine/sniper_s15_fast_track.py`
- `src/engine/kiwoom_orders.py`
- `src/notify/telegram_manager.py`
- `src/bot_main.py`
- `src/tests/test_sniper_entry_latency.py`
- `src/tests/test_sniper_entry_metrics.py`
- `src/tests/test_sniper_scale_in.py`
