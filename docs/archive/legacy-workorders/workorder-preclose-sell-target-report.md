# 작업지시서: 15:00 장마감 전 내일 매도 목표 종목 선정 리포트

> 작성일: 2026-04-15
> 슬롯: POSTCLOSE 착수 → 구현 후 다음 영업일 15:00 첫 실행
> 목표: 매일 15:00 KST 기준으로 당일 보유/관심 종목 중 익일 매도 목표 후보를 선정하고 리포트를 생성한다.

---

## 1. 목적 및 배경

### 기존 리포트와의 차이

| 구분 | 기존 EOD 리포트 | 기존 아침 리포트 | 이번 신규 리포트 |
|---|---|---|---|
| 파일 | `eod_analyzer.py` | `daily_report_service.py` | `preclose_sell_target_report.py` (신규) |
| 실행 방식 | bot_main 스케줄러 (15:40) | bot_main 스케줄러 (08:45) | **크론탭 독립 실행 / 수동 1회성 실행 모두 가능** |
| 목적 | 내일 매수할 종목 5개 | 오늘 추천 종목 현황 | **내일 매도 목표 종목 선정** |
| 입력 | 일봉 DB (최근 5일) | 일봉 DB (60일) + ML 모델 | HOLDING 종목(DB) + T-1 ML 스코어(CSV) + 당일 일봉 |
| 출력 | recommendation_history 저장 + Telegram | JSON 파일 + Telegram | **Markdown 리포트 파일 + Telegram** |

### 신규 리포트가 답해야 하는 질문

> "지금 보유 중이거나 오늘 진입 검토 중인 종목 중, **내일 시가~오전 중 매도**를 목표로 삼을 최우선 후보는 무엇인가?"

후보군은 두 트랙으로 구성된다:
- **Track A (보유 정리)**: 현재 HOLDING 상태인 종목 중 오버나이트 유지 후 익일 매도가 유리한 종목
- **Track B (신규 스윙 진입)**: 오늘 일봉 기준 진입하여 익일 매도를 노리는 모멘텀 종목 (T-1 ML 스코어 + 당일 일봉 필터)

---

## 2. 실행 방식: 독립 스크립트 (크론탭 / 수동)

### bot_main.py와 완전 분리

이 스크립트는 bot_main.py에 통합하지 않는다.
`python preclose_sell_target_report.py` 단독 실행으로 완결된다.

### 크론탭 등록 예시

```cron
# 매 영업일 15:00 KST (UTC+9) 실행
0 6 * * 1-5 cd /home/ubuntu/KORStockScan && /home/ubuntu/KORStockScan/.venv/bin/python src/scanners/preclose_sell_target_report.py >> /home/ubuntu/KORStockScan/logs/preclose_sell_target.log 2>&1
```

### 수동 실행

```bash
cd /home/ubuntu/KORStockScan
python src/scanners/preclose_sell_target_report.py
```

### `__main__` 진입점 구조

```python
if __name__ == "__main__":
    run_preclose_sell_target_report()
```

`run_preclose_sell_target_report()`는 Public API로도 노출하되, 직접 실행과 import 실행 모두 동일하게 작동해야 한다.

---

## 3. 의존성 및 순환참조 방지

### Import 허용 대상 (신규 파일에서 import 가능)

```
src/database/db_manager.py          ← DB 조회 전용
src/database/models.py              ← RecommendationHistory, DailyStockQuote 참조
src/core/event_bus.py               ← Telegram 전송
src/utils/constants.py              ← TRADING_RULES (Tier3 모델명 등)
src/utils/logger.py                 ← 로깅
```

### Import 금지 대상 (순환참조 또는 불필요한 결합)

