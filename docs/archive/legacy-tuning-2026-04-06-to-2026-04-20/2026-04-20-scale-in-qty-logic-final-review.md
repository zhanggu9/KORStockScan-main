# [최종 통합안] 스켈핑 추가매수 로직 및 연관 파이프라인 최적화

**기준 일자:** 2026-04-20  
**대상 시스템:** KORStockScan 자동매매 (Scalping 전략)  
**문서 성격:** 1차 검토의견 + 2차 검토의견(트레이더 통합 보고서) 비교 후 확정안  
**작성 방식:** 두 의견의 공통 진단은 통합, 상충/상보 부분은 근거 기반으로 재조정

---

## 0) 요약 (Executive Summary)

두 검토의견은 **스케일인 수량 로직의 구조적 결함**(`int(1 × 0.5) = 0` 차단)에 대해 완전히 일치된 진단을 내렸다. 차이는 해법의 정밀도와 범위에 있다.

- **1차 검토(수량 전용)**: "리스크 예산 기반 + 포지션 비율 보조"의 이중 기준 공식을 제안. 세부 비율(PYRAMID 0.08, REVERSAL_ADD 0.05 등)까지 제시.
- **2차 검토(파이프라인 전체)**: 수량 이슈를 `max(1, int(...))` 수준의 미니멀 패치로 보고, **지연(Latency) 블록과 AI 프롬프트 문맥 분리**를 더 큰 EV 누수원으로 지목.

두 관점은 충돌하지 않고 **상보적**이다. 수량 로직은 EV가 살아있을 때 이를 실행으로 전환하는 **라스트 마일**이고, 2차 검토가 지적한 지연·프롬프트는 **EV 생성 단계**의 문제다. 둘 다 고쳐야 이수스페셜티케미컬 같은 사례가 재발하지 않는다.

**최종안의 핵심은 세 가지다.**
1. 수량 공식을 **리스크 예산 기반(Primary) + 포지션 비율(Secondary) + 1주 플로어(Floor)** 의 3단 구조로 확정.
2. 지연 블록(`latency_block`)과 AI `WAIT 65` 코호트를 **단일 축 카나리아**로 분리 검증.
3. `HOLDING` 전용 프롬프트 분리 및 Raw 배열 경량화는 **P0 핫픽스**로 동시 진행.

---

## 0-1) 운영 정합성 보정 (현재 플랜과 충돌하는 지점)

이 문서의 원안은 방향은 맞지만, **현재 운영 원칙과 바로 충돌하는 부분**이 있다. 그대로 실행하면 관찰축이 흔들릴 수 있으므로 아래처럼 보정해야 한다.

| 항목 | 원안 | 현재 운영 원칙 | 보정안 |
|---|---|---|---|
| `04-20` 동시 3축 병렬 착수 | `split-entry`, `latency`, `scale-in qty`를 같은 날 병렬 시작 | 현재는 `split-entry/HOLDING` 우선, `한 번에 한 축 canary`, 원격 신규 canary 강제 보류 | `04-20~04-22`에는 scale-in 실반영 금지. 문서/계측 준비만 수행 |
| 메인/원격 동시 반영 | 같은 주간 내 메인과 원격에 모두 패치 반영 전제 | `develop=원격`, `main=본서버`, `main` 선반영 금지 | `원격 shadow-only -> 원격 canary -> main code-load(flag OFF) -> main canary` 순서로 분리 |
| `HOLDING` 프롬프트 분리 P0 동시진행 | 수량 로직과 같은 우선순위로 바로 반영 | 현재 `HOLDING`은 `shadow-only + D+2` 관찰축 유지 중 | `HOLDING`은 기존 일정 유지, scale-in은 별도 축으로 추가만 하고 섞지 않음 |
| `SCALPING_MAX_BUY_BUDGET_KRW`의 scale-in 확장 해석 | scale-in 정책과 함께 재결정 제안 | 현재 코드는 신규 진입 예산 캡 전용이며 scale-in에는 미적용 | 이번 축에서는 `MAX_POSITION_PCT`만 유지. 절대예산 캡의 scale-in 확장은 별도 정책 과제로 분리 |
| `min 1 lot` 즉시 적용 | `PYRAMID/REVERSAL_ADD` 최소 1주 즉시 허용 | 현재 운영은 소수 포지션에서 `zero_qty`를 그대로 차단 | `feature flag + shadow calc`로 먼저 관찰하고, remote canary에서만 실주문 적용 여부 판정 |

