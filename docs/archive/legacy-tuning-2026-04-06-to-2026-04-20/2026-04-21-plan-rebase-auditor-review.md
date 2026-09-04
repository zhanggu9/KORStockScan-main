# 2026-04-21 Plan Rebase 감사인 검토보고서

> Deprecated as active plan: 이 문서는 1차 감사 검토 입력 기록이다.
> 현재 실행 기준은 [2026-04-21-plan-rebase-auditor-report.md](/home/ubuntu/KORStockScan/docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-21-plan-rebase-auditor-report.md)와 날짜별 stage2 checklist를 따른다.
> 본 문서의 `shadow/counterfactual` 지적 문구는 최종 반영 과정의 감사 의견으로만 읽고, 실행 계획으로 사용하지 않는다.

검토일: `2026-04-21`
검토자 역할: 시스템트레이더(감사인)
검토 대상 문서:
- `2026-04-21-stage2-todo-checklist.md`
- `workorder-0421-auditor-performance-report.md`
- `2026-04-21-plan-rebase-auditor-report.md`

---

## 0. 총평

**결론: 개편 방향은 타당하나, 실행계획에 구조적 오류 3건이 있다.**

fallback 설계 실패의 원인귀속, 폐기 판정, 응급 차단 조치는 모두 적절했다. 그러나 후속 튜닝계획이 **"shadow/counterfactual부터 검증"**이라는 원칙을 반복 명시하고 있는데, 이는 현 시스템의 상황과 맞지 않다. GPT 엔진의 무분별한 설계 산출물이 손실을 초래한 직접 원인인 상황에서, shadow 관찰 기간을 추가로 두는 것은 **손실 노출 기간만 연장**할 뿐 판정 품질을 높이지 못한다.

아래 3건의 구조적 오류를 시정한 뒤 실행해야 한다.

---

## 1. 구조적 오류 지적

### [필수 시정 1] shadow/counterfactual 원칙 철회 → canary 즉시 적용 원칙으로 전환

**지적 대상**: Plan Rebase 감사보고서 §6-2 재개 조건 5항, §7 다음 튜닝 후보 전체, §9 다음 액션 4항, stage2 체크리스트 `[PlanRebase0422]`

**현행 문제**:
- "해당 축은 live가 아니라 shadow/counterfactual부터 검증" — 3회 반복 명시
- `position_addition_policy` 초안도 "live 적용은 금지하고 shadow/counterfactual부터 설계" 명시

**감사인 판단**:

shadow는 **설계가 불확실할 때** 리스크를 통제하는 수단이다. 그런데 이번 사고의 본질은 설계 불확실성이 아니라 **GPT 엔진이 산출한 fallback 로직 자체가 의도와 구현이 불일치한 결함품**이었다는 점이다. 결함을 폐기한 뒤 정상 로직을 복원하는 과정에서 shadow를 거치면:

1. 최소 2~3영업일의 관찰 버퍼가 추가된다
2. 그 기간 동안 시스템은 **fallback 폐기 후 축소된 진입 퍼널**로만 운영되어 기회비용이 누적된다
3. shadow 데이터는 어차피 live 체결 조건과 다르므로 canary 전환 시 재판정이 필요하다

따라서 다음 튜닝축은 **canary로 즉시 실전 적용**하되, rollback 트리거를 수치로 고정하여 실패 시 당일 내 복귀하는 구조가 올바르다.

**권고조치**:
- Plan Rebase §6-2 5항: "shadow/counterfactual부터 검증" → **"canary 즉시 적용 + 당일 rollback guard(N_min, reject_rate, loss_cap) 수치 고정"**으로 교체
- §7 전체: "live 적용 금지" 문구 삭제, 각 후보에 **canary 착수 조건 + rollback 수치** 추가
- §9 4항 `[PlanRebase0422]`: "shadow/counterfactual부터 설계" → **"canary 설계 + rollback guard 정의"**로 변경
- stage2 체크리스트 `[PlanRebase0422]`: 동일하게 수정

---

### [필수 시정 2] 관찰축 과잉 — 불필요 축 즉시 제거

**지적 대상**: stage2 체크리스트 장후 항목 전체, Plan Rebase §4 전수점검 범위

