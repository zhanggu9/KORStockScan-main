# 2026-04-15 매매실적 리뷰 — 추가 모니터링 및 분석 필요 포인트

> 작성시각: 2026-04-15 23:00 KST  
> 근거 문서: `2026-04-15-main-scalping-performance-pros-cons-audit-report.md`,  
> `2026-04-15-tuning-result-report-for-auditor.md`,  
> `data/report/server_comparison/server_comparison_2026-04-15.md`

---

## 0) 리뷰 요약 판정

| 축 | 당일 상태 | 익일 우선순위 |
|---|---|---|
| 손익 결과 | 플러스 마감이나 승률·기대값 모두 취약 | 중 |
| 진입 퍼널 | `budget_pass → submitted = 0%` 병목 미해소 | **최우선** |
| 레이턴시 | Gatekeeper p95 = 13,249ms (목표 5,000ms의 2.6배) | **최우선** |
| 체결 품질 | partial/full 비율 역전, sync mismatch 잔존 | 높음 |
| 집계 품질 | aggregation gate FAIL 지속 | 높음 |
| 서버 간 이상 | 메인 31건 vs 원격 44건 체결 수 괴리 | 중 |

---

## 0-1) 개별 사안 판정 및 보완사항

| 항목 | 판정 | 근거 | 보완사항 |
|---|---|---|---|
| 손익 역설 (`승률 38.7%`, `실현손익 +77,774원`) | **1회성 가능성이 큰 정상 분포 현상** | 완료거래 기준 `profit_factor=1.734`, 이익합 `183,669원`, 손실합 `-105,895원`으로 소수 대형 이익이 다수 손실을 상쇄했다. 현재 수치만으로 집계오류로 단정할 근거는 부족하다. | `profit_factor`, 상/하위 3건, 보유시간 분포를 감사 리포트 기본 항목으로 고정 |
| `budget_pass → submitted = 0%` vs 체결 31건 | **구조적 집계 정의 오류/모호성** | `entry_pipeline_flow`는 종목별 `latest stage`가 `submitted`인 경우만 `submitted_stocks`로 센다. 이미 체결/보유/청산으로 진행된 종목은 `submitted`에서 빠질 수 있어 체결 수와 직접 비교가 불가능하다. | `submitted_ever_stocks`, `filled_stocks`, `completed_trades`를 분리하고, 현재 `latest-stage submitted`는 별도 라벨로 명시 |
| Gatekeeper latency 과다 + fast reuse 0% | **구조적 성능/튜닝 이슈** | fast reuse와 gatekeeper cache 경로는 코드에 존재하지만, 양 서버 모두 `0%`이고 p95가 목표치 초과다. 단일 일회성보다는 재사용 조건 불일치 또는 캐시 활용 실패가 지속된 상태다. | `reason_codes` 상위 분포를 일별 저장하고, fast reuse 실패 이유별 카운터를 카드로 승격 |
| AI skip 비율 저조 | **구조적 튜닝 이슈** | holding skip은 `fast_sig_matches`, `age`, `price_change`, `ws_fresh`, `near_* band`를 모두 동시에 만족해야 한다. 조건이 다중 conjunctive라 실제 skip 비율이 낮아질 수밖에 없다. | skip 실패 사유 분포(`sig_changed`, `price_move`, `near_ai_exit`, `near_low_score`)를 감사 표에 추가 |
| partial fill sync mismatch 13건 | **구조적 운영 리스크** | 당일 표본에서 `preset_exit_sync_mismatch=13`이 실측됐다. 단순 1회성 장애라기보다 partial fill 이후 TP 동기화가 취약한 경로가 존재한다. | mismatch 13건의 최종 `exit_rule`과 손익영향을 코호트로 추적하고, `sync_status`별 손익표 추가 |
| 서버 간 체결 수 괴리 (31 vs 44) | **분석 필요, 즉시 오류 단정 불가** | 원격과 메인은 관찰축/설정/재기동 이력이 다르므로 체결 수 차이 자체는 오류 증거가 아니다. 다만 손익 역방향이면 설정 diff 검증은 필요하다. | `config/env diff` 자동 추출과 재기동 전/후 구간 분리 비교 추가 |
| shadow 표본 불균형 | **부분적으로 1회성 표본 부족, 부분적으로 계측 부족** | 메인 shadow 표본 부족만으로 결함으로 볼 수는 없다. 다만 `pipeline 관측`과 `실행 shadow 표본`이 따로 놀면 계측 해석이 흔들린다. | `shadow_observed`, `shadow_executed`, `shadow_diverged`를 별도 단계로 계측 |
| aggregation gate FAIL (`report_2026-04-15.json` `trades` 섹션 부재) | **구조적 계약/문서 오류** | `data/report/report_2026-04-15.json` 생성기는 원래 top-level `trades`를 만들지 않고 `performance`, `sections.top_winners/top_losers` 구조를 쓴다. 즉 “`trades` 키 부재” 자체는 런타임 결함이 아니라 gate 기준이 잘못 잡힌 것이다. | aggregation gate 기준을 `daily_report schema`와 `trade_review snapshot schema`로 분리 정의하고, 검사 대상을 명시적으로 교체 |
| 시간대별 집계 불일치 | **구조적 리포트 계약 불일치** | 비교 리포트는 `since=09:00:00` 필터, 종합 리포트는 일자 전체 기준이라 숫자가 달라지는 것이 정상이다. 현재 문서가 이 차이를 명시하지 않아 해석 혼선을 만든다. | 모든 리포트 헤더에 `coverage: full-day / since-filtered / latest-snapshot` 표기 추가 |
| 메인/원격 holding 이벤트 수치 일부 | **1회성 문서 노후화** | followup 문서의 `holding_events=492/656` 계열 수치는 로그패치 이전 수치다. 현재 재집계 기준 메인은 `5,403`, 원격은 `4,265`다. | followup과 감사 문서의 기준시각/재집계 여부를 같은 헤더 규칙으로 통일 |

