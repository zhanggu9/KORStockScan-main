# IPO Listing-Day Runner 작업결과서

- 제출 대상: 감리인 검토용
- 작성일: 2026-05-10 KST
- 대상 기능: 공모주 상장첫날 YAML-gated 실행 runner
- 관련 산출물:
  - `src/engine/ipo_listing_day_runner.py`
  - `src/engine/kiwoom_websocket.py`
  - `src/utils/kiwoom_utils.py`
  - `src/tests/test_ipo_listing_day_runner.py`
  - `src/tests/test_kiwoom_token_cache.py`
  - `deploy/run_ipo_listing_day_autorun.sh`
  - `deploy/install_ipo_listing_day_autorun_cron.sh`
  - `configs/ipo_listing_day.example.yaml`
  - `docs/time-based-operations-runbook.md`
  - `docs/code-reviews/ipo-listing-day-runner-2026-05-10-code-review-report.md`
  - `.gitignore`

## 1. 작업 목적

공모주 상장첫날의 장전 예상가격 및 개장 직후 호가 변동성을 감시하고, 사용자가 사전에 승인한 YAML 대상 종목에 한해 1회 진입을 시도하는 별도 runner를 구축했다.

본 기능은 기존 스캘핑/스윙 threshold 자동화 체인에 편입하지 않으며, Project, Calendar, runtime env 자동 변경을 수행하지 않는다. 2026-05-10 후속 지시로 당일 YAML 파일이 있을 경우에만 실행하는 cron wrapper를 추가했다.

## 2. 주요 구현 결과

1. 별도 CLI runner와 YAML-gated autorun wrapper를 추가했다.
   - 실행 모듈: `src.engine.ipo_listing_day_runner`
   - 자동 wrapper: `deploy/run_ipo_listing_day_autorun.sh`
   - cron 설치 스크립트: `deploy/install_ipo_listing_day_autorun_cron.sh`
   - 입력 YAML이 승인 artifact 역할을 수행

2. 사용자 지정 종목만 처리하도록 제한했다.
   - `trade_date`와 `listing_date`가 일치하는 enabled target만 선택
   - phase0 기본 `active_symbol_limit=1`
   - 기존 sniper `ACTIVE_TARGETS`를 사용하지 않는 독립 세션 상태 유지

3. 투자금액 상한을 500만원으로 반영했다.
   - YAML의 `budget_cap_krw`가 5,000,000원을 초과해도 실제 산출에는 `effective_budget_cap_krw=5,000,000`을 사용
   - decision fields에 원 입력값, 적용값, 최대값을 모두 기록

4. 장전 및 개장 직후 snapshot 증적을 분리 저장한다.
   - 저장 경로: `data/ipo_listing_day/YYYY-MM-DD/`
   - raw event JSONL, per-symbol decision JSON, end-of-run Markdown summary 생성

5. 주문 및 위험 통제를 구현했다.
   - 실제 매수 주문 가능 시간: `09:00:00~09:00:30 KST`
   - 공모가 대비 premium guard 기본 `250%`
   - quote freshness, VI/호가공백 의심, top 1~3호가 depth `3x` gate
   - OpenAI REPORT tier entry review는 `risk_score >= 80`인 경우에만 hard block
   - `-10%` hard stop, `+20%` 30% 분할익절 후보, AI 보류 조건, 이후 peak 대비 `8%p` trailing, 30분 max hold
   - STOP 파일, 일손실 cap, 주문 실패 cap, global buy pause kill switch

6. Kiwoom token 중복 발급 충돌을 완화했다.
   - `get_kiwoom_token()`은 기본적으로 `data/runtime/kiwoom_token_cache.json` 공유 캐시를 먼저 재사용한다.
   - 새 token 발급이 필요할 때는 `data/runtime/kiwoom_token_cache.lock` 파일 lock을 잡아 프로세스 간 중복 `/oauth2/token` 발급을 막는다.
   - WS 인증 실패 복구 경로만 `force_refresh=True`로 캐시를 우회해 새 token을 발급한다.
   - token cache와 lock 파일은 `.gitignore`에 명시해 커밋 대상에서 제외했다.

## 3. 주식호가잔량(0D) 예상체결가 수집 검토 및 반영

### 판정

