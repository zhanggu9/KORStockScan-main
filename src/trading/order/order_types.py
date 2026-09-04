from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    """Supported order side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Supported order style."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TimeInForce(str, Enum):
    """Supported time-in-force values."""

    DAY = "DAY"
    IOC = "IOC"


@dataclass(slots=True)
class BrokerOrderResult:
    """Normalized broker submit result."""

    accepted: bool
    order_tag: str
    broker_order_id: str
    order_status: str
    request_timestamp: float
    response_timestamp: float
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
