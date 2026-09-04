# IPO Listing-Day Runner - 코드리뷰 결과서

작성일: `2026-05-10 KST`
대상: [ipo_listing_day_runner.py](/home/ubuntu/KORStockScan/src/engine/ipo_listing_day_runner.py), [kiwoom_websocket.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_websocket.py), [run_ipo_listing_day_autorun.sh](/home/ubuntu/KORStockScan/deploy/run_ipo_listing_day_autorun.sh), [test_ipo_listing_day_runner.py](/home/ubuntu/KORStockScan/src/tests/test_ipo_listing_day_runner.py)

## 1. 리뷰 결론

판정: `조건부 승인`

근거:

- 별도 IPO runner로 구현되어 기존 스캘핑/스윙 state machine, threshold-cycle, Sentinel에 연결되지 않는다. 2026-05-10 후속 지시로 당일 YAML 파일이 있을 때만 실행하는 cron wrapper를 추가했다.
- 실제 주문 경로는 기존 Kiwoom order utility를 재사용하되, 신규 진입 시간창, premium guard, quote/depth gate, AI risk block, 1회 retry, kill switch가 코드와 테스트로 고정됐다.
- 2026-05-10 후속 지시로 종목별 실주문 예산 산출 상한을 `5,000,000 KRW`로 제한했다. YAML `budget_cap_krw`가 이를 초과해도 실제 수량 계산은 `effective_budget_cap_krw=5000000` 기준이며 artifact에 원 입력값과 effective 값을 함께 남긴다.
- 2026-05-10 후속 지시로 Kiwoom token 중복 발급 충돌을 줄이기 위해 `get_kiwoom_token()`에 공유 token cache + file lock을 추가했다. IPO runner와 스캘핑 봇은 기본적으로 같은 유효 token을 재사용한다.

조건:

- 실전 전에는 반드시 `--dry-select`로 당일 target 선택 결과를 확인한다.
- 첫 실전 운용은 `active_symbol_limit=1`, STOP 파일 kill switch 확인, Kiwoom 계좌/잔고 대사 가능 상태에서만 진행한다.
- 이 runner의 결과와 status는 threshold-cycle/daily EV 자동 적용 근거로 쓰지 않는다.

## 2. 구현 범위 확인

| 항목 | 확인 결과 |
| --- | --- |
| 실행 방식 | `PYTHONPATH=. .venv/bin/python -m src.engine.ipo_listing_day_runner --config ...` 또는 YAML-gated `deploy/run_ipo_listing_day_autorun.sh` |
| 입력 | YAML/JSON subset config. PyYAML이 없어도 runner 전용 fallback parser로 동작 |
| 승인 artifact | `configs/ipo_listing_day_YYYY-MM-DD.yaml` 파일과 당일 `trade_date`/enabled target |
| 예산 cap | 종목별 effective budget hard cap `5,000,000 KRW` |
| 산출물 | `data/ipo_listing_day/YYYY-MM-DD/events.jsonl`, `*_decision.json`, `summary.md` |
| 진입 시간 | `09:00:00~09:00:30 KST`만 실제 주문 허용 |
| 장전 감시 | `08:59:50`부터 WS snapshot. `0D_expected_open` 우선, 부재 시 `ws_curr` fallback |
| 진입 gate | premium `250%`, quote freshness, VI/quote vacuum, top 1~3 depth `3x`, AI `risk_score >= 80` block |
| retry | 첫 주문 실패/무응답 후 1회 IOC retry, `best_ask + 1tick` 한도 |
| 청산 | `-10%` hard stop, `+20%` 30% partial TP, AI hold defer, post-TP `8%p` trailing, 30분 max hold |
| kill switch | STOP 파일, 일손실 `-100,000 KRW`, 주문 실패 2회 |
| token guard | `data/runtime/kiwoom_token_cache.json` + `data/runtime/kiwoom_token_cache.lock` 공유 재사용. WS 인증 실패 복구만 `force_refresh=True` |

## 3. 주요 리스크와 잔여 확인

1. Kiwoom WS 장전 예상체결 필드와 실제 시초가의 대사가 필요하다.
   - `0D` 주식호가잔량의 예상체결 필드가 수신되면 `indicative_open_source=0D_expected_open`, `explicit_expected_open_available=true`를 남긴다.
   - 해당 필드가 없거나 유효하지 않으면 `indicative_open_source=ws_curr`, `explicit_expected_open_available=false`로 fallback 증적을 남긴다.
   - 실전 첫 표본 후 Kiwoom `0D` 예상체결가, `0H` 주식예상체결, 실제 시초가를 대사해야 한다.

2. 주문 체결가는 현재 v1에서 WS `curr` 기반 assumed fill로 내부 position을 시작한다.
   - 실제 receipt/체결 통보와 완전 바인딩된 execution book은 아직 아니다.
   - 첫 실전 후 `events.jsonl`과 Kiwoom 체결 내역을 수동 대사해야 한다.

3. STOP 파일은 신규 주문 차단용이다.
   - 이미 접수된 주문 취소나 보유 포지션 강제청산까지 자동 보장하지 않는다.
   - 사고 대응 시 Kiwoom 화면 또는 계좌 유틸로 주문/잔고를 같이 확인해야 한다.

4. OpenAI 호출 실패는 fail-open 성격이다.
   - AI가 unavailable/error/call cap이면 정량 gate만으로 진입 판단한다.
   - 의도는 시초가 hot path 지연을 줄이는 것이며, AI는 `risk_score >= 80`일 때만 차단권을 갖는다.

5. token cache는 중복 발급 충돌을 줄이지만 인증 장애 자체를 제거하지는 않는다.
   - cache 파일이 손상되거나 브로커가 기존 token을 서버 측에서 무효화하면 `8005`가 발생할 수 있다.
   - 이 경우 장중 hot-refresh 반복 대신 기존 graceful restart 운영 원칙을 우선한다.

## 4. 테스트 결과

실행 명령:

```bash
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_ipo_listing_day_runner.py src/tests/test_kiwoom_orders.py
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_kiwoom_token_cache.py src/tests/test_kiwoom_websocket.py
PYTHONPATH=. .venv/bin/python -m compileall -q src/engine/ipo_listing_day_runner.py src/tests/test_ipo_listing_day_runner.py
bash -n deploy/run_ipo_listing_day_autorun.sh deploy/install_ipo_listing_day_autorun_cron.sh
git diff --check
```

결과:

- IPO runner + Kiwoom order 관련 테스트: `22 passed`
- Kiwoom token cache + websocket 관련 테스트: `10 passed`
- compileall: 통과
- autorun shell syntax: 통과
- diff whitespace check: 통과

## 5. 리뷰 판정

실전 투입 전 필수 확인:

1. YAML `trade_date`와 target 1개 선택 확인
2. `budget_cap_krw <= 5000000` 또는 `effective_budget_cap_krw=5000000` clamp 인지 확인
3. `data/ipo_listing_day/STOP` 없음 확인
4. Kiwoom 계좌/주문 가능 상태 확인
5. 실행 후 `data/ipo_listing_day/YYYY-MM-DD/summary.md`와 Kiwoom 체결 내역 수동 대사

위 조건을 만족하면 phase0 YAML-gated 실주문 운용은 가능하다. 다만 threshold-cycle/daily EV 반영, 다종목 병렬 운용, `0H` 동시 등록은 별도 workorder와 재리뷰 전까지 금지한다.
