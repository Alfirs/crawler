#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from tcpainfinder.models import AnalysisConfig
from tcpainfinder.pipeline import analyze_exports
from tcpainfinder.reports import write_reports


@dataclass(frozen=True)
class CliArgs:
    input: Path
    out: Path
    since_days: int
    min_message_length: int
    top_k: int
    lang: str
    include_vacancies: bool
    only_client_tasks: bool
    min_fit_score: float
    min_money_score: float
    chat_reports: bool
    leads_include_vacancies: bool


def _parse_bool(value: str) -> bool:
    v = (value or "").strip().lower()
    if v in {"true", "1", "yes", "y", "on"}:
        return True
    if v in {"false", "0", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("Expected true/false")


def _parse_args(argv: list[str]) -> CliArgs:
    parser = argparse.ArgumentParser(
        description=(
            "Telegram Chat Pain Finder: analyzes Telegram JSON chat exports and produces "
            "pain/request insights + offers + sales messages + 14-day action plan."
        )
    )
    parser.add_argument("--input", required=True, help="Input folder (JSON exports or HTML exports) or a single file")
    parser.add_argument("--out", required=True, help="Output folder for reports")
    parser.add_argument("--since-days", type=int, default=60, help="Analyze only last N days (default: 60)")
    parser.add_argument(
        "--min-message-length",
        type=int,
        default=8,
        help="Minimum message length after normalization (default: 8)",
    )
    parser.add_argument("--top-k", type=int, default=20, help="Top pains to include (default: 20)")
    parser.add_argument("--lang", default="ru", help="Language (default: ru)")
    parser.add_argument(
        "--include-vacancies",
        type=_parse_bool,
        default=True,
        help="Include vacancies section in summary/debug (default: true)",
    )
    parser.add_argument(
        "--only-client-tasks",
        type=_parse_bool,
        default=False,
        help="Only focus on CLIENT_TASK (default: false)",
    )
    parser.add_argument(
        "--min-fit-score",
        type=float,
        default=0.4,
        help="Minimum fit_for_me_score for pains/leads (default: 0.4)",
    )
    parser.add_argument(
        "--min-money-score",
        type=float,
        default=0.2,
        help="Minimum money_signal_score for leads/pains (default: 0.2)",
    )
    parser.add_argument(
        "--leads-include-vacancies",
        type=_parse_bool,
        default=False,
        help="Include high-quality vacancies in leads.md (default: false)",
    )
    parser.add_argument(
        "--chat-reports",
        action="store_true",
        help="Also generate per-chat markdown reports in chat_reports/",
    )
    ns = parser.parse_args(argv)
    return CliArgs(
        input=Path(ns.input),
        out=Path(ns.out),
        since_days=ns.since_days,
        min_message_length=ns.min_message_length,
        top_k=ns.top_k,
        lang=ns.lang,
        include_vacancies=bool(ns.include_vacancies),
        only_client_tasks=bool(ns.only_client_tasks),
        min_fit_score=float(ns.min_fit_score),
        min_money_score=float(ns.min_money_score),
        chat_reports=bool(ns.chat_reports),
        leads_include_vacancies=bool(ns.leads_include_vacancies),
    )


def main(argv: list[str]) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    args = _parse_args(argv)
    if args.lang.lower() != "ru":
        logging.warning("Only 'ru' language is tuned well right now; proceeding with lang=%s", args.lang)

    config = AnalysisConfig(
        since_days=args.since_days,
        min_message_length=args.min_message_length,
        top_k=args.top_k,
        lang=args.lang.lower(),
        include_vacancies=args.include_vacancies,
        only_client_tasks=args.only_client_tasks,
        min_fit_score=args.min_fit_score,
        min_money_score=args.min_money_score,
        leads_include_vacancies=args.leads_include_vacancies,
    )

    try:
        result = analyze_exports(args.input, config=config)
        write_reports(args.out, result, top_k=args.top_k, include_chat_reports=args.chat_reports)
    except KeyboardInterrupt:
        logging.error("Interrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        logging.error("%s", exc)
        return 2

    logging.info("Done. Reports written to: %s", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