```
src/bot_main.py                     ← 금지: 독립 실행 스크립트에서 bot_main 참조 불필요
src/scanners/eod_analyzer.py        ← 금지: 별도 로직이므로 재사용 불필요
src/engine/daily_report_service.py  ← 금지: ML 모델 전체 로드 불필요
src/engine/ai_engine.py             ← 금지: GeminiSniperEngine 클래스 초기화가 무거움
                                              google.genai 직접 호출로 대체
```

### AI 호출 방침

- `GeminiSniperEngine`을 import하면 `ai_engine.py → macro_briefing_complete.py` 전체 초기화가 발생한다.
- 이 스크립트는 독립 실행이 목적이므로 **`google.genai` 직접 호출**로 구현한다.
- 모델명은 `src/utils/constants.py`의 `TRADING_RULES.AI_MODEL_TIER3`에서 가져온다.

```python
# constants.py 기준 Tier3 모델
# AI_MODEL_TIER3 = "models/gemini-3.1-pro-preview-customtools"
from src.utils.constants import TRADING_RULES
MODEL = TRADING_RULES.AI_MODEL_TIER3
```

### 의존성 다이어그램

```
preclose_sell_target_report.py   (독립 실행 / 크론탭)
    ├─→ src/database/db_manager.py
    ├─→ src/database/models.py
    ├─→ src/core/event_bus.py
    ├─→ src/utils/constants.py      (TRADING_RULES.AI_MODEL_TIER3)
    ├─→ src/utils/logger.py
    └─→ google.genai                (Tier3 직접 호출)

# 존재하지 않아야 하는 방향
preclose_sell_target_report.py  --X-->  bot_main.py
preclose_sell_target_report.py  --X-->  eod_analyzer.py
preclose_sell_target_report.py  --X-->  daily_report_service.py
preclose_sell_target_report.py  --X-->  ai_engine.py (GeminiSniperEngine)
```

---

## 4. daily_recommendations_v2.csv 활용 방법 (T-1 스코어)

### CSV 생성 타이밍과 15:00 활용 가능성

```
전날 21:32 KST   daily_recommendations_v2.csv 생성 (T-1 기준)
                 예: 2026-04-14 21:32 → date 컬럼 = "2026-04-14"

오늘 08:45       아침 리포트가 동일 CSV의 T-1 스코어로 생성됨

오늘 15:00       CSV 로드 시 date = "2026-04-14" 데이터 (전날 종가 기준)
                 오늘(2026-04-15) 기준 CSV는 오늘 밤에 생성되므로 존재하지 않음
```

**결론: 15:00에는 T-1 스코어(전일 종가 기준)만 사용 가능하다. 이를 설계에 명시적으로 반영한다.**

### 활용 전략

T-1 스코어는 **진입 품질 필터**로만 사용하고, **당일 모멘텀 판단**은 DB의 최신 일봉 데이터로 보완한다.

| 데이터 | 출처 | 역할 |
|---|---|---|
| T-1 ML score | `daily_recommendations_v2.csv` (전날 생성) | Track B 진입 품질 gate — score 임계값 이상만 후보 포함 |
| 당일 일봉 (종가 기준) | `daily_stock_quotes` DB (quote_date = 오늘) | 실제 모멘텀 판단 — 정배열, RSI, BB, 수급 방향 |

```python
def _load_t1_ml_scores() -> dict[str, float]:
    """
    daily_recommendations_v2.csv에서 T-1 스코어 로드.
    date 컬럼은 전날 날짜다 — today()와 비교하지 않고 가장 최근 날짜를 사용한다.
    """
    csv_path = Path("data/daily_recommendations_v2.csv")
    if not csv_path.exists():
        return {}  # Track B는 T-1 스코어 없이 DB만으로 진행
    df = pd.read_csv(csv_path)
    # 날짜 필터 없이 가장 최근 date의 데이터를 사용 (T-1 기준이 맞음)
    latest_date = df["date"].max()
    latest_df = df[df["date"] == latest_date]
    return dict(zip(latest_df["code"].astype(str), latest_df["score"]))
```

