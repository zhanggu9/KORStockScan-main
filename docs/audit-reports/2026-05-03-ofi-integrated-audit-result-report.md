# Order Flow Imbalance 적용현황 종합 감리결과보고서

**수신:** 시스템 운영담당  
**발신:** 수석 감리인  
**작성일:** 2026-05-03 KST  
**대상:** `Order Flow Imbalance(OFI) / Queue Imbalance(QI) orderbook micro`의 트레이딩시스템 적용현황  

**검토자료:**  
1. `2026-05-03-order-flow-imbalance-application-audit-report.md`  
2. `2026-05-03-order-flow-imbalance-application-audit-review.md`  

---

## 1. 종합 감리의견

본 감리의 종합 결론은 다음과 같다.

> **OFI는 현재 시스템에 “구현되어 있고, 실시간 데이터 경로와 AI 진입가 판단 컨텍스트까지 연결되어 있다.”  
> 그러나 이는 독립적인 주문 차단 규칙이나 standalone 전략축이 아니라, `dynamic_entry_ai_price_canary_p2` 내부의 보조 미시구조 피처로 적용된 상태다.  
> 따라서 현 단계의 적용 상태는 “plumbing 적용은 적정, operational 효과 검증은 미흡”으로 판정한다.**

즉, 코드와 데이터 경로 관점에서는 OFI/QI가 실제 적용되어 있으나, 운영상으로 “이 기능이 의사결정 품질을 개선하고 있다”는 증거는 아직 충분하지 않다. 특히 임계값 비대칭, 프롬프트 의존 정책, 실거래 cohort 검증 부재는 운영담당이 즉시 관리해야 할 주요 리스크다.

---

## 2. 최종 판정

| 구분 | 감리 판정 |
|---|---|
| OFI 기능 존재 여부 | **적용 확인** |
| 실시간 호가/체결 입력 반영 | **적용 확인** |
| OFI/QI 계산 및 상태화 | **적용 확인** |
| AI 진입가 판단 컨텍스트 주입 | **적용 확인** |
| 운영 로그 추적 가능성 | **대체로 적정** |
| 테스트 증적 | **기본 증적 존재, 경계·전이 테스트 부족** |
| 독립 hard gate 여부 | **미적용** |
| holding/exit 적용 여부 | **미적용** |
| 도입 효과 검증 | **미흡** |
| 운영 승인 수준 | **조건부 적정** |

**감리 등급:** 조건부 적정  
**운영 조치 등급:** P0 개선사항 해소 전까지 확대 적용 금지  
**권고 운영 상태:** canary 또는 제한 운영 유지. 독립 hard gate 승격, holding/exit 확장, threshold 변경은 별도 승인 전 금지.

---

## 3. 확인된 적용현황

제출된 적용현황 보고서에 따르면 현재 코드베이스에서 OFI는 단순한 문서상 계획이 아니라 실제 계산·전달·로그 구조까지 반영되어 있다.

실시간 websocket 체결·호가 이벤트가 `ORDERBOOK_STABILITY_OBSERVER`로 입력되고, 해당 observer에서 다음 값이 산출되는 구조다.

```text
ofi_instant
ofi_ewma
ofi_norm
ofi_z
qi
qi_ewma
micro_state
```

현재 OFI/QI micro state는 대략 다음과 같이 분류된다.

| 상태 | 조건 |
|---|---|
| `bullish` | `ofi_z >= 1.2` and `qi_ewma >= 0.55` |
| `bearish` | `ofi_z <= -1.0` and `qi_ewma < 0.48` |
| `neutral` | 위 조건 미충족 |
| `insufficient` | 표본 부족 또는 수량 부재 |

계산된 OFI/QI 값은 entry latency snapshot에 포함되고, 이후 `price_context.orderbook_micro` 형태로 `dynamic_entry_ai_price_canary_p2`의 AI 판단 컨텍스트에 전달된다.

