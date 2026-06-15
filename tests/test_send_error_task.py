import unittest
from unittest.mock import patch

from src.scripts.send_error_task import create_error_task


class FakeDirectumClient:
    performer_id = 15

    def __init__(self):
        self.payload = None

    def create_and_start_simple_task(self, payload):
        self.payload = payload
        return 91


class SendErrorTaskTests(unittest.TestCase):
    def test_creates_and_starts_error_task(self):
        client = FakeDirectumClient()
        with patch(
            "src.scripts.send_error_task.DirectumClient.from_config",
            return_value=client,
        ) as from_config:
            task_id = create_error_task(
                "Тема письма",
                "sender@example.com",
                "Ошибка распознавания",
                {"odataurl": "https://directum.example"},
            )

        self.assertEqual(task_id, 91)
        from_config.assert_called_once()
        self.assertEqual(client.payload["performerIds"], [15])
        self.assertEqual(client.payload["observerIds"], [15])
        self.assertIn("Ошибка распознавания", client.payload["text"])


if __name__ == "__main__":
    unittest.main()
