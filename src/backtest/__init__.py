from .engine import BacktestConfig, BacktestResult, Trade, run_backtest
from .strategies import one_minute_scalping_proxy_strategy
from .trend_scalping import trend_scalping_strategy

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "Trade",
    "run_backtest",
    "one_minute_scalping_proxy_strategy",
    "trend_scalping_strategy",
]
