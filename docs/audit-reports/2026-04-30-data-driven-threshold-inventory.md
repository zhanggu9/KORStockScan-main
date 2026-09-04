# 2026-04-30 Data-Driven Threshold Inventory

작성시각: `2026-04-30 14:08 KST`  
범위: main-only, `2026-04-30` 실전 DB + `data/pipeline_events/pipeline_events_2026-04-30.jsonl`  
목적: 데이터 기반 threshold 산정이 가능한 파라미터를 `데이터량`, `산정 가능성`, `운영 전환 방식`으로 분리한다.

## 판정

- 데이터 기반 threshold 산정은 지금부터 바로 열 수 있다.
- 대상은 `REVERSAL_ADD`에 한정되지 않는다. entry gate, latency relief, soft stop, bad entry, pre-submit price guard, partial fill, trailing, position sizing까지 모두 후보군이다.
- 새 보조축으로 `statistical_action_weight`를 둔다. 가격대, 거래량, 시간대별로 `exit_only`, `avg_down_wait`, `pyramid_wait`의 후행 성과를 비교하되, live 판단이 아니라 장후 threshold weight 입력으로만 사용한다.
- 다만 모든 파라미터가 같은 수준으로 준비된 것은 아니다. `분포 산정`이 가능한 축과 `outcome 기반 EV 산정`이 가능한 축을 분리해야 한다.
- 운영 전환은 `실시간 자동변경`이 아니라 `매일 적재 -> 장후 산정 -> 다음 장전 적용` 구조로 고정한다.

## 현재 데이터량 요약

| 데이터 | 현재 표본 |
| --- | ---: |
| DB `COMPLETED + valid profit_rate` | `63`건 |
| DB 손실 거래 | `41`건 |
| `budget_pass` | `6,232`건 / unique `109` |
| `order_bundle_submitted` | `78`건 / unique `73` |
| `exit_signal/sell_order_sent/sell_completed` | 각 `66`건 / unique `66` |
| `strength_momentum_observed` | `153,335`건 / unique `231` |
| `strength_momentum_pass` | `3,726`건 / unique `177` |
| `blocked_strength_momentum` | `153,335`건 / unique `231` |
| `blocked_liquidity` | `2,339`건 / unique `81` |
| `blocked_ai_score` | `349`건 / unique `110` |
| `ai_cooldown_blocked` | `429`건 / unique `111` |
| `soft_stop_micro_grace` | `307`건 / unique `37` |
| `soft_stop_expert_shadow` | `59`건 / unique `12` |
| `soft_stop_absorption_probe` | `7`건 / unique `6` |
| `soft_stop_absorption_extend/recovered` | `1`건 / unique `1` |
| `bad_entry_block_observed` | `329`건 / unique `31` |
| `reversal_add_blocked_reason` | `1,735`건 / unique `65` |
| `reversal_add_candidate` | `22`건 / unique `8` |
| `scale_in_executed` | `7`건 / unique `7`, 전부 `PYRAMID`, `AVG_DOWN=0` |
| partial fill 관련 stage | `0`건 |
| post-sell feedback stage | `0`건 |

## IO 부하 판정 보정 (2026-04-30 POSTCLOSE)

- `data/pipeline_events/pipeline_events_2026-04-30.jsonl`은 장후 확인 시점 기준 약 `486MB`였고, `data/pipeline_events/` 전체는 약 `2.7GB`였다.
- `threshold_cycle_2026-04-30.json`은 `event_count_same_day=10,894`로 생성됐지만, 원천 raw 파일에는 blocker/관찰 이벤트가 훨씬 많아 항목별 반복 full scan은 스토리지 IO 부하를 크게 키운다.
- 오늘 장후 판정은 raw jsonl을 반복 스캔하지 않고, 가능한 한 single-pass 경량 집계와 기존 threshold cycle 산출물을 재사용했다.
- 운영 판정: threshold 수집 기능은 기대값 개선의 기반이지만, 장중/장후마다 raw full scan을 반복하면 시스템 가용성과 체결 truth 품질을 훼손한다. `2026-05-06` `[ThresholdCollectorIO0506]`에서 과부하가 초기 적재 1회성인지, 매 cycle 반복성인지 분리 판정한다.
- 후속 설계 후보: cursor 기반 증분 collector, stage 필터 사전집계, 일자/분 단위 partition, single-pass shared snapshot. 반복성 과부하로 확인되면 이 중 하나를 구현 항목으로 승격한다.