> `date == today()` 비교를 하지 않는다. 오늘 CSV가 없을 때도 전날 CSV로 graceful하게 동작한다.

### CSV 없을 때 (graceful degradation)

- CSV 로드 실패 또는 빈 dict → Track B를 DB 데이터만으로 실행 (T-1 score = 0.0으로 fallback)
- Track A (HOLDING 종목)는 CSV와 무관하게 항상 실행

---

## 5. 데이터 흐름 상세

### 5-1. Track A: 보유 정리 후보 (HOLDING)

```sql
-- 오늘 HOLDING 상태인 모든 종목 + 최신 일봉 조인
SELECT r.stock_code, r.stock_name, r.buy_price, r.profit_rate,
       r.position_tag, r.strategy, r.trade_type,
       q.close_price, q.volume, q.ma20, q.rsi,
       q.bbu, q.bbl, q.foreign_net, q.inst_net
FROM recommendation_history r
JOIN daily_stock_quotes q
  ON r.stock_code = q.stock_code
 AND q.quote_date = (SELECT MAX(quote_date) FROM daily_stock_quotes)
WHERE r.status IN ('HOLDING', 'BUY_ORDERED')
  AND r.rec_date = CURDATE()
ORDER BY r.profit_rate DESC
```

**스코어링 기준 (Track A)**:

| 항목 | 가중치 | 설명 |
|---|---|---|
| 현재 수익률 | 40% | profit_rate > 0 우선. 손실 중이면 익일 조기 손절 관점으로 분류 |
| 모멘텀 지속성 | 30% | 종가 > MA20, RSI 55~75 구간 |
| 수급 방향 | 20% | foreign_net + inst_net 방향성 (최신 일봉 기준) |
| BB 위치 | 10% | (close - bbl) / (bbu - bbl): 0.6 이상이면 익일 눌림 위험 |

출력 분류:
- `SELL_TOMORROW_STRONG`: 수익률 양호 + 모멘텀 지속 → 익일 시가 목표 매도 검토
- `HOLD_MONITOR`: 수익률 중립 + 모멘텀 불명확 → 장전 재판단 필요
- `CUT_LOSS_CONSIDER`: 손실 중 + 모멘텀 하락 → 익일 조기 정리 검토

### 5-2. Track B: 신규 스윙 진입 후보 (풀 크기: 10개)

```python
# 1단계: T-1 ML 스코어가 있는 종목을 품질 gate로 사용
t1_scores = _load_t1_ml_scores()   # {stock_code: score}

# 2단계: DB에서 당일 기술적 조건 필터링
# - 정배열 (close > ma20)
# - RSI 골든존 (50 <= rsi <= 72)
# - 수급 동시 매수 (foreign_net > 0 AND inst_net > 0)
db_candidates = _fetch_daily_quote_candidates(db)

# 3단계: T-1 스코어 병합 후 복합 스코어 정렬 → 상위 10개
for row in db_candidates:
    row["t1_score"] = t1_scores.get(row["stock_code"], 0.0)

ranked = sorted(db_candidates, key=_score_swing, reverse=True)[:10]
```

**복합 스코어 계산 (Track B)**:

| 항목 | 가중치 | 설명 |
|---|---|---|
| T-1 ML score | 35% | CSV의 score (없으면 0.0, 다른 항목으로 선발 가능) |
| BB 스퀴즈 | 25% | `1 - (bbu - bbl) / close`: 값이 클수록 응축 심화 |
| 수급 동시 매수 | 25% | foreign_net > 0 AND inst_net > 0 → 1.0 / 아니면 0.0 |
| RSI 위치 | 15% | 50~65 구간 = 1.0, 66~72 = 0.5, 그 외 = 0.0 |

---

## 6. 파일 구조 및 함수 설계

### 파일: `src/scanners/preclose_sell_target_report.py`

