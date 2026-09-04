# DeepSeek Swing Pattern Lab — Holding/Exit Pattern Analysis Prompt

## Focus

Analyze swing holding and exit quality:
1. MFE (Maximum Favorable Excursion) vs MAE (Maximum Adverse Excursion)
2. Peak drawdown during holding
3. Trailing stop effectiveness
4. Time stop / hard stop timing
5. Holding-flow defer cost (seconds deferred, worsens detected)
6. Post-sell rebound analysis (sold too early?)
7. Exit source distribution (trailing, hard stop, time stop, preset target, manual)

## Questions

1. Are exits capturing enough of the peak profit (MFE capture rate)?
2. Are trailing stops too tight (missing upside) or too loose (giving back profits)?
3. Is holding-flow defer causing missed optimal exits?
4. Do post-sell rebounds indicate systematic exit timing issues?
5. Are hard stops being hit disproportionately (bad entry sign)?

## Constraints

- Do NOT propose OFI/QI-only hard EXIT gates
- Holding-flow OFI smoothing should only be evaluated within existing postprocessor scope
- All runtime_effect must be false