## Threshold Collector IO 구조개선 (2026-04-30 Night)

- 반복 raw full scan은 폐기한다. 운영 경로는 `1회 bootstrap -> daily incremental -> partitioned compact dataset -> 장후 threshold 산정 -> 다음 장전 적용`으로 고정한다.
- compact dataset은 `data/threshold_cycle/date=YYYY-MM-DD/family=<family>/part-000001.jsonl` 구조를 우선 사용하고, 기존 `threshold_events_YYYY-MM-DD.jsonl`은 호환 fallback으로만 남긴다.
- 파티션은 `date/family`뿐 아니라 라인수 상한을 둔다. 기본값은 input chunk `20,000` raw lines, output partition `25,000` compact lines이며, 라인 cap 도달 시 checkpoint를 남기고 다음 실행에서 이어간다.
- checkpoint는 `data/threshold_cycle/checkpoints/YYYY-MM-DD.json`에 source path/size/mtime, byte offset, raw line count, written count, partition state, completed, paused reason, system metric sample을 저장한다.
- source truncate 또는 mtime/size 불일치가 감지되면 자동 재개하지 않고 `stopped_source_changed`로 중단한다. 이 경우 overwrite 여부를 사람이 명시해야 한다.
- 시스템 가용성 측정은 기존 `src/engine/system_metric_sampler.py`를 사용한다. 각 chunk 전후 `cpu.iowait_pct`, `io.disk_read_mb_delta`, `memory.mem_available_mb`를 기록하고, 기본 guard는 `iowait_pct>=20`, `chunk read>=128MB`, `mem_available<512MB`다.
- checkpoint에는 다음 실행 권고값 `recommended_next_input_lines_per_chunk`도 남긴다. guard에 걸리면 현재 cap의 50%로 낮추고, iowait/read/memory가 안정적이면 기본 상한 안에서만 완만하게 늘린다.
- threshold report loader 우선순위는 `partitioned compact > legacy compact > small raw fallback`이다. raw fallback은 기존 `64MB` 이하에서만 허용하고, 초과 시 scan하지 않고 warning/meta만 남긴다.
- `2026-05-01` 오전 휴일 bootstrap은 실전 trading 작업이 아니라 maintenance 작업으로 분리한다. 첫 실행은 보수 line cap으로 시작해 system metric sample을 보고 다음 cap을 조정한다.
- `2026-05-01` 휴일 실행 결과, 가용한 4월 raw 전체(`2026-04-25`, `2026-04-27`, `2026-04-28`, `2026-04-29`, `2026-04-30`)를 partitioned compact로 적재했다. 각 일자 checkpoint는 모두 `completed=true`, `paused_reason=null`이며 compact event count는 각각 `6`, `7653`, `8583`, `15093`, `10894`다.
- `2026-05-04`부터 daily automation은 `07:35 PREOPEN apply manifest`, `16:10 POSTCLOSE collector/report`로 등록했다. live threshold runtime mutation은 `ThresholdOpsTransition0506` acceptance 전까지 `manifest_only`로 유지한다.
- 향후 threshold가 늘어날 때 수집 누락을 막기 위해 stage inclusion rule은 `src/utils/threshold_cycle_registry.py`로 중앙화한다. 새 threshold는 이 registry에 stage/family를 추가하거나, pipeline event `fields`에 `threshold_family`를 남기면 live compact stream, raw backfill, report loader가 같은 규칙으로 자동 포함한다.
- `exit_signal`, `sell_completed`, `scale_in_executed`는 `statistical_action_weight` family로 compact stream에 포함한다. 목적은 가격대/거래량/시간대별 청산/물타기/불타기 대기 성과를 장후에 비교하기 위한 최소 행동 결과 표본 확보다.
- `stat_action_decision_snapshot`도 같은 family로 포함한다. 이 이벤트는 실제 선택 행동뿐 아니라 `eligible_actions`, `rejected_actions`, `chosen_action`, `scale_in_gate_reason`, `scale_in_action_reason`, `exit_rule_candidate`를 함께 남겨 selection bias를 줄이기 위한 decision moment 표본이다.
- 4월 partitioned compact는 이 registry 추가 전에 bootstrap된 파일이므로 historical action stage가 비어 있을 수 있다. 4월 전체 action-weight를 보려면 raw full scan 반복이 아니라 기존 IO guard/checkpoint를 사용하는 maintenance backfill로 action family를 재적재한다.

