from src.trading.config.entry_config import EntryConfig
from src.trading.entry.entry_types import LatencyState
from src.trading.entry.latency_monitor import LatencyMonitor


def test_latency_monitor_safe():
    monitor = LatencyMonitor(EntryConfig())
    result = monitor.evaluate(
        ws_age_ms=100,
        ws_jitter_ms=50,
        order_rtt_avg_ms=100,
        order_rtt_p95_ms=200,
        quote_stale=False,
        spread_ratio=0.001,
    )
    assert result.state == LatencyState.SAFE


def test_latency_monitor_danger_on_stale_quote():
    monitor = LatencyMonitor(EntryConfig())
    result = monitor.evaluate(
        ws_age_ms=900,
        ws_jitter_ms=50,
        order_rtt_avg_ms=100,
        order_rtt_p95_ms=200,
        quote_stale=True,
        spread_ratio=0.001,
    )
    assert result.state == LatencyState.DANGER
