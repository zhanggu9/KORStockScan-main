# `ai_engine.py` 스캘핑 정상화 감리 결과 (`2026-05-02`)

> 작성시각: `2026-05-02 KST`
> 검토 대상: [`src/engine/ai_engine.py`](../../src/engine/ai_engine.py) (2,699 LOC)
> 입력 보고서: `2026-05-02-ai-engine-scalping-normalization-audit-report.md`
> 검토 관점: 로직 충돌(logic conflict) / 불완전 항목(incomplete) / 계획 부재(missing plan)
> 검증 방법: 입력 보고서의 함수 그래프·계약 주장과 실제 코드 라인을 1:1 대조. 의문 항목은 라인 번호로 직접 인용한다.

---

## 0. TL;DR

입력 보고서의 **구조 진단(공유 락/공유 상태/공유 계약이 넓다)** 은 정확하다. 그러나 그 진단이 가리키는 **구체 결손 항목 일부가 본문에서 빠져 있고**, 그중 다수는 단순 코드 정리가 아니라 **운영 정책 차원의 결정**을 요구한다.

본 감리는 코드를 1:1 재독해 다음을 발견했다.

- 로직 충돌 5건 — 락 모드 비대칭 1건, 실패/비활성/쿨다운 정책 비대칭 3건, 어휘 비정합 1건
- 불완전 항목 7건 — dead code 2건, dead 상수 1건, 캐시 정책 결손 2건, 메타 필드 누락 1건, 클램프 무분기 1건
- 계획 부재 7건 — flag-off 항목들의 ON 트리거 부재, 엔진 비활성 복구 경로 부재, 엔진간 parity contract 부재 등

영향이 가장 큰 두 항목:

1. **`evaluate_scalping_overnight_decision`은 `with self.lock:` (blocking) + `ai_disabled` 미참조 + `consecutive_failures`/`last_call_time` 미갱신** — 다른 3개 스캘핑 메서드와 정책이 정반대다. 15:20 슬롯에서 격리된 정책 섬(island)이다.
2. **`ai_disabled=True` 트립은 `analyze_target`만 가능** — entry_price/holding_flow는 카운터만 증가시키고 disable 트립 권한이 없다. 결과적으로 카운터는 공유되고 트립 권한은 단일화되어 있어, **무관해 보이는 경로의 실패가 다른 경로로 폭발하는 cross-contamination**이 구조적으로 가능하다.

---

## 1. 검증 요약 — 입력 보고서 주장 vs 실제 코드

| 입력 보고서 주장 | 코드 근거 | 검증 결과 |
| --- | --- | --- |
| 4개 스캘핑 메서드가 같은 `self.lock` 공유 | line 613, 1610, 1746, 2342, 2471 | ✓ 정확. 단, **락 모드(blocking 여부)가 비대칭**임은 미언급 (§2.1) |
| entry_price/holding_flow는 실패는 올리되 disable까지는 안 함 | line 1680, 2422 | ✓ 정확. **overnight는 카운터도 안 올림**은 미언급 (§2.2) |
| analyze_target만 max_consecutive_failures 검사 | line 1865 | ✓ 정확 |
| entry_price/holding_flow는 캐시 없음 | 명시 캐시 호출 부재 | ✓ 정확. 단, **무캐시 정책의 명문화된 근거 없음**은 §4.4 |
| condition entry/exit는 스캘핑 경로 어댑터 | line 2506-2565 | ✓ 정확. 단, **dead `analyze_condition_target`** (line 1884)는 미언급 (§3.1) |
| schema name 5종을 `_call_gemini_safe`가 받음 | line 1271-1299 | ✓ 정확. 단, **registry flag OFF 상태에서는 검증 미수행**은 §4.1 |
| Tier1=빠른 진입 판단, Tier2=가격/플로우/오버나이트 | line 1102, 1661, 1812, 2403, 2483 | ✓ 정확 |

---

## 2. 로직 충돌 (Logic Conflicts)

### 2.1 락 모드 비대칭 — `overnight`만 blocking

| 메서드 | 락 모드 | 라인 |
| --- | --- | --- |
| `analyze_target` | `acquire(blocking=False)` → 실패 시 즉시 fallback | line 1746 |
| `evaluate_scalping_entry_price` | `acquire(blocking=False)` → 즉시 `USE_DEFENSIVE` | line 1610 |
| `evaluate_scalping_holding_flow` | `acquire(blocking=False)` → 즉시 `EXIT` 보수 fallback | line 2342 |
| `evaluate_scalping_overnight_decision` | **`with self.lock:` (blocking)** | line 2471 |

영향:

- `15:20 KST` 슬롯에 다수 SCALPING 포지션이 동시에 overnight 결정에 진입할 때, 락이 직렬화되어 마지막 종목은 수 초~수십 초 대기할 수 있다.
- 이 시점에 `holding_flow override`나 `analyze_target holding refresh`가 같이 깨어 있으면 overnight가 그 작업 종료를 무한정 기다린다.
- 다른 3개 메서드의 fail-fast 정책과 정면 충돌한다 — overnight만 락 경합에 인내한다.

