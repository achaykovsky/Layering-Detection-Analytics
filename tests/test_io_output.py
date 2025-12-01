import csv
import datetime as dt
from pathlib import Path

from layering_detection.io import read_transactions, write_suspicious_accounts
from layering_detection.models import SuspiciousSequence
from layering_detection.detector import detect_suspicious_sequences


BASE_DIR = Path(__file__).resolve().parent.parent


def _run_detection():
    input_path = BASE_DIR / "input" / "transactions.csv"
    events = read_transactions(input_path)
    return detect_suspicious_sequences(events)


class TestWriteSuspiciousAccounts:
    def test_creates_csv_with_expected_header_and_row_count(self, tmp_path) -> None:
        sequences = _run_detection()
        assert len(sequences) == 2

        out_dir = tmp_path / "output"
        out_path = out_dir / "suspicious_accounts.csv"

        write_suspicious_accounts(out_path, sequences)

        assert out_path.exists()

        with out_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames

        assert fieldnames == [
            "account_id",
            "product_id",
            "total_buy_qty",
            "total_sell_qty",
            "num_cancelled_orders",
            "detected_timestamp",
        ]
        assert len(rows) == 2

    def test_acc001_row_values(self, tmp_path) -> None:
        sequences = _run_detection()
        out_path = tmp_path / "output" / "suspicious_accounts.csv"
        write_suspicious_accounts(out_path, sequences)

        with out_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        acc001_rows = [
            r
            for r in rows
            if r["account_id"] == "ACC001" and r["product_id"] == "IBM"
        ]
        assert len(acc001_rows) == 1
        r1 = acc001_rows[0]
        assert r1["total_buy_qty"] == "15000"
        assert r1["total_sell_qty"] == "10000"
        assert r1["num_cancelled_orders"] == "3"
        assert r1["detected_timestamp"].startswith("2025-10-26T10:21:28")

    def test_acc017_row_values(self, tmp_path) -> None:
        sequences = _run_detection()
        out_path = tmp_path / "output" / "suspicious_accounts.csv"
        write_suspicious_accounts(out_path, sequences)

        with out_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        acc017_rows = [
            r
            for r in rows
            if r["account_id"] == "ACC017" and r["product_id"] == "AAPL"
        ]
        assert len(acc017_rows) == 1
        r2 = acc017_rows[0]
        assert r2["total_buy_qty"] == "12000"
        assert r2["total_sell_qty"] == "8000"
        assert r2["num_cancelled_orders"] == "3"
        assert r2["detected_timestamp"].startswith("2025-10-26T11:05:06")

    def test_only_pattern_accounts_appear(self, tmp_path) -> None:
        sequences = _run_detection()
        out_path = tmp_path / "output" / "suspicious_accounts.csv"
        write_suspicious_accounts(out_path, sequences)

        with out_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        keys = {(r["account_id"], r["product_id"]) for r in rows}
        assert keys == {("ACC001", "IBM"), ("ACC017", "AAPL")}


class TestWriteSuspiciousAccountsSynthetic:
    def test_writes_arbitrary_sequences(self, tmp_path) -> None:
        base = dt.datetime(2025, 2, 1, 14, 0, 0, tzinfo=dt.timezone.utc)

        sequences = [
            SuspiciousSequence(
                account_id="ACC777",
                product_id="GOOG",
                side="BUY",
                start_timestamp=base,
                end_timestamp=base + dt.timedelta(seconds=5),
                total_buy_qty=1000,
                total_sell_qty=0,
                num_cancelled_orders=1,
                order_timestamps=[base],
            ),
            SuspiciousSequence(
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                start_timestamp=base + dt.timedelta(minutes=1),
                end_timestamp=base + dt.timedelta(minutes=1, seconds=10),
                total_buy_qty=0,
                total_sell_qty=2000,
                num_cancelled_orders=2,
                order_timestamps=[
                    base + dt.timedelta(minutes=1),
                    base + dt.timedelta(minutes=1, seconds=2),
                ],
            ),
        ]

        out_path = tmp_path / "output" / "synthetic_suspicious_accounts.csv"
        write_suspicious_accounts(out_path, sequences)

        with out_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2

        row1 = next(r for r in rows if r["account_id"] == "ACC777")
        assert row1["product_id"] == "GOOG"
        assert row1["total_buy_qty"] == "1000"
        assert row1["total_sell_qty"] == "0"
        assert row1["num_cancelled_orders"] == "1"
        assert row1["detected_timestamp"].startswith(
            (base + dt.timedelta(seconds=5)).isoformat()
        )

        row2 = next(r for r in rows if r["account_id"] == "ACC888")
        assert row2["product_id"] == "NFLX"
        assert row2["total_buy_qty"] == "0"
        assert row2["total_sell_qty"] == "2000"
        assert row2["num_cancelled_orders"] == "2"
        assert row2["detected_timestamp"].startswith(
            (base + dt.timedelta(minutes=1, seconds=10)).isoformat()
        )
