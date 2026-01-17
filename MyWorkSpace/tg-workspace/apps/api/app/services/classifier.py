"""
Lead Classification Service
Enhanced with pattern-based detection for freelancer lead identification
"""
import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

# LLM Configuration
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-2.5-pro"

# Classification types
LEAD_TYPES = ["TASK", "VACANCY", "OFFER", "SPAM", "CHATTER"]
LEAD_CATEGORIES = [
    "Bots_TG_WA_VK",
    "Integrations_Sheets_CRM_n8n",
    "Autoposting_ContentFactory",
    "Parsing_Analytics_Reports",
    "Landing_Sites",
    "Sales_CRM_Process",
    "Design_Copy",
    "Other"
]


# ============================================================================
# PATTERN-BASED DETECTION (adapted from tcpainfinder)
# ============================================================================

# Budget detection
_BUDGET_RE = re.compile(
    r"(?i)(?:\b(\d{1,3}(?:[ \u00A0]\d{3})+|\d{4,6})\s*(?:₽|руб\.?|р\.?|rub)\b)|(?:\b(\d{1,3})\s*(?:к|k)\b)"
)

# Vacancy role patterns
_VACANCY_ROLES = (
    r"таргетолог\w*|smm|смм|маркетолог\w*|трафиколог\w*|медиабайер\w*|байер\w*|"
    r"менеджер\w*|моп\b|ассистент\w*|помощник\w*|оператор\w*|куратор\w*|"
    r"проджект\w*|project|продюсер\w*|аккаунт\w*|"
    r"дизайнер\w*|копирайтер\w*|редактор\w*|переводчик\w*|"
    r"сторисмейкер\w*|рилсмейкер\w*|контент[-\s]?менеджер\w*|креатор\w*|"
    r"монтаж[её]р\w*|видеомонтаж[её]р\w*|видеограф\w*|"
    r"аналитик\w*|методист\w*|преподавател\w*|hr\b|эйчар\w*|рекрутер\w*"
)

_VACANCY_ROLE_RE = re.compile(rf"(?i)\b({_VACANCY_ROLES})\b")
_HIRE_VERB_RE = re.compile(r"(?i)\b(ищу|ищем|нужн(о|а|ы|ен)|требуетс\w*|ваканс\w*|нанима\w*)\b")
_VACANCY_CONTEXT_RE = re.compile(
    r"(?i)\b(обязанност\w*|требован\w*|услови\w*|график\w*|занятост\w*|"
    r"зп|зарплат\w*|оклад\w*|ставка\w*|процент\w*|"
    r"испытатель\w*|оформлен\w*|трудоустро\w*|собеседован\w*|резюме\w*|отклик\w*|анкет\w*)\b"
)

# "Looking for <Role>" pattern
_VACANCY_LOOKING_ROLE_RE = re.compile(
    rf"(?i)\b(ищу|ищем|нужн(о|а|ы|ен)|требуетс\w*|ваканс\w*|нанима\w*)\b(?:\s+\w+){{0,6}}\s+({_VACANCY_ROLES})\b"
)

# Tech keywords - these indicate automation/development tasks
_TECH_HINT_RE = re.compile(
    r"(?i)\b(автоматизац\w*|автоматизир\w*|бот\w*|чат[-\s]?бот\w*|telegram\s+bot|телеграм\s+бот|"
    r"aiogram|salebot|manychat|"
    r"n8n|make|integromat|webhook|api|"
    r"google\s+sheets|sheets|crm|amocrm|bitrix|битрикс\w*|notion|"
    r"парсинг|спарс\w*|выгруз\w*|scrap\w*|скрейп\w*|"
    r"отчет\w*|отч[её]т\w*|метрик\w*|дашборд\w*|"
    r"автопост\w*|контент[-\s]?завод\w*|"
    r"лендинг\w*|сайт\w*|wordpress|tilda|taplink|квиз\w*|"
    r"getcourse|геткурс\w*|prodamus|продамус\w*|senler|сенлер\w*)\b"
)

# Non-tech roles (kill fit score)
_NEGATIVE_NOT_ME_RE = re.compile(
    r"(?i)\b(таргет\w*|smm|смм|ведение\w*|контент[-\s]?менеджер\w*|дизайн\w*|копирайт\w*|"
    r"монтаж[её]р\w*|логотип\w*|баннер\w*|сторисмейкер\w*|рилсмейкер\w*|креатор\w*|"
    r"методолог\w*|методист\w*|юрист\w*|адвокат\w*|"
    r"3d\b|рендер\w*|визуализатор\w*|визуал\w*)\b"
)