권고: overnight도 동일하게 `acquire(blocking=False)` + 짧은 timeout(예: 2~3초) 후 보수적 `SELL_TODAY` 폴백. blocking을 유지할 거면 timeout 명시.

### 2.2 실패 카운터 / `ai_disabled` 트립 권한 비대칭

| 메서드 | `ai_disabled` 읽기 | `consecutive_failures` 증가 | `consecutive_failures = 0` 리셋 | `ai_disabled=True` 트립 |
| --- | --- | --- | --- | --- |
| `analyze_target` | ✓ (1777) | ✓ (1861) | ✓ (1838) | **✓ (1866)** |
| `evaluate_scalping_entry_price` | ✓ (1627) | ✓ (1680) | ✓ (1665) | ✗ |
| `evaluate_scalping_holding_flow` | ✓ (2365) | ✓ (2422) | ✓ (2407) | ✗ |
| `evaluate_scalping_overnight_decision` | **✗** | **✗** | **✗** | ✗ |

세 가지 충돌이 동시에 발생한다.

1. **카운터 공유, 트립 권한 단일화** — entry_price/holding_flow 실패가 누적되어 카운터가 한도(`max_consecutive_failures=5`)를 넘겨도 disable이 트립되지 않는다. 다음 `analyze_target` 호출의 첫 시도에서 갑자기 disable로 폭발한다. 즉 무관한 경로의 실패가 한 경로의 시점에 응결돼 터진다.
2. **HOLDING-only 시간대 안전망 부재** — 시간대에 따라 신규 진입(`analyze_target watching`)이 거의 호출되지 않는 구간이 있다. 이때 holding_flow만 실패가 누적되면 `ai_disabled`가 무한히 트립되지 않아 엔진이 살아 있는 것처럼 보인다.
3. **overnight는 정책 섬** — `ai_disabled=True`여도 overnight는 그것을 보지 않으므로 그대로 실행된다 (line 2469-2504). 또 실패해도 카운터를 올리지 않으므로 Gemini 장애의 마지막 신호 통로 하나가 침묵한다.

권고:
- `ai_disabled` 트립 권한을 **모든 경로가 공유**하도록 한다 (`_record_failure(self) → 트립 검사`로 추출).
- overnight도 `ai_disabled` 검사 + 카운터 갱신 + `last_call_time` 갱신을 추가한다.
- 또는 카운터 자체를 경로별로 분리(`failures_by_surface`)하고 트립도 경로별로 가져간다. 어느 쪽이든 **공유 vs 분리**의 정책을 명시.

### 2.3 `min_interval` 쿨다운 비대칭

| 메서드 | `min_interval` 검사 | `last_call_time` 갱신 |
| --- | --- | --- |
| `analyze_target` | ✓ (1791) | ✓ (1839, 1666 형태) |
| `evaluate_scalping_entry_price` | ✗ | ✓ (1666) |
| `evaluate_scalping_holding_flow` | ✗ | ✓ (2408) |
| `evaluate_scalping_overnight_decision` | ✗ | ✗ |
| `analyze_target_shadow_prompt` | ✗ | ✗ |

영향:

- `analyze_target`만 cooldown을 강제하므로, helper 메서드(entry_price/holding_flow)가 cooldown 정책 외부에서 자유롭게 호출되어 `last_call_time`을 갱신한다.
- 결과: helper 호출 직후 `analyze_target`가 호출되면 cooldown에 막혀 `WAIT 50` fallback으로 빠진다 — helper가 main 경로의 처리량을 비대칭적으로 갉아먹는다.
- shadow path는 cooldown도 검사 안 하고 `last_call_time` 갱신도 안 하므로, shadow가 폭주해도 main 경로의 cooldown 인지에 잡히지 않는다 (Gemini 한도에 도달해서 429를 받기 전까지는).

권고: cooldown은 `_call_gemini_safe`로 일원화하거나, 모든 경로가 동일한 `_pre_call_gate()`를 거치도록 정리. 현 구조는 cooldown의 "단일 진실의 원천"이 없다.

### 2.4 `_apply_remote_entry_guard`의 `scalping_watching` literal — dead branch

[`ai_engine.py` line 985](../../src/engine/ai_engine.py:985):

```python
if prompt_type not in {"scalping_entry", "scalping_watching", "scalping_shared"}:
    return result
```

그러나 [`_resolve_scalping_prompt` line 924](../../src/engine/ai_engine.py:924)는 `watching` 프로파일에 대해 prompt_type을 **`scalping_entry`**로 반환한다 (`scalping_watching`이 아님).

영향:

- 가드는 동작한다(`scalping_entry`로 매치되므로). 그러나 `"scalping_watching"` 문자열은 절대 매치되지 않는 dead literal이다.
- 어휘가 비정합한 채로 남아 있어, 후속 작업자가 `scalping_watching`이라는 이름이 어딘가에서 쓰이는 것으로 오인할 수 있다.

권고: literal 제거. 나아가 prompt_type 값들을 **enum/Literal 타입**으로 고정해 어휘 표류를 막는다.

### 2.5 `decision_kind`가 형식적 — intraday vs overnight 분기 부재

