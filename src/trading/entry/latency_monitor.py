from __future__ import annotations

from src.trading.config.entry_config import EntryConfig
from src.trading.entry.entry_types import LatencyState, LatencyStatus


class LatencyMonitor:
    """Classifies current execution health into SAFE/CAUTION/DANGER."""

    def __init__(self, config: EntryConfig) -> None:
        self.config = config

    def evaluate(
        self,
        *,
        ws_age_ms: int,
        ws_jitter_ms: int,
        order_rtt_avg_ms: int,
        order_rtt_p95_ms: int,
        quote_stale: bool,
        spread_ratio: float,
    ) -> LatencyStatus:
        if quote_stale:
            state = LatencyState.DANGER
        elif (
            ws_age_ms <= self.config.max_ws_age_ms_for_safe
            and ws_jitter_ms <= self.config.max_ws_jitter_ms_for_safe
            and order_rtt_avg_ms <= self.config.max_order_rtt_avg_ms_for_safe
            and spread_ratio <= self.config.max_spread_ratio_for_safe
        ):
            state = LatencyState.SAFE
        elif (
            ws_age_ms <= self.config.max_ws_age_ms_for_caution
            and ws_jitter_ms <= self.config.max_ws_jitter_ms_for_caution
            and order_rtt_avg_ms <= self.config.max_order_rtt_avg_ms_for_caution
            and spread_ratio <= self.config.max_spread_ratio_for_caution
        ):
            state = LatencyState.CAUTION
        else:
            state = LatencyState.DANGER

        return LatencyStatus(
            state=state,
            ws_age_ms=int(ws_age_ms),
            ws_jitter_ms=int(ws_jitter_ms),
            order_rtt_avg_ms=int(order_rtt_avg_ms),
            order_rtt_p95_ms=int(order_rtt_p95_ms),
            quote_stale=bool(quote_stale),
            spread_ratio=float(spread_ratio),
        )
