import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.backend.models import DirectumResult, ExtractedData, MessageContext
from src.backend.process_message import run_chain


class FakeSocket:
    def __init__(self):
        self.events = []

    def emit(self, event, data=None):
        self.events.append((event, data))


class PipelineTests(unittest.TestCase):
    def test_failure_does_not_emit_chain_complete(self):
        socket = FakeSocket()
        with tempfile.TemporaryDirectory() as directory:
            context = MessageContext(
                subject="Subject",
                sender="sender@example.com",
                message_id="1",
                root_dir=Path(directory),
            )
            context.prepare()
            with patch(
                "src.backend.process_message._extract_text",
                side_effect=RuntimeError("OCR failed"),
            ):
                result = run_chain(socket, context, {})

        self.assertFalse(result.success)
        self.assertNotIn("chain_complete", [event for event, _ in socket.events])
        self.assertIn("error", [event for event, _ in socket.events])

    def test_success_emits_validated_data_and_completion(self):
        socket = FakeSocket()
        extracted = ExtractedData.from_mapping(
            {
                "content": "Текст",
                "correspondent": "",
                "dateFrom": "",
                "number": "",
                "signedBy": "",
                "recipient": "",
            }
        )

        def set_data(state):
            state["extracted_data"] = extracted

        def set_document(state):
            state["directum_result"] = DirectumResult(
                document_id=42,
                review_task_created=False,
            )

        with tempfile.TemporaryDirectory() as directory:
            context = MessageContext(
                subject="Subject",
                sender="sender@example.com",
                message_id="1",
                root_dir=Path(directory),
            )
            context.prepare()
            with (
                patch("src.backend.process_message._extract_text"),
                patch("src.backend.process_message._extract_data", side_effect=set_data),
                patch(
                    "src.backend.process_message._create_document",
                    side_effect=set_document,
                ),
            ):
                result = run_chain(socket, context, {})

        events = [event for event, _ in socket.events]
        self.assertTrue(result.success)
        self.assertFalse(result.review_task_created)
        self.assertIn("json_data_received", events)
        self.assertIn("chain_complete", events)
        self.assertNotIn("reset", events)


if __name__ == "__main__":
    unittest.main()