[`evaluate_scalping_holding_flow` line 2329-2445](../../src/engine/ai_engine.py:2329)는 `decision_kind` 인자를 받지만, 실제 사용처는 [`_format_scalping_holding_flow_context` line 2274](../../src/engine/ai_engine.py:2274)의 프롬프트 헤더 한 줄과 [line 2402](../../src/engine/ai_engine.py:2402)의 `context_name`뿐이다.

영향:

- `intraday_exit`과 `overnight_sell_today`가 동일 프롬프트, 동일 schema, 동일 클램프(`next_review_sec ∈ [30,90]`)를 거친다.
- 오버나이트는 다음 review가 의미가 없거나 타임프레임이 다르다 — `30~90초` 클램프는 비논리적이다.
- 결과적으로 cadence/exit-policy 차별화는 호출부(`sniper_overnight_gatekeeper.py`)로 외주화되어, `ai_engine` 내부에 단일 진실의 원천이 없다.

권고: `decision_kind`별로 클램프 범위 분리 + 프롬프트 분기. 또는 `decision_kind`를 인자에서 제거하고 호출부가 별도 메서드를 쓰게 한다 (인터페이스를 솔직하게 만든다).

---

## 3. 불완전 항목 (Incomplete)

### 3.1 `analyze_target` 함수 본문 안에 nested된 dead methods

[`ai_engine.py` line 1881-1902](../../src/engine/ai_engine.py:1881):

```text
1881        finally:
1882            self.lock.release()
1883
1884        def analyze_condition_target(self, target_name, ws_data, ...):   # ← 8 spaces
1885            ...
1894            return self.analyze_target(target_name, ws_data, ...)
1895
1896        def evaluate_condition_gatekeeper(self, ...):                    # ← 8 spaces
```

들여쓰기가 8칸이라 **`analyze_target`의 함수 본문 내부에 정의된 inner function**이다. 클래스 메서드로 노출되지 않으므로 `engine.analyze_condition_target(...)` 호출 시 `AttributeError`.

이 두 메서드의 의도된 기능은 [`evaluate_condition_entry`(line 2506)](../../src/engine/ai_engine.py:2506)와 [`evaluate_condition_exit`(line 2537)](../../src/engine/ai_engine.py:2537)이 흡수하고 있다. 따라서 line 1884-1902는 명백한 **들여쓰기 버그 + dead code**다.

권고: 즉시 삭제. 또는 의도가 있다면 클래스 레벨로 들여쓰기 수정 + 호출부 명시.

### 3.2 `SCALPING_BUY_RECOVERY_CANARY_PROMPT` — 정의되었으나 한 군데도 참조되지 않음

[`ai_engine.py` line 284-331](../../src/engine/ai_engine.py:284)에 약 50줄짜리 상수가 정의돼 있으나, 파일 어디에서도 참조되지 않는다.

```bash
grep -n "SCALPING_BUY_RECOVERY_CANARY_PROMPT" ai_engine.py
# 정의 1건만 출력 (line 284)
```

입력 보고서 §10.4는 `buy_recovery_canary 재승격`이 현재 owner가 아니라고 명시한다. 그렇다면 이 상수의 위치가 잘못됐다 — 운영 엔진 파일이 아니라 별도 experimental 파일로 가거나 삭제돼야 한다.

권고:
- 재승격 계획이 살아 있다면 → `experimental/` 또는 `legacy/`로 이동 + 재승격 trigger 문서화.
- 살아 있지 않다면 → 삭제.

### 3.3 `analyze_target_shadow_prompt`의 owner 부재

[`ai_engine.py` line 1015-1137](../../src/engine/ai_engine.py:1015)는 production 경로와 **같은 락, 같은 캐시(`_analysis_cache`)**를 공유하면서 cooldown은 검사하지 않는다. 입력 보고서 §10.2는 OpenAI shadow를 observe-only로 명시하지만, **Gemini shadow path 자체의 owner는 보고서 어디에도 없다**.

영향:

- shadow가 폭주하면 `_analysis_cache`가 production 키로 채워질 수 있다 — production 키와 cache_strategy 필드(line 1044)가 다르므로 직접 충돌은 없으나, 512 entry 트리거를 일찍 넘겨 eviction 압력을 만든다.
- shadow가 lock contention을 일으키면 production 경로가 fail-fast로 빠진다.

권고: shadow path를 **별도 락 + 별도 캐시 + 명시적 ON/OFF 플래그**로 격리한다. 또는 미사용 시 라우터에서 호출이 없음을 단언하는 단정문 추가.

### 3.4 캐시 eviction이 사실상 비활성

[`_cache_set` line 706-722](../../src/engine/ai_engine.py:706):

```python
if len(cache) > 512:
    expired = [k for k, item in cache.items() if item["expires_at"] <= now]
    for k in expired[:128]:
        cache.pop(k, None)
```

영향:

