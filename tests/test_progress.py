import tempfile
import unittest
from pathlib import Path

from src.backend.progress import ProgressStore


class ProgressStoreTests(unittest.TestCase):
    def test_persists_current_progress_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "progress.sqlite3"
            store = ProgressStore(database_path)

            store.start_email(job_id="job-1", subject="Тема", sender="sender@example.com")
            store.set_stage("text_parse", "in-process")
            store.update({"filename": "letter.pdf"})

            restored = ProgressStore(database_path).get()

        self.assertEqual(restored["job_id"], "job-1")
        self.assertEqual(restored["subject"], "Тема")
        self.assertEqual(restored["filename"], "letter.pdf")
        self.assertEqual(restored["stages"]["text_parse"], "in-process")

    def test_reset_does_not_clear_newer_job(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProgressStore(Path(directory) / "progress.sqlite3")
            store.start_email(job_id="old-job", subject="Old", sender="old@example.com")
            store.start_email(job_id="new-job", subject="New", sender="new@example.com")

            snapshot = store.reset(job_id="old-job")

        self.assertEqual(snapshot["job_id"], "new-job")
        self.assertEqual(snapshot["status"], "running")


if __name__ == "__main__":
    unittest.main()
