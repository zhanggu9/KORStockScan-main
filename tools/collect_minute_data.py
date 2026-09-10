from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Allow running as: python tools/collect_minute_data.py ...
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.kiwoom_utils import (  # noqa: E402
    get_kiwoom_token,
    get_minute_candles_ka10080_with_meta,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "minute"


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYYMMDD 형식이어야 합니다.") from exc


def trading_dates(start, end):
    current = start
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def normalize_row(code: str, row: dict, base_date: str) -> dict:
    source_timestamp = str(row.get("source_timestamp") or "").strip()
    if len(source_timestamp) == 14 and source_timestamp.isdigit():
        dt = datetime.strptime(source_timestamp, "%Y%m%d%H%M%S")
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        tm = str(row.get("체결시간") or "").strip()
        timestamp = f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:8]} {tm}" if tm else ""

    return {
        "datetime": timestamp,
        "code": code,
        "open": int(row.get("시가") or 0),
        "high": int(row.get("고가") or 0),
        "low": int(row.get("저가") or 0),
        "close": int(row.get("현재가") or 0),
        "volume": int(row.get("거래량") or 0),
    }


def collect_one_day(token: str, code: str, day, output_dir: Path, limit: int) -> Path | None:
    base_dt = day.strftime("%Y%m%d")

    # The existing with_meta wrapper already supports base_dt. Use it instead
    # of the simpler wrapper, which intentionally exposes only (token, code, limit).
    rows, meta = get_minute_candles_ka10080_with_meta(
        token,
        code,
        limit=limit,
        base_dt=base_dt,
    )

    normalized = [normalize_row(code, row, base_dt) for row in rows]
    normalized = [r for r in normalized if r["datetime"]]
    
    # 15:30 이후 데이터 제외
    normalized = [
        r for r in normalized
        if r["datetime"][11:19] <= "15:30:00"
    ]

    # Defense-in-depth: never write bars belonging to another date into the
    # requested day's file, even if the API returns extra rows.
    prefix = f"{base_dt[:4]}-{base_dt[4:6]}-{base_dt[6:8]}"
    normalized = [r for r in normalized if r["datetime"].startswith(prefix)]
    normalized.sort(key=lambda r: r["datetime"])

    if not normalized:
        print(
            f"[{base_dt}] {code}: 해당 날짜의 1분봉 데이터가 없습니다. "
            f"request_base_dt={meta.get('request_base_dt')}"
        )
        return None

    # Remove duplicate timestamps defensively.
    deduped = {}
    for row in normalized:
        deduped[row["datetime"]] = row
    normalized = list(deduped.values())
    normalized.sort(key=lambda r: r["datetime"])

    day_dir = output_dir / code
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{base_dt}.csv"

    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["datetime", "code", "open", "high", "low", "close", "volume"],
        )
        writer.writeheader()
        writer.writerows(normalized)

    print(
        f"[{base_dt}] {code}: {len(normalized)} bars "
        f"({normalized[0]['datetime']} ~ {normalized[-1]['datetime']}) -> {path}"
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiwoom ka10080 1분봉 수집기")
    parser.add_argument("--code", required=True, help="종목코드 예: 005930")
    parser.add_argument("--start", required=True, type=parse_date, help="시작일 YYYYMMDD")
    parser.add_argument("--end", type=parse_date, help="종료일 YYYYMMDD")
    parser.add_argument(
        "--limit",
        type=int,
        default=1200,
        help="날짜별 요청 봉 수. 기본 1200 (페이지 연속조회 사용)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="저장 루트 디렉터리",
    )
    parser.add_argument("--sleep", type=float, default=0.5, help="날짜 간 요청 간격(초)")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다.")
    end = args.end or args.start
    if end < args.start:
        parser.error("--end는 --start보다 빠를 수 없습니다.")

    token = get_kiwoom_token(require_issued_today=True)
    if not token:
        print("Kiwoom token 발급/조회에 실패했습니다.", file=sys.stderr)
        return 1

    print(f"수집 시작: code={args.code}, start={args.start}, end={end}, limit={args.limit}")
    collected = 0
    for day in trading_dates(args.start, end):
        try:
            if collect_one_day(token, args.code, day, args.output_dir, args.limit):
                collected += 1
        except Exception as exc:
            print(f"[{day:%Y%m%d}] 수집 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(max(0.0, args.sleep))

    print(f"수집 완료: {collected} 거래일")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