다만 이 적용은 “OFI가 주문을 직접 차단한다”는 의미가 아니다. 현재 구조에서 OFI/QI는 submitted 직전 AI 진입가 판단에 사용되는 보조 입력이며, `bearish + ready` 상태일 때 AI가 `SKIP` 판단의 근거로 사용할 수 있는 수준이다. `neutral` 또는 `insufficient` 상태에서는 OFI/QI 단독으로 주문을 차단하지 않도록 프롬프트상 제한되어 있다.

---

## 4. 적용범위와 비적용범위

### 4.1 적용된 범위

| 영역 | 적용 상태 | 감리 의견 |
|---|---:|---|
| 실시간 체결/호가 입력 | 적용 | OFI 계산의 입력 경로 존재 |
| OFI/QI 계산 | 적용 | 정규화·z-score·EWMA 포함 |
| micro state 분류 | 적용 | bullish/bearish/neutral/insufficient |
| entry latency snapshot 포함 | 적용 | downstream 전달 가능 |
| P2 entry AI context 주입 | 적용 | `price_context.orderbook_micro`로 전달 |
| 로그 provenance | 적용 | 사후 감리 가능 |
| 테스트 | 일부 적용 | 기본 계산·context 주입 테스트는 있으나 부족 |

### 4.2 적용되지 않은 범위

| 영역 | 미적용 상태 | 감리 의견 |
|---|---:|---|
| OFI standalone hard gate | 미적용 | 현재 단계에서는 적절. 단, 필요 시 별도 설계 필요 |
| holding/exit live rule | 미적용 | 의도적 제외인지 일정상 보류인지 문서화 필요 |
| watching 단계 BUY/WAIT/DROP 판단 | 불명확 | submitted 직전만으로는 적용 시점이 늦을 수 있음 |
| OFI 단독 손익 검증 | 미적용 | keep/OFF 판정 전 필수 보완 |
| 종목군별 threshold calibration | 미적용 | 소형주/대형주 분포 차이 반영 필요 |

---

## 5. 주요 감리 지적사항

### 5.1 임계값 비대칭에 따른 SKIP 편향 가능성

현재 micro state 임계값은 bullish와 bearish가 대칭이 아니다.

| 축 | bullish 조건 | bearish 조건 | 감리 판단 |
|---|---:|---:|---|
| `ofi_z` | `>= +1.2` | `<= -1.0` | bearish가 더 쉽게 발동 |
| `qi_ewma` | `>= 0.55` | `< 0.48` | bearish가 더 쉽게 발동 |

이 구조는 매수 우위 상태보다 매도 우위 상태를 더 쉽게 감지하도록 설계되어 있다. 이것이 의도된 보수성이라면 문제는 아니지만, 현재 제출자료에는 그 의도가 명확히 문서화되어 있지 않다.

**운영 리스크:**  
bearish 판정이 상대적으로 쉽게 발생하면 AI가 `SKIP` 판단을 더 자주 선택할 수 있으며, 이는 불필요한 진입 회피와 missed upside 증가로 이어질 수 있다.

**운영담당 조치:**  
다음 둘 중 하나를 선택해 명문화해야 한다.

1. **의도된 보수성으로 승인**
   - 한국시장 단기 매도 압박 또는 분배 신호를 더 엄격히 회피하기 위한 설계라고 명시
   - 로그 기반으로 bearish 발동률과 사후 가격 움직임을 검증

2. **대칭 임계값으로 보정**
   - 예: `bearish ofi_z <= -1.2`, `qi_ewma <= 0.45` 등
   - 단, 실거래 로그 검증 없이 즉시 live 변경은 금지

---

### 5.2 bullish state의 운영 의미 불명확

현재 `bearish`는 AI가 `SKIP` 근거로 사용할 수 있으나, `bullish`가 어떤 운영상 이점을 갖는지는 명확하지 않다.

**문제점:**  
OFI/QI가 양의 방향에서는 진입 confidence를 높이거나 주문가 개선, cooldown 단축 등에 사용되지 않고, 음의 방향에서만 SKIP 근거로 활용된다면 기능 전체가 “진입 회피 중심”으로 편향된다.

