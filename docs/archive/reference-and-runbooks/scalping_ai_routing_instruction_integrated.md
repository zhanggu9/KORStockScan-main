# 작업지시서: 스캘핑 AI 모델 라우팅 정리 + 진입/청산 프롬프트 구조화 + 입력 스키마 개선

---

## 최종 목표

스캘핑 매매 AI 호출의 서버별 모델 라우팅을 정리하고,

스캘핑 **진입 프롬프트 / 청산(보유) 프롬프트**를 명시적으로 분리 운영 가능하게 만들며,

입력 토큰을 줄이고 판단 일관성을 높이기 위한 **입력 스키마 개선 설계**까지 반영한다.

---

## 적용 원칙 요약

### 메인서버

- **메인서버의 스캘핑 매매 프롬프트에만 OpenAI 경로를 적용한다.**
- 메인서버의 **스캘핑 매매 프롬프트에만 `gpt-5.4-nano`를 사용한다.**
- 호출 엔진은 반드시 **`ai_engine_openai_v2.py`** 를 사용한다.
- 일반 AI 호출은 기존 로직을 유지하고, 스캘핑 매매 프롬프트는 입력스키마를 개선한다.

### 원격 서버

- 원격 서버는 OpenAI 경로로 바꾸지 않고 스캘핑 매매 프롬프트 입력스키마는 개선한다.
- 원격 서버는 기존 **`tier2 Gemini flash`를 `tier1 Gemini flash lite`로 변경**한다.
- 그 외 원격 서버 라우팅 구조는 유지한다.

### 엔진 구조

- 스캘핑 프롬프트가 **진입 / 보유 / 청산** 구조로 분리돼 있다면, **`ai_engine_openai_v2.py`도 `ai_engine.py`와 동일한 분기 구조**를 갖도록 맞춘다.
- 즉, 메인서버에서는 엔진만 OpenAI v2로 바뀌고, 스캘핑 판단 로직 구조는 기존 `ai_engine.py`와 의미적으로 동일해야 한다.

---

## 현재 프롬프트 상태 인식

현재 업로드된 스캘핑 프롬프트는 다음 성격을 가진다.

### 1. 진입 프롬프트

현재 진입 프롬프트는 다음 역할이다.

- 페르소나: **극강 공격적 초단타 진입 트레이더**
- 목표: **지금 이 순간 진입해도 기대값이 플러스인지 판단**
- 출력:
  - `BUY`: 즉시 진입 유효
  - `WAIT`: 관찰 유지
  - `DROP`: 진입 금지

주요 특징:

- 이미 기계 게이트(유동성/갭/모멘텀)는 통과했다고 가정
- 모델은 **돌파 지속 가능성**만 판단
- 입력이 매우 길고 원문 데이터가 많음
- 실제 필요한 판단보다 원시 입력이 과다할 가능성이 높음

### 2. 청산/보유 프롬프트

현재 보유 프롬프트는 다음 역할이다.

- 페르소나: **초단타 보유 포지션 리스크 매니저**
- 목표: **추세 유지 vs 즉시 이탈**
- 출력:
  - `BUY`
  - `WAIT`
  - `DROP` ← 현재는 사실상 EXIT 신호로 사용

주요 특징:

- 현재 청산 action schema가 완전히 분리되지 않음
- `DROP`이 실질적으로 청산/이탈 의미를 담당
- 진입 프롬프트와 입력 구조는 유사하지만, 판단 초점은 완전히 다름
- 따라서 장기적으로는 **진입/보유/청산의 논리와 액션 스키마를 더 명시적으로 분리**하는 것이 바람직함

---

## 핵심 작업 요구사항

### 1. 서버별 모델 라우팅 변경

#### 메인서버

메인서버의 스캘핑 프롬프트에 한해서만:

- 엔진: `ai_engine_openai_v2.py`
- 모델: `gpt-5.4-nano`

적용 대상:

- `scalping_entry`
- `scalping_holding`
- `scalping_exit`
  (또는 프로젝트 내 실제 동등 개념의 스캘핑 판단 태스크)