# Marketing integration (not tech)
_MARKETING_INTEGRATION_RE = re.compile(
    r"(?i)\bинтеграц\w*\b.*\b(блогер\w*|канал\w*|реклам\w*|посев\w*|закуп\w*|размещен\w*)\b"
    r"|\b(блогер\w*|канал\w*|реклам\w*|посев\w*|закуп\w*|размещен\w*)\b.*\bинтеграц\w*\b"
)


# Intent patterns with weights
_VACANCY_PATTERNS: Tuple[Tuple[str, re.Pattern, float], ...] = (
    ("vacancy:word", re.compile(r"(?i)\b(ваканс\w*|vacancy)\b"), 6.0),
    ("vacancy:in_team", re.compile(r"(?i)\bв\s+команду\b"), 2.2),
    ("vacancy:in_staff", re.compile(r"(?i)\bв\s+штат\b"), 2.5),
    ("vacancy:hire", re.compile(r"(?i)\bнанима\w*\b|\bнайм\b|\bhiring\b"), 2.0),
    ("vacancy:resume", re.compile(r"(?i)\bрезюме\b|\bcv\b"), 1.8),
    ("vacancy:apply", re.compile(r"(?i)\bотклик\w*\b|\bзаполни\w*\s+анкет\w*"), 1.5),
    ("vacancy:conditions", re.compile(r"(?i)\b(обязанност\w*|требован\w*|услови\w*|график\w*|занятост\w*|зп|зарплат\w*|оклад\w*)\b"), 1.6),
)

_SERVICE_OFFER_PATTERNS: Tuple[Tuple[str, re.Pattern, float], ...] = (
    ("offer:help_start", re.compile(r"(?i)^\s*помог(у|аю)\b"), 3.5),
    ("offer:help_word", re.compile(r"(?i)\bпомог(у|аю)\b"), 2.5),
    ("offer:services", re.compile(r"(?i)\b(предлагаю|оказываю)\s+услуг\w*\b"), 2.5),
    ("offer:i_do", re.compile(r"(?i)\bя\s+(делаю|создаю|настраиваю|разрабатываю|собираю|помогаю|веду)\b"), 2.2),
    ("offer:portfolio", re.compile(r"(?i)\bпортфолио\b|\bкейсы?\b"), 2.2),
    ("offer:take_projects", re.compile(r"(?i)\b(беру|возьму)\s+(в\s+работу|проект\w*|клиент\w*)\b"), 2.5),
    ("offer:job_seeker", re.compile(r"(?i)\b(ищу\s+работ\w*|в\s+поиске\s+работ\w*|ищу\s+подработ\w*|ищу\s+заказ\w*)\b"), 2.0),
)

_SPAM_PATTERNS: Tuple[Tuple[str, re.Pattern, float], ...] = (
    ("spam:easy_money", re.compile(r"(?i)\b(легк(ий|ая)\s+заработок|заработа(й|ть)\s+на\s+телефоне|без\s+опыта|доход\s+от)\b"), 4.0),
    ("spam:referral", re.compile(r"(?i)\b(ссылка\s+в\s+профиле|переходи\s+по\s+ссылке)\b"), 2.0),
    ("spam:invest", re.compile(r"(?i)\b(инвестици\w*|крипт\w*|форекс|арбитраж|ставки)\b"), 2.5),
    ("spam:guarantee", re.compile(r"(?i)\b(гарантирую|100%|без\s+вложени\w*)\b"), 2.5),
)

_CLIENT_TASK_PATTERNS: Tuple[Tuple[str, re.Pattern, float], ...] = (
    ("client:need", re.compile(r"(?i)\b(нужн(о|а|ы|ен)|надо|требуетс\w*)\b"), 1.2),
    ("client:do", re.compile(r"(?i)\b(сделать|сделайте|настроить|собрать|подключить|интегрир|автоматизир|спарс|выгруз)\w*"), 1.6),
    ("client:who_can", re.compile(r"(?i)\bкто\s+может\b|\bкто\s+сделает\b|\bкто\s+умеет\b"), 1.6),
    ("client:looking", re.compile(r"(?i)\b(ищу|нужен)\s+(исполнителя|специалиста|разработчика|прогера|кодера)\b"), 1.8),
    ("client:price", re.compile(r"(?i)\b(сколько\s+стоит|цена|стоимость|бюджет|оплата)\b"), 1.1),
    ("client:urgency", re.compile(r"(?i)\b(срочно|сегодня|завтра|горит)\b"), 1.3),
)