**현행 문제**: 장후 체크리스트에 **17개 미완료 항목**이 15:20~18:00 사이 2시간 40분에 배치되어 있다. 항목당 평균 9.4분이며, 이 중 상당수는 이미 폐기된 축의 잔여 절차이거나 판정 불가능한 저표본 축이다.

**감사인 판단 — 즉시 제거 대상 6건**:

| 제거 대상 | 제거 사유 |
|---|---|
| `[AuditFix0421] split-entry 즉시 재평가 canary 1일차 착수 또는 보류 기록` | split-entry 전체가 폐기됨. "착수 또는 보류"를 판정할 대상 자체가 없다. **폐기 완료로 닫고 종결.** |
| `[VisibleResult0421] split-entry leakage canary 승격 또는 보류 사유 기록` | 동일. split-entry 폐기로 leakage canary 승격 판정은 무의미. **폐기 완료로 닫고 종결.** |
| `[PlanSync0421] 개별종목(에이럭스) 관찰축 4분해 유지 여부 재확인` | 개별종목 4분해는 전수점검 로직표에 흡수된다. 별도 항목으로 유지하면 로직표와 이중관리. **로직표 작성 시 포함으로 병합.** |
| `[VisibleResult0421] legacy shadow 1순위 축 canary 착수` | shadow 원칙 자체를 철회해야 하므로 "legacy shadow에서 canary 전환" 절차가 불필요. 다음 튜닝 1축을 바로 canary로 착수하면 된다. **§1 시정과 함께 폐기.** |
| `[AuditFix0421] legacy shadow 저표본 축 폐기 또는 추후 live 병합 경로 고정` | `same_symbol/split_entry/partial_only_timeout` 표본 0~2건 축은 판정 자체가 불가. 병합 경로를 고민하는 시간이 낭비. **전량 폐기로 즉시 종결.** |
| `범위 확정 실패 시 사유 + 다음 실행시각 기록` | 이것은 독립 체크항목이 아니라 `작업12 A/B 범위 확정` 실패 시 해당 항목 내에 기록하면 된다. **별도 항목 해제, 상위 항목에 흡수.** |

**정리 후 장후 필수 항목: 11개 → 실질적으로 의미 있는 판정 항목만 남긴다.**

---

### [필수 시정 3] 튜닝 일정 압축 — 최소기간 실행

**지적 대상**: Plan Rebase §9 다음 액션, stage2 체크리스트 전체 일정 구조

**현행 문제**:
- `진입/보유/청산 로직표 작성` → 04-21 INTRADAY (10:50~12:20)
- `fallback 오염 코호트 재집계` → 04-21 INTRADAY (12:20~12:50)
- `다음 튜닝포인트 1축 재선정` → 04-21 POSTCLOSE (16:30~17:00)
- `position_addition_policy 초안` → **04-22 PREOPEN** (08:00~08:30)

로직표와 코호트 재집계는 이미 Plan Rebase 보고서 §4~§5에 **표 형태로 70% 이상 작성 완료** 상태다. 이를 별도 1.5시간짜리 작업으로 분리하는 것은 과잉이다.

**권고조치 — 압축 일정**:

| 단계 | 기존 일정 | 압축 일정 | 사유 |
|---|---|---|---|
| 로직표 확정 | 04-21 10:50~12:20 (90분) | 04-21 10:50~11:30 (40분) | §4 표를 검증·보완만 하면 됨 |
| 코호트 재집계 | 04-21 12:20~12:50 (30분) | 04-21 11:30~11:50 (20분) | §5 정의 완료, SQL/쿼리 실행만 남음 |
| 1축 재선정 | 04-21 16:30~17:00 (30분) | 04-21 POSTCLOSE 15:20~15:40 (20분) | 후보 4개 중 선택, 코호트 데이터 기반 |
| canary 설계 + rollback guard | 04-22 08:00~08:30 (30분) | **04-21 POSTCLOSE 15:40~16:10** (30분) | shadow 제거로 설계 단순화, 당일 완료 가능 |
| **canary 실전 적용** | 미정 (shadow 후) | **04-22 PREOPEN 08:00~08:10** | canary ON + rollback guard 확인만 |

이렇게 하면 04-22 장 시작 시점에 이미 다음 튜닝 1축이 canary로 가동 중이다. 기존 계획 대비 **최소 1영업일 단축**.

