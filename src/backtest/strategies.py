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


def _rsi(closes: pd.Series, period: int) -> float:
    value = _rsi_series(closes, period).iloc[-1]
    return float(value) if not pd.isna(value) else float("nan")


def one_minute_scalping_proxy_strategy(
    rsi_period: int = 14,
    rsi_buy: float = 70.0,
    rsi_sell: float = 50.0,
    volume_multiplier: float = 2.5,
    average_window: int = 3,
    price_distance_pct: float = 2.0,
):
    """OHLCV-only proxy for the user's intraday scalping rules.

    BUY: RSI >= 70 AND current volume >= prior-window average * 2.5 AND
         current close >= prior-window average close * 1.02.
    SELL: RSI <= 50.

    Signals are evaluated on the current bar. The backtest engine executes
    next-bar open by default, avoiding look-ahead.
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


def diagnose_one_minute_scalping_proxy(
    frame: pd.DataFrame,
    rsi_period: int = 14,
    rsi_buy: float = 70.0,
    rsi_sell: float = 50.0,
    volume_multiplier: float = 2.5,
    average_window: int = 3,
    price_distance_pct: float = 2.0,
) -> dict[str, float | int]:
    """Return condition statistics to explain zero-signal backtests."""
    required = {"datetime", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for diagnostics: {sorted(missing)}")

    bars = frame.copy()
    bars["datetime"] = pd.to_datetime(bars["datetime"], errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars["volume"] = pd.to_numeric(bars["volume"], errors="coerce")
    bars = bars.dropna(subset=["datetime", "close", "volume"]).sort_values("datetime")
    bars = bars.drop_duplicates("datetime").reset_index(drop=True)

    if bars.empty:
        return {
            "valid_bars": 0,
            "rsi_buy_pass": 0,
            "volume_pass": 0,
            "price_pass": 0,
            "all_buy_pass": 0,
            "rsi_sell_pass": 0,
            "max_rsi": float("nan"),
            "max_volume_ratio": float("nan"),
            "max_price_distance_pct": float("nan"),
        }

    closes = bars["close"]
    volumes = bars["volume"]
    rsi = _rsi_series(closes, rsi_period)
    prior_close_avg = closes.shift(1).rolling(average_window).mean()
    prior_volume_avg = volumes.shift(1).rolling(average_window).mean()

    valid = (
        rsi.notna()
        & prior_close_avg.notna()
        & prior_volume_avg.notna()
        & (prior_close_avg > 0)
        & (prior_volume_avg > 0)
    )
    rsi_buy_mask = valid & (rsi >= rsi_buy)
    volume_ratio = volumes / prior_volume_avg
    volume_mask = valid & (volume_ratio >= volume_multiplier)
    price_distance = (closes / prior_close_avg - 1.0) * 100.0
    price_mask = valid & (price_distance >= price_distance_pct)
    all_buy_mask = rsi_buy_mask & volume_mask & price_mask
    rsi_sell_mask = valid & (rsi <= rsi_sell)

    valid_rsi = rsi[valid]
    valid_volume_ratio = volume_ratio[valid]
    valid_price_distance = price_distance[valid]

    return {
        "valid_bars": int(valid.sum()),
        "rsi_buy_pass": int(rsi_buy_mask.sum()),
        "volume_pass": int(volume_mask.sum()),
        "price_pass": int(price_mask.sum()),
        "all_buy_pass": int(all_buy_mask.sum()),
        "rsi_sell_pass": int(rsi_sell_mask.sum()),
        "max_rsi": float(valid_rsi.max()) if not valid_rsi.empty else float("nan"),
        "max_volume_ratio": float(valid_volume_ratio.max()) if not valid_volume_ratio.empty else float("nan"),
        "max_price_distance_pct": float(valid_price_distance.max()) if not valid_price_distance.empty else float("nan"),
    }
