"""Real-time microstructure recorder for intraday backtest data collection.

The recorder persists raw websocket observations so that future backtests can
use execution strength, order-book state, and other microstructure fields
without inventing historical values that the broker does not expose.
"""

from __future__ import annotations

import csv
import os
import queue
import threading
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
MARKET_OPEN = dt_time(9, 0)
MARKET_CLOSE = dt_time(15, 30)


class MicrostructureRecorder:
    """Append real-time observations to one CSV per stock and trading date."""

    FIELDNAMES = (
        "datetime",
        "code",
        "curr",
        "open",
        "high",
        "low",
        "volume",
        "v_pw",
        "ask_tot",
        "bid_tot",
        "best_ask",
        "best_bid",
        "spread",
        "spread_pct",
    )

    def __init__(self, root: Optional[str | Path] = None) -> None:
        configured = root or os.getenv(
            "KORSTOCKSCAN_MICROSTRUCTURE_DIR", "data/microstructure"
        )
        self.root = Path(configured)
        self._queue: queue.Queue[Mapping[str, Any]] = queue.Queue(maxsize=20_000)
        self._stop = threading.Event()
        self._initialized_files: set[Path] = set()
        self._lock = threading.Lock()
        self._worker = threading.Thread(
            target=self._run,
            name="microstructure-recorder",
            daemon=True,
        )
        self._worker.start()

    @staticmethod
    def _first(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            value = data.get(key)
            if value is not None and value != "":
                return value
        return default

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _timestamp(payload: Mapping[str, Any], ws_data: Mapping[str, Any]) -> datetime:
        raw = MicrostructureRecorder._first(
            ws_data, "datetime", "timestamp", "dt", "tm", "time"
        )
        if raw is None:
            raw = MicrostructureRecorder._first(
                payload, "datetime", "timestamp", "dt", "tm", "time"
            )
        if raw is not None:
            text = str(raw).strip()
            for fmt in (
                "%Y%m%d%H%M%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%H%M%S",
            ):
                try:
                    parsed = datetime.strptime(text, fmt)
                    if fmt == "%H%M%S":
                        now = datetime.now(KST)
                        parsed = parsed.replace(
                            year=now.year, month=now.month, day=now.day
                        )
                    return parsed.replace(tzinfo=KST)
                except ValueError:
                    continue
        return datetime.now(KST)

    def record_async(self, payload: Mapping[str, Any]) -> bool:
        """Queue one websocket event without blocking the realtime EventBus."""
        if not isinstance(payload, Mapping):
            return False
        try:
            self._queue.put_nowait(payload)
            return True
        except queue.Full:
            # Dropping an observation is preferable to blocking the trading loop.
            return False

    def record(self, payload: Mapping[str, Any]) -> bool:
        """Persist one websocket event. Returns True when a row is written."""
        if not isinstance(payload, Mapping):
            return False

        code = str(
            payload.get("code") or payload.get("stk_cd") or ""
        ).strip().removeprefix("A")[:6]
        ws_data = payload.get("data")
        if not code or not isinstance(ws_data, Mapping):
            return False

        observed = self._timestamp(payload, ws_data).astimezone(KST)
        if not (MARKET_OPEN <= observed.time() <= MARKET_CLOSE):
            return False

        curr = self._number(self._first(ws_data, "curr", "현재가", "price"))
        if curr <= 0:
            return False

        ask_tot = self._number(
            self._first(ws_data, "ask_tot", "매도호가잔량", "total_ask")
        )
        bid_tot = self._number(
            self._first(ws_data, "bid_tot", "매수호가잔량", "total_bid")
        )
        best_ask = self._number(
            self._first(ws_data, "best_ask", "매도최우선호가", "ask1")
        )
        best_bid = self._number(
            self._first(ws_data, "best_bid", "매수최우선호가", "bid1")
        )

        spread = max(0.0, best_ask - best_bid) if best_ask > 0 and best_bid > 0 else 0.0
        spread_pct = spread / curr * 100.0 if curr > 0 else 0.0

        row = {
            "datetime": observed.strftime("%Y-%m-%d %H:%M:%S"),
            "code": code,
            "curr": curr,
            "open": self._number(self._first(ws_data, "open", "시가")),
            "high": self._number(self._first(ws_data, "high", "고가")),
            "low": self._number(self._first(ws_data, "low", "저가")),
            "volume": self._number(self._first(ws_data, "volume", "거래량")),
            "v_pw": self._number(self._first(ws_data, "v_pw", "체결강도")),
            "ask_tot": ask_tot,
            "bid_tot": bid_tot,
            "best_ask": best_ask,
            "best_bid": best_bid,
            "spread": spread,
            "spread_pct": spread_pct,
        }

        day = observed.strftime("%Y%m%d")
        path = self.root / day / f"{code}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            first_write = path not in self._initialized_files and not path.exists()
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
                if first_write:
                    writer.writeheader()
                writer.writerow(row)
                handle.flush()
            self._initialized_files.add(path)
        return True

    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.record(payload)
            finally:
                self._queue.task_done()

    def close(self) -> None:
        self._stop.set()
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)