---

## 2. 감사 질문에 대한 의견

Plan Rebase 보고서 §8에서 요청한 6개 질문에 대해 감사인 의견을 아래와 같이 제시한다.

### Q1. `fallback_scout/main`을 실패 설계로 폐기하고 baseline에서 제외하는 판단이 타당한가?

**타당하다.** 의도(탐색형 분할진입)와 구현(동시 2-leg 번들)이 불일치한 것은 설계 결함이지 파라미터 문제가 아니다. 파라미터 튜닝으로 교정할 수 있는 범위를 벗어났으므로 폐기가 맞다. 단, 폐기 사유를 코드 주석과 변경이력에 **영구 기록**해야 한다. GPT 엔진이 향후 유사 설계를 재제안하는 것을 차단하려면 프롬프트 레벨에서도 "fallback_scout/main 패턴 금지" 제약을 명시해야 한다.

### Q2. `fallback_single`을 1차 응급가드 오류 표본으로 별도 격리하는 기준이 충분한가?

**충분하다.** `entry_mode=fallback_single`로 태그된 표본은 명확히 식별 가능하고, 발생 시간대(09:24~09:29)도 특정되어 있다. 다만 `fallback_single`이 생성한 포지션이 이후 HOLDING/청산 단계에서 `normal` 포지션과 **동일 종목으로 합산**되었을 가능성이 있으므로, 격리 시 `symbol + timestamp` 교차검증을 추가할 것.

### Q3. `normal_only`와 `post_fallback_deprecation`을 새 baseline으로 삼는 것이 타당한가?

**조건부 타당.** `normal_only`는 과거 전체 기간에서 추출하므로 표본이 충분하다. `post_fallback_deprecation`은 09:45 이후 표본만 포함하므로 당일 기준으로는 표본 부족이 확실하다. 따라서:
- **즉시 사용 가능한 baseline**: `normal_only` (과거 전체)
- **보조 baseline**: `post_fallback_deprecation` (04-21 이후 누적, 3영업일 이상 축적 후 primary 전환 검토)

### Q4. 다음 튜닝 1순위를 `position_addition_policy`로 두는 것이 타당한가?

**타당하지 않다. `entry_filter`를 1순위로 권고한다.**

사유:
- `position_addition_policy`(불타기/물타기/추가진입 상태머신)는 **설계 복잡도가 높고** soft_stop/HOLDING/청산과 모두 연동되어 단일축 canary로 격리하기 어렵다
- 현재 시스템의 가장 직접적인 손실 원인은 **불량 진입**이다. fallback이 폐기되면서 진입 필터가 사실상 `SAFE → ALLOW_NORMAL`만 남았고, 이 필터의 품질이 전체 성과를 결정한다
- `entry_filter` 개선은 단일 게이트 파라미터 조정이므로 canary 격리가 쉽고, rollback도 단순하다
- 진입 품질이 올라가면 `position_addition_policy`의 설계 기반(어떤 종목에 추가할 것인가)도 자연스럽게 명확해진다

**권고 우선순위**: `entry_filter` → `holding_exit` → `position_addition_policy` → `EOD/NXT`

### Q5. `position_addition_policy` 설계 시 shadow 검증 순서

shadow 자체를 철회하므로 이 질문은 **"canary 검증 순서"**로 재해석한다.

추후 `position_addition_policy`를 다룰 때의 canary 순서:
1. **추가진입 중단 규칙** (가장 단순, rollback 용이) — 달아나는 종목에 추가하지 않는 gate
2. **불타기 규칙** (수익 확대 기대, 기존 데이터로 counterfactual 가능)
3. **물타기 규칙** (손실 확대 위험 최대, 가장 마지막)
4. **soft_stop 재해석**은 1~3 결과를 보고 조정

### Q6. EOD/NXT 분리 청산축을 먼저 처리해야 할 운영 리스크로 볼지

**아니다.** EOD/NXT는 **빈도가 낮고**(일 1~2건) 손실 규모도 제한적이다. `entry_filter`로 불량 진입을 줄이면 EOD 청산 대상 자체가 감소한다. 다만 NXT 가능/불가능 종목 분기는 별도 룰이 아니라 `entry_filter`의 진입 시점 조건(장 마감 N분 전 진입 금지 등)으로 흡수하는 것이 구조적으로 깔끔하다.

