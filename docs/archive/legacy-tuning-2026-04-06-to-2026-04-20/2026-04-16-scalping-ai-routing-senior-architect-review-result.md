# 2026-04-16 스캘핑 AI 라우팅 작업 결과서 (시니어 아키텍트 리뷰용)

> 작성시각: 2026-04-16 08:00 KST  
> 최종수정: 2026-04-16 08:01 재기동 로그 기준 증빙/스키마/동형화 보강 반영  
> 기준 문서: `docs/scalping_ai_routing_instruction_integrated.md`  
> 적용 원칙: 금일 장시작 즉시 운영반영 (canary/shadow 라우팅 미사용)

## 0) 최종 판정

| 항목 | 판정 | 근거 |
|---|---|---|
| 메인 스캘핑 라우팅/모델/스키마 즉시 반영 | 완료 | 런타임 라우터로 메인 스캘핑 OpenAI 경로 적용, `gpt-5.4-nano` 고정 |
| 원격 스캘핑 + 조건검색 Tier1 반영 | 완료 | Gemini 스캘핑 경로를 Tier1로 변경, 조건검색 진입/청산 Tier1 유지 |
| 원격 서버 재배포 및 원격 bot 단독 기동 | 완료 | 원격 코드 반영 재확인 후 `KORSTOCKSCAN_RUNTIME_ROLE=remote`로 `bot_main.py` 단독 실행 확인 |
| 액션스키마 분리 처리 규칙 | 완료(판정 규칙 고정) | 기존 튜닝 포함 여부에 따라 후속 분리 vs plan 유지 규칙 문서화 |
| 모델별 A/B 테스트 | 분리 계획 | 금일 운영반영과 분리된 별도 시나리오로 후속 검토 |

## 0-1) 증빙 매트릭스 (보강)

| 주장 | 증빙 | 상태 |
|---|---|---|
| 메인 스캘핑 OpenAI 라우팅 ON | `logs/bot_history.log:1048` `AI 라우팅 활성화: role=main (main_scalping_openai=ON)` | 확인 |
| 메인 스캘핑 모델 `gpt-5.4-nano` 고정 | `logs/bot_history.log:1042~1043` OpenAI 엔진 FAST/DEEP/REPORT=`gpt-5.4-nano`, 고정 완료 로그 | 확인 |
| OpenAI 키 2개 로테이션 반영 | `logs/bot_history.log:1042`, `logs/bot_history.log:1047` | 확인 |
| 원격은 OpenAI 메인 라우팅 비적용(운영원칙) | `RuntimeAIEngineRouter`의 `runtime_role` 분기 (`src/engine/runtime_ai_router.py:56~72`) | 코드 확인 |
| 원격/조건검색 Gemini Tier1 경로 유지 | 조건검색 포함 런타임은 Gemini 엔진 유지 (`src/engine/runtime_ai_router.py:72~81`) | 코드 확인 |
| 설정 스냅샷(민감정보 비노출) | `OPENAI_API_KEY`, `OPENAI_API_KEY_2` 키명 존재 확인 (`data/config_prod.json:12~13`) | 확인 |

## 1) 구현 요약

1. 메인 스캘핑 경로
- `RuntimeAIEngineRouter`를 도입해 메인 런타임에서 스캘핑 분석을 OpenAI로 라우팅.
- OpenAI 스캘핑 엔진 모델을 `gpt-5.4-nano`로 고정.

2. 원격 경로
- Gemini `analyze_target`의 스캘핑 모델을 Tier1로 적용.
- 원격의 조건검색 경로는 기존 Tier1 판단 경로를 유지.

3. 스키마/호환
- OpenAI `analyze_target` 시그니처를 실운영 호출과 호환되게 확장.
- `prompt_profile`에 따라 `scalping_entry/scalping_holding/scalping_exit` 태스크 타입을 입력에 주입.

## 2) 프롬프트 입력스키마 개선 (전/후)

