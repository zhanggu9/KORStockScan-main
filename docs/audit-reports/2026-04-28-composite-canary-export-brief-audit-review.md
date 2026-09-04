# Entry Composite Canary Auditor Export Brief 감리 검토

검토일: `2026-04-28`
검토자 역할: 시스템트레이더(감사인)
검토 대상: `Entry Composite Canary Auditor Export Brief` (기준일 2026-04-28)

---

## 판정: 조건부 승인 — 즉시 시정 3건, 보완 2건

baseline 정의, reference/baseline 분리, 성공기준/guard 분리, direction-only 강등 — 이 4개 잠금 원칙은 이전 감사 권고와 정합한다. 특히 §2-1의 hard baseline 정의는 04-23 정정본 §2-3과 04-27 F-4에서 권고한 `same bundle + canary_applied=False` 기준을 정확히 반영했다.

다만 성공 기준 4개 중 2개에 정의 결함이 있고, 이전 감사에서 잠금한 원칙 2건이 본 brief에 누락되어 있다. brief가 외부 export 용도라면 이 누락이 외부 판정자의 오해를 부른다.

---

## 1. 즉시 시정 항목 (3건)

### [시정 1] 성공 기준 2번 — N_min을 성공 기준으로 분류한 오류

§2-3 성공 기준 2번: "`submitted_orders >= 20`"

이 수치는 Plan Rebase 중심 문서 §6에서 **`N_min` gate 조건**(submitted_orders < 20일 때 hard pass/fail 금지)으로 정의된 값이다. 즉 "판정 가능 여부"의 최소 기준이지, "canary가 성공했는가"의 기준이 아니다.

이것을 성공 기준으로 분류하면:
- submitted_orders가 20에 도달한 것만으로 "성공 1개 충족"으로 카운트될 수 있음
- 실제로는 N_min gate를 통과한 것일 뿐, 효과 검증은 아직 시작 안 된 상태

**권고조치**: §2-3에서 `submitted_orders >= 20`을 **성공 기준에서 제거**하고 §2-4의 direction-only 강등 규칙 옆에 **"판정 가능 전제조건"**으로 분리 배치. 즉:

```
판정 가능 전제 (모두 충족 시에만 hard pass/fail):
- submitted_orders >= 20
- baseline 표본 수 >= N_min
- ShadowDiff0428 해소

성공 기준 (전제 충족 후 평가):
- budget_pass_to_submitted_rate >= baseline + 1.0%p
- latency_state_danger / budget_pass 비율 -5.0%p 이상 개선
- submitted → full_fill + partial_fill 전환율 비악화
```

### [시정 2] 성공 기준 4번 — "비악화"의 정량 기준 부재

§2-3 성공 기준 4번: "`submitted → full_fill + partial_fill` 전환율 비악화"

"비악화"가 정량화되어 있지 않다. 가능한 해석:
- (a) baseline과 정확히 같거나 높음
- (b) baseline 대비 -1.0%p 이내
- (c) 통계적으로 유의한 하락이 아님

판정자에 따라 결과가 갈린다. 특히 직접 손익에 영향을 주는 체결품질 지표인데 임계값이 없는 것은 위험하다.

**권고조치**: "비악화"를 **"baseline 대비 -2.0%p 이내"**로 명시. 사유: 체결품질은 일간 변동성이 ±2%p 정도이므로, 그 이상의 하락은 명백한 악화로 판정.

### [시정 3] 5-parameter bundle 원칙 누락

본 brief에 04-27 F-1에서 잠금한 핵심 원칙이 빠져 있다:

> "`latency_quote_fresh_composite`는 5개 파라미터(`signal>=88`, `ws_age<=950ms`, `ws_jitter<=450ms`, `spread<=0.0075`, `quote_stale=False`)를 묶음 단위 ON/OFF로 운영하며, 개별 파라미터 효과는 분리 측정하지 않는다."

이 원칙이 brief에 없으면, 외부 판정자가 결과를 보고 "ws_age threshold만 살리면 되겠다" 같은 부분 적용을 시도할 수 있다. 그 순간 단일축 원칙이 사후 우회된다.

**권고조치**: §2-3 또는 §2-4 사이에 §2-3a "묶음 단위 운영" 항목 신설:

```
2-3a. 묶음 단위 운영 원칙

- canary 5개 파라미터는 묶음 단위로만 ON/OFF한다.
- 묶음 효과만 판정하며, 개별 파라미터 효과는 분리 측정하지 않는다.
- 묶음이 실패하면 5개 파라미터 모두 동시 OFF한다.
- 부분 적용("ws_age만 유지" 등) 또는 묶음 분해 시도는 단일축 원칙 위반으로 금지한다.
```

---

## 2. 보완 항목 (2건)

### [보완 1] `ShadowDiff0428` 정의 부재

§1-4와 §2-4에서 `ShadowDiff0428`을 두 차례 언급하나, brief 내에 정의가 없다. brief가 export 용도라면 외부 판정자는 이것이 무엇인지 알 수 없다.

