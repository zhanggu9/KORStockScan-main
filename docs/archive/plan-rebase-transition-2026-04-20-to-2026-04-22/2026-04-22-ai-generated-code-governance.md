# 2026-04-22 AI Generated Code Governance

## 목적

- GPT/AI 생성 코드가 실전 스캘핑 기대값을 훼손하지 않도록 금지 패턴과 체크게이트를 문서화한다.
- 신규 실험은 shadow 없이, 필요 시 canary 1축만 허용한다.

## 금지 패턴

- `fallback_scout/main` 동시 다중 leg 생성 금지.
- `fallback_single` 또는 latency fallback을 split-entry처럼 재해석하는 패턴 금지.
- `COMPLETED + valid profit_rate`가 아닌 NULL, 미완료, fallback 정규화 값을 손익 기준으로 사용하는 것 금지.
- full fill과 partial fill을 동일 표본으로 합산해 성과를 판정하는 것 금지.
- `entry_filter_quality`와 `buy_recovery_canary`를 같은 canary 축으로 혼용하는 것 금지.
- 문서상 shadow 금지 항목을 코드에서 shadow-only로 우회 구현하는 것 금지.

## 체크게이트

1. 의도-구현 일치: 변경 목적, 적용 축, rollback guard가 문서/코드/로그에서 같은 이름으로 보여야 한다.
2. 단위 테스트: 신규 분기, 이벤트, 리포트 집계는 최소 1개 이상의 테스트 또는 재현 가능한 검증 명령을 남긴다.
3. 운영자 수동승인: 실주문 변경은 canary 1축만 허용하고, 동시 다축 변경은 금지한다.
4. 데이터 기준: 손익은 `COMPLETED + valid profit_rate`, 비교 리포트는 거래수/퍼널/blocker/체결 품질 우선으로 판정한다.
5. 라벨링: AI 생성 변경은 PR/작업문서에 `ai_generated`, 설계 검토가 끝난 변경은 `design_reviewed`로 구분한다.
6. 롤백: `loss_cap`, `reject_rate`, `latency_p95`, `partial_fill_ratio`, `fallback_regression`, `buy_drought_persist` 중 하나라도 발동하면 canary OFF를 우선한다.

## 2026-04-22 적용

- 대상: `[Governance0422] GPT 엔진 금지패턴 및 AI 생성 코드 체크게이트 문서화`.
- 판정: 문서화 완료. 04-22 POSTCLOSE에는 실제 변경/PR/운영 로그가 위 체크게이트를 위반하지 않았는지만 재확인한다.
