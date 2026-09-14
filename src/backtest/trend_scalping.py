from __future__ import annotations

from typing import Callable, Literal

import numpy as np
import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame | None], Action]


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
    """OHLCV-only intraday continuation strategy."""
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

    def strategy(bar: pd.Series, history: pd.DataFrame | None = None) -> Action:
        if history is None or len(history) < min_history:
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

    def prepare_signals(frame: pd.DataFrame) -> np.ndarray:
        closes = pd.to_numeric(frame["close"], errors="coerce")
        volumes = pd.to_numeric(frame["volume"], errors="coerce")
        actions = np.full(len(frame), "HOLD", dtype="U4")
        if len(frame) < min_history or closes.isna().any() or volumes.isna().any():
            return actions

        ema_fast = _ema(closes, fast_ema).to_numpy(dtype=float)
        ema_slow = _ema(closes, slow_ema).to_numpy(dtype=float)
        ema_trend = _ema(closes, trend_ema).to_numpy(dtype=float)
        rsi = _rsi_series(closes, rsi_period).to_numpy(dtype=float)
        close_values = closes.to_numpy(dtype=float)
        volume_values = volumes.to_numpy(dtype=float)
        prior_volume_avg = volumes.shift(1).rolling(3).mean().to_numpy(dtype=float)

        prev_fast = np.full(len(frame), np.nan, dtype=float)
        prev_slow = np.full(len(frame), np.nan, dtype=float)
        if slope_bars < len(frame):
            prev_fast[slope_bars:] = ema_fast[:-slope_bars]
            prev_slow[slope_bars:] = ema_slow[:-slope_bars]

        valid = (
            ~np.isnan(ema_fast)
            & ~np.isnan(ema_slow)
            & ~np.isnan(ema_trend)
            & ~np.isnan(rsi)
            & ~np.isnan(prev_fast)
            & ~np.isnan(prev_slow)
            & (prior_volume_avg > 0)
        )
        fast_rising = ema_fast > prev_fast
        slow_rising = ema_slow > prev_slow
        stacked = (ema_fast > ema_slow) & (ema_slow > ema_trend)
        not_extended = close_values >= ema_fast * (1.0 - pullback_pct / 100.0)
        momentum_ok = (rsi >= rsi_min) & (rsi <= rsi_max)
        volume_ok = volume_values >= prior_volume_avg * volume_multiplier
        buy = valid & stacked & fast_rising & slow_rising & not_extended & momentum_ok & volume_ok
        sell = valid & ((close_values < ema_fast) | (rsi <= sell_rsi))
        actions[buy] = "BUY"
        actions[sell & ~buy] = "SELL"
        return actions

    strategy.prepare_signals = prepare_signals
    return strategy
