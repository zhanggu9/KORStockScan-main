# Web API Spec Guide

KORStockScan 웹 대시보드와 Flutter 클라이언트가 공통으로 사용하는 JSON API 기준 문서입니다.

## 공통 원칙

- 기준 서버: `src/web/app.py`
- 기본 응답 형식은 `application/json`
- `date`를 생략하면 서버 현재 날짜를 사용합니다.
- `since`를 생략하면 대시보드와 동일하게 최근 2시간 기본 오프셋이 적용될 수 있습니다.

## 주요 엔드포인트

- `/api/daily-report?date=YYYY-MM-DD`
- `/api/entry-pipeline-flow?date=YYYY-MM-DD&since=HH:MM:SS&top=10`
- `/api/trade-review?date=YYYY-MM-DD&code=000000`
- `/api/strategy-performance?date=YYYY-MM-DD`
- `/api/gatekeeper-replay?date=YYYY-MM-DD&code=000000&time=HH:MM:SS`
- `/api/performance-tuning?date=YYYY-MM-DD&since=HH:MM:SS`

## `/api/entry-pipeline-flow`

용도:

- 종목별 최신 진입 시도 흐름
- 마지막 차단/대기 상태
- 마지막 확정 진입 실패 지점

### 쿼리 파라미터

- `date`: 조회 날짜
- `since`: `HH:MM` 또는 `HH:MM:SS`
- `top`: 상위 표시 row 수

### 최신 동작 기준

- `recent_stocks`는 `(종목명, 종목코드)` 단위로 보여주되, 같은 날 재진입이 있으면 `최신 시도 세그먼트`만 반환합니다.
- 이전 주문 제출 시도의 `order_bundle_submitted`와 현재 재진입 시도의 `latency_block` 같은 상태를 한 row에 섞지 않습니다.
- 가능하면 로그의 `RecommendationHistory id`를 함께 써서 시도를 더 안정적으로 구분합니다.

### 핵심 응답 필드

- `date`: 집계 날짜
- `since`: 실제 적용된 시각 필터
- `metrics.total_events`: 집계된 `ENTRY_PIPELINE` 이벤트 수
- `sections.recent_stocks[]`: 종목별 최신 시도 요약

`sections.recent_stocks[]` 내부 주요 필드:

- `name`, `code`
- `record_id`: 최신 시도에 대응하는 `RecommendationHistory.id`
- `attempt_started_at`: 최신 시도 세그먼트의 첫 이벤트 시각
- `latest_timestamp`: 최신 이벤트 시각
- `latest_stage`, `latest_stage_label`
- `stage_class`: `progress`, `blocked`, `waiting`, `submitted`
- `pass_flow[]`: 최신 시도에서 확정 통과한 단계
- `precheck_passes[]`: 확정 진입 전 예비 통과 이력
- `latest_status`: 마지막 상태 요약
- `confirmed_failure`: 최신 시도 기준 마지막 확정 진입 실패
- `events[]`: 최신 시도 세그먼트의 최근 이벤트 목록

### 응답 예시

```json
{
  "date": "2026-04-07",
  "since": "2026-04-07 10:00:00",
  "metrics": {
    "total_events": 128,
    "tracked_stocks": 14
  },
  "sections": {
    "recent_stocks": [
      {
        "name": "엘지전자",
        "code": "066570",
        "record_id": "12841",
        "attempt_started_at": "2026-04-07 10:02:11",
        "latest_timestamp": "2026-04-07 10:02:19",
        "latest_stage": "latency_block",
        "stage_class": "blocked",
        "pass_flow": [
          {"stage": "watching", "label": "감시중", "kind": "start"},
          {"stage": "ai_confirmed", "label": "AI 확답", "kind": "pass"},
          {"stage": "entry_armed", "label": "진입 자격 확보", "kind": "pass"},
          {"stage": "budget_pass", "label": "수량 계산 통과", "kind": "pass"}
        ],
        "latest_status": {
          "stage": "latency_block",
          "label": "지연 리스크 차단",
          "kind": "blocked",
          "reason": "latency_state_danger",
          "reason_label": "지연 리스크 위험구간",
          "timestamp": "2026-04-07 10:02:19"
        },
        "confirmed_failure": {
          "stage": "latency_block",
          "label": "지연 리스크 차단",
          "timestamp": "2026-04-07 10:02:19"
        }
      }
    ]
  }
}
```

## 운영 메모

- 백엔드 Python 코드 변경 후 현재 systemd 서비스는 `ExecReload`가 없으므로 `sudo systemctl restart korstockscan-gunicorn.service`를 사용합니다.
- 배포 직후에는 `/api/entry-pipeline-flow?date=YYYY-MM-DD&top=1`로 `record_id`, `attempt_started_at` 포함 여부를 확인하면 최신 코드 반영 여부를 빠르게 점검할 수 있습니다.
