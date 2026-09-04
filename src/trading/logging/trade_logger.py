from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class TradeLogger:
    """Collects flat, JSON-serializable event logs for signals and orders."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def _push(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {"kind": kind, **payload}
        self.records.append(record)
        return record

    def log_signal(self, **payload: Any) -> dict[str, Any]:
        return self._push("signal", payload)

    def log_policy(self, **payload: Any) -> dict[str, Any]:
        return self._push("policy", payload)

    def log_order(self, **payload: Any) -> dict[str, Any]:
        return self._push("order", payload)

    def log_result(self, **payload: Any) -> dict[str, Any]:
        return self._push("result", payload)

    @staticmethod
    def normalize(value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        return value
