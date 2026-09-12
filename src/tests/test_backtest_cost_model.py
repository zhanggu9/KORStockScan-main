from __future__ import annotations

import pandas as pd

from src.backtest.engine import BacktestConfig, run_backtest


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"datetime": "2026-01-02 09:00", "code": "005930", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
            {"datetime": "2026-01-02 09:01", "code": "005930", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
            {"datetime": "2026-01-02 09:02", "code": "005930", "open": 110, "high": 111, "low": 109, "close": 110, "volume": 1000},
            {"datetime": "2026-01-02 09:03", "code": "005930", "open": 110, "high": 111, "low": 109, "close": 110, "volume": 1000},
        ]
    )


def test_slippage_is_applied_only_once_on_sell() -> None:
    def strategy(bar, history):
        if len(history) == 1:
            return "BUY"
        if len(history) == 3:
            return "SELL"
        return "HOLD"

    result = run_backtest(
        _bars(),
        strategy,
        BacktestConfig(
            initial_cash=10_000,
            fee_bps=0,
            entry_slippage_bps=0,
            exit_slippage_bps=100,
            force_close_eod=False,
        ),
    )
    assert result.total_trades == 1
    trade = result.trades[0]
    assert trade.entry_price == 100
    assert trade.exit_price == 108.9
    assert trade.slippage_cost == 110.0
    assert round(trade.net_pnl, 6) == 890.0
