# 시스템 운영자 전달용 최종 감사의견서
> 작성일: 2026-04-15  
> 대상: 시스템 운영자  
> 주제: 스캘핑 WATCHING/HOLDING 프롬프트 최종 감사의견 및 실행 일정

---

## 1. 감사 범위 및 작성 기준

본 의견서는 아래 세 문서를 함께 반영해 작성한 최종 운영자용 감사의견서다.

- `2026-04-15 스캘핑 프롬프트 작업 감사표`
- `2026-04-15 스캘핑 프롬프트 감사인 검토 답변`
- `2026-04-15 스캘핑 프롬프트 감사의견 충돌항목 재검토 및 최종 감사의견서 작성 요청`

목적은 아래 3가지다.

1. 현재 WATCHING/HOLDING 프롬프트에서 **즉시 수정할 항목**을 확정한다.
2. **canary 후 판단할 항목**을 고정한다.
3. 시스템 운영자가 바로 집행할 수 있도록 **개별 작업별 권고 기한**을 확정 날짜로 제시한다.

---

## 2. 최종 총평

현재 프롬프트 구조는 **방향 자체는 맞다.**  
코드 경로도 WATCHING/HOLDING 분리 착수 완료 상태이며, `WATCHING shared prompt shadow`, `FORCE_EXIT` 제한형 MVP, 감사값 3종 투입이 이미 `develop` 기준으로 진행 중이다.

다만 프롬프트 문구 수준에서 즉시 손봐야 할 항목이 분명히 존재한다.

### 핵심 판정
- WATCHING의 `애매하면 WAIT`는 즉시 수정 대상이다.
- HOLDING의 임시 구조 노출 문구는 즉시 제거 대상이다.
- HOLDING의 `BUY/WAIT` 의미 분리는 즉시 반영해야 한다.
- HOLDING의 추상 리스크 문구는 정량 힌트와 연결해야 한다.
- WATCHING score band 조정은 본서버 즉시 반영이 아니라 canary 대상이다.
- HOLDING 최종 action schema 전환도 canary 대상이다.
- `리스크 매니저` 페르소나 문구는 즉시 수정하되, EV 개선의 핵심 레버가 아니라 보조 항목으로 본다.

---

## 3. 즉시 수정 항목

아래 항목은 **문구 수정** 수준이며, 현재 단계에서 canary를 기다리지 않고 `develop`에 즉시 반영하는 것이 맞다.

| 번호 | 항목 | 위치 | 최종 권고 수정안 | 우선순위 | 권고 기한 |
|---|---|---|---|---|---|
| 1 | WATCHING `애매하면 WAIT` 축소 | WATCHING 프롬프트 | `애매하면 WAIT` → `돌파 근거가 명확하지 않을 때만 WAIT. 약한 신호도 즉시 진입 기대값이 양수면 BUY를 우선한다.` | 핵심 | **2026-04-15 23:00 KST** |
| 2 | 기계 게이트 재의심 금지 문구 보완 | WATCHING 프롬프트 | `이미 통과한 기계 게이트(유동성/갭/모멘텀)는 재검증하지 않는다. 단, 체결 품질 급악화 또는 진입 시점의 VWAP 대비 위치 리스크는 예외 DROP 사유로 반영한다.` | 핵심 | **2026-04-15 23:00 KST** |
| 3 | HOLDING 임시 구조 노출 제거 | HOLDING 프롬프트 | `청산 action schema가 아직 분리되지 않았으므로...` 문장 삭제 후 `DROP은 이 맥락에서 즉시 청산 신호다.`로 교체 | 핵심 | **2026-04-15 23:00 KST** |
| 4 | HOLDING `BUY/WAIT` 의미 분리 | HOLDING 프롬프트 | `BUY=모멘텀 재가속, WAIT=유지 중이나 재가속 미확인, DROP=즉시 청산`으로 의미 분리 | 핵심 | **2026-04-15 23:00 KST** |
| 5 | HOLDING 추상 리스크 문구 정량 힌트 연결 | HOLDING 프롬프트 | `모멘텀 붕괴 / 되밀림 심화 / 하방 리스크 확대`를 틱 속도, 매수 압도율, 고점 대비 낙폭, 대량 매도틱, VWAP 이탈 같은 수치 힌트로 교체 | 핵심 | **2026-04-15 23:00 KST** |
| 6 | HOLDING 페르소나 문구 수정 | HOLDING 프롬프트 | `초단타 보유 포지션 리스크 매니저` → `초단타 트레이더. 지금 들고 있는 포지션의 기대값을 극대화하는 것이 목표다.` | 보조 | **2026-04-15 23:00 KST** |

