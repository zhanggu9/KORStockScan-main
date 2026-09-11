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
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "universe" / "all.csv"
INDEX_ORDER = ("KOSPI 200", "KOSDAQ 150")
DEFAULT_RETRIES = 3
DEFAULT_SLEEP_DAY_SINGLE = 0.3
DEFAULT_SLEEP_DAY_UNIVERSE = 0.3
DEFAULT_SLEEP_STOCK = 0.3
DEFAULT_RETRY_SLEEP = 3.0


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
        explicit_request_code=True,
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


def read_universe(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"유니버스 파일을 찾을 수 없습니다: {path}\n"
            "먼저 `python tools/fetch_index_universe.py --index all`을 실행하세요."
        )

    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"code", "name", "index"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"유니버스 CSV 컬럼이 올바르지 않습니다. 필요한 컬럼: {sorted(required)}"
            )

        seen: set[str] = set()
        for row in reader:
            code = str(row.get("code") or "").strip()
            name = str(row.get("name") or "").strip()
            index_name = str(row.get("index") or "").strip()
            if len(code) != 6 or not code.isdigit() or not index_name:
                continue

            key = f"{index_name}:{code}"
            if key in seen:
                continue
            seen.add(key)
            rows.append({"code": code, "name": name, "index": index_name})

    ordered: list[dict[str, str]] = []
    for index_name in INDEX_ORDER:
        ordered.extend(row for row in rows if row["index"] == index_name)
    ordered.extend(row for row in rows if row["index"] not in INDEX_ORDER)
    return ordered


def output_path(output_dir: Path, code: str, day) -> Path:
    return output_dir / code / f"{day:%Y%m%d}.csv"


