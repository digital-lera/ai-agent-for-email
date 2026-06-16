import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.scripts.pdf_parse import pdf_parse


class PdfParseTests(unittest.TestCase):
    def test_uses_embedded_text_without_initializing_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "letter.pdf"
            output_path = Path(directory) / "ocr.txt"
            pdf_path.write_bytes(b"%PDF fake")

            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="   Встроенный   текст PDF\nдля Directum   ",
                stderr="",
            )

            with (
                patch("src.scripts.pdf_parse.subprocess.run", return_value=completed),
                patch("src.scripts.pdf_parse._initialize_ocr") as initialize_ocr,
                patch("src.scripts.pdf_parse._convert_pdf_to_images") as convert_pdf,
            ):
                result = pdf_parse([pdf_path], output_path)
                output = output_path.read_text(encoding="utf-8")

            initialize_ocr.assert_not_called()
            convert_pdf.assert_not_called()
            self.assertEqual(result, ["=== letter.pdf ===\nВстроенный текст PDF\nдля Directum"])
            self.assertEqual(output, "=== letter.pdf ===\nВстроенный текст PDF\nдля Directum")

    def test_falls_back_to_ocr_when_embedded_text_is_missing(self):
        fake_image = Mock()
        fake_image.width = 100
        fake_image.height = 200

        fake_ocr = Mock()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        with tempfile.TemporaryDirectory() as directory:
            pdf_path = Path(directory) / "scan.pdf"
            output_path = Path(directory) / "ocr.txt"
            pdf_path.write_bytes(b"%PDF fake")

            with (
                patch("src.scripts.pdf_parse.subprocess.run", return_value=completed),
                patch(
                    "src.scripts.pdf_parse._load_ocr_settings",
                    return_value={
                        "workers": 0,
                        "confidence": 0.5,
                        "dpi": 200,
                        "heartbeat_seconds": 0,
                    },
                ),
                patch("src.scripts.pdf_parse._initialize_ocr", return_value=fake_ocr),
                patch("src.scripts.pdf_parse._convert_pdf_to_images", return_value=[fake_image]),
                patch(
                    "src.scripts.pdf_parse._read_page_with_heartbeat",
                    return_value=[(None, "OCR текст", 0.9)],
                ),
            ):
                result = pdf_parse([pdf_path], output_path)
                output = output_path.read_text(encoding="utf-8")

            fake_image.save.assert_called_once()
            self.assertEqual(result, ["=== scan.pdf ===\nOCR текст"])
            self.assertEqual(output, "=== scan.pdf ===\nOCR текст")


if __name__ == "__main__":
    unittest.main()
