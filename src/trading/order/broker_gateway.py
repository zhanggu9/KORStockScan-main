from __future__ import annotations

from typing import Protocol

from src.trading.entry.entry_types import PlannedOrder
from src.trading.order.order_types import BrokerOrderResult


class BrokerGateway(Protocol):
    """Protocol for broker submitters used by the order manager."""

    def submit_order(self, order: PlannedOrder) -> BrokerOrderResult:
        """Submit a single planned order to the broker."""
