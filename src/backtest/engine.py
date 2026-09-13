from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[pd.Series, pd.DataFrame], Action]


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
    if any(v is not None and v <= 0 for v in [config.atr_period, config.stop_atr, config.target_atr, config.trailing_atr, config.max_hold_bars]):
        raise ValueError("risk parameters must be > 0 when provided")

    bars = _prepare_frame(frame)
    atr_series = _atr(bars, config.atr_period) if config.atr_period else pd.Series(float("nan"), index=bars.index)
    code = str(bars["code"].iloc[0])

    cash = float(config.initial_cash)
    quantity = 0
    entry_time: pd.Timestamp | None = None
    entry_price = 0.0
    entry_fees = 0.0
    entry_slippage_cost = 0.0
    entry_atr: float | None = None
    highest_high = 0.0
    hold_bars = 0
    trades: list[Trade] = []
    equity_rows: list[dict] = []

    pending: Action = "HOLD"
    pending_index: int | None = None

    def execute(action: Action, index: int, reason: str = "SIGNAL") -> None:
        nonlocal cash, quantity, entry_time, entry_price, entry_fees, entry_slippage_cost
        nonlocal entry_atr, highest_high, hold_bars
        bar = bars.iloc[index]
        raw_price = float(bar["close"] if config.execution == "close" else bar["open"])
        timestamp = pd.Timestamp(bar["datetime"])

        if action == "BUY" and quantity == 0:
            execution_price = _apply_buy_slippage(raw_price, config.entry_slippage_bps)
            max_qty = int(cash / (execution_price * (1.0 + config.fee_bps / 10_000.0)))
            if max_qty <= 0:
                return
            notional = execution_price * max_qty
            fees = _fee(notional, config.fee_bps)
            cash -= notional + fees
            quantity = max_qty
            entry_time = timestamp
            entry_price = execution_price
            entry_fees = fees
            entry_slippage_cost = abs(execution_price - raw_price) * max_qty
            atr_value = float(atr_series.iloc[index]) if not pd.isna(atr_series.iloc[index]) else None
            entry_atr = atr_value
            highest_high = float(bar["high"])
            hold_bars = 0
            return

        if action == "SELL" and quantity > 0:
            execution_price = _apply_sell_slippage(raw_price, exit_slippage_bps)
            notional = execution_price * quantity
            fees = _fee(notional, config.fee_bps)
            cash += notional - fees
            gross_pnl = (execution_price - entry_price) * quantity
            exit_slippage_cost = abs(raw_price - execution_price) * quantity
            total_slippage_cost = entry_slippage_cost + exit_slippage_cost
            total_fees = entry_fees + fees
            net_pnl = gross_pnl - total_fees
            invested = entry_price * quantity + entry_fees
            return_pct = (net_pnl / invested * 100.0) if invested else 0.0
            trades.append(
                Trade(
                    code=code,
                    entry_time=entry_time or timestamp,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=execution_price,
                    quantity=quantity,
                    gross_pnl=gross_pnl,
                    fees=total_fees,
                    slippage_cost=total_slippage_cost,
                    net_pnl=net_pnl,
                    return_pct=return_pct,
                    exit_reason=reason,
                )
            )
            quantity = 0
            entry_time = None
            entry_price = 0.0
            entry_fees = 0.0
            entry_slippage_cost = 0.0
            entry_atr = None
            highest_high = 0.0
            hold_bars = 0

    def risk_exit(index: int) -> bool:
        nonlocal highest_high, hold_bars
        if quantity <= 0:
            return False
        bar = bars.iloc[index]
        highest_high = max(highest_high, float(bar["high"]))
        hold_bars += 1
        atr = entry_atr
        stop_price = None
        target_price = None
        trail_price = None
        if atr is not None:
            if config.stop_atr is not None:
                stop_price = entry_price - atr * config.stop_atr
            if config.target_atr is not None:
                target_price = entry_price + atr * config.target_atr
            if config.trailing_atr is not None:
                trail_price = highest_high - atr * config.trailing_atr

        low = float(bar["low"])
        high = float(bar["high"])
        close = float(bar["close"])
        # Conservative intrabar rule: when stop and target are both touched,
        # assume the stop was hit first because OHLC does not reveal tick order.
        if stop_price is not None and low <= stop_price:
            execute("SELL", index, "ATR_STOP")
            return True
        if target_price is not None and high >= target_price:
            execute("SELL", index, "ATR_TARGET")
            return True
        if trail_price is not None and low <= trail_price and highest_high > entry_price:
            execute("SELL", index, "ATR_TRAILING")
            return True
        if config.max_hold_bars is not None and hold_bars >= config.max_hold_bars:
            execute("SELL", index, "TIME_STOP")
            return True
        return False

    for i in range(len(bars)):
        current_day = bars.iloc[i]["datetime"].date()
        next_day = bars.iloc[i + 1]["datetime"].date() if i + 1 < len(bars) else None

        if pending_index is not None and pending_index == i:
            execute(pending, i)
            pending = "HOLD"
            pending_index = None

        risk_triggered = risk_exit(i)
        history = bars.iloc[: i + 1]
        action = "HOLD" if risk_triggered else strategy(bars.iloc[i], history)
        if action not in {"BUY", "SELL", "HOLD"}:
            raise ValueError(f"Strategy returned invalid action: {action!r}")

        is_day_end = next_day != current_day
        if config.execution == "close":
            execute(action, i)
            if is_day_end and config.force_close_eod:
                if quantity > 0:
                    execute("SELL", i, "EOD")
        elif not is_day_end:
            pending = action
            pending_index = i + 1
        elif config.force_close_eod:
            if quantity > 0:
                execute("SELL", i, "EOD")
            pending = "HOLD"
            pending_index = None

        mark = cash + quantity * float(bars.iloc[i]["close"])
        equity_rows.append({"datetime": bars.iloc[i]["datetime"], "equity": mark})
        if is_day_end and quantity == 0:
            equity_rows[-1]["equity"] = cash

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
