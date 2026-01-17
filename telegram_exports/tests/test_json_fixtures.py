import json
import unittest
from pathlib import Path

from tcpainfinder.models import AnalysisConfig
from tcpainfinder.telegram_json import load_export


class TestJsonFixtures(unittest.TestCase):
    def test_fixtures_intents_and_redaction(self) -> None:
        root = Path(__file__).parent / "fixtures"
        config = AnalysisConfig(since_days=100000, min_message_length=1, top_k=10)

        cases = [
            ("vacancy.json", "VACANCY_HIRE"),
            ("client_task_bot.json", "CLIENT_TASK"),
            ("service_offer.json", "SERVICE_OFFER"),
            ("spam.json", "SPAM_SCAM"),
        ]

        for filename, expected_intent in cases:
            with self.subTest(filename=filename):
                exp = load_export(root / filename, config=config)
                self.assertIsNotNone(exp)
                assert exp is not None
                self.assertEqual(exp.parsed_messages, 1)
                self.assertEqual(len(exp.messages), 1)
                self.assertEqual(exp.messages[0].intent, expected_intent)

        # Extra assertions for specific fixtures.
        exp = load_export(root / "client_task_bot.json", config=config)
        assert exp is not None
        self.assertIn("Google Sheets", exp.messages[0].text_raw)

        exp = load_export(root / "service_offer.json", config=config)
        assert exp is not None
        self.assertIn("[LINK]", exp.messages[0].text_redacted)
        self.assertIn("[MENTION]", exp.messages[0].text_redacted)

    def test_fixture_files_are_valid_json(self) -> None:
        root = Path(__file__).parent / "fixtures"
        for path in root.glob("*.json"):
            with self.subTest(path=str(path)):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn("messages", data)