# Category patterns
_CATEGORY_RULES: Dict[str, Tuple[Tuple[str, re.Pattern, float], ...]] = {
    "Bots_TG_WA_VK": (
        ("bot_word", re.compile(r"(?i)\bбот\w*\b"), 2.2),
        ("chatbot", re.compile(r"(?i)\bчат[-\s]?бот\w*\b"), 3.0),
        ("telegram_bot", re.compile(r"(?i)\b(telegram\s+bot|телеграм\s+бот|tg\s*бот)\b"), 3.5),
        ("aiogram", re.compile(r"(?i)\baiogram\b"), 3.5),
        ("salebot", re.compile(r"(?i)\bsalebot\b"), 3.2),
        ("manychat", re.compile(r"(?i)\bmanychat\b"), 3.2),
        ("wa", re.compile(r"(?i)\bwhatsapp\b|\bватсап\w*\b|\bвацап\w*\b"), 1.8),
    ),
    "Integrations_Sheets_CRM_n8n": (
        ("n8n", re.compile(r"(?i)\bn8n\b"), 4.5),
        ("make", re.compile(r"(?i)\bmake\b|\bintegromat\b"), 4.0),
        ("integration", re.compile(r"(?i)\bинтеграц\w*\b"), 1.8),
        ("automation", re.compile(r"(?i)\bавтоматизац\w*\b|\bавтоматизир\w*\b"), 2.0),
        ("webhook", re.compile(r"(?i)\bwebhook\b"), 3.0),
        ("api", re.compile(r"(?i)\bapi\b"), 2.5),
        ("sheets", re.compile(r"(?i)\bgoogle\s+sheets\b|\bsheets\b|\bгугл\s*таблиц\w*\b"), 3.0),
        ("crm", re.compile(r"(?i)\bcrm\b|\bamocrm\b|\bamo\b|\bbitrix\b|\bбитрикс\w*\b"), 2.8),
        ("notion", re.compile(r"(?i)\bnotion\b|\bноушн\b"), 2.5),
    ),
    "Autoposting_ContentFactory": (
        ("autopost", re.compile(r"(?i)\bавтопост\w*\b"), 4.0),
        ("content_factory", re.compile(r"(?i)\bконтент[-\s]?завод\w*\b"), 4.0),
        ("publish", re.compile(r"(?i)\bпубликац\w*\b|\bпостинг\w*\b"), 1.6),
        ("rss", re.compile(r"(?i)\brss\b"), 2.5),
    ),
    "Parsing_Analytics_Reports": (
        ("parsing", re.compile(r"(?i)\bпарсинг\b|\bспарс\w*\b"), 4.0),
        ("export", re.compile(r"(?i)\bвыгруз\w*\b"), 3.0),
        ("scraping", re.compile(r"(?i)\bscrap\w*\b|\bскрейп\w*\b"), 3.5),
        ("csv", re.compile(r"(?i)\bcsv\b"), 2.5),
        ("report", re.compile(r"(?i)\bотчет\w*\b|\bотч[её]т\w*\b|\bдашборд\w*\b"), 3.0),
    ),
    "Landing_Sites": (
        ("landing", re.compile(r"(?i)\bлендинг\w*\b"), 3.5),
        ("tilda", re.compile(r"(?i)\btilda\b|\bтильд\w*\b"), 3.2),
        ("taplink", re.compile(r"(?i)\btaplink\b|\bтаплинк\w*\b"), 3.0),
        ("site", re.compile(r"(?i)\bсайт\w*\b"), 2.0),
        ("quiz", re.compile(r"(?i)\bквиз\w*\b"), 2.5),
    ),
    "Sales_CRM_Process": (
        ("funnel", re.compile(r"(?i)\bворонк\w*\b"), 3.0),
        ("leads_word", re.compile(r"(?i)\bлид\w*\b|\bзаявк\w*\b"), 2.2),
        ("scripts", re.compile(r"(?i)\bскрипт\w*\b"), 2.5),
    ),
    "Design_Copy": (
        ("design", re.compile(r"(?i)\bдизайн\w*\b"), 2.8),
        ("logo", re.compile(r"(?i)\bлоготип\w*\b"), 3.0),
        ("banner", re.compile(r"(?i)\bбаннер\w*\b"), 2.6),
        ("copy", re.compile(r"(?i)\bкопирайт\w*\b"), 2.6),
    ),
}


