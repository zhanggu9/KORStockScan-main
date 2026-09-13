from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from src.backtest.pullback_scalping import pullback_scalping_strategy  # noqa: E402


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYYMMDD 형식이어야 합니다.") from exc


def load_code(data_dir: Path, code: str, start, end) -> tuple[pd.DataFrame, int]:
    frames = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            path = data_dir / code / f"{day:%Y%m%d}.csv"
            if path.exists():
                frames.append(pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str}))
        day = day.fromordinal(day.toordinal() + 1)
    if not frames:
        raise FileNotFoundError(f"No minute CSV files found for {code}: {start:%Y%m%d}~{end:%Y%m%d}")
    return pd.concat(frames, ignore_index=True), len(frames)


def main() -> int:
    p = argparse.ArgumentParser(description="VWAP+EMA 눌림목 스캘핑 백테스트")
    p.add_argument("--code", required=True)
    p.add_argument("--start", required=True, type=parse_date)
    p.add_argument("--end", required=True, type=parse_date)
    p.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "minute")
    p.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "backtest")
    p.add_argument("--initial-cash", type=float, default=10_000_000.0)
    p.add_argument("--fee-bps", type=float, default=15.0)
    p.add_argument("--slippage-bps", type=float, default=5.0)
    p.add_argument("--execution", choices=["next_open", "close"], default="next_open")
    p.add_argument("--fast-ema", type=int, default=9)
    p.add_argument("--slow-ema", type=int, default=20)
    p.add_argument("--trend-ema", type=int, default=60)
    p.add_argument("--rsi-period", type=int, default=14)
    p.add_argument("--rsi-min", type=float, default=55.0)
    p.add_argument("--rsi-max", type=float, default=75.0)
    p.add_argument("--volume-multiplier", type=float, default=1.3)
    p.add_argument("--pullback-lookback", type=int, default=8)
    p.add_argument("--touch-tolerance-pct", type=float, default=0.6)
    p.add_argument("--max-pullback-pct", type=float, default=1.5)
    p.add_argument("--breakout-lookback", type=int, default=2)
    p.add_argument("--min-body-pct", type=float, default=0.25)
    p.add_argument("--atr-period", type=int, default=14)
    p.add_argument("--stop-atr", type=float, default=0.8)
    p.add_argument("--target-atr", type=float, default=1.2)
    p.add_argument("--trailing-atr", type=float, default=0.8)
    p.add_argument("--max-hold-bars", type=int, default=15)
    args = p.parse_args()

    if args.end < args.start:
        p.error("--end는 --start보다 빠를 수 없습니다.")

    frame, files = load_code(args.data_dir, args.code, args.start, args.end)
    strategy = pullback_scalping_strategy(
        fast_ema=args.fast_ema,
        slow_ema=args.slow_ema,
        trend_ema=args.trend_ema,
        rsi_period=args.rsi_period,
        rsi_min=args.rsi_min,
        rsi_max=args.rsi_max,
        volume_multiplier=args.volume_multiplier,
        pullback_lookback=args.pullback_lookback,
        touch_tolerance_pct=args.touch_tolerance_pct,
        max_pullback_pct=args.max_pullback_pct,
        breakout_lookback=args.breakout_lookback,
        min_body_pct=args.min_body_pct,
    )
    config = BacktestConfig(
        initial_cash=args.initial_cash,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        execution=args.execution,
        atr_period=args.atr_period,
        stop_atr=args.stop_atr,
        target_atr=args.target_atr,
        trailing_atr=args.trailing_atr,
        max_hold_bars=args.max_hold_bars,
    )
    result = run_backtest(frame, strategy, config)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.code}_{args.start:%Y%m%d}_{args.end:%Y%m%d}_pullback_scalping"
    pd.DataFrame([{
        "code": result.code,
        "initial_cash": result.initial_cash,
        "final_cash": result.final_cash,
        "equity_return_pct": result.equity_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "win_rate_pct": result.win_rate_pct,
        "profit_factor": result.profit_factor,
    }]).to_csv(args.output_dir / f"{prefix}_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([t.__dict__ for t in result.trades]).to_csv(
        args.output_dir / f"{prefix}_trades.csv", index=False, encoding="utf-8-sig"
    )
    result.equity_curve.to_csv(args.output_dir / f"{prefix}_equity.csv", index=False)

    print(f"백테스트 완료: {result.code}")
    print("전략: pullback_scalping")
    print(f"기간: {args.start:%Y%m%d} ~ {args.end:%Y%m%d} | files={files}")
    print(f"최종자산: {result.final_cash:,.0f}")
    print(f"수익률: {result.equity_return_pct:.2f}%")
    print(f"MDD: {result.max_drawdown_pct:.2f}%")
    print(f"거래수: {result.total_trades}")
    print(f"승률: {result.win_rate_pct:.2f}%")
    print(f"Profit Factor: {result.profit_factor:.3f}")
    print(f"결과: {args.output_dir / f'{prefix}_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