## Threshold 후보 분류

| 영역 | 파라미터/묶음 | 데이터량 | 현재 산정 가능성 | 해석 |
| --- | --- | ---: | --- | --- |
| Entry latency | `mechanical_momentum`의 `MAX_SIGNAL_SCORE`, `MIN_STRENGTH`, `MIN_BUY_PRESSURE`, `MAX_WS_AGE`, `MAX_WS_JITTER`, `MAX_SPREAD` | `budget_pass 6,232`, submitted `78` | 가능 | 제출 회복 threshold는 분포 기반 재산정 가능하다. outcome 연결은 completed `63`건이라 direction-only로 둔다. |
| Entry VPW | `SCALP_VPW_MIN_BASE`, `MIN_BUY_VALUE`, `MIN_BUY_RATIO`, `MIN_EXEC_BUY_RATIO`, `NET_BUY_QTY`, relax set | observed `153,335`, pass `3,726` | 가능 | 분포 표본은 충분하다. 다만 pass가 제출/체결/손익으로 이어졌는지 record-level join을 해야 EV 산정이 된다. |
| Entry liquidity | `MIN_SCALP_LIQUIDITY` | blocked `2,339` / unique `81` | 분포 가능, EV 제한 | 현재 blocked 표본은 많지만 미진입 outcome이 없으므로 완화 시 기대값은 submitted 후보와 결합해야 한다. |
| Entry AI score | `BUY_SCORE_THRESHOLD`, `entry_score_threshold`, cooldown threshold | blocked AI `349`, cooldown `429` | 가능 | AI threshold/cooldown 분포는 충분하다. 단, AI 완화는 entry live 축이므로 기존 canary와 분리해야 한다. |
| Pre-submit price guard | `SCALPING_PRE_SUBMIT_MAX_BELOW_BID_BPS=80` | submitted `78`, `price_below_bid_bps` `234`, block `0` | 분포 가능, block outcome 부족 | 현재 p90이 약 `74.7bps`라 80bps anchor 검증은 가능하지만 실제 block 표본이 없어 하향/상향 효과는 장후 보수 판정이다. |
| Soft stop v1 | `SCALP_STOP=-1.5`, `MICRO_GRACE_SEC=20`, `EMERGENCY=-2.0` | micro grace `307` / unique `37`, soft stop exit unique `36` | 가능 | 오늘 손실 핵심축이라 threshold 산정 우선순위가 높다. `profit_rate`, `elapsed_sec`, `peak_profit`, 후행 exit가 연결된다. |
| Soft stop expert v2 | `ABSORPTION_MIN_SCORE`, `EXTENSION_SEC`, `MIN_BUY_PRESSURE`, `MIN_TICK_ACCEL`, `MIN_MICRO_VWAP_BP`, `MAX_TOP3_DEPTH_RATIO` | shadow `59` / unique `12`, probe `7` / unique `6`, extend `1` | 부분 가능 | shadow feature 분포는 가능하지만 live 유예 결과는 표본 부족이다. 장마감까지 유지 후 재집계한다. |
| Bad entry | `MIN_HOLD_SEC=60`, `MIN_LOSS=-0.70`, `MAX_PEAK=0.20`, `AI_LIMIT=45` | observed `329` / unique `31` | 가능 | 손실 flow 1순위와 직접 연결된다. live block 전 counterfactual threshold 산정이 가능하다. |
| REVERSAL_ADD | `PNL_MIN/MAX`, `MIN/MAX_HOLD`, `MIN_AI`, `AI_RECOVERY_DELTA`, supply 3/4, qty ratio | blocked `1,735` / unique `65`, candidate `22` / unique `8`, AVG_DOWN executed `0` | blocked cohort 기반 가능, realized EV 부족 | 현재 조건은 과도하게 좁다. 다만 first-fail 로그라 완화 후 다음 gate 통과 여부를 완전히 복원하려면 all-predicate logging이 필요하다. |
| PYRAMID | `PYRAMID_MIN_PROFIT`, `SIZE_RATIO`, `post_add_trailing_grace` | executed `7` | 부족 | 실제 체결은 있으나 표본이 작다. 오늘은 로직 오류 방지와 would_qty counterfactual만 가능하다. |
| Statistical action weight | 가격대, 거래량, 시간대별 `exit_only`/`avg_down_wait`/`pyramid_wait` 성과 가중치 | completed + compact action stages | 신규 report-only | live 행동 변경 없이 “이 장면에서는 청산/물타기/불타기 후 대기 중 무엇이 유리했는가”를 장후 통계로 본다. 거래량 누락률이 높으면 volume 결론은 금지한다. |
| Trailing | `SCALP_TRAILING_START_PCT`, drawdown/continuation 후보 | trailing exit unique `23` | 제한 가능 | 표본은 작지만 post-sell/continuation과 결합하면 장후 direction-only 가능하다. |
| Preset hard stop | `SCALP_PRESET_HARD_STOP_PCT`, grace/emergency | exit unique `3` | 부족 | 오늘 표본으로 threshold 재산정 금지. 안전가드로 유지한다. |
| Partial fill guard | `SCALP_PARTIAL_FILL_MIN_RATIO_*` | `0` | 불가 | 오늘 실전 표본 없음. historical 또는 다음 체결 발생 전까지 현행 유지. |
| Post-sell feedback | `MISSED_UPSIDE_MFE`, `GOOD_EXIT_MAE/CLOSE` | pipeline stage `0` | 오늘 데이터 불가 | 별도 post-sell 리포트/월간 표본으로만 가능하다. 오늘 pipeline 기준으로는 산정 불가. |