- 모든 항목이 비-만료 상태이면 `expired = []` → 한 건도 evict되지 않는다. 그래도 새 entry는 추가되므로 size는 계속 증가한다.
- 매 `_cache_set` 호출마다 `O(N)` 스캔이 일어나며 락(`cache_lock`)이 점유된다. 1만 entry에 도달하면 매 set마다 만 건 스캔.
- holding refresh가 과활발해지면 시간당 수백~수천 entry 진입이 가능하므로 충분히 도달 가능.

권고: LRU 또는 시간 기반 eviction 도입. 최소한 size 상한 + FIFO 강제 제거.

### 3.5 캐시 키가 `cache_profile`을 digest에 포함하지 않음 (non-holding)

[`_build_analysis_cache_key_with_profile` line 877-884](../../src/engine/ai_engine.py:877):

```python
return self._build_cache_digest({
    "target_name": target_name,
    "strategy": strategy,
    "ws_data": ws_data,
    "recent_ticks": recent_ticks,
    "recent_candles": recent_candles,
    "program_net_qty": program_net_qty,
})
```

`cache_profile`(`default`/`condition_entry`/`condition_exit`)이 digest 입력에 없다. `analyze_target`(line 1721)이 `normalized_profile`을 strategy 문자열에 합치므로 prompt_profile은 구분되지만, **cache_profile 자체는 키에 반영되지 않는다.**

현재는 모두 동일 TTL(8s)이라 silent하게 동작한다. 그러나 향후 `condition_entry`만 TTL을 늘리는 변경이 일어나면 키 충돌로 새 정책이 무력화된다.

권고: `cache_profile`을 digest 입력에 추가. 또는 cache_profile별로 별도 dict로 분리.

### 3.6 `evaluate_scalping_overnight_decision`은 AI 메타 필드를 붙이지 않음

[line 2489-2495](../../src/engine/ai_engine.py:2489):

```python
return {
    'action': action,
    'confidence': int(...),
    'reason': str(...),
    'risk_note': str(...),
    'raw': result,
}
```

다른 3개 메서드는 `_annotate_analysis_result`로 `ai_parse_ok / ai_response_ms / ai_prompt_type / ai_result_source / cache_hit / cache_mode` 등을 일관 추가하지만, overnight만 raw dict를 반환한다.

영향: 사후 감리/관측성에서 overnight 결정만 메타 누락 → `record_id` 단위 attribution이 끊긴다.

권고: overnight도 `_annotate_analysis_result`(또는 동등 헬퍼)로 메타 일관 부착. `prompt_version="overnight_v1"`, `ai_result_source="live"|"exception"|"engine_disabled"`.

### 3.7 `_normalize_holding_flow_result`의 `next_review_sec` 클램프 무분기

[line 2325](../../src/engine/ai_engine.py:2325):

```python
"next_review_sec": max(30, min(90, int(self._safe_float(payload.get("next_review_sec", 60), 60)))),
```

`decision_kind`가 무엇이든 `[30, 90]`으로 강제. 오버나이트의 경우 다음 review 자체가 의미 없는데 30~90을 반환한다.

권고: `decision_kind="intraday_exit"`일 때만 [30, 90] 클램프, overnight는 클램프 자체를 우회하거나 다른 범위.

---

## 4. 계획 부재 (Missing Plans)

### 4.1 `_call_gemini_safe`의 안전 플래그 3종 — 켜는 trigger가 불명

[line 1274-1299](../../src/engine/ai_engine.py:1274)에서 다음 3개 플래그가 모두 OFF 상태로 동작한다.

| 플래그 | OFF 시 영향 |
| --- | --- |
| `GEMINI_SYSTEM_INSTRUCTION_JSON_ENABLED` | 매 호출에 거대한 prompt를 contents 첫 요소로 재전송. 토큰 비용 + Gemini의 system 준수도 약화 |
| `GEMINI_JSON_DETERMINISTIC_CONFIG_ENABLED` | `temperature/top_p/top_k` 미설정. 같은 입력에 다른 출력 가능 |
| `GEMINI_RESPONSE_SCHEMA_REGISTRY_ENABLED` | 5개 schema name(`entry_v1` 등)이 인자로 전달되지만 server-side 검증 미수행 |

입력 보고서 §10.2는 이 셋을 `2026-05-06 AIEngineFlagOffBacklog0506`이라는 **단일 backlog 항목**으로 묶었다. 그러나:

- 셋의 의존성이 다르다(스키마 검증은 deterministic 없이도 의미 있고, system_instruction은 토큰 비용만 줄임).
- ON으로 전환되는 trigger 조건이 명문화되지 않았다.

권고: 3개를 분리 관리 + 각자의 ON 트리거 명시(예: schema는 1주일 shadow 후 mismatch율 < 0.5%면 enable, deterministic은 production canary KPI 안정화 후 enable).

### 4.2 `ai_disabled` 복구 경로 부재

[line 1865-1867](../../src/engine/ai_engine.py:1865)에서 `ai_disabled=True` 트립 후, 이를 다시 `False`로 만드는 코드는 파일 어디에도 없다. 즉 **재시작 외 복구 불가**다.

권고:
- 트립 후 일정 시간 경과 시 자동 복구(쿨다운 + 1회 probe).
- 또는 Gemini 키 로테이션 후 자동 재시도 + 첫 성공 시 복구.
- 어느 쪽이든 **명시적 정책으로 결정**.

