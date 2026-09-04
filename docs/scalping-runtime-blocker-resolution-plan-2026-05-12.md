# Scalping Runtime Blocker Resolution Plan - 2026-05-12

## 목적

- `runtime_approval_summary_2026-05-11.md`와 `threshold_apply_2026-05-12.json`의 스캘핑 미선택 항목을 단순 `hold_sample`이 아니라 blocker 유형별로 닫는다.
- 목표는 완벽한 spot 대기가 아니라 EV/순이익 trade-off가 충분한 지점에서 bounded runtime canary 후보를 빠르게 만들 수 있는 판정 체계다.
- 장중 runtime mutation은 계속 금지한다. 모든 live 변경 후보는 장후 calibration -> 다음 장전 bounded env apply만 허용한다.

## 공통 판정 규칙

- `actual_order_submitted=false`인 sim/probe 표본은 EV/source-quality 입력으로 사용한다. broker execution 품질 또는 실주문 전환 근거로 단독 사용하지 않는다.
- 실전 주문가, 체결, 취소, slippage, receipt 관련 blocker는 real-only 또는 real/sim split에서 real 증거를 우선한다.
- holding/exit 관련 blocker는 runtime provisional signal만으로 닫지 않고 post-sell outcome join 또는 명시적 rollback owner가 있어야 한다.
- sample floor를 넘긴 항목도 edge, downside tail, GOOD_EXIT 훼손, same-stage owner conflict가 닫히지 않으면 live apply 대상이 아니다.
- unblock 결론은 `ready_for_preopen_apply`, `ready_for_bounded_canary_request`, `continue_hold_sample`, `freeze_live_risk`, `report_only_design`, `drop_stale` 중 하나로 닫는다.

## 항목별 blocker 및 해소 방안

