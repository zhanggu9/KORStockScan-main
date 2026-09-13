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


def _vwap(frame: pd.DataFrame) -> pd.Series:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    day = frame["datetime"].dt.date
    pv = typical * frame["volume"]
    return pv.groupby(day).cumsum() / frame["volume"].groupby(day).cumsum().replace(0.0, float("nan"))


def pullback_scalping_strategy(
    fast_ema: int = 9,
    slow_ema: int = 20,
    trend_ema: int = 60,
    rsi_period: int = 14,
    rsi_min: float = 55.0,
    rsi_max: float = 75.0,
    volume_multiplier: float = 1.3,
    pullback_lookback: int = 8,
    touch_tolerance_pct: float = 0.6,
    max_pullback_pct: float = 1.5,
    breakout_lookback: int = 2,
    min_body_pct: float = 0.25,
) -> SignalFn:
    """Trend-following pullback/re-breakout strategy for 1-minute OHLCV bars.

    BUY requires: EMA9 > EMA20 > EMA60, rising EMA20, price above VWAP,
    a recent controlled touch of EMA20 without a deep breakdown, then a
    bullish close breaking the prior short-range high with increased volume.
    RSI is used only as a momentum guard, not as the trigger.
    SELL is generated when price loses EMA20 or VWAP with weak momentum.
    """
    if not (1 <= fast_ema < slow_ema < trend_ema):
        raise ValueError("EMA periods must satisfy fast_ema < slow_ema < trend_ema")
    if rsi_period < 2 or not (0 <= rsi_min < rsi_max <= 100):
        raise ValueError("invalid RSI parameters")
    if volume_multiplier <= 0 or pullback_lookback < 2 or breakout_lookback < 1:
        raise ValueError("invalid lookback/volume parameters")
    if touch_tolerance_pct < 0 or max_pullback_pct <= 0:
        raise ValueError("pullback percentages must be valid")
    if not (0 <= min_body_pct <= 1):
        raise ValueError("min_body_pct must be between 0 and 1")

    min_history = max(trend_ema + 2, rsi_period + 2, pullback_lookback + 2, 10)

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
        trend = _ema(close, trend_ema)
        rsi = _rsi(close, rsi_period)
        vwap = _vwap(x)

        ef, es, et = fast.iloc[-1], slow.iloc[-1], trend.iloc[-1]
        prev_es = slow.iloc[-2]
        rv, vw = rsi.iloc[-1], vwap.iloc[-1]
        if any(pd.isna(v) for v in [ef, es, et, prev_es, rv, vw]):
            return "HOLD"

        c = float(x["close"].iloc[-1])
        o = float(x["open"].iloc[-1])
        h = float(x["high"].iloc[-1])
        l = float(x["low"].iloc[-1])
        current_volume = float(x["volume"].iloc[-1])

        prior = x.iloc[-pullback_lookback - 1 : -1].copy()
        if len(prior) < pullback_lookback:
            return "HOLD"
        prior_slow = _ema(close.iloc[:-1], slow_ema).iloc[-pullback_lookback:]
        if len(prior_slow) != pullback_lookback or prior_slow.isna().any():
            return "HOLD"

        touch = float((prior["low"] / prior_slow - 1.0).min()) <= touch_tolerance_pct / 100.0
        hold_above = float((prior["low"] / prior_slow - 1.0).min()) >= -max_pullback_pct / 100.0
        recent_high = float(x["high"].iloc[-breakout_lookback - 1 : -1].max())
        prior_volume_avg = float(x["volume"].iloc[-6:-1].mean())
        if prior_volume_avg <= 0:
            return "HOLD"

        body = abs(c - o)
        range_ = max(h - l, 1e-9)
        bullish = c > o and body / range_ >= min_body_pct
        breakout = c > recent_high
        volume_ok = current_volume >= prior_volume_avg * volume_multiplier
        trend_ok = float(ef) > float(es) > float(et) and float(es) > float(prev_es)
        vwap_ok = c > float(vw)
        momentum_ok = float(rsi_min) <= float(rv) <= float(rsi_max)

        if trend_ok and vwap_ok and touch and hold_above and bullish and breakout and volume_ok and momentum_ok:
            return "BUY"

        if c < float(es) or c < float(vw) or float(rv) < rsi_min - 8.0:
            return "SELL"
        return "HOLD"

    return strategy