@dataclass
class IntentResult:
    intent: str
    confidence: float
    scores: Dict[str, float]
    tags: Tuple[str, ...]


# ============================================================================
# PROFESSION DETECTION (for lead filtering by user profession)
# ============================================================================

PROFESSION_KEYWORDS: Dict[str, List[str]] = {
    "smm": ["смм", "smm", "соцсети", "соц сети", "контент", "сторис", "сторисмейкер", "ведение аккаунт", "инстаграм", "instagram", "вконтакте", "вк "],
    "designer": ["дизайн", "дизайнер", "логотип", "баннер", "инфографик", "презентац", "визуал", "креатив", "фирменный стиль", "брендинг", "полиграфи"],
    "targetolog": ["таргет", "таргетолог", "реклама", "рекламн", "facebook ads", "instagram ads", "вк реклам", "тизер", "маркетплейс реклам"],
    "reelsmaker": ["рилс", "reels", "монтаж", "монтажер", "видеомонтаж", "видео", "шортс", "shorts", "тикток", "tiktok", "съемк", "ролик", "клип"],
    "techspec": ["геткурс", "getcourse", "bizon", "бизон", "рассылк", "email", "sms", "вебинар", "автовебинар", "платежн", "эквайринг", "tilda настро", "тильда настро"],
    "copywriter": ["копирайт", "текст", "сценар", "прогрев", "контент-план", "посты", "рерайт", "статья", "слоган"],
    "marketer": ["маркетолог", "маркетинг", "стратеги", "продвижен", "бренд", "позиционир", "лид-магнит", "воронк"],
    "ad_buyer": ["закуп", "закупщик", "посев", "размещен", "реклама в канал", "интеграци блогер", "закупка рекламы", "tg ads", "telegram ads"],
    "assistant": ["ассистент", "помощник", "личный ассистент", "бизнес ассистент", "поручен", "административ"],
    "parsing": ["парсинг", "парсер", "выгруз", "спарс", "скрейп", "scraping", "авито парс", "база данных"],
    "lawyer": ["юрист", "юридичес", "договор", "правов", "бухгалтер", "бухучет", "налоговый"],
    "avitolog": ["авито", "avito", "объявлен", "авитолог"],
    "producer": ["продюсер", "запуск", "продакшн", "онлайн школ", "методолог", "курс под ключ"],
    "other": [],
}


def detect_target_professions(text: str) -> List[str]:
    """
    Detect which professions this lead is relevant for.
    Used to filter leads based on user's selected profession.
    """
    text_norm = (text or "").strip().lower()
    if not text_norm:
        return ["other"]
    
    matched: List[str] = []
    
    for profession, keywords in PROFESSION_KEYWORDS.items():
        if profession == "other":
            continue
        for kw in keywords:
            if kw in text_norm:
                matched.append(profession)
                break  # One match per profession is enough
    
    if not matched:
        matched.append("other")
    
    return matched


def _score_from_patterns(text: str, patterns: Tuple[Tuple[str, re.Pattern, float], ...]) -> Tuple[float, List[str]]:
    """Score text against pattern list"""
    score = 0.0
    tags: List[str] = []
    for tag, rx, weight in patterns:
        if rx.search(text):
            score += weight
            tags.append(tag)
    return score, tags


def extract_budget_rub(text: str) -> List[int]:
    """Extract budget mentions in rubles"""
    if not text:
        return []
    budgets: List[int] = []
    for match in _BUDGET_RE.finditer(text.lower()):
        if match.group(1):
            raw = match.group(1).replace(" ", "").replace("\u00A0", "")
            try:
                val = int(raw)
                if 1_000 <= val <= 500_000:
                    budgets.append(val)
            except ValueError:
                continue
        elif match.group(2):
            try:
                val = int(match.group(2)) * 1_000
                if 1_000 <= val <= 500_000:
                    budgets.append(val)
            except ValueError:
                continue
    return budgets


