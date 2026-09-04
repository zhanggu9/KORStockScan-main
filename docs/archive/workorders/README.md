# Archived Workorders

기준일: `2026-05-14 KST`

이 디렉터리는 `docs/` 최상위에 남아 있던 과거 작업지시서를 보존하는 archive다. 현재 실행 owner는 날짜별 checklist와 `Plan Rebase`가 소유하므로, 아래 문서는 현재 OPEN 작업으로 해석하지 않는다.

## 최상위 유지 문서

| 문서 | 유지 사유 |
| --- | --- |
| `docs/workorder-position-sizing-dynamic-formula.md` | 현재 `position_sizing_dynamic_formula` owner의 source bundle, sample floor, provenance, approval schema를 소유한다. |
| `docs/workorder-shadow-canary-runtime-classification.md` | 매일 POSTCLOSE shadow/canary/cohort 분류 확인의 기준문서다. |

## Archive 판정

| 문서 | 판정 | 사유 |
| --- | --- | --- |
| `workorder-0421-auditor-performance-report.md` | completed_historical | 2026-04-21 감사 보고 산출물 생성 지시. 결과 보고와 체크리스트로 닫힘. |
| `workorder-0421-tuning-plan-rebase.md` | superseded_by_plan_rebase | 현재 원칙과 active/open 상태는 `docs/plan-korStockScanPerformanceOptimization.rebase.md`가 소유한다. |
| `workorder-0421-validate-0420-applies.md` | completed_historical | 2026-04-20 적용사항 검증 지시. 2026-04-21 체크리스트에서 닫힘. |
| `workorder-ai-engine-deepseek.md` | completed_historical | DeepSeek 엔진 생성 지시. 현재 live route/approval 판정 owner가 아니다. |
| `workorder-deepseek-performance-tuning-observation-coverage.md` | completed_historical | 결과서가 `PASS`로 닫힌 과거 관찰 coverage 지시다. |
| `workorder-deepseek-performance-tuning-observation-coverage.result.md` | completed_result | 위 workorder의 결과 증적이다. |
| `workorder-deepseek-swing-pattern-lab.md` | completed_historical | swing pattern lab 초기 구축 지시. 현재 swing lifecycle은 threshold-cycle/report chain이 소유한다. |
| `workorder-deepseek-swing-pattern-lab-phase2.md` | completed_historical | phase2 구축 지시. 결과 보고서로 닫힘. |
| `workorder-deepseek-swing-pattern-lab-phase3-remaining.md` | completed_or_superseded | 2026-05-11 checklist 이후 현재 swing dry-run/self-improvement chain으로 흡수됨. |
| `workorder-kiwoom-sniper-v2-loop-performance-improvement.md` | completed_historical | 2026-04 loop 성능 개선 지시. 현재 성능 병목은 code improvement workorder/report chain이 소유한다. |
| `workorder-sniper-codebase-performance-audit-followup.md` | completed_historical | 2026-04 성능 감사 후속 지시. 현재 OPEN owner가 아니다. |
| `workorder_data_client_decompose.md` | historical_reference | 미사용 data client 정리 설계 참고 문서다. 현재 checklist owner가 없다. |
| `workorder_deepseek_engine_review.md` | completed_historical | DeepSeek 엔진 리뷰 후속 지시. acceptance/checklist 이력으로 보존한다. |
| `workorder_gemini_engine_review.md` | completed_historical | Gemini 엔진 리뷰 후속 지시. 현재 Gemini/OpenAI route 판정 owner가 아니다. |

## 운영 규칙

1. archive 문서는 현재 OPEN owner가 아니다.
2. archive 문서를 다시 실행하려면 당일 checklist에 새 parser-friendly 항목과 Source/Section을 추가한다.
3. runtime threshold, provider, 주문 guard, bot restart, 실주문 전환은 archive workorder만으로 변경하지 않는다.