| Family | 현재 상태 | 핵심 blocker | 해소 방안 | Unblock 조건 |
| --- | --- | --- | --- | --- |
| `protect_trailing_smoothing` | `hold_sample`, sample `18/20` | 표본 floor 미달과 protect/trailing smoothing이 GOOD_EXIT를 훼손하지 않는지 검증 부족 | 장후 `post_sell_feedback`에서 protect/trailing 후보별 `would_defer`, `actual_exit`, `rebound_after_exit`, `additional_worsen_after_defer`를 분리 집계한다. `soft_stop_whipsaw_confirmation`과 같은 holding/exit stage 충돌 여부도 같이 기록한다. | rolling 기준 sample floor 통과, GOOD_EXIT 훼손률이 guard 이하, 추가 worsen tail이 기존 protect/hard stop보다 나쁘지 않음, same-stage owner 충돌 없음 |
| `trailing_continuation` | `freeze`, sample `18` | GOOD_EXIT 훼손 리스크가 명시되어 있어 단순 sample 증가만으로 live 금지 해제 불가 | trailing 이후 `MISSED_UPSIDE`와 `GOOD_EXIT`를 같은 record_id/horizon으로 묶고, continuation이 열렸을 때 잃는 확정 수익과 얻는 추가 MFE를 EV로 비교한다. protect/hard/emergency stop 우선순위는 변경하지 않는다. | `MISSED_UPSIDE` 개선 EV가 GOOD_EXIT 훼손 EV보다 크고, downside tail guard를 통과하며, 별도 continuation rollback owner가 지정됨 |
| `pre_submit_price_guard` | `freeze`, sample `710` | quote freshness 품질 저하가 원인이라 threshold 완화로 해결할 수 없음 | `stale_context_or_quote`, `ws_age`, `spread_bps`, `passive_probe_timeout`, `cancel_requested/confirmed`, `late_fill`을 submit 직전 record로 canonical join한다. stale이면 threshold 완화가 아니라 broker 제출 전 block/defensive repricing으로 귀속한다. | stale/late-fill 원인 분해가 daily EV에 보이고, block vs submit counterfactual 비용이 산출되며, fallback/spread cap 완화 없이 가격품질 guard가 유지됨 |
| `liquidity_gate_refined_candidate` | `hold`, sample `3285` | 표본은 충분하지만 report-only design candidate이며 runtime family guard가 없음 | 기존 source bundle 안에서 blocked liquidity 후보의 후행 EV, missed entry, false-positive risk를 산출한다. 신규 관찰축을 만들지 않고 BUY funnel source로 흡수한다. | `gate_relax_candidate`가 threshold family로 명시되고 max step/bounds/rollback guard가 생김. 그 전에는 report-only 유지 |
| `overbought_gate_refined_candidate` | `hold`, sample `82230` | 대량 표본이나 overbought 완화가 손실 tail을 키울 수 있어 family guard 부재 | 과열 차단 후보를 regime/시간대/체결품질로 bucket화하고, missed upside와 overheat reversal tail을 함께 본다. broad score threshold 완화와 분리한다. | 특정 bucket에서 EV 개선과 downside tail guard가 동시에 통과하고, runtime owner가 liquidity/score family와 충돌하지 않음 |
| `bad_entry_refined_canary` | `hold_sample`, candidate `565` | runtime provisional signal은 많지만 post-sell outcome join이 닫히지 않음. rollback owner가 불충분 | `record_id -> post_sell_evaluations` join을 필수 readiness floor로 만든다. `preventable_bad_entry`, `false_positive_exit`, `defer_cost`, `would_exit_benefit`, `would_exit_harm`을 report에 산출한다. | joined candidate floor 통과, preventable EV benefit 양수, false-positive GOOD_EXIT 손상 guard 이하, hard/protect/order safety 우선순위 유지, rollback owner 명시 |
| `holding_exit_decision_matrix_advisory` | `hold_no_edge`, sample `14` | matrix bucket 대부분이 `no_clear_edge`라 live AI 응답 변경 근거 부족 | SAW/ADM bucket이 `recommended_bias != no_clear_edge`인 후보만 advisory canary 후보로 분리한다. advisory는 AI 응답을 직접 바꾸기 전 bounded flag-off provenance로 검증한다. | non-`no_clear_edge` bucket이 충분히 생기고, advisory 추천의 post-decision proxy EV가 baseline보다 높고, rollback owner가 `holding_exit_decision_matrix_advisory`로 분리됨 |
| `scale_in_price_guard` | `hold`, sample `63` | 기존 P1 가격 guard는 ON이나 별도 승인 전 live 값 변경 금지. resolved/executed scale-in cohort가 희소 | AVG_DOWN/PYRAMID를 `REVERSAL_ADD` 귀속으로 유지하고, request price, resolved price, fill/cancel, post-add MAE/MFE를 분리 집계한다. report-only calibration으로 spread/defensive tick 후보만 산출한다. | scale-in resolved/executed cohort floor 통과, direct `ws_data.curr` 제출 재발 없음, price guard 변경이 실체결 품질을 개선, 별도 approval 필요 시 요청 생성 |
| `position_sizing_cap_release` | `hold_sample`, sample `49/30`, score `0.65/0.70` | raw sample은 floor 이상이나 safety floors 실패: `normal_completed_sample`, `cap_reduced_sample`, `submitted_sample`, `severe_downside_floor` | 1주 cap 유지 상태에서 cap-reduced counterfactual과 submitted/filled real split을 누적한다. 해제는 무제한 주문이 아니라 기존 budget/protection guard 안의 qty 산출 복귀로 정의한다. | trade-off score >= 0.70, safety floors 모두 통과, severe downside tail guard 통과, 사용자 approval request 생성 |
| `holding_flow_ofi_smoothing` | `hold`, sample `187` | blocker라기보다 현행값과 추천값 동일 | 현재 holding_flow_override 내부 OFI/QI postprocessor를 유지하고 daily EV에서 defer cost와 EXIT debounce 효과만 계속 확인한다. | 값 차이가 생기고 guard가 통과할 때만 다음 장전 apply 후보 |

## 시뮬레이션 표본이 의사결정을 빠르게 만드는 조건

시뮬레이션 매매실적은 `entry/exit EV`, missed opportunity, source-quality, 후보 bucket 선별을 빠르게 만든다. 다만 다음 조건이 없으면 표본이 많이 쌓여도 live 변경은 빨라지지 않는다.

- sim/real/combined split이 유지되어야 한다.
- sim 포지션도 open/closed lifecycle이 닫혀야 한다.
- post-sell outcome join이 필요한 holding/exit 항목은 sim stage만으로 최종 라벨을 확정하지 않는다.
- broker execution 품질이 핵심인 항목은 real-only guard가 남는다.
- 각 family가 sample floor뿐 아니라 EV benefit, downside tail, false-positive risk, rollback owner를 숫자로 가져야 한다.

따라서 다음 개선 방향은 데이터 수집 자체가 아니라, 표본이 쌓였을 때 자동으로 `ready`, `hold_sample`, `freeze`, `approval_required` 중 하나로 닫히는 readiness guard를 family별로 넣는 것이다.

## 작업 순서