## 즉시 산정 우선순위

1. `bad_entry_block` threshold
   - 이유: 오늘 손실 flow 1순위가 `bad_entry/never-green`이고 observe 표본 `329`건/unique `31`이 있다.
   - 산정축: `MIN_HOLD_SEC`, `MIN_LOSS_PCT`, `MAX_PEAK_PROFIT_PCT`, `AI_SCORE_LIMIT`.

2. `REVERSAL_ADD` threshold
   - 이유: blocked 표본 `1,735`건/unique `65`가 있고 `AVG_DOWN=0`이라 현행 조건이 실제 체결을 거의 열지 못했다.
   - 산정축: `PNL_MIN`, `MAX_HOLD_SEC`, `MIN_AI_SCORE`, `AI_RECOVERY_DELTA`.
   - 주의: 현재 로그가 first-fail 방식이라 all-predicate counterfactual은 보강 필요.

3. `soft_stop_micro_grace` threshold
   - 이유: micro grace `307`건/unique `37`, soft stop exit unique `36`으로 당일 산정 가능한 최소 표본이 있다.
   - 산정축: `GRACE_SEC`, `EMERGENCY_PCT`, `soft stop touch 후 rebound/recovery`.

4. `entry mechanical/VPW/liquidity` threshold
   - 이유: 분포 표본은 가장 많다. 다만 같은 날 holding/exit canary와 섞이지 않게 entry stage 단독으로 산정한다.
   - 산정축: `ws_age`, `spread`, `latest_strength`, `buy_pressure`, VPW buy ratio/exec ratio, liquidity.

5. `statistical_action_weight`
   - 이유: 전문가 규칙만으로는 가격대/거래량/시간대별 행동 선택의 기대값 차이를 설명하기 어렵다.
   - 산정축: `price_bucket`, `volume_bucket`, `time_bucket`별 `exit_only`, `avg_down_wait`, `pyramid_wait` 평균손익/승률/표본수, `confidence_adjusted_score`, `policy_hint`.
   - 주의: 이 축은 다음 live owner가 아니라 threshold weight 및 동적 수량화 후보의 근거다.

## 통계 행동가중치 설계 보강

`statistical_action_weight`는 단순히 bucket별 평균손익이 가장 높은 행동을 고르는 장치가 아니다. 표본이 작고 장면이 빠르게 바뀌는 스캘핑에서는 평균값보다 `얼마나 믿을 수 있는가`와 `틀렸을 때 손실 꼬리가 얼마나 큰가`가 더 중요하다. 따라서 아래 7개 원칙으로 보강한다.