`0D` 주식호가잔량을 통해 예상체결가를 추가 수집하는 것은 타당하다. 키움 REST API 문서의 `0D` 실시간 수신 항목에는 호가 잔량뿐 아니라 예상체결 관련 필드가 포함되어 있다.

확인한 주요 필드는 다음과 같다.

- `23`: 예상체결가
- `24`: 예상체결수량
- `200`: 예상체결가전일종가대비
- `201`: 예상체결가전일종가대비등락율
- `238`: 예상체결가전일종가대비기호
- `291`: 예상체결가, 예상체결 시간 동안에만 유효
- `292`: 예상체결량, 예상체결 시간 동안에만 유효
- `293`: 예상체결가전일대비기호
- `294`: 예상체결가전일대비
- `295`: 예상체결가전일대비등락율
- `299`: 전일거래량대비예상체결율

필드 `23`/`24`와 `291`/`292`는 모두 예상체결 가격/수량 계열이지만, `291`~`295`는 예상체결 시간 동안에만 유효한 전용 필드로 구분한다. 구현은 `expected_price = field 291 or field 23`, `expected_qty = field 292 or field 24` 순서로 매핑해 예상체결 전용 필드를 우선 사용하고, 없을 때 기존 예상체결 가격/수량 필드로 fallback한다.

### 반영 내용

기존 Kiwoom WS는 이미 `0D`를 등록하고 1~5호가 잔량을 파싱하고 있었다. 이번 작업에서 `0D` 수신값 중 예상체결 필드를 `expected_open` dict로 보존하도록 보강했다.

IPO runner는 preopen/live snapshot 작성 시 아래 우선순위를 적용한다.

1. `expected_open.price > 0`이면 `indicative_open_price=expected_open.price`, `indicative_open_source=0D_expected_open`, `explicit_expected_open_available=true`
2. 예상체결 필드가 없거나 유효하지 않으면 기존처럼 `ws_curr` fallback, `explicit_expected_open_available=false`

### 감리상 유의점

`0D` 예상체결가는 예상체결 시간 동안 유효한 실시간 필드로 기록하되, 실제 시초가 또는 실제 체결가와 동일하다고 단정하지 않는다. 첫 실전 표본에서는 `0D_expected_open`, 가능 시 `0H` 주식예상체결, 실제 KRX 시초가, Kiwoom 체결 내역을 사후 대사해야 한다.

## 4. YAML-gated 자동 실행 확인

자동 실행은 아래 조건을 모두 만족할 때만 본 runner를 호출한다.

1. `configs/ipo_listing_day_YYYY-MM-DD.yaml` 파일 존재
2. 주말 아님
3. `data/ipo_listing_day/STOP` 파일 없음
4. 동일 날짜 lock 없음
5. `--dry-select` 결과 당일 enabled target 존재

YAML이 없으면 `data/ipo_listing_day/status/ipo_listing_day_YYYY-MM-DD.status.json`에 `status=skipped`, `reason=config_missing`만 남기고 종료한다.

YAML parsing은 PyYAML이 설치되어 있으면 PyYAML을 우선 사용하고, 없으면 `_load_simple_ipo_yaml()` fallback parser를 사용한다. fallback parser는 승인 artifact의 최소 구조만 처리하는 제한적 parser이며, root scalar key와 `targets` 하위의 flat scalar key-value 목록만 지원한다. nested map/list, multi-line scalar, anchor/alias, inline comment가 포함된 값, 복합 target item은 지원하지 않는다. 따라서 실전 승인 YAML은 `configs/ipo_listing_day.example.yaml`과 같은 평면 구조를 유지해야 하며, 자동 실행 전 `--dry-select` 결과로 실제 선택 target과 적용 budget을 확인해야 한다.

## 5. 자동화 체인 비편입 확인

본 작업은 다음 항목을 변경하지 않았다.

- threshold-cycle calibration 후보 생성
- sentinels, bot_main daemon 등록
- runtime env 자동 변경
- GitHub Project 또는 Calendar sync 자동 실행
- 기존 scalping/swing state machine의 실전 판단 로직

## 6. 스캘핑 봇 token 충돌 검토 및 조치

### 검토 결과

