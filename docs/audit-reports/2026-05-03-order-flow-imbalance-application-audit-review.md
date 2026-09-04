# OFI 적용현황 보고서 검토 — 감리 결과 (`2026-05-03`)

> 작성시각: `2026-05-03 KST`
> 입력 보고서: `2026-05-03-order-flow-imbalance-application-audit-report.md`
> 검토 관점: 잘못 적용된 부분(misapplication) / 개선되어야 할 사항(incomplete · gap)
> 검증 방법: 입력 보고서 §1~§9의 주장과 인용 라인을 1:1 검증. 상수·임계값·결합 정책은 별도 검토.

---

## 0. TL;DR

**총평: "현재 상태에 대한 사실 보고"로는 정확하나, "OFI가 의도대로 일하고 있느냐"의 검증으로는 미달.** 

입력 보고서는 코드의 **존재(presence)**를 정확히 입증하지만, 다음 세 가지를 **입증하지 않은 채 적용을 인정**하고 있습니다.

1. **임계값 비대칭의 의도 불명** — bullish/bearish 임계가 대칭이 아니다. 이게 의도된 보수성인지 우연인지 보고서에 없다.
2. **결합 정책의 산문 기술 부재** — `ready`, `micro_state`, `sample_quote_count`, `price_below_bid_bps`, `latency_state` 사이의 우선순위/충돌 해소 정책이 한 군데에 정리돼 있지 않다.
3. **도입 효과의 사전·사후 측정 부재** — "기능이 켜져 있고 로그가 남는다"가 "기능이 가치를 낸다"의 증명이 아니다.

가장 시급한 항목 두 가지:

- **§2.1 임계값 비대칭** — `bullish (z≥+1.2 ∧ qi≥0.55)` vs `bearish (z≤-1.0 ∧ qi<0.48)`. SKIP을 더 쉽게 트립시키는 방향으로 비대칭이며, 그 결과 진입 기회 손실 가능. **의도 명문화 또는 대칭화** 둘 중 하나가 필요.
- **§4.1 도입 효과 측정 부재** — `dynamic_entry_ai_price_canary_p2`의 `2026-05-04 POSTCLOSE` keep/OFF 판정이 다가오는데, OFI feature on/off cohort 비교가 보고서에 없다. **판정 직전에는 반드시 필요.**

---

## 1. 검증 — 보고서 주장의 정합성

| 보고서 주장 | 검증 결과 | 비고 |
| --- | --- | --- |
| websocket → observer 입력 (§3.1) | ✓ 인용 라인 일관 | record_trade/record_quote 분리 적절 |
| OFI/QI 6종 + micro_state 계산 (§3.2) | ✓ 항목 정합 | 단, 시간 윈도우/EWMA 알파 미공개 (§3.1) |
| latency snapshot 포함 (§3.3) | ✓ | snapshot 시점과 주문 전송 시점의 gap은 별도 (§3.3) |
| price_context 주입 (§3.4) | ✓ | flag 게이팅(`SCALPING_ENTRY_PRICE_ORDERBOOK_MICRO_ENABLED`) 정확 |
| AI 프롬프트 규칙 반영 (§3.5) | ⚠️ **부분 정합** | 규칙 요약은 정확하나 결합 우선순위 부재 (§2.2) |
| 3 엔진 parity (§3.6) | ⚠️ **표현 과장** | 입력 경로는 동일하나 OpenAI/DeepSeek은 미승인 라우팅 (§5.2) |
| flag 기본값 ON (§3.7) | ✓ | |
| 로그 provenance 10종 (§4) | ✓ | 사후 감리 가능 |
| 테스트 2건 (§5) | ⚠️ **커버리지 부족** | bullish/threshold 경계/state 전이 미검증 (§4.2) |
| holding/exit 미적용 (§6) | ✓ | 단, 그것이 의도인지 보류인지 불명 (§3.4) |

요약: 보고서 §1~§4의 사실 기술은 정확하다. 문제는 §5~§9의 **해석과 결론**에 검증 누락이 있다는 점이다.

---

## 2. 잘못 적용된 부분 (Misapplications)

### 2.1 micro_state 임계값 비대칭 — bias toward SKIP