---

## 4. canary 후 판단 항목

아래 항목은 현재 단계에서 즉시 본서버 반영하지 말고, 반드시 `develop`/shadow/canary 경로에서 먼저 판단해야 한다.

| 번호 | 항목 | 현재 최종 권고 | 필요한 관측지표 | 권고 기한 |
|---|---|---|---|---|
| 1 | WATCHING score band (`80/50` vs `75/40`) | 본서버 즉시 변경 금지, canary 전용 | `ai_score` 분포, `entry_funnel_delta`, `action_diverged`, WAIT 비중, missed-winner 변화 | **2026-04-17 18:00 KST**까지 canary 설계 확정 / **2026-04-18 09:00 KST** 적용 |
| 2 | WATCHING `reason` 구조화 확장 | 1줄 유지, 구조화 포맷은 canary 후 판단 | `parse_ok`, `reason` 길이, 사후복기 품질, token 증가량 | **2026-04-17 18:00 KST**까지 포맷안 확정 / **2026-04-18 09:00 KST** 적용 |
| 3 | HOLDING 최종 action schema | 현 단계는 `BUY/WAIT/DROP` 의미 정리만 반영, 최종 전환은 canary 후 판단 | `holding_ai_action` 분포, `override_triggered`, `FORCE_EXIT` 오발동률, trailing 연계성 | **2026-04-19 18:00 KST** 판정 |
| 4 | HOLDING에 `WATCH` action 도입 여부 | 현 단계에서는 **도입하지 않음**. `HOLD/SELL/FORCE_EXIT` 3분기안과 비교 검토 | action 분산도, override 복잡도, trailing 로직 영향 | **2026-04-19 18:00 KST** 판정 |
| 5 | HOLDING reason 구조화 | 수치 블록형 reason 도입은 canary 전용 | `parse_ok`, `response_latency_ms`, 사후분석 유효성 | **2026-04-18 18:00 KST** 결과 정리 |

---

## 5. 유지 가능 항목

아래 항목은 현 단계에서 그대로 유지하는 것이 맞다.

| 항목 | 유지 판단 | 이유 |
|---|---|---|
| WATCHING `BUY/WAIT/DROP` 3분기 구조 | 유지 | 전용 schema 전환 전까지는 가장 단순하고 운영 안정적 |
| JSON-only 출력 | 유지 | parse 안정성 핵심 |
| `WATCHING shared prompt shadow`는 shadow-only | 유지 | 실주문 비연결 원칙이 타당 |
| `main` 선반영 금지 원칙 | 유지 | `develop` 선행 후 장후 결과로만 승격 판단하는 원칙이 맞음 |
| `FORCE_EXIT` 제한형 MVP 범위 | 유지 | 일반 HOLDING 한정, 일반 SELL 로그 우선 유지가 적절 |
| 작업 9 helper 추출 분리 원칙 | 유지 | 공통 feature helper 추출 후 이식 방향 유지 |

---

## 6. 충돌항목에 대한 최종 운영 판단

충돌항목은 아래와 같이 운영자 기준 최종 판단을 확정한다.

### 6-1. `이미 통과한 기계 게이트는 다시 의심하지 말고`
**최종 판단:** 원칙 유지 + 예외 범위 명시

- 기계 게이트 재검증 금지 원칙은 유지
- 다만 `체결 품질 급악화`, `진입 시점의 VWAP 대비 위치 리스크`는 예외 DROP 사유로 명시

즉, **원형 유지도 아니고 삭제도 아니다. 보완 문구로 확정한다.**

---

### 6-2. HOLDING 최종 action schema에 `WATCH` 포함 여부
**최종 판단:** 현 단계 도입 보류

- 현재 단계는 `WATCH`를 도입하지 않는다.
- 이유: action 4분기 구조는 override 복잡도를 증가시킨다.
- 중립 상태는 현 단계에서 score band로 처리한다.
- `WATCH` 도입 여부는 **2026-04-19 18:00 KST**에 재판정한다.

---

### 6-3. `애매하면 WAIT`의 원인 해석
**최종 판단:** `핵심 기여 요인`으로 기술

- 이 문구는 WAIT 편향을 구조적으로 강화하는 문구다.
- 그러나 EV 누수의 **직접 주원인**으로 단정하지 않는다.
- 운영 병목의 1차 축은 `latency_block`, `blocked_strength_momentum`이다.
- 따라서 감사의견서 표현은 아래로 고정한다.

> `애매하면 WAIT`는 EV 누수의 직접 주원인이라기보다, WAIT 편향을 강화하는 핵심 기여 요인이다.

---