| 구분 | 개선 전 | 개선 후 |
|---|---|---|
| 입력 구조 | 시장/틱/호가 원문 중심 입력 | `[task_type] + 정량 피처 패킷` 중심 입력 |
| 태스크 구분 | 스캘핑 공용 문맥(`shared`) 비중 큼 | `scalping_entry / scalping_holding / scalping_exit` 명시 주입 |
| 라우팅 연계 | 프롬프트 타입과 엔진 라우팅 결합 약함 | `prompt_profile -> task_type` 매핑으로 라우팅/판단 목적 정렬 |
| 운영 목적 | 단일 포맷 재사용 | 진입/보유/청산 목적별 입력 분리로 판단 일관성 강화 |

- 참고: 기존 Gemini 경로도 `prompt_profile` 분기를 유지하며, 메인 스캘핑 OpenAI 경로는 동일한 호출 시그니처로 수용되도록 맞췄다.

### 2-0) 입력 payload 스냅샷 (민감정보 제거)

개선 전(요약): 자연어 원문 중심 (호가/틱/분봉 본문 비중 큼)

```text
[현재 상태]
- 현재가/등락률/체결강도
[최근 1분봉 흐름]
...
[실시간 호가창]
...
[최근 10틱 상세]
...
```

개선 후(실운영 포맷): `task_type` + 정량 피처 블록 + 원문 보조 블록

```text
[task_type]
scalping_entry

[정량 피처]
- curr_price
- latest_strength
- spread_krw, spread_bp
- top1_depth_ratio, top3_depth_ratio, orderbook_total_ratio
- micro_price, microprice_edge_bp
- buy_pressure_10t, net_aggressive_delta_10t
- price_change_10t_pct
- recent_5tick_seconds, prev_5tick_seconds, tick_acceleration_ratio
- same_price_buy_absorption
- large_sell_print_detected, large_buy_print_detected
- distance_from_day_high_pct, intraday_range_pct
- volume_ratio_pct
- curr_vs_micro_vwap_bp, curr_vs_ma5_bp
- micro_vwap_value, ma5_value
```

근거 코드:
- 정량 피처 추출: `src/engine/ai_engine_openai_v2.py:507~670`
- 입력 조립: `src/engine/ai_engine_openai_v2.py:329~506`
- task_type 주입: `src/engine/ai_engine_openai_v2.py:753~763`

### 2-1) 실제 프롬프트 (개선 전)

`src/engine/ai_engine.py`의 기존 스캘핑 공용 프롬프트:

```text
SCALPING_SYSTEM_PROMPT
- 페르소나: 극강 공격적 초단타(Scalping) 프랍 트레이더
- 핵심 규칙:
  1) 매수 압도율 70%+ + 틱 가속에서 BUY
  2) 속도 저하/고가부근 매도틱에서 DROP
  3) Micro-VWAP 하회/고가 줄설거지 패턴 회피
- 출력:
  {
    "action": "BUY" | "WAIT" | "DROP",
    "score": 0~100,
    "reason": "1줄 요약"
  }
```

### 2-2) 실제 프롬프트 (개선 후)

`src/engine/ai_engine_openai_v2.py`의 정량형 프롬프트 + 태스크 타입 주입:

```text
SCALPING_SYSTEM_PROMPT_V3
- 최우선 해석: [정량 피처] > [수급/위치] > [최근 틱] > [호가창]
- 핵심 BUY 조건:
  buy_pressure_10t, tick_acceleration_ratio, net_aggressive_delta,
  curr_vs_micro_vwap, large_sell_print_detected 등을 동시 점검
- 즉시 DROP 조건:
  Micro-VWAP 하회, 고가부근 대량매도틱, 가속 둔화 등
- 출력:
  {
    "action": "BUY" | "WAIT" | "DROP",
    "score": 0~100,
    "reason": "정량 피처 기반 1줄"
  }
```

운영 입력에 추가되는 태스크 타입 헤더(개선 후):

```text
[task_type]
scalping_entry | scalping_holding | scalping_exit
```

### 2-3) task_type 매핑 규칙

| prompt_profile | task_type |
|---|---|
| `watching` | `scalping_entry` |
| `holding` | `scalping_holding` |
| `exit` | `scalping_exit` |
| 기타/기본 | `scalping_shared` |

근거: `src/engine/ai_engine_openai_v2.py:753~762`

## 3) 근거 코드

