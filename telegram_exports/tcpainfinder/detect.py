from __future__ import annotations

import re
from dataclasses import dataclass

from tcpainfinder.models import Category, MessageIntent


_HASHTAG_RE = re.compile(r"(?i)#[a-zа-яё0-9_]{3,}")

# Budget-like mentions.
_BUDGET_RE = re.compile(
    r"(?i)(?:\b(\d{1,3}(?:[ \u00A0]\d{3})+|\d{4,6})\s*(?:₽|руб\.?|р\.?|rub)\b)|(?:\b(\d{1,3})\s*(?:к|k)\b)"
)

_VACANCY_ROLES = (
    r"таргетолог\w*|smm|смм|маркетолог\w*|трафиколог\w*|медиабайер\w*|байер\w*|закупщик\w*|"
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

# "Looking for <Role>" - very strong vacancy signal
_VACANCY_LOOKING_ROLE_RE = re.compile(
    rf"(?i)\b(ищу|ищем|нужн(о|а|ы|ен)|требуетс\w*|ваканс\w*|нанима\w*)\b(?:\s+\w+){{0,6}}\s+({_VACANCY_ROLES})\b"
)

# Explicitly "Not my" roles - used to kill fit score
_NEGATIVE_NOT_ME_RE = re.compile(
    r"(?i)\b(таргет\w*|smm|смм|ведение\w*|контент[-\s]?менеджер\w*|дизайн\w*|копирайт\w*|"
    r"монтаж[её]р\w*|логотип\w*|баннер\w*|сторисмейкер\w*|рилсмейкер\w*|креатор\w*|"
    r"методолог\w*|методист\w*|юрист\w*|адвокат\w*|"
    r"3d\b|рендер\w*|визуализатор\w*|визуал\w*)\b"
)

# Tech/automation hints
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

_MARKETING_INTEGRATION_RE = re.compile(
    r"(?i)\bинтеграц\w*\b.*\b(блогер\w*|канал\w*|реклам\w*|посев\w*|закуп\w*|размещен\w*)\b"
    r"|\b(блогер\w*|канал\w*|реклам\w*|посев\w*|закуп\w*|размещен\w*)\b.*\bинтеграц\w*\b"
)


@dataclass(frozen=True)
class IntentResult:
    intent: MessageIntent
    confidence: float
    scores: dict[MessageIntent, float]
    tags: tuple[str, ...]


def extract_budget_rub(text_lower: str) -> list[int]:
    if not text_lower:
        return []
    budgets: list[int] = []
    # Basic protection against very short texts triggering false positives is done outside by min_len
    for match in _BUDGET_RE.finditer(text_lower):
        if match.group(1):
            raw = match.group(1).replace(" ", "").replace("\u00A0", "")
            try:
                val = int(raw)
            except ValueError:
                continue
            if 1_000 <= val <= 500_000:
                budgets.append(val)
        elif match.group(2):
            try:
                val = int(match.group(2)) * 1_000
            except ValueError:
                continue
            if 1_000 <= val <= 500_000:
                budgets.append(val)
    return budgets


def _score_from_patterns(text: str, patterns: tuple[tuple[str, re.Pattern[str], float], ...]) -> tuple[float, list[str]]:
    score = 0.0
    tags: list[str] = []
    for tag, rx, weight in patterns:
        if rx.search(text):
            score += weight
            tags.append(tag)
    return score, tags


# PATTERNS DEFINITION
_VACANCY_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("vacancy:vacancy_word", re.compile(r"(?i)\b(ваканс\w*|vacancy)\b"), 6.0),
    ("vacancy:in_team", re.compile(r"(?i)\bв\s+команду\b"), 2.2),
    ("vacancy:in_staff", re.compile(r"(?i)\bв\s+штат\b"), 2.5),
    ("vacancy:hire", re.compile(r"(?i)\bнанима\w*\b|\bнайм\b|\bhiring\b"), 2.0),
    ("vacancy:resume", re.compile(r"(?i)\bрезюме\b|\bcv\b"), 1.8),
    ("vacancy:apply", re.compile(r"(?i)\bотклик\w*\b|\bзаполни\w*\s+анкет\w*"), 1.5),
    ("vacancy:conditions", re.compile(r"(?i)\b(обязанност\w*|требован\w*|услови\w*|график\w*|занятост\w*|зп|зарплат\w*|оклад\w*)\b"), 1.6),
)