주의:

- 메인서버의 일반 분석/리포트/장문 추론/기타 AI 호출은 변경하지 말 것
- 전체 기본 모델을 `gpt-5.4-nano`로 바꾸지 말 것

#### 원격 서버

원격 서버에서는:

- 기존 `tier2 Gemini flash` → `tier1 Gemini flash lite`로 변경
- OpenAI v2 경로로 변경하지 말 것
- 기존 원격 서버 동작 구조는 최대한 유지

---

### 2. 가능할 경우 스캘핑 프롬프트 분기 명시화

스캘핑 프롬프트는 최소한 다음 세 가지로 명시적으로 구분 가능해야 한다.

- `scalping_entry`
- `scalping_holding`
- `scalping_exit`

프로젝트 구조상 `holding`과 `exit`가 아직 분리되지 않았다면, 우선은 기존 동작을 유지한다.

---

### 3. ai_engine_openai_v2.py 구조 동형화

`ai_engine_openai_v2.py`는 단순히 모델만 바꾸는 파일이 아니라, 스캘핑 프롬프트 처리 구조가 `ai_engine.py`와 **동일한 의미 구조**를 가져야 한다.

#### 반드시 맞춰야 할 것

- 스캘핑 진입 판단 분기
- 스캘핑 보유 판단 분기
- 스캘핑 청산 판단 분기
- 요청 조립 방식
- 응답 파싱 방식
- 예외 처리 / fallback 흐름
- task_type 또는 prompt_type 기반 라우팅

#### 구현 원칙

- `ai_engine.py` 전체를 무식하게 복붙하지 말 것
- 스캘핑 판단에 필요한 구조만 동형으로 맞출 것
- 호출부에서 엔진만 바꿔도 의미상 동일하게 동작하도록 만들 것

---

### 4. 입력 스키마 개선 설계 반영

#### 배경

현재 스캘핑 입력은 다음 문제를 가진다.

- 1분봉 원문이 길다
- 호가창 원문이 길다
- 최근 10틱 상세 원문이 길다
- 자연어 설명 중복이 있다
- 모델 판단에 꼭 필요하지 않은 raw text가 많다

현재 프롬프트는 시장 상태를 풍부하게 보여주지만, `gpt-5.4-nano` 같은 저비용/고빈도 모델에는 **입력이 너무 비대할 가능성**이 높다.

따라서 이번 작업에서는 단순 모델 교체만 하지 말고, 메인서버와 원격서버 모두 **입력 스키마를 축약 가능한 구조로 개선**을 코드에 반영해야 한다.

---

## 입력 스키마 개선 목표

### 목표 1. 원시 텍스트 대신 구조화된 수치 입력 우선

- 자연어 원문 나열 축소
- 로컬 전처리 후 수치/카테고리 피처 전달
- 모델은 "판단"에 집중
- 계산 가능한 정보는 사전에 계산해서 넣기

### 목표 2. 진입/보유/청산의 입력 목적 분리

입력은 공통 필드 + 태스크별 추가 필드로 구성한다.

- `entry`: 돌파 지속 가능성
- `holding`: 추세 유지/재가속 가능성
- `exit`: 하방 리스크 확대 및 즉시 이탈 필요성

### 목표 3. 토큰 절감

원문 1분봉/틱/호가를 전부 주입하지 말고, 핵심 파생 피처 중심으로 바꿔 토큰 수를 대폭 줄인다.

---

## 권장 입력 스키마 설계

아래는 권장 구조다. 실제 구현은 프로젝트 타입에 맞게 필드명 조정 가능하지만, 핵심 개념은 유지한다.

