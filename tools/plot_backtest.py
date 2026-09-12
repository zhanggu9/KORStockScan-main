from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KORStockScan 백테스트 결과 시각화")
    parser.add_argument("--equity", type=Path, required=True, help="*_equity.csv 경로")
    parser.add_argument("--trades", type=Path, required=True, help="*_trade_details.csv 경로")
    parser.add_argument("--output-dir", type=Path, help="PNG 출력 폴더. 기본값은 입력 파일 폴더")
    return parser.parse_args()


def load_equity(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"datetime", "equity"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"equity CSV 필수 컬럼 누락: {sorted(missing)}")
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame.dropna(subset=["datetime", "equity"]).sort_values("datetime").drop_duplicates("datetime")
    if frame.empty:
        raise ValueError("유효한 equity 데이터가 없습니다.")
    frame["drawdown_pct"] = (frame["equity"] / frame["equity"].cummax() - 1.0) * 100.0
    return frame


def load_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        return frame
    for col in ["signal_time", "entry_time", "exit_time"]:
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
    for col in [
        "entry_price", "exit_price", "quantity", "holding_minutes", "gross_pnl",
        "fees", "slippage_cost", "net_pnl", "return_pct", "signal_rsi",
        "signal_volume_ratio", "signal_price_distance_pct",
        "max_favorable_excursion_pct", "max_adverse_excursion_pct",
    ]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def save_figure(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


def main() -> int:
    args = parse_args()
    out_dir = args.output_dir or args.equity.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    equity = load_equity(args.equity)
    trades = load_trades(args.trades)
    stem = args.equity.stem.replace("_equity", "")

    plt.figure(figsize=(12, 5))
    plt.plot(equity["datetime"], equity["equity"])
    plt.title("Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Equity")
    save_figure(out_dir / f"{stem}_equity.png")

    plt.figure(figsize=(12, 4))
    plt.plot(equity["datetime"], equity["drawdown_pct"])
    plt.title("Drawdown")
    plt.xlabel("Time")
    plt.ylabel("Drawdown (%)")
    save_figure(out_dir / f"{stem}_drawdown.png")

    if not trades.empty and "net_pnl" in trades.columns:
        plt.figure(figsize=(10, 5))
        plt.hist(trades["net_pnl"].dropna(), bins=40)
        plt.title("Trade Net PnL Distribution")
        plt.xlabel("Net PnL")
        plt.ylabel("Trades")
        save_figure(out_dir / f"{stem}_pnl_distribution.png")

        cumulative = trades["net_pnl"].fillna(0).cumsum()
        plt.figure(figsize=(12, 4))
        plt.plot(range(1, len(cumulative) + 1), cumulative)
        plt.title("Cumulative Trade PnL")
        plt.xlabel("Trade Number")
        plt.ylabel("Cumulative Net PnL")
        save_figure(out_dir / f"{stem}_trade_pnl.png")

    if not trades.empty and {"entry_time", "net_pnl"}.issubset(trades.columns):
        by_hour = trades.dropna(subset=["entry_time"]).assign(hour=lambda x: x["entry_time"].dt.hour).groupby("hour")["net_pnl"].agg(["count", "sum", "mean"])
        if not by_hour.empty:
            plt.figure(figsize=(10, 5))
            plt.bar(by_hour.index.astype(str), by_hour["sum"])
            plt.title("PnL by Entry Hour")
            plt.xlabel("Entry Hour")
            plt.ylabel("Net PnL")
            save_figure(out_dir / f"{stem}_pnl_by_hour.png")

    print("시각화 완료")
    print(f"출력 폴더: {out_dir}")
    print(f"Equity: {out_dir / f'{stem}_equity.png'}")
    print(f"Drawdown: {out_dir / f'{stem}_drawdown.png'}")
    if not trades.empty:
        print(f"PnL 분포: {out_dir / f'{stem}_pnl_distribution.png'}")
        print(f"거래 누적손익: {out_dir / f'{stem}_trade_pnl.png'}")
        if {"entry_time", "net_pnl"}.issubset(trades.columns):
            print(f"시간대별 PnL: {out_dir / f'{stem}_pnl_by_hour.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
