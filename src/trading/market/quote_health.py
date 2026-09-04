from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class QuoteHealth:
    """Realtime quote health summary derived from cached websocket data."""

    ws_age_ms: int
    ws_jitter_ms: int
    quote_stale: bool
    spread_ratio: float
    best_ask: int
    best_bid: int
    last_price: int

    def to_dict(self) -> dict[str, int | float | bool]:
        return asdict(self)
