import csv
from pathlib import Path

from layering_detection.runner import run_pipeline


BASE_DIR = Path(__file__).resolve().parent.parent


class TestRunnerPipeline:
    def test_run_pipeline_creates_outputs_and_logs(self, tmp_path) -> None:
        input_path = BASE_DIR / "input" / "transactions.csv"
        assert input_path.exists(), "Expected sample transactions.csv for pipeline test"

        output_dir = tmp_path / "output"
        logs_dir = tmp_path / "logs"

        run_pipeline(input_path=input_path, output_dir=output_dir, logs_dir=logs_dir)

        suspicious_path = output_dir / "suspicious_accounts.csv"
        logs_path = logs_dir / "detections.csv"

        assert suspicious_path.exists()
        assert logs_path.exists()

        # Sanity check contents of suspicious_accounts.csv
        with suspicious_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # From the detector tests we expect two sequences for the sample data.
        assert len(rows) == 2
        keys = {(r["account_id"], r["product_id"]) for r in rows}
        assert keys == {("ACC001", "IBM"), ("ACC017", "AAPL")}

        # Sanity check contents of detections.csv
        with logs_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            log_rows = list(reader)
            log_fieldnames = reader.fieldnames

        assert log_fieldnames == [
            "account_id",
            "product_id",
            "order_timestamps",
            "duration_seconds",
        ]
        assert len(log_rows) == 2


