# 2026-05-04 Symbol Follow-up Risk Report

## 판정

1. `지투파워(388050)` `ID 4988`은 실제 매수 체결이 복원되지 않은 상태에서 DB/report에 `COMPLETED`로 남은 정합성 의심 표본이다. 손익 표본에서는 `ID 4799`와 분리해야 한다.
2. `SK네트웍스(001740)`는 첫 매매 `ID 4738`과 두 번째 매매 `ID 4884` 모두 하향 가격 흐름에서 진입했고 soft stop 손실로 끝났다. entry report에서 하락 재진입 blocker로 추적해야 한다.
3. `피노(033790)` `ID 4810`은 장중에는 holding으로 보였지만 DB 기준 `11:17:20` `-1.93%` soft stop 완료다. 물타기 미도달 사유와 flow override 보류 후 손실 확대를 장후 분석 대상으로 둔다.

## 근거

### 지투파워 `388050`

| record_id | 상태 | 근거 |
| --- | --- | --- |
| `4799` | 정상 실거래 표본 | `10:50:32` 1주 체결 `16,730원`, `10:56:36` soft stop, DB profit `-1.78%` |
| `4988` | 분리 필요 | DB에는 `10:56:38` 매수, `10:58:26` 매도, `-0.23%`로 존재하지만 pipeline에는 신규 `holding_started`/`ENTRY_FILL`이 없고 `10:56:41` `0주 매도가능` 매도거절이 발생 |

해석:

- `ID 4988`은 같은 종목 동일 수량의 직전 포지션 종료 직후 생성된 revived/watch row 또는 상태 롤백 경로가 DB completed row로 오염됐을 가능성이 높다.
- 현재 1주 cap이라 실제 손실은 작지만, cap이 없었다면 `0주 매도가능`/상태 롤백/중복 completed가 대수량 포지션에서 손익 왜곡과 주문 재시도 리스크로 커질 수 있다.
- 장후 손익 계산은 `ID 4799`만 유효 실거래로 보고, `ID 4988`은 `receipt_mismatch_zero_sellable` 후보로 분리한다.

### SK네트웍스 `001740`

| record_id | 진입 | 청산 | 손익 | 핵심 문제 |
| --- | --- | --- | ---: | --- |
| `4738` | `09:15:06`, `6,650원` | `09:27:53`, `6,530원` | `-2.03%` | soft stop 전까지 `REVERSAL_ADD`는 `hold_sec_out_of_range`, `pnl_out_of_range`, `ai_recovered/soft_stop_zone`으로 막힘 |
| `4884` | `10:03:00`, `6,560원` | `11:01:36`, `6,460원` | `-1.75%` | 첫 손절가보다 낮은 가격에서 재진입했으나 다시 soft stop |

해석:

- 두 번째 진입가 `6,560원`은 첫 매도 `6,530원`보다 약간 높지만 첫 매수가 `6,650원` 대비 낮은 하향 구조다.
- 같은 종목 첫 손절 직후 재진입은 `same_symbol_repeat_loss`, `downtrend_reentry`, `post_soft_stop_reentry`로 report에서 분리해야 한다.
- `bad_entry_refined`는 보유/청산 canary라 제출 전 진입 자체를 막지 못한다. 향후 방어는 entry-side threshold/report로 `same-symbol post-loss cooldown`, `downtrend reentry gate`, `entry price trend veto`를 별도 후보로 봐야 한다.

### 피노 `033790`

| record_id | 진입 | 청산 | 손익 | 물타기 미도달 요약 |
| --- | --- | --- | ---: | --- |
| `4810` | `10:46:12`, `15,820원` | `11:17:20`, `15,550원` | `-1.93%` | 초기에는 AI/수급 회복 부족, 이후에는 `REVERSAL_ADD` 손실률/보유시간 범위 이탈 |

해석:

- `REVERSAL_ADD` 기준은 `pnl -0.70%~-0.10%`, `held_sec 20~180`, `AI>=60`, AI 회복/수급 조건이다.
- 피노는 `10:47~10:48` 구간에 시간/손실률 일부는 맞았지만 AI `55/53`과 수급 회복이 부족했다.
- 이후 `-1.11%~-1.55%` 구간은 손실이 너무 깊고, 보유시간도 `300초+`로 벗어나 물타기 대상이 아니었다.
- flow override는 `흡수/HOLD`로 soft stop 청산을 보류했지만 최종 `-1.93%`로 닫혔으므로, 보류가 손실 확대를 만든 표본인지 장후 `HoldingFlowOverride0504-Postclose`에서 분리한다.

## 다음 액션

- `지투파워 ID 4988`은 `COMPLETED + valid profit_rate` 손익 표본에서 바로 쓰지 말고, receipt/position reconciliation follow-up으로 분리한다.
- `SK네트웍스`는 entry-side `downtrend same-symbol reentry` blocker 후보로 추적한다. 이는 `bad_entry_refined` 조정만으로 막을 수 있는 축이 아니다.
- `피노`는 soft stop 후행 표본으로 `flow override defer -> max_defer/force_exit -> realized outcome`과 `REVERSAL_ADD blocked_reason`을 같이 본다.
