from __future__ import annotations

import csv
from pathlib import Path

from src.engine.microstructure_recorder import MicrostructureRecorder


def test_record_realtime_microstructure(tmp_path: Path):
    recorder = MicrostructureRecorder(tmp_path)
    payload = {
        "code": "005930",
        "data": {
            "tm": "20260911093015",
            "curr": "75000",
            "open": "74800",
            "high": "75200",
            "low": "74700",
            "volume": "12000",
            "v_pw": "118.5",
            "ask_tot": "4000",
            "bid_tot": "6000",
            "best_ask": "75100",
            "best_bid": "75000",
        },
    }

    assert recorder.record(payload) is True

    target = tmp_path / "20260911" / "005930.csv"
    assert target.exists()
    with target.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["code"] == "005930"
    assert rows[0]["v_pw"] == "118.5"
    assert rows[0]["ask_tot"] == "4000.0"
    assert rows[0]["bid_tot"] == "6000.0"
    assert rows[0]["spread"] == "100.0"


def test_record_ignores_outside_market_hours(tmp_path: Path):
    recorder = MicrostructureRecorder(tmp_path)
    payload = {
        "code": "005930",
        "data": {"tm": "20260911080000", "curr": "75000"},
    }

    assert recorder.record(payload) is False
    assert not (tmp_path / "20260911" / "005930.csv").exists()
