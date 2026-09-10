from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.kiwoom_utils import (  # noqa: E402
    get_kiwoom_token,
)
from tools.collect_minute_data import collect_one_day, parse_date, trading_dates  # noqa: E402

DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "universe" / "all.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "minute"
DEFAULT_LIMIT = 1200
DEFAULT_SLEEP_STOCK = 0.5
DEFAULT_SLEEP_DAY = 0.5
DEFAULT_RETRIES = 3

INDEX_ORDER = ("KOSPI 200", "KOSDAQ 150")


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
    unknown = [row for row in rows if row["index"] not in INDEX_ORDER]
    ordered.extend(unknown)
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
) -> bool:
    code = row["code"]
    name = row["name"]
    path = output_path(output_dir, code, day)

    if path.exists() and not overwrite:
        print(f"    ↳ SKIP {code} {name}: 이미 존재 ({path})")
        return True

    for attempt in range(1, retries + 2):
        try:
            result = collect_one_day(token, code, day, output_dir, limit)
            if result is not None:
                return True
            return False
        except Exception as exc:
            if attempt > retries:
                print(
                    f"    ↳ FAIL {code} {name} {day:%Y%m%d}: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                return False
            wait = retry_sleep * attempt
            print(
                f"    ↳ RETRY {code} {name} {day:%Y%m%d}: "
                f"attempt={attempt}/{retries}, wait={wait:.1f}s, "
                f"error={type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            time.sleep(max(0.0, wait))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="all.csv의 KOSPI 200 + KOSDAQ 150을 순서대로 Kiwoom 1분봉으로 일괄 수집합니다."
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=DEFAULT_UNIVERSE,
        help="유니버스 CSV. 기본: data/universe/all.csv",
    )
    parser.add_argument("--start", required=True, type=parse_date, help="시작일 YYYYMMDD")
    parser.add_argument("--end", type=parse_date, help="종료일 YYYYMMDD")
    parser.add_argument(
        "--index",
        choices=["all", "kospi200", "kosdaq150"],
        default="all",
        help="수집할 지수. 기본: all",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="날짜별 요청 봉 수. 기본: 1200",
    )
    parser.add_argument(
        "--sleep-stock",
        type=float,
        default=DEFAULT_SLEEP_STOCK,
        help="종목 간 요청 간격(초). 기본: 0.5",
    )
    parser.add_argument(
        "--sleep-day",
        type=float,
        default=DEFAULT_SLEEP_DAY,
        help="한 종목의 날짜 간 요청 간격(초). 기본: 0.5",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="실패 재시도 횟수. 기본: 3",
    )
    parser.add_argument(
        "--retry-sleep",
        type=float,
        default=2.0,
        help="재시도 대기시간 배수의 기준 초. 기본: 2.0",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="1분봉 저장 루트. 기본: data/minute",
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        help="테스트용 최대 종목 수. 지정하지 않으면 전체 수집",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="이미 존재하는 일별 CSV도 다시 수집",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit은 1 이상이어야 합니다.")
    if args.retries < 0:
        parser.error("--retries는 0 이상이어야 합니다.")
    if args.sleep_stock < 0 or args.sleep_day < 0 or args.retry_sleep < 0:
        parser.error("sleep 관련 옵션은 0 이상이어야 합니다.")

    end = args.end or args.start
    if end < args.start:
        parser.error("--end는 --start보다 빠를 수 없습니다.")

    rows = read_universe(args.universe)
    if args.index == "kospi200":
        rows = [row for row in rows if row["index"] == "KOSPI 200"]
    elif args.index == "kosdaq150":
        rows = [row for row in rows if row["index"] == "KOSDAQ 150"]

    if args.max_stocks is not None:
        if args.max_stocks < 1:
            parser.error("--max-stocks는 1 이상이어야 합니다.")
        rows = rows[: args.max_stocks]

    days = list(trading_dates(args.start, end))
    if not rows:
        print("수집할 종목이 없습니다.", file=sys.stderr)
        return 1
    if not days:
        print("수집할 거래일이 없습니다.", file=sys.stderr)
        return 1

    token = get_kiwoom_token(require_issued_today=True)
    if not token:
        print("Kiwoom token 발급/조회에 실패했습니다.", file=sys.stderr)
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
    print(f"저장 루트: {args.output_dir}")

    current_index = None
    for stock_no, row in enumerate(rows, start=1):
        if row["index"] != current_index:
            current_index = row["index"]
            print(f"\n===== {current_index} =====", flush=True)

        print(
            f"[{stock_no}/{len(rows)}] {row['code']} {row['name']} | {row['index']}",
            flush=True,
        )
        for day_no, day in enumerate(days, start=1):
            path = output_path(args.output_dir, row["code"], day)
            existed = path.exists() and not args.overwrite
            ok = collect_with_retry(
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
                if existed:
                    skipped += 1
                else:
                    success += 1
            else:
                failed += 1
            if day_no < len(days):
                time.sleep(max(0.0, args.sleep_day))
        time.sleep(max(0.0, args.sleep_stock))

    finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
    print(
        f"\n대량 수집 완료: {finished_at} | "
        f"success={success}, skipped={skipped}, failed={failed}, jobs={total_jobs}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