def classify_intent_pattern(text: str) -> IntentResult:
    """Pattern-based intent classification (fast, no LLM)"""
    text_norm = (text or "").strip().lower()
    if not text_norm or len(text_norm) < 10:
        return IntentResult(intent="CHATTER", confidence=0.3, scores={}, tags=())
    
    tags: List[str] = []
    
    # Score all intent types
    spam_score, spam_tags = _score_from_patterns(text_norm, _SPAM_PATTERNS)
    tags.extend(spam_tags)
    
    offer_score, offer_tags = _score_from_patterns(text_norm, _SERVICE_OFFER_PATTERNS)
    tags.extend(offer_tags)
    
    vacancy_score, vacancy_tags = _score_from_patterns(text_norm, _VACANCY_PATTERNS)
    tags.extend(vacancy_tags)
    
    client_score, client_tags = _score_from_patterns(text_norm, _CLIENT_TASK_PATTERNS)
    tags.extend(client_tags)
    
    # Boosts and penalties
    
    # Strong vacancy signal: "ищу <Role>"
    if _VACANCY_LOOKING_ROLE_RE.search(text_norm):
        vacancy_score += 5.0
        tags.append("vacancy:looking_role_strong")
    elif _HIRE_VERB_RE.search(text_norm) and _VACANCY_ROLE_RE.search(text_norm):
        vacancy_score += 2.0
        tags.append("vacancy:hire_and_role")
    
    # Budget mention -> client task
    budgets = extract_budget_rub(text_norm)
    if budgets:
        client_score += 0.8
        tags.append("client:budget")
    
    # Question mark
    if "?" in text_norm:
        client_score += 0.3
        tags.append("client:question")
    
    # Tech hint -> likely client task
    has_tech = _TECH_HINT_RE.search(text_norm)
    has_marketing = _MARKETING_INTEGRATION_RE.search(text_norm)
    
    if has_tech and not has_marketing:
        client_score += 0.8
        tags.append("client:tech_hint")
    elif has_marketing:
        client_score = max(0.0, client_score - 0.7)
        tags.append("client:marketing_penalty")
    
    # Decision
    scores = {
        "SPAM": spam_score,
        "OFFER": offer_score,
        "VACANCY": vacancy_score,
        "TASK": client_score,
        "CHATTER": 0.0,
    }
    
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    
    if best_score < 1.6:
        intent = "CHATTER"
    else:
        intent = best_intent
    
    # Overrides
    if intent == "TASK":
        if vacancy_score >= 2.0 and vacancy_score >= (client_score - 1.0):
            intent = "VACANCY"
            tags.append("tie:switched_to_vacancy")
        elif offer_score >= 2.5 and offer_score >= (client_score - 1.0):
            intent = "OFFER"
            tags.append("tie:switched_to_offer")
    
    if spam_score >= 4.0:
        intent = "SPAM"
        tags.append("override:spam")
    
    # Confidence
    if intent == "CHATTER":
        confidence = 0.4
    else:
        confidence = min(0.99, max(0.2, (best_score - second_score) / max(1.0, best_score)))
    
    return IntentResult(intent=intent, confidence=confidence, scores=scores, tags=tuple(tags))


def categorize_text(text: str) -> str:
    """Categorize text into tech category"""
    text_norm = (text or "").strip().lower()
    if not text_norm:
        return "Other"
    
    best_category = "Other"
    best_score = 0.0
    
    for cat, rules in _CATEGORY_RULES.items():
        score, _ = _score_from_patterns(text_norm, rules)
        if score > best_score:
            best_score = score
            best_category = cat
    
    if best_score < 1.5:
        return "Other"
    
    # Marketing integration check
    if best_category == "Integrations_Sheets_CRM_n8n":
        if _MARKETING_INTEGRATION_RE.search(text_norm) and not re.search(r"(?i)\b(n8n|make|integromat|webhook|api|sheets)\b", text_norm):
            return "Other"
    
    return best_category


def compute_fit_score(text: str, intent: str, category: str) -> float:
    """Compute how well this lead fits freelancer skills"""
    if intent not in ("TASK", "VACANCY"):
        return 0.0
    
    text_norm = (text or "").strip().lower()
    if not text_norm:
        return 0.0
    
    # Non-tech roles -> kill fit
    if _NEGATIVE_NOT_ME_RE.search(text_norm):
        if not _TECH_HINT_RE.search(text_norm):
            return 0.0
        return 0.1
    
    # Vacancy disguised as task
    if intent == "TASK":
        if _VACANCY_CONTEXT_RE.search(text_norm) and _HIRE_VERB_RE.search(text_norm):
            return 0.0
    
    base_by_category = {
        "Bots_TG_WA_VK": 0.95,
        "Integrations_Sheets_CRM_n8n": 0.95,
        "Autoposting_ContentFactory": 0.90,
        "Parsing_Analytics_Reports": 0.90,
        "Landing_Sites": 0.85,
        "Sales_CRM_Process": 0.50,
        "Design_Copy": 0.0,
        "Other": 0.10,
    }
    
    base = base_by_category.get(category, 0.10)
    
    tech_hits = _TECH_HINT_RE.findall(text_norm)
    boost = 0.0
    if tech_hits:
        boost = 0.1 + (0.05 * min(4, len(set(tech_hits))))
    
    total = base + boost
    
    if not tech_hits:
        total = min(total, 0.5)
    
    return max(0.0, min(total, 1.0))


