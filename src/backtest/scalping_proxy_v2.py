from __future__ import annotations

from typing import Callable, Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame], Action]


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.mask(avg_loss == 0.0, 100.0)
    out = out.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    return out


def _session_vwap(frame: pd.DataFrame) -> pd.Series:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    day = frame["datetime"].dt.date
    pv = typical * frame["volume"]
    cumulative_pv = pv.groupby(day).cumsum()
    cumulative_volume = frame["volume"].groupby(day).cumsum().replace(0.0, float("nan"))
    return cumulative_pv / cumulative_volume


def scalping_proxy_v2_strategy(
    rsi_period: int = 14,
    rsi_min: float = 70.0,
    rsi_max: float = 85.0,
    volume_multiplier: float = 2.0,
    volume_window: int = 3,
    fast_ema: int = 9,
    slow_ema: int = 20,
    breakout_lookback: int = 2,
    require_vwap_rising: bool = True,
) -> SignalFn:
    """Momentum scalping proxy filtered by EMA trend and session VWAP.

    BUY: EMA fast > slow, slow EMA rising, close above VWAP, optional VWAP rise,
    RSI within a strong-but-not-extreme band, volume expansion, and a short
    breakout. RSI is a guard, not the sole trigger.
    SELL: close loses fast EMA or VWAP, or RSI falls materially below the band.
    """
    if not (1 <= fast_ema < slow_ema):
        raise ValueError("fast_ema must be smaller than slow_ema")
    if rsi_period < 2 or not (0 <= rsi_min < rsi_max <= 100):
        raise ValueError("invalid RSI parameters")
    if volume_multiplier <= 0 or volume_window < 1 or breakout_lookback < 1:
        raise ValueError("invalid volume/breakout parameters")

    min_history = max(slow_ema + 2, rsi_period + 2, volume_window + 2, breakout_lookback + 2, 10)

    def strategy(bar: pd.Series, history: pd.DataFrame) -> Action:
        if len(history) < min_history:
            return "HOLD"
        x = history.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            x[col] = pd.to_numeric(x[col], errors="coerce")
        x["datetime"] = pd.to_datetime(x["datetime"], errors="coerce")
        x = x.dropna(subset=["datetime", "open", "high", "low", "close", "volume"])
        if len(x) < min_history:
            return "HOLD"

        close = x["close"]
        fast = _ema(close, fast_ema)
        slow = _ema(close, slow_ema)
        rsi = _rsi(close, rsi_period)
        vwap = _session_vwap(x)

        ef, es = fast.iloc[-1], slow.iloc[-1]
        prev_es = slow.iloc[-2]
        rv, vw = rsi.iloc[-1], vwap.iloc[-1]
        prev_vw = vwap.iloc[-2]
        if any(pd.isna(v) for v in [ef, es, prev_es, rv, vw, prev_vw]):
            return "HOLD"

        c = float(close.iloc[-1])
        volume = float(x["volume"].iloc[-1])
        prior_volume = float(x["volume"].iloc[-volume_window - 1:-1].mean())
        recent_high = float(x["high"].iloc[-breakout_lookback - 1:-1].max())
        if prior_volume <= 0:
            return "HOLD"

        trend_ok = float(ef) > float(es) and float(es) > float(prev_es)
        vwap_ok = c > float(vw) and (not require_vwap_rising or float(vw) >= float(prev_vw))
        momentum_ok = float(rsi_min) <= float(rv) <= float(rsi_max)
        volume_ok = volume >= prior_volume * volume_multiplier
        breakout_ok = c > recent_high

        if trend_ok and vwap_ok and momentum_ok and volume_ok and breakout_ok:
            return "BUY"
        if c < float(ef) or c < float(vw) or float(rv) < rsi_min - 10.0:
            return "SELL"
        return "HOLD"

    return strategy