1. `empirical bayes shrinkage`
   - bucket/action 표본이 작으면 해당 bucket 평균을 그대로 믿지 않는다.
   - `exit_only`, `avg_down_wait`, `pyramid_wait` 각 action의 전체 prior 평균으로 당겨서 과최적화를 줄인다.
   - 현재 report는 action별 prior strength `8`을 기본값으로 둔다.

2. `lower confidence bound`
   - 추천 score는 평균손익이 아니라 `empirical_bayes_profit_rate - uncertainty_penalty`다.
   - 표본이 적거나 변동성이 큰 bucket은 평균이 좋아도 score가 낮아진다.
   - 이 값은 `confidence_adjusted_score`로 기록한다.

3. `no-clear-edge policy`
   - 최고 행동과 차선 행동의 score 차이가 `0.15%p` 미만이면 행동 우위를 선언하지 않는다.
   - 이런 경우는 `policy_hint=no_clear_edge`로 두고 live threshold 변경 근거로 쓰지 않는다.

4. `tail-risk veto`
   - 어떤 행동의 평균이 좋아도 손실 비율이 `65%` 이상이면 `defensive_only_high_loss_rate`로 둔다.
   - 물타기/불타기처럼 노출을 늘리는 행동은 평균보다 downside p10과 loss_rate를 더 엄격히 본다.

5. `hierarchical context`
   - 1단계는 global action prior다.
   - 2단계는 `time_bucket`, `price_bucket`, `volume_bucket` 단일축이다.
   - 3단계는 충분한 표본이 쌓인 뒤에만 `price x time`, `volume x time`, `price x volume` 교차축으로 확장한다.
   - 3축 동시 교차는 표본이 급격히 희소해지므로 최소 `bucket-action sample>=20` 전에는 금지한다.

6. `action nudge, not action switch`
   - 이 축은 "지금은 반드시 물타기" 같은 직접 명령을 만들지 않는다.
   - 결과는 threshold 또는 수량 산식의 작은 가중치로만 쓴다.
   - 예: `avg_down_wait` score가 `exit_only`보다 충분히 높으면 `REVERSAL_ADD_MAX_HOLD_SEC` 완화 또는 `would_qty` confidence multiplier 후보가 되고, `exit_only`가 높으면 bad-entry/refined exit 쪽 weight가 올라간다.

7. `opportunity cost 포함`
   - `exit_only`는 손실 축소만 보면 과대평가될 수 있다.
   - post-sell MFE/MAE, same-symbol reentry, missed upside가 연결되면 `exit_only` 보상에서 missed upside penalty를 차감한다.
   - 이 연결이 없으면 `exit_only` 우위도 provisional로만 본다.

8. `decision snapshot 우선`
   - 실제로 선택된 행동만 보면 selection bias가 생긴다.
   - HOLDING 루프에서 `exit_now`, `hold_wait`, `avg_down_wait`, `pyramid_wait` 중 무엇이 가능했고 무엇이 차단됐는지를 `stat_action_decision_snapshot`으로 남긴다.
   - 장후 리포트는 최종적으로 `chosen_action` 성과와 `eligible_but_not_chosen` 후보의 후행 MFE/MAE를 분리해야 한다.

## 통계 행동가중치 2차 고급축 로드맵

2차 고급축은 parking하지 않는다. 다만 1차 단일축 표본과 사람이 읽는 Markdown 리포트가 먼저 열려야 하므로 아래 순서로 고정한다.