### 4.3 `runtime_ai_router`와의 인터페이스 contract 부재

입력 보고서 §10.2는 OpenAI/DeepSeek 라이브 라우팅이 미승인 상태임을 명시한다. 그러나 `ai_engine.py`에 다른 엔진들이 만족해야 할 **인터페이스(Protocol/ABC) 정의가 없다**. 반드시 다음이 동등해야 한다.

- `analyze_target(prompt_profile, cache_profile, ...)` 시그니처
- `evaluate_scalping_entry_price(price_ctx)` 반환 keys (`action`, `order_price`, `confidence`, `reason`, `max_wait_sec`)
- `evaluate_scalping_holding_flow(decision_kind=...)` 반환 keys
- `evaluate_scalping_overnight_decision()` 반환 keys
- AI 메타 필드 셋

권고: `src/engine/ai_engine_protocol.py`로 추출. 모든 구현체(Gemini/OpenAI/DeepSeek)가 type check 통과하도록 강제. 이게 없으면 라우터 enable 검증이 ad-hoc하게 된다.

### 4.4 무캐시 정책의 명문화 없음

`evaluate_scalping_entry_price`와 `evaluate_scalping_holding_flow`는 캐시를 쓰지 않는다 (입력 보고서 §8.3). 이 결정의 근거가 코드에도 문서에도 없다.

후보 근거:
- entry_price는 제출 직전 1회만 호출되므로 캐시 의미 없음 — 그러나 같은 후보에 대한 retry/race 시나리오에서 캐시 미스 비용이 누적될 수 있다.
- holding_flow는 `flow_history`/`position_ctx`가 매번 다르므로 캐시 적중률이 낮음 — 그러나 30~90초 review cadence면 실제로는 동일 입력 가능성이 있다.

권고: 무캐시 정책을 **결정 메모(ADR)**로 문서화. 향후 P2 확장 시 부하 추정의 baseline.

### 4.5 P2 microstructure-adaptive band 확장 시 ai_engine 부하 영향 추정 부재

직전 감리 후속(`2026-04-29 daehan-cable-rereport`) §3에서 P2를 보류했다. 그러나 P2가 ON되면:

- `evaluate_scalping_entry_price` 호출 빈도가 늘어남 (defensive band가 더 정교해질수록 호출 후보가 늘어날 수 있음 — 입증 필요).
- `_call_gemini_safe`는 락 + Gemini 라운드트립으로 직렬화돼 있어 호출 빈도 증가가 즉시 latency로 전이.

권고: P2 설계 입력에 **현재 ai_engine 호출 빈도 측정 → P2 ON 시 추정 빈도 → 락/캐시 임팩트** 항목을 명시 포함. 측정 없이 ON 시 회귀 추정 불가.

### 4.6 Tier3 모델의 실시간 스캘핑 사용 정책 부재

[line 1925, 2628](../../src/engine/ai_engine.py:1925)에서 Tier3는 EOD/scanner 보고서 등 batch 경로에서만 쓰인다. 실시간 스캘핑에는 사용 계획이 없다 — 이 자체는 합리적이지만, "**실시간 결정에 deep model을 쓸 것인가**"의 정책이 명문화되지 않았다.

향후 자연스럽게 "entry_price를 Tier3로 한 번 더 검증" 같은 요청이 올 수 있는데, 그 때 기각/수용 기준이 없다.

권고: Tier 별 사용 정책을 한 페이지로 정리 (지연 예산, 비용 예산, 어떤 경로에서 어떤 Tier).

### 4.7 `decision_kind`별 cadence/exit-policy SSoT 부재

§2.5와 연결. 현재 `decision_kind` 분기는 `ai_engine` 외부(`sniper_overnight_gatekeeper`, `sniper_state_handlers`)로 분산돼 있다. 어떤 cadence/exit-policy가 정답인지의 **단일 진실의 원천**이 없어, 향후 변경 시 어느 파일을 보면 되는지가 불명확.

권고: `decision_kind` 정책을 `src/engine/holding_flow_decision_policy.py` 같은 단일 파일로 추출. ai_engine은 그 파일을 import하는 소비자가 된다.

---

## 5. 우선순위 매트릭스

