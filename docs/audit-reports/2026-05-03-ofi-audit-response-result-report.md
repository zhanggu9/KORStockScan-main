# OFI 감리 지적 대응 결과보고서

**작성일:** 2026-05-03 KST  
**대상:** `Order Flow Imbalance(OFI) / Queue Imbalance(QI) orderbook micro` 감리 지적 대응  
**범위:** `dynamic_entry_ai_price_canary_p2` 내부 live 입력 feature, bucket runtime calibration, snapshot/log provenance

---

## 1. 결론

감리 지적 중 실시간 주문 판단의 단일축 원칙을 해치지 않으면서 보완 가능한 항목은 수용했다. 이번 반영은 OFI/QI를 standalone hard gate로 승격하는 작업이 아니라, 이미 live 입력으로 쓰이는 `dynamic_entry_ai_price_canary_p2` 내부 feature의 추적성, 임계값 provenance, bucket별 runtime calibration 기반을 보강하는 작업이다.

핵심 변경은 다음과 같다.

| 구분 | 처리 |
|---|---|
| snapshot/log provenance | 수용 |
| staleness/observer health 분리 | 수용 |
| threshold provenance | 수용 |
| AI `SKIP` policy warning | 수용 |
| bucket-first runtime calibration | 수용, 기본 OFF |
| symbol anomaly watch | 수용, report-only |
| OFI standalone hard gate | 미수용 |
| watching/holding/exit 확장 | 미수용 |
| 종목별 runtime threshold | 미수용 |
| 효과측정 기반 live 결정 | 미수용 |

---

## 2. 수용 및 반영 사항

### 2.1 Snapshot/Log provenance

`orderbook_micro`, `price_context.orderbook_micro`, `ENTRY_PIPELINE` 로그에 다음 계열의 필드를 추가했다.

| 계열 | 필드 |
|---|---|
| 시점/health | `captured_at_ms`, `snapshot_age_ms`, `observer_healthy`, `observer_missing_reason`, `observer_last_quote_age_ms`, `observer_last_trade_age_ms` |
| 계산 파라미터 | `micro_window_sec`, `micro_z_min_samples`, `micro_lambda` |
| threshold provenance | `ofi_bull_threshold`, `ofi_bear_threshold`, `qi_bull_threshold`, `qi_bear_threshold`, `ofi_threshold_source`, `ofi_threshold_bucket_key`, `ofi_threshold_manifest_id`, `ofi_threshold_manifest_version`, `ofi_threshold_fallback_reason` |
| calibration/anomaly | `ofi_calibration_bucket`, `ofi_bucket_key`, `ofi_symbol_sample_count`, `ofi_bucket_sample_count`, `ofi_symbol_bearish_rate`, `ofi_bucket_bearish_rate`, `ofi_symbol_bullish_rate`, `ofi_bucket_bullish_rate`, `ofi_symbol_bucket_deviation`, `ofi_calibration_warning` |

이 필드들은 감리 재현성, 장후 분석, snapshot 품질 확인을 위한 provenance다. 주문 판단을 직접 바꾸는 지점은 bucket threshold가 선택한 `micro_state`뿐이다.

### 2.2 Bucket-first runtime calibration

`SCALPING_ENTRY_PRICE_ORDERBOOK_MICRO_BUCKET_CALIBRATION_ENABLED`를 추가했다. 기본값은 `False`다.

flag OFF 상태에서는 기존 global threshold를 그대로 쓴다. flag ON 상태에서는 `data/config/ofi_bucket_threshold_manifest.json`의 bucket threshold를 조회한다. manifest missing, invalid, bucket miss, sample 부족이면 global threshold로 fallback하고 `ofi_threshold_source=fallback`, `ofi_threshold_fallback_reason`을 남긴다.

runtime v1 bucket key는 실시간에서 안정적으로 계산 가능한 값만 쓴다.

```text
spread=tight|normal|wide|unknown
price=low|mid|high|unknown
depth=thin|normal|thick|unknown
sample=insufficient|normal|rich
```