| 단계 | 대상 | 적용 형태 | 진입 조건 | 산출물 |
| --- | --- | --- | --- | --- |
| `SAW-1` | 단일축 `price_bucket`, `volume_bucket`, `time_bucket` | report-only | `stat_action_decision_snapshot` 적재 확인 | `statistical_action_weight_YYYY-MM-DD.md/json` |
| `SAW-2` | 교차축 `price x time`, `volume x time`, `price x volume` | report-only | 단일축 bucket-action sample floor 충족, `volume_unknown` 과다 아님 | 교차축 표본/score/희소 bucket 제외표 |
| `SAW-3` | `eligible_but_not_chosen` 후행 성과 | observe-only + report | snapshot timestamp와 후행 quote/position outcome 연결 가능 | 후보별 `post_decision_mfe/mae`, missed upside, avoided loss |
| `SAW-4` | 체결 품질 `full/partial`, slippage, adverse fill | observe-only + report | execution receipt와 decision snapshot join key 확보 | action별 fill quality/realized slippage 분리표 |
| `SAW-5` | 시장/종목 맥락 `market_regime`, `volatility`, `marcap`, sector/theme, VI/freshness | report-only | 기본 bucket 표본 유지 + regime/source 누락률 허용 범위 충족 | 맥락별 action weight 후보 |
| `SAW-6` | orderbook absorption / large sell print / micro VWAP 이탈 | observe-only + report | orderbook snapshot 필드 안정성 확인 | absorption 조건별 soft stop/avg_down/pyramid 성과 |

작업 소유권은 다음과 같이 둔다.

- `2026-05-06 POSTCLOSE`: `SAW-1` Markdown 리포트 자동 생성 구현/검증, `SAW-2` 교차축 설계 및 sample floor 확정.
- `2026-05-07 POSTCLOSE`: `SAW-3` eligible-but-not-chosen 후행 MFE/MAE 연결 설계.
- `2026-05-08 POSTCLOSE`: `SAW-4~SAW-6` 체결품질/시장맥락/orderbook 고급축 적재 가능성 판정.

공통 금지조건은 아래와 같다.

- `statistical_action_weight`는 직접 매수/매도/추가매수 결정을 바꾸지 않는다.
- 교차축은 `bucket-action sample>=20` 전에는 추천값을 만들지 않고 `insufficient_sample`로만 남긴다.
- 2차 고급축 결과가 좋아 보여도 다음 장전 live 적용은 별도 threshold owner, 단일축 canary, rollback guard가 없으면 금지한다.

## AI 보유/청산 판단 Matrix 적용 로드맵

`statistical_action_weight`는 threshold 산정만을 위한 축으로 끝내지 않는다. 별도 산출물인 `holding_exit_decision_matrix`를 만들어 AI가 보유/청산 판단을 할 때 참조할 수 있는 통계 요약과 가중치 신호를 제공한다.

단, 실시간 tick 중 학습/가중치 갱신은 금지한다. 장후에 산정한 matrix를 다음 장전 로드하고, 장중에는 immutable context로만 사용한다. 이렇게 하면 AI 판단에는 실시간으로 개입하지만, 원인귀속은 `matrix_version` 단위로 고정된다.

| 단계 | 대상 | 적용 형태 | 진입 조건 | 산출물 |
| --- | --- | --- | --- | --- |
| `ADM-1` | AI 참조용 matrix schema | report-only | `statistical_action_weight` Markdown 생성 | `holding_exit_decision_matrix_YYYY-MM-DD.json/md` |
| `ADM-2` | holding/exit prompt context 주입 | shadow prompt only | matrix key coverage, token budget, cache key 영향 확인 | AI 응답 diff, action_label drift, confidence drift |
| `ADM-3` | AI 판단 후처리 가중치 | observe-only | shadow prompt diff가 안정적이고 false-positive exit 증가 없음 | `ai_matrix_nudge_score`, would_action |
| `ADM-4` | runtime intervention canary | single owner canary | rollback guard, cohort tag, matrix_version provenance 확정 | holding/exit AI matrix canary |
| `ADM-5` | daily feedback loop | postclose batch | threshold version별 성과 분석 완료 | 다음 matrix weight 미세조정 |

matrix는 아래 필드를 최소 단위로 가진다.

- `matrix_version`, `source_report`, `generated_at`, `valid_for_date`
- `context_bucket`: `price_bucket`, `volume_bucket`, `time_bucket`, 이후 `price x time` 등 교차축
- `recommended_bias`: `prefer_exit`, `prefer_hold`, `prefer_avg_down_wait`, `prefer_pyramid_wait`, `no_clear_edge`
- `confidence_adjusted_score`, `edge_margin`, `sample`, `loss_rate`, `downside_p10_profit_rate`
- `hard_veto`: emergency/hard stop, active sell pending, invalid feature, post-add eval exclusion
- `prompt_hint`: AI에게 제공할 짧은 통계 문맥. 직접 명령이 아니라 "이 조건의 과거 outcome 경향"으로 표현한다.

