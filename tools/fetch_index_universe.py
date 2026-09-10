from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from pykrx import stock
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pykrx가 설치되어 있지 않습니다. 먼저 `pip install pykrx`를 실행하세요."
    ) from exc

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "universe"

# KRX index codes used by pykrx.
INDEXES = {
    "kospi200": {"index_code": "1028", "market": "KOSPI", "name": "KOSPI 200"},
    "kosdaq150": {"index_code": "2203", "market": "KOSDAQ", "name": "KOSDAQ 150"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="현재 KOSPI 200 / KOSDAQ 150 구성종목을 KRX에서 가져옵니다."
    )
    parser.add_argument(
        "--index",
        choices=["kospi200", "kosdaq150", "all"],
        default="all",
        help="가져올 지수. 기본값: all",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="구성종목 CSV 저장 디렉터리",
    )
    return parser.parse_args()


def fetch_constituents(index_key: str) -> list[dict[str, str]]:
    info = INDEXES[index_key]
    tickers = stock.get_index_portfolio_deposit_file(info["index_code"])
    if not tickers:
        raise RuntimeError(
            f"{info['name']} 구성종목을 가져오지 못했습니다. KRX 응답이 비어 있습니다."
        )

    # One market-level request is preferable to calling get_market_ticker_name()
    # once per constituent.
    ticker_names = stock.get_market_ticker_and_name(market=info["market"])

    rows: list[dict[str, str]] = []
    for ticker in tickers:
        code = str(ticker).zfill(6)
        name = str(ticker_names.get(code, "")).strip()
        rows.append(
            {
                "code": code,
                "name": name,
                "index": info["name"],
                "index_code": info["index_code"],
            }
        )

    rows.sort(key=lambda row: row["code"])
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["code", "name", "index", "index_code"],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_combined(rows: list[dict[str, str]], path: Path) -> None:
    # A stock can theoretically appear in both universes. Keep one row per code
    # while retaining both index memberships in the `index` column.
    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        code = row["code"]
        if code not in grouped:
            grouped[code] = dict(row)
        else:
            existing = grouped[code]
            memberships = {x.strip() for x in existing["index"].split("|") if x.strip()}
            memberships.add(row["index"])
            existing["index"] = "|".join(sorted(memberships))

    write_csv(sorted(grouped.values(), key=lambda row: row["code"]), path)


def main() -> int:
    args = parse_args()
    selected = list(INDEXES) if args.index == "all" else [args.index]

    retrieved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    all_rows: list[dict[str, str]] = []

    print(f"KRX 구성종목 수집 시작: {retrieved_at}")

    for index_key in selected:
        info = INDEXES[index_key]
        try:
            rows = fetch_constituents(index_key)
        except Exception as exc:
            print(
                f"[{info['name']}] 수집 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1

        path = args.output_dir / f"{index_key}.csv"
        write_csv(rows, path)
        all_rows.extend(rows)
        missing_names = sum(1 for row in rows if not row["name"])
        print(
            f"[{info['name']}] {len(rows)}종목 -> {path}"
            + (f" (종목명 미매핑 {missing_names}개)" if missing_names else "")
        )

    if len(selected) > 1:
        combined_path = args.output_dir / "all.csv"
        write_combined(all_rows, combined_path)
        unique_codes = len({row["code"] for row in all_rows})
        print(f"[ALL] {unique_codes}개 고유 종목 -> {combined_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