```python
"""
preclose_sell_target_report.py

15:00 KST 기준 익일 매도 목표 종목 선정 리포트.
크론탭 또는 수동으로 단독 실행한다. bot_main.py와 무관하게 동작한다.

실행:
    python src/scanners/preclose_sell_target_report.py

크론탭:
    0 6 * * 1-5 cd /home/ubuntu/KORStockScan && .venv/bin/python src/scanners/preclose_sell_target_report.py

의존성:
    - src/database/db_manager.py
    - src/database/models.py
    - src/core/event_bus.py
    - src/utils/constants.py (TRADING_RULES.AI_MODEL_TIER3)
    - src/utils/logger.py
    - google.genai (직접 호출)

순환참조 금지:
    - bot_main, eod_analyzer, daily_report_service, ai_engine(GeminiSniperEngine) import 불가
"""

# --- Public API ---
def run_preclose_sell_target_report() -> None:
    """크론탭 / 수동 실행 진입점. 예외 발생 시 로그 후 종료."""

# --- 데이터 수집 ---
def _fetch_holding_candidates(db: DBManager) -> list[dict]:
    """Track A: 오늘 HOLDING/BUY_ORDERED 종목 조회 + 최신 일봉 조인"""

def _fetch_daily_quote_candidates(db: DBManager) -> list[dict]:
    """Track B용 DB 후보: 정배열 + RSI 골든존 + 수급 동시 매수 종목"""

def _load_t1_ml_scores() -> dict[str, float]:
    """daily_recommendations_v2.csv에서 T-1 스코어 로드 (가장 최근 date 기준)"""

# --- 스코어링 ---
def _score_holding(row: dict) -> dict:
    """Track A 복합 스코어 + label(SELL_TOMORROW_STRONG / HOLD_MONITOR / CUT_LOSS_CONSIDER) 반환"""

def _score_swing(row: dict) -> float:
    """Track B 복합 스코어 (T-1 ML 35% + BB스퀴즈 25% + 수급 25% + RSI 15%)"""

# --- AI 호출 ---
def _call_gemini_preclose(
    holding_candidates: list[dict],
    swing_candidates: list[dict],
) -> dict:
    """
    google.genai 직접 호출 (TRADING_RULES.AI_MODEL_TIER3 사용).
    GeminiSniperEngine import 없이 독립 구현.
    반환: {"sell_targets": [...], "summary": str, "market_caution": str}
    """

# --- 출력 ---
def _render_markdown(result: dict, report_date: str) -> str:
    """Markdown 리포트 문자열 생성"""

def _save_report(markdown: str, report_date: str) -> Path:
    """data/report/preclose_sell_target_YYYY-MM-DD.md 저장"""

def _broadcast_telegram(markdown: str) -> None:
    """EventBus를 통해 Telegram VIP_ALL 전송"""

# --- 진입점 ---
if __name__ == "__main__":
    run_preclose_sell_target_report()
```

---

## 7. Gemini 프롬프트 설계