1. `bad_entry_refined_canary` lifecycle join readiness를 수치화한다.
2. `protect_trailing_smoothing`과 `trailing_continuation`의 GOOD_EXIT 훼손 guard를 daily EV에 노출한다.
3. `pre_submit_price_guard`는 threshold 완화 후보가 아니라 submit revalidation/late-fill 원인 분해 report로 닫는다.
4. `liquidity_gate_refined_candidate`와 `overbought_gate_refined_candidate`는 family guard가 생기기 전까지 report-only design candidate로 유지한다.
5. `position_sizing_cap_release`는 trade-off score와 failed safety floor를 approval request 생성 조건으로 고정한다.
6. sim 표본은 combined EV 가속 입력으로 쓰되, 실주문 전환과 execution quality는 real-only guard를 유지한다.

## 2026-05-12 Postclose 판정 고정

| Family | 오늘 결론 | 고정 근거 | 다음 owner / 입력 |
| --- | --- | --- | --- |
| `protect_trailing_smoothing` | `continue_hold_sample` | `threshold_cycle_ev_2026-05-12.md` sample `18/20`; `GOOD_EXIT` 훼손 guard를 아직 수치로 노출하지 못했다 | `post_sell_feedback`, `panic_sell_defense`, `threshold_cycle_ev`에 `good_exit_damage_rate`, `additional_worsen_after_defer`를 추가 확인 |
| `trailing_continuation` | `freeze_live_risk` | sample `18/20`이고 `threshold_version=direction_conflict_or_live_risk`; continuation EV보다 `GOOD_EXIT` 훼손 리스크가 우선 blocker다 | `holding_exit_observation`, `post_sell_feedback`에서 `MISSED_UPSIDE` 개선과 `GOOD_EXIT` 손상 비교를 같은 cohort로 잠근다 |
| `pre_submit_price_guard` | `continue_hold_sample` (`existing_guard_hold`) | sample `0/20`; 현재 guard는 이미 ON이고, 이번 blocker는 threshold 값이 아니라 stale quote / passive probe attribution 부족이다 | `daily_threshold_cycle_report` source bundle에서 stale/late-fill/cancel provenance를 계속 누적한다 |
| `liquidity_gate_refined_candidate` | `report_only_design` | sample `8360/20`로 표본은 충분하지만 runtime family guard와 rollback owner가 없다 | BUY funnel source 안에서 bucket EV만 계속 보고 새 live family는 만들지 않는다 |
| `overbought_gate_refined_candidate` | `report_only_design` | sample `80361/20`이지만 downside tail bucket guard와 owner conflict 정리가 없다 | regime/time bucket별 missed upside vs reversal tail만 유지한다 |
| `bad_entry_refined_canary` | `continue_hold_sample` | lifecycle attribution 기준 `candidate_records=1`, `post_sell_joined_records=0`, `post_sell_pending_records=1`, `preventable_bad_entry_candidate_records=0` | `record_id -> post_sell_evaluations` join completion과 preventable vs false-positive dominance를 먼저 닫는다 |
| `holding_exit_decision_matrix_advisory` | `continue_hold_sample` (`minimum_edge_missing`) | matrix summary `entry_count=14`, `non_no_clear_edge_count=0`, `candidate_weight_source_non_clear_edge_count=0` | `summary.non_no_clear_edge_count`와 `per_action_edge_buckets`가 0이 아니게 쌓일 때까지 report-only 유지 |
| `scale_in_price_guard` | `continue_hold_sample` (`existing_guard_hold`) | sample `56/20`이지만 resolved/executed scale-in cohort가 아직 부족하고 live apply는 승인 전 금지다 | `resolved_price`, `fill/cancel`, `post_add_mae_mfe`를 유지하고 price/qty 변경은 닫지 않는다 |
| `position_sizing_cap_release` | `continue_hold_sample` | sample `28/30`, `score=0.65/0.70`, `failed_safety_floor=normal_completed_sample,cap_reduced_sample,submitted_sample,severe_downside_floor` | approval request 전용 family로만 유지하고 1주 cap 해제는 사용자 승인 없이는 열지 않는다 |
| `holding_flow_ofi_smoothing` | `continue_hold_sample` | sample `0/20`; 현재 holding_flow_override 값과 추천값 차이가 없다 | defer cost / debounce 효과만 daily EV에서 계속 본다 |

## Bad Entry Lifecycle Join Readiness Guard

`bad_entry_refined_canary`는 runtime provisional signal을 post-sell outcome 없이 최종 라벨로 승격하지 않는다. `2026-05-12` postclose 기준 readiness guard는 아래 수치로 고정한다.

1. `joined_candidate_records >= 10`
   - family sample floor와 같은 rolling 기준선으로 맞춘다. 당일 `candidate_records=1`은 아직 floor에 한참 못 미친다.
2. `join_completion_rate >= 0.90`
   - 계산식은 `post_sell_joined_records / candidate_records`다. bounded canary request를 만들 때는 `post_sell_pending_records == 0`도 같이 요구한다.