**운영담당 조치:**  

- `bullish`를 진입 confidence 보강 또는 주문가 개선 판단에 사용
- 아니면 `bullish`를 제거하고 `bearish / non_bearish` 이진 구조로 단순화
- 현 상태를 유지할 경우 “bearish-only 방어 피처”라고 명시

---

### 5.3 OFI 정책이 AI 프롬프트에만 의존

현재 `bearish + ready → SKIP 근거 가능`이라는 정책은 프롬프트 수준에서 규정되어 있다. 그러나 프롬프트는 자연어 정책이며, 모델 교체·프롬프트 변경·provider 변경 시 정책 drift가 발생할 수 있다.

**운영 리스크:**  
AI가 OFI 정책을 무시하거나, `neutral`/`insufficient` 상태에서도 OFI를 근거로 SKIP하는 경우를 시스템적으로 차단하기 어렵다.

**운영담당 조치:**  
프롬프트 외부에 후처리 검증 로직을 둬야 한다.

권고 정책:

```text
AI가 SKIP을 반환한 경우:
1. orderbook_micro.ready 여부 확인
2. micro_state가 bearish인지 확인
3. neutral/insufficient 상태에서 OFI 단독 SKIP이 발생하지 않았는지 확인
4. 위반 시 warning 또는 fallback reason 부여
```

---

### 5.4 도입 효과 측정 부재

가장 중요한 운영상 결손은 OFI가 실제로 성과를 개선했는지에 대한 사전·사후 측정이 부족하다는 점이다. 적용현황 보고서는 기능의 존재와 입력 경로, 로그 증적을 입증하고 있으나, 기능이 의사결정 품질을 개선했는지는 입증하지 못한다.

**운영담당 필수 산출물:**

| 비교군 | 필수 KPI |
|---|---|
| OFI ON vs OFF | submitted rate, fill rate, partial fill, soft stop |
| bearish SKIP vs bearish non-SKIP | 1분/5분/30분 후 mid price 변화 |
| bullish 발생 cohort | 진입률, 체결률, 사후 수익률 |
| insufficient/neutral cohort | 불필요한 SKIP 발생 여부 |
| snapshot age cohort | AI 응답 지연 중 micro state stale 여부 |

**감리 판단:**  
이 측정이 없으면 keep/OFF 판정은 승인할 수 없다. 기능이 “켜져 있다”는 것과 “운영 가치가 있다”는 것은 별개의 문제다.

---

### 5.5 snapshot staleness 관리 부재

OFI는 초단기 미시구조 신호이므로 snapshot 시점과 AI 응답 시점 사이의 지연이 중요하다. 현재 보고서상으로는 `price_context` 생성 시점의 micro state가 AI 응답 시점에도 유효한지 재확인하는 구조가 명확하지 않다.

**운영 리스크:**  
AI 호출 latency 동안 `bearish → neutral` 또는 `neutral → bearish`로 바뀔 수 있다. stale snapshot으로 인해 잘못된 SKIP 또는 잘못된 진입이 발생할 수 있다.

**운영담당 조치:**  
`orderbook_micro`에 `captured_at_ms`를 추가하고, AI 응답 후 다음 조건을 점검해야 한다.

```text
now_ms - orderbook_micro.captured_at_ms > MICRO_STALE_THRESHOLD_MS
```

초과 시 해당 micro signal을 무시하거나 별도 warning을 남겨야 한다.

---

### 5.6 Observer 장애와 insufficient 상태의 구분 부재

현재 `insufficient`는 정상적인 표본 부족일 수 있고, websocket/observer 장애에 따른 데이터 미수신일 수도 있다. 두 상태를 동일하게 취급하면 운영 장애가 조용히 neutral 또는 insufficient로 흡수될 위험이 있다.

**운영담당 조치:**  
다음 상태를 분리해야 한다.

