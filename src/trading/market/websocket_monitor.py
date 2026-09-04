from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class WebsocketMonitor:
    """Tracks recent websocket packet intervals for jitter analysis."""

    max_samples: int = 20
    _intervals_ms: deque[int] = field(default_factory=deque)

    def add_interval(self, interval_ms: int) -> None:
        if len(self._intervals_ms) >= self.max_samples:
            self._intervals_ms.popleft()
        self._intervals_ms.append(max(0, int(interval_ms)))

    def jitter_ms(self) -> int:
        if len(self._intervals_ms) < 2:
            return 0
        return max(self._intervals_ms) - min(self._intervals_ms)
