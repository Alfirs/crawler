import unittest

from tcpainfinder.detect import classify_intent
from tcpainfinder.text import build_text_pack


class TestIntentClassifier(unittest.TestCase):
    def _intent(self, text: str) -> str:
        pack = build_text_pack(text, lang="ru")
        return classify_intent(pack.redacted.lower(), pack.normalized).intent

    def test_vacancy_hire(self) -> None:
        text = "Ищу таргетолога в команду, оклад 50 000 руб/мес, отклик в лс"
        self.assertEqual(self._intent(text), "VACANCY_HIRE")

    def test_client_task_bot(self) -> None:
        text = "Нужно настроить телеграм бот: заявки -> Google Sheets. Кто может и сколько стоит?"
        self.assertEqual(self._intent(text), "CLIENT_TASK")

    def test_service_offer(self) -> None:
        text = "Привет! Меня зовут Иван, я делаю ботов и интеграции. Пишите в лс"
        self.assertEqual(self._intent(text), "SERVICE_OFFER")

    def test_spam(self) -> None:
        text = "Легкий заработок без опыта, доход от 5000₽ в день, пиши в лс"
        self.assertEqual(self._intent(text), "SPAM_SCAM")

    def test_offer_tie_break_like_client(self) -> None:
        text = "Помогу. Нужно подключить оплату (с рассрочками) на сайте или в чат-боте? Пишите в лс"
        self.assertEqual(self._intent(text), "SERVICE_OFFER")

    def test_vacancy_word_override(self) -> None:
        text = "Вакансия: тех специалист Telegram-бота. Срочно нужен специалист, условия обсудим в лс"
        self.assertEqual(self._intent(text), "VACANCY_HIRE")