| # | 항목 | 카테고리 | 파급도 | 시급도 | 권장 트랙 |
| --- | --- | --- | --- | --- | --- |
| 2.1 | overnight blocking lock | 충돌 | 高 (15:20 stall) | 高 | **P0 hotfix** |
| 2.2 | ai_disabled 트립 권한 단일화 | 충돌 | 高 (cross-contamination) | 高 | **P0 hotfix** |
| 3.1 | dead `analyze_condition_target` indentation | 불완전 | 低 (호출 시도 시 오류) | 中 | P0 정리 |
| 3.2 | dead `BUY_RECOVERY_CANARY_PROMPT` | 불완전 | 低 | 中 | P0 정리 |
| 4.2 | `ai_disabled` 복구 경로 | 부재 | 高 (재시작 외 복구 없음) | 中 | P1 |
| 2.3 | `min_interval` cooldown 비대칭 | 충돌 | 中 | 中 | P1 |
| 2.5 / 3.7 / 4.7 | `decision_kind` 분기 부재 (3개 항목 묶음) | 충돌+부재 | 中 | 中 | P1 |
| 3.4 | 캐시 eviction 사실상 비활성 | 불완전 | 中 (장시간 운영 시) | 中 | P1 |
| 3.6 | overnight 메타 필드 누락 | 불완전 | 中 (관측성) | 中 | P1 |
| 4.1 | flag-off 3종의 ON 트리거 | 부재 | 中 | 低 | P2 |
| 4.3 | runtime router parity contract | 부재 | 中 | 低 | P2 |
| 3.3 | shadow path owner 부재 | 불완전 | 低-中 | 低 | P2 |
| 3.5 | cache key의 cache_profile 미포함 | 불완전 | 低 (현재는 silent) | 低 | P2 |
| 4.4-4.6 | 정책 문서화 (무캐시/Tier/부하 추정) | 부재 | 低 | 低 | 백로그 |
| 2.4 | dead literal `scalping_watching` | 충돌 | 極低 | 低 | 백로그 청소 |

---

## 6. 권고 — P0 / P1 분리 배포안

### 6.1 P0 (이번 주, 안전성)

1. **`evaluate_scalping_overnight_decision`을 다른 3개와 정책 정합화**:
   - `acquire(blocking=False)` + 짧은 timeout 폴백
   - `ai_disabled` 검사 추가
   - 실패 시 `consecutive_failures += 1`, 성공 시 `= 0`, `last_call_time = time.time()`
   - `_annotate_analysis_result`로 메타 필드 부착
2. **`ai_disabled` 트립 권한 분산**: 4개 메서드 모두 `_record_failure_and_maybe_disable()` 헬퍼 호출.
3. **dead code 정리**: line 1884-1902 indentation 수정 또는 삭제, line 284 상수 정리.

이 P0는 신규 alpha 도입이 아니라 **회귀 위험을 줄이고 관측성을 회복**하는 작업이다. shadow/canary 거치지 않고 정규 PR로 진행 가능.

### 6.2 P1 (다음 스프린트, 정책 일관성)

4. `min_interval` cooldown을 모든 경로 공통 게이트로 일원화.
5. `decision_kind` 정책을 별도 파일로 추출, `next_review_sec` 클램프 분기.
6. `ai_disabled` 자동 복구 정책 도입 (timeout + probe).
7. 캐시 LRU eviction 도입.

### 6.3 P2 (이후, 구조 정비)

8. `ai_engine_protocol.py` 추출 + 모든 구현체 type check.
9. `_call_gemini_safe` flag 3종을 분리 관리 + 각자 ON 트리거 명시.
10. shadow path 격리(별도 락/캐시).

---

## 7. 검증 명령

본 감리 결과를 코드에서 재현·검증할 때 사용한 명령:

```bash
grep -n "self.lock.acquire\|with self.lock" /mnt/user-data/uploads/ai_engine.py
grep -n "consecutive_failures\|ai_disabled\|last_call_time\|min_interval" /mnt/user-data/uploads/ai_engine.py
grep -n "SCALPING_BUY_RECOVERY_CANARY_PROMPT" /mnt/user-data/uploads/ai_engine.py   # 정의 1건만 출력
grep -n "scalping_watching\|scalping_entry\|scalping_holding\|scalping_shared" /mnt/user-data/uploads/ai_engine.py
```

추가로 다음 회귀 테스트를 P0 PR에 묶을 것을 권장한다.

- `test_overnight_lock_timeout`: blocking lock이 timeout 내 폴백되는지.
- `test_ai_disabled_trips_from_holding_flow`: holding_flow 실패 5회 누적 시 `ai_disabled=True`가 설정되는지.
- `test_overnight_skips_when_disabled`: `ai_disabled=True`일 때 overnight가 보수 폴백을 반환하는지.
- `test_no_dead_method_attribute_error`: `engine.analyze_condition_target(...)` 호출이 의도적이라면 동작, 아니면 삭제 확인.

---

## 8. 입력 보고서와의 차이 정리

입력 보고서가 잘 정리한 부분(공유 락/공유 상태/공유 계약의 구조 진단)은 그대로 두되, 본 감리는 다음을 **추가** 또는 **시급도 상향**한다.

| 항목 | 입력 보고서 위치 | 본 감리에서 추가/상향한 내용 |
| --- | --- | --- |
| 락 모드 | §8.1에 "단일 클래스 락" 언급 | overnight만 blocking이라는 비대칭 추가 (§2.1) |
| 실패 정책 | §8.2에 "비대칭" 언급 | overnight는 카운터도 안 올린다는 점 + cross-contamination 시나리오 추가 (§2.2) |
| dead code | 미언급 | line 1884 indentation 버그, line 284 dead 상수 (§3.1, §3.2) |
| cooldown | 미언급 | analyze_target만 강제하는 비대칭 (§2.3) |
| eviction | §8.3에 캐시 정책 분리만 언급 | 512 도달 시 eviction이 사실상 비활성 (§3.4) |
| overnight 메타 | 미언급 | `_annotate_analysis_result` 미부착 (§3.6) |
| ai_disabled 복구 | 미언급 | 재시작 외 경로 없음 (§4.2) |
| router parity | §10.4에 라우팅 미승인만 언급 | 인터페이스 Protocol 부재 (§4.3) |

