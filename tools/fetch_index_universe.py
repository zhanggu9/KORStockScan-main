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
    import FinanceDataReader as fdr
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "FinanceDataReader가 설치되어 있지 않습니다. `pip install finance-datareader`를 실행하세요."
    ) from exc

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "universe"

INDEXES = {
    "kospi200": {"snapshot": "KRX/INDEX/STOCK/1028", "market": "KOSPI", "name": "KOSPI 200"},
    "kosdaq150": {"snapshot": "KRX/INDEX/STOCK/2203", "market": "KOSDAQ", "name": "KOSDAQ 150"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="현재 KOSPI 200 / KOSDAQ 150 구성종목을 자동으로 가져옵니다."
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


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    if df is None:
        return None
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]
    return None


def _extract_codes(raw: pd.DataFrame) -> list[str]:
    if raw is None or raw.empty:
        return []
    code_col = _find_column(
        raw, ("Symbol", "Code", "Ticker", "종목코드", "티커", "ISU_SRT_CD")
    )
    values = raw[code_col].tolist() if code_col is not None else raw.index.tolist()
    codes: list[str] = []
    for value in values:
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 6:
            codes.append(digits)
    return list(dict.fromkeys(codes))


def _load_name_map(market: str) -> dict[str, str]:
    try:
        listing = fdr.StockListing(market)
    except Exception as exc:
        print(f"[{market}] 종목명 매핑 조회 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}
    code_col = _find_column(listing, ("Symbol", "Code", "Ticker", "종목코드", "티커"))
    name_col = _find_column(listing, ("Name", "name", "종목명"))
    if code_col is None or name_col is None:
        return {}
    return {
        str(row[code_col]).strip().zfill(6): str(row[name_col]).strip()
        for _, row in listing.iterrows()
    }


def fetch_constituents(index_key: str) -> list[dict[str, str]]:
    info = INDEXES[index_key]
    print(f"[{info['name']}] FinanceDataReader 조회: {info['snapshot']}")
    try:
        raw = fdr.SnapDataReader(info["snapshot"])
    except Exception as exc:
        raise RuntimeError(
            f"{info['name']} 구성종목 조회 실패: {type(exc).__name__}: {exc}"
        ) from exc

    codes = _extract_codes(raw)
    if not codes:
        raise RuntimeError(
            f"{info['name']} 구성종목을 가져오지 못했습니다. "
            f"응답형식={type(raw).__name__}, shape={getattr(raw, 'shape', None)}"
        )

    name_map = _load_name_map(info["market"])
    rows = [
        {
            "code": code,
            "name": name_map.get(code, ""),
            "index": info["name"],
            "index_code": info["snapshot"].rsplit("/", 1)[-1],
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
