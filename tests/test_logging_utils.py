import csv
import datetime as dt
from pathlib import Path

from layering_detection.models import SuspiciousSequence
from layering_detection.logging_utils import write_detection_logs
from layering_detection.security_utils import sanitize_for_csv


class TestWriteDetectionLogs:
    def test_writes_one_row_per_sequence_with_expected_fields(self, tmp_path) -> None:
        base = dt.datetime(2025, 3, 1, 10, 0, 0, tzinfo=dt.timezone.utc)

        sequences = [
            SuspiciousSequence(
                account_id="ACC100",
                product_id="XYZ",
                side="BUY",
                start_timestamp=base,
                end_timestamp=base + dt.timedelta(seconds=8),
                total_buy_qty=5000,
                total_sell_qty=2000,
                num_cancelled_orders=3,
                order_timestamps=[
                    base,
                    base + dt.timedelta(seconds=2),
                    base + dt.timedelta(seconds=4),
                ],
            ),
            SuspiciousSequence(
                account_id="ACC200",
                product_id="ABC",
                side="SELL",
                start_timestamp=base + dt.timedelta(minutes=1),
                end_timestamp=base + dt.timedelta(minutes=1, seconds=5),
                total_buy_qty=1000,
                total_sell_qty=3000,
                num_cancelled_orders=2,
                order_timestamps=[
                    base + dt.timedelta(minutes=1),
                    base + dt.timedelta(minutes=1, seconds=3),
                ],
            ),
        ]

        log_path = tmp_path / "logs" / "detections.csv"
        write_detection_logs(log_path, sequences)

        assert log_path.exists()

        with log_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames

        assert fieldnames == [
            "account_id",
            "product_id",
            "window_start_timestamp",
            "detected_timestamp",
            "duration_seconds",
            "num_cancelled_orders",
            "total_buy_qty",
            "total_sell_qty",
            "order_timestamps",
        ]
        assert len(rows) == 2

        r1 = next(r for r in rows if r["account_id"] == "ACC100")
        assert r1["product_id"] == "XYZ"
        assert r1["window_start_timestamp"].startswith(base.isoformat())
        assert r1["detected_timestamp"].startswith(
            (base + dt.timedelta(seconds=8)).isoformat()
        )
        assert r1["num_cancelled_orders"] == "3"
        assert r1["total_buy_qty"] == "5000"
        assert r1["total_sell_qty"] == "2000"
        # order_timestamps should contain all three timestamps, separated by semicolons
        assert ";" in r1["order_timestamps"]

        r2 = next(r for r in rows if r["account_id"] == "ACC200")
        assert r2["product_id"] == "ABC"
        assert r2["num_cancelled_orders"] == "2"
        assert r2["total_buy_qty"] == "1000"
        assert r2["total_sell_qty"] == "3000"

    def test_pseudonymize_accounts_option_hashes_account_ids(self, tmp_path) -> None:
        base = dt.datetime(2025, 3, 1, 10, 0, 0, tzinfo=dt.timezone.utc)

        sequences = [
            SuspiciousSequence(
                account_id="=ACC_FORMULA",
                product_id="@XYZ",
                side="BUY",
                start_timestamp=base,
                end_timestamp=base + dt.timedelta(seconds=8),
                total_buy_qty=5000,
                total_sell_qty=2000,
                num_cancelled_orders=3,
                order_timestamps=[base],
            )
        ]

        log_path = tmp_path / "logs" / "detections_pseudo.csv"
        write_detection_logs(log_path, sequences, pseudonymize_accounts=True, salt="s1")

        with log_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        r = rows[0]

        # account_id should be a hash, not the original and not starting with '='
        assert r["account_id"] != "=ACC_FORMULA"
        assert not r["account_id"].startswith("=")
        # product_id should still be sanitized for CSV (prefixed)
        assert r["product_id"] == sanitize_for_csv("@XYZ")



