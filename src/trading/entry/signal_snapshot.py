from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.trading.entry.entry_types import SignalSnapshot


def build_signal_snapshot(
    *,
    symbol: str,
    strategy_id: str,
    signal_price: int,
    signal_strength: float,
    planned_qty: int,
    side: str = "BUY",
    signal_time: datetime | None = None,
    context: dict[str, Any] | None = None,
) -> SignalSnapshot:
    """Create a consistent signal snapshot for orchestration."""

    return SignalSnapshot(
        symbol=symbol,
        strategy_id=strategy_id,
        signal_time=signal_time or datetime.now(UTC),
        signal_price=int(signal_price),
        signal_strength=float(signal_strength),
        planned_qty=int(planned_qty),
        side=side,
        context=context or {},
    )
