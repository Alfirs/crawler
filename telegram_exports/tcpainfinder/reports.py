from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tcpainfinder.generation import recommended_offer_for_category
from tcpainfinder.models import AnalysisResult, PainCluster
from tcpainfinder.text import to_one_line
from tcpainfinder.user_profile import PRIMARY_CATEGORIES
from tcpainfinder.utils import sanitize_filename


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clusters_top(clusters: list[PainCluster], *, k: int) -> list[PainCluster]:
    return [c for c in clusters[: max(0, k)] if c.frequency > 0]


def _summary_md(result: AnalysisResult, *, top_k: int = 10) -> str:
    now = datetime.now(tz=timezone.utc)
    total_parsed = sum(e.parsed_messages for e in result.exports)

    lines: list[str] = [
        "# Telegram Chat Pain Finder - summary",
        "",
        "Важно: в отчетах удалены телефоны/email/ссылки/@упоминания/похожие на токены строки. Примеры - 1 строка.",
        "",
        "## Статистика",
        f"- Чатов/экспортов: {len(result.exports)}",
        f"- Сообщений (текст, после фильтров): {total_parsed}",
        f"- CLIENT_TASK: {len(result.client_task_messages)}",
        f"- VACANCY_HIRE: {len(result.vacancy_messages)}",
        f"- SERVICE_OFFER: {len(result.service_offer_messages)}",
        f"- SPAM_SCAM: {len(result.spam_messages)}",
        f"- CHATTER: {len(result.chatter_messages)}",
        f"- Период: последние {result.config.since_days} дней (на момент запуска: {now.date().isoformat()})",
        "",
        "## Где смотреть лиды",
        "- leads.md - список кому писать прямо сейчас (20-100+ лидов, если есть).",
        "",
        "## ТОП-10 ЗАКАЗОВ (CLIENT_TASK) - мои деньги",
    ]

    client_top = _clusters_top(list(result.client_task_clusters), k=top_k)
    if not client_top:
        lines.append(
            "- Не найдено задач под фильтры fit/money. Попробуй снизить --min-fit-score или --min-money-score, или увеличить --since-days."
        )
    else:
        for c in client_top:
            lines.append(
                f"- {c.pain_id} | {c.category} | {to_one_line(c.title, max_len=120)} "
                f"(freq={c.frequency}, money={c.money_signal_score:.2f}, fit={c.fit_for_me_score:.2f}, recency={c.recency_score:.2f})"
            )

    if result.config.include_vacancies and not result.config.only_client_tasks:
        lines.extend(["", "## ТОП-10 ВАКАНСИЙ (VACANCY_HIRE) - фон рынка"])
        vac_top = _clusters_top(list(result.vacancy_clusters_top), k=top_k)
        if not vac_top:
            lines.append("- Вакансии не найдены (или отключены).")
        else:
            for c in vac_top:
                lines.append(f"- {c.pain_id} | {to_one_line(c.title, max_len=130)} (freq={c.frequency}, recency={c.recency_score:.2f})")

    lines.extend(["", "## ТОП-5 идей заработка под мои услуги", ""])
    ideas: list[str] = []
    for c in list(result.client_task_clusters):
        if c.category not in PRIMARY_CATEGORIES:
            continue
        if c.fit_for_me_score < result.config.min_fit_score:
            continue
        ideas.append(f"- {c.category}: {c.quick_solution_1_2_days} Цена: {c.suggested_price_range}.")
        if len(ideas) >= 5:
            break
    if ideas:
        lines.extend(ideas)
    else:
        lines.append("- Нет подходящих идей под мои услуги по текущим фильтрам.")

    # What to sell first: most common categories in top clusters.
    cat_counts = Counter([c.category for c in list(result.client_task_clusters)[:20] if c.category in PRIMARY_CATEGORIES])
    lines.extend(["", "## Что продавать первым (1-2 продукта)", ""])
    if cat_counts:
        for cat, _ in cat_counts.most_common(2):
            lines.append(f"- {recommended_offer_for_category(cat)}")
    else:
        lines.append('- Начни с "Интеграция n8n: заявки -> Sheets/CRM + уведомления" и "Бот + заявки в таблицу".')

    return "\n".join(lines).rstrip() + "\n"


def _write_pains_csv(path: Path, clusters: list[PainCluster]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "pain_id",
                "category",
                "title",
                "frequency",
                "money_signal_score",
                "fit_for_me_score",
                "recency_score",
                "example_phrase",
                "quick_solution_1_2_days",
                "suggested_price_range",
            ],
        )
        writer.writeheader()
        for c in clusters:
            writer.writerow(
                {
                    "pain_id": c.pain_id,
                    "category": c.category,
                    "title": to_one_line(c.title, max_len=220),
                    "frequency": c.frequency,
                    "money_signal_score": f"{c.money_signal_score:.2f}",
                    "fit_for_me_score": f"{c.fit_for_me_score:.2f}",
                    "recency_score": f"{c.recency_score:.2f}",
                    "example_phrase": to_one_line(c.example_phrase, max_len=220),
                    "quick_solution_1_2_days": to_one_line(c.quick_solution_1_2_days, max_len=220),
                    "suggested_price_range": c.suggested_price_range,
                }
            )


def _chat_report_md(result: AnalysisResult, *, chat_key: str, top_k: int = 10) -> str:
    exp_by_key = {e.chat_key: e for e in result.exports}
    exp = exp_by_key.get(chat_key)
    clusters = list(result.client_task_clusters)

    lines: list[str] = [f"# Chat report: {chat_key}", ""]
    if exp:
        lines.append(f"- Source: {exp.source_path.name}")
        lines.append(f"- Messages parsed: {exp.parsed_messages}")
        lines.append("")

    stats: list[tuple[PainCluster, int]] = []
    for c in clusters:
        count = sum(1 for m in c.messages if m.chat_key == chat_key)
        if count:
            stats.append((c, count))
    stats.sort(key=lambda x: (-x[1], -x[0].fit_for_me_score, -x[0].money_signal_score))

    lines.append("## ТОП заказов (CLIENT_TASK) в этом чате")
    if not stats:
        lines.append("- Нет подходящих заказов под текущие фильтры.")
    else:
        for c, count in stats[:top_k]:
            lines.append(
                f"- {c.pain_id} | {c.category} | {to_one_line(c.title, max_len=120)} (в чате: {count}, fit={c.fit_for_me_score:.2f})"
            )

    return "\n".join(lines).rstrip() + "\n"


def write_reports(out_dir: Path, result: AnalysisResult, *, top_k: int = 20, include_chat_reports: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    client_clusters = list(result.client_task_clusters)[:top_k]

    _write_text(out_dir / "summary.md", _summary_md(result, top_k=10))
    _write_pains_csv(out_dir / "pains.csv", client_clusters)
    _write_text(out_dir / "leads.md", result.leads_md)
    _write_text(out_dir / "offers.md", result.generated_offers_md)
    _write_text(out_dir / "sales_messages.md", result.generated_sales_messages_md)
    _write_text(out_dir / "action_plan_14_days.md", result.generated_action_plan_md)
    _write_json(out_dir / "debug_stats.json", result.debug_stats)

    if include_chat_reports:
        base = out_dir / "chat_reports"
        base.mkdir(parents=True, exist_ok=True)
        for exp in result.exports:
            filename = sanitize_filename(exp.chat_key, fallback="chat") + ".md"
            _write_text(base / filename, _chat_report_md(result, chat_key=exp.chat_key, top_k=10))

