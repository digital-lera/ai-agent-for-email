import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import requests

from src.backend.directum_rules import (
    DirectumIds,
    apply_email_rules,
    apply_id_rules,
    apply_sender_rules,
    load_directum_rules,
)
from src.backend.models import ExtractedData, MessageContext
from src.scripts.directum import DirectumClient


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

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/IIncomingLetters"):
            return response({"Id": 42})
        if url.endswith("/Docflow/CreateSimpleTask"):
            return response(77)
        return response({})


class DirectumRuleTests(unittest.TestCase):
    def test_loads_enabled_rules_from_json_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(
                """
                {
                  "rules": [
                    {"name": "active", "when": {"any_id": 1}, "actions": []},
                    {
                      "name": "disabled",
                      "enabled": false,
                      "when": {"any_id": 2},
                      "actions": []
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            rules = load_directum_rules({"directum_rules_path": str(path)})

        self.assertEqual([rule["name"] for rule in rules], ["active"])

    def test_sender_rule_skips_directum_case_insensitively(self):
        rules = [
            {
                "name": "skip sender",
                "when": {"sender_email": "KalmykovaRR@taif.ru"},
                "actions": [{"type": "skip_directum", "reason": "excluded"}],
            }
        ]

        decision = apply_sender_rules(rules, "Kalmykova <kalmykovarr@taif.ru>")

        self.assertTrue(decision.skip_directum)
        self.assertEqual(decision.reason, "excluded")

    def test_email_rule_fuzzy_matches_resume_text(self):
        rules = [
            {
                "name": "forward candidate letters",
                "when": {"text_contains_any": ["кандидат"]},
                "actions": [
                    {"type": "forward_email", "to": "MikhelAA@taif.ru"},
                    {"type": "skip_directum", "reason": "forwarded"},
                ],
            }
        ]

        decision = apply_email_rules(
            rules,
            sender="sender@example.com",
            subject="Отклик",
            body="Добрый день, направляем кандитат на рассмотрение.",
        )

        self.assertTrue(decision.skip_directum)
        self.assertEqual(decision.forward_to, ("MikhelAA@taif.ru",))

    def test_email_rule_matches_resume_attachment_stem(self):
        rules = [
            {
                "name": "forward resume attachment",
                "when": {"attachment_name_contains_any": ["резюме", "CV"]},
                "actions": [
                    {"type": "forward_email", "to": "MikhelAA@taif.ru"},
                    {"type": "skip_directum", "reason": "forwarded"},
                ],
            }
        ]

        decision = apply_email_rules(
            rules,
            sender="sender@example.com",
            attachment_names=("CV_Ivanov.docx",),
        )

        self.assertTrue(decision.skip_directum)
        self.assertEqual(decision.forward_to, ("MikhelAA@taif.ru",))

    def test_any_id_rule_replaces_only_matching_fields(self):
        rules = [
            {
                "name": "replace 807",
                "when": {"any_id": 807},
                "actions": [{"type": "replace_matched_id", "id": 582}],
            }
        ]

        decision = apply_id_rules(
            rules,
            DirectumIds(signed_by_id=807, recipient_id=608, counterparty_id=-1),
        )
        ids = decision.apply_to_ids(
            DirectumIds(signed_by_id=807, recipient_id=608, counterparty_id=-1)
        )

        self.assertEqual(ids.signed_by_id, 582)
        self.assertEqual(ids.recipient_id, 608)

    def test_directum_client_uses_rewritten_ids_in_payload(self):
        session = FakeSession()
        client = DirectumClient(
            base_url="https://directum.example",
            auth=("user", "password"),
            performer_id=1,
            session=session,
            rules=[
                {
                    "name": "replace 807",
                    "when": {"any_id": 807},
                    "actions": [{"type": "replace_matched_id", "id": 582}],
                }
            ],
        )
        client._lookup = lambda entity, name, is_person=False: {
            "IContacts": 807,
            "IEmployees": 7,
            "ICounterparties": -1,
        }[entity]
        data = ExtractedData.from_mapping(
            {
                "content": "Текст",
                "correspondent": "",
                "dateFrom": "",
                "number": "",
                "signedBy": "Иванов И",
                "recipient": "Петров П",
            }
        )

        client.create_incoming_letter(data, [])

        payload = session.calls[0][2]["json"]
        self.assertEqual(
            payload["SignedBy@odata.bind"],
            "https://directum.example/IContacts(582)",
        )
        self.assertEqual(
            payload["Addressee@odata.bind"],
            "https://directum.example/IEmployees(7)",
        )

    def test_directum_client_can_forward_and_skip_by_recipient_id(self):
        session = FakeSession()
        client = DirectumClient(
            base_url="https://directum.example",
            auth=("user", "password"),
            performer_id=1,
            session=session,
            config={"smtp_server": "smtp.example"},
            rules=[
                {
                    "name": "forward 608",
                    "when": {"recipient_id": 608},
                    "actions": [
                        {"type": "forward_email", "to": "StryginaVM@taif.ru"},
                        {"type": "skip_directum", "reason": "forwarded"},
                    ],
                }
            ],
        )
        client._lookup = lambda entity, name, is_person=False: {
            "IContacts": -1,
            "IEmployees": 608,
            "ICounterparties": -1,
        }[entity]
        context = MessageContext(
            subject="Subject",
            sender="sender@example.com",
            message_id="1",
            root_dir=Path(tempfile.gettempdir()),
            raw_message=b"raw",
        )
        data = ExtractedData.from_mapping(
            {
                "content": "Текст",
                "correspondent": "",
                "dateFrom": "",
                "number": "",
                "signedBy": "",
                "recipient": "Петров П",
            }
        )

        with patch("src.scripts.directum.forward_original_email") as forward:
            result = client.create_incoming_letter(data, [], context=context)

        self.assertTrue(result.skipped_directum)
        self.assertTrue(result.forwarded_to_recipient)
        self.assertIsNone(result.document_id)
        forward.assert_called_once()
        self.assertFalse(
            any(call[1].endswith("/IIncomingLetters") for call in session.calls)
        )


if __name__ == "__main__":
    unittest.main()