IPO runner와 스캘핑 봇은 서로 다른 프로세스지만 동일 Kiwoom 계정 token을 사용한다. 기존 구현은 양쪽 모두 `get_kiwoom_token()` 호출 시 `/oauth2/token`을 직접 호출했으므로, 브로커 정책상 새 token 발급이 기존 token을 무효화하는 경우 스캘핑 봇의 REST/WS 경로가 `8005 Token이 유효하지 않습니다`로 장애를 낼 수 있었다.

### 조치 내용

`get_kiwoom_token()`을 공유 캐시 방식으로 변경했다.

1. 유효한 cache가 있으면 bot, IPO runner, 웹/리포트 경로가 동일 token을 재사용한다.
2. cache miss, 만료, 명시 `force_refresh=True`에서만 새 token을 발급한다.
3. 새 token 발급은 파일 lock 안에서 수행해 동시 실행 프로세스가 중복 발급하지 않도록 한다.
4. cache key는 API base URL과 app key hash를 기준으로 분리해 PROD/DEV token 혼용을 막는다.

### 잔여 유의점

token cache는 중복 발급 충돌을 줄이는 장치이며, Kiwoom 서버 측 인증 장애 자체를 제거하지는 않는다. 실전 중 `8005`가 반복되면 장중 hot-refresh 실험이 아니라 기존 표준대로 graceful restart와 계좌/주문 상태 대사를 우선한다.

### 실제 동시사용 테스트

2026-05-10 KST에 실제 Kiwoom PROD token으로 동시사용 테스트를 수행했다.

테스트 절차:

1. 기존 `data/runtime/kiwoom_token_cache.json`을 백업 후 제거했다.
2. 독립 Python 프로세스 8개를 동시에 실행했다.
3. 각 프로세스가 `get_kiwoom_token()`을 호출하도록 했다.
4. 각 프로세스가 반환받은 token으로 삼성전자 `005930` 기본정보 read-only API를 호출했다.
5. token 원문은 출력하지 않고 SHA-256 hash, 길이, 성공 여부만 비교했다.
6. 테스트 후 임시 worker와 백업 token cache는 삭제하고, 새로 생성된 유효 cache만 유지했다.

테스트 결과:

- 실제 token 발급 대상: Kiwoom PROD `https://api.kiwoom.com`
- 실제 token 발급 설정: `data/config_prod.json`
- 단독 실제 발급 결과: 성공, token length 86, 발급 소요 약 0.110초
- 단독 발급 직후 cache 재사용 확인: 성공
- worker 수: 8
- 모든 worker exit code: 0
- 모든 worker token 획득 성공
- 모든 worker read-only API 호출 성공
- unique token hash count: 1
- 모든 worker token hash가 cache token hash와 일치
- token length: 86
- cache 만료까지 약 86,313초
- 전체 동시 테스트 소요 약 1.32초
- worker별 token 획득 시간: 0.0007초~0.1016초
- worker별 read-only API 호출 시간: 0.0751초~0.0892초
- token cache 파일 권한: `600`
- token lock 파일 권한: `600`

판정: 여러 독립 프로세스가 동시에 실행되어도 공유 cache/file lock 경로로 동일 token을 재사용했고, 동일 token으로 복수 read-only Kiwoom API 호출이 성공했다. IPO runner와 스캘핑 봇의 token 중복 발급 충돌 방지 목적은 실제 동시사용 테스트 기준으로 통과했다.

## 7. AI Provider 호출 빈도

`0D` 예상체결 필드 수집은 WS 파싱 및 event 기록만 추가하므로 AI Provider 호출 빈도를 증가시키지 않는다.

현재 runner 구조 기준 예상 호출 빈도는 다음과 같다.

1. 장전 `08:59:50~09:00:00` snapshot 수집 구간: AI 호출 없음
2. 매수 진입 가능 구간 `09:00:00~09:00:30`: `poll_sec=0.2` 기본값에서 이론상 최대 약 150회 polling iteration이 발생할 수 있음
3. 실제 AI API 호출은 `IpoAiAdvisor` cap으로 제한된다. 기본값은 `max_ai_calls_per_symbol=6`, `max_ai_calls_per_run=10`이며, cap 도달 또는 Provider 미가용 시 `ai_status=skipped`, `reason=call_cap_or_unavailable`로 deterministic gate를 계속 적용한다.
4. 실제로 즉시 진입 성공, terminal block, STOP, premium guard, AI risk block이 발생하면 해당 종목은 완료 처리되어 1회 또는 소수 호출로 종료
5. 보유 중 exit review는 `+20%` 도달 후 첫 분할익절 전 AI 보류 판단이 필요할 때만 호출하며, 같은 run-level cap의 적용을 받는다.
6. hard stop, max-hold, trailing, 일반 exit gate는 AI보다 deterministic guard가 우선

