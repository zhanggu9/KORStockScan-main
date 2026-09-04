# Widget mechanical Entry-AI replay — 2026-08-04

- authority: `offline_widget_mechanical_replay_only`
- runtime_effect: `false`
- actual_order_submitted: `false`
- outcome: 10m tight entry path (`+0.3% / -0.7%`)

| Cohort | Samples | Stocks | Target first | Adverse first | Target-first rate | Target share among decisive | Equal-weight 10m end |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AI BUY | 2 | 2 | 1 | 1 | 50.0 | 50.0 | -0.277289 |
| AI WAIT/DROP | 390 | 134 | 60 | 297 | 15.384615 | 16.806723 | -0.645381 |
| Mechanical signal (price-comparable) | 0 | 0 | 0 | 0 | None | None | None |
| Mechanical candidate before spread gate (price-comparable) | 0 | 0 | 0 | 0 | None | None | None |
| Mechanical candidate before spread gate (AI-ask proxy) | 11 | 9 | 0 | 9 | 0.0 | 0.0 | -0.734567 |

## Stock-code cohorts

Only cohorts with a mechanical signal or a pre-spread candidate are shown; the JSON artifact retains every joined stock code.

| Stock code | Joined | Mechanical signals | Pre-spread candidates | Target first | Adverse first | Equal-weight 10m end |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 006340 | 8 | 0 | 3 | 1 | 4 | -1.246136 |
| 010950 | 8 | 0 | 1 | 1 | 7 | -0.920325 |
| 047050 | 9 | 0 | 2 | 0 | 8 | -0.782013 |
| 064350 | 4 | 0 | 1 | 1 | 2 | 0.114555 |
| 095340 | 1 | 0 | 1 | 0 | 0 | -0.154679 |
| 100840 | 2 | 0 | 2 | 0 | 2 | -0.362976 |
| 108490 | 4 | 0 | 1 | 0 | 3 | 0.131881 |
| 112610 | 1 | 0 | 1 | 0 | 1 | -0.75188 |
| 217590 | 3 | 0 | 1 | 0 | 3 | -0.64728 |

## Scope limits

Samsung-specific peer relative strength, investor/program flow, and Yahoo external risk were not fabricated for other symbols. Portable-core passes are therefore capped at `ENTRY_CAUTION`. The 10-second promotion filter and stateful recovery-episode filter are not replayed from event-spaced AI snapshots.

The pre-spread AI-ask proxy keeps the Entry-AI executable ask only as a conservative decision-point sensitivity check. It is not the widget recommended-range fill result; rows whose recommended range excludes that ask remain price-noncomparable.

This daily report is diagnostic counterfactual evidence only. It cannot replace Entry AI, approve live runtime changes, or submit orders.
