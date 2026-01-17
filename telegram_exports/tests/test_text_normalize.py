import unittest

from tcpainfinder.text import build_text_pack


class TestTextNormalize(unittest.TestCase):
    def test_underscores_become_separators(self) -> None:
        pack = build_text_pack("#личный_помощник ищу помощника", lang="ru")
        self.assertIn("личный помощник", pack.normalized)

