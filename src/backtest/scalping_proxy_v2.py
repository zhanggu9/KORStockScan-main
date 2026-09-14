from __future__ import annotations

from collections import deque
from typing import Callable, Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame], Action]


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

    Indicator values are updated incrementally per bar instead of being
    recomputed from the full history on every strategy call.
    """
    if not (1 <= fast_ema < slow_ema):
        raise ValueError("fast_ema must be smaller than slow_ema")
    if rsi_period < 2 or not (0 <= rsi_min < rsi_max <= 100):
        raise ValueError("invalid RSI parameters")
    if volume_multiplier <= 0 or volume_window < 1 or breakout_lookback < 1:
        raise ValueError("invalid volume/breakout parameters")

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

    def strategy(bar: pd.Series, history: pd.DataFrame) -> Action:
        nonlocal count, previous_datetime, previous_close
        nonlocal fast_value, slow_value, previous_slow
        nonlocal avg_gain, avg_loss, valid_rsi_deltas
        nonlocal cumulative_pv, cumulative_volume, session_date
        nonlocal vwap_value, previous_vwap

        if history.empty:
            return "HOLD"

        current = history.iloc[-1]
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
        close = float(close)
        high = float(high)
        low = float(low)
        volume = float(volume)

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
                avg_gain = gain
                avg_loss = loss
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

        if avg_loss == 0.0:
            rv = 100.0
        else:
            rs = avg_gain / avg_loss
            rv = 100.0 - (100.0 / (1.0 + rs))

        trend_ok = fast_value > slow_value and slow_value > previous_slow
        vwap_ok = close > vwap_value and (not require_vwap_rising or vwap_value >= previous_vwap)
        momentum_ok = rsi_min <= rv <= rsi_max
        volume_ok = volume >= prior_volume * volume_multiplier
        breakout_ok = close > recent_high

        if trend_ok and vwap_ok and momentum_ok and volume_ok and breakout_ok:
            return "BUY"
        if close < fast_value or close < vwap_value or rv < rsi_min - 10.0:
            return "SELL"
        return "HOLD"

    return strategy