보고서 §3.2가 인용한 임계:

| 상태 | 조건 |
| --- | --- |
| `bullish` | `ofi_z ≥ +1.2` **AND** `qi_ewma ≥ 0.55` |
| `bearish` | `ofi_z ≤ -1.0` **AND** `qi_ewma < 0.48` |

대칭 기준점에서의 거리:

| 축 | 균형점 | bullish 거리 | bearish 거리 | 비대칭 |
| --- | --- | --- | --- | --- |
| `ofi_z` | 0 | +1.2 | -1.0 | bearish가 0.2 더 가까움 |
| `qi_ewma` | 0.50 | +0.05 | -0.02 | bearish가 0.03 더 가까움 |

**영향**: 두 축 모두에서 `bearish` 발동이 `bullish` 발동보다 쉽다. 그리고 프롬프트는 `bearish + ready → SKIP 근거 가능`(§3.5)이므로 비대칭은 **진입 회피 방향으로 system-wide bias**를 만든다.

이 비대칭이:

- (a) **의도된 보수성** — 한국시장 특성상 분배(ask 측 압박)가 흡수보다 더 의미 있다는 사전 분석 결과라면, 명시 필요.
- (b) **우연** — 튜닝 과정에서 우연히 형성됐다면, 대칭화 또는 데이터 기반 재calibration 필요.

보고서 어디에도 의도 명시 없음. **둘 중 하나로 결정 + 명문화**가 필요하다.

권고:

```
# 명시 옵션 A — 보수성 의도 인정
SCALPING_OFI_BEARISH_BIAS_INTENTIONAL = True
# 근거: 한국시장 평균 매도 압박 우위 / 분배 시그널의 우선 인지 / Backtest XX 기준
# Z 임계 -1.0, QI 임계 0.48은 대칭값 -1.2, 0.45 대비 ~30% 더 자주 트립

# 명시 옵션 B — 대칭화
SCALPING_OFI_Z_BULL_THRESHOLD = 1.2
SCALPING_OFI_Z_BEAR_THRESHOLD = -1.2   # ← -1.0 → -1.2
SCALPING_OFI_QI_BULL_THRESHOLD = 0.55
SCALPING_OFI_QI_BEAR_THRESHOLD = 0.45  # ← 0.48 → 0.45
```

### 2.2 AND 결합의 보수성 vs SKIP 발동의 자유 — 결합 비대칭

`bullish`/`bearish`는 **AND** 조합이지만(둘 다 만족해야 발동), `bullish` 상태가 진입 결정에 미치는 영향은 보고서에 명시 없음. 대조적으로 `bearish + ready`는 SKIP 근거가 된다.

즉 다음 비대칭이 발생한다.

| 시나리오 | micro_state | 결과 |
| --- | --- | --- |
| `ofi_z = +2.0, qi_ewma = 0.52` (한쪽만 강함) | `neutral` | 프롬프트상 SKIP 금지 |
| `ofi_z = +1.3, qi_ewma = 0.56` (둘 다 약하게 양) | `bullish` | 진입 가속 시그널 없음 (프롬프트 미명시) |
| `ofi_z = -0.5, qi_ewma = 0.46` (qi만 약하게 음) | `neutral` | SKIP 금지 |
| `ofi_z = -1.1, qi_ewma = 0.47` (둘 다 약하게 음) | `bearish` | SKIP 근거 가능 |

**영향**:
- `bullish`는 시스템에 어떤 영향도 주지 않는 사실상 dead state. AI가 자발적으로 가산점으로 사용하길 기대하는 정도.
- 즉 OFI는 사실상 **음의 비대칭 기능**(bearish-only signal)으로 작동.

이건 잘못된 적용이라기보다 **불완전한 설계**다. 양쪽 모두 의미를 갖게 하거나, 명시적으로 "bearish-only signal"이라고 문서화해야 한다.

권고:
- bullish → 진입 confidence 부스트의 입력 또는 cooldown 단축의 입력으로 활용. 또는
- 사문화된 bullish 분기를 제거하고 `bearish | non_bearish`의 이진 상태로 단순화.