---

## 9. 결론

`ai_engine.py`의 스캘핑 정상화는 입력 보고서가 진단한 대로 "프롬프트 문구"가 아니라 **공유 인프라의 정책 비대칭** 문제다. 본 감리는 그 비대칭의 구체 항목을 라인 단위로 재고정하고, 다음 두 가지를 P0로 권고한다.

1. **overnight 정책 섬 해소**: blocking lock + ai_disabled 미참조 + 카운터 미반영 → 다른 3개와 동일 규약으로 묶는다.
2. **`ai_disabled` 트립 권한 분산**: cross-contamination을 차단하고, HOLDING-only 시간대에서도 엔진 장애가 자동 검출된다.

이 두 P0가 적용되기 전에는 `dynamic_entry_ai_price_canary_p2` keep/OFF 판정 (`2026-05-04 POSTCLOSE`)을 권하지 않는다. 정책 비대칭 위에서 측정된 KPI는 origin이 흐려진다.

P1/P2는 본 보고서 §6에 우선순위로 정렬했다. 순서 변경/병합 의견 있으면 회신 부탁드린다.

---

## 10. Codex 검토 및 반영 결과 (2026-05-02)

### 10.1 타당하여 즉시 반영한 항목

- `Gemini/OpenAI/DeepSeek` 공통으로 스캘핑 `evaluate_scalping_overnight_decision`을 non-blocking lock, `ai_disabled` 검사, 실패 카운터, 성공 리셋, `_annotate_analysis_result` 메타 부착 방식으로 정합화했다.
- `evaluate_scalping_entry_price`, `analyze_target`, `evaluate_scalping_holding_flow`, `evaluate_scalping_overnight_decision`의 실패 기록을 `_record_failure_and_maybe_disable()` 헬퍼로 통일했다.
- 성공 호출 기록을 `_mark_successful_ai_call()`로 통일해 `consecutive_failures`와 `last_call_time` 갱신 정책을 한 곳으로 모았다.
- non-holding 분석 캐시 key에 `cache_profile`을 포함해 shadow/canary profile 간 캐시 혼선을 차단했다.
- 캐시가 만료 entry 없이 512건을 초과할 때도 `AI_RESULT_CACHE_MAX_ENTRIES` 기준으로 오래된 entry를 제거하도록 bounded eviction을 추가했다.
- `_apply_remote_entry_guard`의 dead literal `scalping_watching`을 제거했다. 현재 watching profile은 `_resolve_scalping_prompt()`에서 `scalping_entry`로 정규화된다.
- `ai_engine.py` 내부 `analyze_target` 아래에 잘못 중첩되어 class method로 노출되지 않던 dead method 블록을 삭제했다.
- `holding_flow`의 `next_review_sec` clamp는 intraday 기본 `30~90초`를 유지하되, `decision_kind="overnight_sell_today"`일 때는 `0~600초` 범위로 분리했다.

### 10.2 타당하지만 즉시 런타임 변경하지 않은 항목

- `min_interval` 공통 cooldown 적용은 active `dynamic_entry_ai_price_canary_p2`와 `holding_flow_override`의 호출 cadence를 직접 바꿀 수 있어 이번 변경에서 제외했다.
- `SCALPING_BUY_RECOVERY_CANARY_PROMPT` 삭제는 OpenAI/DeepSeek import 및 기존 shadow prompt 테스트와 연결되어 있어 스캘핑 정상화 범위의 안전 변경으로 보지 않았다.
- provider protocol 추출, flag-off trigger 세분화, shadow 전용 lock/cache, `ai_disabled` 자동 복구 probe는 2026-05-06 `AIEngineFlagOffBacklog0506`의 재분류 대상으로 남긴다.

### 10.3 체크리스트 상충 검토

- 본 보고서의 "P0 적용 전에는 2026-05-04 POSTCLOSE `dynamic_entry_ai_price_canary_p2` keep/OFF 판정을 권하지 않는다"는 문장은 2026-05-04 checklist의 `OrderbookMicroP2Canary0504-Postclose` 판정 일정과 조건부 상충이 있었다.
- 2026-05-02 반영으로 P0 중 overnight 정합화, failure helper 통일, dead code 삭제, 캐시 eviction/profile 분리가 적용되었으므로 해당 상충은 "P0 미적용 상태" 조건에서는 해소됐다.
- 다만 cooldown 공통화, auto recovery, protocol/shadow 격리는 아직 policy/backlog 성격이므로 2026-05-04 keep/OFF 판정의 필수 선행조건으로 올리면 active canary 일정과 다시 충돌한다.

## 11. 재검토 반영 및 호출량 재산정 (2026-05-02)

### 11.1 코드 재검토 반영 결과