| 상태 | 의미 | 처리 |
|---|---|---|
| `None` | observer 장애 또는 데이터 경로 이상 | 시스템 health issue |
| `insufficient` | 정상 수신 중이나 표본 부족 | 판단 보류 또는 OFI 무시 |
| `neutral` | 충분한 표본에서 중립 | OFI 단독 SKIP 금지 |
| `bearish` | 유효한 매도 우위 | SKIP 근거 가능 |
| `bullish` | 유효한 매수 우위 | 정책 결정 필요 |

---

## 6. 운영담당 지시사항

### 6.1 P0 — 즉시 조치

다음 항목은 keep/OFF 판정 또는 확대 적용 전에 반드시 완료해야 한다.

#### P0-1. OFI 효과 cohort 비교 산출

운영 로그 기준으로 다음 표본을 산출한다.

```text
1. orderbook_micro_state = bearish AND ai_action = SKIP
2. orderbook_micro_state = bearish AND ai_action != SKIP
3. orderbook_micro_state = bullish
4. orderbook_micro_state = neutral
5. orderbook_micro_ready = false 또는 insufficient
```

각 cohort에 대해 다음 지표를 산출한다.

```text
- 1분 후 mid price 변화
- 5분 후 mid price 변화
- 30분 후 mid price 변화
- fill rate
- partial fill rate
- unfilled rate
- soft stop 발생률
- missed upside 추정치
```

#### P0-2. 임계값 비대칭 의도 명문화

운영담당은 전략담당 및 개발담당과 함께 다음 중 하나를 결정해야 한다.

| 선택지 | 조치 |
|---|---|
| 보수적 bearish bias 유지 | ADR 또는 운영정책서에 의도와 근거 명시 |
| 대칭화 | 변경 전 shadow test 후 canary 반영 |
| 판단 보류 | 현행 유지하되 확대 적용 금지 |

#### P0-3. provenance와 의사결정 연결 검증

로그에 `orderbook_micro_*` 필드가 남는 것만으로 충분하지 않다. 실제 AI 결정과 연결되어야 한다.

필수 확인 항목:

```text
- bearish + ready 발생 건수
- 그중 SKIP 발생 건수
- SKIP reason에 OFI/QI/orderbook/micro 관련 근거가 포함된 비율
- neutral/insufficient 상태에서 OFI 단독 SKIP이 발생한 사례 여부
```

#### P0-4. keep/OFF decision tree 수립

운영담당은 다음 의사결정 트리를 사전에 확정해야 한다.

| 결과 | 후속 조치 |
|---|---|
| KEEP | 임계값 의도 명문화, staleness/health check 보강 |
| OFF | feature flag OFF, 코드 제거 금지, 재canary 조건 정의 |
| PARTIAL KEEP | 종목군·시간대별 threshold calibration 검토 |
| 판단 불가 | canary 유지 또는 shadow-only 전환, 확대 금지 |

---

### 6.2 P1 — 다음 스프린트 조치

#### P1-1. 프롬프트 외부 후처리 검증 추가

AI 응답 후 `SKIP` 사유가 OFI 정책을 위반하지 않는지 검증한다.

권고 검증 항목:

```text
- SKIP인데 orderbook_micro.ready=false인 경우 warning
- SKIP인데 micro_state=neutral/insufficient인 경우 warning
- bearish가 아닌 상태에서 OFI만 근거로 SKIP한 경우 policy violation
```

#### P1-2. snapshot staleness timestamp 추가

`orderbook_micro`에 다음 필드를 추가한다.

```text
captured_at_ms
snapshot_age_ms
stale_reason
```

#### P1-3. Observer health check 추가

다음 필드를 운영 로그에 포함한다.

```text
observer_healthy
observer_last_quote_age_ms
observer_last_trade_age_ms
observer_missing_reason
```

#### P1-4. 테스트 커버리지 보강

현재 테스트는 계산과 context 주입 여부 중심이다. 다음 테스트를 추가해야 한다.

```text
test_orderbook_micro_state_thresholds_boundary
test_orderbook_micro_state_transitions
test_price_context_micro_keyset_parity_across_engines
test_insufficient_state_does_not_skip_alone
test_bearish_threshold_asymmetry_intentional
test_micro_snapshot_staleness_policy
```

