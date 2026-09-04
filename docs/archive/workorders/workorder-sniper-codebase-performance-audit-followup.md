# sniper 코드베이스 성능 감사 후속 작업지시서

작성일: `2026-04-25 KST`  
대상: DeepSeek 구현 담당  
기준 문서:

1. [sniper-codebase-performance-audit.md](/home/ubuntu/KORStockScan/docs/code-reviews/sniper-codebase-performance-audit.md)
2. [workorder-kiwoom-sniper-v2-loop-performance-improvement.md](/home/ubuntu/KORStockScan/docs/archive/workorders/workorder-kiwoom-sniper-v2-loop-performance-improvement.md)

이 문서는 체크리스트/Project/Calendar 자동관리 대상이 아닌 DeepSeek 구현 지시용 독립 workorder다.

---

## 1. 판정

이번 감사보고서의 제안은 그대로 일괄 구현하지 않는다. 실제 코드베이스 기준으로 `저위험 즉시개선`, `설계만 잠글 중기개선`, `보류/금지`를 분리한다.

판정은 아래로 고정한다.

1. `_ensure_state_handler_deps()` 호출 축소는 즉시 수정 승인.
   - 판정: 승인
   - 근거: `run_sniper()`의 per-target handler wrapper를 통해 동일한 deps 비교가 반복되고, 동작 의미를 바꾸지 않는 저위험 최적화다.
   - 다음 액션: 루프당 1회 보장으로 이동하고 wrapper 중복 호출을 제거한다.

2. WATCHING/HOLDING 동기 AI 호출 worker 분리는 이번 턴 구현 금지.
   - 판정: 보류
   - 근거: [sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py:1) 의 AI 호출은 stale 응답, state race, cohort 오염, rollback 복잡도를 동반한다.
   - 다음 액션: worker화는 별도 설계 문서로 분리하고 이번 workorder에서는 명시적으로 제외한다.

3. `TradingRulesCache` 도입은 이번 턴 구현 금지.
   - 판정: 보류
   - 근거: `getattr(TRADING_RULES, ...)`는 산재 범위가 크고, 설정 접근 계층 전체에 파급되는 대형 리팩토링이다.
   - 다음 액션: 추후 독립 리팩토링 과제로만 다룬다.

4. `sniper_gatekeeper_replay.py`의 `_append_jsonl()` 비동기화는 즉시 full 구현 금지, 설계 우선.
   - 판정: 조건부 승인
   - 근거: 메인루프 blocking 완화 효과는 있으나 write ordering, flush, shutdown 시점, 실패 로그 규약이 고정되지 않으면 운영 증적을 깨뜨릴 수 있다.
   - 다음 액션: 이번 문서에서 최소 비동기 writer 규약을 먼저 고정한다. 구현은 그 규약 범위에서만 허용한다.

5. `_RECENT_SNAPSHOT_SIGNATURES` prune 추가는 승인.
   - 판정: 승인
   - 근거: 장기 실행 시 메모리 누수 가능성이 있고, 동작 의미를 바꾸지 않는 저위험 운영 보강이다.
   - 다음 액션: TTL 기반 prune를 `record_gatekeeper_snapshot()` 경로에 붙인다.

6. `sniper_entry_latency._CACHE_LOCK` 구조 변경은 이번 턴 구현 금지.
   - 판정: 보류
   - 근거: lock 세분화는 동시성 버그와 quote health 정합성 리스크가 크다.
   - 다음 액션: 병목 증거만 유지하고 구조 변경은 별도 설계 과제로 넘긴다.

7. adaptive sleep은 `LOOP_METRICS` 실로그 기준선 확보 전 금지.
   - 판정: 금지
   - 근거: 현재 루프는 동기 DB/API/AI 호출이 남아 있어 sleep만 건드리면 EV 개선보다 운영 리스크가 먼저 커질 수 있다.
   - 다음 액션: `LOOP_METRICS` 실로그 확인 후에만 다음 단계 후보로 올린다.

8. 아래 항목은 낮은 우선순위로만 기록하고 이번 턴 구현하지 않는다.
   - `perf_counter()` 미세 오버헤드
   - `targets[:]` cleanup 자체
   - 60초 로그용 카운트 계산 미세 최적화

---

## 2. 구현 범위

이번 DeepSeek 구현 범위는 두 축으로 제한한다.

### 축 A. `run_sniper()` 상태 의존성 바인딩 호출 축소

대상 근거 파일: [kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py:1)

구현 요구사항:

1. `_ensure_state_handler_deps()`는 `run_sniper()` 루프 상단에서 1회만 실행되게 바꾼다.
2. per-target wrapper `handle_watching_state()` / `handle_holding_state()`에서는 `_ensure_state_handler_deps()`를 호출하지 않는다.
3. 런타임 중 deps가 동적으로 변한다는 가정을 추가하지 않는다.
4. boot, restart, module import 흐름 기준으로 현재 의미를 유지한다.
5. handler wrapper 시그니처와 기존 호출 경로는 유지한다. 외부 호출자가 깨지면 안 된다.

