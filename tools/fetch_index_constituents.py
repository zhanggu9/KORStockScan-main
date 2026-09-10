from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from pykrx import stock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "universe" / "current_constituents.csv"

INDEXES = {
    "KOSPI200": ("KOSPI", "1028"),
    "KOSDAQ150": ("KOSDAQ", "2203"),
}


def parse_date(value: str) -> str:
    try:
        date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYYMMDD 형식이어야 합니다.") from exc
    return value


def _extract_tickers(value) -> list[str]:
    """Handle both the documented list return and DataFrame return seen in some pykrx builds."""
    if value is None:
        return []

    if isinstance(value, pd.DataFrame):
        if value.empty:
            return []

        # Current pykrx normally returns a list, but some builds/wrappers can
        # expose the underlying KRX result as a DataFrame. Prefer the standard
        # ISU_SRT_CD column and fall back to the DataFrame index.
        for column in ("ISU_SRT_CD", "티커", "ticker", "code"):
            if column in value.columns:
                values = value[column].tolist()
                break
        else:
            values = value.index.tolist()
    else:
        try:
            values = list(value)
        except TypeError:
            return []

    result = []
    for ticker in values:
        if pd.isna(ticker):
            continue
        ticker = str(ticker).strip()
        if ticker:
            result.append(ticker.zfill(6))
    return result


def fetch_index(index_name: str, as_of: str) -> pd.DataFrame:
    market, index_code = INDEXES[index_name]

    try:
        raw = stock.get_index_portfolio_deposit_file(index_code, as_of)
    except Exception as exc:
        raise RuntimeError(
            f"{index_name} 구성종목 API 조회 실패: {type(exc).__name__}: {exc}"
        ) from exc

    tickers = _extract_tickers(raw)
    if not tickers:
        raw_type = type(raw).__name__
        raw_shape = getattr(raw, "shape", None)
        raise RuntimeError(
            f"{index_name} 구성종목을 가져오지 못했습니다. "
            f"조회일={as_of}, index={index_code}, "
            f"응답형식={raw_type}, shape={raw_shape}. "
            "pykrx/한국거래소 응답이 비어 있거나 차단되었을 가능성이 있습니다."
        )

    rows = []
    for ticker in tickers:
        try:
            name = stock.get_market_ticker_name(ticker)
        except Exception:
            name = ""
        rows.append(
            {
                "index": index_name,
                "market": market,
                "code": ticker,
                "name": name,
                "as_of": as_of,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="현재(또는 지정 기준일) KOSPI200 + KOSDAQ150 구성종목 자동 조회"
    )
    parser.add_argument(
        "--date",
        type=parse_date,
        default=None,
        help="기준일 YYYYMMDD. 생략하면 오늘 날짜를 사용",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="통합 구성종목 CSV 저장 경로",
    )
    args = parser.parse_args()

    as_of = args.date or date.today().strftime("%Y%m%d")

    frames = []
    for index_name in INDEXES:
        print(f"{index_name} 구성종목 조회: {as_of}")
        frame = fetch_index(index_name, as_of)
        print(f"  -> {len(frame)}개")
        frames.append(frame)

    result = pd.concat(frames, ignore_index=True)
    result = result.drop_duplicates(subset=["index", "code"]).sort_values(
        ["index", "code"]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")

    all_path = args.output.with_name("all_current.csv")
    all_result = (
        result.sort_values(["code", "index"])
        .groupby("code", as_index=False)
        .agg(
            name=("name", "first"),
            market=("market", "first"),
            indexes=("index", lambda s: ",".join(s)),
            as_of=("as_of", "first"),
        )
    )
    all_result.to_csv(all_path, index=False, encoding="utf-8-sig")

    print(f"저장: {args.output}")
    print(f"전체 중복제거 유니버스: {len(all_result)}개 -> {all_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