핵심은 **수량 공식 자체는 유효하되, 반영 순서와 토글 설계가 현재 운영원칙에 맞게 조정되어야 한다**는 점이다.

## 0-2) 당일 운영 판정 메모 (2026-04-20)

- 판정: `코드 수정 보류`, `관찰축 유지`가 현재 최적.
- 이유: 개별 종목 손익 이슈는 `scale-in` 단일 원인으로 환원하지 않고, 전체 운영 관찰축에서 원인 귀속을 분리해야 한다.
- 유지 관찰축:
  - `latency_block -> ALLOW_FALLBACK` 전환 구간
  - `blocked_liquidity` 반복 구간
  - `dynamic_strength_canary` 완화 진입 구간
  - `post_sell_feedback`의 `MISSED_UPSIDE` vs `GOOD_EXIT` 분리
- 실행 원칙:
  - 당일/익일은 문서와 리포트 관찰만 수행
  - 실주문 로직 변경은 `N_min/Δ_min/rollback trigger` 충족 후 단일 축 canary로만 진행
  - 개별 종목 판정은 `plan/execution-delta/stage2 checklist`에서 관리하고, 본 문서에는 정책/수량 로직만 유지

---

## 1) 두 의견 비교 매트릭스

| 항목 | 1차 검토 (수량 전용) | 2차 검토 (통합 보고서) | 최종안 채택 근거 |
|---|---|---|---|
| 스케일인 수량 구조 진단 | "기존 포지션 × 비율" 공식 자체가 스켈핑과 부정합 | `int()` 버림으로 1주 케이스에서 0 발생 | **동일 결론**. 두 진단 모두 유지 |
| 수량 해법의 정밀도 | 예산 기반 주 + 포지션 비율 보조, 비율 수치 제시 | `max(1, int(...))` 또는 `math.ceil` | **1차 방식 채택** (2차는 증상 치료). 단 1주 플로어는 1차의 조건부 허용보다 2차 제안을 더 강하게 반영 |
| PYRAMID vs REVERSAL_ADD 차등 | 노셔널 비율 차등(0.08 vs 0.05) | 언급 없음 | **1차 채택**. 리스크 성격이 다르므로 차등 필수 |
| 고가주 레짐 대응 | 동적 `MAX_PYRAMID_COUNT` 제한 등 제시 | 언급 없음 | **1차 채택**. 계좌 규모 대비 고가주는 별도 정책 필요 |
| Latency 블록 | 미다룸 | 34/34 차단, 14건은 내부 처리 지연으로 진단 | **2차 채택**. 수량 공식보다 EV 누수 규모가 클 가능성 |
| AI WAIT 65 코호트 | 미다룸 | AI 예측력은 살아있으나 다운스트림에서 차단 | **2차 채택**. AI 신호 품질 재튜닝이 아닌 실행 문제로 프레이밍 |
| HOLDING 프롬프트 분리 | 미다룸 | Context Blindness 진단, 별도 프롬프트 제안 | **2차 채택**. 엑싯 판단의 근본적 개선 여지 |
| Raw 배열 경량화 | 미다룸 | 사전연산 지표로 대체하여 지연 최소화 | **2차 채택**. Latency 개선과 시너지 |
| 신호단 프리체크 | 제안(로그 노이즈/통계 왜곡 방지) | 미다룸 | **1차 채택**. 2차의 단일축 카나리아 원칙과도 호환 |
| 검증 로드맵 | 미다룸 | 04-20~04-24 주간 조정안 제시 | **2차 채택**, 단 수량 로직 패치 축을 추가 |

