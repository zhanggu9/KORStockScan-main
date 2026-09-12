from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.trend_scalping import trend_scalping_strategy


def _frame(n: int = 120) -> pd.DataFrame:
    x = np.arange(n, dtype=float)
    close = 100.0 + x * 0.15
    volume = np.full(n, 1000.0)
    volume[-1] = 1800.0
    return pd.DataFrame(
        {
            "datetime": pd.date_range("2026-01-01 09:00", periods=n, freq="min"),
            "code": ["005930"] * n,
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": volume,
        }
    )


def test_trend_scalping_accepts_rising_stack_and_volume():
    frame = _frame()
    strategy = trend_scalping_strategy()
    assert strategy(frame.iloc[-1], frame) == "BUY"


def test_trend_scalping_rejects_weak_volume():
    frame = _frame()
    frame.loc[frame.index[-1], "volume"] = 1000.0
    strategy = trend_scalping_strategy()
    assert strategy(frame.iloc[-1], frame) == "HOLD"


def test_trend_scalping_exits_when_price_breaks_fast_ema():
    frame = _frame()
    frame.loc[frame.index[-1], "close"] = frame["close"].iloc[-2] - 2.0
    frame.loc[frame.index[-1], "open"] = frame["close"].iloc[-1]
    strategy = trend_scalping_strategy()
    assert strategy(frame.iloc[-1], frame) == "SELL"
