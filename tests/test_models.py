import unittest

from src.backend.models import ExtractedData, ValidationError


class ExtractedDataTests(unittest.TestCase):
    def test_accepts_valid_payload(self):
        data = ExtractedData.from_mapping(
            {
                "content": "Краткое содержание",
                "correspondent": "ООО Тест",
                "dateFrom": "15.06.2026",
                "number": "123-4",
                "signedBy": "Иванов А",
                "recipient": "Петров Б",
            }
        )

        self.assertEqual(data.number, "123-4")
        self.assertEqual(data.to_dict()["dateFrom"], "15.06.2026")

    def test_rejects_invalid_date(self):
        with self.assertRaises(ValidationError):
            ExtractedData.from_mapping(
                {
                    "content": "Текст",
                    "correspondent": "",
                    "dateFrom": "2026-06-15",
                    "number": "",
                    "signedBy": "",
                    "recipient": "",
                }
            )

    def test_missing_optional_fields_become_empty_strings(self):
        data = ExtractedData.from_mapping({"content": "Текст"})

        self.assertEqual(
            data.to_dict(),
            {
                "content": "Текст",
                "correspondent": "",
                "dateFrom": "",
                "number": "",
                "signedBy": "",
                "recipient": "",
            },
        )

    def test_rejects_non_json_model_output(self):
        with self.assertRaises(ValidationError):
            ExtractedData.from_json("not json")

    def test_accepts_json_code_fence(self):
        data = ExtractedData.from_json(
            """```json
            {
              "content": "Текст",
              "correspondent": "",
              "dateFrom": "",
              "number": "",
              "signedBy": "",
              "recipient": ""
            }
            ```"""
        )
        self.assertEqual(data.content, "Текст")


if __name__ == "__main__":
    unittest.main()