---

## 2) 통합 진단: 세 개의 EV 누수점

이수스페셜티케미컬 사례는 단일 버그가 아니라 **세 지점의 누수가 동시에 일어난 결과**로 재해석해야 한다.

**지점 A — EV 생성 단계 (AI/프롬프트)**
- `WATCHING`과 `HOLDING`이 동일 프롬프트를 공유 → 엑싯 상황에서 AI가 현재 P&L 문맥을 반영하지 못함.
- Raw 분봉/틱 배열이 그대로 주입 → LLM 응답 지연 → 파이프라인 전체 지연 누적.
- AI 점수 65점 `WAIT` 군집에 상승 종목이 다수 → AI 엣지는 있으나 보수적 임계값이 누수 유발.

**지점 B — 실행 파이프라인 (Latency/Gates)**
- `budget_pass` 통과 후 주문 직전 `latency_block` 34/34.
- 그 중 14건은 시세가 신선(`quote_stale=False`)함에도 차단 → 내부 처리 지연이 주원인.
- 이는 수량 이슈와 독립적으로 EV를 증발시키는 구조적 문제.

**지점 C — 수량 확정 단계 (현재 집중 검토 대상)**
- 공식 `int(buy_qty × ratio)`가 소규모 포지션에서 구조적으로 0을 생산.
- 스켈핑은 초기 포지션이 작은 것이 정상이므로 공식 전제 자체가 부정합.
- 캡(`MAX_POSITION_PCT`)은 정상 작동했으나 템플릿이 0을 내보내 캡 이전에 차단.

**세 지점이 직렬로 연결되어 있다는 것이 핵심이다.** A를 고치면 신호 품질이 올라가지만 B에서 다시 버려지고, B를 고쳐도 C에서 0주로 막힌다. 역순으로 C만 고치면 신호가 올 때라도 B의 지연 블록에서 잘린다. 우선순위는 아래 5절에서 정리한다.

---

## 3) [최종] 스케일인 수량 공식

### 3.1 확정 공식

```text
입력: buy_qty, curr_price, deposit, strategy, add_type, add_reason

# --- 상수 ---
MAX_POSITION_PCT        = 0.20
REMAINING_BUFFER        = 0.95

# 전략/유형별 '1차 기준' - deposit 대비 추가투입 노셔널 비율
ADD_NOTIONAL_RATIO = {
    ("SCALPING", "PYRAMID")      : 0.08,
    ("SCALPING", "REVERSAL_ADD") : 0.05,
    ("SWING",    "PYRAMID")      : 0.06,
    ("SWING",    "AVG_DOWN")     : 0.08,
}

# 전략/유형별 '2차 기준' - 보유수량 비율 (기존 로직 유지)
POSITION_RATIO = {
    ("SCALPING", "PYRAMID")      : 0.50,
    ("SCALPING", "REVERSAL_ADD") : 0.33,  # REVERSAL_ADD_SIZE_RATIO
    ("SWING",    "PYRAMID")      : 0.30,
    ("SWING",    "AVG_DOWN")     : 0.50,
}

# --- 계산 ---
max_budget       = deposit * MAX_POSITION_PCT
current_value    = buy_qty * curr_price
remaining_budget = max(max_budget - current_value, 0)

# 1차: 리스크 예산 기반
target_notional  = deposit * ADD_NOTIONAL_RATIO[(strategy, add_type)]
qty_by_budget    = int(target_notional // curr_price)

# 2차: 포지션 비율 기반 (누적 포지션이 커질수록 자연 스케일)
qty_by_position  = int(buy_qty * POSITION_RATIO[(strategy, add_type)])

# 템플릿: 둘 중 큰 쪽 (초기엔 예산, 성장 후엔 포지션이 바인딩)
template_qty     = max(qty_by_budget, qty_by_position)

# 플로어: PYRAMID/REVERSAL_ADD 한정, 예산이 1주라도 받쳐주면 최소 1주
if (template_qty < 1
        and add_type in ("PYRAMID", "REVERSAL_ADD")
        and remaining_budget >= curr_price):
    template_qty = 1

# 캡: MAX_POSITION_PCT 기반 절대 한계
cap_qty = int((remaining_budget * REMAINING_BUFFER) // curr_price)

# 최종
qty = min(template_qty, cap_qty)
return qty if qty >= 1 else 0
```

