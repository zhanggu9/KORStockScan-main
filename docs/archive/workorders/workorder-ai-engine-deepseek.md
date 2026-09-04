# 작업지시서: ai_engine_deepseek.py 신규 개발

작성일: 2026-04-24 KST  
대상: DeepSeek AI (코딩 에이전트)  
범위: `src/engine/ai_engine_deepseek.py` 신규 파일 생성  
ApplyTarget: 신규 파일 1개만 생성. 기존 파일(ai_engine.py, ai_engine_openai_v2.py, constants.py, 라우팅 파일) 수정 금지.

---

## 1. 목적 및 배경

현재 KORStockScan은 `GeminiSniperEngine` (ai_engine.py)을 기본 AI 엔진으로 사용한다.  
DeepSeek API는 OpenAI 호환 REST 엔드포인트를 제공하므로, 동일한 퍼블릭 인터페이스를 유지하면서 DeepSeek 백엔드로 교체 가능한 엔진 클래스 `DeepSeekSniperEngine`을 구현한다.

AI 엔진 라우팅(어느 호출지점에서 Gemini를 DeepSeek으로 교체할지)은 **이 작업지시서 범위 밖**이다.  
라우팅 부분은 별도 작업지시서로 Codex에 지시될 예정이므로, 이 파일은 **독립 실행 가능한 엔진 클래스**만 구현한다.

---

## 2. 참조 파일

| 파일 | 역할 |
|------|------|
| `src/engine/ai_engine.py` | 퍼블릭 인터페이스 및 내부 구조의 완전한 기준. `GeminiSniperEngine` 클래스를 100% 참조한다. |
| `src/engine/ai_engine_openai_v2.py` | OpenAI SDK 클라이언트 패턴 (키 로테이션, `_call_openai_safe`, JSON 파싱) 참조 |
| `data/config_prod.json` | API 키 위치 확인용 (실제 키 값은 코드에 하드코딩 금지) |
| `src/utils/constants.py` | `TRADING_RULES` 상수 참조 패턴 확인용 |

**DeepSeek API 공식 문서**: https://api-docs.deepseek.com/

---

## 3. API 연동 방식

### 3-1. 클라이언트 초기화

DeepSeek API는 OpenAI SDK와 완전히 호환된다. `openai` 패키지를 그대로 사용하되 `base_url`만 변경한다.

```python
from openai import OpenAI

client = OpenAI(
    api_key="<DEEPSEEK_API_KEY>",
    base_url="https://api.deepseek.com"
)
```

### 3-2. API 키 로딩

`data/config_prod.json`에서 `DEEPSEEK_API_KEY` 키를 읽는다.  
클래스 생성자는 `api_keys` 파라미터를 받고, 호출부에서 주입한다 (클래스 내부에서 config.json을 직접 읽지 않음).  
단일 키 문자열도 리스트로 정규화한다 (`GeminiSniperEngine.__init__` 패턴 동일).

### 3-3. 모델 티어 구성

| 티어 | 모델명 | 용도 |
|------|--------|------|
| Tier1 (fast) | `deepseek-v4-flash` | 초단타 스캘핑 실시간 분석 (최저지연) |
| Tier2 (balanced) | `deepseek-v4-flash` | 스윙/실시간 리포트 균형형 |
| Tier3 (deep) | `deepseek-v4-Pro` | 시장 브리핑, EOD 리더 발굴, 게이트키퍼 심층 추론 |

> 주의: 모델명은 `constants.py`의 `TRADING_RULES`에서 오버라이드 가능하도록 구현한다.
> 상수 키 이름: `DEEPSEEK_MODEL_TIER1`, `DEEPSEEK_MODEL_TIER2`, `DEEPSEEK_MODEL_TIER3`
> constants.py에 해당 상수가 없으면 위 표의 기본값을 fallback으로 사용한다.

---

## 4. 구현 클래스: DeepSeekSniperEngine

### 4-1. 클래스 선언 및 생성자

`GeminiSniperEngine.__init__` 구조를 그대로 따른다:

```python
class DeepSeekSniperEngine:
    def __init__(self, api_keys, announce_startup=True):
```

