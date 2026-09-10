from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestConfig, run_backtest


def test_next_open_execution_and_eod_close():
    frame = pd.DataFrame(
        [
            ["2026-09-01 09:00:00", "005930", 100, 101, 99, 100, 1000],
            ["2026-09-01 09:01:00", "005930", 110, 111, 109, 110, 1000],
            ["2026-09-01 15:30:00", "005930", 120, 121, 119, 120, 1000],
            ["2026-09-02 09:00:00", "005930", 130, 131, 129, 130, 1000],
            ["2026-09-02 09:01:00", "005930", 125, 126, 124, 125, 1000],
            ["2026-09-02 15:30:00", "005930", 120, 121, 119, 120, 1000],
        ],
        columns=["datetime", "code", "open", "high", "low", "close", "volume"],
    )

    def strategy(bar, history):
        if len(history) == 1:
            return "BUY"
        return "HOLD"

    result = run_backtest(
        frame,
        strategy,
        BacktestConfig(initial_cash=1_000_000, fee_bps=0, slippage_bps=0),
    )

    assert result.total_trades == 1
    trade = result.trades[0]
    assert trade.entry_time == pd.Timestamp("2026-09-01 09:01:00")
    assert trade.entry_price == 110
    assert trade.exit_time == pd.Timestamp("2026-09-01 15:30:00")
    assert trade.exit_price == 120


def test_costs_reduce_profit():
    frame = pd.DataFrame(
        [
            ["2026-09-01 09:00:00", "005930", 100, 100, 100, 100, 1000],
            ["2026-09-01 09:01:00", "005930", 110, 110, 110, 110, 1000],
            ["2026-09-01 15:30:00", "005930", 110, 110, 110, 110, 1000],
        ],
        columns=["datetime", "code", "open", "high", "low", "close", "volume"],
    )

    def strategy(bar, history):
        return "BUY" if len(history) == 1 else "HOLD"

    free = run_backtest(
        frame,
        strategy,
        BacktestConfig(initial_cash=1_000_000, fee_bps=0, slippage_bps=0),
    )
    costly = run_backtest(
        frame,
        strategy,
        BacktestConfig(initial_cash=1_000_000, fee_bps=10, slippage_bps=10),
    )

    assert costly.final_cash < free.final_cash