### 3.2 설계 원칙 정리

- **Primary (예산)**: 종목 가격·초기 진입 규모와 무관하게 일관된 리스크 노출을 보장.
- **Secondary (포지션)**: 누적 매수 후에는 이쪽이 자연스럽게 바인딩되어 기존 피라미딩 감각 유지.
- **Floor (1주)**: 스켈핑 고가주 레짐에서 신호가 버려지지 않도록 최소 실행 단위 보장. 단, REVERSAL_ADD와 PYRAMID에만 적용 (AVG_DOWN은 원칙상 로스컷 직전 행위이므로 플로어 미적용).
- **Cap (MAX_POSITION_PCT)**: 항상 최상위 제약. 리스크 캡은 절대 훼손하지 않음.

### 3.3 이수스페셜티케미컬 재계산

```text
deposit = 8,678,470  curr_price = 113,400  buy_qty = 1
strategy = SCALPING  add_type = PYRAMID

target_notional  = 8,678,470 × 0.08   = 694,277
qty_by_budget    = 694,277 // 113,400 = 6
qty_by_position  = int(1 × 0.50)      = 0
template_qty     = max(6, 0)          = 6
remaining_budget = 1,735,694 − 113,400 = 1,622,294
cap_qty          = (1,622,294 × 0.95) // 113,400 = 13
qty              = min(6, 13)         = 6   ← 정상 체결
```

기존 로직의 `0주` → 신규 로직의 `6주`. 리스크 캡(13주)은 그대로 존중되므로 과매수 위험도 없다.

### 3.4 Fallback: 미니멀 패치 (전환 부담 시)

전면 교체가 부담이면 2차 검토가 제안한 미니멀 패치만 우선 적용 가능.

```python
template_qty = int(buy_qty * ratio)
if (template_qty < 1
        and add_type in ("PYRAMID", "REVERSAL_ADD")
        and remaining_budget >= curr_price):
    template_qty = 1
qty = min(template_qty, cap_qty)
```

단 이는 증상 치료이며, 고가주에서 초기 포지션이 2~3주인 경우에도 `int(2×0.5)=1` 같은 과소 수량이 계속 발생한다. **중장기적으로는 3.1 전면 공식으로 이전 권장.**

---

## 4) 연관 이슈 통합 (2차 검토 반영)

### 4.1 Latency Block 해소

**현황 요약**: `budget_pass` 후 주문 직전에서 34/34 차단, 그중 14건은 시세가 신선한 상태 → 내부 처리 지연이 주범. 반사실 EV 누수 추정 +24,960원.

**권고**:
- P0: 주문 직전 구간의 처리 지연 프로파일링 착수. 버그픽스-온리 카나리아로 분리.
- 수량 로직 패치와 **동일 데이로 병행하되 카나리아 축은 분리** (원인 귀속 명확화).
- 처리 지연 원인 후보: 동기식 로그 플러시, AI 응답 직렬화, 계좌 조회 중복 호출 — 프로파일링 결과에 따라 조치.

### 4.2 AI `WAIT 65` 코호트 재처리

**현황 요약**: 점수 65점 군집이 WAIT로 라벨링되었으나 상당수가 `MISSED_WINNER`로 귀결. 방향성 엣지는 살아있으나 후단에서 차단.

