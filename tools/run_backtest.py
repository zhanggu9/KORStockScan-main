from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from src.backtest.strategies import (  # noqa: E402
    _rsi,
    ema_cross_strategy,
    one_minute_scalping_proxy_strategy,
)


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
    frames = [
        pd.read_csv(path, encoding="utf-8-sig", dtype={"code": str})
        for path in paths
    ]
    return pd.concat(frames, ignore_index=True), len(paths)


def load_universe(universe_path: Path, max_stocks: int | None = None) -> pd.DataFrame:
    if not universe_path.exists():
        raise FileNotFoundError(f"유니버스 파일이 없습니다: {universe_path}")
    frame = pd.read_csv(universe_path, encoding="utf-8-sig", dtype={"code": str})
    required = {"code", "name", "index"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"유니버스 필수 컬럼이 없습니다: {sorted(missing)}")
    frame["code"] = frame["code"].str.extract(r"(\d{6})", expand=False)
    frame = frame.dropna(subset=["code"]).drop_duplicates("code").sort_values("code")
    if max_stocks is not None:
        frame = frame.head(max_stocks)
    return frame.reset_index(drop=True)


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


def build_strategy(args):
    if args.strategy == "ema":
        return ema_cross_strategy(args.fast, args.slow)
    return one_minute_scalping_proxy_strategy(
        rsi_period=args.rsi_period,
        rsi_buy=args.rsi_buy,
        rsi_sell=args.rsi_sell,
        volume_multiplier=args.volume_multiplier,
        average_window=args.average_window,
        price_distance_pct=args.price_distance_pct,
    )


