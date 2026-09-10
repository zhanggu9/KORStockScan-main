from __future__ import annotations

import pandas as pd


def ema_cross_strategy(
    fast: int = 5,
    slow: int = 20,
):
    if fast < 1 or slow <= fast:
        raise ValueError("slow must be greater than fast, and fast must be >= 1")

    def strategy(bar: pd.Series, history: pd.DataFrame) -> str:
        closes = pd.to_numeric(history["close"], errors="coerce")
        fast_ema = closes.ewm(span=fast, adjust=False, min_periods=fast).mean().iloc[-1]
        slow_ema = closes.ewm(span=slow, adjust=False, min_periods=slow).mean().iloc[-1]
        if pd.isna(fast_ema) or pd.isna(slow_ema):
            return "HOLD"

        prev = closes.iloc[:-1]
        if len(prev) < slow:
            return "HOLD"
        prev_fast = prev.ewm(span=fast, adjust=False, min_periods=fast).mean().iloc[-1]
        prev_slow = prev.ewm(span=slow, adjust=False, min_periods=slow).mean().iloc[-1]
        if fast_ema > slow_ema and prev_fast <= prev_slow:
            return "BUY"
        if fast_ema < slow_ema and prev_fast >= prev_slow:
            return "SELL"
        return "HOLD"

    return strategy
