from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from pykrx import stock
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pykrx가 설치되어 있지 않습니다. `pip install pykrx`를 실행하세요."
    ) from exc

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "universe"

# KRX index codes used by pykrx.
INDEXES = {
    "kospi200": {"index_code": "1028", "market": "KOSPI", "name": "KOSPI 200"},
    "kosdaq150": {"index_code": "2203", "market": "KOSDAQ", "name": "KOSDAQ 150"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="현재 KOSPI 200 / KOSDAQ 150 구성종목을 pykrx로 가져옵니다."
    )
    parser.add_argument(
        "--index", choices=["kospi200", "kosdaq150", "all"], default="all",
        help="가져올 지수. 기본값: all",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="구성종목 CSV 저장 디렉터리",
    )
    return parser.parse_args()


def _normalize_codes(values: list[str] | tuple[str, ...]) -> list[str]:
    codes: list[str] = []
    for value in values:
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 6:
            codes.append(digits)
    return list(dict.fromkeys(codes))


def fetch_constituents(index_key: str) -> list[dict[str, str]]:
    info = INDEXES[index_key]
    index_code = info["index_code"]
    print(f"[{info['name']}] pykrx 조회: index_code={index_code}", flush=True)
    try:
        values = stock.get_index_portfolio_deposit_file(index_code)
    except Exception as exc:
        raise RuntimeError(
            f"{info['name']} 구성종목 조회 실패: {type(exc).__name__}: {exc}"
        ) from exc

    codes = _normalize_codes(values)
    if not codes:
        raise RuntimeError(
            f"{info['name']} 구성종목을 가져오지 못했습니다. "
            f"pykrx 반환값={type(values).__name__}, count=0"
        )

    # 이번 단계는 구성종목 코드 조회 자체를 검증하는 테스트이므로
    # 종목명 조회는 별도로 수행하지 않는다.
    rows = [
        {
            "code": code,
            "name": "",
            "index": info["name"],
            "index_code": index_code,
        }
        for code in codes
    ]
    rows.sort(key=lambda row: row["code"])
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["code", "name", "index", "index_code"]).to_csv(
        path, index=False, encoding="utf-8-sig"
    )


def write_combined(rows: list[dict[str, str]], path: Path) -> None:
    grouped: dict[str, dict[str, str]] = {}
    for row in rows:
        code = row["code"]
        if code not in grouped:
            grouped[code] = dict(row)
            continue
        memberships = {x.strip() for x in grouped[code]["index"].split("|") if x.strip()}
        memberships.add(row["index"])
        grouped[code]["index"] = "|".join(sorted(memberships))
    write_csv(sorted(grouped.values(), key=lambda row: row["code"]), path)


def main() -> int:
    args = parse_args()
    selected = list(INDEXES) if args.index == "all" else [args.index]
    retrieved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    all_rows: list[dict[str, str]] = []
    print(f"지수 구성종목 수집 시작: {retrieved_at}")

    for index_key in selected:
        info = INDEXES[index_key]
        try:
            rows = fetch_constituents(index_key)
        except Exception as exc:
            print(f"[{info['name']}] 수집 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        path = args.output_dir / f"{index_key}.csv"
        write_csv(rows, path)
        all_rows.extend(rows)
        print(f"[{info['name']}] {len(rows)}종목 -> {path}")

    if len(selected) > 1:
        combined_path = args.output_dir / "all.csv"
        write_combined(all_rows, combined_path)
        unique_codes = len({row["code"] for row in all_rows})
        print(f"[ALL] {unique_codes}개 고유 종목 -> {combined_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
