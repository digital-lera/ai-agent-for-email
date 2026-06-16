import tempfile
import unittest
import json
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from src.backend.email_check import _process_one_message
from src.backend.models import PipelineResult


class FakeSocket:
    def __init__(self):
        self.events = []

    def emit(self, event, data=None):
        self.events.append((event, data))


class FakeImap:
    def __init__(self, raw_message):
        self.raw_message = raw_message

    def fetch(self, message_number, query):
        return "OK", [(b"1 (BODY[])", self.raw_message)]

    def store(self, message_number, operation, flags):
        return "OK", []


def pdf_email():
    message = EmailMessage()
    message["Subject"] = "PDF test"
    message["From"] = "sender@example.com"
    message["Message-ID"] = "<statistics-test@example.com>"
    message.set_content("Message body")
    message.add_attachment(
        b"%PDF-1.4 test",
        maintype="application",
        subtype="pdf",
        filename="letter.pdf",
    )
    return message.as_bytes()


def resume_email():
    message = EmailMessage()
    message["Subject"] = "Отклик на вакансию"
    message["From"] = "candidate@example.com"
    message["Message-ID"] = "<resume-test@example.com>"
    message.set_content("Добрый день, направляю CV.")
    message.add_attachment(
        b"resume",
        maintype="application",
        subtype="octet-stream",
        filename="резюме.docx",
    )
    return message.as_bytes()


class StatisticsLifecycleTests(unittest.TestCase):
    def run_message(self, pipeline_result, error_task_error=None):
        counters = []
        socket = FakeSocket()
        imap = FakeImap(pdf_email())

        def record_counter(socketio, counter, message_id):
            counters.append((counter, message_id))

        error_task_effect = error_task_error
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "src.backend.email_check.JOBS_DIR",
                    Path(directory),
                ),
                patch(
                    "src.backend.process_message.run_chain",
                    return_value=pipeline_result,
                ),
                patch(
                    "src.backend.email_check.increment_and_emit",
                    side_effect=record_counter,
                ),
                patch("src.backend.email_check._move_to_processed"),
                patch(
                    "src.backend.email_check.create_error_task",
                    side_effect=error_task_effect,
                ),
            ):
                _process_one_message(
                    imap,
                    b"1",
                    socket,
                    {"max_attachment_bytes": 1024},
                )

        return [counter for counter, _ in counters]

    def test_clean_completion_counts_successful(self):
        counters = self.run_message(
            PipelineResult(
                success=True,
                document_id=42,
                review_task_created=False,
            )
        )
        self.assertEqual(counters, ["received", "successful"])

    def test_review_task_completion_counts_partial(self):
        counters = self.run_message(
            PipelineResult(
                success=True,
                document_id=42,
                review_task_created=True,
            )
        )
        self.assertEqual(counters, ["received", "partial"])

    def test_pipeline_failure_with_error_task_counts_manual(self):
        counters = self.run_message(
            PipelineResult(success=False, error="OCR failed")
        )
        self.assertEqual(counters, ["received", "manual"])

    def test_failed_error_task_does_not_count_manual(self):
        counters = self.run_message(
            PipelineResult(success=False, error="OCR failed"),
            error_task_error=RuntimeError("Directum unavailable"),
        )
        self.assertEqual(counters, ["received"])

    def test_resume_rule_forwards_and_skips_pipeline(self):
        counters = []
        socket = FakeSocket()
        imap = FakeImap(resume_email())

        def record_counter(socketio, counter, message_id):
            counters.append((counter, message_id))

        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "rules.json"
            rules_path.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "name": "forward resume",
                                "when": {
                                    "attachment_name_contains_any": ["резюме", "CV"]
                                },
                                "actions": [
                                    {
                                        "type": "forward_email",
                                        "to": "MikhelAA@taif.ru",
                                    },
                                    {
                                        "type": "skip_directum",
                                        "reason": "resume",
                                    },
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch("src.backend.email_check.JOBS_DIR", Path(directory)),
                patch("src.backend.process_message.run_chain") as run_chain,
                patch(
                    "src.backend.email_check.forward_original_email",
                ) as forward_original_email,
                patch(
                    "src.backend.email_check.increment_and_emit",
                    side_effect=record_counter,
                ),
                patch("src.backend.email_check._move_to_processed"),
            ):
                _process_one_message(
                    imap,
                    b"1",
                    socket,
                    {
                        "max_attachment_bytes": 1024,
                        "directum_rules_path": str(rules_path),
                    },
                )

        run_chain.assert_not_called()
        forward_original_email.assert_called_once()
        self.assertEqual([counter for counter, _ in counters], ["received", "successful"])


if __name__ == "__main__":
    unittest.main()