- [runtime_ai_router.py](/home/ubuntu/KORStockScan/src/engine/runtime_ai_router.py)
- [kiwoom_sniper_v2.py](/home/ubuntu/KORStockScan/src/engine/kiwoom_sniper_v2.py)
- [ai_engine.py](/home/ubuntu/KORStockScan/src/engine/ai_engine.py)
- [ai_engine_openai_v2.py](/home/ubuntu/KORStockScan/src/engine/ai_engine_openai_v2.py)
- [test_ai_engine_cache.py](/home/ubuntu/KORStockScan/src/tests/test_ai_engine_cache.py)

## 4) 검증 결과

- `py_compile` 통과
- `pytest src/tests/test_ai_engine_cache.py` 통과 (`13 passed`)

### 4-1) 런타임 라우팅/모델 검증 (실로그)

- 메인 라우팅 ON: `logs/bot_history.log:1048`
- OpenAI 2키 로테이션: `logs/bot_history.log:1042`, `logs/bot_history.log:1047`
- 메인 스캘핑 모델 고정 완료: `logs/bot_history.log:1043`

### 4-2) 엔진 구조 동형화 대응표 (`ai_engine.py` ↔ `ai_engine_openai_v2.py`)

| 관점 | Gemini 엔진 (`ai_engine.py`) | OpenAI 엔진 (`ai_engine_openai_v2.py`) | 판정 |
|---|---|---|---|
| 공통 시그니처 | `analyze_target(..., strategy, program_net_qty, cache_profile, prompt_profile)` (`1182~1192`) | 동일 시그니처 (`729~739`) | 동일 |
| 진입/보유/청산 분기 입력 | `_resolve_scalping_prompt(prompt_profile)` (`732~742`) | `prompt_profile -> task_type` 매핑 (`753~762`) | 대응 |
| 경합 락 처리 | lock 경합 시 `WAIT/50` (`1227~1239`) | lock 경합 시 `WAIT/50` (`741~743`) | 동일 |
| 쿨다운 처리 | `min_interval` 미달 시 `WAIT/50` (`1272~1284`) | 동일 (`748~750`) | 동일 |
| 스캘핑 입력 조립 | `_format_market_data` (`986+`) | `_extract_scalping_features` + `_format_market_data` (`507+`, `329+`) | 강화 대응 |
| 예외 fallback | 예외 시 `WAIT/50` + reason (`1334~1345`) | 예외 시 `WAIT/50` + reason (`800~802`) | 동일 |
| 결과 메타 | `ai_prompt_type/version` 부착 (`1311~1322`) | `ai_prompt_type/version` 부착 (`794~796`) | 동일 |

### 4-3) 모델 출력 품질 지표 (기준선 + 금일 관찰)

기준선(전일 2026-04-15, `stage=ai_confirmed`/`ai_holding_review` 집계):

- ENTRY `ai_confirmed` 액션 분포: `BUY 116 / WAIT 197 / DROP 106` (총 419)
- ENTRY parse 정상률: `378 / 419 = 90.2%`
- ENTRY fallback(score=50) 비율: `41 / 419 = 9.8%`
- ENTRY score-action 일관성(규칙: BUY>=80, WAIT 50~79, DROP<50): `419 / 419 = 100%`
- HOLDING prompt 분포: `scalping_holding 1535건`
- HOLDING parse 정상률: `1180 / 1535 = 76.9%`

금일(2026-04-16) 장전 시점:

- `stage=ai_confirmed` 표본: `0건` (장중 샘플 축적 후 동일 지표 재집계 필요)

## 4-4) 배치 범위 명확화 (In/Out Scope)

| 구분 | 이번 배치 포함 | 이번 배치 제외 |
|---|---|---|
| 메인 스캘핑 | OpenAI 라우팅, `gpt-5.4-nano` 고정 | 스윙/리포트 기본 모델 체계 전면 변경 |
| 원격 스캘핑 | Gemini Tier1 경로 유지 | 원격 OpenAI 전환 |
| 조건검색 | 기존 Tier1 경로 유지(호환 유지 범위) | 조건검색 로직 구조 리팩터링 |
| 스키마 | `task_type` + 정량 피처 주입 강화 | `scalping_exit` 액션스키마 완전 분리 즉시 강행 |
| 실험 | 운영 즉시반영 | 모델별 A/B 테스트(별도 시나리오) |

