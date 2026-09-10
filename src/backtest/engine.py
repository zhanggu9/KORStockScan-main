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
    slippage_bps: float = 5.0
    execution: Literal["next_open", "close"] = "next_open"
    force_close_eod: bool = True


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
    net_pnl: float
    return_pct: float


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


def _buy_price(raw_price: float, slippage_bps: float) -> float:
    return raw_price * (1.0 + slippage_bps / 10_000.0)


def _sell_price(raw_price: float, slippage_bps: float) -> float:
    return raw_price * (1.0 - slippage_bps / 10_000.0)


def _fee(notional: float, fee_bps: float) -> float:
    return notional * fee_bps / 10_000.0


def run_backtest(
    frame: pd.DataFrame,
    strategy: SignalFn,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    config = config or BacktestConfig()
    bars = _prepare_frame(frame)
    code = str(bars["code"].iloc[0])

    cash = float(config.initial_cash)
    quantity = 0
    entry_time: pd.Timestamp | None = None
    entry_price = 0.0
    entry_fees = 0.0
    trades: list[Trade] = []
    equity_rows: list[dict] = []

    pending: Action = "HOLD"
    pending_index: int | None = None

    def execute(action: Action, index: int) -> None:
        nonlocal cash, quantity, entry_time, entry_price, entry_fees
        bar = bars.iloc[index]
        price = float(bar["close"] if config.execution == "close" else bar["open"])
        timestamp = pd.Timestamp(bar["datetime"])

        if action == "BUY" and quantity == 0:
            execution_price = _buy_price(price, config.slippage_bps)
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
            return

        if action == "SELL" and quantity > 0:
            execution_price = _sell_price(price, config.slippage_bps)
            notional = execution_price * quantity
            fees = _fee(notional, config.fee_bps)
            cash += notional - fees
            gross_pnl = (execution_price - entry_price) * quantity
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
                    net_pnl=net_pnl,
                    return_pct=return_pct,
                )
            )
            quantity = 0
            entry_time = None
            entry_price = 0.0
            entry_fees = 0.0

    def force_close(index: int) -> None:
        nonlocal pending, pending_index
        pending = "HOLD"
        pending_index = None
        if quantity > 0:
            execute("SELL", index)

    for i in range(len(bars)):
        current_day = bars.iloc[i]["datetime"].date()
        next_day = (
            bars.iloc[i + 1]["datetime"].date() if i + 1 < len(bars) else None
        )

        if pending_index is not None and pending_index == i:
            execute(pending, i)
            pending = "HOLD"
            pending_index = None

        history = bars.iloc[: i + 1]
        action = strategy(bars.iloc[i], history)
        if action not in {"BUY", "SELL", "HOLD"}:
            raise ValueError(f"Strategy returned invalid action: {action!r}")

        is_day_end = next_day != current_day
        if config.execution == "close":
            execute(action, i)
            if is_day_end and config.force_close_eod:
                force_close(i)
        elif not is_day_end:
            pending = action
            pending_index = i + 1
        elif config.force_close_eod:
            force_close(i)
        else:
            pending = "HOLD"
            pending_index = None

        mark = cash + quantity * float(bars.iloc[i]["close"])
        equity_rows.append(
            {"datetime": bars.iloc[i]["datetime"], "equity": mark}
        )
        if is_day_end and quantity == 0:
            equity_rows[-1]["equity"] = cash

    equity = pd.DataFrame(equity_rows)
    if equity.empty:
        equity = pd.DataFrame(columns=["datetime", "equity"])
    peak = equity["equity"].cummax() if not equity.empty else pd.Series(dtype=float)
    drawdown = (
        (equity["equity"] / peak - 1.0) * 100.0
        if not equity.empty
        else pd.Series(dtype=float)
    )
    max_dd = abs(float(drawdown.min())) if not drawdown.empty else 0.0

    wins = sum(t.net_pnl > 0 for t in trades)
    losses = sum(t.net_pnl < 0 for t in trades)
    gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))
    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
        if gross_profit > 0
        else 0.0
    )

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