_SERVICE_OFFER_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("offer:help_start", re.compile(r"(?i)^\s*помог(у|аю)\b"), 3.5),
    ("offer:help_word", re.compile(r"(?i)\bпомог(у|аю)\b"), 2.5),
    ("offer:what_i_can", re.compile(r"(?i)\bчто\s+могу\s+(сделать|помочь)\b"), 2.2),
    ("offer:take_care", re.compile(r"(?i)\bберу\s+на\s+себя\b"), 1.6),
    ("offer:i_am_tech", re.compile(r"(?i)\bя\b.{0,40}\b(техническ\w*\s+специалист|техспец)\b"), 2.5),
    ("offer:want_do", re.compile(r"(?i)\bхочешь\b.*\b(сделаю|настрою|соберу|подключу|запущу)\b"), 2.2),
    ("offer:will_do", re.compile(r"(?i)\b(сделаю|настрою|соберу|подключу|запущу|автоматизирую|интегрирую)\b"), 1.8),
    ("offer:services", re.compile(r"(?i)\b(предлагаю|оказываю)\s+услуг\w*\b"), 2.5),
    ("offer:i_do", re.compile(r"(?i)\bя\s+(делаю|создаю|настраиваю|разрабатываю|собираю|помогаю|веду)\b"), 2.2),
    ("offer:portfolio", re.compile(r"(?i)\bпортфолио\b|\bкейсы?\b"), 2.2),
    ("offer:take_projects", re.compile(r"(?i)\b(беру|возьму)\s+(в\s+работу|проект\w*|клиент\w*)\b"), 2.5),
    ("offer:dm", re.compile(r"(?i)\bпишите\s+в\s+(лс|личку)\b"), 0.8),
    ("offer:job_seeker_basic", re.compile(r"(?i)\b(ищу\s+работ\w*|в\s+поиске\s+работ\w*|ищу\s+подработ\w*|ищу\s+заказ\w*)\b"), 2.0),
)

_SPAM_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("spam:easy_money", re.compile(r"(?i)\b(легк(ий|ая)\s+заработок|заработа(й|ть)\s+на\s+телефоне|без\s+опыта|доход\s+от)\b"), 4.0),
    ("spam:referral", re.compile(r"(?i)\b(ссылка\s+в\s+профиле|переходи\s+по\s+ссылке)\b"), 2.0),
    ("spam:invest", re.compile(r"(?i)\b(инвестици\w*|крипт\w*|форекс|арбитраж|ставки)\b"), 2.5),
    ("spam:guarantee", re.compile(r"(?i)\b(гарантирую|100%|без\s+вложени\w*)\b"), 2.5),
)

_CLIENT_TASK_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    ("client:need", re.compile(r"(?i)\b(нужн(о|а|ы|ен)|надо|требуетс\w*)\b"), 1.2),
    ("client:do", re.compile(r"(?i)\b(сделать|сделайте|настроить|собрать|подключить|интегрир|автоматизир|спарс|выгруз)\w*"), 1.6),
    ("client:who_can", re.compile(r"(?i)\bкто\s+может\b|\bкто\s+сделает\b|\bкто\s+умеет\b"), 1.6),
    ("client:looking_exec", re.compile(r"(?i)\b(ищу|нужен)\s+(исполнителя|специалиста|разработчика|прогера|кодера)\b"), 1.8),
    ("client:price", re.compile(r"(?i)\b(сколько\s+стоит|цена|стоимость|бюджет|оплата)\b"), 1.1),
    ("client:urgency", re.compile(r"(?i)\b(срочно|сегодня|завтра|горит)\b"), 1.3),
)