## 5) 운영 체크리스트 (수정본)

- [x] 엔진 재기동 후 `AI 라우팅 활성화: role=...` 로그 확인
- [x] 메인에서 `main_scalping_openai=ON` 확인
- [x] 원격에서 `role=remote (main_scalping_openai=OFF)` 확인
- [x] 원격 bot 단독 기동 상태 확인(`bot_main.py` 1개)
- [ ] 장중 퍼널/blocker/체결품질 기준 운영 모니터링(금일 장중)
- [ ] POSTCLOSE 비교집계 및 `scalping_exit` 스키마 분리 착수 여부 1차 판정(금일 15:30~)
- [ ] PREOPEN 최종 확정(익일 08:00~08:30)

## 6) 후속

- 액션스키마 완전 분리는 기존 튜닝 포함 여부를 장후 확정 후 차기 배치에 반영.
- 모델별 A/B 테스트는 별도 시나리오로 분리 검토.

## 6-1) 실행 Plan (수정본)

1. 금일 즉시 운영반영 축
- 상태: 완료
- 범위: 메인 스캘핑 OpenAI 고정 + 원격 Tier1 + 원격 bot 단독 기동

2. 금일 장중 관찰 축
- 상태: 진행 예정
- 기준: 거래수, 퍼널 전환율, blocker 분포, full/partial fill 분리 체결품질

3. 장후 판정 축
- 상태: 진행 예정
- 시간: 2026-04-16 15:30~
- 기준: 원격 비교 결과 기반 `scalping_exit` 스키마 분리 착수 여부 1차 결정

4. 익일 장전 확정 축
- 상태: 진행 예정
- 시간: 2026-04-17 08:00~08:30
- 기준: 1차 판정 반영 최종 확정(후속 분리 이행 또는 plan 유지)

5. 모델별 A/B 테스트 축
- 상태: 분리 계획
- 기준: 금일 운영반영 축과 완전 분리해 별도 시나리오로 설계

6. `recommendation_history.nxt` 정리 착수 축
- 상태: 익일 착수 예정
- 시간: 2026-04-17 PREOPEN (08:30~09:00)
- 기준: `nxt` 대체필드/호환경로/제거순서 확정 후 구현 시작

## 7) 스키마 분리 의사결정 타임라인 및 원격 비교 기준 (아키텍트 리뷰용)

### 7-1) 결정 시점

- 1차 결정: `2026-04-16 POSTCLOSE (15:30~)`  
  오늘 운영반영 결과를 기준으로 `scalping_exit` 액션스키마 분리 착수 여부를 판정한다.
- 최종 확정: `2026-04-17 PREOPEN (08:00~08:30)`  
  1차 판정 결과를 반영해 다음 배치 범위(즉시 분리/plan 유지)를 확정한다.

### 7-2) 원격 비교 기반 판정 기준

- 퍼널 기준: `budget_pass -> submitted` 전환 및 blocker 분포
- 체결품질 기준: `full fill / partial fill` 분리 성과, `sync mismatch` 영향
- 지연 기준: `Gatekeeper / holding` 지연 지표
- 운영결과 기준: 거래수/퍼널/blocker/체결품질 우선
- 손익 기준: `COMPLETED + valid profit_rate`만 집계에 사용

### 7-3) 스키마 분리 판정 규칙 (고정)

- 기존 튜닝 범위에 `scalping_exit action schema 분리`가 명시 포함:
  후속 분리 작업으로 즉시 이행
- 기존 튜닝 범위에 명시 포함이 없음:
  금일 배치에서는 강행하지 않고 plan 검토항목으로 유지

### 7-4) 지적 방지 메모

- 본 배치는 운영반영 배치이며, 스키마 완전 분리는 근거 없는 즉시 확대가 아니라
  `장후 실운영 비교 -> 익일 장전 확정` 절차로 관리한다.
- 따라서 스키마 분리 지연은 미수행이 아니라, 원격 비교 기반의 통제된 범위 관리로 정의한다.