**권고**:
- 임계값 자체를 내리는 것은 **보류**. Latency 문제가 풀리지 않은 상태에서 진입 빈도만 늘리면 부분체결/슬리피지 악화 가능.
- 대신 `WAIT 65` 표본의 **차단 원인별 분포**를 별도 대시보드화. Latency 해소 후 잔여 `blocked_strength_momentum` 비중에 따라 재튜닝 여부 결정.

### 4.3 HOLDING 전용 프롬프트 분리 (P0 핫픽스)

**구조**:
- `WATCHING` 프롬프트: 방향성·모멘텀·진입 타이밍 중심.
- `HOLDING` 프롬프트: 수익 보존·리스크 관리·엑싯 신호 중심.

**주입 데이터 구성 (`HOLDING`)**:
- 포지션 문맥: `current_profit_rate`, `peak_profit_rate`, `held_seconds`, `drawdown_from_peak`
- 시장 수급 (사전연산): `tick_acceleration_ratio`, `buy_pressure_10t`, `prog_delta_qty_1m`
- Raw 분봉/틱 배열: **제거 또는 최근 N틱만 잔존** (N은 측정 후 결정, 초기값 20틱)

**기대 효과**: 엑싯 판단 정밀도 향상 + 토큰 절감 + LLM 응답 지연 단축 → 4.1 Latency 문제와 간접 시너지.

### 4.4 신호단 프리체크 추가 (1차 검토 반영)

**변경**: 신호 생성 시점에 `remaining_budget < curr_price`이면 신호 자체를 생성하지 않음. 수량 계산 단계까지 가지 않도록 조기 차단.

**효과**:
- `ADD_BLOCKED zero_qty` 로그 노이즈 제거.
- "신호 생성 횟수 vs 실행 횟수" 지표의 정합성 회복 (현재는 생성 횟수가 인플레되어 AI 품질 판단을 왜곡).
- AI 학습/평가 피드백 루프가 실제 실행 가능한 케이스 기준으로 정상화.

---

## 5) 우선순위 및 실행 순서

| Priority | 항목 | 근거 | 리스크 |
|---|---|---|---|
| **P0** | Latency 버그픽스-온리 카나리아 | EV 누수 규모 최대 추정 (+24,960원) | 낮음 (기능 추가 없음) |
| **P0** | `HOLDING` 프롬프트 분리 + Raw 배열 경량화 | 엑싯 품질 개선 + 지연 완화 시너지 | 중간 (프롬프트 회귀 필요) |
| **P0** | 스케일인 수량 공식 교체 (§3.1) | 신호→실행 전환율 구조 개선 | 낮음 (캡은 유지) |
| **P1** | 신호단 프리체크 (§4.4) | 통계 정합성 회복 | 낮음 |
| **P1** | `WAIT 65` 차단 원인 분포 대시보드 | 재튜닝 여부 근거 수집 | 없음 (관측만) |
| **P2** | 고가주 레짐 동적 정책 (MAX_PYRAMID_COUNT 축소 등) | 특수 상황 대응 | 낮음, 단 측정 필요 |
| **P2** | `SCALPING_MAX_BUY_BUDGET_KRW`의 스케일인 반영 여부 결정 | 계좌 성장 시 종목당 절대 캡 부재 | 정책 결정 필요 |

**P0 3건은 동일 주간에 병렬 준비는 가능하지만, 실반영은 축별로 분리해야 한다.** 현재 운영 기준에서는 "수량 패치 축", "Latency 버그픽스 축", "HOLDING 프롬프트 축"을 같은 서버에서 같은 관찰창에 동시에 실주문 변경으로 열면 안 된다.

---

## 6) 수정된 주간 반영 로드맵 (2026-04-20 ~ 04-24)

원안 일정보다 한 단계 보수적으로 조정한다. 목적은 **현재 `split-entry/HOLDING` 관찰축을 흔들지 않으면서 scale-in 축을 메인/원격 양쪽에 준비하는 것**이다.

