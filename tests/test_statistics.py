import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.backend.statistics import StatisticsStore


class StatisticsStoreTests(unittest.TestCase):
    def test_persists_daily_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "statistics.sqlite3"
            store = StatisticsStore(database_path)
            day = date(2026, 6, 15)

            store.increment("received", message_id="<one@example>", day=day)
            store.increment("successful", message_id="<one@example>", day=day)

            reopened = StatisticsStore(database_path)
            snapshot = reopened.get_day(day)

        self.assertEqual(snapshot.received, 1)
        self.assertEqual(snapshot.successful, 1)
        self.assertEqual(snapshot.partial, 0)
        self.assertEqual(snapshot.manual, 0)

    def test_same_message_and_counter_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StatisticsStore(Path(directory) / "statistics.sqlite3")
            day = date(2026, 6, 15)

            store.increment("received", message_id="<one@example>", day=day)
            snapshot = store.increment(
                "received",
                message_id="<one@example>",
                day=day,
            )

        self.assertEqual(snapshot.received, 1)

    def test_different_outcomes_have_separate_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StatisticsStore(Path(directory) / "statistics.sqlite3")
            day = date(2026, 6, 15)

            store.increment("successful", message_id="<one@example>", day=day)
            snapshot = store.increment(
                "partial",
                message_id="<two@example>",
                day=day,
            )

        self.assertEqual(snapshot.successful, 1)
        self.assertEqual(snapshot.partial, 1)

    def test_same_message_has_only_one_terminal_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StatisticsStore(Path(directory) / "statistics.sqlite3")
            day = date(2026, 6, 15)

            store.increment("successful", message_id="<one@example>", day=day)
            snapshot = store.increment(
                "partial",
                message_id="<one@example>",
                day=day,
            )

        self.assertEqual(snapshot.successful, 1)
        self.assertEqual(snapshot.partial, 0)


if __name__ == "__main__":
    unittest.main()
