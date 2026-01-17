from __future__ import annotations

import collections
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tcpainfinder.clustering import cluster_messages
from tcpainfinder.generation import (
    generate_action_plan_14_days_md,
    generate_offers_md,
    generate_sales_messages_md,
    recommended_offer_for_category,
)
from tcpainfinder.models import AnalysisConfig, AnalysisResult, ChatMessage, MessageIntent, PainCluster
from tcpainfinder.telegram_json import load_exports_from_path
from tcpainfinder.text import to_one_line, top_keywords
from tcpainfinder.user_profile import CATEGORY_PRICE_RANGES


@dataclass(frozen=True)
class LeadRow:
    chat_name: str
    message_date: str
    category: str
    snippet: str
    recommended_offer: str
    suggested_price: str
    confidence: float
    lead_intent: MessageIntent
    why: str


def _fmt_dt_local(dt: datetime) -> str:
    try:
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return dt.strftime("%Y-%m-%d %H:%M")


def _lead_confidence(m: ChatMessage) -> float:
    # Practical confidence: intent confidence + fit.
    return max(0.0, min(1.0, (m.intent_confidence * 0.55) + (m.fit_for_me_score * 0.45)))


def _make_leads_md(leads: list[LeadRow], *, config: AnalysisConfig) -> str:
    lines: list[str] = [
        "# Leads (кому писать)",
        "",
        f"- Фильтры: since_days={config.since_days}, min_fit_score={config.min_fit_score}, min_money_score={config.min_money_score}",
        f"- Vacancies included: {config.leads_include_vacancies}",
        f"- Лидов: {len(leads)}",
        "",
        "| # | chat_name | message_date | type | category | snippet | recommended_offer | suggested_price | why | confidence |",
        "|---:|---|---|---|---|---|---|---|---|---:|",
    ]
    for i, row in enumerate(leads, start=1):
        snippet = row.snippet.replace("|", "/")
        rec_offer = row.recommended_offer.replace("|", "/")
        intent_short = "TASK" if row.lead_intent == "CLIENT_TASK" else "VACANCY"
        lines.append(
            f"| {i} | {row.chat_name} | {row.message_date} | {intent_short} | {row.category} | {snippet} | {rec_offer} | {row.suggested_price} | {row.why} | {row.confidence:.2f} |"
        )
    lines.append("")
    return "\n".join(lines)


def _debug_stats(messages: list[ChatMessage], *, config: AnalysisConfig) -> dict:
    intents = collections.Counter([m.intent for m in messages])
    categories = collections.Counter([m.category for m in messages if m.intent == "CLIENT_TASK"])
    
    # helper for tokens
    def get_tokens(intent_name):
        return [t for m in messages if m.intent == intent_name for t in m.tokens]

    top_client_tokens = top_keywords(get_tokens("CLIENT_TASK"), k=20)
    top_vacancy_tokens = top_keywords(get_tokens("VACANCY_HIRE"), k=20)
    
    top_tags_by_intent = {
        intent: collections.Counter([tag for m in messages if m.intent == intent for tag in m.intent_tags]).most_common(20)
        for intent in ("CLIENT_TASK", "VACANCY_HIRE", "SERVICE_OFFER", "SPAM_SCAM")
    }
    return {
        "config": {
            "since_days": config.since_days,
            "min_message_length": config.min_message_length,
            "top_k": config.top_k,
            "min_fit_score": config.min_fit_score,
            "min_money_score": config.min_money_score,
            "include_vacancies": config.include_vacancies,
            "only_client_tasks": config.only_client_tasks,
            "leads_include_vacancies": config.leads_include_vacancies,
            "lang": config.lang,
        },
        "counts": {
            "messages_total": len(messages),
            "CLIENT_TASK": intents.get("CLIENT_TASK", 0),
            "VACANCY_HIRE": intents.get("VACANCY_HIRE", 0),
            "SERVICE_OFFER": intents.get("SERVICE_OFFER", 0),
            "SPAM_SCAM": intents.get("SPAM_SCAM", 0),
            "CHATTER": intents.get("CHATTER", 0),
        },
        "client_task_categories": dict(categories.most_common(20)),
        "top_tokens": {
            "CLIENT_TASK": top_client_tokens,
            "VACANCY_HIRE": top_vacancy_tokens,
        },
        "top_intent_tags": top_tags_by_intent,
    }


def _is_spam_by_content(text_norm: str) -> bool:
    bad_words = [
        "подработка", "доход в день", "лайки", "комментарии", "17+", "выплаты", "без опыта", 
        "заработок", "отзывы", "опросы"
    ]
    for b in bad_words:
        if b in text_norm:
            return True
    return False


def _get_lead_why(m: ChatMessage) -> str:
    parts = []
    if m.money_signal_score >= 0.4:
        parts.append("money")
    if m.fit_for_me_score >= 0.7:
        parts.append("high_fit")
    if "urgent" in str(m.intent_tags):
        parts.append("urgent")
    if "tech_hint" in str(m.intent_tags):
        parts.append("tech")
    
    if not parts:
        return "match"
    return ",".join(parts)


