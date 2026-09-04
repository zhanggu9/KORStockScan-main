# 2026-04-27 진입병목 단일축 튜닝 감리 보고서

## 1. 감리 판정

진입병목 단일축 튜닝은 `gatekeeper_fast_reuse`, `other_danger-only normal override`, `ws_jitter-only relief replacement` 순서로 장중 검증했으나, 세 축 모두 `submitted/full/partial` 회복을 만들지 못했다.

따라서 단일 사유 residual을 더 붙드는 것은 기대값 개선보다 매몰 리스크가 크다. 현재 진입병목은 미해소 상태이며, 다음 live entry 축은 단일 residual이 아니라 `latency_quote_fresh_composite` 복합축으로 전환했다.

## 2. 단일축별 결과

| 축 | 적용/판정 | 핵심 결과 | 감리 의견 |
| --- | --- | --- | --- |
| `gatekeeper_fast_reuse` | 종료 | 10~11시 bundle에서 `gatekeeper_fast_reuse_ratio=0.0%`, `budget_pass_to_submitted_rate=0.2%` | 지연 진단 보조값으로는 유효하나 제출 회복축 아님 |
| `other_danger-only normal override` | 종료 | 13시 bundle `budget_pass=5628`, `submitted=9`, `budget_pass_to_submitted_rate=0.2%`, `latency_state_danger=5290` | `min_signal 90 -> 85` 완화에도 제출 효율 개선 없음 |
| `ws_jitter-only relief replacement` | 종료 | 15시 bundle `budget_pass=7568`, `submitted=11`, `budget_pass_to_submitted_rate=0.1%`, `latency_state_danger=7178` | absolute submitted는 늘었지만 효율은 악화. 단일 jitter 축으로는 direct 회복 실패 |

## 3. 복합축 전환 근거

`ws_jitter_1500` danger 분해는 `other_danger=3256`, `ws_age_too_high=2224`, `ws_jitter_too_high=2203` 순이었다. 단일 사유가 아니라 quote freshness family가 동시에 residual로 남은 형태다.

그래서 다음 확률 우선순위는 아래와 같이 본다.

1. `quote_fresh composite`: `ws_age/ws_jitter/spread/other_danger`가 겹친 복합축. 현재 적용.
2. `signal strength x quote freshness`: `low_signal` 완화만으로 실패했으므로 신호 강도와 quote 상태 교차축은 후속 후보.
3. `gatekeeper signature churn x quote freshness`: fast reuse 단독은 실패했지만 signature churn이 quote 상태 변화와 결합했을 가능성은 보조 분석 후보.

## 4. 복합축 선정 결과

선정축은 `latency_quote_fresh_composite`다. 선정 사유는 단일 residual 세 축이 모두 제출 회복을 만들지 못했고, 15:00 분해에서 `other_danger`, `ws_age_too_high`, `ws_jitter_too_high`가 동시에 커져 같은 quote freshness family의 복합 병목으로 보는 편이 가장 설명력이 높기 때문이다.

선정 조건:

- 적용 단계: entry latency 단계 한정
- 적용 방식: `REJECT_DANGER -> ALLOW_NORMAL` normal override
- 적용 태그: `SCANNER`, `VWAP_RECLAIM`, `OPEN_RECLAIM`
- 최소 신호: `signal>=88`
- quote 상한: `ws_age<=950ms`, `ws_jitter<=450ms`, `spread<=0.0075`, `quote_stale=False`
- 금지 경로: `fallback`, `fallback split-entry`, 전역 threshold 하향, 동일 entry 단계 canary 중복

비선정 축:

- `other_danger-only`: 13:00 판정에서 제출 효율이 개선되지 않아 단일축으로는 종료.
- `ws_jitter-only`: 15:00 판정에서 absolute submitted는 늘었지만 `budget_pass_to_submitted_rate`가 악화돼 종료.
- `gatekeeper_fast_reuse`: reuse ratio와 signature churn은 진단 보조값일 뿐, 제출 회복 직접축으로는 종료.
- `fallback/split-entry`: 보유청산의 물타기 또는 reversal add 튜닝이 성과를 낼수록 entry 이전 저품질 quote 상태에서 분할 진입하는 경로는 기대값 개선축이 아니라 원인귀속 오염과 partial/rebase 복잡도만 키우는 경로가 된다. 따라서 실행 경로는 유지 후보가 아니라 삭제 후보이며, 단기적으로는 과거 로그/영수증 호환과 폐기 경로 감지용 최소 코드만 남긴다.

