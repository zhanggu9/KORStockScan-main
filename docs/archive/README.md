# Docs Archive

아카이브는 현재 Plan Rebase 의사결정 원본이 아닌 문서를 감사 추적성과 과거 판단 근거 보존 목적으로 유지하는 영역이다.

현재 작업은 루트 `docs/`의 Plan Rebase, prompt, 날짜별 checklist, 최신 audit/report 문서를 먼저 본다. 아카이브 문서는 과거 배경, 이전 감사 의견, 완료된 workorder, setup/runbook 참고용으로만 사용한다.

## 디렉터리

- `legacy-tuning-2026-04-06-to-2026-04-20/`: Plan Rebase 이전의 dated tuning, audit, remote 비교, 실험 문서.
- `plan-rebase-transition-2026-04-20-to-2026-04-22/`: Plan Rebase 전환기의 감사, 운영자 응답, 성과 보고, AI generated code governance 증적.
- `legacy-workorders/`: 완료되었거나 새 workorder로 대체된 과거 workorder.
- `reference-and-runbooks/`: 현재 루트 판단 원본은 아니지만 재참조 가능성이 있는 setup, runbook, API note, 일반 참조 문서.

## 이동 기준

- 현재 또는 미래 checklist 작업항목을 직접 소유하는 문서는 루트에 둔다.
- Plan Rebase, prompt, report/threshold 운영 기준처럼 반복 참조되는 문서는 루트에 둔다.
- 현재 문서에서 링크만 필요한 과거 증적은 아카이브로 이동하고 링크를 새 위치로 보정한다.
- 과거 workorder라도 Plan Rebase, 날짜별 checklist, acceptance spec, audit/build report가 루트 절대경로로 직접 참조하면 링크 보정 없이 이동하지 않는다.
- parser가 직접 참조하는 고정 입력 문서는 코드 변경 없이 이동하지 않는다.

## 이동 이력

- `archive-manifest-2026-04-21.md`: 2026-04-21 기준 1차 아카이빙 계획.
- `archive-manifest-2026-05-03.md`: 2026-05-03 기준 docs README 현행화와 Plan Rebase 전환 증적 이동.
- `plan-korStockScanPerformanceOptimization.rebase.pre-automation-renewal-2026-05-13.md`: 2026-05-13 자동화체인 기준 Plan Rebase 리뉴얼 전 원문.
- `plan-korStockScanPerformanceOptimization.prompt.pre-automation-renewal-2026-05-13.md`: 2026-05-13 자동화체인 기준 prompt 리뉴얼 전 원문.
- `plan-korStockScanPerformanceOptimization.qna.pre-automation-renewal-2026-05-13.md`: 2026-05-13 자동화체인 기준 Q&A 리뉴얼 전 원문.
