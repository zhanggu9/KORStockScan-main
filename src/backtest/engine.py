from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np
import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame | None], Action]


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 10_000_000.0
    fee_bps: float = 15.0
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 5.0
    slippage_bps: float | None = None
    execution: Literal["next_open", "close"] = "next_open"
    force_close_eod: bool = True
    atr_period: int | None = None
    stop_atr: float | None = None
    target_atr: float | None = None
    trailing_atr: float | None = None
    max_hold_bars: int | None = None
    peak_retrace_1_pct: float | None = None
    peak_retrace_1_ratio: float = 0.40
    peak_retrace_2_pct: float | None = None
    peak_retrace_2_ratio: float = 0.60


@dataclass
class Trade:
    code: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    quantity: int
    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float
    return_pct: float
    exit_reason: str = "SIGNAL"


@dataclass
class BacktestResult:
    code: str
    initial_cash: float
    final_cash: float
    equity_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"datetime", "code", "open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    out = frame.copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["datetime", "open", "high", "low", "close"])
    out = out.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    if out.empty:
        raise ValueError("No valid OHLCV rows remain after normalization")
    if out["code"].astype(str).nunique() != 1:
        raise ValueError("run_backtest accepts exactly one stock code per run")
    return out


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    prev_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _apply_buy_slippage(raw_price: float, slippage_bps: float) -> float:
    return raw_price * (1.0 + slippage_bps / 10_000.0)


def _apply_sell_slippage(raw_price: float, slippage_bps: float) -> float:
    return raw_price * (1.0 - slippage_bps / 10_000.0)


def _fee(notional: float, fee_bps: float) -> float:
    return notional * fee_bps / 10_000.0