def compute_money_score(text: str) -> float:
    """Compute money signal score"""
    text_norm = (text or "").strip().lower()
    if not text_norm:
        return 0.0
    
    score = 0.0
    
    if extract_budget_rub(text_norm):
        score += 0.45
    
    if re.search(r"(?i)\b(сколько\s+стоит|цена|стоимость|бюджет|оплата|предоплата)\b", text_norm):
        score += 0.25
    
    if re.search(r"(?i)\b(в\s+лс|в\s+личку|в\s+личные)\b", text_norm):
        score += 0.15
    
    if re.search(r"(?i)\b(срочно|сегодня|завтра|горит)\b", text_norm):
        score += 0.25
    
    if re.search(r"(?i)\b(срок|сроки|за\s+\d+\s+дн(я|ей))\b", text_norm):
        score += 0.15
    
    return max(0.0, min(score, 1.0))


# ============================================================================
# LLM-BASED CLASSIFICATION (for complex cases)
# ============================================================================

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
    Classify a message using pattern-based detection first, then LLM for uncertain cases
    """
    # Step 1: Pattern-based classification
    intent_result = classify_intent_pattern(text)
    category = categorize_text(text)
    fit_score = compute_fit_score(text, intent_result.intent, category)
    money_score = compute_money_score(text)
    
    # Detect target professions for this lead
    target_professions = detect_target_professions(text)
    
    # If confidence is high enough, skip LLM
    if intent_result.confidence >= 0.7 or intent_result.intent in ("SPAM", "CHATTER"):
        return {
            "type": intent_result.intent,
            "category": category,
            "fit_score": fit_score,
            "money_score": money_score,
            "confidence": intent_result.confidence,
            "target_professions": target_professions,
            "reasoning": f"Pattern-based: {', '.join(intent_result.tags[:5])}"
        }
    
    # Step 2: LLM for uncertain cases
    try:
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

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        
        content = response.choices[0].message.content.strip()
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            
            result['type'] = result.get('type', 'CHATTER').upper()
            if result['type'] not in LEAD_TYPES:
                result['type'] = 'CHATTER'
            
            result['category'] = result.get('category', 'Other')
            if result['category'] not in LEAD_CATEGORIES:
                result['category'] = 'Other'
            
            for key in ['fit_score', 'money_score', 'confidence']:
                result[key] = max(0.0, min(1.0, float(result.get(key, 0.5))))
            
            result['target_professions'] = target_professions
            return result
            
    except Exception as e:
        logger.warning(f"LLM classification failed, using pattern result: {e}")
    
    # Fallback to pattern-based result
    return {
        "type": intent_result.intent,
        "category": category,
        "fit_score": fit_score,
        "money_score": money_score,
        "confidence": intent_result.confidence,
        "target_professions": target_professions,
        "reasoning": f"Pattern-based (LLM fallback): {', '.join(intent_result.tags[:5])}"
    }


def get_default_classification() -> Dict[str, Any]:
    """Return default classification when all methods fail"""
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
    """Calculate weighted total score"""
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


def quick_filter(text: str) -> Tuple[bool, str]:
    """
    Quick keyword-based filter before classification
    Returns (is_potential_lead, likely_type)
    """
    intent_result = classify_intent_pattern(text)
    
    if intent_result.intent == "SPAM":
        return False, "SPAM"
    
    if intent_result.intent == "CHATTER" and intent_result.confidence > 0.5:
        return False, "CHATTER"
    
    return True, intent_result.intent


def batch_classify_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Classify multiple messages with pattern-based detection
    """
    results = []
    
    for msg in messages:
        text = msg.get('text', '')
        author = msg.get('author', '')
        msg_date = msg.get('date')
        
        # Skip very short messages
        if len(text) < 15:
            continue
        
        # Classify (pattern-based first, LLM only if needed)
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