AI 개입 방식은 3단계로 제한한다.

1. `shadow prompt injection`
   - 기존 AI 판단에는 영향 없이 같은 입력에 matrix context를 추가한 shadow prompt를 호출해 응답 차이만 본다.
   - 산출물은 `action_label`, `confidence`, `reason`, `exit/hold/add` drift다.

2. `observe-only nudge`
   - live AI 응답을 바꾸지 않고 matrix 기준 `would_nudge`와 `nudge_strength`만 로그에 남긴다.
   - 이 단계에서 `exit_now` 강화, `hold_wait` 강화, `avg_down_wait` 강화 후보를 분리한다.

3. `single-owner canary`
   - 승인된 날에만 holding/exit 단계의 단일 owner로 적용한다.
   - AI 점수 자체를 임의로 덮어쓰지 않고, prompt context 또는 후처리 가중치 중 하나만 사용한다.

즉 이 축의 목표는 `threshold 적용`이 아니라 `AI 보유/청산 판단의 통계적 문맥 주입`이다. threshold family와 같은 데이터를 쓰지만 산출물, 적용 위치, rollback owner는 분리한다.

## 일일 Threshold 운영 사이클

실시간 자동변경 아이디어는 폐기한다. threshold는 장중에 흔들지 않고, 아래 일일 사이클로만 움직인다.

1. `장중 적재`
   - 실전 런타임은 고정 threshold만 사용한다.
   - 대신 모든 후보 축에 대해 `would_pass`, `would_block`, `would_add`, `would_exit`, 후행 `COMPLETED + valid profit_rate`, soft/hard/trailing 전환을 계속 적재한다.

2. `장후 산정`
   - `same-day`, `rolling 3d`, `rolling 7d`를 같이 본다.
   - 추천 threshold는 family별 최소 표본을 넘길 때만 산출한다.
   - 기본 최소 표본 anchor:
     - entry gate: submitted `>=50` 또는 budget_pass `>=500`
     - holding/exit: completed `>=30`
     - `REVERSAL_ADD`: candidate `>=20`
     - `bad_entry_block`: observed `>=30`

3. `bounded recommendation`
   - 추천값은 문서화된 상하한 안에서만 움직인다.
   - 예: `REVERSAL_ADD_MAX_HOLD_SEC=180~900`, `REVERSAL_ADD_PNL_MIN=-0.70~-1.30`, `SCALPING_PRE_SUBMIT_MAX_BELOW_BID_BPS=60~120`, `SCALP_SOFT_STOP_MICRO_GRACE_SEC=10~60`.

4. `change governor`
   - 하루 변경폭 cap을 둔다.
   - 예: 시간 threshold는 일일 `+-60초`, 손익률 threshold는 일일 `+-0.15%p`, ratio/bps threshold는 일일 `+-10~15%` 또는 `+-10bps` 이내로 제한한다.

5. `다음 장전 적용`
   - 장후 추천값을 바로 live에 넣지 않는다.
   - 다음 장전 `PREOPEN`에서 `단일 owner`, `rollback guard`, `cohort tag`를 잠근 뒤 적용한다.
   - 같은 단계에서는 하루에 1축만 live owner가 된다.

6. `장중 고정`
   - 장중에는 추천값이 다시 계산돼도 적용하지 않는다.
   - 재계산 결과는 `shadow recommendation`으로만 남기고 다음 장후 판정 입력으로 넘긴다.

## 운영전환 필수 구현 조건

최종 안정화가 완료되어 threshold cycle을 운영 전환할 때는 아래 4개 조건을 모두 구현해야 한다. 하나라도 빠지면 수동 리포트/수동 적용 단계로 유지한다.

1. `매일 자동 실행`
   - 장중에는 compact threshold event 적재가 자동으로 계속되어야 한다.
   - 장후에는 partitioned compact dataset 기준 threshold 산정 배치가 자동 실행되어야 한다.
   - raw full scan은 bootstrap/복구성 작업으로만 허용하고, daily path에는 넣지 않는다.

