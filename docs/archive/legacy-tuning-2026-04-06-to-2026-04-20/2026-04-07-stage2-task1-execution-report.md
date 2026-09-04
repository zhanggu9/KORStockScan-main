# 2단계 1차 작업 결과서: 보유 AI `sig_delta` 분해

**작업일**: 2026-04-07  
**상태**: ✅ 완료  
**범위**: 2단계 첫 작업 `sig_changed` 원인 분해

---

## 작업 목적

- 보유 AI fast reuse가 왜 자주 깨지는지 `reason_codes` 수준이 아니라 필드 수준으로 확인한다.
- `sig_changed`의 주 원인이 `curr`, `spread`, `buy_ratio` 같은 미세 WS 변화인지 대시보드에서 바로 읽을 수 있게 만든다.
- 다음 단계인 fast signature 완화 검토와 shadow band 로그 설계의 입력값을 확보한다.

---

## 반영 내용

### 1. 리포트 집계 확장

- [sniper_performance_tuning_report.py](../src/engine/sniper_performance_tuning_report.py)
  - `sig_delta` 문자열에서 필드명만 추출하는 `_count_sig_delta_fields()` 추가
  - `ai_holding_reuse_bypass` 이벤트에서 `holding_sig_deltas` Counter 집계 추가
  - API 응답 `breakdowns.holding_sig_deltas` 추가

### 2. 대시보드 UI 추가

- [app.py](../src/web/app.py)
  - `보유 AI 재사용 차단 사유` 카드 추가
  - `보유 AI 시그니처 변경 필드` 카드 추가

### 3. 테스트 보강

- [test_performance_tuning_report.py](../src/tests/test_performance_tuning_report.py)
  - 기본 리포트 테스트에 보유 AI `sig_delta` 검증 추가
  - `test_holding_sig_delta_parsing()` 신규 추가

---

## 테스트 결과

### 자동 테스트

1. `./.venv/bin/python -m pytest src/tests/test_performance_tuning_report.py`
   - 결과: `4 passed in 0.70s`

2. `./.venv/bin/python -m py_compile src/engine/sniper_performance_tuning_report.py src/web/app.py`
   - 결과: 문법 오류 없음

### 서비스 반영 확인

1. `sudo systemctl restart korstockscan-gunicorn.service`
   - 결과: `2026-04-07 15:16:43 KST` 재기동 완료

2. `curl -sS 'http://127.0.0.1:5000/api/performance-tuning?date=2026-04-07&since=09:00:00'`
   - 결과: `breakdowns.holding_sig_deltas` 응답 확인

---

## 2026-04-07 라이브 확인 결과

### 보유 AI 재사용 차단 사유

- `시그니처 변경 9`
- `안전수익 경계 5`
- `재사용 창 만료 4`
- `가격 변화 확대 1`

### 보유 AI 시그니처 변경 상위 필드

- `curr 7`
- `spread 4`
- `ask_bid_balance 2`
- `depth_balance 2`
- `tick_trade_value 1`
- `fluctuation 1`
- `v_pw 1`

### 해석

1. 현재 보유 AI fast signature에서 `sig_changed`를 가장 많이 만드는 필드는 `curr`, `spread`다.
2. 즉시 다음 분석 대상으로 `curr` / `spread`의 bucket 완화 가능성을 검토할 근거가 생겼다.
3. 다만 `안전수익 경계`도 5건으로 적지 않아서, signature 완화만으로는 MISS 체감을 충분히 줄이지 못할 가능성이 있다.

---

## 결론

이번 작업으로 2단계 첫 질문인 "보유 AI `sig_changed`가 주로 어떤 필드에서 발생하는가"에 대한 가시성은 확보됐다. 이제 대시보드만 봐도 `curr`, `spread`가 상위 원인인지 바로 확인할 수 있고, 이후 완화 실험이 실제로 blocker 구조를 바꿨는지도 같은 화면에서 추적할 수 있다.

---

## 다음 작업과 진행 시점

### 바로 진행 가능한 작업

- `2026-04-08`부터 2단계 다음 작업 착수 가능
- 권장 순서:
  1. `curr`, `spread` 완화 후보를 fast signature 기준으로 분석
  2. `ai_holding_shadow_band` 장중 수집값 검증
  3. `near_ai_exit`, `near_safe_profit`이 실제 fresh review 강제 사유로 얼마나 큰지 수집

### 정책 변경 판단 시점

- `ai_holding_shadow_band`는 `2026-04-07` 코드 선반영 완료 상태다.
- 봇을 `2026-04-08` 장 시작 전 수동 재실행하면 최소 5거래일 수집 완료 시점은 `2026-04-14` 장마감이다.
- 따라서 fast signature 완화나 band 축소 같은 실제 운영 정책 변경은 가장 이르게는 `2026-04-15` 장 시작 전 검토가 적절하다.

### 왜 바로 정책 변경하지 않는가

1. `curr`, `spread`는 분명 상위 원인이지만 단일 날짜 표본만으로는 장중 변동성 구간 차이를 충분히 설명하기 어렵다.
2. `near_safe_profit`과 같은 band 강제 재평가가 함께 섞여 있으므로, signature만 완화하면 기대보다 효과가 작을 수 있다.
3. 이번 단계의 목적은 "원인 분해"였고, 다음 단계의 목적은 "완화 후보 검증"이다.

---

## 참고 문서

- [plan-korStockScanPerformanceOptimization.prompt.md](./plan-korStockScanPerformanceOptimization.prompt.md)
- [2026-04-07-performance-tuning-checklist.md](./2026-04-07-performance-tuning-checklist.md)
