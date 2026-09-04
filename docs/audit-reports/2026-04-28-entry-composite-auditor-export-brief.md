# Entry Composite Canary Auditor Export Brief

기준일: `2026-04-28 KST`  
대상 축: `latency_quote_fresh_composite`

## 1. 판정

이 축의 감리 포인트는 4개로 잠근다.

1. hard baseline은 `same bundle + canary_applied=False + normal_only + post_fallback_deprecation` 표본이다.
2. `2026-04-27 15:00` offline bundle은 hard baseline이 아니라 방향성 참고선이다.
3. 성공 기준과 rollback guard는 분리해 해석한다.
4. baseline 부족 또는 `ShadowDiff0428` 미해소 시에는 `direction-only` 판정으로만 유지한다.

## 2. 근거

### 2-1. Baseline 고정 원칙

- 같은 bundle 안의 `canary_applied=False` 표본이 가장 가까운 대조군이다.
- 이 기준을 쓰면 장중 장세 변화, snapshot 시각 차이, bundle 간 조건 차이로 인한 왜곡을 가장 적게 받는다.
- 따라서 이 축의 primary baseline은 `same bundle + canary_applied=False + normal_only + post_fallback_deprecation`으로 고정한다.

### 2-2. Reference와 Baseline 분리

- `2026-04-27 15:00` offline bundle은 주병목과 방향성을 설명하는 reference로는 유효하다.
- 그러나 같은 bundle 내 대조군보다 우선할 수 없고, data-quality gate가 완전히 닫힌 상태도 아니다.
- 따라서 이 수치는 `현 상태가 얼마나 나빴는가`를 보여주는 참고선으로만 사용한다.

### 2-3. 성공 기준과 Guard 분리

- 성공 기준은 제출 회복과 blocker 감소를 보는 지표다.
- rollback guard는 부작용과 회귀를 끊는 안전 기준이다.
- 두 기준을 섞으면 일부 개선이 있어도 부작용이 큰 케이스를 오판하거나, 반대로 표본 부족을 성공처럼 읽는 오류가 생긴다.

현재 성공 기준:

- `budget_pass_to_submitted_rate >= baseline + 1.0%p`
- `submitted_orders >= 20`
- `latency_state_danger / budget_pass` 비율 `-5.0%p` 이상 개선
- `submitted -> full_fill + partial_fill` 전환율 비악화

현재 주요 guard:

- `loss_cap`
- `reject_rate`
- `latency_p95`
- `partial_fill_ratio`
- `fallback_regression`
- `composite_no_recovery`

### 2-4. Direction-Only 강등 규칙

- baseline 표본이 `N_min`에 못 미치면 hard pass/fail을 닫지 않는다.
- `ShadowDiff0428`이 닫히기 전까지는 submitted/full/partial 집계차가 남아 있으므로 hard baseline 승격을 보류한다.
- 이 경우 판정은 `유지/종료 방향성`만 읽고, 승격/확정은 다음 판정창으로 넘긴다.

## 3. 다음 액션

- 감리인은 위 4개가 checklist, 중심 문서, 보고 문구에서 동일하게 유지되는지 확인한다.
- `ShadowDiff0428` 해소 전에는 이 축의 판정을 `direction-only`로만 승인한다.
- hard pass/fail 승격은 same bundle baseline 확보와 data-quality gate 해소가 동시에 확인된 뒤에만 허용한다.