메모:
- `trade_review_2026-04-15.json` 스냅샷은 15:45 저장본이라 여전히 패치 전 로그 경로를 가리킨다.
- 따라서 `aggregation`과 `holding_events` 관련 일부 지적은 “실제 엔진 오류”와 “구형 스냅샷/잘못된 gate 계약”이 섞여 있다.

---

## 1) 손익 구조 — 승률과 실현손익의 역설 분석 필요

**현상**: 승률 38.7%(12승/19패)임에도 실현손익 +77,774원 플러스 마감.

**문제**: 합산 플러스가 개별 거래 기대값(-0.16%)과 반대 방향이다.  
이는 두 가지 중 하나를 의미한다:

1. **소수 대형 이익 거래가 다수 소형 손실을 상쇄** — 손절/수익 비율(profit factor)이 우연히 양수
2. **특정 체결 구조(partial fill 과다)가 집계를 왜곡** — 실제 기대값이 보고치보다 나쁠 가능성

### 추가 분석 포인트

- [ ] **profit factor 계산**: 총 이익금 / 총 손실금 — 1.0 미만이면 구조적 취약
- [ ] **이익 상위 3건 + 손실 상위 3건 개별 검토**: 이상치(outlier) 여부 확인
- [ ] **partial fill 건과 full fill 건의 손익률 분포 분리**: `partial_fill=53, full_fill=27` 혼재 시 건별 비교가 의미 있는지 검증
- [ ] **당일 장세(변동성/방향성) 보정**: 시장 방향 덕분에 손절이 얕았을 가능성 배제 필요

---

## 2) 진입 퍼널 병목 — `budget_pass → submitted = 0%`의 구조적 의미

**현상**: `tracked_stocks=168`, `submitted_stocks=2`, `expired_armed_total=374`.  
그런데 실제 체결은 31건이 존재. 전환율 0%와 체결 31건이 양립한다.

**문제**: 이 지표가 정말 0%라면 31건 체결이 어디서 왔는지 설명이 되지 않는다.  
→ 지표 집계 기준 또는 시간 범위 불일치 가능성.

### 추가 모니터링 포인트

- [ ] **`budget_pass_no_submit` 로그 이벤트 실제 발생 건수 확인**: 집계 미반영인지, 실제로 0건인지 구분
- [ ] **`submitted_stocks` 집계 범위**: `09:00:00 since` 기준인 비교 리포트(3건)와 전체 집계(2건)가 불일치 → 시간대 필터 정합성 점검
- [ ] **`budget_pass` → `submitted` 전환을 막는 직접 원인 4축 분리**:
  1. 쿨다운 타이머 발동 비율
  2. 호가 스프레드 가드 차단 비율
  3. 주문가드(중복주문 방지) 차단 비율
  4. 잔고/증거금 부족 차단 비율
- [ ] **`entry_armed_expired_after_wait` 88.8%(332/374)**: after_wait 편중의 원인이 쿨다운인지 호가 조건인지 샘플 5건 이상 수작업 추적

---

## 3) Gatekeeper Latency — 목표 대비 2.6배 초과 지속