| 일자 | 카나리아 축 | 목표 |
|---|---|---|
| **04-20 (월)** | 문서 확정 only | scale-in 수량 공식/충돌사항/필요 flag 정의. 실주문 로직 변경 금지 |
| **04-21 (화)** | 기존 `split-entry/HOLDING` 관찰 유지 | scale-in 관련 신규 canary 미오픈. 현재 축 해석 우선 |
| **04-22 (수)** | `AI 엔진 A/B preflight` 문맥에 scale-in 축 추가 | 원격 반영 범위(`shadow-only`, `flag`, `rollback`)를 문서화 |
| **04-23 (목)** | **remote code-load + shadow-only** | 원격에 코드 적재 가능. 단 `qty_v2`는 shadow 계산/로그만 허용, 실주문 변경 금지 |
| **04-24 (금)** | 주간 통합 판정 | `remote shadow` 결과가 충분하면 다음주 `remote canary` 승인 여부만 결정. `main`은 코드 적재하더라도 `flag OFF` 유지 |

**현재 플랜 기준의 반영 순서**:
1. `04-23 POSTCLOSE`: `remote`에 `scale-in qty v2` 코드 적재 + `shadow-only`
2. `04-24 POSTCLOSE`: `remote canary` go/no-go 판정
3. 다음주: `remote canary`
4. 그 이후: `main` 코드 적재(`flag OFF`) -> `main canary`

---

## 6-1) 메인/원격 반영 정책

### 원격 (`develop`, 실험서버)

- `04-23 POSTCLOSE`: 코드 적재 가능
- 첫 단계는 반드시 `shadow-only`
- 실주문 변경은 `remote canary` 승인 후에만 허용

### 메인 (`main`, 본서버)

- 현재 주간에는 **실주문 변경 금지**
- 허용 가능한 최대치는 `code-load + feature flag OFF`
- `remote shadow/canary` 결과가 정량 기준을 넘기기 전에는 `main` 실반영 금지

이 순서를 지키면 메인/원격 모두에 "반영 준비"는 하되, 관찰축 자체는 유지할 수 있다.

---

## 6-2) 구현 전 필요한 토글/관찰축

현행 코드에는 아래와 같은 scale-in 전용 토글이 없다. 메인/원격 동시 준비를 안전하게 하려면 최소 이 수준의 토글이 필요하다.

- `KORSTOCKSCAN_SCALE_IN_QTY_V2_ENABLED`
- `KORSTOCKSCAN_SCALE_IN_QTY_SHADOW_ONLY`
- `KORSTOCKSCAN_SCALE_IN_MIN_LOT_FLOOR_ENABLED`
- `KORSTOCKSCAN_SCALE_IN_SIGNAL_PREFLIGHT_ENABLED`

추가로 관찰 로그도 분리돼야 한다.

- `qty_v1`
- `qty_v2_shadow`
- `template_qty_by_budget`
- `template_qty_by_position`
- `cap_qty`
- `floor_applied`
- `would_execute_v2`

토글과 관찰 로그가 없으면, 메인과 원격에 동시에 코드를 싣더라도 **어느 변경이 결과를 만들었는지 분해가 불가능**하다.

---

## 6-3) 현재 운영로직과 상충해 수정이 필요한 항목

아래는 "문서상 제안은 맞지만, 현행 코드/운영과 직접 충돌하므로 수정 또는 분리 과제가 필요한 지점"이다.

1. `04-20 병렬 3축 착수`
현재 체크리스트/플랜과 충돌. 삭제 또는 "문서 확정 only"로 수정 필요.

2. `main/remote 동주 실반영`
현재 운영 원칙과 충돌. `main`은 `flag OFF` 적재까지만 허용하도록 수정 필요.

3. `SCALPING_MAX_BUY_BUDGET_KRW` scale-in 확장
현행 코드는 신규 진입 전용. 이번 축에 섞으면 관찰축이 늘어나므로 별도 정책 항목으로 분리 필요.

