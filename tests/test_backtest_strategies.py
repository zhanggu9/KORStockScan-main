from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.strategies import one_minute_scalping_proxy_strategy


def test_scalping_proxy_buys_only_when_all_entry_filters_pass():
    rows = []
    close_values = [100 + i * 0.5 for i in range(14)]
    volumes = [1000] * 13 + [3000]
    for i, (close, volume) in enumerate(zip(close_values, volumes)):
        rows.append(
            [
                f"2026-09-01 09:{i:02d}:00",
                "005930",
                close,
                close,
                close,
                close,
                volume,
            ]
        )
    frame = pd.DataFrame(
        rows,
        columns=["datetime", "code", "open", "high", "low", "close", "volume"],
    )
    frame.loc[13, "close"] = frame.loc[10:12, "close"].mean() * 1.021
    frame.loc[13, "open"] = frame.loc[13, "close"]
    frame.loc[13, "high"] = frame.loc[13, "close"]
    frame.loc[13, "low"] = frame.loc[13, "close"]

    strategy = one_minute_scalping_proxy_strategy()
    assert strategy(frame.iloc[-1], frame.iloc[:]) == "BUY"


def test_scalping_proxy_sell_uses_rsi_threshold():
    close_values = [120 - i for i in range(16)]
    frame = pd.DataFrame(
        [
            [
                f"2026-09-01 09:{i:02d}:00",
                "005930",
                close,
                close,
                close,
                close,
                1000,
            ]
            for i, close in enumerate(close_values)
        ],
        columns=["datetime", "code", "open", "high", "low", "close", "volume"],
    )
    strategy = one_minute_scalping_proxy_strategy()
    assert strategy(frame.iloc[-1], frame.iloc[:]) == "SELL"


def test_scalping_proxy_can_feed_backtest_engine():
    frame = pd.DataFrame(
        [
            ["2026-09-01 09:00:00", "005930", 100, 100, 100, 100, 1000],
            ["2026-09-01 09:01:00", "005930", 101, 101, 101, 101, 1000],
            ["2026-09-01 09:02:00", "005930", 102, 102, 102, 102, 1000],
            ["2026-09-01 09:03:00", "005930", 103, 103, 103, 103, 1000],
            ["2026-09-01 15:30:00", "005930", 103, 103, 103, 103, 1000],
        ],
        columns=["datetime", "code", "open", "high", "low", "close", "volume"],
    )
    result = run_backtest(
        frame,
        one_minute_scalping_proxy_strategy(rsi_period=2),
        BacktestConfig(initial_cash=1_000_000, fee_bps=0, slippage_bps=0),
    )
    assert result.code == "005930"