def build_trade_details(
    frame: pd.DataFrame,
    result,
    *,
    strategy_name: str,
    rsi_period: int,
    average_window: int,
) -> pd.DataFrame:
    """Create one row per trade with signal-time and post-entry statistics."""
    if not result.trades:
        return pd.DataFrame()

    bars = frame.copy()
    bars["datetime"] = pd.to_datetime(bars["datetime"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        bars[col] = pd.to_numeric(bars[col], errors="coerce")
    bars = (
        bars.dropna(subset=["datetime", "open", "high", "low", "close", "volume"])
        .sort_values("datetime")
        .drop_duplicates("datetime")
        .reset_index(drop=True)
    )

    rows: list[dict] = []
    for trade_no, trade in enumerate(result.trades, start=1):
        entry_positions = bars.index[
            bars["datetime"] == pd.Timestamp(trade.entry_time)
        ].tolist()
        if not entry_positions:
            continue
        entry_idx = entry_positions[0]

        exit_positions = bars.index[
            bars["datetime"] == pd.Timestamp(trade.exit_time)
        ].tolist()
        exit_idx = exit_positions[0] if exit_positions else entry_idx
        if exit_idx < entry_idx:
            exit_idx = entry_idx

        trade_bars = bars.iloc[entry_idx : exit_idx + 1]
        max_high = float(trade_bars["high"].max())
        min_low = float(trade_bars["low"].min())
        mfe_pct = (max_high / trade.entry_price - 1.0) * 100.0
        mae_pct = (min_low / trade.entry_price - 1.0) * 100.0
        holding_minutes = (
            pd.Timestamp(trade.exit_time) - pd.Timestamp(trade.entry_time)
        ).total_seconds() / 60.0

        signal_time = pd.NaT
        signal_close = float("nan")
        signal_rsi = float("nan")
        volume_ratio = float("nan")
        price_distance_pct = float("nan")

        if entry_idx > 0:
            signal_idx = entry_idx - 1
            signal_time = pd.Timestamp(bars.iloc[signal_idx]["datetime"])
            signal_close = float(bars.iloc[signal_idx]["close"])

            if strategy_name == "scalping_proxy":
                history = bars.iloc[: signal_idx + 1]
                closes = history["close"]
                volumes = history["volume"]
                signal_rsi = _rsi(closes, rsi_period)
                prior_closes = closes.iloc[-average_window - 1 : -1]
                prior_volumes = volumes.iloc[-average_window - 1 : -1]
                if len(prior_closes) == average_window and len(prior_volumes) == average_window:
                    avg_close = float(prior_closes.mean())
                    avg_volume = float(prior_volumes.mean())
                    if avg_close > 0:
                        price_distance_pct = (signal_close / avg_close - 1.0) * 100.0
                    if avg_volume > 0:
                        volume_ratio = float(bars.iloc[signal_idx]["volume"]) / avg_volume

        rows.append(
            {
                "trade_no": trade_no,
                "code": trade.code,
                "signal_time": signal_time,
                "entry_time": trade.entry_time,
                "entry_price": trade.entry_price,
                "exit_time": trade.exit_time,
                "exit_price": trade.exit_price,
                "quantity": trade.quantity,
                "holding_minutes": holding_minutes,
                "gross_pnl": trade.gross_pnl,
                "fees": trade.fees,
                "net_pnl": trade.net_pnl,
                "return_pct": trade.return_pct,
                "signal_close": signal_close,
                "signal_rsi": signal_rsi,
                "signal_volume_ratio": volume_ratio,
                "signal_price_distance_pct": price_distance_pct,
                "max_favorable_excursion_pct": mfe_pct,
                "max_adverse_excursion_pct": mae_pct,
                "result": "WIN" if trade.net_pnl > 0 else "LOSS" if trade.net_pnl < 0 else "FLAT",
            }
        )

    return pd.DataFrame(rows)


def run_one(args, code: str):
    frame, file_count = load_code(args.data_dir, code, args.start, args.end)
    strategy = build_strategy(args)
    config = BacktestConfig(
        initial_cash=args.initial_cash,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        execution=args.execution,
    )
    result = run_backtest(frame, strategy, config)
    return frame, file_count, result


def save_single_outputs(args, frame, result, file_count, code: str):
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{code}_{args.start:%Y%m%d}_{args.end:%Y%m%d}_{args.strategy}"
    summary_path = args.output_dir / f"{prefix}_summary.csv"
    trades_path = args.output_dir / f"{prefix}_trades.csv"
    trade_details_path = args.output_dir / f"{prefix}_trade_details.csv"
    equity_path = args.output_dir / f"{prefix}_equity.csv"

    pd.DataFrame([result_row(result)]).to_csv(summary_path, index=False, encoding="utf-8-sig")
    pd.DataFrame([t.__dict__ for t in result.trades]).to_csv(
        trades_path, index=False, encoding="utf-8-sig"
    )
    trade_details = build_trade_details(
        frame,
        result,
        strategy_name=args.strategy,
        rsi_period=args.rsi_period,
        average_window=args.average_window,
    )
    trade_details.to_csv(trade_details_path, index=False, encoding="utf-8-sig")
    result.equity_curve.to_csv(equity_path, index=False)

    return summary_path, trade_details_path


def print_result(args, result, file_count, code: str):
    print(f"백테스트 완료: {result.code}")
    print(f"전략: {args.strategy}")
    print(f"기간: {args.start:%Y%m%d} ~ {args.end:%Y%m%d} | files={file_count}")
    print(f"최종자산: {result.final_cash:,.0f}")
    print(f"수익률: {result.equity_return_pct:.2f}%")
    print(f"MDD: {result.max_drawdown_pct:.2f}%")
    print(f"거래수: {result.total_trades}")
    print(f"승률: {result.win_rate_pct:.2f}%")
    print(f"Profit Factor: {result.profit_factor:.3f}")


def print_diagnostics(args, frame):
    from src.backtest.strategies import diagnose_one_minute_scalping_proxy

    diagnostics = diagnose_one_minute_scalping_proxy(
        frame,
        rsi_period=args.rsi_period,
        rsi_buy=args.rsi_buy,
        rsi_sell=args.rsi_sell,
        volume_multiplier=args.volume_multiplier,
        average_window=args.average_window,
        price_distance_pct=args.price_distance_pct,
    )
    print("\n[조건 진단]")
    print(f"유효 봉 수: {diagnostics['valid_bars']:,}")
    print(f"RSI >= {args.rsi_buy:g}: {diagnostics['rsi_buy_pass']:,}")
    print(f"거래량 >= 평균×{args.volume_multiplier:g}: {diagnostics['volume_pass']:,}")
    print(f"종가 >= 평균 대비 {args.price_distance_pct:g}%: {diagnostics['price_pass']:,}")
    print(f"세 조건 동시 충족: {diagnostics['all_buy_pass']:,}")
    print(f"RSI <= {args.rsi_sell:g}: {diagnostics['rsi_sell_pass']:,}")
    print(f"최대 RSI: {diagnostics['max_rsi']:.2f}")
    print(f"최대 거래량 배수: {diagnostics['max_volume_ratio']:.2f}x")
    print(f"최대 평균종가 대비 상승률: {diagnostics['max_price_distance_pct']:.2f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="KORStockScan 1분봉 CSV 백테스트 실행기")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--code", help="단일 종목코드 예: 005930")
    target.add_argument("--universe", action="store_true", help="data/universe/all.csv 전체를 일괄 백테스트")
    parser.add_argument("--max-stocks", type=int, help="--universe에서 앞에서부터 최대 N종목만 실행")
    parser.add_argument("--universe-file", type=Path, default=PROJECT_ROOT / "data" / "universe" / "all.csv")
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", required=True, type=parse_date)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "minute")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "backtest")
    parser.add_argument("--initial-cash", type=float, default=10_000_000.0)
    parser.add_argument("--fee-bps", type=float, default=15.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--strategy", choices=["scalping_proxy", "ema"], default="scalping_proxy")
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--rsi-buy", type=float, default=70.0)
    parser.add_argument("--rsi-sell", type=float, default=50.0)
    parser.add_argument("--volume-multiplier", type=float, default=2.5)
    parser.add_argument("--average-window", type=int, default=3)
    parser.add_argument("--price-distance-pct", type=float, default=2.0)
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--execution", choices=["next_open", "close"], default="next_open")
    args = parser.parse_args()

    if args.end < args.start:
        parser.error("--end는 --start보다 빠를 수 없습니다.")
    if args.initial_cash <= 0:
        parser.error("--initial-cash는 0보다 커야 합니다.")
    if args.fee_bps < 0 or args.slippage_bps < 0:
        parser.error("비용은 0 이상이어야 합니다.")
    if args.max_stocks is not None and args.max_stocks <= 0:
        parser.error("--max-stocks는 1 이상이어야 합니다.")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if not args.universe:
        try:
            frame, file_count, result = run_one(args, args.code)
            summary_path, trade_details_path = save_single_outputs(args, frame, result, file_count, args.code)
        except Exception as exc:
            print(f"백테스트 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

        print_result(args, result, file_count, args.code)
        if args.diagnostics and args.strategy == "scalping_proxy":
            print_diagnostics(args, frame)
        print(f"거래 상세: {trade_details_path}")
        print(f"결과: {summary_path}")
        return 0

    try:
        universe = load_universe(args.universe_file, args.max_stocks)
    except Exception as exc:
        print(f"유니버스 로드 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(
        f"일괄 백테스트 시작: {args.start:%Y%m%d} ~ {args.end:%Y%m%d} | "
        f"stocks={len(universe)}"
    )
    print(f"유니버스: {args.universe_file}")

    rows: list[dict] = []
    skipped = 0
    failed = 0

    for n, item in enumerate(universe.itertuples(index=False), start=1):
        code = str(item.code).zfill(6)
        name = str(item.name)
        index_name = str(item.index)
        print(f"[{n}/{len(universe)}] {code} {name} | {index_name}")
        try:
            frame, file_count, result = run_one(args, code)
        except FileNotFoundError as exc:
            print(f"    ↳ SKIP: {exc}")
            skipped += 1
            continue
        except Exception as exc:
            print(f"    ↳ FAIL: {type(exc).__name__}: {exc}")
            failed += 1
            continue

        row = result_row(result)
        row.update({"name": name, "index": index_name, "files": file_count})
        rows.append(row)
        print(
            f"    ↳ return={result.equity_return_pct:.2f}% | "
            f"MDD={result.max_drawdown_pct:.2f}% | trades={result.total_trades} | "
            f"win={result.win_rate_pct:.2f}% | PF={result.profit_factor:.3f}"
        )

    if not rows:
        print("일괄 백테스트 결과가 없습니다.", file=sys.stderr)
        return 2

    result_frame = pd.DataFrame(rows)
    result_frame = result_frame[
        [
            "code", "name", "index", "files", "initial_cash", "final_cash",
            "equity_return_pct", "max_drawdown_pct", "total_trades",
            "winning_trades", "losing_trades", "win_rate_pct", "profit_factor",
        ]
    ].sort_values("equity_return_pct", ascending=False)

    prefix = f"universe_{args.start:%Y%m%d}_{args.end:%Y%m%d}_{args.strategy}"
    output_path = args.output_dir / f"{prefix}_summary.csv"
    result_frame.to_csv(output_path, index=False, encoding="utf-8-sig")

    profitable = int((result_frame["equity_return_pct"] > 0).sum())
    pf_positive = int((result_frame["profit_factor"] > 1).sum())
    print("\n===== 일괄 백테스트 완료 =====")
    print(f"실행: {len(rows)} | skip={skipped} | fail={failed}")
    print(f"수익 종목: {profitable}/{len(rows)}")
    print(f"Profit Factor > 1: {pf_positive}/{len(rows)}")
    print(f"평균 수익률: {result_frame['equity_return_pct'].mean():.2f}%")
    print(f"중앙값 수익률: {result_frame['equity_return_pct'].median():.2f}%")
    print(f"결과: {output_path}")
    print("\n[수익률 상위 10]")
    print(
        result_frame[["code", "name", "index", "equity_return_pct", "max_drawdown_pct", "total_trades", "win_rate_pct", "profit_factor"]]
        .head(10)
        .to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