### 2.3 `ready`와 `micro_state`의 이중 게이트 — 결합 정책 부재

OFI 사용을 결정짓는 게이트가 둘이다.

- `ready` (boolean)
- `micro_state` (`bullish`/`bearish`/`neutral`/`insufficient`)

보고서는 `ready=True ∧ micro_state=bearish` → SKIP 근거를 명시하지만, 다음 조합의 처리가 불명하다.

| `ready` | `micro_state` | 처리 정책 |
| --- | --- | --- |
| True | bearish | SKIP 근거 (명시) |
| True | bullish | ? |
| True | neutral | OFI 단독 SKIP 금지 (명시) |
| True | insufficient | OFI 단독 SKIP 금지 (명시) |
| **False** | bearish | **불명** |
| **False** | (any) | **불명** |

`ready=False`이면서 micro_state가 의미 있는 값을 가질 수 있는가? 코드 의미상으로는 두 필드가 redundant할 가능성도 있다. 그렇다면 둘 중 하나만 노출하는 게 맞다.

권고: 결합표(combination matrix)를 코드 또는 docstring에 명시. 또는 `ready=False`일 때 `micro_state`는 항상 `insufficient`가 되도록 invariant 강제.

### 2.4 프롬프트 규칙이 운영 정책의 SSoT가 됨 — fragile 결합

`bearish + ready → SKIP`이라는 정책이 **AI 프롬프트 안에만** 명시돼 있다(§3.5의 인용은 ai_engine.py:118).

문제:

- 프롬프트는 자연어다. 지키리라는 보장이 없다 (LLM은 가끔 무시한다).
- 프롬프트 변경(예: 새 모델로 갱신, system_instruction 분리 ON 등)이 일어나면 정책이 silent하게 drift한다.
- 3 엔진(Gemini/OpenAI/DeepSeek) 각자의 프롬프트가 동일한 정책을 갖고 있는지의 확인이 보고서에 없다 (§5.2와 연결).

권고: OFI → SKIP 정책을 **프롬프트 외부의 후처리 검증**으로 이중화.

```python
def post_validate_skip_decision(ai_result, price_ctx):
    micro = (price_ctx or {}).get("orderbook_micro", {})
    if ai_result.action == "SKIP":
        if not micro.get("ready"):
            return ai_result.with_warning("SKIP_BUT_OFI_NOT_READY")
        if micro.get("micro_state") in {"neutral", "insufficient"}:
            # 프롬프트 정책 위반 가능 — 다른 근거가 충분한지 검증
            return ai_result.with_warning("SKIP_WITHOUT_BEARISH_OFI")
    return ai_result
```

이런 후처리가 있어야 프롬프트 drift에 대한 안전망이 생긴다.

---

## 3. 누락 / 불완전 (Incomplete)

### 3.1 시간 윈도우 / EWMA 파라미터 미공개

보고서 §3.2는 6종 계산 항목을 나열했지만, 다음이 보고서에 없다.

- `ofi_z`의 z-score window 길이 (몇 초? 몇 quote?)
- `ofi_ewma`, `qi_ewma`의 smoothing 계수 α
- `depth_ewma`의 정규화 기준
- `sample_quote_count`의 최소 임계 (이 값 이상이면 `ready=True`?)

이 파라미터들은 OFI의 **반응성과 노이즈 사이의 trade-off를 결정**한다. 감리 재현성 관점에서 보고서에 명시되어야 한다.

권고: §3.2에 파라미터 표 추가. 또는 `orderbook_stability_observer.py`의 default 인자값을 직접 인용.

### 3.2 `holding/exit` 경로 미적용 — 의도인지 보류인지 불명

보고서 §6 항목 2: "holding/exit 실전 로직 직접 반영 미적용". 사실 진술은 정확하지만, **이게 의도인지 보류인지가 빠져 있다.**

OFI는 entry보다 holding/exit에 **더 직접적 가치**가 있을 가능성이 크다.

- 진입 시점: 이미 BUY 결정이 되어 있으므로 OFI는 마지막 sanity check 정도.
- 보유 시점: 진입 thesis가 깨졌는지(분배 시작/흡수 종료) 판단의 1차 입력.