- `_resolve_scalping_model_for_prompt`는 실제 `analyze_target` 경로에서 생성되지 않는 `scalping_watching`, `scalping_exit` 분기를 포함하고 있어 삭제했다. 현재 `analyze_target` 스캘핑 split prompt는 `watching/holding/exit/shared` 모두 Tier1 분석면으로 유지하고, `entry_price`, `holding_flow`, `overnight` 같은 중요 판단면은 각 전용 메서드에서 Tier2를 직접 사용한다.
- `entry_price`, `holding_flow`, `overnight` Tier2 성공 호출이 `analyze_target`의 `min_interval` 기준인 `last_call_time`을 갱신하지 않도록 분리했다. 이 변경은 provider 호출 횟수를 줄이는 변경은 아니지만, Tier2 판단 직후 Tier1 `analyze_target`이 불필요하게 `cooldown` 폴백되는 부작용을 차단한다.
- `Gemini/OpenAI/DeepSeek` 공통으로 `holding_flow` 입력 컨텍스트에 `decision_kind`별 `review_cadence` 지시를 추가했다. 장중 청산 후보는 30~90초 범위, 오버나이트 SELL_TODAY 재검문은 불필요하면 `next_review_sec=0`, 필요 시 300~600초를 권장한다.
- shadow 경로는 메인 `ai_disabled=True` 상태에서 신규 API 호출을 하지 않도록 막았다. shadow 실패를 메인 실패 카운터에 합산하는 정책은 shadow가 메인을 죽일 수 있어 이번 범위에서는 적용하지 않았다.
- `SCALPING_BUY_RECOVERY_CANARY_PROMPT`는 `ai_engine.py` 내부에서는 정의만 있으나 OpenAI/DeepSeek import, `sniper_state_handlers.py`의 `AI_MAIN_BUY_RECOVERY_CANARY_ENABLED=False` 가드 경로, 기존 shadow prompt 테스트와 연결되어 있다. 현재 live owner가 아니므로 삭제 대신 flag-off/legacy prompt로 유지한다.

### 11.2 Tier별 일간 호출량 추정

아래 수치는 기본 설정 기준의 상한/공식이다. 실제 호출량은 감시 종목 수, 보유 종목 수, 청산 후보 발생 수, cache hit, fast signature reuse에 따라 낮아진다.

| 구분 | 기존 대비 | Tier | 기본 cadence/trigger | 일간 호출량 산식 |
| --- | --- | --- | --- | --- |
| `analyze_target` watching | `2026-05-04` 완화 | Tier1 | `AI_WATCHING_COOLDOWN=90초`, 신규 매수 cutoff 15:00 | 감시 후보 1개당 최대 약 238~240회/일 (`09:03~15:00` 또는 `09:00~15:00`) |
| `analyze_target` holding/exit profile | `2026-05-04` 완화 | Tier1 | 일반 `45~180초`, critical `20~45초`, 가격변화 trigger 및 fast reuse 적용 | 보유 1개당 이론상 약 130회/일(180초)~1,170회/일(20초), 실제는 reuse/가격 trigger로 제한 |
| `evaluate_scalping_entry_price` | canary 신규/유지 | Tier2 | 제출 직전 가격 판단 후보별 1회 | AI 가격 canary 도달 후보 수와 동일 |
| `evaluate_scalping_holding_flow` intraday | `holding_flow_override` 신규축 | Tier2 | 청산 후보 발생 시 최초 1회, HOLD/TRIM이면 30~90초 재검문, `max_defer=90초` | 청산 후보 1건당 최대 3회 (`t=0/30/60`, `t>=90` force exit) |
| `evaluate_scalping_overnight_decision` | P0 정합화 후 동일 목적 | Tier2 | 15:20 이후 DB 기준 일 1회 gatekeeper 실행 | 오버나이트 판정 대상 SCALPING 보유 수와 동일 |
| `holding_flow` overnight SELL_TODAY 재검문 | 제한적 | Tier2 | 오버나이트 SELL_TODAY 후보 중 flow override 대상만 | 후보별 0~1회가 정상 기대값, 재검문 필요 시에만 추가 |

### 11.3 판정

- "HOLDING-only 시간대에 holding_flow가 모든 보유 종목에 대해 30~90초마다 호출된다"는 해석은 코드 기준으로는 부정확하다. 현재 호출점은 모든 HOLDING 루프가 아니라 `_holding_flow_override_applicable()`을 통과한 청산 후보에 한정된다.
- 다만 후보 1건당 최대 3회 Tier2 호출은 가능하므로, 호출 예산이 문제되면 첫 조정 대상은 `HOLDING_FLOW_REVIEW_MIN_INTERVAL_SEC` 상향이 아니라 `HOLDING_FLOW_OVERRIDE_MAX_DEFER_SEC`와 후보 적용 exit_rule 범위다. 현재 90초 max defer는 기대값 방어 목적상 짧은 canary 보류로 해석된다.
- 이번 수정 후 provider 호출 횟수 자체는 동일하나, Tier2 성공 호출이 Tier1 `analyze_target` cooldown을 밀어내는 비대칭 부작용은 제거됐다.
