# 시장시간 하드코딩 점검 및 오프셋 전환 후보

## 목적

한국 주식시장 개장/폐장 시간이 변경될 때 영향을 받는 하드코딩 시간을 점검하고, 절대 시각 대신 `시장 기준 시각 + 오프셋` 형태로 바꿔야 할 지점을 정리한다.

기준이 되는 현재 중앙 설정은 아래다.

- `MARKET_OPEN_TIME`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L154)
- `SCALPING_EARLIEST_BUY_TIME`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L155)
- `SWING_EARLIEST_BUY_TIME`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L156)
- `SCALPING_NEW_BUY_CUTOFF`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L157)
- `SCALPING_OVERNIGHT_DECISION_TIME`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L158)
- `MARKET_CLOSE_TIME`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L159)
- `SYSTEM_SHUTDOWN_TIME`: [src/utils/constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py#L160)
- 중앙 시간 변환 레이어: [src/engine/sniper_time.py](/home/ubuntu/KORStockScan/src/engine/sniper_time.py)

## 요약

이미 `constants.py`와 `sniper_time.py`로 일부 중앙화는 되어 있지만, 실제 운영 코드에는 아직 시장 시간을 직접 박아둔 부분이 남아 있다.

오프셋 전환 우선순위는 아래 순서를 권장한다.

1. 시장 기준시간을 직접 문자열로 비교하는 코드
2. 조건검색 프로파일처럼 여러 구간이 개장/폐장 상대시간으로 표현되는 코드
3. 텔레그램/배치 스케줄처럼 운영상 절대시간이지만 사실상 장 기준으로 움직여야 하는 코드

## 1. 바로 오프셋 전환이 필요한 후보

### `scalping_scanner.py`

- 위치: [src/scanners/scalping_scanner.py](/home/ubuntu/KORStockScan/src/scanners/scalping_scanner.py#L57)
- 현재 값: `09:05:00 ~ 15:00:00`
- 의미:
  - 개장 후 5분부터 스캐너 가동
  - 장 마감 30분 전 신규 스캔 종료
- 문제:
  - 시장이 30분 늦게 열리거나 닫히면 함께 이동해야 하는데 지금은 절대시각이다.
- 권장 오프셋:
  - `SCALPING_SCAN_START_OFFSET_MIN = +5`
  - `SCALPING_SCAN_END_OFFSET_MIN = -30`

### `kosdaq_scanner.py`

- 위치: [src/scanners/kosdaq_scanner.py](/home/ubuntu/KORStockScan/src/scanners/kosdaq_scanner.py#L61)
- 현재 값: `09:05:00 ~ 19:15:00`
- 의미:
  - 스윙 스캔 시작은 개장 후 5분
  - 종료는 시스템/야간 처리 기준에 가까움
- 문제:
  - 시작 시각은 분명히 시장 기준이어야 한다.
  - 종료 시각 `19:15`는 장 종료 기준인지, 시스템 운영 기준인지 정책이 문서화되어 있지 않다.
- 권장 오프셋:
  - 시작: `SWING_SCAN_START_OFFSET_MIN = +5`
  - 종료: 정책 결정 필요
  - 만약 장 기준이면 `SWING_SCAN_END_OFFSET_MIN = +225`
  - 만약 시스템 운영 기준이면 절대시각 상수로 분리

### `sniper_analysis.py`

- 위치: [src/engine/sniper_analysis.py](/home/ubuntu/KORStockScan/src/engine/sniper_analysis.py#L69)
- 현재 값: `09:00:00 ~ 20:00:00`
- 의미:
  - 실시간 종목 분석 허용 시간
- 문제:
  - 메시지는 "정규장"이라고 표현하지만 실제 범위는 장 종료 후 야간까지 포함한다.
  - 시장시간 변경 시 자동 추종되지 않는다.
- 권장 오프셋:
  - 시작: `REALTIME_ANALYSIS_START_OFFSET_MIN = 0`
  - 종료:
    - 장 기준이면 `REALTIME_ANALYSIS_END_OFFSET_MIN`
    - 시스템 기준이면 `SYSTEM_SHUTDOWN_TIME`과 연결

### `sniper_condition_handlers.py`

- 위치: [src/engine/sniper_condition_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_condition_handlers.py#L216)
- 현재 값:
  - `09:00~09:30`
  - `09:20~11:00`
  - `09:40~13:00`
  - `09:40~13:30`
  - `13:00~15:20`
  - `14:30~15:30`
  - `15:30~07:00`
  - `09:00~15:00`
  - `15:30~23:59:59`
  - `09:02~10:30`
  - `09:05~11:00`
- 의미:
  - 조건검색식별자별 허용 시간창
- 문제:
  - 가장 시장시간 민감한 핵심 구간인데 전부 절대시각이다.
  - 개장/폐장 시간 변경 시 거의 전 전략이 어긋난다.
- 권장 오프셋:
  - 각 구간을 `MARKET_OPEN_TIME`, `MARKET_CLOSE_TIME`, `SYSTEM_DAY_END_TIME`, `PREMARKET_START_TIME` 기준 상대 분으로 재정의
  - 예시:
    - `scalp_candid_*`: `open + 0` ~ `open + 30`
    - `scalp_strong_01`: `open + 20` ~ `open + 120`
    - `scalp_afternoon_01`: `open + 240` ~ `close - 10`
    - `kospi_*_swing_01`: `close - 60` ~ `close`
    - `vcp_candid_01`: `close` ~ `next_day_premarket_start`
    - `s15_scan_base`: `open + 2` ~ `open + 90`

## 2. 이미 중앙값을 쓰지만, 오프셋 구조로 더 정리하면 좋은 곳

### `kiwoom_sniper_v2.py`

- 주요 위치:
  - [src/engine/kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py#L396)
  - [src/engine/kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py#L410)
  - [src/engine/kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py#L839)
  - [src/engine/kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py#L925)
- 상태:
  - `sniper_time.py`를 통해 중앙 시간 상수를 잘 참조하고 있다.
- 추가 정리 포인트:
  - 현재는 `TIME_09_03`, `TIME_09_05`, `TIME_15_30` 같은 "결과 시각 상수" 중심이다.
  - 향후 장시간 변경 대응을 더 쉽게 하려면 "의미 기반 오프셋" 이름이 더 적합하다.
- 권장 방향:
  - `TIME_09_03` 대신 `MARKET_OPEN_TIME + 3분`
  - `TIME_09_05` 대신 `MARKET_OPEN_TIME + 5분`
  - `TIME_15_30` 대신 `MARKET_CLOSE_TIME`

### `sniper_state_handlers.py`

- 주요 위치:
  - [src/engine/sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py#L406)
  - [src/engine/sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py#L424)
  - [src/engine/sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py#L1602)
- 상태:
  - 대부분 중앙값을 쓰고 있다.
  - 특히 `MARKET_CLOSE_TIME - 5분`, `SCALPING_NEW_BUY_CUTOFF`처럼 이미 상대 개념이 드러난다.
- 추가 정리 포인트:
  - `MARKET_CLOSE_TIME - 5분`은 코드 안에서 직접 계산하지 말고 별도 규칙명으로 빼는 편이 낫다.
- 권장 오프셋:
  - `NO_SCALE_IN_BEFORE_CLOSE_OFFSET_MIN = -5`

### `sniper_execution_receipts.py`

- 위치: [src/engine/sniper_execution_receipts.py](/home/ubuntu/KORStockScan/src/engine/sniper_execution_receipts.py#L639)
- 상태:
  - `TIME_15_30`를 사용하므로 직접 하드코딩 문제는 작다.
- 추가 정리 포인트:
  - "스캘핑 부활 가능 마감시각"이라는 의미 상수를 따로 두면 의도가 더 분명해진다.

## 3. 시장 기준으로 바꿀지 정책 확인이 필요한 운영 스케줄

### `bot_main.py`

- 위치:
  - [src/bot_main.py](/home/ubuntu/KORStockScan/src/bot_main.py#L252)
  - [src/bot_main.py](/home/ubuntu/KORStockScan/src/bot_main.py#L262)
  - [src/bot_main.py](/home/ubuntu/KORStockScan/src/bot_main.py#L266)
- 현재 값:
  - 아침 브로드캐스트 `08:50`
  - 장 마감 요약 `15:40`
  - 시스템 재시작 `23:50`
- 분류:
  - `23:50` 재시작은 시장과 무관한 운영 시각이라 절대시각 유지 가능
  - `08:50`, `15:40`은 시장과 연동될 가능성이 높다
- 권장 오프셋:
  - 아침 브로드캐스트: `MARKET_OPEN_TIME - 10분`
  - 장 마감 요약: `MARKET_CLOSE_TIME + 10분`

### `sniper_overnight_gatekeeper.py`

- 위치:
  - [src/engine/sniper_overnight_gatekeeper.py](/home/ubuntu/KORStockScan/src/engine/sniper_overnight_gatekeeper.py#L140)
  - [src/engine/sniper_overnight_gatekeeper.py](/home/ubuntu/KORStockScan/src/engine/sniper_overnight_gatekeeper.py#L207)
- 상태:
  - 실행 자체는 상위 호출부에서 `TIME_SCALPING_OVERNIGHT_DECISION`을 사용해 제어된다.
  - 다만 로그/문구에는 `15:30`가 박혀 있다.
- 권장 방향:
  - 기능상 문제는 작지만, 운영 문구도 중앙 상수 기반 문자열로 맞추는 편이 좋다.

## 4. 유지해도 되는 시간

아래는 시장 개폐시간 변경과 직접 연동되지 않으므로, 굳이 오프셋화하지 않아도 된다.

- `last_closed_msg_time > 3600` 같은 도배 방지 주기: [src/scanners/scalping_scanner.py](/home/ubuntu/KORStockScan/src/scanners/scalping_scanner.py#L62)
- DB poll 5초, FIFO 10초, 계좌 동기화 90초: [src/engine/kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py#L851)
- 시스템 일일 재시작 `23:50`: [src/bot_main.py](/home/ubuntu/KORStockScan/src/bot_main.py#L266)

이 값들은 "시장 기준 시각"이 아니라 "시스템 동작 주기"다.

## 5. 권장 리팩터링 방향

### A. 절대시각 상수보다 기준+오프셋 상수로 전환

예시 이름:

- `MARKET_OPEN_TIME`
- `MARKET_CLOSE_TIME`
- `PREMARKET_START_TIME`
- `SYSTEM_SHUTDOWN_TIME`
- `SCALPING_SCAN_START_OFFSET_MIN`
- `SCALPING_SCAN_END_OFFSET_MIN`
- `MORNING_REPORT_OFFSET_MIN`
- `ENTRY_METRICS_REPORT_OFFSET_MIN`
- `SCALPING_OVERNIGHT_DECISION_OFFSET_MIN`
- `NO_SCALE_IN_BEFORE_CLOSE_OFFSET_MIN`

### B. `sniper_time.py`를 "시간 계산기"로 확장

현재는 문자열을 `time` 객체로 바꾸는 역할이 중심이다. 여기에 아래 성격의 헬퍼를 두면 전체 코드가 단순해진다.

- `time_from_open(offset_min)`
- `time_from_close(offset_min)`
- `in_market_offset_window(now, start_offset_min, end_offset_min)`

### C. 조건검색 프로파일은 데이터화

`resolve_condition_profile()`의 다수 `if/elif` 구간은 하드코딩 시간이 가장 많다. 아래처럼 데이터 테이블 구조로 바꾸면 유지보수가 쉬워진다.

- 조건명 패턴
- 전략
- 포지션 태그
- 시작 기준점: `open`, `close`, `premarket`, `day_end`
- 시작 오프셋(분)
- 종료 기준점
- 종료 오프셋(분)

## 6. 우선 작업 추천

1. `sniper_condition_handlers.py` 시간창을 기준점+오프셋 테이블로 변경
2. `scalping_scanner.py`, `kosdaq_scanner.py`, `sniper_analysis.py`의 직접 문자열 시간을 중앙 규칙 참조로 변경
3. `bot_main.py`의 `08:50`, `15:40`을 장 기준 오프셋으로 변경
4. 로그 메시지의 `15:30`, `15:30` 같은 문구도 동적 생성으로 정리

## 7. 이번 점검 결론

시장 개폐시간 변경 대응 관점에서 가장 취약한 곳은 아래 세 군데다.

- 조건검색 시간창 정의: [src/engine/sniper_condition_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_condition_handlers.py#L216)
- 스캐너 운영 시간 체크: [src/scanners/scalping_scanner.py](/home/ubuntu/KORStockScan/src/scanners/scalping_scanner.py#L57)
- 운영 스케줄러의 장 연동 시각: [src/bot_main.py](/home/ubuntu/KORStockScan/src/bot_main.py#L252)

반대로 `kiwoom_sniper_v2.py`, `sniper_state_handlers.py`, `sniper_time.py`는 이미 중앙화 방향으로 잘 가고 있으므로, 여기서는 "절대 시각 이름"을 "시장 기준 오프셋 의미"로 한 단계 더 추상화하면 된다.