만약 `holding_flow override`나 `evaluate_scalping_holding_flow`에 OFI가 들어가지 않는 게 의도라면, 그 이유가 명시돼야 한다. 가설:

- (a) holding 경로는 다른 입력(profit_rate, drawdown, recent_ticks)이 충분하므로 OFI 추가 가치가 작다고 판단.
- (b) holding 경로의 cadence(30~90초)가 OFI 변화의 timescale과 안 맞는다고 판단.
- (c) 단순히 P2 범위를 entry로 한정한 일정상의 결정. 향후 확장 예정.

(a)/(b)/(c) 중 무엇인지에 따라 후속 권고가 달라진다.

권고: 보고서 §6에 한 단락 보강. 또는 별도 backlog 항목 신설 (`OFIHoldingExtension-Plan`).

### 3.3 Snapshot staleness — AI 응답 latency 동안의 변화

OFI는 실시간 미시구조 신호다. timescale은 보통 100ms~1s. 그러나:

- price_context 빌드 → AI 호출 → AI 응답 → 주문 전송 사이의 latency는 보통 200~800ms (Tier2 Gemini 기준).
- 이 사이 micro_state는 바뀔 수 있다 (예: bearish였던 상태가 응답 도착 시점에 neutral).

보고서에 다음이 부재:

- AI 응답 도착 시점에서 micro_state를 **재확인**하는지
- 또는 snapshot 시점과 응답 시점의 시간차를 기록하는지(`ai_response_ms` 필드는 있으나 micro_state 시점은 별도 timestamp 없음)

권고:
- `orderbook_micro` snapshot에 `captured_at_ms` 타임스탬프 추가
- 후처리에서 `now - captured_at_ms > MICRO_STALE_THRESHOLD_MS`이면 micro 입력을 무시

### 3.4 entry decision (watching) 단계의 OFI 주입 여부 불명

보고서는 entry **price** canary(P2)에 OFI가 들어간다고 했지만, **watching 단계의 BUY/WAIT/DROP 결정**(`analyze_target prompt_profile=watching`, `entry_v1` schema)에 OFI가 들어가는지는 명시 안 됐다.

흐름:
```
WATCHING (BUY/WAIT/DROP 결정)
   ↓ BUY일 때만
SUBMITTED 직전 (USE_DEFENSIVE/USE_REFERENCE/IMPROVE_LIMIT/SKIP 결정)  ← OFI 주입
```

OFI를 SUBMITTED 직전에만 쓰는 건 좀 늦다. WATCHING 단계의 BUY 결정 자체에서 사용하는 게 더 자연스럽다 — 적어도 "BUY로 갈 후보를 좁히는" 단계에 정보가 있어야 한다.

권고:
- WATCHING prompt(`SCALPING_WATCHING_SYSTEM_PROMPT`)에 OFI 입력이 들어가는지 명시 검증.
- 들어가지 않는다면 `dynamic_entry_ai_price_canary_p2` 범위 너머의 별도 후속(`SCALPING_WATCHING_OFI_INPUT-Plan`)으로 분리.

### 3.5 종목별 calibration 부재

OFI 분포는 종목군별로 다르다.

- 대형주(시총 10조 원 이상): OFI std가 작고 변화가 느림. 임계 ±1.2가 너무 엄격할 수 있음.
- 소형주/테마주: OFI std가 크고 노이즈 많음. 임계 ±1.0~±1.2가 너무 헐거울 수 있음.

보고서 §6 항목 4에 "OFI 단독 손익 판정 체계"가 후속으로 언급되지만, 더 우선되는 건 **distribution-aware threshold**다. fixed threshold로는 시총 그룹별 SKIP율이 매우 다르게 나타날 수 있다.

권고: 운영 로그에서 종목 시총군별로 `bearish` 발동 빈도를 집계. 빈도가 그룹별로 ±20% 이상 차이가 나면 per-group threshold 도입.

---

## 4. 측정 / 검증 결손 (Validation Gap)

### 4.1 도입 효과의 사전·사후 측정 부재 — **가장 시급**

