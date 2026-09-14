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
from src.backtest.scalping_proxy_v2 import (  # noqa: E402
    scalping_proxy_v2_indicators,
    scalping_proxy_v2_strategy,
)
from src.backtest.strategies import (  # noqa: E402
    _rsi,
    ema_cross_strategy,
    one_minute_scalping_proxy_strategy,
)
from src.backtest.trend_scalping import trend_scalping_strategy  # noqa: E402


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
    if args.strategy == "trend_scalping":
        return trend_scalping_strategy(
            fast_ema=args.trend_fast_ema,
            slow_ema=args.trend_slow_ema,
            trend_ema=args.trend_ema,
            slope_bars=args.slope_bars,
            rsi_period=args.trend_rsi_period,
            rsi_min=args.rsi_min,
            rsi_max=args.rsi_max,
            volume_multiplier=args.trend_volume_multiplier,
            pullback_pct=args.pullback_pct,
            sell_rsi=args.trend_sell_rsi,
        )
    if args.strategy == "scalping_proxy_v2":
        return scalping_proxy_v2_strategy(
            rsi_period=args.v2_rsi_period,
            rsi_min=args.v2_rsi_min,
            rsi_max=args.v2_rsi_max,
            volume_multiplier=args.v2_volume_multiplier,
            volume_window=args.v2_volume_window,
            fast_ema=args.v2_fast_ema,
            slow_ema=args.v2_slow_ema,
            breakout_lookback=args.v2_breakout_lookback,
            require_vwap_rising=args.v2_require_vwap_rising,
        )
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
    v2_rsi_period: int = 14,
    v2_volume_window: int = 3,
    v2_fast_ema: int = 9,
    v2_slow_ema: int = 20,
    v2_breakout_lookback: int = 2,
) -> pd.DataFrame:
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

    v2_indicators = None
    if strategy_name == "scalping_proxy_v2":
        v2_indicators = scalping_proxy_v2_indicators(
            bars,
            rsi_period=v2_rsi_period,
            volume_window=v2_volume_window,
            fast_ema=v2_fast_ema,
            slow_ema=v2_slow_ema,
            breakout_lookback=v2_breakout_lookback,
        )

    rows: list[dict] = []
    for trade_no, trade in enumerate(result.trades, start=1):
        entry_positions = bars.index[bars["datetime"] == pd.Timestamp(trade.entry_time)].tolist()
        if not entry_positions:
            continue
        entry_idx = entry_positions[0]
        exit_positions = bars.index[bars["datetime"] == pd.Timestamp(trade.exit_time)].tolist()
        exit_idx = exit_positions[0] if exit_positions else entry_idx
        if exit_idx < entry_idx:
            exit_idx = entry_idx

        trade_bars = bars.iloc[entry_idx : exit_idx + 1]
        max_high = float(trade_bars["high"].max())
        min_low = float(trade_bars["low"].min())
        mfe_pct = (max_high / trade.entry_price - 1.0) * 100.0
        mae_pct = (min_low / trade.entry_price - 1.0) * 100.0
        holding_minutes = (pd.Timestamp(trade.exit_time) - pd.Timestamp(trade.entry_time)).total_seconds() / 60.0

        signal_time = pd.NaT
        signal_close = float("nan")
        signal_rsi = float("nan")
        volume_ratio = float("nan")
        price_distance_pct = float("nan")
        v2_ema_fast = float("nan")
        v2_ema_slow = float("nan")
        v2_ema_spread_pct = float("nan")
        v2_ema_slow_slope_pct = float("nan")
        v2_vwap = float("nan")
        v2_vwap_distance_pct = float("nan")
        v2_vwap_slope_pct = float("nan")
        v2_breakout_distance_pct = float("nan")
        v2_signal_strength = float("nan")
        v2_trend_ok = None
        v2_vwap_ok = None
        v2_momentum_ok = None
        v2_volume_ok = None
        v2_breakout_ok = None

        if entry_idx > 0:
            signal_idx = entry_idx - 1
            signal_time = pd.Timestamp(bars.iloc[signal_idx]["datetime"])
            signal_close = float(bars.iloc[signal_idx]["close"])
            if strategy_name in {"scalping_proxy", "trend_scalping"}:
                history = bars.iloc[: signal_idx + 1]
                closes = history["close"]
                volumes = history["volume"]
                signal_rsi = _rsi(closes, rsi_period).iloc[-1]
                prior_closes = closes.iloc[-average_window - 1 : -1]
                prior_volumes = volumes.iloc[-average_window - 1 : -1]
                if len(prior_closes) == average_window and len(prior_volumes) == average_window:
                    avg_close = float(prior_closes.mean())
                    avg_volume = float(prior_volumes.mean())
                    if avg_close > 0:
                        price_distance_pct = (signal_close / avg_close - 1.0) * 100.0
                    if avg_volume > 0:
                        volume_ratio = float(bars.iloc[signal_idx]["volume"]) / avg_volume
            elif strategy_name == "scalping_proxy_v2" and v2_indicators is not None:
                diag = v2_indicators.iloc[signal_idx]
                signal_rsi = float(diag["v2_rsi"])
                volume_ratio = float(diag["v2_volume_ratio"])
                price_distance_pct = float(diag["v2_vwap_distance_pct"])
                v2_ema_fast = float(diag["v2_ema_fast"])
                v2_ema_slow = float(diag["v2_ema_slow"])
                v2_ema_spread_pct = float(diag["v2_ema_spread_pct"])
                v2_ema_slow_slope_pct = float(diag["v2_ema_slow_slope_pct"])
                v2_vwap = float(diag["v2_vwap"])
                v2_vwap_distance_pct = float(diag["v2_vwap_distance_pct"])
                v2_vwap_slope_pct = float(diag["v2_vwap_slope_pct"])
                v2_breakout_distance_pct = float(diag["v2_breakout_distance_pct"])
                v2_signal_strength = float(diag["v2_signal_strength"])
                v2_trend_ok = bool(diag["v2_trend_ok"])
                v2_vwap_ok = bool(diag["v2_vwap_ok"])
                v2_momentum_ok = bool(diag["v2_momentum_ok"])
                v2_volume_ok = bool(diag["v2_volume_ok"])
                v2_breakout_ok = bool(diag["v2_breakout_ok"])

        rows.append({
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
            "slippage_cost": trade.slippage_cost,
            "net_pnl": trade.net_pnl,
            "return_pct": trade.return_pct,
            "signal_close": signal_close,
            "signal_rsi": signal_rsi,
            "signal_volume_ratio": volume_ratio,
            "signal_price_distance_pct": price_distance_pct,
            "v2_ema_fast": v2_ema_fast,
            "v2_ema_slow": v2_ema_slow,
            "v2_ema_spread_pct": v2_ema_spread_pct,
            "v2_ema_slow_slope_pct": v2_ema_slow_slope_pct,
            "v2_vwap": v2_vwap,
            "v2_vwap_distance_pct": v2_vwap_distance_pct,
            "v2_vwap_slope_pct": v2_vwap_slope_pct,
            "v2_breakout_distance_pct": v2_breakout_distance_pct,
            "v2_signal_strength": v2_signal_strength,
            "v2_trend_ok": v2_trend_ok,
            "v2_vwap_ok": v2_vwap_ok,
            "v2_momentum_ok": v2_momentum_ok,
            "v2_volume_ok": v2_volume_ok,
            "v2_breakout_ok": v2_breakout_ok,
            "max_favorable_excursion_pct": mfe_pct,
            "max_adverse_excursion_pct": mae_pct,
            "result": "WIN" if trade.net_pnl > 0 else "LOSS" if trade.net_pnl < 0 else "FLAT",
        })
    return pd.DataFrame(rows)