**현상**:
- 메인: `gatekeeper_eval_ms_avg=10,508ms`, `p95=13,249ms`
- 원격: `gatekeeper_eval_ms_avg=10,658ms`, `p95=12,876ms`
- **목표**: `re-enable ≤ 5,000ms / preferred < 1,200ms`
- **현재**: 양 서버 모두 p95가 목표의 2.5~2.6배

**문제**: Gatekeeper fast reuse 비율이 양 서버 모두 0.0% (목표 15~55%).  
fast reuse가 전혀 작동하지 않는다는 것은 매번 full AI 호출이 발생한다는 의미.

### 추가 모니터링 포인트

- [ ] **fast reuse 0%의 원인 규명**:
  - `gatekeeper_action_age_p95 = 1,484s(메인) / 1,310s(원격)` — 재사용 가능 캐시가 너무 오래된 건인지, 아니면 캐시 키 불일치인지
  - 캐시 키로 사용되는 `market_signature` 또는 `stock fingerprint`가 매 평가마다 변경되는지 확인
- [ ] **Gatekeeper AI cache hit ratio = 0.0%**: AI 호출 결과 캐싱이 전혀 활성화되지 않음. 캐시 TTL 설정값 확인
- [ ] **Gatekeeper 평가 횟수 63~74회 대비 bypass_evaluation_samples 63~75회**: 사실상 100% bypass 평가. bypass가 full eval을 의미하는지 정의 재확인 필요
- [ ] **holding_review_ms_avg = 6,312ms(메인)**: AI skip 비율 6.5%인데 review 평균이 6초. skip이 거의 안 된다는 뜻 — skip 조건 임계값이 너무 보수적인지 점검

---

## 4) AI Skip 비율 저조 — 목표 20~60% 대비 6.5% / 2.4%

**현상**:
- 메인 `holding_skip_ratio=6.5%`, 원격 `2.4%`
- 목표: `20% ~ 60%`

**문제**: skip이 없으면 매 holding tick마다 AI를 호출 → latency 악화의 직접 원인.  
반면 skip이 너무 많으면 신호 지연 위험.

### 추가 분석 포인트

- [ ] **skip 조건(`holding_skip_ws_age_p95 = 0.55s / 0.48s`)**: WS 데이터 신선도 기준(1.5s)보다 훨씬 낮은데 skip이 발생하지 않는 이유 확인
  - skip 임계값이 WS age 외에 추가 조건(AI score 변화량, holding duration 등)이 있는지 점검
- [ ] **메인 vs 원격 skip 비율 차이(6.5% vs 2.4%)**: 원격이 더 적극적으로 체결하지만 skip은 더 적음 → 원격의 holding 모드 진입 조건이 다른지 확인

---

## 5) Partial Fill sync mismatch — 체결품질 병목 추적

**현상**: `full_fill=27`, `partial_fill=53`, `preset_exit_sync_ok/mismatch=40/13`.  
mismatch 13건 / 전체 40+13=53건 → mismatch율 **24.5%**.

**문제**: partial fill 발생 후 preset exit 주문 동기화가 1/4에서 실패. 이는 preset TP가 잘못된 수량으로 등록될 위험.

### 추가 모니터링 포인트

- [ ] **mismatch 13건의 실제 결과 추적**: 해당 거래의 최종 exit_rule은 `preset_tp`인지, `manual_exit`인지, `hard_stop`인지 분류
- [ ] **partial fill 중 `min_fill_ratio` 미달로 취소된 건 수**: 체결 취소 후 재진입 시도 여부 추적
- [ ] **sync mismatch → hard_stop 전환 경로 존재 여부**: mismatch가 손실 확대로 이어지는 케이스 선별 필요
- [ ] **원격 서버 partial fill 표본**: 원격에서 동일 지표가 어떻게 나오는지 비교 미수행 (보수 해석 유지 중) → 익일 원격 집계 필요

---

## 6) 서버 간 체결 수 괴리 — 메인 31건 vs 원격 44건

**현상**: 동일 전략, 동일 종목풀인데 원격이 42% 더 많이 체결.  
원격 실현손익 `-14,618원` vs 메인 `+77,774원`.

**문제**: 체결 수가 많은 쪽이 손실이라는 것은 진입 기준이 완화될수록 손익이 나빠진다는 신호일 수 있음.

### 추가 분석 포인트

- [ ] **서버 간 파라미터 차이 목록화**: 어느 파라미터가 원격의 체결을 더 많이 허용하는지 diff 확인
- [ ] **원격 2건 미종료 포지션의 현재 PnL**: `open_trades=2` — 익일 장전에 청산/유지 판단 필요
- [ ] **원격 `holding_events=656` vs 메인 `492`**: 원격이 64 이벤트 더 많음에도 holding_skip_ratio가 낮음(2.4%) — 보유 중 모니터링 비용 과다 발생
- [ ] **당일 재기동 영향 구간 격리**: 원격은 15:30 치명오류 후 재기동. 재기동 전/후 체결 패턴이 다른지 시간대별 분리