추정: submitted/full/partial 집계 경로 간 차이를 추적하는 항목으로 보이나, 다음 정보가 누락:
- 어떤 두 집계의 차이인가 (예: live runtime vs offline bundle?)
- 해소 기준은 무엇인가 (정확히 일치? 1건 이내?)
- 해소 책임자/일정은?

**권고**: §2-4 끝에 `ShadowDiff0428` 1줄 정의 추가. 예: "submitted/full/partial 집계의 live runtime 경로와 offline bundle 경로 간 차이가 1건 이내로 좁혀진 상태"

### [보완 2] direction-only 판정의 유효기간 누락

§2-4 direction-only 강등 규칙에 **유효기간이 없다**. 04-23 정정본 R-8에서 잠금한 규칙은:

> "방향성 판정은 2영업일 이내 재판정 필수. 미재판정 시 자동 보류"

이 brief에서는 "다음 판정창으로 넘긴다"고만 했고, 그 다음 판정창이 안 열리거나 또 표본 부족이면 무한 순연될 수 있다.

**권고**: §2-4에 "direction-only 판정은 발생일로부터 2영업일 이내 재판정 필수. 미재판정 시 canary 자동 OFF" 추가.

---

## 3. fast_reuse 활성 여부 — 판정 누락 확인

04-27 B-1에서 권고한 "fast_reuse 활성 여부 확인을 다음 후보 우선순위 결정 전 선행"이 본 brief에 반영되어 있지 않다. brief의 범위가 `latency_quote_fresh_composite` 단일축이므로 다른 축 우선순위는 다루지 않는 것이 맞으나, **현재 composite canary 결과 해석에 fast_reuse 활성 상태가 영향을 준다**:

- fast_reuse가 미활성인 채로 composite가 성공하면 → composite 효과로 잠정 판정
- fast_reuse가 미활성인 채로 composite가 실패하면 → composite 효과 부재인지 fast_reuse 미활성이 latency 병목을 유지한 것인지 분리 불가

**권고**: §2 끝에 1줄 메모 추가. "본 축 판정 시 fast_reuse 활성 상태(04-27 B-1 결과)를 보조 정보로 첨부할 것"

---

## 4. 긍정 평가

1. **§2-1 baseline 정의의 정확성**: `same bundle + canary_applied=False + normal_only + post_fallback_deprecation` 4중 조건. 04-23~04-27 감사에서 단편적으로 흩어져 있던 baseline 조건을 단일 표현으로 통합한 것이 본 brief의 핵심 가치
2. **§2-2 reference/baseline 분리**: offline bundle을 "참고선"으로 격하한 표현이 정확. 이전 보고서에서 자주 발생하던 "어제 수치 대비 비교"의 시점 오염 문제를 사전 차단
3. **§2-3 성공기준/guard 분리**: 두 개념을 섞었을 때 발생하는 양방향 오판(부작용 큰데 일부 개선으로 통과 / 표본 부족인데 성공으로 읽기)을 명시한 것이 적정
4. **§2-4 direction-only 강등**: hard pass/fail을 닫지 않는 보수적 접근. 04-21에 처음 권고한 "표본 부족 시 hard pass/fail 금지" 원칙의 일관 유지

---

## 5. 수정권고 요약

| 번호 | 분류 | 조치 | 기한 |
|---|---|---|---|
| G-1 | **즉시** | `submitted_orders >= 20`을 성공 기준에서 제거, "판정 가능 전제조건"으로 분리 배치 | 다음 판정 전 |
| G-2 | **즉시** | "비악화"를 "baseline 대비 -2.0%p 이내"로 정량화 | 다음 판정 전 |
| G-3 | **즉시** | §2-3a "묶음 단위 운영" 원칙 신설 (5개 파라미터 묶음 ON/OFF, 개별 분리 금지) | 다음 판정 전 |
| H-1 | 보완 | `ShadowDiff0428` 1줄 정의 추가 | 04-28 장중 |
| H-2 | 보완 | direction-only 판정의 2영업일 유효기간 명시 | 04-28 장중 |

---

## 6. 결론

이 brief는 **이전 감사들에서 분산되어 있던 baseline·성공기준·guard·강등 규칙을 단일 축으로 압축**한 것으로, 외부 export 문서로서의 골격은 적절하다.

다만 즉시 시정 3건은 brief의 신뢰성에 직접 영향을 준다:
- G-1(N_min을 성공 기준으로 분류한 오류)는 판정 자체를 왜곡할 수 있음
- G-2("비악화" 미정량)는 판정자별 결과 불일치를 초래
- G-3(묶음 단위 원칙 누락)은 외부에서 부분 적용 시도를 차단하지 못함

다음 판정 창이 열리기 전에 이 3건을 반영해야 brief가 export 용도로 작동한다.

direction-only 유효기간(H-2)이 빠진 것은 가장 가벼운 누락이지만, 04-23에 잠금한 원칙이 brief가 바뀔 때마다 다시 빠지는 패턴이 보인다. 잠금 원칙은 brief 템플릿 단계에서 고정 항목으로 두는 것이 안전하다.

---

> 감사인 서명: 시스템트레이더(감사인)
> 검토 완료 시각: 2026-04-28