보고서가 입증한 것: **존재(presence) + 입력 경로(plumbing) + 로그 provenance**.
보고서가 입증하지 않은 것: **OFI 입력이 의사결정 품질을 개선하는가**.

`dynamic_entry_ai_price_canary_p2`의 `2026-05-04 POSTCLOSE` keep/OFF 판정이 다가온다. 그 시점에는 다음이 필요하다.

| 비교 | KPI |
| --- | --- |
| OFI ON cohort vs OFI OFF cohort (가능하다면 A/B) | `submitted_but_unfilled_rate`, `entry_slippage_bps`, `time_to_fill_p50/p90` |
| OFI ON 내에서 `bearish` SKIP 발동 vs `bearish` 무시 (다른 신호로 진입) | 30분 후 mid price 비교 |
| OFI ON 내에서 `bullish` 발생 cohort | 진입률 변화, 사후 수익률 |
| OFI staleness (§3.3) 분포 | snapshot age p50/p90/p99 |

이 측정이 없으면 keep/OFF 판정은 직관에 의존하게 된다.

권고: §9 다음 액션을 다음으로 격상.

```
P0 (포스트클로즈 직전):
- bearish SKIP 발동 표본 N건의 1분/5분/30분 후 mid price 변화 분포
- bearish 무시(SKIP 미발동) 표본의 동일 분포
- 두 분포 차이가 의사결정 가치를 만드는지의 통계적 검정 (Mann-Whitney 또는 단순 누적분포 비교)
```

이게 없으면 §8 결론은 "켜져 있음"의 보고일 뿐 keep/OFF 판정의 근거가 안 된다.

### 4.2 테스트 커버리지 — 경계값/전이/3 엔진 부재

보고서 §5의 테스트 2건은 다음을 검증한다.

- `qi`, `qi_ewma`, `ofi_*`, `depth_ewma` 계산
- `ready=True` + `ofi_z != None` + `micro_state` 생성

검증되지 않는 것:

- **bullish 조건의 경계값 테스트** (`ofi_z = 1.2 - ε` 시 neutral, `ofi_z = 1.2` 시 bullish 등)
- **state 전이** (bearish → neutral → bullish, neutral → insufficient)
- **임계값 비대칭이 의도대로 발동하는지** (§2.1과 짝)
- **3 엔진 모두 동일한 `price_context.orderbook_micro` 키 셋을 받는지**의 contract test
- **insufficient 상태에서 SKIP이 발생하지 않는지**의 후처리 검증 (§2.4와 짝)

권고: 다음 테스트를 P1 PR에 묶음.

```
test_orderbook_micro_state_thresholds_boundary
test_orderbook_micro_state_transitions
test_price_context_micro_keyset_parity_across_engines
test_insufficient_state_does_not_skip_alone
test_bearish_threshold_asymmetry_intentional   # §2.1 의도가 명시됐다면 그것의 회귀 보호
```

### 4.3 Provenance ↔ 의사결정 연결 검증 부재

보고서 §4는 10종 로그 필드(`orderbook_micro_*`)가 남는다고 했다. 그러나 이 필드들이 실제 의사결정과 **인과적으로 연결**되는지의 검증이 빠져 있다.

다음 sample 검증이 필요하다.

- `orderbook_micro_state=bearish` AND `result_source=live` AND `action=SKIP` 의 발생 건수
- 그중 reason 텍스트에 OFI/QI/imbalance/매도/분배 같은 단어가 포함된 비율
- 같은 종목의 같은 시점에서 micro_state가 neutral이었다면 SKIP이 발생했을지의 counterfactual

이게 측정되지 않으면 OFI가 실제로 SKIP 결정에 기여하는지 모른다 — AI가 OFI를 무시하고 다른 근거로 SKIP했을 수도 있다.

권고: P2 keep/OFF 판정 전 1주일치 로그에서 위 분포를 산출.

---

## 5. 운영 정책 결손 (Operational Policy Gap)

### 5.1 Observer 장애 시 fallback 정책 부재

`ORDERBOOK_STABILITY_OBSERVER`가 죽거나 lag되면 어떻게 되는가? 보고서에 명시 없음.

가능한 시나리오:

- Observer 프로세스 죽음 → snapshot이 None 또는 stale → `orderbook_micro=null`
- WS 끊김 → record_quote/record_trade 미수신 → `sample_quote_count`이 감소하다 0 → `insufficient`
- Observer 정상이지만 특정 종목의 데이터만 누락 → silent neutral

각각의 처리 정책이 코드 단일 진실의 원천에 명시돼 있는지 보고서에 검증 부재.

권고:
- Observer health check 추가 (`observer.is_healthy()` 또는 last_update timestamp)
- Health 미충족 시 `price_context.orderbook_micro = None`로 명시 누락
- AI는 None일 때와 insufficient일 때를 다르게 처리해야 함 (None: 시스템 장애, insufficient: 정상이나 표본 부족)

### 5.2 3 엔진 parity의 표현 — 운영 의미 없음

보고서 §3.6은 "3 엔진 모두 price_context를 동일하게 입력받는다"고 명시. 코드 인용은 정확하다.

그러나 운영 의미 차원에서:

- OpenAI/DeepSeek은 미승인 라이브 라우팅 (이전 감리 §10.2)
- 즉, 실제 production에서는 **Gemini만 OFI 입력을 사용**
- "3 엔진 parity"라는 표현은 **plumbing parity**일 뿐 **operational parity**가 아님

이걸 그대로 두면 후속 작업자가 "3 엔진에서 검증됐다"고 오해할 수 있다.

권고: §3.6의 표현을 다음과 같이 수정.

```
3 엔진 코드 입구는 동일한 price_context를 받도록 구현돼 있다 (plumbing parity).
다만 실제 운영 라우팅은 Gemini로 한정되며, OpenAI/DeepSeek 라우팅 enable 시점에는
별도 parity 검증(프롬프트 정책 동등성 + 응답 분포 동등성)이 선행되어야 한다.
```

### 5.3 AI 의존 의사결정 chain의 단일 실패점

OFI → SKIP 정책이 **AI를 통해서만** 적용된다(§2.4와 연결). 즉:

- AI가 ai_disabled → OFI 정보가 의사결정에 도달하지 못함
- AI가 lock_contention → OFI 정보 미반영
- AI parse_fail → fallback 경로(P1 resolver)로 가는데, 그 경로는 OFI 무관

따라서 시스템 장애 또는 부하 시점에는 **OFI 기능 자체가 무력화**된다. 이건 단순한 fallback 부재가 아니라 **"OFI가 가장 필요한 시점(시장 격변·고변동)에 정확히 작동 안 함"**을 의미한다.

고변동 시점일수록:
- AI 호출 빈도 ↑ → cooldown/lock_contention ↑
- OFI 신호 강도 ↑ (의미 있는 시점)
- 그러나 OFI 적용 path가 정확히 그때 끊김

권고: AI를 거치지 않는 **non-AI hard guard**를 별도로 도입할지 결정. 예:

```python
# AI를 거치지 않고도 작동하는 보조 hard rule
def pre_submit_ofi_guard(price_ctx, cfg):
    micro = (price_ctx or {}).get("orderbook_micro", {})
    if not micro.get("ready"):
        return GuardResult(block=False)
    if micro.get("micro_state") == "bearish":
        z = float(micro.get("ofi_z", 0))
        if z <= cfg.OFI_HARD_GUARD_Z_THRESHOLD:   # 예: -2.0 (매우 강한 bearish만)
            return GuardResult(block=True, reason="ofi_hard_bearish")
    return GuardResult(block=False)
```

이 guard는 매우 보수적인 임계(예: `z ≤ -2.0`)로 두고, AI 미동작 시점에서도 극단 케이스만 차단한다. AI가 정상 동작할 때는 AI의 판단을 신뢰하되, AI가 죽었을 때의 마지막 안전망 역할.

`SCALPING_OFI_HARD_GUARD_ENABLED=False`로 시작해 shadow→canary→live 단계로 enable 검토.

### 5.4 P2 keep/OFF 판정의 실패 모드 부재

보고서 §7은 문서·코드·계획이 모두 같은 결론이라고 함. 그러나 keep/OFF 판정 시 다음 시나리오가 보고서에 없다.

