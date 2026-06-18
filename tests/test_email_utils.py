import unittest
from email.message import EmailMessage

from src.backend.email_check import (
    _message_recipient_addresses,
    _unique_name,
    decode_filename,
    decode_mime_header,
    read_email_text,
)


class EmailUtilityTests(unittest.TestCase):
    def test_decodes_mime_header(self):
        self.assertEqual(
            decode_mime_header("=?utf-8?B?0KLQtdGB0YI=?="),
            "Тест",
        )

    def test_filename_cannot_escape_workspace(self):
        self.assertEqual(decode_filename("../../login.json"), "login.json")
        self.assertEqual(decode_filename(r"..\..\secret.pdf"), "secret.pdf")

    def test_duplicate_filenames_are_renamed(self):
        used = set()
        self.assertEqual(_unique_name("letter.pdf", used), "letter.pdf")
        self.assertEqual(_unique_name("letter.pdf", used), "letter-2.pdf")

    def test_plain_text_is_preferred_over_html(self):
        message = EmailMessage()
        message.set_content("plain body")
        message.add_alternative("<b>html body</b>", subtype="html")

        self.assertEqual(read_email_text(message), "plain body")

    def test_extracts_recipient_addresses_from_delivery_headers(self):
        message = EmailMessage()
        message["To"] = "Users <mailusers@taif.ru>"
        message["Cc"] = "Other <other@taif.ru>"
        message["X-Original-To"] = "original@taif.ru"

        self.assertEqual(
            _message_recipient_addresses(message),
            ("mailusers@taif.ru", "other@taif.ru", "original@taif.ru"),
        )


if __name__ == "__main__":
    unittest.main()