```python
PRECLOSE_SELL_TARGET_PROMPT = """
너는 한국 주식 단기 트레이더다.
오늘 15:00 기준으로 내일 매도를 목표로 하는 종목을 선정한다.

[참고: 입력 데이터 특성]
- Track A 보유 종목은 오늘 현재 HOLDING 상태이며, 오버나이트 유지 후 익일 매도 여부를 판단한다.
- Track B 후보는 오늘 일봉 기준 기술적 조건을 충족하며, T-1(전일) ML 스코어로 품질을 검증했다.
  T-1 스코어는 전날 종가 기준으로 생성된 ML 예측값이므로 오늘 시장 변화를 반영하지 않는다.
  따라서 당일 일봉 지표(RSI, BB, 수급)를 T-1 스코어보다 우선하여 판단한다.

[입력 데이터 A - 현재 보유 종목]
{holding_json}

[입력 데이터 B - 신규 스윙 진입 후보 (상위 10개)]
{swing_json}

[판단 기준]
1. 익일 시가~오전 매도가 유리한 종목을 최대 5개 선정한다.
2. Track A는 현재 수익률, 모멘텀 지속성, 수급 방향을 종합하여 SELL/HOLD/CUT_LOSS를 판정한다.
3. Track B는 당일 BB 스퀴즈 + 수급 동시 매수를 우선하고, T-1 ML 스코어는 보조 신호로 참고한다.
4. 익일 되돌림 리스크(BB 상단 근접, RSI 70 초과, 외인/기관 이탈)가 있는 종목은 제외한다.
5. 각 종목별로 매도 근거 1줄과 리스크 1줄을 명시한다.

[출력 형식 - JSON only, 다른 텍스트 출력 금지]
{
  "sell_targets": [
    {
      "rank": 1,
      "stock_code": "000100",
      "stock_name": "유한양행",
      "track": "A",
      "sell_rationale": "익일 시가 강세 기대, 수급 3일 연속 매수",
      "risk_note": "RSI 68로 단기 과열 주의",
      "sell_timing": "익일 09:05~09:30 시초가 근처",
      "confidence": 78
    }
  ],
  "summary": "오늘 장 막판 모멘텀 강세 종목 중심, 익일 오전 차익 실현 전략",
  "market_caution": "시장 전반 과열 여부 또는 주의 사항 1줄"
}
"""
```

---

## 8. 리포트 출력 형식

### 파일 저장 경로

```
data/report/preclose_sell_target_YYYY-MM-DD.md
```

### Markdown 템플릿

```markdown
# 📋 [YYYY-MM-DD] 익일 매도 목표 종목 리포트 (15:00 기준)

> 생성시각: YYYY-MM-DD 15:00 KST | Track A: 보유 정리 | Track B: 신규 스윙 (T-1 ML + 당일 일봉)

## 시장 종합 판단
{market_caution}

## 익일 매도 목표 TOP 5

| 순위 | 종목 | 트랙 | 수익률 | 매도 타이밍 | 신뢰도 |
|---|---|---|---|---|---|
| 1 | 유한양행 (000100) | A(보유) | +3.2% | 익일 09:05~09:30 | 78 |
| 2 | LG유플러스 (032640) | B(스윙) | — | 익일 09:00~09:20 | 65 |

### 1위: 유한양행 (000100) [Track A — 보유 정리]
- **매도 근거**: 익일 시가 강세 기대, 수급 3일 연속 매수
- **리스크**: RSI 68로 단기 과열 주의

### 2위: LG유플러스 (032640) [Track B — 신규 스윙]
- **매도 근거**: BB 스퀴즈 + 외인/기관 동시 매수
- **리스크**: T-1 ML 스코어가 어제 기준이므로 오늘 시장 변화 주의

## 전략 요약
{summary}

---
*본 리포트는 15:00 스냅샷 기준. Track B의 T-1 ML 스코어는 전일(YYYY-MM-DD) 종가 기준입니다.*
*이후 장중 변동 및 오늘 밤 생성되는 오늘 기준 ML 스코어는 반영되지 않습니다.*
```

### Telegram 축약 메시지

```
📋 [익일 매도 목표] YYYY-MM-DD 15:00 기준

🎯 *TOP 5 선정 완료*
1. 유한양행(000100) [보유] — 익일 09:05~09:30 / 신뢰도 78
2. LG유플러스(032640) [스윙] — 익일 09:00~09:20 / 신뢰도 65

⚠️ {market_caution}
📄 상세: data/report/preclose_sell_target_YYYY-MM-DD.md
```

---

## 9. 확정된 파라미터

