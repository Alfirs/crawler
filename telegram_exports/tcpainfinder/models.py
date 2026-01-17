from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


Category = Literal[
    "Bots_TG_WA_VK",
    "Integrations_Sheets_CRM_n8n",
    "Autoposting_ContentFactory",
    "Parsing_Analytics_Reports",
    "Landing_Sites",
    "Sales_CRM_Process",
    "Design_Copy",
    "Other",
]

MessageIntent = Literal[
    "CLIENT_TASK",
    "VACANCY_HIRE",
    "SERVICE_OFFER",
    "SPAM_SCAM",
    "CHATTER",
]


@dataclass(frozen=True)
class ChatMessage:
    chat_key: str
    chat_name: str
    source_path: Path
    dt: datetime
    author: str | None
    text_raw: str
    text_redacted: str
    text_norm: str
    tokens: tuple[str, ...]
    intent: MessageIntent
    intent_confidence: float
    intent_tags: tuple[str, ...]
    money_signal_score: float
    fit_for_me_score: float
    category: Category


@dataclass(frozen=True)
class ChatExport:
    chat_key: str
    display_name: str
    source_path: Path
    total_messages_in_file: int
    parsed_messages: int
    messages: tuple[ChatMessage, ...]


@dataclass
class PainCluster:
    pain_id: str
    category: Category
    title: str
    messages: list[ChatMessage] = field(default_factory=list)
    frequency: int = 0
    money_signal_score: float = 0.0
    fit_for_me_score: float = 0.0
    recency_score: float = 0.0
    example_phrase: str = ""
    quick_solution_1_2_days: str = ""
    suggested_price_range: str = ""


@dataclass(frozen=True)
class AnalysisConfig:
    since_days: int = 60
    min_message_length: int = 8
    top_k: int = 20
    lang: str = "ru"
    include_vacancies: bool = True
    only_client_tasks: bool = False
    min_fit_score: float = 0.4
    min_money_score: float = 0.2
    leads_include_vacancies: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    config: AnalysisConfig
    exports: tuple[ChatExport, ...]
    messages: tuple[ChatMessage, ...]
    client_task_messages: tuple[ChatMessage, ...]
    vacancy_messages: tuple[ChatMessage, ...]
    service_offer_messages: tuple[ChatMessage, ...]
    spam_messages: tuple[ChatMessage, ...]
    chatter_messages: tuple[ChatMessage, ...]
    client_task_clusters: tuple[PainCluster, ...]
    vacancy_clusters_top: tuple[PainCluster, ...]
    leads_md: str
    debug_stats: dict
    generated_offers_md: str
    generated_sales_messages_md: str
    generated_action_plan_md: str