def run_backtest(frame: pd.DataFrame, strategy: SignalFn, config: BacktestConfig | None = None) -> BacktestResult:
    config = config or BacktestConfig()
    exit_slippage_bps = config.slippage_bps if config.slippage_bps is not None else config.exit_slippage_bps
    if exit_slippage_bps < 0 or config.fee_bps < 0 or config.entry_slippage_bps < 0:
        raise ValueError("fee/slippage values must be >= 0")
    risk_values = [config.atr_period, config.stop_atr, config.target_atr, config.trailing_atr, config.max_hold_bars, config.peak_retrace_1_pct, config.peak_retrace_2_pct]
    if any(v is not None and v <= 0 for v in risk_values):
        raise ValueError("risk parameters must be > 0 when provided")
    if not 0 < config.peak_retrace_1_ratio <= 1 or not 0 < config.peak_retrace_2_ratio <= 1:
        raise ValueError("peak retrace ratios must be in (0, 1]")
    if config.peak_retrace_1_pct is not None and config.peak_retrace_2_pct is not None and config.peak_retrace_2_pct <= config.peak_retrace_1_pct:
        raise ValueError("peak_retrace_2_pct must be greater than peak_retrace_1_pct")

    bars = _prepare_frame(frame)
    atr_series = _atr(bars, config.atr_period) if config.atr_period else pd.Series(float("nan"), index=bars.index)
    atr_values = atr_series.to_numpy(dtype=float)
    datetimes = bars["datetime"].to_numpy()
    days = bars["datetime"].dt.date.to_numpy()
    opens = bars["open"].to_numpy(dtype=float)
    highs = bars["high"].to_numpy(dtype=float)
    lows = bars["low"].to_numpy(dtype=float)
    closes = bars["close"].to_numpy(dtype=float)
    code = str(bars["code"].iloc[0])

    prepared = getattr(strategy, "prepare_signals", None)
    prepared_actions: np.ndarray | None = None
    if callable(prepared):
        prepared_actions = np.asarray(prepared(bars))
        if len(prepared_actions) != len(bars):
            raise ValueError("prepare_signals must return one action per bar")

    cash = float(config.initial_cash)
    quantity = 0
    entry_time: pd.Timestamp | None = None
    entry_price = 0.0
    entry_fees = 0.0
    entry_slippage_cost = 0.0
    entry_atr: float | None = None
    highest_high = 0.0
    hold_bars = 0
    peak_stage = 0
    trades: list[Trade] = []
    equity_rows: list[dict] = []
    pending: Action = "HOLD"
    pending_index: int | None = None

    def execute(action: Action, index: int, reason: str = "SIGNAL", quantity_override: int | None = None) -> int:
        nonlocal cash, quantity, entry_time, entry_price, entry_fees, entry_slippage_cost
        nonlocal entry_atr, highest_high, hold_bars, peak_stage
        raw_price = closes[index] if config.execution == "close" else opens[index]
        timestamp = pd.Timestamp(datetimes[index])

        if action == "BUY" and quantity == 0:
            execution_price = _apply_buy_slippage(float(raw_price), config.entry_slippage_bps)
            max_qty = int(cash / (execution_price * (1.0 + config.fee_bps / 10_000.0)))
            if max_qty <= 0:
                return 0
            notional = execution_price * max_qty
            fees = _fee(notional, config.fee_bps)
            cash -= notional + fees
            quantity = max_qty
            entry_time = timestamp
            entry_price = execution_price
            entry_fees = fees
            entry_slippage_cost = abs(execution_price - raw_price) * max_qty
            atr_value = atr_values[index]
            entry_atr = float(atr_value) if not np.isnan(atr_value) else None
            highest_high = highs[index]
            hold_bars = 0
            peak_stage = 0
            return max_qty

        if action == "SELL" and quantity > 0:
            sell_qty = quantity if quantity_override is None else min(int(quantity_override), quantity)
            if sell_qty <= 0:
                return 0
            execution_price = _apply_sell_slippage(float(raw_price), exit_slippage_bps)
            notional = execution_price * sell_qty
            fees = _fee(notional, config.fee_bps)
            cash += notional - fees
            gross_pnl = (execution_price - entry_price) * sell_qty
            exit_slippage_cost = abs(raw_price - execution_price) * sell_qty
            allocated_entry_fees = entry_fees * (sell_qty / quantity)
            allocated_entry_slippage = entry_slippage_cost * (sell_qty / quantity)
            total_slippage_cost = allocated_entry_slippage + exit_slippage_cost
            total_fees = allocated_entry_fees + fees
            net_pnl = gross_pnl - total_fees
            invested = entry_price * sell_qty + allocated_entry_fees
            return_pct = net_pnl / invested * 100.0 if invested else 0.0
            trades.append(Trade(code, entry_time or timestamp, entry_price, timestamp, execution_price, sell_qty, gross_pnl, total_fees, total_slippage_cost, net_pnl, return_pct, reason))
            quantity -= sell_qty
            entry_fees -= allocated_entry_fees
            entry_slippage_cost -= allocated_entry_slippage
            if quantity == 0:
                entry_time = None
                entry_price = 0.0
                entry_fees = 0.0
                entry_slippage_cost = 0.0
                entry_atr = None
                highest_high = 0.0
                hold_bars = 0
                peak_stage = 0
            return sell_qty
        return 0

    def risk_exit(index: int) -> bool:
        nonlocal highest_high, hold_bars, peak_stage
        if quantity <= 0:
            return False
        highest_high = max(highest_high, highs[index])
        hold_bars += 1
        atr = entry_atr
        stop_price = entry_price - atr * config.stop_atr if atr is not None and config.stop_atr is not None else None
        target_price = entry_price + atr * config.target_atr if atr is not None and config.target_atr is not None else None
        trail_price = highest_high - atr * config.trailing_atr if atr is not None and config.trailing_atr is not None else None
        low, high = lows[index], highs[index]

        if stop_price is not None and low <= stop_price:
            execute("SELL", index, "ATR_STOP")
            return True
        if target_price is not None and high >= target_price:
            execute("SELL", index, "ATR_TARGET")
            return True

        if config.peak_retrace_2_pct is not None and peak_stage < 2:
            retrace_2 = (highest_high - low) / highest_high * 100.0 if highest_high > 0 else 0.0
            if retrace_2 >= config.peak_retrace_2_pct and peak_stage >= 1:
                sell_qty = int(round(quantity * config.peak_retrace_2_ratio)) or quantity
                execute("SELL", index, "PEAK_RETRACE_2", sell_qty)
                peak_stage = 2
                return quantity == 0

        if config.peak_retrace_1_pct is not None and peak_stage == 0:
            retrace_1 = (highest_high - low) / highest_high * 100.0 if highest_high > 0 else 0.0
            if retrace_1 >= config.peak_retrace_1_pct and highest_high > entry_price:
                sell_qty = int(round(quantity * config.peak_retrace_1_ratio))
                if sell_qty >= quantity:
                    sell_qty = max(quantity - 1, 0)
                if sell_qty > 0:
                    execute("SELL", index, "PEAK_RETRACE_1", sell_qty)
                    peak_stage = 1
                    if quantity == 0:
                        return True

        if trail_price is not None and low <= trail_price and highest_high > entry_price:
            execute("SELL", index, "ATR_TRAILING")
            return True
        if config.max_hold_bars is not None and hold_bars >= config.max_hold_bars:
            execute("SELL", index, "TIME_STOP")
            return True
        return False

    for i in range(len(bars)):
        next_day = days[i + 1] if i + 1 < len(bars) else None
        is_day_end = next_day != days[i]

        if pending_index == i:
            execute(pending, i)
            pending = "HOLD"
            pending_index = None

        risk_triggered = risk_exit(i)
        if risk_triggered:
            action: Action = "HOLD"
        elif prepared_actions is not None:
            action = str(prepared_actions[i])
        else:
            history = bars.iloc[: i + 1]
            action = strategy(bars.iloc[i], history)
        if action not in {"BUY", "SELL", "HOLD"}:
            raise ValueError(f"Strategy returned invalid action: {action!r}")

        if config.execution == "close":
            execute(action, i)
            if is_day_end and config.force_close_eod and quantity > 0:
                execute("SELL", i, "EOD")
        elif not is_day_end:
            pending = action
            pending_index = i + 1
        elif config.force_close_eod:
            if quantity > 0:
                execute("SELL", i, "EOD")
            pending = "HOLD"
            pending_index = None

        mark = cash + quantity * closes[i]
        equity_rows.append({"datetime": pd.Timestamp(datetimes[i]), "equity": mark if not (is_day_end and quantity == 0) else cash})

    equity = pd.DataFrame(equity_rows)
    if equity.empty:
        equity = pd.DataFrame(columns=["datetime", "equity"])
    peak = equity["equity"].cummax() if not equity.empty else pd.Series(dtype=float)
    drawdown = (equity["equity"] / peak - 1.0) * 100.0 if not equity.empty else pd.Series(dtype=float)
    max_dd = abs(float(drawdown.min())) if not drawdown.empty else 0.0

    wins = sum(t.net_pnl > 0 for t in trades)
    losses = sum(t.net_pnl < 0 for t in trades)
    gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    return BacktestResult(
        code=code,
        initial_cash=config.initial_cash,
        final_cash=cash,
        equity_return_pct=(cash / config.initial_cash - 1.0) * 100.0,
        max_drawdown_pct=max_dd,
        total_trades=len(trades),
        winning_trades=wins,
        losing_trades=losses,
        win_rate_pct=(wins / len(trades) * 100.0) if trades else 0.0,
        profit_factor=profit_factor,
        trades=trades,
        equity_curve=equity,
    )
