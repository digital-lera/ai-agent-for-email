import tempfile
import unittest
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from src.backend.models import DirectumResult, ExtractedData, MessageContext
from src.backend.process_message import _extract_data, _extract_text, run_chain


class FakeSocket:
    def __init__(self):
        self.events = []

    def emit(self, event, data=None):
        self.events.append((event, data))


class PipelineTests(unittest.TestCase):
    def test_pdf_email_extracts_only_pdf_text(self):
        with tempfile.TemporaryDirectory() as directory:
            context = MessageContext(
                subject="Subject",
                sender="sender@example.com",
                message_id="1",
                root_dir=Path(directory),
                raw_text="Текст письма и имя отправителя",
            )
            context.prepare()
            pdf = context.work_dir / "letter.pdf"
            pdf.write_bytes(b"pdf")
            context.attachments.append(pdf)
            context.pdf_attachments.append(pdf)

            def write_pdf_text(pdf_files, output_path, config):
                output_path.write_text("Только текст PDF", encoding="utf-8")

            with patch("src.scripts.pdf_parse.pdf_parse", side_effect=write_pdf_text):
                _extract_text({"context": context, "config": {}})

            self.assertEqual(
                context.extracted_text_path.read_text(encoding="utf-8"),
                "Только текст PDF",
            )

    def test_pdf_email_sends_only_pdf_attachment_names_to_ai(self):
        with tempfile.TemporaryDirectory() as directory:
            context = MessageContext(
                subject="Subject",
                sender="sender@example.com",
                message_id="1",
                root_dir=Path(directory),
            )
            context.prepare()
            pdf = context.work_dir / "letter.pdf"
            txt = context.work_dir / "note.txt"
            context.extracted_text_path.write_text("Только текст PDF", encoding="utf-8")
            context.attachments.extend([pdf, txt])
            context.pdf_attachments.append(pdf)

            extracted = ExtractedData.from_mapping({"content": "Текст"})
            fake_ai_module = ModuleType("src.scripts.ai_output_json")
            fake_ai_module.process_text_with_ai = unittest.mock.Mock(
                return_value=extracted
            )

            with patch.dict(
                sys.modules,
                {"src.scripts.ai_output_json": fake_ai_module},
            ):
                state = {"context": context}
                _extract_data(state)

            fake_ai_module.process_text_with_ai.assert_called_once_with(
                "Только текст PDF",
                context.processed_data_path,
                ["letter.pdf"],
            )
            self.assertEqual(state["extracted_data"], extracted)

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
