"""
Lead Classification Service
Uses Gemini LLM for intelligent classification and scoring
"""
import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

# LLM Configuration
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"

# Classification categories
LEAD_TYPES = ["TASK", "VACANCY", "OFFER", "SPAM", "CHATTER"]
LEAD_CATEGORIES = [
    "Bots_TG_WA_VK",
    "Landing_Sites", 
    "Parsing_Analytics_Reports",
    "Integrations_Sheets_CRM_n8n",
    "Sales_CRM_Process",
    "Autoposting_ContentFactory",
    "Other"
]


def get_llm_client() -> OpenAI:
    """Get OpenAI client configured for Gemini"""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")
    
    return OpenAI(
        api_key=api_key,
        base_url=GEMINI_BASE_URL
    )


def classify_message(text: str, author: str = "", use_pro: bool = False) -> Dict[str, Any]:
    """
    Classify a message using Gemini
    Returns type, category, and scores
    """
    client = get_llm_client()
    model = PRO_MODEL if use_pro else FLASH_MODEL
    
    prompt = f"""Analyze this Telegram message and classify it.

MESSAGE:
Author: {author}
Text: {text}

Classify into:
1. TYPE: One of {LEAD_TYPES}
   - TASK: Someone looking for a service/developer to do work
   - VACANCY: Job posting or hiring
   - OFFER: Someone offering their services
   - SPAM: Advertising, scam, irrelevant
   - CHATTER: General discussion, not a lead

2. CATEGORY: One of {LEAD_CATEGORIES}
   Based on what service/skill is needed

3. SCORES (0.0 to 1.0):
   - fit_score: How well this matches automation/development services
   - money_score: Potential revenue (based on budget mentions, complexity)
   - confidence: How confident are you in this classification

Respond in JSON format only:
{{
    "type": "TASK",
    "category": "Bots_TG_WA_VK",
    "fit_score": 0.8,
    "money_score": 0.6,
    "confidence": 0.9,
    "reasoning": "Brief explanation"
}}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            
            # Validate and normalize
            result['type'] = result.get('type', 'CHATTER').upper()
            if result['type'] not in LEAD_TYPES:
                result['type'] = 'CHATTER'
            
            result['category'] = result.get('category', 'Other')
            if result['category'] not in LEAD_CATEGORIES:
                result['category'] = 'Other'
            
            # Clamp scores
            for key in ['fit_score', 'money_score', 'confidence']:
                result[key] = max(0.0, min(1.0, float(result.get(key, 0.5))))
            
            return result
        else:
            logger.warning(f"Could not parse LLM response: {content}")
            return get_default_classification()
            
    except Exception as e:
        logger.error(f"LLM classification error: {e}")
        return get_default_classification()


def get_default_classification() -> Dict[str, Any]:
    """Return default classification when LLM fails"""
    return {
        "type": "CHATTER",
        "category": "Other",
        "fit_score": 0.0,
        "money_score": 0.0,
        "confidence": 0.0,
        "reasoning": "Could not classify"
    }


def calculate_recency_score(message_date: Optional[datetime]) -> float:
    """
    Calculate recency score based on message date
    - Messages from today: 1.0
    - Messages from last week: 0.8-0.9
    - Messages from last month: 0.5-0.7
    - Older: 0.1-0.4
    """
    if not message_date:
        return 0.5
    
    now = datetime.utcnow()
    diff = now - message_date
    days = diff.days
    
    if days < 1:
        return 1.0
    elif days < 3:
        return 0.9
    elif days < 7:
        return 0.8
    elif days < 14:
        return 0.7
    elif days < 30:
        return 0.5
    elif days < 60:
        return 0.3
    else:
        return 0.1


def calculate_total_score(
    fit_score: float,
    money_score: float,
    recency_score: float,
    confidence: float
) -> float:
    """
    Calculate weighted total score
    Weights: fit=0.3, money=0.25, recency=0.25, confidence=0.2
    """
    weights = {
        'fit': 0.30,
        'money': 0.25,
        'recency': 0.25,
        'confidence': 0.20,
    }
    
    total = (
        fit_score * weights['fit'] +
        money_score * weights['money'] +
        recency_score * weights['recency'] +
        confidence * weights['confidence']
    )
    
    return round(total, 3)


def batch_classify_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Classify multiple messages with rate limiting
    Returns list of classifications with message references
    """
    results = []
    
    for msg in messages:
        text = msg.get('text', '')
        author = msg.get('author', '')
        msg_date = msg.get('date')
        
        # Skip very short messages
        if len(text) < 15:
            continue
        
        # Classify
        classification = classify_message(text, author)
        
        # Add recency score
        recency = calculate_recency_score(msg_date)
        classification['recency_score'] = recency
        
        # Calculate total score
        classification['total_score'] = calculate_total_score(
            classification['fit_score'],
            classification['money_score'],
            recency,
            classification['confidence']
        )
        
        # Add message reference
        classification['msg_id'] = msg.get('msg_id')
        classification['text'] = text
        classification['author'] = author
        classification['date'] = msg_date
        
        results.append(classification)
    
    return results


def quick_filter(text: str) -> Tuple[bool, str]:
    """
    Quick keyword-based filter before LLM classification
    Returns (is_potential_lead, likely_type)
    """
    text_lower = text.lower()
    
    # Spam indicators
    spam_keywords = [
        'заработок без вложений', 'пассивный доход', 'криптовалюта заработок',
        'казино', 'ставки', 'быстрые деньги', 'схема заработка',
        'mlm', 'пирамида', 'инвестиции с гарантией',
    ]
    if any(kw in text_lower for kw in spam_keywords):
        return False, "SPAM"
    
    # Task indicators (highest priority)
    task_keywords = [
        'ищу разработчика', 'нужен бот', 'требуется программист',
        'кто сделает', 'кто может сделать', 'нужна помощь с',
        'сколько стоит', 'бюджет', 'готов заплатить',
        'нужно автоматизировать', 'нужен парсер', 'нужен сайт',
        'ищу подрядчика', 'нужна интеграция', 'задача:',
    ]
    if any(kw in text_lower for kw in task_keywords):
        return True, "TASK"
    
    # Vacancy indicators
    vacancy_keywords = [
        'вакансия', 'ищем в команду', 'требуется на постоянную',
        'удаленная работа', 'зп от', 'оклад',
    ]
    if any(kw in text_lower for kw in vacancy_keywords):
        return True, "VACANCY"
    
    # General potential
    potential_keywords = [
        'бот', 'парсер', 'автоматизация', 'интеграция',
        'crm', 'bitrix', 'telegram', 'python', 'n8n',
    ]
    if any(kw in text_lower for kw in potential_keywords):
        return True, "CHATTER"  # Needs LLM classification
    
    return False, "CHATTER"
