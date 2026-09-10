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
        "--index",
        choices=["kospi200", "kosdaq150", "all"],
        default="all",
        help="가져올 지수. 기본값: all",
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


def fetch_constituents(index_key: str, date: str | None = None) -> list[dict[str, str]]:
    info = INDEXES[index_key]
    index_code = info["index_code"]
    print(
        f"[{info['name']}] pykrx 조회: index_code={index_code}"
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

    rows = [
        {
            "code": code,
            "name": "",
            "index": info["name"],
            "index_code": index_code,
            "as_of_date": date or "",
        }
        for code in codes
    ]
    rows.sort(key=lambda row: row["code"])
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        rows,
        columns=["code", "name", "index", "index_code", "as_of_date"],
    ).to_csv(path, index=False, encoding="utf-8-sig")


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
    try:
        _validate_krx_credentials()
    except RuntimeError as exc:
        print(f"[KRX 인증 필요] {exc}", file=sys.stderr)
        return 2

    selected = list(INDEXES) if args.index == "all" else [args.index]
    retrieved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    all_rows: list[dict[str, str]] = []
    print(f"지수 구성종목 수집 시작: {retrieved_at}")

    for index_key in selected:
        info = INDEXES[index_key]
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
        all_rows.extend(rows)
        print(f"[{info['name']}] {len(rows)}종목 -> {path}")

    if len(selected) > 1:
        combined_path = args.output_dir / "all.csv"
        write_combined(all_rows, combined_path)
        unique_codes = len({row["code"] for row in all_rows})
        print(f"[ALL] {unique_codes}개 고유 종목 -> {combined_path}")

    print(f"완료: {retrieved_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