def classify_intent(text_redacted_lower: str, text_norm: str) -> IntentResult:
    # raw used for budgets and punctuation checks
    raw = (text_redacted_lower or "").strip().lower()
    # norm used for pattern matching
    norm = (text_norm or "").strip().lower()
    
    tags: list[str] = []

    # 1. Base Scores
    spam_score, spam_tags = _score_from_patterns(norm, _SPAM_PATTERNS)
    tags.extend(spam_tags)
    
    offer_score, offer_tags = _score_from_patterns(norm, _SERVICE_OFFER_PATTERNS)
    tags.extend(offer_tags)
    
    vacancy_score, vacancy_tags = _score_from_patterns(norm, _VACANCY_PATTERNS)
    tags.extend(vacancy_tags)
    
    client_score, client_tags = _score_from_patterns(norm, _CLIENT_TASK_PATTERNS)
    tags.extend(client_tags)

    # 2. Heuristics & Boosts
    
    # Hashes -> Offer (usually)
    if len(_HASHTAG_RE.findall(raw)) >= 3:
        offer_score += 1.0
        tags.append("offer:many_hashtags")
    
    # Vacancy Strong Signal: "I am looking for <Role>"
    if _VACANCY_LOOKING_ROLE_RE.search(norm):
        vacancy_score += 5.0
        tags.append("vacancy:looking_role_strong")
    elif _HIRE_VERB_RE.search(norm) and _VACANCY_ROLE_RE.search(norm):
        vacancy_score += 2.0
        tags.append("vacancy:hire_and_role")
        
    # Budget check
    budgets = extract_budget_rub(raw)
    if budgets:
        client_score += 0.8
        tags.append("client:budget")
        
    if "?" in raw:
        client_score += 0.3
        tags.append("client:question")
        
    # Tech hints vs Marketing hints
    has_tech = _TECH_HINT_RE.search(norm)
    has_marketing_int = _MARKETING_INTEGRATION_RE.search(norm)
    
    if has_tech and not has_marketing_int:
        client_score += 0.8
        tags.append("client:tech_hint")
    elif has_marketing_int:
        # Marketing integration is usually spam or vacancy or offer, rarely technical client task
        client_score = max(0.0, client_score - 0.7)
        tags.append("client:marketing_penalty")

    # 3. Decision Logic
    scores: dict[MessageIntent, float] = {
        "SPAM_SCAM": spam_score,
        "SERVICE_OFFER": offer_score,
        "VACANCY_HIRE": vacancy_score,
        "CLIENT_TASK": client_score,
        "CHATTER": 0.0,
    }

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_intent, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_score < 1.6:
        intent: MessageIntent = "CHATTER"
    else:
        intent = best_intent

    # 4. Tie Breakers and Overrides
    
    # If it looks like client task, but has strong vacancy signals -> It's a vacancy
    if intent == "CLIENT_TASK":
        if vacancy_score >= 2.0 and vacancy_score >= (client_score - 1.0):
            intent = "VACANCY_HIRE"
            tags.append("tie:switched_to_vacancy")
            
    # If it looks like client task, but has strong offer signals -> It's an offer
    if intent == "CLIENT_TASK":
        if offer_score >= 2.5 and offer_score >= (client_score - 1.0):
            intent = "SERVICE_OFFER"
            tags.append("tie:switched_to_offer")

    # Explicit hard overrides for very strong signals
    if spam_score >= 4.0:
        intent = "SPAM_SCAM"
        tags.append("override:spam")
        
    # Confidence calc
    if intent == "CHATTER":
        confidence = 0.4
    else:
        # Normalize somewhat
        confidence = min(0.99, max(0.2, (best_score - second_score) / max(1.0, best_score)))

    return IntentResult(intent=intent, confidence=confidence, scores=scores, tags=tuple(tags))


def compute_money_signal_score(text_redacted_lower: str) -> float:
    text = (text_redacted_lower or "").lower()
    if not text:
        return 0.0

    score = 0.0
    if extract_budget_rub(text):
        score += 0.45
    
    # Simple keyword checks without regex compilation overhead for every call (cached by re module anyway but still)
    # Using previous regexes:
    
    if re.search(r"(?i)\b(сколько\s+стоит|цена|стоимость|бюджет|оплата|предоплата)\b", text):
        score += 0.25
        
    if re.search(r"(?i)\b(в\s+лс|в\s+личку|в\s+личные)\b", text):
        score += 0.15
        
    if re.search(r"(?i)\b(срочно|сегодня|завтра|горит)\b", text):
        score += 0.25
        
    if re.search(r"(?i)\b(срок|сроки|за\s+\d+\s+дн(я|ей))\b", text):
        score += 0.15
        
    if re.search(r"(?i)\b(ищу|нужен).*\b(исполнителя|спец)", text):
        score += 0.10

    return max(0.0, min(score, 1.0))


def compute_fit_for_me_score(text_norm: str, *, intent: MessageIntent, category: Category) -> float:
    # Only relevant for potential leads (Tasks or Vacancies if allowed)
    if intent not in ("CLIENT_TASK", "VACANCY_HIRE"):
        return 0.0

    text_norm = (text_norm or "").lower()
    if not text_norm:
        return 0.0

    # 1. Critical Rejects from User Rules
    
    # "Not my services" -> SMM, Target, Design
    if _NEGATIVE_NOT_ME_RE.search(text_norm):
        # Only excuse: if tech automation is explicitly mentioned
        if not _TECH_HINT_RE.search(text_norm):
            return 0.0
        # Penalty even if tech hint is present, because it's likely "Target + Bot", implying full stack marketing
        return 0.1 

    # Vacancy in Client Task check (double check)
    # If we are here, intent might be CLIENT_TASK, but if text screams vacancy, we kill the fit score
    # to prevent it from showing up as a "Hot Lead" unless specifically asked for vacancies
    if intent == "CLIENT_TASK":
         if _VACANCY_CONTEXT_RE.search(text_norm) and _HIRE_VERB_RE.search(text_norm):
             # It's a vacancy disguised as a task
             return 0.0

    base_by_category: dict[Category, float] = {
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
    
    # No tech keywords -> cap at 0.5 (low confidence fit)
    if not tech_hits:
        total = min(total, 0.5)

    return max(0.0, min(total, 1.0))
