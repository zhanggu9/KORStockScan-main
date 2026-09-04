# [최종 통합안 v1.1] 스켈핑 Add-Position 로직 및 연관 파이프라인 최적화

**기준 일자:** 2026-04-20  
**대상 시스템:** KORStockScan 자동매매 (Scalping 전략)  
**문서 성격:** 4개 검토의견 통합 최종안  
**개정 사유:** v1.0의 전제 중 `PYRAMID LIVE / AVG_DOWN·REVERSAL_ADD OFF` 구분을 충분히 반영하지 못한 부분 교정

---

## 0) 개정 요약 (v1.0 → v1.1)

v1.0은 "스케일인 수량 공식 교체"를 단일 P0로 이번 주 병렬 배치했다. 이 접근은 **PYRAMID(LIVE 축)의 버그픽스**와 **AVG_DOWN/REVERSAL_ADD(OFF 축)의 재오픈**을 구조적으로 혼동한 오류가 있었다. 이후 입수된 두 개의 트레이더 의견(Add-Position Axis Trader Review, Add-Position 시스템 트레이더 검토 리포트)은 동일한 방향으로 교정을 요구했고, 두 의견 간에도 완전한 합의점이 형성되었다.

**v1.1의 핵심 교정 세 가지:**

1. **LIVE 축 버그픽스와 OFF 축 재오픈을 분리.** PYRAMID 1주 플로어 패치는 단독 카나리아, AVG_DOWN/REVERSAL_ADD는 Shadow 단계부터 순차 진행.
2. **이번 주(04-20~04-24)는 코드 변경 0건 유지.** HOLDING shadow 오염 방지 및 원인 귀속 보존이 결정적 근거.
3. **다음 주(04-27~) 이후 REVERSAL_ADD Shadow 착수의 3가지 선결 조건 명문화.** 두 트레이더 의견이 수렴한 지점.

## 0-1) 수용 / 보류 / 거절

### 수용

1. `PYRAMID zero_qty`는 별도 bugfix-only Stage 1 축으로 분리한다.
2. 금주(`2026-04-20~2026-04-24`)는 코드 변경 0건을 유지한다.
3. `same_symbol_soft_stop_cooldown_shadow` 판정이 add-position 축보다 선행한다.
4. `HOLDING` 품질 안정화가 churn 해법의 1순위라는 해석을 유지한다.
5. `math.ceil` 기반 최소 1주 보장은 Stage 1 후보 공식으로 채택한다.

### 보류

1. `reversal_add_candidate 일평균 5~10건`은 readiness 참고지표로는 수용하되, 단독 절대 컷오프로 고정하지는 않는다.
2. `Stage 2 노셔널 기반 전면 공식`은 Stage 1 관찰 종료 전까지 설계 보류한다.

### 거절

1. **Stage 1을 `REVERSAL_ADD`까지 포함하는 제안은 거절한다.**
   - 이유: `REVERSAL_ADD`는 현재 OFF 축이며 shadow readiness도 아직 미닫힘 상태다.
   - 따라서 Stage 1 실주문 범위는 `SCALPING/PYRAMID zero_qty bugfix`로 한정한다.
2. **`04-27`에 `전 종목 전 전략 대상`으로 Stage 1을 여는 제안은 거절한다.**
   - 이유: 현재 관찰/근거는 스캘핑 add-position 케이스에 집중되어 있고, 단일축 canary 원칙상 범위를 먼저 좁혀야 한다.
   - 승인 시에도 `remote -> SCALPING/PYRAMID only -> main flag OFF` 순서가 맞다.
3. **금주 일정명으로 `scale-in qty v2`를 유지한 채 폭넓게 해석하는 방식은 거절한다.**
   - 이유: 이번 합의안의 실질 범위는 `PYRAMID zero_qty Stage 1`이며, `AVG_DOWN/REVERSAL_ADD` 재오픈과 섞이면 원인 귀속이 다시 흐려진다.

---