---

## 3. 체크리스트 항목별 판정

### 이미 완료된 항목 (3건) — 판정 적정

| 항목 | 감사 판정 |
|---|---|
| `[AuditFix0421] gatekeeper fast_reuse 완화 구현증거` | **적정.** 구현증거·테스트 통과·다음 액션 연결 완료. |
| `[Governance0421] partial fill min_fill_ratio canary 승인 로그 고정` | **적정.** 승인 로그 고정 및 유지/롤백 조건 분리 완료. |
| `[AuditFix0421] 테스트 카운트 불일치 재현` | **적정.** 16 passed 재현 확인, warning은 무관. |

### 응급 조치 (2건) — 판정 적정, 보완 필요

| 항목 | 감사 판정 |
|---|---|
| `[EmergencyStop0421] fallback 즉시 중단` | **적정.** 원인귀속 정정 및 3중 차단(플래그/정책/코드) 완료. **보완**: GPT 엔진 프롬프트에 "fallback_scout/main 패턴 재생성 금지" 제약 추가 필요. |
| `[EmergencyStop0421B] fallback_scout/main 폐기` | **적정.** deprecated null-object 처리 및 reject 경로 확인. **보완**: 코드 주석에 폐기 일자·사유·감사 reference 영구 기록. |

### 미완료 항목 — 감사 판정

| 항목 | 감사 판정 |
|---|---|
| `[PlanRebase0421] 튜닝 canary/승격 판단 일시중단 선언` | **유지.** 중단 선언은 필요. 단, "일시"가 아니라 **"fallback 관련 축 영구 폐기 + 신규 축 canary 전환"**으로 문구 변경. |
| `[PlanRebase0421] 진입/보유/청산 로직표 작성` | **유지, 일정 압축.** §4 표가 70% 완성. 40분으로 단축. |
| `[PlanRebase0421] fallback 오염 코호트 재집계` | **유지, 일정 압축.** §5 정의 완료, 실행만 남음. 20분 단축. |
| `[Midday0421] 오전 체결 1차 판정 잠금` | **유지.** 오전 표본 기록은 필수. |
| `[Midday0421] 미진입 blocker 4축 오전 분포` | **유지.** 기회비용 측정 기반. |
| `[Midday0421] 장후 최종판정 후보축 1차 고정` | **유지.** |
| `[AuditResponse0421] timestamp/evidence 분리 검증` | **유지.** 감사 추적 필수. |
| `[AuditFix0421] split-entry 즉시 재평가 canary` | **제거.** split-entry 폐기로 판정 대상 소멸. |
| `[VisibleResult0421] split-entry leakage canary` | **제거.** 동일 사유. |
| `[AuditFix0421] HOLDING baseline 재계산 + D+1 확인` | **유지.** 단, HOLDING 성과판정은 D+2 이관이므로 이 항목은 baseline 재계산 기록만 남기고 판정은 04-22로 이관. |
| `AIPrompt 작업12 A/B 범위 확정` | **유지.** |
| `[VisibleResult0421] 다음 영업일 승격축 1개 고정` | **유지, 내용 변경.** 승격축이 아니라 **canary 착수축 1개 확정**으로 명칭 변경. `entry_filter`를 1순위로 권고. |
| `[PlanRebase0421] 감사인 전달용 개편 요약` | **유지.** |
| `[PlanRebase0421] 다음 튜닝포인트 1축 재선정` | **유지, 일정 당겨짐.** POSTCLOSE 15:20~15:40으로 이동. |
| `[DataAudit0421] baseline source-of-truth audit` | **유지.** |
| `[PlanSync0421] 원격 canary 보류 유지` | **유지.** A/B preflight 04-23 고정은 적정. |
| `[PlanSync0421] 에이럭스 관찰축 4분해` | **제거.** 로직표에 흡수. |
| `[VisibleResult0421] legacy shadow 1순위 축 canary` | **제거.** shadow 철회로 불필요. |
| `[AuditFix0421] legacy shadow 저표본 축 폐기/병합` | **제거.** 표본 0~2 전량 즉시 폐기. |
| `[QuantVerify0421] 정량 기대효과 검증` | **유지.** 핵심 판정 항목. |
| `[Workorder0421] 적용사항 결과검증` | **유지.** |
| `[AuditorDelivery0421] 감사인 전달용 보고서` | **유지.** |
| `[OpsVerify0421] system metric sampler coverage` | **유지.** |
| `[AuditFix0421] HOLDING 성과판정 D+2 이관` | **유지.** 기록만. |
| `범위 확정 실패 시 사유 기록` | **제거.** 상위 항목에 흡수. |
| `[PlanRebase0422] position_addition_policy 초안` | **보류.** 1순위를 `entry_filter`로 변경 권고. `position_addition_policy`는 2순위 이후. |

