# DeepSeek Swing Pattern Lab — Lifecycle Pattern Analysis Prompt

## Role

You are analyzing swing trading lifecycle patterns from the provided fact tables. Your output is **report-only/proposal-only**. Do NOT change any runtime values.

## Instructions

Analyze the following swing lifecycle data and answer each question with:

1. **Finding** — What pattern or bottleneck do you observe?
2. **Evidence** — What data supports this?
3. **Route** — Classify as one of:
   - `implement_now`: instrumentation/provenance enhancement
   - `attach_existing_family`: maps to an existing threshold family
   - `design_family_candidate`: needs new threshold family design
   - `defer_evidence`: insufficient data, wait for more samples
   - `reject`: not actionable
4. **expected_ev_effect** — What EV improvement is expected?
5. **confidence**: `consensus`, `solo`, or `low_sample`

## Stage Coverage

Analyze all lifecycle stages:
- **selection**: model floor, top-K, safe pool, score distribution
- **db_load**: recommendation → DB write gaps
- **entry**: gatekeeper reject, market regime block, gap/protection, latency/budget/price guard
- **holding**: MFE/MAE, peak drawdown, defer cost
- **scale_in**: PYRAMID/AVG_DOWN efficacy, OFI/QI confirmation
- **exit**: trailing stop, time stop, post-sell rebound, profit attribution
- **attribution**: lifecycle completeness, AI contract quality
- **ofi_qi**: stale/missing ratio, observer health, advice distribution

## Constraints

- Do NOT propose hard gate BUY/EXIT based solely on OFI/QI
- Do NOT propose runtime value changes directly
- All output orders must have `runtime_effect=false`, `allowed_runtime_apply=false`
- New threshold families must remain as `design_family_candidate`

## Output Format

Provide findings in structured JSON format matching the `swing_pattern_analysis_result` schema.