- `2026-05-04 POSTCLOSE`에 OFF가 결정되면, 코드 변경 없이 flag만 OFF인가? 아니면 코드 제거?
- OFF 후 재시도(re-canary) trigger는?
- KEEP인 경우 임계값 calibration 트리거(§3.5의 종목별 calibration)는 자동인가 수동인가?

권고: §9 다음 액션에 keep/OFF 결과별 후속 트리(decision tree) 추가.

```
KEEP:
  → §2.1 임계값 의도 명문화
  → §3.5 종목별 calibration 검토
  → §3.4 watching 단계 OFI 입력 검토
  → §5.1 observer health check
OFF:
  → 코드 보존 (제거 아님), flag OFF
  → 재시도 trigger: 임계값 재calibration 또는 holding/exit 적용 검토 시
부분 KEEP (특정 시간대/종목군만):
  → cohort-aware threshold 도입
```

---

## 6. 우선순위 매트릭스

| # | 항목 | 카테고리 | 시급도 | 권장 트랙 |
| --- | --- | --- | --- | --- |
| 4.1 | 도입 효과 측정 (cohort 비교) | 검증 결손 | **極高** | **P0 (POSTCLOSE 직전)** |
| 2.1 | 임계값 비대칭 의도 명문화 또는 대칭화 | misapplication | 高 | P0 |
| 2.4 | 프롬프트 외부 후처리 검증 | misapplication | 高 | P0 또는 P1 |
| 3.3 | snapshot staleness 측정 + 임계 | 불완전 | 中-高 | P1 |
| 5.1 | observer health check + None 처리 | 운영 결손 | 中-高 | P1 |
| 4.3 | provenance ↔ 의사결정 연결 검증 | 검증 결손 | 中 | P0 보고용 |
| 2.3 | ready/micro_state 결합표 명시 | misapplication | 中 | P1 |
| 4.2 | 테스트 커버리지 보강 | 검증 결손 | 中 | P1 |
| 2.2 | bullish 분기 활용 또는 dead state로 명시 | misapplication | 中 | P1 |
| 3.2 | holding/exit 미적용 의도/보류 명문화 | 불완전 | 中 | P1 |
| 5.4 | keep/OFF 판정 결과별 후속 트리 | 운영 결손 | 中 | P0 (POSTCLOSE 직전) |
| 3.1 | 시간 윈도우/EWMA α 공개 | 불완전 | 低 | 백로그 |
| 5.2 | "3 엔진 parity" 표현 정정 | 운영 결손 | 低 | 백로그 |
| 3.5 | 종목별 calibration | 불완전 | 低-中 | P2 (KEEP 결정 시) |
| 3.4 | watching 단계 OFI 입력 검토 | 불완전 | 低-中 | P2 |
| 5.3 | non-AI hard guard 도입 검토 | 운영 결손 | 低-中 | P2 (별도 설계) |

---

## 7. 권고 — P0 / P1 / P2 분리

### P0 — `2026-05-04 POSTCLOSE` 판정 직전 (이번 주)

1. **Cohort 비교 데이터 산출** (§4.1) — micro ON/OFF, bearish SKIP 유무, 그 이후 mid price 변화 분포.
2. **임계값 비대칭 의도 명문화** (§2.1) — 보수성 의도 인정 또는 대칭화. 둘 중 하나 결정 후 코드 또는 ADR 1쪽 작성.
3. **provenance ↔ 의사결정 연결 sample** (§4.3) — bearish + ready 발동 시 SKIP 비율, reason 분석.
4. **keep/OFF 판정 후 후속 트리** (§5.4) — 결정 직전에 의사결정 register 업데이트.

### P1 — 다음 스프린트 (구조 보강)

5. **프롬프트 외부 후처리 검증** (§2.4) — `post_validate_skip_decision()` 추가.
6. **snapshot staleness 추적** (§3.3) — `captured_at_ms` 타임스탬프 + threshold.
7. **observer health check + None 처리** (§5.1) — None과 insufficient 분리.
8. **테스트 커버리지** (§4.2) — boundary, transition, parity, post_validate 등 5건.
9. **결합표 명시** (§2.3) + **holding/exit 의도 명문화** (§3.2) + **bullish 분기 정리** (§2.2).

