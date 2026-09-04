# Preclose Sell Target Revival Plan

기준일: `2026-05-04 KST`

## 판정

`preclose_sell_target`는 2026-04-15 단발 legacy Markdown에서 정기 report-only 산출물 후보로 재개한다. 단, 즉시 cron/live 주문 판단으로 복구하지 않고 `canonical JSON + Markdown` 구조화 산출물부터 잠근다.

## 재개 원칙

1. 산출물의 canonical data는 `data/report/preclose_sell_target/preclose_sell_target_YYYY-MM-DD.json`이다.
2. 사람이 읽는 Markdown은 `data/report/preclose_sell_target/preclose_sell_target_YYYY-MM-DD.md`이고, 기존 루트 Markdown 경로는 호환성 용도로만 유지한다.
3. 현재 단계는 `R1_daily_report`, `policy_status=report_only`, `live_runtime_effect=false`다.
4. AI/Telegram/legacy write는 CLI 옵션으로 분리한다. 검증은 `--no-ai --no-telegram`으로 먼저 닫는다.
5. 이 리포트는 보유/오버나이트, swing trailing, ADM ladder, threshold cycle context의 입력 후보지만, 별도 acceptance 없이 live threshold mutation, bot restart, 자동 주문 제출에 쓰지 않는다.

## 구조화 계약

| 필드 | 의미 | 개선 연결 |
|---|---|---|
| `input_summary.track_a_holding_count` | 현재 보유/BUY_ORDERED 후보 수 | overnight/holding flow 검토 |
| `input_summary.track_b_swing_count` | T-1 ML + 당일 일봉 기반 swing 후보 수 | 스윙 윈도우 후보 발굴 |
| `decision_summary.sell_target_count` | AI 또는 deterministic 선정 결과 수 | 15:00 preclose 의사결정 품질 |
| `sell_targets[]` | 순위/종목/트랙/근거/리스크 | operator review, ADM prompt hint 후보 |
| `track_a_holding_candidates[]` | 보유 후보 scoring snapshot | hold vs sell_today vs overnight 사후 비교 |
| `track_b_swing_candidates[]` | 신규 swing 후보 scoring snapshot | missed upside / next-day follow-up |

## 단계별 작업계획

1. `P0 code contract`: JSON/Markdown 쌍, CLI 안전 옵션, wrapper, 단위 테스트를 고정한다.
2. `P1 dry-run`: 다음 KRX 운영일 15:00 전후 `--no-ai --no-telegram`으로 DB 후보/파일 생성/스키마를 확인한다.
3. `P2 AI/Telegram acceptance`: Gemini package/API key/응답 JSON/Telegram 수신을 분리 검증한다.
4. `P3 scheduled report`: cron 등록은 P1/P2 통과 후 별도 checklist에서만 진행한다.
5. `P4 automation consumer`: threshold/ADM/swing trailing 쪽 소비자는 `report-based-automation-traceability.md`와 날짜별 checklist owner가 닫힌 뒤 추가한다.

## 다음 owner

- `2026-05-06` checklist `PrecloseSellTargetRevival0506-Intraday`가 P1 dry-run 및 정기화 여부 판정을 소유한다.
- Project/Calendar 동기화 대상은 날짜별 checklist 항목만 소유한다.