`market_cap_bucket`, `liquidity_bucket`은 실시간 source가 고정되기 전까지 runtime key에 넣지 않고 report-only 후보로 유지한다.

### 2.3 AI SKIP policy warning

AI가 `SKIP`을 반환한 경우 후처리에서 다음 필드를 남긴다.

| 필드 | 의미 |
|---|---|
| `entry_ai_price_skip_policy_warning` | OFI 정책 관점의 warning |
| `entry_ai_price_skip_policy_basis` | `SKIP`이 bearish OFI로 지지되는지 여부 |

정책은 다음과 같다.

| 조건 | 기록 |
|---|---|
| `ready=True` and `micro_state=bearish` | `basis=ofi_bearish_supported` |
| `ready=False` | `warning=ofi_not_ready` |
| `micro_state in neutral/insufficient/missing` | `warning=skip_without_bearish_ofi` |

warning은 `SKIP`을 취소하지 않는다. 프롬프트 drift와 의사결정 provenance를 추적하기 위한 관찰값이다.

### 2.4 장후 리포트 집계

`performance_tuning_report`에 OFI orderbook micro 요약을 추가했다.

| 집계 | 의미 |
|---|---|
| `ofi_orderbook_micro_states` | `bearish/bullish/neutral/insufficient` 분포 |
| `ofi_orderbook_micro_threshold_sources` | `global/bucket/fallback` 분포 |
| `ofi_orderbook_micro_buckets` | runtime bucket key 분포 |
| `ofi_orderbook_micro_warnings` | calibration warning 분포 |
| `symbol_anomalies` | 종목별 이상치 후보 |

종목별 값은 anomaly watch와 후속 calibration 후보 생성에만 사용한다. 종목별 runtime threshold 적용은 금지한다.

---

## 3. 미수용 사항 및 사유

| 항목 | 미수용 사유 |
|---|---|
| OFI standalone hard gate | 현재 active owner는 `dynamic_entry_ai_price_canary_p2`다. 동일 단계 내 별도 hard gate를 추가하면 단일축 canary 원칙을 훼손한다. |
| watching/holding/exit 확장 | 적용 지점과 cadence가 다르다. entry price P2 감리 대응 범위를 넘어선 새 workorder가 필요하다. |
| 종목별 runtime threshold | 표본 부족과 과최적화 위험이 크다. 이번 범위에서는 bucket runtime calibration까지만 허용한다. |
| threshold 자동 live mutation | 운영 규칙상 manifest 적용은 env/code 반영 및 restart 기반으로만 한다. 자동 runtime mutation은 금지한다. |
| 도입효과 측정 기반 live 결정 | OFI/QI는 이미 P2 내부 live 입력 feature다. 이번 사항은 live 승인/keep/OFF 조건이 아니라 추적성과 calibration 보강이다. |

---

## 4. 운영 기준

- bucket calibration은 P2 내부 feature 보정이다.
- `SCALPING_ENTRY_PRICE_ORDERBOOK_MICRO_BUCKET_CALIBRATION_ENABLED=False`가 기본값이며 rollback owner다.
- 초기 manifest는 global threshold와 같은 값으로 시작한다.
- 다른 bucket threshold는 별도 운영 승인 없이는 추가하지 않는다.
- manifest 적용은 env/code 반영과 restart 기반으로만 한다.
- symbol-level runtime threshold는 금지한다.
- `OFI standalone hard gate`, `watching/holding/exit` 확장은 별도 workorder 없이는 금지한다.

---

## 5. 검증

대상 테스트:

```bash
PYTHONPATH=. .venv/bin/pytest src/tests/test_orderbook_stability_observer.py src/tests/test_sniper_scale_in.py src/tests/test_performance_tuning_report.py -q
```

문서 parser 검증:

```bash
PYTHONPATH=. .venv/bin/python -m src.engine.sync_docs_backlog_to_project --print-backlog-only --limit 500
```