### P2 — KEEP 결정 후 (운영 검증 후)

10. **종목별 calibration** (§3.5)
11. **watching 단계 OFI 입력** (§3.4) — 별도 canary로 분리
12. **non-AI hard guard** (§5.3) — 매우 보수적 임계로 단계적 enable

---

## 8. 감리용 결론 — §8 보강안

원 보고서 §8 결론은 사실 진술로는 정확하지만, **현재 한계와 검증 상태**를 같이 명시하는 것이 정확하다. 다음 문안을 권고한다.

> 현재 코드베이스에는 Order Flow Imbalance가 `OFI/QI orderbook micro` 형태로 구현돼 있으며, 실시간 호가/체결 이벤트로부터 계산된 `ofi_norm`, `ofi_z`, `qi`, `qi_ewma`, `micro_state`가 스캘핑 `dynamic_entry_ai_price_canary_p2`의 AI 진입가 컨텍스트(`price_context.orderbook_micro`)에 주입됩니다. 이는 독립 hard gate가 아니라 submitted 직전 주문가/`SKIP` 판단을 보조하는 입력 feature이며, `neutral`/`insufficient` 상태에서는 OFI 단독으로 주문을 차단하지 않도록 프롬프트 수준에서 제한돼 있습니다.
>
> **다만 (1) bullish/bearish 임계값에 비대칭이 존재하며 그 의도가 명문화되지 않은 점, (2) OFI → SKIP 정책이 AI 프롬프트 안에만 명시되어 후처리 검증이 부재한 점, (3) 도입 효과의 cohort 비교가 보고서 작성 시점까지 산출되지 않은 점**이 한계입니다. 따라서 본 적용은 **plumbing 단계의 적용**으로 인정되며, **operational 단계의 적용** — 즉 의사결정 품질 개선의 통계적 입증 — 은 `2026-05-04 POSTCLOSE` 판정의 일부로 별도 산출되어야 합니다.

---

## 9. 검증 명령

본 감리 결과를 코드/로그에서 재현·검증할 때:

```bash
# 임계값 비대칭 확인
grep -nE "ofi_z|qi_ewma|micro_state" src/trading/entry/orderbook_stability_observer.py

# 결합표 / 후처리 검증 부재 확인
grep -nE "orderbook_micro|micro_state" src/engine/sniper_state_handlers.py
grep -nE "post_validate|skip_validation" src/engine/sniper_state_handlers.py   # 결과 0건 예상

# 3 엔진 parity (plumbing)
grep -nE "price_context|orderbook_micro" \
    src/engine/ai_engine.py src/engine/ai_engine_openai.py src/engine/ai_engine_deepseek.py

# 프롬프트 정책 SSoT 검증
grep -nE "neutral|insufficient|bearish" src/engine/ai_engine.py | head

# 로그 provenance
grep -nE "orderbook_micro_(state|ofi_z|qi|ready)" src/engine/sniper_state_handlers.py
```

추가로 POSTCLOSE 판정 직전 다음 운영 쿼리(또는 그에 준하는 분석)가 필요하다.

```text
# 1주일치 운영 로그 기준
- COUNT(*) WHERE orderbook_micro_state = 'bearish' AND ai_action = 'SKIP'
- COUNT(*) WHERE orderbook_micro_state = 'bearish' AND ai_action != 'SKIP'
- 위 두 cohort의 1분/5분/30분 후 mid price 변화 분포
- COUNT(*) WHERE orderbook_micro_ready = false (observer 장애 추정)
- COUNT(*) WHERE micro_state = 'bullish'  (사문화 여부 확인)
```

---

## 10. 한 줄 결론

> **OFI는 plumbing 차원에서 깨끗하게 들어와 있고 로그도 잘 남는다. 그러나 임계값 비대칭이 명문화되지 않았고, 프롬프트 내 정책에만 의존하며, 도입 효과가 측정되지 않은 채 keep/OFF 판정이 다가오고 있다. POSTCLOSE 판정 전에 §4.1 cohort 비교와 §2.1 의도 명문화는 반드시 닫아야 한다.**