---

## 4. 작업지시서(workorder-0421-auditor-performance-report) 검토

### 적정 사항

- 예비본(13:00)/확정본(17:30) 분리 제공 구조: **적정.** 오전 체결 집중과 오후 미진입 데이터의 성격이 다르므로 분리 판정 후 보정하는 구조는 합리적
- 감사 정정 별도 섹션 분리: **적정.** 기존 진단 누락과 응급 차단을 명확히 분리
- `fallback_scout/main` 폐기 설계 분류: **적정.** "개선 후보"가 아닌 "실패 설계"로 명시한 것은 정확
- 결과표 지표 9개: **적정.** 핵심 지표 커버리지 충분

### 시정 사항

| 항목 | 지적 | 권고 |
|---|---|---|
| §3-8 Plan Rebase 포함 항목 | "shadow/counterfactual부터 검증" 문구가 §9에서도 반복 | shadow 관련 문구 전량 삭제, canary 원칙으로 통일 |
| §5-4 표본 부족 규칙 | "방향성 판정으로 명시하고 과잉 결론 금지"는 좋으나, **방향성 판정의 유효기간**이 없음 | "방향성 판정은 2영업일 이내 재판정 필수, 미재판정 시 자동 보류"로 보완 |
| §6-2 확정본 템플릿 | "다음 액션"에 `유지축 1개`만 있고 **rollback 발동 수치**가 없음 | rollback guard 수치(reject_rate 상한, loss_cap, N_min) 필드 추가 |

---

## 5. 서버 비교 자동 리포트 경고

stage2 체크리스트 하단의 서버 비교 결과가 4개 영역 모두 `remote_error` 상태다. safe 기준 차이가 0이라 해도, 원격 서버와의 통신 자체가 실패한 상태에서 "차이 없음"은 **"비교 불가"와 동의어**다. 이 상태를 "safe 기준 차이 없음"으로 표기하는 것은 오해의 소지가 있다.

**권고**: `remote_error` 시 결론을 "차이 없음"이 아니라 **"비교 불가 — 원격 정합성 미확인"**으로 표기. 원격 서버 복구 후 재비교 시점을 명시.

---

## 6. GPT 엔진 거버넌스 권고

이번 사고의 근본 원인은 GPT 엔진이 생성한 `fallback_scout/main` 설계가 **의도-구현 불일치 상태로 실전 투입**된 것이다. 재발 방지를 위해:

1. **AI 생성 코드의 실전 투입 전 체크게이트 신설**: AI가 생성한 진입/청산 로직은 반드시 (a) 의도 명세서와 구현의 일치 검증 (b) 단위 테스트 (c) 운영자 수동 승인을 거쳐야 한다
2. **GPT 엔진 프롬프트에 금지 패턴 목록 추가**: `fallback_scout/main` 유형의 동시 다중 leg 진입 패턴을 명시적으로 금지
3. **AI 생성 설계의 라벨링 의무화**: 모든 AI 생성 로직에 `ai_generated=True`, `design_reviewed=False/True` 태그를 붙여 감사 추적 가능하게 할 것

---

## 7. 수정권고 요약

