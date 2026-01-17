from __future__ import annotations

import re
from dataclasses import dataclass

from tcpainfinder.models import Category


@dataclass(frozen=True)
class CategoryScore:
    category: Category
    score: float
    matched: tuple[str, ...] = ()


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_TECH_INTEGRATION_HINT_RE = _rx(r"\b(n8n|make|integromat|webhook|api|google\s+sheets|sheets|crm|amocrm|bitrix|notion)\b")
_MARKETING_INTEGRATION_HINT_RE = _rx(
    r"\bинтеграц\w*\b.*\b(блогер\w*|канал\w*|реклам\w*|посев\w*|закуп\w*|размещен\w*)\b"
    r"|\b(блогер\w*|канал\w*|реклам\w*|посев\w*|закуп\w*|размещен\w*)\b.*\bинтеграц\w*\b"
)


_RULES: dict[Category, tuple[tuple[str, re.Pattern[str], float], ...]] = {
    "Bots_TG_WA_VK": (
        ("bot_word", _rx(r"\bбот\w*\b"), 2.2),
        ("chatbot", _rx(r"\bчат[-\s]?бот\w*\b"), 3.0),
        ("telegram_bot", _rx(r"\b(telegram\s+bot|телеграм\s+бот|tg\s*бот)\b"), 3.5),
        ("aiogram", _rx(r"\baiogram\b"), 3.5),
        ("salebot", _rx(r"\bsalebot\b"), 3.2),
        ("manychat", _rx(r"\bmanychat\b"), 3.2),
        ("botfather", _rx(r"\bbotfather\b"), 3.0),
        ("buttons", _rx(r"\bкнопк\w*\b"), 0.5), # Lowered significantly
        ("menu", _rx(r"\bменю\b"), 0.5),        # Lowered significantly
        ("wa", _rx(r"\bwhatsapp\b|\bватсап\w*\b|\bвацап\w*\b"), 1.8),
        ("vk_bot", _rx(r"\b(вк|vk)\s*бот\w*\b"), 2.5),
        ("autofunnel", _rx(r"\bавтоворонк\w*\b"), 1.0),
    ),
    "Integrations_Sheets_CRM_n8n": (
        ("n8n", _rx(r"\bn8n\b"), 4.5), # Boosted
        ("make", _rx(r"\bmake\b|\bintegromat\b"), 4.0),
        ("integration_word", _rx(r"\bинтеграц\w*\b"), 1.8),
        ("automation", _rx(r"\bавтоматизац\w*\b|\bавтоматизир\w*\b"), 2.0),
        ("webhook", _rx(r"\bwebhook\b"), 3.0),
        ("api", _rx(r"\bapi\b"), 2.5),
        ("sheets", _rx(r"\bgoogle\s+sheets\b|\bsheets\b|\bгугл\s*таблиц\w*\b"), 3.0),
        ("table", _rx(r"\bтаблиц\w*\b"), 1.0),
        ("crm", _rx(r"\bcrm\b|\bamocrm\b|\bamo\b|\bbitrix\b|\bбитрикс\w*\b"), 2.8),
        ("notion", _rx(r"\bnotion\b|\bноушн\b"), 2.5),
        (
            "payments",
            _rx(
                r"\b(yookassa|cloudpayments)\b|\bюкасс\w*\b|\bюmoney\b|\bюмани\b|\bплат[её]ж\w*\b|\bпри[её]м\s+оплат\w*\b|\bподключить\s+оплат\w*\b"
            ),
            1.5,
        ),
    ),
    "Autoposting_ContentFactory": (
        ("autopost", _rx(r"\bавтопост\w*\b"), 4.0),
        ("content_factory", _rx(r"\bконтент[-\s]?завод\w*\b"), 4.0),
        ("publish", _rx(r"\bпубликац\w*\b|\bпостинг\w*\b"), 1.6),
        ("queue", _rx(r"\bочеред\w*\b.*\b(пост\w*|публикац\w*)\b"), 2.8),
        ("rss", _rx(r"\brss\b"), 2.5),
        ("reels", _rx(r"\breels\b|\bshorts\b|\btiktok\b|\bрилс\w*\b"), 0.8),
    ),
    "Parsing_Analytics_Reports": (
        ("parsing", _rx(r"\bпарсинг\b|\bспарс\w*\b"), 4.0),
        ("export", _rx(r"\bвыгруз\w*\b"), 3.0),
        ("scraping", _rx(r"\bscrap\w*\b|\bскрейп\w*\b"), 3.5),
        ("data", _rx(r"\bданн\w*\b"), 1.0),
        ("csv", _rx(r"\bcsv\b"), 2.5),
        ("excel", _rx(r"\bexcel\b"), 2.0),
        ("report", _rx(r"\bотчет\w*\b|\bотч[её]т\w*\b|\bдашборд\w*\b"), 3.0),
        ("metrics", _rx(r"\bметрик\w*\b"), 2.5),
    ),
    "Landing_Sites": (
        ("landing", _rx(r"\bлендинг\w*\b"), 3.5),
        ("tilda", _rx(r"\btilda\b|\bтильд\w*\b"), 3.2),
        ("taplink", _rx(r"\btaplink\b|\bтаплинк\w*\b"), 3.0),
        ("site", _rx(r"\bсайт\w*\b"), 2.0),
        ("quiz", _rx(r"\bквиз\w*\b"), 2.5),
        ("form", _rx(r"\bформа\w*\b|\bform\w*\b"), 1.5),
        ("wordpress", _rx(r"\bwordpress\b|\bвордпресс\b"), 2.5),
    ),
    "Sales_CRM_Process": (
        ("funnel", _rx(r"\bворонк\w*\b"), 3.0),
        ("leads", _rx(r"\bлид\w*\b|\bзаявк\w*\b"), 2.2),
        ("crm", _rx(r"\bcrm\b|\bamocrm\b|\bbitrix\b|\bбитрикс\w*\b"), 2.0), # Lower than Integration
        ("scripts", _rx(r"\bскрипт\w*\b"), 2.5),
        ("conversion", _rx(r"\bконверс\w*\b"), 2.0),
        ("pipeline", _rx(r"\bпроцесс\w*\b.*\bпродаж\w*\b"), 3.0),
        ("managers", _rx(r"\bменеджер\w*\b"), 0.5), # Very low, usually vacancy
    ),
    "Design_Copy": (
        ("design", _rx(r"\bдизайн\w*\b"), 2.8),
        ("logo", _rx(r"\bлоготип\w*\b"), 3.0),
        ("covers", _rx(r"\bобложк\w*\b"), 2.2),
        ("templates", _rx(r"\bшаблон\w*\b"), 1.8),
        ("presentation", _rx(r"\bпрезентац\w*\b"), 2.2),
        ("banner", _rx(r"\bбаннер\w*\b"), 2.6),
        ("figma", _rx(r"\bfigma\b|\bфигм\w*\b"), 2.2),
        ("copy", _rx(r"\bкопирайт\w*\b"), 2.6),
        ("text", _rx(r"\bтекст\w*\b"), 0.6),
    ),
    "Other": (),
}


