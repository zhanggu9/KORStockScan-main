# DeepSeek Swing Pattern Lab — Entry Pattern Analysis Prompt

## Focus

Analyze swing entry funnel bottlenecks:
1. Selection → recommendation gap
2. Recommendation → DB load gap
3. Gatekeeper operation (accept/reject distribution, cooldown, eval latency)
4. Market regime block/pass distribution
5. Gap/protection guard hit rate
6. Budget/qty/price/latency guard effects

## Questions

1. What percentage of selected candidates reach order submission?
2. Where in the entry funnel do candidates get blocked most?
3. Are gatekeeper reject patterns consistent or noisy?
4. Is market regime block preventing quality entries in bull/bear regimes?
5. Is the DB load gap preventing timely entry?

## Constraints

- Do NOT propose single-metric hard gates (e.g., OFI/QI-only BUY gate)
- Propose only instrumentation/provenance enhancements or threshold family attachments
- All runtime_effect must be false