def _filter_lead_candidate(m: ChatMessage, *, config: AnalysisConfig) -> bool:
    # 1. Never SPAM
    if m.intent == "SPAM_SCAM":
        return False
    
    # 2. Key phrases filter (content based) - strict check
    if _is_spam_by_content(m.text_norm):
        return False
        
    # 3. Intent Logic
    if m.intent == "CLIENT_TASK":
        if m.fit_for_me_score < config.min_fit_score:
            return False
        if m.money_signal_score < config.min_money_score:
            return False
        return True
        
    if m.intent == "VACANCY_HIRE":
        if not config.leads_include_vacancies:
            return False
        # Strict rules for vacancies
        if m.fit_for_me_score < 0.8:
            return False
        if m.intent_confidence < 0.6:
            return False
        return True
        
    return False


def analyze_exports(input_path: Path, config: AnalysisConfig) -> AnalysisResult:
    exports = load_exports_from_path(input_path, config=config)
    if not exports:
        raise ValueError(
            "No Telegram exports found. Expected a JSON export (result.json) or HTML export (messages.html)."
        )

    all_messages = [m for e in exports for m in e.messages]
    total_parsed = sum(e.parsed_messages for e in exports)

    by_intent: dict[MessageIntent, list[ChatMessage]] = {
        "CLIENT_TASK": [],
        "VACANCY_HIRE": [],
        "SERVICE_OFFER": [],
        "SPAM_SCAM": [],
        "CHATTER": [],
    }
    for m in all_messages:
        by_intent[m.intent].append(m)

    # For reporting clusters - we use standard logic
    client_tasks_all = by_intent["CLIENT_TASK"]
    vacancies_all = by_intent["VACANCY_HIRE"]
    service_offers_all = by_intent["SERVICE_OFFER"]
    spam_all = by_intent["SPAM_SCAM"]
    chatter_all = by_intent["CHATTER"]

    # For grouping into clusters (summary of pains), we use standard client task filter
    # But we reuse _filter_lead_candidate logic partially? 
    # Actually, clusters are mostly for "hot topics". Let's keep using base filters for clusters.
    client_tasks_filtered = [
        m for m in client_tasks_all 
        if m.fit_for_me_score >= config.min_fit_score and m.money_signal_score >= config.min_money_score
    ]

    client_clusters = cluster_messages(client_tasks_filtered, cluster_prefix="P")

    vacancy_clusters: list[PainCluster] = []
    if config.include_vacancies and not config.only_client_tasks:
        vacancy_clusters = cluster_messages(vacancies_all, cluster_prefix="V")

    # --- LEADS GENERATION (Strict) ---
    leads_candidates = []
    for m in all_messages:
        if _filter_lead_candidate(m, config=config):
            leads_candidates.append(m)

    # Sort candidates
    leads_candidates.sort(
        key=lambda m: (m.fit_for_me_score, m.money_signal_score, m.dt),
        reverse=True,
    )

    leads: list[LeadRow] = []
    seen: set[tuple[str, str]] = set()
    
    for m in leads_candidates:
        key = (m.chat_key, m.text_norm[:120])
        if key in seen:
            continue
        seen.add(key)
        
        confidence = _lead_confidence(m)
        if confidence < 0.55:
            continue
            
        leads.append(
            LeadRow(
                chat_name=m.chat_name,
                message_date=_fmt_dt_local(m.dt),
                category=m.category,
                snippet=to_one_line(m.text_redacted, max_len=170),
                recommended_offer=recommended_offer_for_category(m.category),
                suggested_price=CATEGORY_PRICE_RANGES.get(m.category, ""),
                confidence=confidence,
                lead_intent=m.intent,
                why=_get_lead_why(m)
            )
        )
        if len(leads) >= 120:
            break

    leads_md = _make_leads_md(leads, config=config)
    debug_stats = _debug_stats(all_messages, config=config)

    offers_md = generate_offers_md()
    sales_messages_md = generate_sales_messages_md()
    action_plan_md = generate_action_plan_14_days_md(client_clusters)

    return AnalysisResult(
        config=config,
        exports=tuple(exports),
        messages=tuple(all_messages),
        client_task_messages=tuple(client_tasks_all),
        vacancy_messages=tuple(vacancies_all),
        service_offer_messages=tuple(service_offers_all),
        spam_messages=tuple(spam_all),
        chatter_messages=tuple(chatter_all),
        client_task_clusters=tuple(client_clusters),
        vacancy_clusters_top=tuple(vacancy_clusters[: min(50, len(vacancy_clusters))]),
        leads_md=leads_md,
        debug_stats=debug_stats,
        generated_offers_md=offers_md,
        generated_sales_messages_md=sales_messages_md,
        generated_action_plan_md=action_plan_md,
    )
