# 2026-04-20 Add-Position Axis Trader Review

## 1. 판정

1. 현재 스캘핑 추가매수 축은 `전부 OFF`가 아니다.
2. `불타기(PYRAMID)`는 이미 실전 ON이고, `물타기(AVG_DOWN)`와 `역전확인 추가매수(REVERSAL_ADD)`만 OFF다.
3. 따라서 트레이더 검토의 핵심은 `불타기 유지/물타기 보완`을 한 묶음으로 보되, 이번 주에는 실주문 변경 없이 `shadow readiness`만 닫는 것이다.
4. 현재 관찰축만으로도 물타기축 보완 가능성은 1차 판정할 수 있다. 다만 `좋은 종목 보유 연장 실패`와 `익절 후 동일종목 재진입 churn`은 전용 add-position 축이 아직 없어 별도 해석이 필요하다.

## 2. 현재 운영 상태

| 축 | 현재 상태 | 근거 |
| --- | --- | --- |
| `ENABLE_SCALE_IN` | ON | `src/utils/constants.py` |
| `PYRAMID` | ON | `SCALPING_MAX_PYRAMID_COUNT=2`, `SCALPING_PYRAMID_MIN_PROFIT_PCT=1.5` |
| `AVG_DOWN` | OFF | `SCALPING_ENABLE_AVG_DOWN=False`, `SCALPING_MAX_AVG_DOWN_COUNT=0` |
| `REVERSAL_ADD` | OFF | `REVERSAL_ADD_ENABLED=False` |
| `SCALP_LOSS_FALLBACK` | 실주문 OFF, observe-only 유지 | `SCALP_LOSS_FALLBACK_ENABLED=False`, `SCALP_LOSS_FALLBACK_OBSERVE_ONLY=True` |

## 3. 확인된 운영 근거

### 3-1. 불타기(PYRAMID)는 실전 ON

- 설정:
  - `ENABLE_SCALE_IN=True`
  - `SCALPING_MAX_PYRAMID_COUNT=2`
  - `SCALPING_PYRAMID_MIN_PROFIT_PCT=1.5`
- 코드:
  - `src/engine/sniper_scale_in.py`의 `evaluate_scalping_pyramid()`는 별도 enable 토글 없이 `count/profit` 조건으로 동작한다.
- 실로그:
  - `2026-04-20 09:12:47` 이수스페셜티케미컬 `ADD_SIGNAL type=PYRAMID reason=scalping_pyramid_ok`
  - `2026-04-20 09:25:16` 엑스게이트 `ADD_SIGNAL type=PYRAMID reason=scalping_pyramid_ok`
  - `2026-04-20 11:15:09` 이수페타시스 `ADD_SIGNAL type=PYRAMID reason=scalping_pyramid_ok` 직후 `ADD_BLOCKED reason=zero_qty buy_qty=1`

### 3-2. 물타기(AVG_DOWN)와 REVERSAL_ADD는 실전 OFF

- `SCALPING_ENABLE_AVG_DOWN=False`
- `SCALPING_MAX_AVG_DOWN_COUNT=0`
- `REVERSAL_ADD_ENABLED=False`
- 즉 현재 스캘핑 추가매수 개선 논의는 `새 물타기 로직을 지금 켠다`가 아니라, `기존 불타기 ON 상태를 유지한 채 물타기축을 shadow readiness로 재오픈할지`가 쟁점이다.

## 4. 현재 관찰축으로 이미 볼 수 있는 것

| 관찰축 | 현재 의미 | add-position 보완 판단에 주는 시사점 |
| --- | --- | --- |
| `same_symbol_repeat` | 동일종목 반복 진입 오염 확인 | 좋은 종목에서 재진입 churn이 구조적인지 확인 가능 |
| `same_symbol_soft_stop_cooldown_shadow` | soft-stop 뒤 재진입 차단 후보 확인 | 손실 재진입 억제가 add-position 보완보다 먼저인지 판단 가능 |
| `MISSED_UPSIDE / GOOD_EXIT / capture_efficiency` | 청산 품질과 승자 보유 품질 확인 | 더 오래 들고 갔어야 하는지, add-position보다 holding 품질 이슈인지 분리 가능 |
| `reversal_add_candidate` | 역전확인 추가매수 후보 로그 | REVERSAL_ADD를 켤 표본과 시간대 분포를 shadow 없이도 일부 판정 가능 |
| `buy_qty 분포 / zero_qty / add_judgment_locked` | 실제 체결 가능 수량과 판단 락 확인 | 물타기축을 열어도 수량/락 제약으로 실효성이 낮은지 사전 판정 가능 |

## 5. 현재 관찰축만으로 부족한 것

1. `익절 후 동일종목 재진입 churn` 전용 add-position 축이 없다.
2. `좋은 종목을 조금 익절한 뒤 더 들고 가거나 피라미딩했으면 기대값이 더 컸는지`를 전용 cohort로 묶는 축이 없다.
3. `횡보 후 재상승` 구간에서 `AVG_DOWN`이 유효했는지와 `HOLDING 연장`이 더 유효했는지를 같은 기준으로 비교하는 전용 표가 없다.

즉 현재 축만으로도 1차 해석은 가능하지만, 트레이더가 원하는 `불타기 vs 물타기 vs 그냥 더 보유` 비교는 아직 문서형 판정으로 분리돼 있지 않다.

## 6. 운영 상충 포인트

1. 이번 주 활성 플랜은 `split-entry leakage`와 `HOLDING shadow`가 최우선이다.
2. `불타기(PYRAMID)`가 이미 LIVE이므로 `AVG_DOWN` 또는 `REVERSAL_ADD`를 이번 주에 같이 실주문으로 열면 add-position 축 내부에서도 원인 귀속이 흐려진다.
3. 따라서 이번 주에는 `물타기축 readiness 판정`만 하고, 다음 주 `remote shadow-only` 여부만 결정하는 것이 현재 운영원칙과 맞다.

## 7. 트레이더 검토 포인트

1. 좋은 종목에서 `부분익절 -> 재진입 -> 손절 -> 재익절` churn이 반복될 때 우선 해법이 `불타기 강화`인지 `물타기 보완`인지 `보유 연장`인지
2. `buy_qty=1~2` 비중이 높은 종목군에서 물타기 설계가 실효성이 있는지
3. `PYRAMID` 최소 수량 보정이 먼저인지, `REVERSAL_ADD` 같은 방향성 확인 추가매수가 먼저인지
4. `soft-stop 반복 억제`가 add-position 보완보다 우선인지

## 8. 이번 주 일정 반영

1. `2026-04-23 POSTCLOSE`
   - `물타기축(AVG_DOWN/REVERSAL_ADD) 재오픈 일정 및 shadow 전제조건 확정`
   - 입력 자료: 이 문서 + `buy_qty 분포` + `reversal_add_candidate` + `add_judgment_locked`
2. `2026-04-24 POSTCLOSE`
   - `다음주 remote shadow-only 착수 승인 또는 보류`
   - 조건: `split-entry/HOLDING` 관찰축 비간섭, `buy_qty>=3` 비율, 후보 표본 충분성

## 9. 다음 액션

1. 이번 주에는 코드 변경 없이 `불타기 ON / 물타기 OFF` 상태를 유지한다.
2. `2026-04-23`에 이 문서를 트레이더 검토 입력으로 사용해 `물타기축 shadow readiness`만 판정한다.
3. `2026-04-24`에 다음 주 `remote shadow-only` 승인 또는 보류를 닫는다.