2. `다음 장전 자동 적용 + 봇 기동`
   - 장후 산정 결과 중 승인된 `apply_candidate_list`만 다음 장전 `PREOPEN`에 적용한다.
   - 적용 전에는 `threshold_snapshot`, `change governor`, `rollback_guard_pack`, `single owner` 조건을 검사한다.
   - 적용 후 봇이 기동될 때 runtime config/env provenance에 `threshold_version`, `source_report`, `applied_family`, `current -> applied` diff가 남아야 한다.

3. `장후 매매실적 결과 분석 제출`
   - 매일 장후에는 당일 적용 threshold version별 매매실적 결과를 제출해야 한다.
   - 최소 분석 단위는 `COMPLETED + valid profit_rate`, 거래수, blocker 분포, submitted/full/partial, sell_completed, soft/hard/trailing exit, GOOD_EXIT/MISSED_UPSIDE, owner contamination 여부다.
   - threshold 변경이 없던 날도 baseline 유지 결과로 제출한다.

4. `실적 기반 다음 가중치 미세조정`
   - 장후 실적 결과는 다음 threshold 산정의 weight 입력으로 들어가야 한다.
   - weight는 실시간으로 바꾸지 않고 장후 배치에서만 갱신한다.
   - 같은 family 안에서도 손익만 보지 않고 opportunity cost, blocker 감소, 체결 품질, post-exit MFE/MAE를 같이 반영한다.
   - `statistical_action_weight`는 이 단계의 보조 weight source로 사용한다. 가격대/거래량/시간대별 best action이 sample floor를 충족할 때만 다음 threshold 추천의 가중치 입력으로 반영한다.
   - 단일축 canary 원칙을 깨지 않도록 최종 live 적용은 다음 장전 1축 owner로 제한한다.

## 일일 산정 산출물

장후 배치가 남겨야 할 산출물은 아래 4종으로 고정한다.

1. `threshold_snapshot`
   - family별 현행값, 추천값, 상하한, sample count, 적용 가능 여부

2. `threshold_diff_report`
   - `current -> recommended` 변화량, 변화 이유, 예상 blocker 감소/증가, 후행 손익 변화

3. `apply_candidate_list`
   - 다음 장전 live 후보 1축과 observe/shadow 유지축 분리

4. `rollback_guard_pack`
   - 신규 추천값 적용 시 감시할 `loss_cap`, `quality regression`, `cross-contamination`, `sample insufficiency` 조건

## Threshold Family별 적용 원칙

1. `entry`
   - `mechanical_momentum`, VPW, liquidity, AI threshold, pre-submit price guard는 같은 family로 묶지 않고 개별 owner로 본다.
   - 다음 장전에는 이 중 하나만 live 완화/강화 후보가 된다.

2. `holding/exit`
   - `soft_stop_micro_grace`, `soft_stop_expert_defense`, `bad_entry_block`, `REVERSAL_ADD`, trailing은 서로 outcome contamination이 크므로 동시 live 변경을 금지한다.

3. `position sizing`
   - `PYRAMID`, `AVG_DOWN`, `partial de-risk`는 수량/평단/후행 손익 계산을 바꾸므로 threshold family보다 한 단계 보수적으로 다룬다.
   - 표본이 충분해도 먼저 `would_qty`와 shadow PnL로만 본다.

4. `decision support`
   - `statistical_action_weight`는 threshold family와 live canary 사이에 있는 decision-support 축이다.
   - 리포트는 만들지만 직접 runtime threshold를 바꾸지 않는다.
   - 장후 weight 산정에는 쓸 수 있으나, 다음 장전 live 적용은 반드시 별도 owner 항목과 rollback guard를 거친다.

## 로깅 보강 필요

- `REVERSAL_ADD`는 현재 first-fail reason만 남는다. 데이터 기반 완화값을 정확히 산정하려면 `pnl_ok`, `hold_ok`, `low_floor_ok`, `ai_ok`, `supply_ok`, 각 원시값을 한 이벤트에 모두 남겨야 한다.
- entry gate도 threshold별 `would_pass_at_candidate_threshold`를 남기면 장후 grid search가 빨라진다.
- soft stop 계열은 `touch_price`, `would_exit_price`, `max_rebound_10m`, `min_adverse_10m`가 연결되어야 grace/absorption threshold를 안정적으로 산정할 수 있다.