완료 기준:

1. 기존 wrapper 호출 경로 회귀 없음.
2. `run_sniper` 기준 state handler deps 바인딩이 루프당 1회 이하로 보장됨.
3. 기존 P0/P1 loop metrics 변경과 충돌 없음.

### 축 B. `sniper_gatekeeper_replay.py` 운영성 보강

대상 근거 파일: [sniper_gatekeeper_replay.py](/home/ubuntu/KORStockScan/src/engine/sniper_gatekeeper_replay.py:1)

구현 요구사항:

1. `_RECENT_SNAPSHOT_SIGNATURES`에 TTL prune를 추가한다.
2. prune는 `record_gatekeeper_snapshot()` 경로에서만 수행하고, 별도 background thread를 만들지 않는다.
3. prune 기준은 `GATEKEEPER_SNAPSHOT_DEDUP_TTL_SEC`보다 충분히 긴 보존 구간을 쓰되, dedup 의미를 깨지 않도록 한다.
4. `_append_jsonl()` 비동기화는 아래 규약이 문서에 고정될 때만 구현한다.

비동기 writer 규약:

1. `single-thread writer`
2. `best-effort enqueue`
3. `process exit 시 flush`
4. write 실패는 기존처럼 예외 전파 대신 `log_error` + `None` 반환 규약 유지
5. same-process ordering은 보장

이번 턴에서 비동기 writer까지 구현하려면 위 5개를 그대로 따른다. 이 규약을 만족시키기 어렵거나 구현 범위가 커지면 prune만 넣고 비동기 write는 문서에 parking 한다.

완료 기준:

1. `_RECENT_SNAPSHOT_SIGNATURES` 크기가 무기한 증가하지 않음.
2. dedup TTL 의미 유지.
3. write 실패 시 현재 실패 규약 유지.
4. 운영 증적 파일 포맷(JSONL) 변경 없음.

### 실로그 기준선

`LOOP_METRICS`는 이번 workorder의 코드 변경 대상이 아니다. 실로그 검증 결과를 후속 기준선으로만 사용한다.

후속 운영 acceptance:

1. `[LOOP_METRICS]` 로그에 `loop_elapsed_ms`, `db_active_targets_ms`, `account_sync_ms`, `target_count`, `watching`, `holding`이 최소 1회 이상 기록
2. 이 결과가 잠기기 전에는 adaptive sleep 검토 금지

---

## 3. 검증

DeepSeek는 아래 검증 기준을 문서대로 수행한다.

1. `_ensure_state_handler_deps()` 관련
   - wrapper 호출 경로 회귀 없음
   - `run_sniper` 루프에서 state handler deps 바인딩이 루프당 1회 이하임을 검증하는 테스트 추가 또는 기존 테스트 보강

2. `gatekeeper replay` 관련
   - `_RECENT_SNAPSHOT_SIGNATURES` prune 동작 테스트
   - dedup TTL 유지 테스트
   - write 실패 시 `record_gatekeeper_snapshot()`가 예외 전파 없이 `None` 또는 기존 실패 규약을 유지하는지 테스트

3. 회귀 테스트 묶음
   - `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_sniper_loop_metrics.py`
   - gatekeeper replay 관련 테스트 신규 추가 또는 기존 테스트 보강
   - `PYTHONPATH=. .venv/bin/pytest -q src/tests/test_performance_tuning_report.py src/tests/test_sniper_entry_latency.py`

4. 운영 acceptance
   - `[LOOP_METRICS]` 실로그 확인은 테스트와 별도다.
   - 실로그 값이 남지 않으면 adaptive sleep, AI worker, 주문 worker 검토는 자동 보류다.

---

## 4. 보류/금지

아래 항목은 이번 DeepSeek 작업 범위에서 구현하지 않는다.

1. `time.sleep(1)` 변경
2. `ai_engine.analyze_target()` 경로 worker화
3. `kiwoom_orders.get_deposit()`, `send_buy_order()`, `send_sell_order_market()` 비동기화
4. `sniper_state_handlers.py` 대규모 분할
5. `TradingRulesCache` 도입
6. `sniper_entry_latency._CACHE_LOCK` 구조변경
7. adaptive sleep
8. `targets[:]` cleanup 리팩토링
9. `perf_counter()` 미세 오버헤드 제거
10. 60초 로그용 카운트 계산 미세 최적화

이번 workorder의 우선순위 해석은 EV 직접개선이 아니라, 후속 EV 개선축을 안전하게 열기 위한 운영 병목 제거다.
