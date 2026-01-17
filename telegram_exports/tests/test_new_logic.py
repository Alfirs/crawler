import unittest
from tcpainfinder.detect import classify_intent, compute_fit_for_me_score
from tcpainfinder.categorize import categorize_text

class TestNewLogic(unittest.TestCase):
    def test_vacancy_detection(self):
        text = "Ищу таргетолога в команду, зп 50к."
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "VACANCY_HIRE", f"Should be VACANCY: {text}")

        text = "Нужен менеджер по продажам, график 5/2"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "VACANCY_HIRE")
        
        # Difficult case: "Need targetologist" (without salary/schedule)
        text = "Ищу таргетолога"
        res = classify_intent(text, text)
        # Even if it looks like a task, fit should be zero.
        # But our new logic promotes "looking for <Role>" to Vacancy.
        self.assertEqual(res.intent, "VACANCY_HIRE")

    def test_client_task_fit(self):
        text = "Нужно сделать бота для приема заявок"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "CLIENT_TASK")
        cat = categorize_text(text)
        self.assertEqual(cat, "Bots_TG_WA_VK")
        fit = compute_fit_for_me_score(text, intent="CLIENT_TASK", category=cat)
        self.assertGreater(fit, 0.8)

    def test_client_task_low_fit(self):
        # User doesn't want design
        text = "Нужно сделать дизайн лендинга, нарисовать баннер"
        res = classify_intent(text, text)
        # Maybe client task
        if res.intent == "CLIENT_TASK":
            cat = categorize_text(text)
            # Should match Design
            self.assertEqual(cat, "Design_Copy")
            # Fit should be 0 because category Design_Copy is 0.0 base
            fit = compute_fit_for_me_score(text, intent="CLIENT_TASK", category=cat)
            self.assertLess(fit, 0.2)

    def test_client_task_low_fit_target(self):
        # User doesn't want target
        text = "Нужно настроить таргет в вк"
        res = classify_intent(text, text)
        cat = categorize_text(text) # likely Other or maybe Integration if it matches something
        fit = compute_fit_for_me_score(text, intent=res.intent, category=cat)
        # Should be penalized heavily
        self.assertLess(fit, 0.2)

    def test_spam(self):
        text = "Легкий заработок на телефоне без опыта"
        res = classify_intent(text, text)
        self.assertEqual(res.intent, "SPAM_SCAM")

    def test_category_bots(self):
        text = "Нужен бот для телеграм"
        cat = categorize_text(text)
        self.assertEqual(cat, "Bots_TG_WA_VK")

    def test_category_integration(self):
        text = "Нужна интеграция n8n с google sheets"
        cat = categorize_text(text)
        self.assertEqual(cat, "Integrations_Sheets_CRM_n8n")

if __name__ == '__main__':
    unittest.main()
