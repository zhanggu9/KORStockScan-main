from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from src.backtest.strategies import ema_cross_strategy  # noqa: E402


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYYMMDD 형식이어야 합니다.") from exc


def trading_files(data_dir: Path, code: str, start, end):
    day = start
    while day <= end:
        if day.weekday() < 5:
            path = data_dir / code / f"{day:%Y%m%d}.csv"
            if path.exists():
                yield path
        day = day.fromordinal(day.toordinal() + 1)


def load_code(data_dir: Path, code: str, start, end) -> tuple[pd.DataFrame, int]:
    paths = list(trading_files(data_dir, code, start, end))
    if not paths:
        raise FileNotFoundError(
            f"No minute CSV files found for {code}: {start:%Y%m%d}~{end:%Y%m%d}"
        )
    frames = [pd.read_csv(path, encoding="utf-8-sig") for path in paths]
    return pd.concat(frames, ignore_index=True), len(paths)


def result_row(result):
    return {
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KORStockScan 1분봉 CSV 백테스트 실행기")
    parser.add_argument("--code", required=True, help="종목코드 예: 005930")
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", required=True, type=parse_date)
    parser.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data" / "minute"
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "backtest")
    parser.add_argument("--initial-cash", type=float, default=10_000_000.0)
    parser.add_argument("--fee-bps", type=float, default=15.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument(
        "--execution",
        choices=["next_open", "close"],
        default="next_open",
        help="신호 다음 봉 시가(기본) 또는 같은 봉 종가에 체결",
    )
    args = parser.parse_args()

    if args.end < args.start:
        parser.error("--end는 --start보다 빠를 수 없습니다.")
    if args.initial_cash <= 0:
        parser.error("--initial-cash는 0보다 커야 합니다.")
    if args.fee_bps < 0 or args.slippage_bps < 0:
        parser.error("비용은 0 이상이어야 합니다.")

    try:
        frame, file_count = load_code(args.data_dir, args.code, args.start, args.end)
        strategy = ema_cross_strategy(args.fast, args.slow)
        config = BacktestConfig(
            initial_cash=args.initial_cash,
            fee_bps=args.fee_bps,
            slippage_bps=args.slippage_bps,
            execution=args.execution,
        )
        result = run_backtest(frame, strategy, config)
    except Exception as exc:
        print(f"백테스트 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / f"{args.code}_{args.start:%Y%m%d}_{args.end:%Y%m%d}_summary.csv"
    trades_path = args.output_dir / f"{args.code}_{args.start:%Y%m%d}_{args.end:%Y%m%d}_trades.csv"
    equity_path = args.output_dir / f"{args.code}_{args.start:%Y%m%d}_{args.end:%Y%m%d}_equity.csv"

    pd.DataFrame([result_row(result)]).to_csv(
        summary_path, index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([t.__dict__ for t in result.trades]).to_csv(
        trades_path, index=False, encoding="utf-8-sig"
    )
    result.equity_curve.to_csv(equity_path, index=False, encoding="utf-8-sig")

    print(f"백테스트 완료: {result.code}")
    print(f"기간: {args.start:%Y%m%d} ~ {args.end:%Y%m%d} | files={file_count}")
    print(f"최종자산: {result.final_cash:,.0f}")
    print(f"수익률: {result.equity_return_pct:.2f}%")
    print(f"MDD: {result.max_drawdown_pct:.2f}%")
    print(f"거래수: {result.total_trades}")
    print(f"승률: {result.win_rate_pct:.2f}%")
    print(f"Profit Factor: {result.profit_factor:.3f}")
    print(f"결과: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