| 항목 | 확정값 | 비고 |
|---|---|---|
| 실행 방식 | 크론탭 / 수동 단독 실행 | bot_main.py 통합 제외 |
| Gemini 모델 | `TRADING_RULES.AI_MODEL_TIER3` | `models/gemini-3.1-pro-preview-customtools` |
| Track B 풀 크기 | **10개** | DB 후보 상위 10개 → Gemini 입력 |
| T-1 CSV 없을 때 | DB만으로 Track B 실행 (score=0.0 fallback) | graceful degradation |
| Telegram 채널 | VIP_ALL | 기존 EOD와 동일 |
| DB 저장 | 1차 미포함 (파일 저장만) | 2차 구현 시 추가 |

---

## 10. 테스트 포인트

### 단위 테스트 (`src/tests/test_preclose_sell_target_report.py`)

| 테스트 | 검증 내용 |
|---|---|
| `test_load_t1_scores_latest_date` | CSV에서 최신 date 기준으로 스코어 로드, today() 비교 안 함 |
| `test_load_t1_scores_missing_csv` | CSV 없으면 빈 dict 반환, 예외 없음 |
| `test_fetch_holding_empty` | HOLDING 종목 없을 때 빈 리스트 반환 |
| `test_score_holding_strong` | profit_rate > 0, RSI < 70 → `SELL_TOMORROW_STRONG` |
| `test_score_holding_loss` | profit_rate < -2% → `CUT_LOSS_CONSIDER` |
| `test_score_swing_ranking` | T-1 score 높음 + BB 스퀴즈 + 수급 동시 매수 → 상위 순위 |
| `test_score_swing_no_t1` | T-1 score 없어도 DB 지표만으로 스코어 계산 |
| `test_render_markdown_t1_disclaimer` | 출력 Markdown에 T-1 기준 안내 문구 포함 확인 |
| `test_save_report_path` | `data/report/preclose_sell_target_YYYY-MM-DD.md` 경로 |
| `test_no_heavy_import` | `ai_engine`, `bot_main`, `eod_analyzer`, `daily_report_service` import 없음 확인 |

### 수동 검증

```bash
# import 오류 없음 확인
python -c "from src.scanners.preclose_sell_target_report import run_preclose_sell_target_report"

# 테스트 실행
python -m pytest src/tests/test_preclose_sell_target_report.py -v

# 실제 실행 (리포트 생성 + Telegram 전송 확인)
python src/scanners/preclose_sell_target_report.py
```

---

## 11. 롤백

- 크론탭에서 해당 줄을 주석 처리하면 즉시 비활성화
- bot_main.py 변경이 없으므로 봇 재시작 불필요

---

## 12. 구현 순서 (권장)

1. `src/scanners/preclose_sell_target_report.py` 신규 작성
   - `_load_t1_ml_scores` (CSV T-1 로드, latest date 기준)
   - `_fetch_holding_candidates` (DB 조회)
   - `_fetch_daily_quote_candidates` (DB 후보, 상위 10개 반환)
   - `_score_holding`, `_score_swing` 구현
   - `_call_gemini_preclose` (google.genai 직접 호출, TIER3)
   - `_render_markdown`, `_save_report` 구현
   - `_broadcast_telegram` (EventBus 재사용)
   - `run_preclose_sell_target_report` + `if __name__ == "__main__":` 조립

2. `src/tests/test_preclose_sell_target_report.py` 작성 및 통과

3. 크론탭 등록

4. dry-run 확인 → 파일 생성 + Telegram 전송 확인

---

## 참고 문서

- [eod_analyzer.py](../src/scanners/eod_analyzer.py) — 1차 필터링 로직 참조
- [bot_main.py](../src/bot_main.py) — EventBus / Telegram 전송 패턴 참조
- [models.py](../src/database/models.py) — RecommendationHistory 스키마
- [constants.py](../src/utils/constants.py) — `TRADING_RULES.AI_MODEL_TIER3` 위치
- [daily_recommendations_v2.csv](../data/daily_recommendations_v2.csv) — T-1 ML 스코어 소스 (전날 21:30경 생성)
