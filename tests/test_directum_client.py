import json
import tempfile
import unittest
from pathlib import Path

import requests

from src.backend.models import ExtractedData
from src.scripts.directum import DirectumClient, SUCCESS_TASK_TEXT, find_fuzzy_id


def response(payload, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode("utf-8")
    return result


class FakeSession:
    def __init__(self):
        self.calls = []
        self.auth = None
        self.verify = None
        self.version_id = 10

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/IIncomingLetters"):
            return response({"Id": 42})
        if url.endswith("/Versions"):
            self.version_id += 1
            return response({"Id": self.version_id})
        if url.endswith("/Docflow/CreateSimpleTask"):
            return response(77)
        return response({})


class LookupSession(FakeSession):
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/IContacts"):
            return response({"value": [{"Id": 10, "Name": "Иванов Иван Иванович"}]})
        if url.endswith("/IEmployees"):
            return response({"value": [{"Id": 20, "Name": "Петров Петр Петрович"}]})
        if url.endswith("/ICounterparties"):
            return response({"value": [{"Id": 30, "Name": "ООО Ромашка"}]})
        if url.endswith("/IIncomingLetters"):
            return response({"Id": 42})
        if url.endswith("/Docflow/CreateSimpleTask"):
            return response(77)
        return response({})


class DirectumClientTests(unittest.TestCase):
    def test_from_config_uses_directum_username(self):
        client = DirectumClient.from_config(
            {
                "username": "email-user",
                "directum-username": "directum-user",
                "password": "directum-password",
                "odataurl": "https://directum.example",
                "performer_id": 1,
                "directum_rules_path": "/tmp/missing-directum-rules.json",
            }
        )

        self.assertEqual(client.auth, ("directum-user", "directum-password"))
        self.assertEqual(client.session.auth, ("directum-user", "directum-password"))

    def test_fuzzy_person_lookup_returns_original_item_id(self):
        item_id = find_fuzzy_id(
            [
                {"Id": 5, "Name": "Иванов Андрей Петрович"},
                {"Id": 8, "Name": "Петров Борис Иванович"},
            ],
            "Иванов А",
            is_person=True,
        )
        self.assertEqual(item_id, 5)

    def test_empty_json_fields_make_result_partial(self):
        session = FakeSession()
        client = DirectumClient(
            base_url="https://directum.example",
            auth=("user", "password"),
            performer_id=1,
            session=session,
        )
        data = ExtractedData.from_mapping(
            {
                "content": "Текст",
                "correspondent": "",
                "dateFrom": "16.06.2026",
                "number": "123-4",
                "signedBy": "",
                "recipient": "",
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.pdf"
            second = Path(directory) / "second.pdf"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            result = client.create_incoming_letter(data, [first, second])

        self.assertEqual(result.document_id, 42)
        self.assertTrue(result.review_task_created)
        self.assertFalse(session.verify)
        self.assertTrue(all(call[2]["verify"] is False for call in session.calls))
        letter_payload = session.calls[0][2]["json"]
        self.assertNotIn("Correspondent@odata.bind", letter_payload)
        self.assertNotIn("SignedBy@odata.bind", letter_payload)
        self.assertNotIn("Addressee@odata.bind", letter_payload)
        put_calls = [call for call in session.calls if call[0] == "PUT"]
        self.assertEqual(len(put_calls), 2)
        self.assertEqual(
            [call[2]["data"] for call in put_calls],
            [b"first", b"second"],
        )
        task_calls = [
            call
            for call in session.calls
            if call[1].endswith("/Docflow/CreateSimpleTask")
        ]
        self.assertEqual(len(task_calls), 1)
        self.assertIn(
            "Некоторые данные письма требуют ручной проверки",
            task_calls[0][2]["json"]["text"],
        )
        self.assertNotEqual(task_calls[0][2]["json"]["text"], SUCCESS_TASK_TEXT)
        self.assertEqual(task_calls[0][2]["json"]["documentIds"], [42])
        start_calls = [
            call
            for call in session.calls
            if call[1].endswith("/Docflow/StartTask")
        ]
        self.assertEqual(len(start_calls), 1)
        self.assertEqual(start_calls[0][2]["json"], {"taskId": 77})

    def test_complete_json_fields_create_success_task(self):
        session = LookupSession()
        client = DirectumClient(
            base_url="https://directum.example",
            auth=("user", "password"),
            performer_id=1,
            session=session,
        )
        data = ExtractedData.from_mapping(
            {
                "content": "Текст",
                "correspondent": "ООО Ромашка",
                "dateFrom": "16.06.2026",
                "number": "123-4",
                "signedBy": "Иванов И",
                "recipient": "Петров П",
            }
        )

        result = client.create_incoming_letter(data, [])

        self.assertFalse(result.review_task_created)
        letter_payloads = [
            call[2]["json"]
            for call in session.calls
            if call[1].endswith("/IIncomingLetters")
        ]
        self.assertEqual(len(letter_payloads), 1)
        self.assertEqual(letter_payloads[0]["InNumber"], "123-4")
        self.assertEqual(letter_payloads[0]["Dated"], "2026-06-16")
        self.assertIn("Correspondent@odata.bind", letter_payloads[0])
        self.assertIn("SignedBy@odata.bind", letter_payloads[0])
        self.assertIn("Addressee@odata.bind", letter_payloads[0])
        task_payloads = [
            call[2]["json"]
            for call in session.calls
            if call[1].endswith("/Docflow/CreateSimpleTask")
        ]
        self.assertEqual(len(task_payloads), 1)
        self.assertEqual(task_payloads[0]["text"], SUCCESS_TASK_TEXT)

    def test_reports_review_task_creation(self):
        session = FakeSession()
        client = DirectumClient(
            base_url="https://directum.example",
            auth=("user", "password"),
            performer_id=1,
            session=session,
        )
        data = ExtractedData.from_mapping(
            {
                "content": "Текст",
                "correspondent": "Неизвестная компания",
                "dateFrom": "",
                "number": "",
                "signedBy": "",
                "recipient": "",
            }
        )

        result = client.create_incoming_letter(data, [])

        self.assertTrue(result.review_task_created)
        self.assertTrue(
            any(
                call[1].endswith("/Docflow/CreateSimpleTask")
                for call in session.calls
            )
        )
        start_calls = [
            call
            for call in session.calls
            if call[1].endswith("/Docflow/StartTask")
        ]
        self.assertEqual(len(start_calls), 1)
        self.assertEqual(start_calls[0][2]["json"], {"taskId": 77})
        self.assertIs(start_calls[0][2]["verify"], False)
        task_payloads = [
            call[2]["json"]
            for call in session.calls
            if call[1].endswith("/Docflow/CreateSimpleTask")
        ]
        self.assertEqual(len(task_payloads), 1)
        self.assertIn("Некоторые данные письма требуют ручной проверки", task_payloads[0]["text"])
        self.assertNotEqual(task_payloads[0]["text"], SUCCESS_TASK_TEXT)

    def test_extracts_task_id_from_wrapped_response(self):
        self.assertEqual(
            DirectumClient._extract_task_id(response({"value": "81"})),
            81,
        )


if __name__ == "__main__":
    unittest.main()
