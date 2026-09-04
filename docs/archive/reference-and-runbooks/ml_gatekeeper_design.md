# KOSPI_ML / KOSDAQ_ML WATCHING Gatekeeper 전환 설계안

## 목표
- `kiwoom_sniper_v2.py`의 `handle_watching_state()`에서 `KOSPI_ML`, `KOSDAQ_ML` 종목이 매수 직전 마지막 문지기(Gatekeeper)로 `ai_engine.generate_realtime_report()` 계열 판단을 사용하도록 전환한다.
- 기존 `# --- [3] 퀀트가 '매수'를 외쳤을 때만 AI 등판 ---` 구간의 `ai_engine.analyze_target(...)` 호출을 제거한다.
- Gatekeeper가 거부하면 동일 종목은 **2시간 쿨타임**에 들어간다.
- 프로그램 전체에서 `analyze_target()` 잔존 사용처를 확인하고, 더 이상 사용되지 않을 때만 삭제한다.

## 현재 코드 기준 사실관계
- `handle_watching_state()`의 `KOSPI_ML / KOSDAQ_ML` 분기에서는 여전히 `ai_engine.analyze_target(...)`를 호출해 점수 기반으로 진입을 막거나 허용한다. fileciteturn29file0
- `ai_engine.py`에는 이미 `generate_realtime_report()`가 있고, dict 기반 `realtime_ctx`를 받으면 `SCALP / SWING / DUAL` 프롬프트로 리포트를 생성한다. fileciteturn28file0
- `analyze_target()`는 현재 `execute_fast_track_scalp_v2`, `get_detailed_reason`, `get_realtime_ai_scores`, `handle_holding_state` 등 여러 곳에서 아직 사용 중이다. 따라서 이번 패치만으로는 삭제하면 안 된다. fileciteturn28file4turn29file0

## 이번 패치의 핵심 변경
1. `kiwoom_utils.py`
   - `build_realtime_analysis_context(...)` 추가
   - `ws_data + REST 보강 데이터 + 기존 퀀트 score/conclusion/metrics`를 합쳐 `generate_realtime_report()`용 표준 dict 생성

2. `ai_engine.py`
   - `extract_realtime_gatekeeper_action(report_text)` 추가
   - `evaluate_realtime_gatekeeper(...)` 추가
   - 내부적으로 `generate_realtime_report()`를 호출한 뒤 `[즉시 매수] / [눌림 대기] / [전량 회피] ...` 라벨을 추출해 `allow_entry`를 반환

3. `kiwoom_sniper_v2.py`
   - `KOSPI_ML / KOSDAQ_ML` WATCHING 진입부의 `analyze_target()` 호출 제거
   - 대신 `build_realtime_analysis_context(...)` → `evaluate_realtime_gatekeeper(..., analysis_mode='SWING')` 경로 사용
   - Gatekeeper가 `즉시 매수`가 아니면 2시간 쿨타임
   - AI 엔진 오류/미초기화는 별도 10분 쿨타임
   - 승인/거부 리포트는 텔레그램으로 발행 가능하도록 `_publish_gatekeeper_report(...)` 헬퍼 추가

## 진입 허용 규칙
- 허용: `action_label == "즉시 매수"`
- 거부: `눌림 대기`, `보유 지속`, `일부 익절`, `전량 회피`, `UNKNOWN`
- 거부 시: `cooldowns[code] = now + 7200`

## analyze_target 삭제 여부 결론
이번 패치 시점에서는 **삭제하지 않는다**.

이유:
- `execute_fast_track_scalp_v2()`에서 사용 중
- `get_detailed_reason()`에서 사용 중
- `get_realtime_ai_scores()`에서 사용 중
- `handle_holding_state()`의 SCALPING 보유 감시에서 사용 중

따라서 이번 작업의 범위는 **WATCHING 상태의 KOSPI_ML / KOSDAQ_ML 진입 Gatekeeper 교체**이며, `analyze_target()` 제거는 후속 리팩터링 과제로 분리하는 것이 안전하다.

## 적용 파일
- `ai_engine_gatekeeper.patch`
- `kiwoom_utils_gatekeeper.patch`
- `kiwoom_sniper_v2_gatekeeper.patch`

## 권장 적용 순서
1. `kiwoom_utils_gatekeeper.patch`
2. `ai_engine_gatekeeper.patch`
3. `kiwoom_sniper_v2_gatekeeper.patch`

## 검증 포인트
- `KOSPI_ML / KOSDAQ_ML` 종목이 WATCHING 상태에서 퀀트 score는 통과했지만 Gatekeeper가 `[눌림 대기]`를 내리면 2시간 쿨타임에 들어가는지
- Gatekeeper가 `[즉시 매수]`를 내리면 기존 매수 공통 로직까지 정상 연결되는지
- `analyze_target()` 기반 기존 기능(S15, 보유 AI 감시, 상세 사유, 실시간 일괄 점수)이 그대로 동작하는지