4. `min 1 lot` 즉시 활성화
증상 치료로는 유효하지만, 현재 리스크정책과 직접 연결되므로 `shadow-only` 후 승인하도록 수정 필요.

5. `HOLDING P0`와 scale-in 동주 병행 실주문 변경
현재 `HOLDING` 관찰축과 충돌. 같은 주에는 문서/설계 병행만 하고 실반영 축은 분리 필요.

---

## 6-4) 승격 판정 기준 제안 (수량 패치 축)

- `ADD_BLOCKED zero_qty` 발생 건수: 기존 대비 `100% 감소`
- `remote shadow qty_v2` 기준 `would_execute_v2 > 0` 표본 확보
- `MAX_POSITION_PCT` 캡 위반 `0건`
- `full fill / partial fill` 분리 기준으로 체결 품질 악화 없음
- 추가매수 실행건 기준 평균 실현수익률 또는 `capture_efficiency` 동등 이상

---

## 7) 기각 사안 재확인

두 검토 모두 또는 2차 검토에서 기각한 항목을 명시적으로 유지.

- **신규 텔레그램 알림 추가**: 보류. 현 단계는 시그널·실행 계측이 우선.
- **인프라 즉시 리팩터링**: 보류. 카나리아 원칙 위배, 원인 귀속 불가.
- **OpenAI 엔진 즉시 교체**: 보류. AI 엣지가 살아있다는 증거(WAIT 65 코호트) 하에서 엔진 교체는 독립변수 오염.

---

## 8) 트레이더 최종 결정 체크리스트

운영 적용 전 확인 요청 항목.

- [ ] **ADD_NOTIONAL_RATIO 초기값** (PYRAMID 0.08 / REVERSAL_ADD 0.05) 수용 여부 — 백테스트 결과로 재조정 가능
- [ ] **1주 플로어**를 PYRAMID/REVERSAL_ADD에만 적용하는 것에 동의 (AVG_DOWN 제외)
- [ ] **AVG_DOWN은 현재 `SCALPING_ENABLE_AVG_DOWN=False`로 비활성화**되어 있음을 재확인. 스켈핑 철학상 유지 권고
- [ ] **`SCALPING_MAX_BUY_BUDGET_KRW`의 스케일인 반영 여부** — 현재는 신규 진입에만 적용. 계좌 성장 시 정책 필요
- [ ] **신호단 프리체크 도입** 시 기존 로그·통계 기준점 리셋 여부 (통계 연속성 vs 정합성 트레이드오프)
- [ ] **주간 승격 기준**의 정량 임계값 — 위 §6은 제안치

---

## 9) 요약 그림 (로직 플로우)

```text
[Signal Generation]                    (§4.4 프리체크 추가)
        │
        ├── remaining_budget < curr_price ?  ──→ 신호 미생성
        │
        ▼
[AI Evaluation]                        (§4.3 HOLDING 전용 프롬프트 분기)
        │
        ▼
[Gate Checks - budget_pass etc.]
        │
        ▼
[Latency Gate]                         (§4.1 내부 처리 지연 해소 대상)
        │
        ▼
[calc_scale_in_qty]                    (§3.1 공식 v2 적용)
        │
        │   qty_by_budget  = int(deposit × ratio / price)   ← Primary
        │   qty_by_position = int(buy_qty × ratio)          ← Secondary
        │   template_qty = max(Primary, Secondary)
        │   if template_qty < 1 and PYRAMID/REVERSAL_ADD and budget>=price:
        │       template_qty = 1                             ← Floor
        │   qty = min(template_qty, cap_qty)                 ← Cap
        │
        ▼
[Order Submission]
```

---

**문서 버전**: v1.0 (2026-04-20 통합 최종안)  
**다음 검토 예정**: 2026-04-24 주간 승격 판정 후 v1.1