| 번호 | 분류 | 조치 | 기한 |
|---|---|---|---|
| R-1 | **필수** | shadow/counterfactual 원칙 철회 → 전 문서에서 삭제, canary 즉시 적용 + rollback guard 수치 고정 원칙으로 교체 | 04-21 POSTCLOSE |
| R-2 | **필수** | 불필요 관찰축 6건 제거 (split-entry 2건, 에이럭스 4분해, legacy shadow 2건, 범위확정 실패 분리항목) | 04-21 POSTCLOSE |
| R-3 | **필수** | 튜닝 일정 압축 — 로직표 40분, 코호트 20분, 1축 재선정 04-21 당일, canary 설계 04-21 당일, **04-22 장 개시 시 canary 가동** | 04-21 POSTCLOSE |
| R-4 | **필수** | 다음 튜닝 1순위를 `entry_filter`로 변경 (`position_addition_policy`는 2순위 이후) | 04-21 POSTCLOSE |
| R-5 | 권고 | GPT 엔진 프롬프트에 fallback_scout/main 패턴 재생성 금지 제약 추가 | 04-22 |
| R-6 | 권고 | 서버 비교 `remote_error` 시 "비교 불가" 표기로 변경 | 04-22 |
| R-7 | 권고 | AI 생성 코드 실전 투입 전 3단계 체크게이트(의도-구현 일치 / 단위테스트 / 수동승인) 신설 | 04-23 |
| R-8 | 권고 | 방향성 판정 유효기간(2영업일) 및 자동 보류 규칙 추가 | 04-22 |

---

## 8. 결론

개편 방향(fallback 폐기, 코호트 분리, 로직 전수점검)은 **전부 타당**하다. 문제는 실행 속도다.

현재 계획은 shadow 관찰이라는 불필요한 버퍼를 두어 **최소 2~3일을 낭비**하는 구조다. fallback이 폐기된 지금, 시스템은 축소된 진입 퍼널로 기회비용을 매일 지불하고 있다. 빠르게 `entry_filter` canary를 띄워 진입 품질을 복구하는 것이 순이익 극대화의 최단 경로다.

shadow를 두지 말고, canary로 결과를 판정하고, 실패하면 당일 rollback하라. 이것이 시스템트레이더의 원칙이다.


---

## 9. Codex 반영 의견 및 문의

반영일: `2026-04-21`
반영자: Codex

### 9-1. 반영 판정

| 권고 | 반영 판정 | 조치 |
|---|---|---|
| R-1 shadow/counterfactual 원칙 철회 | 반영 | 전 문서에서 다음 1축을 `canary 즉시 적용 + 당일 rollback guard`로 수정 |
| R-2 불필요 관찰축 제거 | 반영 | split-entry 재평가/leakage, 에이럭스 별도 4분해, legacy shadow 2건, 범위확정 실패 분리항목 제거 또는 상위 항목 흡수 |
| R-3 일정 압축 | 반영 | 04-21 15:20~16:10에 1축 선정과 guard 설계 완료, 04-22 08:00~08:10 적용 판단으로 수정 |
| R-4 entry_filter 1순위 | 반영 | `entry_filter -> holding_exit -> position_addition_policy -> EOD/NXT` 순서로 재정렬 |
| R-5 GPT 금지패턴 | 후속 반영 | 04-22 `[Governance0422]` 작업으로 등록 |
| R-6 remote_error 표기 | 반영 | 기존 차이 없음 해석을 `비교 불가 - 원격 정합성 미확인`으로 수정 |
| R-7 AI 생성 코드 체크게이트 | 후속 반영 | 04-22 `[Governance0422]` 작업으로 등록 |
| R-8 방향성 판정 유효기간 | 반영 | 2영업일 이내 재판정, 미재판정 시 자동 보류 규칙 추가 |

### 9-2. 운영상 확인 필요

- `entry_filter` canary rollback guard의 baseline 연동값은 04-21 장후 `normal_only` 재집계가 끝나면 최종 확정한다.
- baseline이 부족할 경우 임시 backstop은 `reject_rate baseline -10.0%p`, `normal_only_avg_profit_rate <= -0.35%`, `soft_stop_count/completed_trades >= 35.0%`, `gatekeeper_eval_ms_p95 > 15,900ms`, `partial_fill_ratio >= baseline + 10.0%p`, fallback 신규 1건 발생 즉시 OFF로 둔다.
- `position_addition_policy`를 후순위로 내리는 것은 물타기/불타기 기대값을 폐기한다는 뜻이 아니라, 먼저 불량 진입 필터를 안정화해 추가진입 상태머신의 입력 품질을 확보한다는 의미다.
