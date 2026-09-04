# 스캘핑 AI 판단 결과 평탄화(Smoothing) 방안

> 진입–보유–청산 단계에서 연속적인 AI 판단이 너무 민감하게 급변하는 문제를 OFI 및 기타 기법으로 평탄화하는 종합 가이드

---

## 1. OFI 기반 Smoothing — 구체적 활용 방안

OFI(Order Flow Imbalance, Cont–Kukanov–Stoikov 정의)는 호가창 변화에서 순매수/매도 압력을 추출하므로, AI 판단의 잡음을 시장 마이크로구조로 필터링하는 데 잘 맞는다.

### 1.1 Confirmation Gate

AI가 진입/청산 신호를 내도, OFI 부호(또는 z-score)가 같은 방향일 때만 실행. 반대 방향이면 직전 상태를 유지한다. "근거 없는 flip"을 막는 1차 필터.

```
if AI_signal == LONG and OFI_z > 0:
    execute()
else:
    hold_previous_state()
```

### 1.2 비대칭 Hysteresis with OFI Bands

진입과 청산의 임계치를 다르게, 그리고 OFI를 결합한다.

- **진입**: `AI_score > 0.7 AND OFI_z > +1.0`
- **청산**: `AI_score < 0.3 OR OFI_z < -1.5`

임계 근처에서의 진동(chattering) 제거에 가장 효과적.

### 1.3 Composite Signal

AI 확률/로짓과 OFI z-score를 가중합한 연속 점수를 만들고, 그 점수에 EMA를 걸어 평탄화. 이산 라벨을 평활화하는 것보다 훨씬 안정적이다.

```
composite = α · AI_logit + β · OFI_z
smoothed  = EMA(composite, span=N)
```

### 1.4 Multi-level OFI 권장

top-1 호가만 보면 OFI 자체도 noisy하다. 5~10 레벨 누적 또는 거리에 따라 가중한 OFI를 사용. tick 간격이 짧을수록 중요해진다.

### 1.5 OFI의 한계

- 큰 주문이 분할되어 들어올 때 일시적으로 OFI가 역전될 수 있음
- 매우 thin한 마켓에서는 신호 자체가 불안정
- **보조 신호**: 체결 기준 signed volume(Trade Flow Imbalance), micro-price 변화를 함께 보면 robust해짐

---

## 2. OFI 외의 평탄화 방안

### 2.1 모델 출력 수준

- **연속 신뢰도 점수**: 라벨이 아니라 logits/확률을 받아 EMA 또는 Kalman filter 적용. Flash Lite에 "0~100 신뢰도 점수" 출력을 프롬프트로 강제하면 이산 결정의 jitter를 거의 제거할 수 있다.
- **k-of-n 합의**: 직전 N번 호출 중 K번 이상 같은 결정일 때만 상태 전이.

### 2.2 정책 / State Machine 수준

- **Dwell Time**: 한번 진입하면 최소 보유 시간(예: 20~30초) 동안 청산 신호 무시. Scalping이라도 그 이하의 hold는 거의 항상 noise + 수수료 손실.
- **Switching Cost Penalty**: 매 호출마다 "현재 상태 유지"에 +0.1 정도 보너스. 명확히 강한 반대 신호에서만 flip하도록 모델 출력 후처리에서 적용.
- **HMM Smoothing**: hidden state를 {long, flat, short}로 두고 AI 출력을 emission으로 보는 forward–backward. 단발 outlier 자동 제거에 깔끔하지만 latency·튜닝 부담이 있다.

### 2.3 모델 라우팅 수준

현재 작업 중인 라우팅 로직과 자연스럽게 결합되는 패턴들.

- **2-Tier 의사결정**: Flash Lite는 매 tick 모니터링과 "변화 후보 detection"만 담당, 실제 상태 전이는 상위 모델(Gemini Flash, GPT급)이 confirm한 경우에만 실행. 비용 대비 안정성이 가장 좋은 패턴.
- **Regime Gating**: 분 단위로 도는 별도의 느린 분류기가 trending / ranging / chop을 판정하고, chop 구간에서는 진입 임계치를 자동으로 높여 의도적으로 둔감화.

### 2.4 프롬프트 수준 (의외로 효과 큼)

프롬프트에 직전 결정과 그 근거를 포함시키고 **"직전 결정을 뒤집으려면 새로운 명확한 근거가 필요하다"** 는 제약을 명시. LLM은 입력의 사소한 변화에 과민반응하므로, 일관성 비용을 모델이 직접 internalize하게 만드는 것이 효과적이다.

---

## 3. 추천 조합 순서 (효과 / 구현비용 비)

Scalping + Flash Lite급 빠른 호출이 전제라면 다음 순서로 적용하는 것을 권장한다.

| 우선순위 | 조치 | 핵심 효과 |
|---|---|---|
| 1 | 이산 라벨 대신 **연속 신뢰도 점수 출력 + EMA + 비대칭 hysteresis** | 가장 싸고 즉효 |
| 2 | **Multi-level OFI confirmation gate** 추가 | 마이크로구조 기반 검증 |
| 3 | **Dwell time + switching cost penalty** | 단발 flip 차단 |
| 4 | **Regime gating** | chop 구간 자동 둔감화 |
| 5 | 필요시 **상위 모델 escalation** | 비용/안정성 균형 |

### 핵심 인사이트

HMM·Kalman은 이론적으로 깔끔하지만, **1~4 조합만으로 실전 flicker의 80~90%는 제거**된다. 특히 (1)의 **"라벨 → 연속 점수" 전환이 단일 조치로는 가장 ROI가 높다.**

---

## 4. 다음 단계로 더 깊이 파볼 항목

- OFI confirmation gate의 임계치 캘리브레이션 방법
- EMA 계수(span / α) 선택 — 데이터 기반 vs 휴리스틱
- Dwell time 백테스트 설계
- 2-tier 라우팅에서 escalation 트리거 조건 설계
- Multi-level OFI 가중 함수 설계 (선형 / 지수감쇠 / 거래량 가중)

---

*작성: 2026-05-04*