생성자에서 초기화할 속성:
- `self.api_keys` (list), `self.key_cycle` (itertools.cycle), `self.current_key` (str)
- `self.client` (OpenAI 인스턴스)
- `self.model_tier1_fast` → `TRADING_RULES.DEEPSEEK_MODEL_TIER1` 또는 `"deepseek-v4-flash"`
- `self.model_tier2_balanced` → `TRADING_RULES.DEEPSEEK_MODEL_TIER2` 또는 `"deepseek-v4-flash"`
- `self.model_tier3_deep` → `TRADING_RULES.DEEPSEEK_MODEL_TIER3` 또는 `"deepseek-v4-Pro"`
- `self.current_model_name` → `self.model_tier1_fast`
- `self.lock` (threading.Lock), `self.api_call_lock` (threading.Lock)
- `self.last_call_time` (float = 0), `self.min_interval` → `TRADING_RULES.DEEPSEEK_ENGINE_MIN_INTERVAL` 또는 `0.5`
- `self.consecutive_failures` (int = 0), `self.ai_disabled` (bool = False)
- `self.max_consecutive_failures` → `TRADING_RULES.AI_MAX_CONSECUTIVE_FAILURES` 또는 `5`
- `self.cache_lock` (threading.RLock)
- `self.analysis_cache_ttl` → `TRADING_RULES.AI_ANALYZE_RESULT_CACHE_TTL_SEC` 또는 `8.0`
- `self.holding_analysis_cache_ttl` → `TRADING_RULES.AI_HOLDING_RESULT_CACHE_TTL_SEC` 또는 `max(8.0, 30.0)`
- `self.gatekeeper_cache_ttl` → `TRADING_RULES.AI_GATEKEEPER_RESULT_CACHE_TTL_SEC` 또는 `12.0`
- `self._analysis_cache` (dict = {}), `self._gatekeeper_cache` (dict = {})
- `self.current_api_key_index` (int = 0)

시작 배너 출력:
```
🧠 [DeepSeek 엔진] N개 키 로테이션 가동! (T1: deepseek-v4-flash / T2: deepseek-v4-flash / T3: deepseek-v4-Pro)
```

### 4-2. 내부 헬퍼 메서드 (GeminiSniperEngine와 동일하게 구현)

아래 메서드들은 `ai_engine.py`의 `GeminiSniperEngine` 구현을 **그대로 복사**하되, Gemini 전용 의존성(`google.genai` 등)을 제거한다:

| 메서드 | 원본 위치 (ai_engine.py 기준 라인) | 비고 |
|--------|-------------------------------------|------|
| `_rotate_client()` | 553행 근처 | `OpenAI(api_key=..., base_url="https://api.deepseek.com")` 사용 |
| `_get_tier1_model()` | 562행 | 동일 |
| `_get_tier2_model()` | 569행 | 동일 |
| `_get_tier3_model()` | 573행 | 동일 |
| `_normalize_for_cache()` | 575행 | 동일 복사 |
| `_build_cache_digest()` | 601행 | 동일 복사 |
| `_cache_get()` | 606행 | 동일 복사 |
| `_cache_set()` | 624행 | 동일 복사 |
| `_build_analysis_cache_key()` | 642행 | 동일 복사 |
| `_build_analysis_cache_key_with_profile()` | 위임 형태 | 동일 복사 |
| `_bucket_int_for_cache()` | 653행 | 동일 복사 |
| `_bucket_float_for_cache()` | 660행 | 동일 복사 |
| `_price_bucket_step_for_cache()` | 669행 | 동일 복사 |
| `_get_best_levels_for_cache()` | 684행 | 동일 복사 |
| `_compact_holding_ws_for_cache()` | 694행 | 동일 복사 |
| `_resolve_analysis_cache_ttl()` | 804행 | 동일 복사 |
| `_annotate_analysis_result()` | 809행 | 동일 복사 |
| `_resolve_scalping_prompt()` | 835행 | 동일 복사 |
| `_normalize_scalping_action_schema()` | 849행 | 동일 복사 |
| `_apply_remote_entry_guard()` | 902행 | 동일 복사 |
| `_format_market_data()` | 1259행 | 동일 복사 |
| `_format_swing_market_data()` | 1447행 | 동일 복사 |
| `_infer_realtime_mode()` | 1726행 | 동일 복사 |
| `_get_realtime_prompt()` | 1790행 | 동일 복사 |

### 4-3. 핵심 API 호출기: `_call_deepseek_safe()`

`GeminiSniperEngine._call_gemini_safe()` 또는 `GPTSniperEngine._call_openai_safe()`에 해당하는 중앙 집중식 호출기.

```python
def _call_deepseek_safe(
    self,
    prompt,
    user_input,
    require_json=True,
    context_name="Unknown",
    model_override=None,
    temperature_override=None,
):
```

구현 요건:
1. `self.api_call_lock`으로 동시 호출 직렬화
2. `messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_input}]` 조립 (prompt가 None이면 user만)
3. `require_json=True`이면 `response_format={"type": "json_object"}` 추가
4. `temperature`: require_json이면 `0.0`, 텍스트면 `0.7` (temperature_override 우선)
5. `model`: `model_override` 우선, 없으면 `self.current_model_name`
6. 키 로테이션 루프: `len(self.api_keys)`번 시도
7. 성공 시: JSON이면 `_parse_json_response_text(raw_text)` 반환, 텍스트면 raw 반환
8. 실패 처리:
   - `RateLimitError` 또는 429/quota/503 포함 에러: 키 교체 후 `time.sleep(0.8)` 후 재시도
   - 그 외 에러: `RuntimeError` 즉시 raise
