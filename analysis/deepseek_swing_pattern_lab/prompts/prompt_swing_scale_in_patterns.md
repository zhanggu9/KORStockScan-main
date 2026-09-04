# DeepSeek Swing Pattern Lab — Scale-In Pattern Analysis Prompt

## Focus

Analyze swing scale-in (PYRAMID/AVG_DOWN) patterns:
1. PYRAMID vs AVG_DOWN vs NONE distribution
2. Post-add outcome analysis (MFE/MAE after add)
3. OFI/QI micro context at time of scale-in decision
4. Scale-in price guard effectiveness
5. Dynamic quantity resolution quality

## Questions

1. What is the win rate after PYRAMID vs AVG_DOWN adds?
2. Does OFI/QI confirmation improve post-add outcomes?
3. Are scale-in price guards (defensive tick, best_bid) improving entry price?
4. Are there patterns where scale-in worsens position P&L?

## Constraints

- DO NOT propose changes to add quantity, add price, or add decision based on OFI/QI alone
- OFI/QI should be evaluated as confirmation/provenance only
- All runtime_effect must be false