3. `preventable_bad_entry_candidate_records >= 3`
   - joined record가 있더라도 preventable 표본이 너무 적으면 조기정리 canary의 precision을 읽을 수 없다.
4. `preventable_bad_entry_candidate_records > false_positive_risk_after_candidate_records`
   - `GOOD_EXIT` 훼손 또는 과조기 정리 risk가 preventable count보다 크거나 같으면 readiness를 닫지 않는다.
5. `late_detected_soft_stop_zone_records`는 readiness numerator에 넣지 않는다.
   - `soft_stop_zone`은 조기 진입 차단이 아니라 late-detected 후보라서 `preventable`과 분리한다.

오늘 값은 `candidate_records=1`, `post_sell_joined_records=0`, `post_sell_pending_records=1`, `preventable_bad_entry_candidate_records=0`, `false_positive_risk_after_candidate_records=0`다. 따라서 결론은 `continue_hold_sample`이다.

## Blocked Family Readiness Guard Inputs

다음 postclose automation이 blocker를 숫자로 닫으려면 아래 입력 필드를 source bundle에 계속 유지해야 한다.

| Family | 필수 자동화 입력 | live apply 금지 조건 |
| --- | --- | --- |
| `protect_trailing_smoothing` | `post_sell_joined_sample_count`, `good_exit_damage_rate`, `additional_worsen_after_defer_p95`, `rebound_after_exit_rate` | `good_exit_damage_rate`가 guard를 넘거나 joined sample이 floor 미달이면 금지 |
| `trailing_continuation` | `missed_upside_rate`, `good_exit_damage_rate`, `continuation_mfe_delta_pct`, `downside_tail_p95` | `GOOD_EXIT` 훼손 EV가 continuation EV보다 크면 금지 |
| `pre_submit_price_guard` | `stale_context_or_quote_count`, `ws_age_p95_ms`, `spread_bps_p95`, `passive_probe_timeout_count`, `cancel_confirm_gap_ms_p95`, `late_fill_count` | score threshold/spread cap/fallback 재개를 blocker 해소 수단으로 쓰지 않는다 |
| `holding_exit_decision_matrix_advisory` | `summary.non_no_clear_edge_count`, `summary.candidate_weight_source_non_clear_edge_count`, `summary.per_action_edge_buckets` | `non_no_clear_edge_count == 0`이면 advisory live apply 금지 |
| `position_sizing_cap_release` | `sample_count`, `sample_floor`, `tradeoff_score`, `failed_safety_floor`, `normal_completed_sample`, `cap_reduced_sample`, `submitted_sample`, `severe_downside_floor` | `allowed_runtime_apply=false` 유지, approval request와 사용자 승인 없이는 cap 해제 금지 |

## Sim Acceleration / Real-Only Guard Matrix

| Family | `sim_accelerates_decision` | `real_only_guard` | `approval_required` | 이유 |
| --- | --- | --- | --- | --- |
| `score65_74_recovery_probe` | `true` | `true` | `false` | `missed_probe_counterfactual`는 EV/기회비용을 빠르게 보지만 `actual_order_submitted=false`라 broker execution 판단에는 못 쓴다 |
| `liquidity_gate_refined_candidate` | `true` | `true` | `false` | blocked entry 후행 EV는 sim/combined로 충분하지만 실주문 체결 품질은 real-only다 |
| `overbought_gate_refined_candidate` | `true` | `true` | `false` | 과열 차단 missed upside는 sim으로 가속 가능하나 live 완화는 downside tail guard가 더 중요하다 |
| `bad_entry_refined_canary` | `partial` | `true` | `false` | holding/exit EV는 sim/combined가 보조 입력이지만 final label은 `post_sell` joined outcome이 필요하다 |
| `pre_submit_price_guard` | `false` | `true` | `false` | 핵심 blocker가 stale quote, cancel, late-fill 같은 execution quality라 sim만으로는 닫히지 않는다 |
| `holding_exit_decision_matrix_advisory` | `partial` | `true` | `false` | matrix edge 후보는 report-only로 가속 가능하지만 live 적용 전에는 non-`no_clear_edge` bucket과 real holding path 분리가 필요하다 |
| `scale_in_price_guard` | `partial` | `true` | `false` | sim이 opportunity EV를 넓혀도 resolved/executed scale-in 품질은 real guard가 남는다 |
| `position_sizing_cap_release` | `true` | `true` | `true` | cap opportunity EV는 sim/combined로 가속할 수 있지만 실주문 수량 증가와 severe downside는 approval-required real guard다 |
