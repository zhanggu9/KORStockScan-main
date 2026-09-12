from __future__ import annotations

from typing import Callable, Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame], Action]


def _ema(closes: pd.Series, span: int) -> pd.Series:
    return closes.ewm(span=span, adjust=False, min_periods=span).mean()


def _rsi_series(closes: pd.Series, period: int) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.mask(avg_loss == 0.0, 100.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    return rsi


def trend_scalping_strategy(
    fast_ema: int = 5,
    slow_ema: int = 20,
    trend_ema: int = 60,
    slope_bars: int = 3,
    rsi_period: int = 14,
    rsi_min: float = 55.0,
    rsi_max: float = 78.0,
    volume_multiplier: float = 1.5,
    pullback_pct: float = 0.8,
    sell_rsi: float = 45.0,
) -> SignalFn:
    """OHLCV-only intraday continuation strategy.

    BUY requires a stacked/rising trend instead of simply chasing RSI >= 70:
      * fast EMA > slow EMA > trend EMA
      * fast and slow EMA are rising over ``slope_bars`` bars
      * current close is not materially below fast EMA
      * RSI stays inside a momentum band
      * current volume is above the prior-window average

    SELL occurs when momentum fails (close below fast EMA) or RSI falls below
    ``sell_rsi``. The backtest engine executes the signal on the next bar open
    by default, so the signal never uses future data.
    """
    if not (1 <= fast_ema < slow_ema < trend_ema):
        raise ValueError("EMA periods must satisfy fast_ema < slow_ema < trend_ema")
    if slope_bars < 1:
        raise ValueError("slope_bars must be >= 1")
    if rsi_period < 2:
        raise ValueError("rsi_period must be >= 2")
    if not (0.0 <= rsi_min < rsi_max <= 100.0):
        raise ValueError("RSI bounds must satisfy 0 <= min < max <= 100")
    if volume_multiplier <= 0:
        raise ValueError("volume_multiplier must be > 0")
    if pullback_pct < 0:
        raise ValueError("pullback_pct must be >= 0")
    if not (0.0 <= sell_rsi < rsi_min):
        raise ValueError("sell_rsi must be >= 0 and below rsi_min")

    min_history = max(trend_ema + 1, rsi_period + 1, slope_bars + 1, 4)

    def strategy(bar: pd.Series, history: pd.DataFrame) -> Action:
        if len(history) < min_history:
            return "HOLD"

        closes = pd.to_numeric(history["close"], errors="coerce")
        volumes = pd.to_numeric(history["volume"], errors="coerce")
        if closes.isna().any() or volumes.isna().any():
            return "HOLD"

        ema_fast_series = _ema(closes, fast_ema)
        ema_slow_series = _ema(closes, slow_ema)
        ema_trend_series = _ema(closes, trend_ema)
        rsi_series = _rsi_series(closes, rsi_period)

        fast = ema_fast_series.iloc[-1]
        slow = ema_slow_series.iloc[-1]
        trend = ema_trend_series.iloc[-1]
        rsi = rsi_series.iloc[-1]
        if any(pd.isna(x) for x in (fast, slow, trend, rsi)):
            return "HOLD"

        current_close = float(closes.iloc[-1])
        current_volume = float(volumes.iloc[-1])
        prior_volume_avg = float(volumes.iloc[-4:-1].mean())
        if prior_volume_avg <= 0:
            return "HOLD"

        prev_fast = ema_fast_series.iloc[-1 - slope_bars]
        prev_slow = ema_slow_series.iloc[-1 - slope_bars]
        if pd.isna(prev_fast) or pd.isna(prev_slow):
            return "HOLD"

        fast_rising = fast > prev_fast
        slow_rising = slow > prev_slow
        stacked = fast > slow > trend
        not_extended = current_close >= float(fast) * (1.0 - pullback_pct / 100.0)
        momentum_ok = rsi_min <= float(rsi) <= rsi_max
        volume_ok = current_volume >= prior_volume_avg * volume_multiplier

        if stacked and fast_rising and slow_rising and not_extended and momentum_ok and volume_ok:
            return "BUY"

        if current_close < float(fast) or float(rsi) <= sell_rsi:
            return "SELL"

        return "HOLD"

    return strategy
