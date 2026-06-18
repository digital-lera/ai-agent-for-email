import unittest
import sys
from types import ModuleType


fake_ollama = ModuleType("ollama")
fake_ollama.Client = object
sys.modules.setdefault("ollama", fake_ollama)

from src.scripts.ai_output_json import _build_preprocessing_request


class AiOutputJsonTests(unittest.TestCase):
    def test_preprocessing_request_contains_email_text(self):
        request = _build_preprocessing_request(
            "Промпт",
            "Текст письма из PDF и тела email",
            "letter.pdf",
        )

        self.assertIn("Промпт", request)
        self.assertIn("ИМЕНА ВЛОЖЕНИЙ:\nletter.pdf", request)
        self.assertIn("<<<BEGIN_EMAIL>>>", request)
        self.assertIn("Текст письма из PDF и тела email", request)
        self.assertIn("<<<END_EMAIL>>>", request)


if __name__ == "__main__":
    unittest.main()