def score_categories(text_norm: str) -> list[CategoryScore]:
    text_norm = (text_norm or "").lower()
    if not text_norm:
        return [CategoryScore(category="Other", score=0.0, matched=())]

    out: list[CategoryScore] = []
    for cat, rules in _RULES.items():
        score = 0.0
        matched: list[str] = []
        for tag, rx, weight in rules:
            if rx.search(text_norm):
                score += weight
                matched.append(tag)
        out.append(CategoryScore(category=cat, score=score, matched=tuple(matched)))

    out.sort(key=lambda x: x.score, reverse=True)
    return out


def categorize_text(text_norm: str) -> Category:
    scores = score_categories(text_norm)
    if not scores:
        return "Other"

    best = scores[0]
    if best.score <= 0.0:
        return "Other"

    # Special case: "интеграция" в маркетинге (у блогеров) ≠ тех интеграция.
    if best.category == "Integrations_Sheets_CRM_n8n":
        if _MARKETING_INTEGRATION_HINT_RE.search(text_norm) and not _TECH_INTEGRATION_HINT_RE.search(text_norm):
            return "Other"

    # Autoposting: avoid classifying by "reels" alone.
    if best.category == "Autoposting_ContentFactory":
        # Must have at least moderate score to avoid false positives on just "reels"
        if best.score < 1.5:
            return "Other"

    return best.category
