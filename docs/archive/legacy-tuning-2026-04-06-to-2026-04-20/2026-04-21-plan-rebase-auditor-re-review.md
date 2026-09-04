# 2026-04-21 Plan Rebase 감사인 재검토보고서

> Deprecated as active plan: 이 문서는 2차 감사 재검토 입력 기록이다.
> 현재 실행 기준은 [2026-04-21-plan-rebase-auditor-report.md](/home/ubuntu/KORStockScan/docs/archive/plan-rebase-transition-2026-04-20-to-2026-04-22/2026-04-21-plan-rebase-auditor-report.md)와 날짜별 stage2 checklist를 따른다.
> 본 문서의 잔여 시정/보완 의견은 최종 보고서에 반영된 이력으로만 읽고, 실행 계획으로 직접 사용하지 않는다.

검토일: `2026-04-21`
검토자 역할: 시스템트레이더(감사인)
검토 대상: `2026-04-21-plan-rebase-auditor-report.md` (감사인 검토 반영본)
검토 성격: GPT 엔진 수정본에 대한 2차 재검토

---

## 0. 총평

**결론: 조건부 승인 — 잔여 시정 3건 완료 시 04-22 PREOPEN canary 적용 가능**

이전 감사 권고(R-1~R-8) 반영 상태는 적정하다. shadow 철회, 불필요 축 제거, 일정 압축, entry_filter 1순위 전환이 모두 문서에 반영되었다. 다만 canary 실전 적용을 위한 **rollback guard 수치 정식 정의가 누락**되어 있어, 이 상태로 04-22 장전에 canary를 켜면 이전 fallback과 동일한 "수동 판단 의존 → 대응 지연" 패턴이 반복될 위험이 있다.

---

## 1. 이전 권고 반영 상태 점검

| 권고 | 반영 판정 | 비고 |
|---|---|---|
| R-1 shadow 철회 | **완료** | §1-5항, §6-2-5항 모두 canary + rollback guard로 교체 확인 |
| R-2 불필요 축 제거 | **완료** | §9-1에 제거/흡수 명시 |
| R-3 일정 압축 | **완료** | §9 액션 일정이 압축본으로 교체됨 |
| R-4 entry_filter 1순위 | **완료** | §7 순위 재정렬, §3-2 질문 4·5번 반영 |
| R-5 GPT 금지패턴 | **후속 등록** | 04-22 Governance 항목으로 이관, 수용 |
| R-6 remote_error 표기 | **완료** | |
| R-7 AI 생성 코드 체크게이트 | **후속 등록** | 04-22 Governance 항목으로 이관, 수용 |
| R-8 방향성 판정 유효기간 | **완료** | 2영업일 + 자동 보류 규칙 반영 |

**8건 중 6건 완료, 2건 후속 이관(수용). 이전 권고 반영은 적정.**

---

## 2. 신규 지적사항

### [시정 A] §1 6항 "AI 엔진 A/B 테스트 연기" — 연기 종료 조건 미정의

- **위치**: §1 6항 "AI 엔진 A/B 테스트는 기본 튜닝 로직 재정렬 완료 이후로 연기"
- **위험 등급**: 중(Medium)

§1에 "핵심 진입/보유/청산 로직 정렬 이후로 미룬다"고 기재했으나, **"로직 정렬 완료"의 판정 기준**이 없다. 로직표 작성만으로 완료인지, entry_filter canary 결과 확인까지인지, 아니면 전체 4축 순회 후인지 불명확하다. 이대로면 A/B 테스트가 무기한 후순위에 밀릴 수 있다.

**권고조치**: "A/B 테스트 재개 조건 = entry_filter canary 1차 판정 완료(최대 3영업일) 시점"으로 기한을 고정할 것. 3영업일 내 entry_filter 판정이 나오지 않으면 A/B 재개 여부를 별도 판정.

---

### [시정 B] §9-1 하단 rollback guard 수치 — 본문 미등재, 정식 정의 필요 (필수)

- **위치**: §9-1 하단 문의/확인 메모
- **위험 등급**: **상(High) — canary 적용 전 반드시 해결**

§9-1 하단에 `loss_cap=-0.35%`, `reject_rate=-10.0%p`, `partial_fill_ratio=baseline+10.0%p`가 "baseline 부족 시 운영 backstop"으로 기재되어 있다. 그런데 이 수치가 **본문 어디에도 정식 정의되어 있지 않다.** §6-2-5항에서 "당일 rollback guard로 검증"이라고만 하고 구체 수치를 제시하지 않았으므로, 이 하단 메모가 유일한 수치 근거다.

**구체적 문제점**:

1. `loss_cap=-0.35%`의 기준이 종목당인지 일간 합산인지 불명
2. `reject_rate=-10.0%p`의 부호가 혼동됨. 마이너스는 "baseline 대비 10%p 감소 시"를 의미하는 것 같으나, reject_rate는 증가 방향이 위험한 지표이므로 마이너스 부호를 쓰면 오독 가능
3. `partial_fill_ratio=baseline+10.0%p`도 baseline 값이 확정 전이므로 실질적으로 계산 불가

**권고조치**: rollback guard를 §6-2 또는 별도 §6-3으로 승격하여 정식 표로 작성할 것. 최소 아래 형식을 따를 것:

| Guard 지표 | 발동 조건 | 기준 | 발동 시 조치 |
|---|---|---|---|
| loss_cap | 일간 합산 실현손실 ≤ -0.35% | 당일 NAV 대비 | canary OFF + 전일 설정 복귀 |
| reject_rate | canary 적용 후 reject_rate가 baseline 대비 +10.0%p 이상 **증가** | normal_only baseline | canary OFF |
| partial_fill_ratio | canary 적용 후 partial_fill_ratio가 baseline 대비 +10.0%p 이상 **증가** | normal_only baseline | canary OFF |
| latency_p95 | canary 적용 후 gatekeeper_eval_ms_p95 > 15,900ms | 절대값 | canary OFF |
| N_min 미달 | 판정 시점 trade_count < 50 | 절대값 | 방향성 판정으로 전환, hard pass/fail 금지 |

부호 혼동 방지를 위해 모든 발동 조건에 **방향(증가/감소)**을 명시할 것.

---

### [시정 C] §8 감사인 검토 요청 5번 — 질문이 답을 전제하고 있음

- **위치**: §8 질문 5번
- **위험 등급**: 하(Low)

> "5. `entry_filter` canary의 rollback guard(`N_min`, `reject_rate`, `loss_cap`, `latency_p95`, `partial_fill_ratio`)가 충분히 보수적/공격적으로 균형 잡혔는가?"

이 질문은 guard 수치가 **본문에 정식 정의된 뒤에야** 감사인이 답할 수 있다. 현재는 §9-1 하단 메모에만 수치가 있고 본문에는 없으므로, 감사인에게 "균형 판정"을 요청하는 것은 시기상조다.

**권고조치**: 시정 B를 먼저 완료하여 guard 수치를 정식 표로 올린 뒤, 이 질문을 유지할 것.

---

## 3. 경미한 확인 사항 2건

### [확인 1] §2-2 응급 차단 표 10:55 KST 행 — 검증 증거 미기재

이전 버전에 없던 "live 스캘핑 AI 라우팅 Gemini 변경" 행이 추가되었다. 조치 자체는 적정하나, 관련 구현 위치에 `runtime_ai_router.py`, `kiwoom_sniper_v2.py`, `OPENAI_DUAL_PERSONA_ENABLED=False` 3건이 추가되었다.

이 3건에 대해 기존 응급 차단 항목들과 동일한 수준의 **검증 증거(py_compile, 정책 호출 테스트, 로그 부재 확인)**가 기록되어야 하는데, 현재는 구현 위치만 나열되어 있다.

**권고**: 장후 보고서에서 10:55 KST 변경 3건의 검증 증거를 보완 기록할 것.

### [확인 2] §3-2 변경된 감사 질문 6번 — 시정 A와 연동 필요

"AI 엔진 A/B 테스트를 기본 튜닝 로직 완료 이후로 연기하고 Gemini live 기준선을 유지하는 것이 타당한가?"

이 질문은 시정 A와 연동된다. 연기 종료 조건이 고정되면 이 질문도 더 구체적으로 바꿀 수 있다.

**권고**: 시정 A 반영 후 질문을 "entry_filter canary 1차 판정(최대 04-24) 후 A/B 재개가 타당한가?"로 구체화할 것.

---

## 4. 감사인 검토 요청(§8) 변경 질문에 대한 보완 의견

이전 리뷰에서 Q1~Q6에 답변을 제시했으므로, 이번 수정본에서 변경된 Q4~Q6에 대해서만 보완한다.

### Q4 (변경됨): "entry_filter를 1순위 canary로 두는 것이 타당한가?"

**타당하다.** 이전 의견 유지. fallback 폐기 후 진입 퍼널이 `SAFE → ALLOW_NORMAL`만 남은 상태에서 이 필터의 품질이 전체 PnL을 좌우한다.

### Q5 (변경됨): "entry_filter canary의 rollback guard가 균형 잡혔는가?"

**판정 불가 — 시정 B 선행 필요.** guard 수치가 본문에 정식 정의되지 않았다. §9-1 하단 메모 기준으로 사전 의견을 제시하면:

- `loss_cap=-0.35%`: 스캘핑 시스템 일간 변동 범위를 고려할 때 **적정 수준**이나, 종목당/합산 구분이 필수
- `reject_rate` 기준 +10.0%p: **보수적**. entry_filter 변경은 reject 증가가 의도된 효과이므로, 불량 진입 감소 목적에 비해 트리거가 너무 빠를 수 있음. **+15.0%p까지 여유를 두는 것을 검토**할 것
- `partial_fill_ratio` +10.0%p: entry_filter와 직접 연관이 약함. entry 단계 변경이 partial fill에 미치는 영향은 간접적이므로, **guard에서 제외하거나 모니터링 지표로 격하**해도 됨

### Q6 (변경됨): "position_addition_policy를 후순위로 미루면 기대값 개선이 지연되지 않는가?"

**수용 가능한 지연이다.** 불타기 기회는 진입 품질이 좋을 때만 의미가 있다. 불량 진입 종목에 불타기하면 손실이 확대되므로, entry_filter를 먼저 개선하는 것이 순서상 맞다. 다만 불타기 수익 데이터는 `scale_in_profit_expansion` 코호트로 **지금부터 축적**해 두어야 position_addition_policy 착수 시 baseline이 확보된다.

---

## 5. 수정권고 요약

| 번호 | 분류 | 조치 | 기한 |
|---|---|---|---|
| A | 중(Medium) | A/B 테스트 연기 종료 조건을 "entry_filter canary 1차 판정 완료(최대 3영업일)"로 고정 | 04-21 POSTCLOSE |
| B | **상(High)** | rollback guard 수치를 §6-3 정식 표로 승격. 발동 조건·기준·방향·조치를 명시. 부호 혼동 제거 | **04-21 POSTCLOSE (canary 적용 전 필수)** |
| C | 하(Low) | §8 Q5를 시정 B 완료 후 재질의로 변경 | 시정 B 완료 후 |
| 확인1 | 확인 | 10:55 KST Gemini 라우팅 변경 3건의 검증 증거 보완 | 04-21 장후 보고서 |
| 확인2 | 확인 | §3-2 Q6을 시정 A 반영 후 구체화 | 시정 A 완료 후 |

---

## 6. 최종 판정

| 구분 | 판정 |
|---|---|
| 이전 권고 반영 | **적정** (8/8 반영 또는 수용) |
| 문서 구조 | **적정** (개편 사유·코호트·로직표·순위 일관성 확보) |
| 잔여 시정 | **3건** (A: A/B 연기 종료조건, B: rollback guard 정식 정의, C: Q5 질문 순서) |
| 실행 가능성 | **시정 B 완료 시 04-22 PREOPEN canary 적용 가능** |

시정 B가 가장 급하다. rollback guard 수치가 정식 표로 올라가야 04-22 장전에 canary를 켤 때 자동 판정이 가능하다. 이것 없이 canary를 켜면 이전 fallback과 같은 "수동 판단 의존 → 대응 지연" 패턴이 반복된다.

---

> 감사인 서명: 시스템트레이더(감사인)
> 검토 완료 시각: 2026-04-21


---

## 7. Codex 최종 반영

반영일: `2026-04-21`
반영자: Codex

| 항목 | 반영 판정 | 조치 |
|---|---|---|
| 시정 A | 반영 | A/B 재개 조건을 `entry_filter` canary 1차 판정 완료 후로 고정하고, 최대 기한을 `2026-04-24 POSTCLOSE`로 명시 |
| 시정 B | 반영 | rollback guard를 감사보고서 §6-3 및 workorder §7 정식 표로 승격. 발동 조건, 기준, 방향, 조치를 명시 |
| 시정 C | 반영 | §6-3 guard 정의 후 §8 Q5를 재질의하는 구조로 수정 |
| 확인1 | 반영 | Gemini 라우팅 변경 검증 증거로 `py_compile`, runtime router pytest `3 passed`, 라우터 로그, 런타임 상수 확인을 기록 |
| 확인2 | 반영 | §3-2 Q6을 `2026-04-24 POSTCLOSE` A/B 재개 판정 질문으로 구체화 |

### 최종 guard 보정

- `loss_cap`: 종목별이 아니라 canary cohort 일간 합산 실현손익을 당일 스캘핑 배정 NAV 대비 평가한다. 발동 기준은 `<= -0.35%`다.
- `reject_rate`: 음수 표기를 제거하고 위험 방향을 증가로 명시한다. 감사인 보완 의견을 반영해 `normal_only baseline +15.0%p` 이상 증가 시 OFF로 둔다.
- `partial_fill_ratio`: entry_filter와 직접 연관성이 낮으므로 단독 rollback에서 제외하고 복합 guard로 격하한다. baseline 대비 `+10.0%p` 이상 증가 시 경고, 동시에 `loss_cap` 또는 `soft_stop_count/completed_trades >= 35.0%`이면 OFF다.