감리 판정은 `선정 완료 / live canary 적용 대상 / 다음 bundle에서 효율 검증`이다. 다음 판정에서 `quote_fresh_composite_canary_applied` 표본의 `submitted/full/partial`, `budget_pass_to_submitted_rate`, `latency_state_danger`, `normal_slippage_exceeded`, `COMPLETED + valid profit_rate`가 동시에 개선되지 않으면 복합축도 종료한다.

## 5. 코드 적용 상태

적용 파일:

- `src/utils/constants.py`
- `src/engine/sniper_entry_latency.py`
- `src/engine/sniper_execution_receipts.py`
- `src/trading/entry/entry_policy.py`
- `src/trading/entry/entry_orchestrator.py`
- `src/tests/test_sniper_entry_latency.py`

신규 live entry canary:

- `SCALP_LATENCY_QUOTE_FRESH_COMPOSITE_CANARY_ENABLED=True`
- `SCALP_LATENCY_QUOTE_FRESH_COMPOSITE_MIN_SIGNAL_SCORE=88.0`
- `SCALP_LATENCY_QUOTE_FRESH_COMPOSITE_MAX_WS_AGE_MS=950`
- `SCALP_LATENCY_QUOTE_FRESH_COMPOSITE_MAX_WS_JITTER_MS=450`
- `SCALP_LATENCY_QUOTE_FRESH_COMPOSITE_MAX_SPREAD_RATIO=0.0075`

적용 방식은 `REJECT_DANGER -> ALLOW_NORMAL` normal override만 허용한다. `fallback`, `fallback split-entry`, `latency fallback`은 계속 금지다.

추가 정합화:

- `EntryPolicy`는 `CAUTION` 상태에서 더 이상 `ALLOW_FALLBACK`을 반환하지 않고 `latency_fallback_deprecated` reject로 고정했다.
- `sniper_entry_latency`는 legacy fallback builder 경로를 실주문 경로에서 사용하지 않는다.
- `split_entry_rebase_integrity_shadow`, `split_entry_immediate_recheck_shadow` runtime emit 기본값을 OFF로 전환했다.
- `fallback_qty_guard`는 live 조작점이 아니라 historical label로만 해석한다.

## 6. 검증

실행 결과:

```bash
PYTHONPATH=. .venv/bin/pytest -q src/tests/test_sniper_entry_latency.py
```

결과: `17 passed`

```bash
PYTHONPATH=. .venv/bin/python -m py_compile src/engine/sniper_entry_latency.py src/utils/constants.py src/tests/test_sniper_entry_latency.py
```

결과: 통과

## 7. 감리 리스크

- 이 축은 단일 residual이 아니라 복합축이므로, 판정 시 `quote_fresh_composite_canary_applied` 표본을 별도 분리해야 한다.
- `submitted`만 증가하고 `full/partial` 또는 `COMPLETED + valid profit_rate`가 악화되면 기대값 개선으로 볼 수 없다.
- `normal_slippage_exceeded`가 늘면 composite 조건이 넓은 것이 아니라 주문가 방어선이 병목인 것으로 재분해해야 한다.
- 보유/청산 `soft_stop_micro_grace`와 병렬 운용은 가능하지만, 성과는 entry 단계와 holding/exit 단계로 분리 판정해야 한다.

## 8. 다음 판정 입력

다음 bundle 또는 live 집계에서 반드시 볼 값:

- `latency_canary_reason=quote_fresh_composite_canary_applied`
- `budget_pass_to_submitted_rate`
- `submitted/full/partial`
- `latency_state_danger`
- `latency_danger_reasons`
- `normal_slippage_exceeded`
- `COMPLETED + valid profit_rate`

위 값에서 제출 회복과 체결 품질 개선이 동시에 확인되지 않으면, `latency_quote_fresh_composite`는 종료하고 `signal strength x quote freshness` 또는 상위 entry filter 재판정으로 넘긴다.
