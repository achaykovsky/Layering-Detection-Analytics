import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from layering_detection.io import read_transactions
from layering_detection.models import TransactionEvent
from layering_detection.detector import (
    detect_suspicious_sequences,
    group_events_by_account_product,
    _detect_sequences_for_group,
)


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_events() -> list:
    input_path = BASE_DIR / "input" / "transactions.csv"
    assert input_path.exists(), f"Missing test input CSV at {input_path}"
    return read_transactions(input_path)


class TestDetectorGrouping:
    def test_grouping_and_basic_counts(self) -> None:
        events = _load_events()

        grouped = group_events_by_account_product(events)

        assert len(events) == 18
        assert {("ACC001", "IBM"), ("ACC017", "AAPL"), ("ACC050", "MSFT")} == set(
            grouped.keys()
        )


@pytest.mark.parametrize(
    "account_id,product_id,expected_side,expected_start,expected_end,expected_buy,expected_sell,expected_cancels",
    [
        (
            "ACC001",
            "IBM",
            "BUY",
            dt.datetime(2025, 10, 26, 10, 21, 20, tzinfo=dt.timezone.utc),
            dt.datetime(2025, 10, 26, 10, 21, 28, tzinfo=dt.timezone.utc),
            15000,
            10000,
            3,
        ),
        (
            "ACC017",
            "AAPL",
            "BUY",
            dt.datetime(2025, 10, 26, 11, 5, 0, tzinfo=dt.timezone.utc),
            dt.datetime(2025, 10, 26, 11, 5, 6, tzinfo=dt.timezone.utc),
            12000,
            8000,
            3,
        ),
    ],
)
class TestDetectorSequences:
    def test_detect_sequences_for_group_main_patterns(
        self,
        account_id: str,
        product_id: str,
        expected_side: str,
        expected_start: dt.datetime,
        expected_end: dt.datetime,
        expected_buy: int,
        expected_sell: int,
        expected_cancels: int,
    ) -> None:
        events = _load_events()
        grouped = group_events_by_account_product(events)
        group_events = grouped[(account_id, product_id)]

        sequences = _detect_sequences_for_group(account_id, product_id, group_events)

        assert len(sequences) == 1
        seq = sequences[0]
        assert seq.account_id == account_id
        assert seq.product_id == product_id
        assert seq.side == expected_side
        assert seq.start_timestamp == expected_start
        assert seq.end_timestamp == expected_end
        assert seq.total_buy_qty == expected_buy
        assert seq.total_sell_qty == expected_sell
        assert seq.num_cancelled_orders == expected_cancels


class TestDetectorTopLevel:
    def test_detect_suspicious_sequences_returns_only_pattern_matches(self) -> None:
        events = _load_events()

        sequences = detect_suspicious_sequences(events)

        # Only ACC001/IBM and ACC017/AAPL follow the layering pattern in the sample data.
        assert len(sequences) == 2
        keys = {(s.account_id, s.product_id) for s in sequences}
        assert keys == {("ACC001", "IBM"), ("ACC017", "AAPL")}


class TestDetectorSyntheticPatterns:
    def test_synthetic_positive_pattern_for_new_account(self) -> None:
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)

        events = [
            # Three BUY orders within 10 seconds
            TransactionEvent(
                timestamp=base,
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price=Decimal("100.5"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price=Decimal("101.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Cancellations within 5 seconds of placement
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=3),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=4),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price=Decimal("100.5"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price=Decimal("101.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade within 2 seconds after last cancellation
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=6),
                account_id="ACC999",
                product_id="TSLA",
                side="SELL",
                price=Decimal("99.5"),
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        grouped = group_events_by_account_product(events)
        group_events = grouped[("ACC999", "TSLA")]

        sequences = _detect_sequences_for_group("ACC999", "TSLA", group_events)

        assert len(sequences) == 1
        seq = sequences[0]
        assert seq.account_id == "ACC999"
        assert seq.product_id == "TSLA"
        assert seq.side == "BUY"
        assert seq.start_timestamp == base
        assert seq.end_timestamp == base + dt.timedelta(seconds=6)
        # Spoof-side cancelled volume is on BUY, opposite-side executed on SELL
        assert seq.total_buy_qty == 3000
        assert seq.total_sell_qty == 5000
        assert seq.num_cancelled_orders == 3

    def test_synthetic_negative_pattern_trade_too_late(self) -> None:
        base = dt.datetime(2025, 1, 1, 9, 30, 0, tzinfo=dt.timezone.utc)

        events = [
            TransactionEvent(
                timestamp=base,
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price=Decimal("200.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price=Decimal("199.5"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price=Decimal("199.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=3),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price=Decimal("200.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=4),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price=Decimal("199.5"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price=Decimal("199.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade occurs 5 seconds after last cancellation (too late)
            TransactionEvent(
                timestamp=base + dt.timedelta(seconds=10),
                account_id="ACC888",
                product_id="NFLX",
                side="BUY",
                price=Decimal("201.0"),
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        sequences = detect_suspicious_sequences(events)
        # Trade is outside the 2-second window, so no detection should occur.
        assert sequences == []