#### P1-5. ready와 micro_state 결합표 명문화

다음 조합표를 코드 주석, 운영문서 또는 ADR에 명시한다.

| ready | micro_state | 정책 |
|---|---|---|
| true | bearish | SKIP 근거 가능 |
| true | bullish | 정책 결정 필요 |
| true | neutral | OFI 단독 SKIP 금지 |
| true | insufficient | 비정상 조합 여부 확인 |
| false | any | OFI 판단 금지 또는 insufficient 강제 |

---

### 6.3 P2 — KEEP 결정 후 검토

P0/P1 조치가 완료되고 OFI 기능의 운영 가치가 확인된 이후 다음 확장을 검토한다.

| 항목 | 검토 방향 |
|---|---|
| 종목군별 calibration | 대형주/소형주/테마주별 발동률 비교 |
| watching 단계 OFI 주입 | BUY/WAIT/DROP 판단 전 단계에 적용 가능성 검토 |
| holding/exit 적용 | 진입 후 분배·흡수 종료 감지에 활용 가능성 검토 |
| non-AI hard guard | 극단적 bearish만 차단하는 보수적 guard shadow 운영 |
| bullish 활용 | 진입 confidence, 주문가 개선, cooldown 조정에 반영 가능성 검토 |

---

## 7. 운영상 금지사항

P0 조치 완료 전까지 다음을 금지한다.

1. **OFI를 독립 전략축으로 홍보 또는 운영보고서에 기재 금지**
   - 현재는 보조 피처다.

2. **OFI 단독 hard gate 승격 금지**
   - 실거래 cohort 검증 없이 주문 차단 규칙으로 승격하면 missed upside 리스크가 커진다.

3. **holding/exit 경로 확장 금지**
   - entry P2 적용 효과가 먼저 입증되어야 한다.

4. **threshold 임의 변경 금지**
   - 임계값 비대칭은 운영 리스크이지만, 로그 검증 없는 즉시 변경도 별도 리스크다.

5. **3 엔진 parity를 운영 검증 완료로 표현 금지**
   - 현재 3 엔진은 입력 경로 측면의 plumbing parity일 뿐, 실제 운영 라우팅과 응답 정책 parity가 검증된 것은 아니다.

---

## 8. 운영담당 제출 산출물

운영담당은 다음 산출물을 제출해야 한다.

| 번호 | 산출물 | 기한/우선순위 |
|---|---|---|
| 1 | OFI cohort 성과 비교표 | P0 |
| 2 | bearish SKIP 표본 상세 로그 5~10건 | P0 |
| 3 | 임계값 비대칭 의도 확인서 또는 ADR | P0 |
| 4 | keep/OFF decision tree | P0 |
| 5 | post-validation 설계안 | P1 |
| 6 | staleness/health check 필드 설계안 | P1 |
| 7 | 테스트 보강 PR 또는 테스트 계획서 | P1 |
| 8 | holding/exit 미적용 사유 문서 | P1 |
| 9 | 종목군별 calibration 검토안 | P2 |

---

## 9. 운영 승인 조건

### 9.1 최소 유지 조건

```text
- bearish SKIP cohort의 사후 가격 하락 또는 위험 회피 효과가 관찰될 것
- neutral/insufficient 상태에서 OFI 단독 SKIP이 발생하지 않을 것
- observer 장애와 표본 부족이 로그상 구분될 것
- snapshot staleness가 측정 가능할 것
```

### 9.2 KEEP 승인 조건

```text
- OFI ON cohort가 OFF 또는 비사용 cohort 대비 fill quality 또는 손실 회피 측면에서 개선될 것
- missed upside가 허용 한도 이내일 것
- 임계값 비대칭의 의도가 명문화될 것
- SKIP decision provenance가 추적 가능할 것
```

### 9.3 OFF 또는 shadow-only 전환 조건