---

## 7) Shadow Probe 표본 불균형 — 메인 1건 vs 원격 22건

**현상**: `watching_shared_prompt_shadow` 메인 11건(pipeline), 실제 shadow 작동 표본 1건.  
원격: pipeline 8건, shadow 표본 22건.

**문제**: 메인의 shadow 표본이 너무 적어 `action_diverged` 패턴 분석이 불가.  
원격 22건 중 `diverged=6`(27.3%) — 이 diverge 방향이 수익에 도움이 되는지 방향성 검증 필요.

### 추가 모니터링 포인트

- [ ] **원격 diverged 6건의 내용 분류**: shadow가 `BUY`를 추천했는데 main이 거부한 건인지, 반대인지 방향 분류
- [ ] **diverge 케이스의 사후 주가 흐름**: 해당 종목의 diverge 결정 이후 10분/30분 수익률 추적
- [ ] **메인 shadow 표본 확대 방안**: `watching_shared_prompt_shadow`가 11건 관찰됐는데 왜 shadow 실행은 1건인지 전환 조건 점검

---

## 8) Aggregation Quality Gate FAIL — 집계 파이프라인 복구

**현상**: `report_2026-04-15.json`에 `trades` 섹션 부재. 양 서버 공통.  
→ 자동 감사 파이프라인에서 손익 결론을 단독 근거로 사용 불가.

**위험**: 이 상태가 지속되면 Pros/Cons 리포트의 핵심 수치(승률, 평균손익률)를 자동 산출할 수 없어 수작업 재집계에 의존하게 됨.

### 추가 분석 포인트

- [ ] **`trades` 섹션 미생성 원인 규명**: `build_trade_review_report()` 실행 시 `trades` key가 빠지는 코드 경로 추적
- [ ] **재현 조건 격리**: 재기동 전/후, DB 세션 만료 후에만 발생하는지 확인
- [ ] **aggregation gate 통과 기준 문서화**: 어떤 조건을 만족해야 gate를 통과하는지 명시적 기준 부재

---

## 9) 시간대별 집계 불일치 — 데이터 비교 신뢰도

**현상**: 서버 비교 리포트(`since=09:00:00`)와 종합 리포트 수치가 다름.

| 지표 | 종합 리포트 | 비교 리포트(09:00~) |
|---|---|---|
| tracked_stocks(메인) | 168 | 142 |
| submitted_stocks(메인) | 2 | 3 |
| total_trades(메인) | 31 | 25 |

**문제**: 어떤 수치를 기준으로 해석해야 하는지 명확하지 않음. 재기동 시각 이전 거래가 포함/제외 방식이 다를 수 있음.

### 추가 모니터링 포인트

- [ ] **시간 범위 기준 표준화**: 모든 집계 리포트의 `since` 기준을 통일하거나, 각 리포트의 커버리지를 헤더에 명시
- [ ] **재기동 시각 기록 + 구간 분리**: 재기동 전/후를 명시적으로 분리한 서브집계 필요

---

## 10) 익일 모니터링 우선순위 요약

| 우선순위 | 항목 | 담당 액션 | 기준 슬롯 |
|---|---|---|---|
| P0 | `budget_pass → submitted` 원인 4축 분해 로그 추가 | 코드/로그 보강 | PREOPEN |
| P0 | Gatekeeper fast reuse 0% 원인 규명 (캐시 키 점검) | 로그 분석 | PREOPEN |
| P1 | aggregation quality gate `trades` 섹션 부재 원인 추적 | 코드 분석 | PREOPEN |
| P1 | profit factor 산출 (총이익/총손실) | 수작업 집계 | PREOPEN |
| P1 | partial fill mismatch 13건 → 실제 exit_rule 분류 | 로그 추적 | POSTCLOSE |
| P2 | 원격 shadow diverged 6건 방향성 검증 | 로그 분석 | INTRADAY |
| P2 | 원격 미종료 2건 포지션 확인 및 처리 | 운영 | 장전 즉시 |
| P2 | AI skip 조건 임계값 재점검 (6.5% vs 목표 20~60%) | 파라미터 분석 | PREOPEN |
| P3 | 서버 간 파라미터 diff 목록화 | 문서 | POSTCLOSE |
| P3 | 시간 범위 기준 표준화 (since 기준 통일) | 문서/코드 | POSTCLOSE |