### 6-4. HOLDING `리스크 매니저` 페르소나
**최종 판단:** 즉시 수정 / 보조 항목

- 문구 변경은 즉시 수행한다.
- 다만 EV 개선의 핵심 레버로 보지 않는다.
- action schema 정비와 정량 트리거 연결이 더 상위 우선순위다.

---

## 7. 권장 action schema 및 score band

### 7-1. WATCHING
현 단계 권장안:

- Action: `BUY / WAIT / DROP`
- score band:
  - `80~100` 현행 유지 상태로 canary 전까지 유지
  - canary 비교안: `75~100 BUY / 40~74 WAIT / 0~39 DROP`

### 7-2. HOLDING
현 단계 권장안:

- Action 해석: `BUY / WAIT / DROP` 유지
- 의미 재정의:
  - `BUY`: 모멘텀 재가속, 보유 우호
  - `WAIT`: 유지 중이나 재가속 미확인
  - `DROP`: 즉시 청산

최종 목표안:

- `HOLD / SELL / FORCE_EXIT`
- `WATCH`는 현 단계 도입하지 않음

### 7-3. PRESET_TP
권장안 유지:

- `EXTEND / EXIT`

---

## 8. 개별 작업 권고 일정

아래 일정은 운영자가 바로 집행 가능한 **확정 일정**으로 제시한다.

| 날짜 | 작업 | 산출물 | 운영 지시 |
|---|---|---|---|
| **2026-04-15 23:00 KST** | 즉시 수정 6항목 반영 | 수정된 WATCHING/HOLDING 프롬프트 본문, 변경 diff | `develop`에만 반영, `main` 반영 금지 |
| **2026-04-16 12:00 KST** | 문구 수정 반영 여부 재확인 | 수정 적용 체크리스트, prompt version 갱신 로그 | 운영자 확인 완료 |
| **2026-04-16 18:00 KST** | 작업 5/8/10 장후 점검 | `action_diverged`, `entry_funnel_delta`, 감사값 입력 표본, `FORCE_EXIT` 입력 정리 | 장후 점검 메모 작성 |
| **2026-04-17 18:00 KST** | WATCHING score band canary 설계 확정 | score band canary 사양서, reason 구조화 포맷안, 비교 지표표 | canary write scope 고정 |
| **2026-04-18 09:00 KST** | score band / reason 구조화 canary 적용 | canary env 반영, 변경 로그 | `develop`/shadow 전용 적용 |
| **2026-04-18 18:00 KST** | 작업 9 helper 착수 및 HOLDING reason 구조 결과 정리 | helper 착수 커밋, HOLDING reason 결과 메모 | helper 작업 계속 진행 |
| **2026-04-19 18:00 KST** | HOLDING hybrid 1차 평가 및 action schema 판정 | `FORCE_EXIT` 제한형 MVP 평가표, `WATCH` 도입 여부 판정표 | HOLDING 최종 schema 운영안 확정 |
| **2026-04-20 18:00 KST** | 본서버 `main` 승격 여부 최종 판정 | 항목별 승격/보류 판정서 | 운영자 최종 승인 또는 보류 |

---

## 9. 운영자 최종 지시사항

### 즉시 집행
- 2026-04-15 23:00 KST까지 문구 수정 6항목을 `develop`에 반영한다.
- 반영 직후 prompt version을 갱신하고 변경 diff를 기록한다.

### 반드시 보류
- WATCHING score band 본서버 즉시 변경 금지
- HOLDING 최종 action schema 즉시 전환 금지
- `WATCH` action 즉시 도입 금지
- `main` 선반영 금지

### 운영 우선순위
1. 문구 수정 6항목
2. 장후 점검 및 shadow 비교
3. score band / reason canary
4. HOLDING action schema 판정
5. `main` 승격 여부 최종 결정

---

## 10. 최종 감사 의견 종합

현재 프롬프트는 구조 개선이 이미 착수된 상태이며, 방향성은 적절하다.  
다만 WATCHING의 WAIT 편향, HOLDING의 임시 구조 노출, BUY/WAIT 의미 중복, 추상 리스크 문구는 즉시 수정 가능한 결함이다.

반면 score band 조정, reason 구조화 확장, HOLDING 최종 action schema 전환은 본서버 즉시 변경 대상이 아니라 canary 후 판단 대상이다.

따라서 운영자는 아래 원칙으로 집행하는 것이 맞다.

> **문구 결함은 2026-04-15에 즉시 수정하고, 판단 기준 변경은 2026-04-18 canary 후 2026-04-19에 판정하며, 본서버 승격은 2026-04-20에 최종 결정한다.**

이상과 같이 최종 감사의견을 제시한다.
