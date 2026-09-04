# 2026-04-20 추가매수 수량 결정 로직 설명서 (트레이더 컨설팅용)

## 1) 핵심 판정

- 현재 로직은 **기존 보유수량(`buy_qty`)을 기준으로 템플릿 수량을 먼저 계산**한 뒤,
- 계좌 리스크 캡(`MAX_POSITION_PCT`)을 적용해 최종 수량을 확정한다.
- 따라서 보유수량이 너무 작으면(예: 1주) `PYRAMID`에서도 추가매수 수량이 `0주`가 될 수 있다.

## 2) 실행 흐름 (신호 -> 게이트 -> 수량 -> 주문)

1. `HOLDING` 종목에서 추가매수 공통 게이트를 통과해야 함  
   참고: [sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py:4105)
2. 전략별 추가매수 시그널 평가(`AVG_DOWN`, `PYRAMID`, `REVERSAL_ADD`)  
   참고: [sniper_scale_in.py](/home/ubuntu/KORStockScan/src/engine/sniper_scale_in.py:37)
3. 시그널이 생기면 `calc_scale_in_qty()`로 최종 수량 계산  
   참고: [sniper_scale_in.py](/home/ubuntu/KORStockScan/src/engine/sniper_scale_in.py:246)
4. 수량이 `0`이면 주문하지 않고 `ADD_BLOCKED reason=zero_qty` 로그 + 사용자 메시지 출력  
   참고: [sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py:4498)

## 3) 수량 계산식 (현재 운영 로직)

```text
입력: buy_qty, curr_price, deposit, strategy, add_type, add_reason

max_budget      = deposit * MAX_POSITION_PCT
current_value   = buy_qty * curr_price
remaining_budget= max(max_budget - current_value, 0)

ratio =
  SCALPING + AVG_DOWN(reversal_add_ok) -> REVERSAL_ADD_SIZE_RATIO (기본 0.33)
  SCALPING + 그 외(add_type=PYRAMID 포함) -> 0.50
  SWING   + AVG_DOWN -> 0.50
  SWING   + PYRAMID  -> 0.30

template_qty = int(buy_qty * ratio)        # 소수점 버림
cap_qty      = int((remaining_budget * 0.95) // curr_price)
qty          = min(template_qty, cap_qty)

최종 반환: qty >= 1 이면 qty, 아니면 0
```

코드 근거:
- [sniper_scale_in.py](/home/ubuntu/KORStockScan/src/engine/sniper_scale_in.py:259)
- [sniper_scale_in.py](/home/ubuntu/KORStockScan/src/engine/sniper_scale_in.py:279)
- [sniper_scale_in.py](/home/ubuntu/KORStockScan/src/engine/sniper_scale_in.py:285)

## 4) 현재 주요 설정값 (2026-04-20 기준)

- `ENABLE_SCALE_IN=True`
- `MAX_POSITION_PCT=0.20`
- `ADD_JUDGMENT_LOCK_SEC=20`
- `SCALE_IN_COOLDOWN_SEC=180`
- `SCALPING_ENABLE_AVG_DOWN=False`
- `SCALPING_MAX_AVG_DOWN_COUNT=0`
- `SCALPING_MAX_PYRAMID_COUNT=2`
- `SCALPING_PYRAMID_MIN_PROFIT_PCT=1.5`
- `REVERSAL_ADD_SIZE_RATIO=0.33`

참고:
- [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py:45)
- [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py:57)
- [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py:202)

## 5) 실제 사례 재현 (이수스페셜티케미컬, 2026-04-20 09:12:47)

로그:
- `ADD_SIGNAL ... type=PYRAMID reason=scalping_pyramid_ok`
- 직후 `ADD_BLOCKED ... reason=zero_qty deposit=8678470 curr_price=113400 buy_qty=1 add_type=PYRAMID`

참고:
- [sniper_state_handlers_info.log](/home/ubuntu/KORStockScan/logs/sniper_state_handlers_info.log:70247)
- [sniper_state_handlers_info.log](/home/ubuntu/KORStockScan/logs/sniper_state_handlers_info.log:70248)
- [bot_history.log](/home/ubuntu/KORStockScan/logs/bot_history.log:2018)

재현 계산:

```text
deposit      = 8,678,470
curr_price   = 113,400
buy_qty      = 1
add_type     = PYRAMID
strategy     = SCALPING
ratio        = 0.50

template_qty = int(1 * 0.5) = 0
max_budget   = 8,678,470 * 0.20 = 1,735,694
current_value= 1 * 113,400 = 113,400
remaining    = 1,622,294
cap_qty      = int((1,622,294 * 0.95) // 113,400) = 13
qty          = min(0, 13) = 0
=> zero_qty 차단
```

## 6) 트레이더 컨설팅 포인트

- 현재 설계는 "추가매수 크기 = 기존 포지션의 비율" 구조다.
- 결과적으로 초기 포지션이 작을수록(특히 1주) `PYRAMID`/`REVERSAL_ADD`가 사실상 비활성화될 수 있다.
- 고가주/소수주 포지션에서 신호는 발생해도 주문은 막히는 구조인지 확인이 필요하다.

## 7) 트레이더에게 확인할 의사결정 질문

1. `추가매수`를 기존 보유수량 기준으로 유지할지, 리스크 예산 기준(목표금액 기준)으로 바꿀지
2. `template_qty`가 0일 때 최소 1주를 허용할지 (`min_lot=1`) 또는 현재처럼 차단할지
3. `PYRAMID`와 `REVERSAL_ADD`의 수량정책을 동일하게 둘지, 서로 다른 최소 단위를 둘지
4. 고가주에서 1주 보유 상태일 때 추가매수 신호를 아예 만들지(신호 단계 차단) 또는 주문단에서만 차단할지
5. 기대값 기준으로 `체결 가능성`과 `평균단가 개선폭` 중 무엇을 우선 최적화할지

## 8) 주의사항

- `SCALPING_MAX_BUY_BUDGET_KRW`는 신규 진입(`WATCHING -> BUY`) 예산 캡에 쓰이며,
- 현재 `calc_scale_in_qty()`에는 직접 반영되지 않는다.

참고:
- [sniper_state_handlers.py](/home/ubuntu/KORStockScan/src/engine/sniper_state_handlers.py:2466)
- [constants.py](/home/ubuntu/KORStockScan/src/utils/constants.py:79)

## 9) 운영 반영 상태 (2026-04-20)

- 판정: 본 문서는 `로직 변경 지시서`가 아니라 `관찰/컨설팅 자료`로 유지한다.
- 현재 결정:
  - 코드 수정 없음
  - 현행 관찰축으로 표본 누적 후 유효성 판정
  - 개별 종목 판정 결과는 본 문서에 누적하지 않고 `plan + stage2 checklist`에만 반영
- 다음 변경 착수 조건:
  - `N_min`, `Δ_min`, `rollback trigger` 충족
  - 단일 축 canary 원칙(한 번에 한 축) 유지