def print_v2_diagnostics(trade_details: pd.DataFrame):
    if trade_details.empty:
        return

    df = trade_details.copy()
    print("\n===== scalping_proxy_v2 거래 진입조건 분석 =====")
    grouped = df.groupby("result", dropna=False)
    for label in ["WIN", "LOSS"]:
        if label not in grouped.groups:
            continue
        g = grouped.get_group(label)
        print(
            f"{label}: n={len(g)} | 평균 net={g['net_pnl'].mean():,.0f} | "
            f"평균 return={g['return_pct'].mean():.3f}% | "
            f"평균 MFE={g['max_favorable_excursion_pct'].mean():.3f}% | "
            f"평균 MAE={g['max_adverse_excursion_pct'].mean():.3f}% | "
            f"평균 RSI={g['signal_rsi'].mean():.2f} | "
            f"평균 vol={g['signal_volume_ratio'].mean():.2f}x | "
            f"평균 EMA spread={g['v2_ema_spread_pct'].mean():.3f}% | "
            f"평균 VWAP dist={g['v2_vwap_distance_pct'].mean():.3f}% | "
            f"평균 breakout={g['v2_breakout_distance_pct'].mean():.3f}%"
        )

    print("\n[진입조건 통과율]")
    for col, name in [
        ("v2_trend_ok", "EMA trend"),
        ("v2_vwap_ok", "VWAP"),
        ("v2_momentum_ok", "RSI"),
        ("v2_volume_ok", "Volume"),
        ("v2_breakout_ok", "Breakout"),
    ]:
        rates = df.groupby("result")[col].mean() * 100.0
        win = rates.get("WIN", float("nan"))
        loss = rates.get("LOSS", float("nan"))
        print(f"{name}: WIN {win:.1f}% | LOSS {loss:.1f}%")

    df["entry_hour"] = pd.to_datetime(df["signal_time"]).dt.hour
    hourly = (
        df.groupby("entry_hour")
        .agg(trades=("trade_no", "count"), win_rate=("net_pnl", lambda s: (s > 0).mean() * 100.0), avg_return=("return_pct", "mean"), avg_mae=("max_adverse_excursion_pct", "mean"), avg_mfe=("max_favorable_excursion_pct", "mean"))
        .sort_index()
    )
    print("\n[시간대별]")
    print(hourly.to_string(float_format=lambda x: f"{x:.3f}"))

    bad_entry = df[(df["max_favorable_excursion_pct"] < 0.5) & (df["return_pct"] < 0)]
    delayed_exit = df[(df["max_favorable_excursion_pct"] >= 1.0) & (df["return_pct"] < 0)]
    print("\n[진입/청산 분류]")
    print(f"진입 자체가 나빴다고 볼 수 있는 거래(MFE < 0.5%, LOSS): {len(bad_entry)}")
    print(f"진입 후 충분히 올랐지만 손실로 끝난 거래(MFE >= 1.0%, LOSS): {len(delayed_exit)}")


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
    pd.DataFrame([t.__dict__ for t in result.trades]).to_csv(trades_path, index=False, encoding="utf-8-sig")
    trade_details = build_trade_details(
        frame,
        result,
        strategy_name=args.strategy,
        rsi_period=args.rsi_period,
        average_window=args.average_window,
        v2_rsi_period=args.v2_rsi_period,
        v2_volume_window=args.v2_volume_window,
        v2_fast_ema=args.v2_fast_ema,
        v2_slow_ema=args.v2_slow_ema,
        v2_breakout_lookback=args.v2_breakout_lookback,
    )
    trade_details.to_csv(trade_details_path, index=False, encoding="utf-8-sig")
    result.equity_curve.to_csv(equity_path, index=False)
    return summary_path, trade_details_path, trade_details


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
    parser.add_argument("--strategy", choices=["scalping_proxy", "scalping_proxy_v2", "trend_scalping", "ema"], default="scalping_proxy")
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--rsi-buy", type=float, default=70.0)
    parser.add_argument("--rsi-sell", type=float, default=50.0)
    parser.add_argument("--volume-multiplier", type=float, default=2.5)
    parser.add_argument("--average-window", type=int, default=3)
    parser.add_argument("--price-distance-pct", type=float, default=2.0)
    parser.add_argument("--v2-rsi-period", type=int, default=14)
    parser.add_argument("--v2-rsi-min", type=float, default=70.0)
    parser.add_argument("--v2-rsi-max", type=float, default=85.0)
    parser.add_argument("--v2-volume-multiplier", type=float, default=2.0)
    parser.add_argument("--v2-volume-window", type=int, default=3)
    parser.add_argument("--v2-fast-ema", type=int, default=9)
    parser.add_argument("--v2-slow-ema", type=int, default=20)
    parser.add_argument("--v2-breakout-lookback", type=int, default=2)
    parser.add_argument("--v2-require-vwap-rising", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--trend-fast-ema", type=int, default=5)
    parser.add_argument("--trend-slow-ema", type=int, default=20)
    parser.add_argument("--trend-ema", type=int, default=60)
    parser.add_argument("--slope-bars", type=int, default=3)
    parser.add_argument("--trend-rsi-period", type=int, default=14)
    parser.add_argument("--rsi-min", type=float, default=55.0)
    parser.add_argument("--rsi-max", type=float, default=78.0)
    parser.add_argument("--trend-volume-multiplier", type=float, default=1.5)
    parser.add_argument("--pullback-pct", type=float, default=0.8)
    parser.add_argument("--trend-sell-rsi", type=float, default=45.0)
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
            summary_path, trade_details_path, trade_details = save_single_outputs(args, frame, result, file_count, args.code)
        except Exception as exc:
            print(f"백테스트 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        print_result(args, result, file_count, args.code)
        if args.diagnostics and args.strategy == "scalping_proxy":
            print_diagnostics(args, frame)
        if args.strategy == "scalping_proxy_v2":
            print_v2_diagnostics(trade_details)
        print(f"거래 상세: {trade_details_path}")
        print(f"결과: {summary_path}")
        return 0

    try:
        universe = load_universe(args.universe_file, args.max_stocks)
    except Exception as exc:
        print(f"유니버스 로드 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(f"일괄 백테스트 시작: {args.start:%Y%m%d} ~ {args.end:%Y%m%d} | stocks={len(universe)}")
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
        print(f"    ↳ return={result.equity_return_pct:.2f}% | MDD={result.max_drawdown_pct:.2f}% | trades={result.total_trades} | win={result.win_rate_pct:.2f}% | PF={result.profit_factor:.3f}")

    if not rows:
        print("일괄 백테스트 결과가 없습니다.", file=sys.stderr)
        return 2

    result_frame = pd.DataFrame(rows)
    result_frame = result_frame[["code", "name", "index", "files", "initial_cash", "final_cash", "equity_return_pct", "max_drawdown_pct", "total_trades", "winning_trades", "losing_trades", "win_rate_pct", "profit_factor"]].sort_values("equity_return_pct", ascending=False)
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
    print(result_frame[["code", "name", "index", "equity_return_pct", "max_drawdown_pct", "total_trades", "win_rate_pct", "profit_factor"]].head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