```json
{
  "task_type": "scalping_entry | scalping_holding | scalping_exit",

  "market_context": {
    "symbol": "string",
    "current_price": 0,
    "pct_change_from_prev_close": 0.0,
    "session_high": 0,
    "distance_from_high_pct": 0.0,
    "ws_trade_strength": 0.0
  },

  "micro_structure": {
    "price_vs_5ma_pct": 0.0,
    "price_vs_micro_vwap_pct": 0.0,
    "orderbook_imbalance_ratio": 0.0,
    "best_ask_size": 0,
    "best_bid_size": 0,
    "sell_wall_nearby": true,
    "buy_support_nearby": true
  },

  "flow_summary": {
    "volume_ratio_vs_recent_avg": 0.0,
    "tick_speed_sec_for_10ticks": 0.0,
    "buy_pressure_pct": 0.0,
    "trade_strength_now": 0.0,
    "trade_strength_delta_10ticks": 0.0
  },

  "minute_bar_features": {
    "bars_used": 10,
    "close_change_1m_pct": 0.0,
    "close_change_3m_pct": 0.0,
    "close_change_5m_pct": 0.0,
    "high_breakout_attempts": 0,
    "pullback_depth_pct": 0.0,
    "range_expansion_pct": 0.0,
    "close_position_in_range_pct": 0.0,
    "volume_trend": "up | flat | down"
  },

  "tick_features": {
    "last_tick_direction": "up | flat | down",
    "uptick_count_10": 0,
    "downtick_count_10": 0,
    "neutral_tick_count_10": 0,
    "largest_trade_side": "buy | sell | neutral",
    "largest_trade_size": 0
  },

  "task_specific": {
    "entry": {
      "breakout_level": 0,
      "breakout_reclaim_success": true,
      "absorption_success": true,
      "chasing_risk_pct": 0.0
    },
    "holding": {
      "entry_price": 0,
      "unrealized_pnl_pct": 0.0,
      "peak_pnl_pct": 0.0,
      "drawdown_from_peak_pct": 0.0,
      "trend_persistence_score": 0.0
    },
    "exit": {
      "entry_price": 0,
      "unrealized_pnl_pct": 0.0,
      "drawdown_from_peak_pct": 0.0,
      "breakdown_risk_score": 0.0,
      "support_loss_confirmed": true
    }
  }
}
```

---

### 5. 입력 스키마 개선의 구체 구현 요구

#### A. 원시 데이터 직접 주입 최소화

다음은 가능하면 원문 그대로 넣지 말 것:

- 최근 1분봉 40줄 전체
- 최근 10틱 상세 원문 전체
- 호가 10레벨 전체
- 설명형 자연어 중복 문장

#### B. 로컬 전처리 후 파생 피처 생성

다음 값은 코드에서 미리 계산해 전달하는 것을 우선 검토한다.

**공통 피처**

- 현재가 vs 5MA 괴리율
- 현재가 vs Micro-VWAP 괴리율
- 고점 대비 이격도
- 거래량 비율
- 체결강도 현재값
- 체결강도 변화량
- 틱 속도
- 최근 10틱 매수 압도율
- 호가 불균형 비율
- 직근 매도벽/매수받침 존재 여부

**진입 전용 피처**

- 돌파 레벨 재안착 여부
- 직전 눌림 후 회복 성공 여부
- 추격 진입 리스크
- 고점 인접 재돌파 시도 횟수
- 돌파 직후 거래량 유지 여부

**보유 전용 피처**

- 진입가 대비 수익률
- 최고 수익 대비 되밀림 폭
- VWAP/5MA 이탈 여부
- 추세 유지 점수
- 재가속 가능성 점수

**청산 전용 피처**

- 지지 이탈 여부
- 매도벽 확대 여부
- 체결강도 붕괴 여부
- 하락 틱 연속성
- 반등 실패 횟수
- 익절 후반부 되밀림 심화 여부

#### C. task_type 기반 프롬프트 구성

프롬프트는 다음 구조로 단순화하는 것이 목표다.

1. 시스템 역할
2. task_type별 판단 원칙
3. 구조화된 입력 JSON
4. 고정 JSON 응답 스키마

즉, 장문의 자연어 브리핑 덩어리를 계속 붙이는 방식이 아니라, **구조화된 데이터 + 짧은 규칙** 중심으로 바꾸는 방향으로 설계한다.