9. 모든 키 소진 시: `log_error` 호출 후 `RuntimeError` raise
10. **Google Search 도구 미지원**: `use_google_search` 파라미터가 넘어와도 무시 (DeepSeek API는 Google Search 미지원)

`_parse_json_response_text()` 메서드: `ai_engine_openai_v2.py`의 `GPTSniperEngine._parse_json_response_text()` 구현을 그대로 복사.

### 4-4. 퍼블릭 메서드 (GeminiSniperEngine 인터페이스 100% 호환)

아래 메서드들은 `ai_engine.py`를 참조하여 **동일한 시그니처와 반환 구조**로 구현한다.  
내부 `_call_gemini_safe()` 호출을 `_call_deepseek_safe()`로 교체하는 것이 핵심 변경사항이다.

#### (A) `analyze_target()` — 핵심 실시간 분석 (ai_engine.py 1493행)
```python
def analyze_target(
    self,
    target_name,
    ws_data,
    recent_ticks,
    recent_candles,
    strategy="SCALPING",
    program_net_qty=0,
    cache_profile="default",
    prompt_profile="shared",
)
```
- 캐시 조회/저장 로직 동일 유지
- `strategy in ["KOSPI_ML", "KOSDAQ_ML"]` → Tier2 모델 사용
- 그 외 (SCALPING) → Tier1 모델 사용
- `_apply_remote_entry_guard`, `_normalize_scalping_action_schema`, `feature_audit_fields` 로직 동일 유지
- `use_google_search` 인자 전달 불필요 (DeepSeek 미지원)

#### (B) `analyze_target_shadow_prompt()` — 그림자 프롬프트 분석 (ai_engine.py 935행)
- 동일 시그니처, `_call_deepseek_safe()` 교체만

#### (C) `analyze_scanner_results()` — 텔레그램 시장 브리핑 (ai_engine.py 1695행)
```python
def analyze_scanner_results(self, total_count, survived_count, stats_text, macro_text="")
```
- Tier3 모델 사용
- `use_google_search=True` 옵션 **제거** (DeepSeek 미지원)
- 대신 `require_json=False`로 텍스트 응답만 받음
- 나머지 로직 동일

#### (D) `evaluate_realtime_gatekeeper()` (ai_engine.py 1929행)
```python
def evaluate_realtime_gatekeeper(self, stock_name, stock_code, realtime_ctx, analysis_mode="AUTO")
```
- 동일 시그니처, Tier3 모델 교체, `_call_deepseek_safe()` 사용

#### (E) `evaluate_scalping_overnight_decision()` (ai_engine.py 1990행)
```python
def evaluate_scalping_overnight_decision(self, stock_name, stock_code, realtime_ctx)
```
- 동일 시그니처, `_call_deepseek_safe()` 교체

#### (F) `evaluate_condition_entry()` (ai_engine.py 2026행)
```python
def evaluate_condition_entry(self, stock_name, stock_code, ws_data, recent_ticks, recent_candles, condition_profile)
```
- 동일 시그니처 유지. `2026-05-02` 이후 조건검색 전용 프롬프트/endpoint는 런타임에서 제거하고 기존 scalping entry 라우팅 결과를 condition 호환 응답으로 변환한다.

#### (G) `evaluate_condition_exit()` (ai_engine.py 2057행)
```python
def evaluate_condition_exit(self, stock_name, stock_code, ws_data, recent_ticks, recent_candles, condition_profile, profit_rate, peak_profit, current_ai_score)
```
- 동일 시그니처 유지. `2026-05-02` 이후 조건검색 전용 프롬프트/endpoint는 런타임에서 제거하고 기존 scalping exit 라우팅 결과를 condition 호환 응답으로 변환한다.

---

## 5. 시스템 프롬프트

`ai_engine.py` 상단에 정의된 모든 시스템 프롬프트 상수를 **그대로 import**하거나 동일 내용으로 파일 상단에 재정의한다.  
재정의 방식을 권장한다 (순환 import 방지):

