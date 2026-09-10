from __future__ import annotations

import pandas as pd


def ema_cross_strategy(
    fast: int = 5,
    slow: int = 20,
):
    if fast < 1 or slow <= fast:
        raise ValueError("slow must be greater than fast, and fast must be >= 1")

    def strategy(bar: pd.Series, history: pd.DataFrame) -> str:
        closes = pd.to_numeric(history["close"], errors="coerce")
        fast_ema = closes.ewm(span=fast, adjust=False, min_periods=fast).mean().iloc[-1]
        slow_ema = closes.ewm(span=slow, adjust=False, min_periods=slow).mean().iloc[-1]
        if pd.isna(fast_ema) or pd.isna(slow_ema):
            return "HOLD"

        prev = closes.iloc[:-1]
        if len(prev) < slow:
            return "HOLD"
        prev_fast = prev.ewm(span=fast, adjust=False, min_periods=fast).mean().iloc[-1]
        prev_slow = prev.ewm(span=slow, adjust=False, min_periods=slow).mean().iloc[-1]
        if fast_ema > slow_ema and prev_fast <= prev_slow:
            return "BUY"
        if fast_ema < slow_ema and prev_fast >= prev_slow:
            return "SELL"
        return "HOLD"

    return strategy


def _rsi(closes: pd.Series, period: int) -> float:
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    latest_gain = avg_gain.iloc[-1]
    latest_loss = avg_loss.iloc[-1]
    if pd.isna(latest_gain) or pd.isna(latest_loss):
        return float("nan")
    if latest_loss == 0:
        return 100.0
    if latest_gain == 0:
        return 0.0
    rs = latest_gain / latest_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def one_minute_scalping_proxy_strategy(
    rsi_period: int = 14,
    rsi_buy: float = 70.0,
    rsi_sell: float = 50.0,
    volume_multiplier: float = 2.5,
    average_window: int = 3,
    price_distance_pct: float = 2.0,
):
    """OHLCV-only proxy for the user's intraday scalping rules.

    The live radar uses websocket order-book imbalance, execution strength,
    liquidity, and AI inputs. Those are not present in the historical 1-minute
    CSV schema, so this strategy intentionally reproduces only the OHLCV rules:
      BUY: RSI >= 70 AND volume >= 2.5x the prior 3-bar average AND
           close >= 2% above the prior 3-bar average close
      SELL: RSI <= 50

    Signals are evaluated on the current bar; the backtest engine executes them
    on the next bar open by default, avoiding look-ahead.
    """
    if rsi_period < 2:
        raise ValueError("rsi_period must be >= 2")
    if average_window < 1:
        raise ValueError("average_window must be >= 1")
    if volume_multiplier <= 0:
        raise ValueError("volume_multiplier must be > 0")
    if price_distance_pct < 0:
        raise ValueError("price_distance_pct must be >= 0")
    if rsi_sell >= rsi_buy:
        raise ValueError("rsi_sell must be lower than rsi_buy")

    min_history = max(rsi_period + 1, average_window + 1)

    def strategy(bar: pd.Series, history: pd.DataFrame) -> str:
        if len(history) < min_history:
            return "HOLD"

        closes = pd.to_numeric(history["close"], errors="coerce")
        volumes = pd.to_numeric(history["volume"], errors="coerce")
        if closes.isna().any() or volumes.isna().any():
            return "HOLD"

        current_close = float(closes.iloc[-1])
        current_volume = float(volumes.iloc[-1])
        prior_closes = closes.iloc[-average_window - 1 : -1]
        prior_volumes = volumes.iloc[-average_window - 1 : -1]
        if len(prior_closes) < average_window or len(prior_volumes) < average_window:
            return "HOLD"

        avg_close = float(prior_closes.mean())
        avg_volume = float(prior_volumes.mean())
        rsi_value = _rsi(closes, rsi_period)
        if pd.isna(rsi_value) or avg_close <= 0 or avg_volume <= 0:
            return "HOLD"

        volume_ok = current_volume >= avg_volume * volume_multiplier
        price_ok = current_close >= avg_close * (1.0 + price_distance_pct / 100.0)

        if rsi_value >= rsi_buy and volume_ok and price_ok:
            return "BUY"
        if rsi_value <= rsi_sell:
            return "SELL"
        return "HOLD"

    return strategy