---

### 6. 진입 프롬프트 개선 요구

현재 진입 프롬프트는 "이미 기계 게이트를 통과했으니 돌파 지속만 본다"는 점은 좋다. 다만 입력이 과도하게 길고, 일부 피처는 진입 판단보다 보유/청산에 더 가까운 정보도 섞여 있다.

#### 개선 방향

- 진입 프롬프트는 **돌파 지속 / 흡수 성공 / 속도 유지** 중심으로 좁힌다.
- 보유나 청산에 가까운 피처는 최소화한다.
- 응답은 기존처럼 유지 가능: `BUY` / `WAIT` / `DROP`

#### 진입 프롬프트용 입력 핵심

- 현재가 vs 돌파 레벨
- 현재가 vs Micro-VWAP
- 현재가 vs 5MA
- 최근 10틱 매수 압도율
- 틱 속도
- 거래량 유지율
- 직근 매도벽 압박
- 돌파 재안착 여부
- 추격 리스크

---

### 7. 보유/청산 프롬프트 개선 요구

현재 보유 프롬프트는 `DROP`을 사실상 청산으로 사용하는 상태다. 즉시 운영상 문제는 없지만, 코드 구조상으로는 아래 둘을 분리 가능하게 정리해야 한다.

- `holding`: 보유 지속 가능성
- `exit`: 즉시 이탈 필요성

#### 요구사항

- 당장 액션 스키마를 바꾸지 않더라도 내부 task 구분은 가능하게 만들 것
- 프롬프트 또는 라우팅 상에서 `scalping_holding`과 `scalping_exit`를 분리 수용 가능하게 설계할 것
- 향후 `EXIT` 액션을 독립시켜도 파급이 작도록 구조화할 것

#### 보유/청산 입력 핵심

- 진입가 대비 수익률
- 최고 수익 대비 되밀림 폭
- VWAP 하회 여부
- 5MA 하회 여부
- 체결강도 둔화/붕괴
- 하락 틱 연속성
- 반등 실패
- 지지 이탈 확인
- 매도벽 확대

---

### 8. 라우팅 구현 지침

#### 권장 task_type

가능하면 호출부에서 명시적으로 아래 값을 넘긴다.

- `scalping_entry`
- `scalping_holding`
- `scalping_exit`

문자열 본문 분석으로 추론하지 말고, 가능하면 타입/enum/상수로 식별한다.

#### 메인서버 라우팅 규칙

| task_type | 엔진 | 모델 |
|---|---|---|
| `scalping_entry` | `ai_engine_openai_v2.py` | `gpt-5.4-nano` |
| `scalping_holding` | `ai_engine_openai_v2.py` | `gpt-5.4-nano` |
| `scalping_exit` | `ai_engine_openai_v2.py` | `gpt-5.4-nano` |

#### 원격 서버 라우팅 규칙

- 원격 서버 스캘핑 경로 → 기존 Gemini 경로 유지
- 단, `tier2 Gemini flash` → `tier1 Gemini flash lite`로 변경

---

### 9. 절대 금지사항

- 전체 기본 모델을 `gpt-5.4-nano`로 바꾸지 말 것
- 원격 서버를 OpenAI 경로로 바꾸지 말 것
- 일반 AI 호출 모델까지 바꾸지 말 것
- `ai_engine_openai_v2.py`를 우회하는 새 경로를 만들지 말 것
- 스캘핑과 무관한 기능까지 범위를 넓히지 말 것
- 원시 입력을 더 늘리는 방향으로 수정하지 말 것
- 임시 디버그 코드/출력 남기지 말 것

---

### 10. 검증 항목

#### 메인서버

| # | task | 엔진 | 모델 |
|---|---|---|---|
| 1 | `scalping_entry` | `ai_engine_openai_v2.py` | `gpt-5.4-nano` |
| 2 | `scalping_holding` | `ai_engine_openai_v2.py` | `gpt-5.4-nano` |
| 3 | `scalping_exit` | `ai_engine_openai_v2.py` | `gpt-5.4-nano` |
| 4 | 일반 호출 | 기존 모델 유지 | 회귀 없음 |