```python
# ai_engine.py 의 프롬프트를 직접 import (ai_engine이 변경되어도 동기화됨)
from src.engine.ai_engine import (
    SCALPING_SYSTEM_PROMPT,
    SCALPING_WATCHING_SYSTEM_PROMPT,
    SCALPING_HOLDING_SYSTEM_PROMPT,
    SCALPING_SYSTEM_PROMPT_V3,
    SCALPING_SYSTEM_PROMPT_75_CANARY,
    SCALPING_BUY_RECOVERY_CANARY_PROMPT,
    SWING_SYSTEM_PROMPT,
    ENHANCED_MARKET_ANALYSIS_PROMPT,
    REALTIME_ANALYSIS_PROMPT_SCALP,
    REALTIME_ANALYSIS_PROMPT_SWING,
    REALTIME_ANALYSIS_PROMPT_DUAL,
    SCALPING_OVERNIGHT_DECISION_PROMPT,
    EOD_TOMORROW_LEADER_PROMPT,
    EOD_TOMORROW_LEADER_JSON_PROMPT,
    DUAL_PERSONA_AGGRESSIVE_PROMPT,
    DUAL_PERSONA_CONSERVATIVE_PROMPT,
)
```

`prompt_profile="exit"`는 별도 시스템 프롬프트를 갖지 않고 `SCALPING_HOLDING_SYSTEM_PROMPT` / `holding_exit_v1` 호환 경로로 처리한다. 조건검색 exit adapter도 런타임에서는 scalping holding route를 재사용한다.

---

## 6. imports 및 파일 헤더

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import threading
import json
import re
import hashlib
from datetime import datetime, timezone
from itertools import cycle
from openai import OpenAI, RateLimitError

from src.engine.scalping_feature_packet import (
    build_scalping_feature_audit_fields,
    extract_scalping_feature_packet,
)
from src.utils.logger import log_error
from src.utils.constants import TRADING_RULES
from src.engine.macro_briefing_complete import build_scanner_data_input
from src.engine.sniper_position_tags import normalize_position_tag
from src.engine.ai_engine import (
    SCALPING_SYSTEM_PROMPT,
    # ... (5장 참조)
)
```

---

## 7. constants.py 신규 상수 선언 안내 (별도 작업)

아래 상수는 `constants.py`에 **이 작업지시서 범위 밖에서** 추가되어야 한다.  
현재는 fallback 기본값으로 동작하므로, 이 파일만으로 즉시 실행 가능하다.

```python
# TRADING_RULES 클래스 내 추가 권장 상수
DEEPSEEK_MODEL_TIER1: str = "deepseek-v4-flash"
DEEPSEEK_MODEL_TIER2: str = "deepseek-v4-flash"
DEEPSEEK_MODEL_TIER3: str = "deepseek-v4-Pro"
DEEPSEEK_ENGINE_MIN_INTERVAL: float = 0.5
```

---

## 8. 구현 제약 및 금지 사항

1. **Google Search 도구 사용 금지**: DeepSeek API는 Google Search 도구를 지원하지 않는다. `use_google_search` 파라미터 관련 코드 블록 모두 제거/무시.
2. **기존 파일 수정 금지**: `ai_engine.py`, `ai_engine_openai_v2.py`, `constants.py`, 라우팅 파일, 스나이퍼 파일 등 일체 수정 금지.
3. **API 키 하드코딩 금지**: config에서 주입받는 구조 유지.
4. **실거래 주문 로직 변경 금지**: 이 파일은 AI 분석 응답만 생성하며, 주문 제출/매수·매도 판단 threshold/canary flag를 변경하지 않는다.
5. **인터페이스 호환성 필수**: `DeepSeekSniperEngine`의 모든 퍼블릭 메서드는 `GeminiSniperEngine`과 동일한 시그니처 및 반환 dict 구조를 유지해야 한다. 라우팅 레이어에서 duck-typing으로 교체 가능해야 한다.
6. **반환 dict 구조 동일 유지**: `_annotate_analysis_result()`가 추가하는 메타 필드(`ai_parse_ok`, `ai_response_ms`, `ai_model_tier` 등) 포함 완전 동일.

---

## 9. 출력 파일

- **생성**: `src/engine/ai_engine_deepseek.py` (단일 파일)
- **수정 없음**: 나머지 모든 파일

---

## 10. 검증 기준

구현 완료 후 아래를 확인한다:

1. `from src.engine.ai_engine_deepseek import DeepSeekSniperEngine` import 성공
2. `DeepSeekSniperEngine(api_keys=["test_key"])` 인스턴스 생성 시 배너 출력 확인
3. `analyze_target()` 호출 시그니처가 `GeminiSniperEngine.analyze_target()`과 완전 동일
4. `_call_deepseek_safe()`에서 RateLimitError 시 키 로테이션 동작 확인 (단위 테스트 불필요, 코드 로직 검토로 대체)
5. `analyze_scanner_results()`에서 `use_google_search` 관련 코드 없음 확인
