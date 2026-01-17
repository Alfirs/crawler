"""
LLM Service for Message Generation and AI Coaching
Uses Google Gemini via OpenAI-compatible API
"""
import os
import json
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"


def get_client() -> OpenAI:
    """Get OpenAI client configured for Gemini"""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    
    return OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)


def should_use_pro(context: Dict[str, Any]) -> bool:
    """
    Decide whether to use Pro model based on context complexity
    """
    # Use Pro for:
    # - Objection handling
    # - Complex conversations (multiple exchanges)
    # - High-value leads
    # - Coach recommendations
    
    if context.get('has_objection', False):
        return True
    if context.get('conversation_length', 0) > 3:
        return True
    if context.get('money_score', 0) > 0.8:
        return True
    if context.get('task_type') in ['coach', 'objection', 'strategy']:
        return True
    
    return False


def generate_outreach_message(
    lead_text: str,
    lead_author: str,
    category: str,
    template: Optional[str] = None,
    offers: Optional[List[str]] = None,
    previous_messages: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate personalized outreach message for a lead
    Returns message text and metadata
    """
    client = get_client()
    context = context or {}
    model = PRO_MODEL if should_use_pro(context) else FLASH_MODEL
    
    # Build context for prompt
    offers_text = "\n".join(offers) if offers else "Автоматизация и разработка: боты, парсеры, интеграции, CRM"
    prev_text = "\n".join(previous_messages) if previous_messages else "Первое сообщение"
    
    prompt = f"""Ты - опытный продавец IT-услуг. Напиши персонализированное сообщение для потенциального клиента из Telegram.

КОНТЕКСТ ЛИДА:
Автор: {lead_author}
Сообщение: {lead_text}
Категория: {category}

МОИ УСЛУГИ:
{offers_text}

ПРЕДЫДУЩАЯ ПЕРЕПИСКА:
{prev_text}

{'ШАБЛОН ДЛЯ АДАПТАЦИИ: ' + template if template else ''}

ПРАВИЛА:
1. Сообщение должно быть коротким (2-4 предложения)
2. Персонализируй под конкретный запрос
3. Не используй шаблонные фразы типа "Добрый день! Увидел ваше сообщение..."
4. Покажи экспертизу, но не хвастайся
5. Задай уточняющий вопрос или предложи следующий шаг
6. Тон: дружелюбный, но профессиональный
7. НЕ используй эмодзи в избытке (максимум 1-2)
8. Добавь уникальности (цифры, кейсы, конкретику)

Ответь в JSON:
{{
    "message": "Текст сообщения",
    "hook": "Что именно зацепили в запросе",
    "next_step": "Предложенный следующий шаг",
    "personalization_points": ["Точка 1", "Точка 2"]
}}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            result['model_used'] = model
            return result
        else:
            return {
                "message": content,
                "hook": "",
                "next_step": "",
                "personalization_points": [],
                "model_used": model
            }
            
    except Exception as e:
        logger.error(f"Message generation error: {e}")
        return {
            "message": "",
            "error": str(e),
            "model_used": model
        }


def handle_objection(
    objection_text: str,
    lead_context: str,
    previous_attempts: List[str] = None
) -> Dict[str, Any]:
    """
    Generate response to client objection
    Always uses Pro model for better quality
    """
    client = get_client()
    
    prev_text = "\n".join(previous_attempts) if previous_attempts else "Нет предыдущих попыток"
    
    prompt = f"""Клиент выдвинул возражение. Помоги ответить.

КОНТЕКСТ:
{lead_context}

ВОЗРАЖЕНИЕ КЛИЕНТА:
{objection_text}

ПРЕДЫДУЩИЕ ОТВЕТЫ:
{prev_text}

Дай рекомендацию по работе с возражением и предложи вариант ответа.
Ответ должен:
1. Признать точку зрения клиента
2. Мягко переформулировать возражение
3. Дать ценность или аргумент
4. Предложить следующий шаг

JSON формат:
{{
    "objection_type": "цена/сроки/доверие/приоритет/другое",
    "response": "Текст ответа",
    "strategy": "Какую стратегию использовали",
    "alternative_responses": ["Вариант 2", "Вариант 3"],
    "tips": ["Совет 1", "Совет 2"]
}}"""

    try:
        response = client.chat.completions.create(
            model=PRO_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=1000,
        )
        
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{[\s\S]*\}', content)
        
        if json_match:
            return json.loads(json_match.group())
        else:
            return {"response": content, "objection_type": "unknown"}
            
    except Exception as e:
        logger.error(f"Objection handling error: {e}")
        return {"error": str(e)}


def get_sales_coach_advice(
    lead_info: Dict[str, Any],
    current_status: str,
    history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get AI Sales Coach recommendation for next action
    """
    client = get_client()
    
    history_text = json.dumps(history, ensure_ascii=False, indent=2) if history else "Нет истории"
    
    prompt = f"""Ты AI Sales Coach. Проанализируй лид и дай рекомендации.

ИНФОРМАЦИЯ О ЛИДЕ:
{json.dumps(lead_info, ensure_ascii=False, indent=2)}

ТЕКУЩИЙ СТАТУС: {current_status}

ИСТОРИЯ ВЗАИМОДЕЙСТВИЙ:
{history_text}

Дай краткие, actionable рекомендации:
1. Что делать дальше?
2. Какой подход использовать?
3. Какие риски учесть?
4. Оценка вероятности успеха

JSON:
{{
    "next_action": "Конкретное действие",
    "approach": "Рекомендуемый подход",
    "timing": "Когда лучше связаться",
    "risks": ["Риск 1"],
    "success_probability": 0.7,
    "one_liner_tip": "Короткий совет в одно предложение"
}}"""

    try:
        response = client.chat.completions.create(
            model=FLASH_MODEL,  # Coach can use Flash for speed
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=600,
        )
        
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{[\s\S]*\}', content)
        
        if json_match:
            return json.loads(json_match.group())
        else:
            return {"one_liner_tip": content}
            
    except Exception as e:
        logger.error(f"Coach advice error: {e}")
        return {"error": str(e)}


def generate_daily_summary(stats: Dict[str, Any]) -> str:
    """
    Generate end-of-day summary with AI insights
    """
    client = get_client()
    
    prompt = f"""Сгенерируй краткое (2-3 предложения) ежедневное резюме для пользователя CRM.

СТАТИСТИКА ДНЯ:
- Отправлено сообщений: {stats.get('messages_sent', 0)}
- Получено ответов: {stats.get('replies', 0)}
- Движений по воронке: {stats.get('funnel_moves', 0)}
- Новых лидов: {stats.get('new_leads', 0)}
- Закрыто сделок: {stats.get('won', 0)}

Резюме должно:
1. Похвалить за успехи или мягко мотивировать
2. Дать один конкретный совет на завтра
3. Быть позитивным, но не приторным

Ответь только текстом резюме, без JSON."""

    try:
        response = client.chat.completions.create(
            model=FLASH_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=200,
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        return f"Сегодня отправлено {stats.get('messages_sent', 0)} сообщений. Продолжай в том же духе! 💪"


def uniqualize_message(template: str, variations: int = 3) -> List[str]:
    """
    Generate unique variations of a message template
    For anti-spam protection
    """
    client = get_client()
    
    prompt = f"""Создай {variations} уникальных варианта этого сообщения.
Сохрани смысл, но измени структуру, слова, порядок.
Каждый вариант должен выглядеть как написанный вручную.

ОРИГИНАЛ:
{template}

Ответь JSON списком:
["Вариант 1", "Вариант 2", "Вариант 3"]"""

    try:
        response = client.chat.completions.create(
            model=FLASH_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=1000,
        )
        
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\[[\s\S]*\]', content)
        
        if json_match:
            return json.loads(json_match.group())
        else:
            return [template]
            
        return [template]

def test_connection() -> Dict[str, Any]:
    """Test Gemini API connection"""
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=FLASH_MODEL,
            messages=[{"role": "user", "content": "Say 'OK' if connection works"}],
            max_tokens=5
        )
        return {
            "status": "ok",
            "message": response.choices[0].message.content.strip(),
            "model": FLASH_MODEL
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
