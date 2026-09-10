from __future__ import annotations

import argparse
import os
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

INDEXES = {
    "kospi200": {"index_code": "1028", "market": "KOSPI", "name": "KOSPI 200"},
    "kosdaq150": {"index_code": "2203", "market": "KOSDAQ", "name": "KOSDAQ 150"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="현재 KOSPI 200 / KOSDAQ 150 구성종목을 pykrx로 가져옵니다."
    )
    parser.add_argument(
        "--index",
        choices=["kospi200", "kosdaq150", "all"],
        default="all",
        help="가져올 지수. 기본값: all (KOSPI200 먼저, KOSDAQ150 다음)",
    )
    parser.add_argument(
        "--date",
        help="구성종목 기준일 (YYYYMMDD). 기본값: 최근 영업일",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="구성종목 CSV 저장 디렉터리",
    )
    return parser.parse_args()


def _validate_krx_credentials() -> None:
    missing = [name for name in ("KRX_ID", "KRX_PW") if not os.getenv(name)]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"pykrx 최신 버전은 KRX 로그인에 {names} 환경변수가 필요합니다.\n"
            "WSL에서 아래처럼 설정한 뒤 다시 실행하세요.\n"
            "  export KRX_ID='당신의_KRX_아이디'\n"
            "  export KRX_PW='당신의_KRX_비밀번호'\n"
            "영구 설정은 ~/.bashrc에 추가하면 됩니다.\n"
            "※ 비밀번호를 GitHub에 커밋되는 파일에 저장하지 마세요."
        )


def _normalize_codes(values) -> list[str]:
    codes: list[str] = []
    if isinstance(values, pd.DataFrame):
        values = values.index.tolist()
    elif isinstance(values, pd.Series):
        values = values.tolist()

    for value in values:
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 6:
            codes.append(digits)
    return list(dict.fromkeys(codes))


def _fetch_stock_names(market: str, date: str | None = None) -> dict[str, str]:
    """Fetch the market ticker list, then map each ticker to its name."""
    try:
        tickers = stock.get_market_ticker_list(date=date, market=market)
    except Exception as exc:
        raise RuntimeError(
            f"{market} 종목 목록 조회 실패: {type(exc).__name__}: {exc}"
        ) from exc

    names: dict[str, str] = {}
    for ticker in _normalize_codes(tickers):
        try:
            name = stock.get_market_ticker_name(ticker)
        except Exception as exc:
            print(
                f"[{market}] 종목명 조회 실패: {ticker}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        if name:
            names[ticker] = str(name).strip()
    return names


def fetch_constituents(index_key: str, date: str | None = None) -> list[dict[str, str]]:
    info = INDEXES[index_key]
    index_code = info["index_code"]
    print(
        f"[{info['name']}] 구성종목 수집 시작: index_code={index_code}"
        + (f", date={date}" if date else ""),
        flush=True,
    )

    try:
        values = stock.get_index_portfolio_deposit_file(index_code, date=date)
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

    print(f"[{info['name']}] 구성종목 코드 {len(codes)}개 확인")
    print(f"[{info['name']}] 종목명 매핑 중...", flush=True)
    name_map = _fetch_stock_names(info["market"], date=date)

    rows = [
        {
            "code": code,
            "name": name_map.get(code, ""),
            "index": info["name"],
        }
        for code in codes
    ]
    rows.sort(key=lambda row: row["code"])
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["code", "name", "index"]).to_csv(
        path, index=False, encoding="utf-8-sig"
    )


def main() -> int:
    args = parse_args()
    try:
        _validate_krx_credentials()
    except RuntimeError as exc:
        print(f"[KRX 인증 필요] {exc}", file=sys.stderr)
        return 2

    selected = ["kospi200", "kosdaq150"] if args.index == "all" else [args.index]
    retrieved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"지수 구성종목 수집 시작: {retrieved_at}")

    for order, index_key in enumerate(selected, start=1):
        info = INDEXES[index_key]
        print(f"\n===== {order}/{len(selected)}: {info['name']} =====")
        try:
            rows = fetch_constituents(index_key, args.date)
        except Exception as exc:
            print(
                f"[{info['name']}] 수집 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 1

        path = args.output_dir / f"{index_key}.csv"
        write_csv(rows, path)
        missing_names = sum(1 for row in rows if not row["name"])
        print(
            f"[{info['name']}] {len(rows)}종목 -> {path}"
            + (f" (종목명 미매핑 {missing_names}개)" if missing_names else "")
        )

    print("\n수집 완료: KOSPI200과 KOSDAQ150을 각각 별도 CSV로 저장했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
