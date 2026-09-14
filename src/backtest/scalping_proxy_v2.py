from __future__ import annotations

from collections import deque
from typing import Callable, Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame | None], Action]


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


def _session_minute_ok(timestamp: pd.Timestamp, start_minute: int, end_minute: int) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return start_minute <= minute <= end_minute


def scalping_proxy_v2_indicators(
    frame: pd.DataFrame,
    rsi_period: int = 14,
    rsi_min: float = 70.0,
    rsi_max: float = 85.0,
    volume_multiplier: float = 2.0,
    volume_window: int = 3,
    fast_ema: int = 9,
    slow_ema: int = 20,
    breakout_lookback: int = 2,
    require_vwap_rising: bool = True,
) -> pd.DataFrame:
    if not (1 <= fast_ema < slow_ema):
        raise ValueError("fast_ema must be smaller than slow_ema")
    if rsi_period < 2 or not (0 <= rsi_min < rsi_max <= 100):
        raise ValueError("invalid RSI parameters")
    if volume_multiplier <= 0 or volume_window < 1 or breakout_lookback < 1:
        raise ValueError("invalid volume/breakout parameters")

    out = frame.copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    for col in ["high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = (
        out.dropna(subset=["datetime", "high", "low", "close", "volume"])
        .sort_values("datetime")
        .drop_duplicates("datetime")
        .reset_index(drop=True)
    )
    if out.empty:
        return pd.DataFrame(index=out.index)

    close = out["close"]
    out["v2_ema_fast"] = _ema(close, fast_ema)
    out["v2_ema_slow"] = _ema(close, slow_ema)
    out["v2_ema_spread_pct"] = (out["v2_ema_fast"] / out["v2_ema_slow"] - 1.0) * 100.0
    out["v2_ema_slow_slope_pct"] = (out["v2_ema_slow"] / out["v2_ema_slow"].shift(1) - 1.0) * 100.0
    out["v2_rsi"] = _rsi(close, rsi_period)

    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    day = out["datetime"].dt.date
    cumulative_volume = out["volume"].groupby(day).cumsum()
    out["v2_vwap"] = (typical * out["volume"]).groupby(day).cumsum() / cumulative_volume.replace(0.0, float("nan"))
    out["v2_vwap_distance_pct"] = (out["close"] / out["v2_vwap"] - 1.0) * 100.0
    out["v2_vwap_slope_pct"] = (out["v2_vwap"] / out["v2_vwap"].shift(1) - 1.0) * 100.0

    prior_volume = out["volume"].shift(1).rolling(volume_window).mean()
    prior_high = out["high"].shift(1).rolling(breakout_lookback).max()
    out["v2_volume_ratio"] = out["volume"] / prior_volume.replace(0.0, float("nan"))
    out["v2_breakout_distance_pct"] = (out["close"] / prior_high - 1.0) * 100.0
    out["v2_trend_ok"] = (out["v2_ema_fast"] > out["v2_ema_slow"]) & (out["v2_ema_slow_slope_pct"] > 0)
    out["v2_vwap_ok"] = (out["close"] > out["v2_vwap"]) & (~require_vwap_rising | (out["v2_vwap_slope_pct"] >= 0))
    out["v2_momentum_ok"] = out["v2_rsi"].between(rsi_min, rsi_max, inclusive="both")
    out["v2_volume_ok"] = out["v2_volume_ratio"] >= volume_multiplier
    out["v2_breakout_ok"] = out["close"] > prior_high
    out["v2_signal_strength"] = out[["v2_trend_ok", "v2_vwap_ok", "v2_momentum_ok", "v2_volume_ok", "v2_breakout_ok"]].astype(int).sum(axis=1)
    return out


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
    entry_start_minute: int = 0,
    entry_end_minute: int = 1439,
    min_ema_spread_pct: float = 0.0,
    min_breakout_distance_pct: float = 0.0,
    max_volume_ratio: float | None = None,
) -> SignalFn:
    if not (1 <= fast_ema < slow_ema):
        raise ValueError("fast_ema must be smaller than slow_ema")
    if rsi_period < 2 or not (0 <= rsi_min < rsi_max <= 100):
        raise ValueError("invalid RSI parameters")
    if volume_multiplier <= 0 or volume_window < 1 or breakout_lookback < 1:
        raise ValueError("invalid volume/breakout parameters")
    if not (0 <= entry_start_minute <= entry_end_minute <= 1439):
        raise ValueError("invalid entry session")
    if min_ema_spread_pct < 0 or min_breakout_distance_pct < 0:
        raise ValueError("entry quality thresholds must be non-negative")
    if max_volume_ratio is not None and max_volume_ratio <= 0:
        raise ValueError("max_volume_ratio must be positive or None")

    min_history = max(slow_ema + 2, rsi_period + 2, volume_window + 2, breakout_lookback + 2, 10)
    alpha_rsi = 1.0 / rsi_period
    alpha_fast = 2.0 / (fast_ema + 1.0)
    alpha_slow = 2.0 / (slow_ema + 1.0)

    count = 0
    previous_datetime: pd.Timestamp | None = None
    previous_close: float | None = None
    fast_value: float | None = None
    slow_value: float | None = None
    previous_slow: float | None = None
    avg_gain: float | None = None
    avg_loss: float | None = None
    valid_rsi_deltas = 0
    cumulative_pv = 0.0
    cumulative_volume = 0.0
    session_date = None
    vwap_value: float | None = None
    previous_vwap: float | None = None
    prior_volumes: deque[float] = deque(maxlen=volume_window)
    prior_highs: deque[float] = deque(maxlen=breakout_lookback)

    def reset() -> None:
        nonlocal count, previous_datetime, previous_close
        nonlocal fast_value, slow_value, previous_slow
        nonlocal avg_gain, avg_loss, valid_rsi_deltas
        nonlocal cumulative_pv, cumulative_volume, session_date
        nonlocal vwap_value, previous_vwap
        prior_volumes.clear()
        prior_highs.clear()
        count = 0
        previous_datetime = None
        previous_close = None
        fast_value = None
        slow_value = None
        previous_slow = None
        avg_gain = None
        avg_loss = None
        valid_rsi_deltas = 0
        cumulative_pv = 0.0
        cumulative_volume = 0.0
        session_date = None
        vwap_value = None
        previous_vwap = None

    def strategy(bar: pd.Series, history: pd.DataFrame | None = None) -> Action:
        nonlocal count, previous_datetime, previous_close
        nonlocal fast_value, slow_value, previous_slow
        nonlocal avg_gain, avg_loss, valid_rsi_deltas
        nonlocal cumulative_pv, cumulative_volume, session_date
        nonlocal vwap_value, previous_vwap

        current = bar if bar is not None else (history.iloc[-1] if history is not None and not history.empty else None)
        if current is None:
            return "HOLD"

        timestamp = pd.to_datetime(current["datetime"], errors="coerce")
        if pd.isna(timestamp):
            return "HOLD"
        if previous_datetime is not None and timestamp <= previous_datetime:
            reset()

        close = pd.to_numeric(current["close"], errors="coerce")
        high = pd.to_numeric(current["high"], errors="coerce")
        low = pd.to_numeric(current["low"], errors="coerce")
        volume = pd.to_numeric(current["volume"], errors="coerce")
        if any(pd.isna(v) for v in [close, high, low, volume]):
            return "HOLD"
        close, high, low, volume = map(float, (close, high, low, volume))

        if count == 0:
            fast_value = close
            slow_value = close
            previous_slow = None
        else:
            previous_slow = slow_value
            fast_value = alpha_fast * close + (1.0 - alpha_fast) * fast_value
            slow_value = alpha_slow * close + (1.0 - alpha_slow) * slow_value

        if previous_close is not None:
            delta = close - previous_close
            gain = max(delta, 0.0)
            loss = max(-delta, 0.0)
            if valid_rsi_deltas == 0:
                avg_gain, avg_loss = gain, loss
            else:
                avg_gain = alpha_rsi * gain + (1.0 - alpha_rsi) * avg_gain
                avg_loss = alpha_rsi * loss + (1.0 - alpha_rsi) * avg_loss
            valid_rsi_deltas += 1

        current_day = timestamp.date()
        if session_date != current_day:
            session_date = current_day
            cumulative_pv = 0.0
            cumulative_volume = 0.0
        previous_vwap = vwap_value
        typical = (high + low + close) / 3.0
        cumulative_pv += typical * volume
        cumulative_volume += volume
        vwap_value = cumulative_pv / cumulative_volume if cumulative_volume > 0 else float("nan")

        prior_volume = sum(prior_volumes) / len(prior_volumes) if prior_volumes else 0.0
        recent_high = max(prior_highs) if prior_highs else float("nan")
        prior_volumes.append(volume)
        prior_highs.append(high)

        count += 1
        previous_datetime = timestamp
        previous_close = close

        if count < min_history or valid_rsi_deltas < rsi_period:
            return "HOLD"
        if any(v is None or pd.isna(v) for v in [fast_value, slow_value, previous_slow, avg_gain, avg_loss, vwap_value, previous_vwap]):
            return "HOLD"
        if prior_volume <= 0 or pd.isna(recent_high):
            return "HOLD"

        rv = 100.0 if avg_loss == 0.0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        trend_ok = fast_value > slow_value and slow_value > previous_slow
        vwap_ok = close > vwap_value and (not require_vwap_rising or vwap_value >= previous_vwap)
        momentum_ok = rsi_min <= rv <= rsi_max
        volume_ratio = volume / prior_volume
        volume_ok = volume_ratio >= volume_multiplier
        volume_cap_ok = max_volume_ratio is None or volume_ratio <= max_volume_ratio
        breakout_distance_pct = (close / recent_high - 1.0) * 100.0
        breakout_ok = close > recent_high
        ema_spread_pct = (fast_value / slow_value - 1.0) * 100.0
        ema_spread_ok = ema_spread_pct >= min_ema_spread_pct
        breakout_strength_ok = breakout_distance_pct >= min_breakout_distance_pct
        session_ok = _session_minute_ok(timestamp, entry_start_minute, entry_end_minute)

        if trend_ok and vwap_ok and momentum_ok and volume_ok and volume_cap_ok and breakout_ok and ema_spread_ok and breakout_strength_ok and session_ok:
            return "BUY"
        if close < fast_value or close < vwap_value or rv < rsi_min - 10.0:
            return "SELL"
        return "HOLD"

    return strategy