def collect_with_retry(
    token: str,
    row: dict[str, str],
    day,
    output_dir: Path,
    limit: int,
    retries: int,
    retry_sleep: float,
    overwrite: bool,
) -> tuple[bool, bool]:
    code = row["code"]
    name = row["name"]
    path = output_path(output_dir, code, day)

    if path.exists() and not overwrite:
        print(f"    ↳ SKIP {code} {name}: 이미 존재 ({path})")
        return True, True

    for attempt in range(1, retries + 2):
        try:
            result = collect_one_day(token, code, day, output_dir, limit)
            return result is not None, False
        except Exception as exc:
            if attempt > retries:
                print(
                    f"    ↳ FAIL {code} {name} {day:%Y%m%d}: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                return False, False

            wait = retry_sleep * attempt
            print(
                f"    ↳ RETRY {code} {name} {day:%Y%m%d}: "
                f"attempt={attempt}/{retries}, wait={wait:.1f}s, "
                f"error={type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            time.sleep(max(0.0, wait))

    return False, False


def collect_single_code(args, token: str, end) -> int:
    print(f"수집 시작: code={args.code}, start={args.start}, end={end}, limit={args.limit}")
    collected = 0
    failed = 0

    for day in trading_dates(args.start, end):
        try:
            if collect_one_day(token, args.code, day, args.output_dir, args.limit):
                collected += 1
        except Exception as exc:
            failed += 1
            print(f"[{day:%Y%m%d}] 수집 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        time.sleep(max(0.0, args.sleep_day))

    print(f"수집 완료: {collected} 거래일, failed={failed}")
    return 0 if failed == 0 else 2


def collect_universe(args, token: str, end) -> int:
    try:
        rows = read_universe(args.universe)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.index != "all":
        target_index = "KOSPI 200" if args.index == "kospi200" else "KOSDAQ 150"
        rows = [row for row in rows if row["index"] == target_index]

    if args.start_stock is not None:
        if args.start_stock > len(rows):
            print(
                f"--start-stock={args.start_stock}가 현재 유니버스 종목 수({len(rows)})를 초과합니다.",
                file=sys.stderr,
            )
            return 1
        rows = rows[args.start_stock - 1 :]

    if args.max_stocks is not None:
        rows = rows[: args.max_stocks]

    days = list(trading_dates(args.start, end))
    if not rows:
        print("수집할 종목이 없습니다.", file=sys.stderr)
        return 1
    if not days:
        print("수집할 거래일이 없습니다.", file=sys.stderr)
        return 1

    total_jobs = len(rows) * len(days)
    success = 0
    skipped = 0
    failed = 0
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")

    print(
        f"대량 수집 시작: {started_at} | "
        f"stocks={len(rows)}, days={len(days)}, jobs={total_jobs}"
    )
    if args.start_stock is not None:
        print(f"시작 종목 순번: {args.start_stock}")
    print(f"유니버스: {args.universe}")
    print(f"저장 루트: {args.output_dir}")

    current_index = None
    seen_codes: set[str] = set()

    for stock_no, row in enumerate(rows, start=1):
        display_stock_no = stock_no + (args.start_stock - 1 if args.start_stock is not None else 0)
        if row["index"] != current_index:
            current_index = row["index"]
            print(f"\n===== {current_index} =====", flush=True)

        if row["code"] in seen_codes:
            print(
                f"[{display_stock_no}/{display_stock_no + len(rows) - stock_no}] {row['code']} {row['name']} | "
                "DUPLICATE CODE - skip",
                flush=True,
            )
            continue
        seen_codes.add(row["code"])

        total_stock_count = len(rows) + (args.start_stock - 1 if args.start_stock is not None else 0)
        print(
            f"[{display_stock_no}/{total_stock_count}] {row['code']} {row['name']} | {row['index']}",
            flush=True,
        )

        stock_requested = False
        for day_no, day in enumerate(days, start=1):
            ok, was_skipped = collect_with_retry(
                token,
                row,
                day,
                args.output_dir,
                args.limit,
                args.retries,
                args.retry_sleep,
                args.overwrite,
            )
            if ok:
                if was_skipped:
                    skipped += 1
                else:
                    success += 1
                    stock_requested = True
            else:
                failed += 1

            if not was_skipped and day_no < len(days):
                time.sleep(max(0.0, args.sleep_day))

        if stock_requested:
            time.sleep(max(0.0, args.sleep_stock))

    finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
    print(
        f"\n대량 수집 완료: {finished_at} | "
        f"success={success}, skipped={skipped}, failed={failed}, jobs={total_jobs}"
    )
    return 0 if failed == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kiwoom ka10080 1분봉 수집기 (단일 종목 / all.csv 유니버스 일괄 수집)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--code", help="단일 종목코드 예: 005930")
    group.add_argument(
        "--universe",
        nargs="?",
        const=DEFAULT_UNIVERSE,
        type=Path,
        help="all.csv 기반 유니버스 일괄 수집. 값 생략 시 data/universe/all.csv",
    )
    parser.add_argument("--start", required=True, type=parse_date, help="시작일 YYYYMMDD")
    parser.add_argument("--end", type=parse_date, help="종료일 YYYYMMDD")
    parser.add_argument(
        "--index",
        choices=["all", "kospi200", "kosdaq150"],
        default="all",
        help="--universe에서 수집할 지수. 기본: all",
    )
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
    parser.add_argument(
        "--sleep",
        dest="sleep_day",
        type=float,
        default=None,
        help="날짜 간 요청 간격(초). 단일 종목 기본 0.3, 유니버스 기본 0.3",
    )
    parser.add_argument(
        "--sleep-day",
        dest="sleep_day",
        type=float,
        default=argparse.SUPPRESS,
        help="날짜 간 요청 간격(초). --sleep보다 우선",
    )
    parser.add_argument(
        "--sleep-stock",
        type=float,
        default=DEFAULT_SLEEP_STOCK,
        help="--universe에서 실제 API 호출이 있었던 종목 간 요청 간격(초). 기본 0.3",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="--universe에서 실패 재시도 횟수. 기본 3",
    )
    parser.add_argument(
        "--retry-sleep",
        type=float,
        default=DEFAULT_RETRY_SLEEP,
        help="재시도 대기시간 배수의 기준 초. 기본 3.0",
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        help="--universe 테스트용 최대 종목 수",
    )
    parser.add_argument(
        "--start-stock",
        type=int,
        help="--universe에서 필터링된 종목 목록의 1-based 시작 순번. 예: 53이면 53번째 종목부터 수집",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="--universe에서 이미 존재하는 일별 CSV도 다시 수집",
    )
    args = parser.parse_args()

    if args.sleep_day is None:
        args.sleep_day = DEFAULT_SLEEP_DAY_SINGLE if args.code else DEFAULT_SLEEP_DAY_UNIVERSE

    if args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다.")
    if args.retries < 0:
        parser.error("--retries는 0 이상이어야 합니다.")
    if args.sleep_day < 0 or args.sleep_stock < 0 or args.retry_sleep < 0:
        parser.error("sleep 관련 옵션은 0 이상이어야 합니다.")
    if args.max_stocks is not None and args.max_stocks < 1:
        parser.error("--max-stocks는 1 이상이어야 합니다.")
    if args.start_stock is not None and args.start_stock < 1:
        parser.error("--start-stock은 1 이상이어야 합니다.")
    if args.start_stock is not None and args.code:
        parser.error("--start-stock은 --universe에서만 사용할 수 있습니다.")

    end = args.end or args.start
    if end < args.start:
        parser.error("--end는 --start보다 빠를 수 없습니다.")

    token = get_kiwoom_token(require_issued_today=True)
    if not token:
        print("Kiwoom token 발급/조회에 실패했습니다.", file=sys.stderr)
        return 1

    if args.code:
        return collect_single_code(args, token, end)
    return collect_universe(args, token, end)


if __name__ == "__main__":
    raise SystemExit(main())