#### 원격 서버

| # | 항목 | 확인 내용 |
|---|---|---|
| 5 | 기존 `tier2 Gemini flash` 사용 경로 | `tier1 Gemini flash lite`로 교체 확인 |
| 6 | 원격 서버 비대상 기능 | 기존 구조 유지, OpenAI v2로 바뀌지 않음 |

#### 입력 스키마

| # | 항목 |
|---|---|
| 7 | 기존 raw 입력 대비 구조화된 필드 중심으로 줄어들었는지, 동일 판단에 필요한 핵심 피처가 유지되는지 |
| 8 | 각 task_type이 서로 다른 목적의 피처를 받는지, 프롬프트 목적과 입력이 정렬되어 있는지 |

---

### 11. 최종 산출물 형식

작업 완료 후 아래 순서로 보고한다.

#### 1. 변경 파일 목록

- 수정 파일명
- 수정 이유 1줄

#### 2. 메인서버 적용 내용

- 어떤 기준으로 스캘핑 프롬프트를 식별했는지
- 왜 `ai_engine_openai_v2.py`를 타게 했는지
- 어디서 `gpt-5.4-nano`를 강제했는지

#### 3. 원격 서버 적용 내용

- `tier2 Gemini flash` 위치
- `tier1 Gemini flash lite`로의 교체 방식

#### 4. 엔진 구조 정합성

- `ai_engine.py` 대비 `ai_engine_openai_v2.py`에서 맞춘 분기
- 진입/보유/청산 구조가 어떻게 동형화되었는지

#### 5. 입력 스키마 개선 내용

- 어떤 raw 입력을 줄였는지
- 어떤 파생 피처를 추가했는지
- 진입/보유/청산별로 어떤 필드가 달라졌는지

#### 6. 검증 결과

- 메인서버 스캘핑 3종 task 모델 확인
- 원격 서버 Gemini tier 변경 확인
- 일반 기능 회귀 여부

#### 7. 잔여 리스크

- 아직 task_type 식별이 취약한 부분
- 향후 `EXIT` 액션 독립 필요 여부
- 서버별 라우팅 상수 통합 필요 여부

---

### 12. Codex 작업 순서

1. `ai_engine.py`와 `ai_engine_openai_v2.py`의 구조를 비교한다.
2. 스캘핑 진입/보유/청산 분기 존재 여부를 먼저 확인한다.
3. 메인서버 스캘핑 경로를 `ai_engine_openai_v2.py`로 고정한다.
4. 메인서버 스캘핑 모델을 `gpt-5.4-nano`로 강제한다.
5. 원격 서버의 `tier2 Gemini flash`를 `tier1 Gemini flash lite`로 교체한다.
6. 입력 스키마에서 raw 데이터 과다 주입 지점을 찾는다.
7. 구조화된 입력 필드와 파생 피처 중심으로 축약 설계를 반영한다.
8. 가능하면 진입/보유/청산별 task_type과 필드 차이를 명확히 만든다.
9. 일반 기능 회귀 없이 변경 범위를 최소화한다.
10. 최종적으로 파일별 diff 관점에서 설명 가능한 상태로 정리한다.

---

## 최종 한줄 요구

> **메인서버의 스캘핑 진입/보유/청산 프롬프트에만 `gpt-5.4-nano`를 적용하고 반드시 `ai_engine_openai_v2.py`를 사용하게 하며, 원격 서버는 기존 `tier2 Gemini flash`를 `tier1 Gemini flash lite`로 변경하고, `ai_engine_openai_v2.py`를 `ai_engine.py`와 동일한 스캘핑 분기 구조로 맞추며, 동시에 스캘핑 진입/청산 프롬프트의 입력 스키마를 raw 원문 중심에서 구조화된 파생 피처 중심으로 개선하라.**