## 1) 네 개 검토의견의 합의 지점

| 쟁점 | 1차 검토 (1차 컨설팅) | 2차 검토 (통합 보고서) | 3차 검토 (Add-Position Axis) | 4차 검토 (시스템 트레이더) | v1.1 확정 |
|---|---|---|---|---|---|
| Zero Qty 버그 해결 필요성 | 동의 | 동의 | 동의 | 동의 (선결 조건 #1) | **확정** |
| 해결 공식 | 예산 기반 + 포지션 비율 + 조건부 플로어 | `max(1, int(...))` 또는 `math.ceil` | 플로어 패치 필요 (공식 미지정) | `math.ceil` 명시 | **math.ceil 채택** (§5) |
| LIVE/OFF 축 구분 | 미반영 | 미반영 | 명시적 구분 | 명시적 구분 | **반영** |
| 이번 주 코드 변경 | P0 투입 제안 | P0 투입 제안 | 0건 유지 | 0건 유지 | **0건 유지** |
| Churn 해법 우선순위 | 언급 없음 | HOLDING 프롬프트 분리 | HOLDING 품질 먼저 | HOLDING 품질이 1순위 | **HOLDING 최우선** |
| soft-stop 쿨다운 vs add-position | 언급 없음 | 언급 없음 | 쿨다운 선행 | 쿨다운 압도적 우선 | **쿨다운 선행** |
| PYRAMID vs REVERSAL_ADD | PYRAMID 먼저 | 언급 없음 | PYRAMID 먼저 | PYRAMID 무조건 먼저 | **PYRAMID 먼저** |
| Latency 블록 해소 | 언급 없음 | 주요 EV 누수원 | 언급 없음 | 언급 없음 | **독립 카나리아 유지** |

네 개의 의견이 모두 일치하는 지점(Zero Qty 해결, PYRAMID 우선, HOLDING 품질)은 이번 개정의 척추다. 나머지는 부차적 조정 사항.

---

## 2) 합의된 우선순위 (Sequencing)

```
[P0 이번 주 완료]
  1. HOLDING shadow 평가 (진행 중)
  2. split-entry leakage 관찰
  3. same_symbol_soft_stop_cooldown_shadow 판정

[P1 주말/04-27 투입]
  4. PYRAMID Zero Qty 패치 (단독 카나리아, bugfix-only)

[P2 04-27 이후 Shadow 착수 조건부]
  5. REVERSAL_ADD Shadow (선결 3조건 모두 충족 시)

[P3 차차주 이후 검토]
  6. 스케일인 수량 공식 전면 교체 (ADD_NOTIONAL_RATIO 기반)
  7. AVG_DOWN Shadow (스켈핑 철학상 장기 보류 가능)
```

이 순서의 근거는 **"모든 변경은 직전 단계의 관찰이 닫힌 뒤에만 다음 단계로 간다"** 는 단일축 카나리아 원칙이다. v1.0의 병렬 P0 배치는 이 원칙과 충돌했다.

---

## 3) REVERSAL_ADD Shadow 착수 3가지 선결 조건

4차 검토가 제안한 선결 조건을 **확정안**으로 수용한다. 다만 readiness 판정은 단일 수치가 아니라 `표본 충분성 + 관찰축 비간섭 + HOLDING/쿨다운 선행 판정`을 함께 본다.

### 조건 1 — Zero Qty 버그 해결

- **요구사항:** 고가주(1~2주 보유) 환경에서도 PYRAMID 추가매수가 최소 1주 이상 산출되도록 수량 산식 패치 완료 및 배포.
- **판정 지표:** 패치 배포 후 1영업일 이상 관찰 기간에서 `ADD_BLOCKED reason=zero_qty` 발생 0건.
- **부차 조건:** `MAX_POSITION_PCT` 위반 0건 (절대 조건).

**대표 사례: 이수페타시스(007660)**
- `2026-04-20 11:15:09` `ADD_SIGNAL type=PYRAMID reason=scalping_pyramid_ok profit=+2.68%`
- 직후 `ADD_BLOCKED reason=zero_qty deposit=8685270 curr_price=134100 buy_qty=1 add_type=PYRAMID`
- 해석: `buy_qty=1`, `ratio=0.50`에서 `int(1 * 0.5)=0`이 되어 추가매수 실패. 남은 예산은 충분했으므로 자금 부족이 아니라 템플릿 수량 공식의 구조적 문제다.
- 같은 패턴이 `11:12:51`, `11:13:15`, `11:13:38`, `11:14:10`, `11:15:09`, `11:16:41`, `11:17:09` 등 반복 발생.

### 조건 2 — HOLDING 품질 안정화

- **요구사항:** 금주 `HOLDING action schema shadow` 결과, Capture Efficiency 개선 유의미.
- **판정 지표 후보** (운영팀 선택):
  - `MISSED_UPSIDE / GOOD_EXIT` 비율이 shadow 기간 중 개선 추세.
  - `same_symbol_repeat` 발생 빈도가 shadow 모델 적용 시 축소.
  - "부분익절 → 재진입 → 손절" 3단 시퀀스의 발생 횟수 감소.
- **불통과 시 처리:** HOLDING 모델 재튜닝 1주 연장 후 재판정. REVERSAL_ADD Shadow는 추가 연기.

### 조건 3 — REVERSAL_ADD 후보 표본 충분성

- **요구사항:** `reversal_add_candidate` 로그가 주간 기준으로 의미 있는 표본을 형성해야 한다.
- **관찰 기간:** 최소 5영업일 (04-20~04-24).
- **권장 참고선:** 일평균 `5~10건`은 참고지표로 사용하되, 단독 절대 컷오프는 아님.
- **불통과 시 처리:** 표본 부족 시 Shadow 자체의 통계적 의미가 약하므로 REVERSAL_ADD 도입 자체를 재검토한다.

### 부차 조건 4 (v1.1 추가) — soft-stop 쿨다운 확정

- **요구사항:** `same_symbol_soft_stop_cooldown_shadow`가 "억제 확정" 또는 "억제 불필요"로 판정 완료.
- **근거:** add-position 성과 측정은 재진입 오염이 통제된 상태에서만 정합성을 가짐. 3차·4차 검토 모두 동일 취지 지적.

---

## 4) 금주 (2026-04-20 ~ 04-24) 운영 원칙

### 원칙 A — 코드 변경 0건

- 3차 검토 §9 및 4차 검토 결론 수용.
- **결정적 근거:** HOLDING shadow가 진행 중인 상태에서 PYRAMID 플로어 패치를 이번 주에 투입하면, PYRAMID 추가매수로 인한 포지션 변동이 HOLDING 엑싯 시퀀스를 오염시켜 shadow 평가의 통제변수가 깨짐.
- Latency 버그픽스 카나리아는 HOLDING과 독립 축이므로 이 제약에 해당하지 않음. 단 축 분리가 명확히 유지되어야 함.

### 원칙 B — 관찰 축 3개 병행

| 축 | 상태 | 금주 목표 |
|---|---|---|
| split-entry leakage | 관찰 | 판정 |
| HOLDING action schema shadow | 관찰 | Capture Efficiency 측정 완료 |
| same_symbol_soft_stop_cooldown_shadow | 관찰 | 억제 확정/불필요 판정 |

### 원칙 C — Readiness 자료 수집 (04-23 판정 입력용)

- `buy_qty` 분포 (특히 `buy_qty >= 3` 비율)
- 지난 N영업일 PYRAMID 신호 중 `zero_qty` 차단 비율
- `reversal_add_candidate` 일별 발생 건수
- `add_judgment_locked` 발생 분포

---

## 5) 스케일인 수량 공식 확정

### 5.1 Stage 1 공식 (단독 카나리아 — 04-27 이후 적용 후보)

4차 검토가 명시적으로 제안한 `math.ceil` 기반 최소 수량 보장. 코드 변경 범위를 최소화하여 bugfix-only로 프레이밍 가능하도록 설계한다.

**적용 범위 확정:**
- `SCALPING/PYRAMID`에 한해 Stage 1 후보로 검토한다.
- `REVERSAL_ADD`는 OFF 축이므로 Stage 1 실주문 범위에서 제외한다.
- `AVG_DOWN`은 현재 OFF 유지, readiness 자료만 수집한다.

```python
import math

# --- 기존 ratio 계산 유지 ---
ratio = _get_ratio(strategy, add_type, add_reason)  # 기존 로직

# --- 변경 지점: int → max(1, math.ceil) with guards ---
raw_qty = buy_qty * ratio

if add_type == "PYRAMID" and raw_qty > 0:
    template_qty = max(1, math.ceil(raw_qty))
else:
    template_qty = int(raw_qty)  # REVERSAL_ADD/AVG_DOWN 등 기존 로직 유지

# --- 캡 계산 기존 유지 ---
max_budget       = deposit * MAX_POSITION_PCT
current_value    = buy_qty * curr_price
remaining_budget = max(max_budget - current_value, 0)
cap_qty          = int((remaining_budget * 0.95) // curr_price)

# --- 남은 예산이 1주도 안 되면 1주 플로어 무효화 (캡이 우선) ---
qty = min(template_qty, cap_qty)
return qty if qty >= 1 else 0
```

**주요 변경점:**
- `SCALPING/PYRAMID`에만 `math.ceil + max(1, ...)` 적용.
- `REVERSAL_ADD/AVG_DOWN`은 현재 OFF 또는 shadow readiness 상태이므로 패치 범위에서 제외한다.
- cap_qty가 0이면 결과도 0 — MAX_POSITION_PCT 위반 불가.
- ratio 테이블 자체는 건드리지 않음 — 버그픽스 성격 보존.

### 5.2 이수스페셜티케미컬 재계산

```text
deposit = 8,678,470  curr_price = 113,400  buy_qty = 1
strategy = SCALPING  add_type = PYRAMID  ratio = 0.50

raw_qty          = 1 × 0.50 = 0.5
template_qty     = max(1, math.ceil(0.5)) = 1
remaining_budget = 1,622,294
cap_qty          = (1,622,294 × 0.95) // 113,400 = 13
qty              = min(1, 13) = 1   ← 정상 체결
```

v1.0의 노셔널 비율 공식은 이 케이스에서 6주를 산출했으나, v1.1의 math.ceil 공식은 1주만 산출. 리스크 캡(13주) 대비 훨씬 보수적이며, **초기 패치의 안정성 측면에서 오히려 적합**하다. 이후 관찰 기간을 거쳐 체결 품질이 확보되면 Stage 2로 상향 조정.

### 5.2-1 이수페타시스 반복 사례

```text
deposit = 8,685,270  curr_price = 134,100  buy_qty = 1
strategy = SCALPING  add_type = PYRAMID  ratio = 0.50

raw_qty          = 1 × 0.50 = 0.5
template_qty     = max(1, math.ceil(0.5)) = 1
max_budget       = 8,685,270 × 0.20 = 1,737,054
remaining_budget = 1,737,054 - 134,100 = 1,602,954
cap_qty          = (1,602,954 × 0.95) // 134,100 = 11
qty              = min(1, 11) = 1   ← 정상 체결 가능
```

현재 운영에서는 같은 상황에서 `template_qty = int(1 × 0.5) = 0`이므로 반복적으로 `zero_qty` 차단이 발생했다.  
즉 이수페타시스는 이수스페셜티케미컬과 동일한 구조의 **재현 샘플**이며, Stage 1 bugfix 필요성을 강화하는 근거다.

### 5.3 Stage 2 공식 (차차주 이후 검토)

v1.0 §3.1의 노셔널 비율 기반 전면 공식은 **Stage 1 카나리아가 1~2주 안정 운영된 이후** 재검토. 다음 조건이 충족되어야 이전 승격:

- Stage 1 기간 중 `zero_qty` 0건 유지.
- 추가매수 실행 당 평균 실현수익률이 기존 대비 동등 이상.
- 트레이더의 Stage 2 전환 명시적 승인.

Stage 2는 리스크 예산 기반으로 수량을 더 공격적으로 잡는 구조이므로, bugfix가 아닌 **기능 변경**으로 분류. 카나리아 축도 재할당 필요.

---

## 6) 주간 로드맵 (2026-04-20 ~ 05-01)

| 일자 | 활성 작업 | 목표 |
|---|---|---|
| **04-20 (월)** | 관찰 축 3개 가동 | split-entry / HOLDING shadow / soft-stop cooldown shadow |
| **04-21 (화)** | Raw 입력 축소 범위 A/B | Latency 해소 조기 착수 (독립 축) |
| **04-22 (수)** | HOLDING Shadow 중간 점검 | 표본 누적 확인 |
| **04-23 (목) POSTCLOSE** | **1차 판정 회의** | §3 선결 조건 충족 현황 점검, buy_qty 분포, reversal_add_candidate 건수 확인, `PYRAMID zero_qty Stage 1` 범위 확정 |
| **04-24 (금) POSTCLOSE** | **주간 통합 판정** | `PYRAMID zero_qty Stage 1` 다음 주 원격 canary 승인 또는 보류 결정 |
| **04-25~26 (주말)** | 승인 시 패치 준비 | Stage 1 공식(§5.1) 배포 준비, rollback 플랜 포함 |
| **04-27 (월)** | Stage 1 단독 카나리아 시작 | 승인 시 `remote -> SCALPING/PYRAMID only`, bugfix-only |
| **04-28~04-30** | Stage 1 관찰 | zero_qty 0건 유지 확인, 평균 실현수익률 모니터링 |
| **05-01 (금) POSTCLOSE** | **차주 Shadow 승인 판정** | §3 선결 조건 3개 재확인, REVERSAL_ADD Shadow 착수 여부 결정 |

---

## 7) v1.0 대비 철회/유지 항목 명시

### 철회 항목

| v1.0 항목 | 철회 사유 |
|---|---|
| 수량 공식 §3.1 전면 교체의 이번 주 투입 | LIVE/OFF 축 혼동. 3차·4차 검토 공통 지적. |
| `ADD_NOTIONAL_RATIO`의 AVG_DOWN/REVERSAL_ADD 값 사전 지정 | Shadow 판정 전 수치 확정 금지 원칙 위배. |
| 주간 로드맵 04-20 "scale-in qty formula v2" 투입 | Stage 1/Stage 2 분할로 대체. |
| PYRAMID/REVERSAL_ADD를 동일 공식으로 취급 | REVERSAL_ADD는 OFF 축이므로 현 시점에서 공식 대상 아님. |

### 유지 항목

| v1.0 항목 | 유지 사유 |
|---|---|
| Latency 버그픽스 카나리아 (독립 축) | add-position과 간섭 없음. 2차 검토의 +24,960원 누수 추정 여전히 유효. |
| HOLDING 프롬프트 분리 (이미 shadow 진행 중) | 4차 검토의 "Churn 1순위 해법이 HOLDING 품질"과 정합. |
| 신호단 프리체크 제안 | LIVE 축(PYRAMID)에만 한정 적용 가능. Stage 1 이후 검토. |
| 트레이더 체크리스트 (일부 재조정) | §8에 재구성. |

---

## 8) 트레이더 최종 확인 체크리스트 (v1.1)

금주 운영 관련:
- [ ] 금주 코드 변경 0건 유지 원칙에 동의 (§4 원칙 A)
- [ ] HOLDING shadow 오염 방지가 이번 주 PYRAMID 플로어 미투입의 결정적 근거임에 동의
- [ ] Latency 버그픽스 카나리아는 독립 축으로 병행 진행 가능함에 동의

04-24 판정 관련:
- [ ] Stage 1 공식 `math.ceil` 기반 (§5.1) 수용 여부 — 4차 검토 수용
- [ ] Stage 1 투입 범위는 PYRAMID/REVERSAL_ADD에 한정, AVG_DOWN은 제외
- [ ] Stage 1 관찰 기간 (최소 1주) 동안 `zero_qty` 0건을 성공 지표로 수용

차주 이후 관련:
- [ ] REVERSAL_ADD Shadow 착수 3가지 선결 조건(§3)을 공식 게이트로 운영
- [ ] `reversal_add_candidate` 일평균 5~10건을 정량 컷오프로 확정 — 4차 검토 제안
- [ ] soft-stop 쿨다운 판정이 REVERSAL_ADD Shadow의 선행 조건임에 동의 — 3차·4차 검토 공통
- [ ] Stage 2 (노셔널 비율 공식 전면 교체)는 Stage 1 안정 운영 확인 후 별도 승인 절차

장기 정책 관련:
- [ ] AVG_DOWN의 스켈핑 도입 자체를 장기 보류 또는 폐기 검토 — 4차 검토의 "Churn 해법은 물타기가 아니다" 입장 수용 여부
- [ ] `SCALPING_MAX_BUY_BUDGET_KRW`의 스케일인 반영 여부 (계좌 성장 시 종목당 절대 캡 부재 이슈)

---

## 9) 로직 플로우 (v1.1 기준)

```
[Signal Generation]
       │
       ▼
[AI Evaluation]
       │   WATCHING: 진입용 프롬프트
       │   HOLDING:  엑싯용 프롬프트 (shadow → 04-24 후 LIVE 검토)
       ▼
[Gate: budget_pass]
       │
       ▼
[Gate: latency_block]  ← Latency 버그픽스 카나리아 (독립 축)
       │
       ▼
[Gate: same_symbol_soft_stop_cooldown]  ← shadow → 04-24 후 LIVE 검토
       │
       ▼
[calc_scale_in_qty]
       │
       │   현재 (~04-24): 기존 int(buy_qty × ratio) 유지
       │   Stage 1 (04-27~): max(1, math.ceil(raw_qty)) with PYRAMID/REVERSAL_ADD guard
       │   Stage 2 (TBD):   노셔널 비율 기반 전면 교체 (별도 승인 후)
       │
       │   cap_qty = int((remaining_budget × 0.95) // curr_price)
       │   qty = min(template_qty, cap_qty)
       │
       ▼
[Order Submission]
```

---

## 10) 요약

**이번 주:** 코드 변경 0, 관찰 3축 완주.  
**04-24:** PYRAMID Zero Qty 패치(Stage 1) 차주 투입 승인 판정.  
**04-27~:** Stage 1 단독 카나리아 — zero_qty 0건, cap 위반 0건 확인.  
**05-01:** REVERSAL_ADD Shadow 착수 3조건 재확인, 조건 충족 시 Shadow 개시.  
**차차주 이후:** Stage 2 노셔널 비율 공식 별도 승인 절차.

네 개의 검토의견은 세부 수치에서 차이가 있었으나 **"LIVE 축 버그픽스 먼저 → OFF 축 Shadow는 조건부"** 라는 큰 틀에서는 완전히 일치했다. v1.1은 이 합의를 체계적으로 반영한 운영 문서이다.

---

**문서 버전:** v1.1 (2026-04-20 재개정)  
**이전 버전:** v1.0 (2026-04-20 최초)  
**다음 재검토 예정:** 2026-04-24 POSTCLOSE 판정 결과 반영 → v1.2  
**개정 반영 검토의견:**
- 1차 컨설팅 (scale-in 수량 로직 전용)
- 2차 통합 보고서 (파이프라인 전체)
- 3차 Add-Position Axis Trader Review
- 4차 Add-Position 시스템 트레이더 검토 리포트
