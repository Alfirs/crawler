import unittest
from tcpainfinder.detect import classify_intent, compute_fit_for_me_score, IntentResult
from tcpainfinder.categorize import categorize_text
from tcpainfinder.models import AnalysisConfig, ChatMessage

# Mock for pipeline filtering logic since it's hard to import private functions
# We will duplicate the logic logic here slightly or import if possible.
# Actually we can import _filter_lead_candidate if we access protected member or just copy logic for unit testing "logic"

class TestFiltering(unittest.TestCase):
    def _create_msg(self, text, intent="CLIENT_TASK", fit=0.0, money=0.0, confidence=0.8):
        # Helper to create a dummy message
        return ChatMessage(
            chat_key="test", chat_name="Test", source_path=".", dt=None, author=None,
            text_raw=text, text_redacted=text, text_norm=text.lower(), tokens=[],
            intent=intent, intent_confidence=confidence, intent_tags=[],
            money_signal_score=money, fit_for_me_score=fit, category="Other"
        )

    def test_spam_detection(self):
        # Case: "18+ reviews"
        text = "Подработка для девушек 18+ лайки комментарии отзывы без опыта"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "SPAM_SCAM")
        
        # Case: "Investment"
        text = "Инвестиции в крипту, доход каждый день"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "SPAM_SCAM")

    def test_vacancy_detection(self):
        text = "Ищу ассистента в команду, график 5/2, зп 40000"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "VACANCY_HIRE")
        
        # "Looking for targetologist" -> Vacancy now
        text = "Ищу таргетолога для настройки рекламы"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "VACANCY_HIRE")

    def test_client_task_detection(self):
        text = "Нужно сделать бота под ключ для приема заявок, оплата 20к"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "CLIENT_TASK")
        
        # Check fit
        cat = categorize_text(text)
        fit = compute_fit_for_me_score(text, intent="CLIENT_TASK", category=cat)
        self.assertGreater(fit, 0.8)

    def test_offer_detection(self):
        text = "Я создаю чат-ботов под ключ. Пишите в лс. Портфолио в закрепе."
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "SERVICE_OFFER")

    def test_fit_score_not_me(self):
        # "SMM specialist needed" -> intent might be client task or vacancy, 
        # but if treated as client task, fit should be low
        text = "Нужен смм специалист для ведения сторис"
        res = classify_intent(text, text)
        # Even if classifier thinks it's a task (weakly), fit must be low
        fit = compute_fit_for_me_score(text, intent="CLIENT_TASK", category="Sales_CRM_Process")
        self.assertEqual(fit, 0.0, "Should reject SMM tasks")

    def test_fit_score_tech(self):
        text = "Нужна интеграция n8n с google sheets"
        res = classify_intent(text, text)
        fit = compute_fit_for_me_score(text, intent="CLIENT_TASK", category="Integrations_Sheets_CRM_n8n")
        self.assertGreater(fit, 0.9)

if __name__ == '__main__':
    unittest.main()