감리상 권고는 다음과 같다.

- 현재 hard cap이 존재하더라도, 실전 운용 전 entry AI review는 종목당 1회 또는 2초 이상 TTL cache로 추가 제한하는 것이 적절하다.
- partial TP defer 판단은 최초 `+20%` 도달 시 1회만 허용하거나, 명시 TTL과 최대 호출 횟수를 둬야 한다.
- 위 호출 제한은 전략 판단 변경이 아니라 Provider 비용, rate limit, 감사 증적 안정성을 위한 운영 guard로 별도 workorder에서 다루는 것이 적절하다.

## 8. 검증 결과

실행한 검증 명령은 다음과 같다.

```bash
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_ipo_listing_day_runner.py src/tests/test_kiwoom_orders.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_kiwoom_token_cache.py src/tests/test_kiwoom_websocket.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_kiwoom_token_cache.py src/tests/test_kiwoom_websocket.py src/tests/test_ipo_listing_day_runner.py src/tests/test_kiwoom_orders.py
PYTHONPATH=. .venv/bin/python -m compileall -q src/utils/kiwoom_utils.py src/engine/kiwoom_websocket.py src/engine/ipo_listing_day_runner.py src/tests/test_kiwoom_token_cache.py src/tests/test_ipo_listing_day_runner.py
bash -n deploy/run_ipo_listing_day_autorun.sh deploy/install_ipo_listing_day_autorun_cron.sh
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
git diff --check
```

검증 결과:

- IPO runner 및 Kiwoom order 관련 테스트 통과
- Kiwoom token cache 및 websocket 인증 실패 경로 테스트 통과
- 관련 테스트 통합 실행 `32 passed`
- Python compile 검증 통과
- autorun shell syntax 검증 통과
- 문서 backlog parser 검증 통과
- whitespace diff check 통과

## 9. 잔여 리스크

1. 실제 주문 체결가는 v1에서 broker 체결 통보와 완전한 execution book으로 결합되어 있지 않다.
2. `0D` 예상체결 필드는 실시간 예상 값이므로 실제 시초가, 실제 주문 체결가와 사후 대사가 필요하다.
3. STOP 파일은 신규 주문 차단을 보장하지만, 이미 접수된 주문 취소나 보유 포지션 강제 청산까지 자동 보장하지 않는다.
4. `0H` 주식예상체결은 문서상 별도 실시간 타입으로 존재하나, 이번 변경은 기존 등록 중인 `0D`의 예상체결 필드 보존에 한정했다. `0H` 동시 등록은 별도 workorder와 실전 안정성 검토 후 진행하는 것이 적절하다.
5. AI Provider 호출은 현재 기능 검증 범위에서는 동작하지만, 실전 전 비용/rate limit guard를 명시적으로 추가하는 것이 바람직하다.
6. YAML 파일 존재 자체가 실주문 승인 artifact이므로, 잘못된 날짜/종목/공모가 입력은 실주문 리스크로 이어진다. 자동 실행 전 `--dry-select` 출력과 config diff 확인이 필요하다.
7. token cache 파일이 손상되거나 Kiwoom 서버가 token을 조기 무효화하는 경우 인증 장애가 발생할 수 있다. 이 경우 cache 삭제/재발급보다 실전 상태 대사와 graceful restart를 우선한다.

## 10. 결론

본 작업은 공모주 상장첫날 runner의 phase0 구현과 운영문서화를 완료한 상태다. `0D` 예상체결 필드 수집은 감리 관점에서 기존 `ws_curr` fallback보다 증적성이 높으므로 반영했으며, YAML-gated 자동 실행은 당일 YAML 파일이 있을 때만 작동하도록 제한했다. 추가로 공유 token cache와 file lock을 적용해 스캘핑 봇과 IPO runner의 Kiwoom token 중복 발급 충돌 가능성을 줄였다. 실전 첫 표본 이후 실제 시초가 및 체결 내역과의 대사를 필수 운영 절차로 남긴다.