```text
- bearish SKIP 이후 가격 상승 사례가 유의미하게 많을 경우
- insufficient/neutral 상태에서 SKIP이 반복될 경우
- observer lag 또는 stale snapshot 비율이 높을 경우
- OFI ON cohort의 fill rate 또는 기대값이 악화될 경우
```

---

## 10. 수석 감리인 최종 의견

현재 OFI/QI orderbook micro는 기술적으로는 비교적 깨끗하게 시스템에 연결되어 있다. 실시간 호가/체결 입력, observer 계산, latency snapshot, AI price context 주입, 로그 provenance까지 이어지는 경로는 적용현황 보고서상 충분히 확인된다.

그러나 운영 감리 관점에서 핵심은 “기능이 존재하는가”가 아니라 “기능이 통제 가능한 방식으로 의사결정 품질을 개선하는가”이다. 이 기준에서 현재 상태는 아직 미완이다. 특히 `bearish` 쪽으로 더 쉽게 발동하는 임계값 비대칭, `bullish` state의 운영 의미 부재, 프롬프트 의존 정책, snapshot staleness, observer 장애 구분, cohort 효과 측정 부재는 즉시 보완되어야 한다.

따라서 본 수석 감리인은 다음과 같이 최종 지시한다.

> **OFI 적용은 “조건부 적정”으로 인정한다.  
> 단, 이는 `dynamic_entry_ai_price_canary_p2` 내부 보조 피처로서의 인정에 한정한다.  
> P0 조치 완료 전까지 독립 hard gate, holding/exit 확장, threshold live 변경, 운영 성과 개선 주장, 3 엔진 운영 parity 주장은 모두 금지한다.  
> 운영담당은 OFI cohort 효과 측정과 임계값 비대칭 의도 명문화 자료를 우선 제출해야 한다.**

---

## 11. 결재용 한 줄 요약

> **OFI는 시스템에 적용되어 있으나 현재는 “plumbing 완료, operational 검증 미완료” 상태다. 운영담당은 keep/OFF 판정 전 cohort 성과 검증, 임계값 비대칭 명문화, 프롬프트 외부 검증, staleness/observer health 관리 체계를 우선 보완해야 한다.**

---

## 부록 A. 운영 검증 명령 예시

```bash
# 임계값 비대칭 확인
grep -nE "ofi_z|qi_ewma|micro_state" src/trading/entry/orderbook_stability_observer.py

# 결합표 / 후처리 검증 부재 확인
grep -nE "orderbook_micro|micro_state" src/engine/sniper_state_handlers.py
grep -nE "post_validate|skip_validation" src/engine/sniper_state_handlers.py

# 3 엔진 plumbing parity 확인
grep -nE "price_context|orderbook_micro" \
    src/engine/ai_engine.py src/engine/ai_engine_openai.py src/engine/ai_engine_deepseek.py

# 프롬프트 정책 SSoT 검증
grep -nE "neutral|insufficient|bearish" src/engine/ai_engine.py | head

# 로그 provenance 확인
grep -nE "orderbook_micro_(state|ofi_z|qi|ready)" src/engine/sniper_state_handlers.py
```

---

## 부록 B. POSTCLOSE 운영 쿼리 예시

```text
# 1주일치 운영 로그 기준
- COUNT(*) WHERE orderbook_micro_state = 'bearish' AND ai_action = 'SKIP'
- COUNT(*) WHERE orderbook_micro_state = 'bearish' AND ai_action != 'SKIP'
- 위 두 cohort의 1분/5분/30분 후 mid price 변화 분포
- COUNT(*) WHERE orderbook_micro_ready = false
- COUNT(*) WHERE micro_state = 'bullish'
```

---

## 부록 C. 권고 테스트 목록

```text
test_orderbook_micro_state_thresholds_boundary
test_orderbook_micro_state_transitions
test_price_context_micro_keyset_parity_across_engines
test_insufficient_state_does_not_skip_alone
test_bearish_threshold_asymmetry_intentional
test_micro_snapshot_staleness_policy
```

---

**문서 끝**
