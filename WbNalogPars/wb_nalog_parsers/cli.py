from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from .analytics import AnalyticsPipeline
from .bot import build_bot_application
from .config import AppConfig
from .image_parser import ImageParser
from .nalog_api import NalogAPI
from .pdf_parser import PDFParser
from .wb_api import WildberriesAPI


def fetch_nalog(args: argparse.Namespace) -> None:
    config = AppConfig.load()
    api = NalogAPI(config.nalog_api)
    if args.mode == "company":
        payload = api.search_company(args.inn, args.kpp)
    elif args.mode == "debt":
        payload = api.fetch_tax_debt(args.inn)
    else:
        today = date.today()
        payload = api.fetch_statements(args.inn, date_from=today - timedelta(days=30), date_to=today)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved response to {args.output}")


def fetch_wb(args: argparse.Namespace) -> None:
    config = AppConfig.load()
    api = WildberriesAPI(config.wb_api)
    if args.mode == "orders":
        payload = api.get_orders(args.date_from, args.status)
    elif args.mode == "stocks":
        payload = api.get_stocks(args.warehouse_id)
    else:
        payload = api.get_detail_report(args.date_from, args.date_to)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved response to {args.output}")


def parse_image(args: argparse.Namespace) -> None:
    parser = ImageParser()
    payload = parser.parse_invoice(args.path)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved OCR result to {args.output}")


def parse_pdf(args: argparse.Namespace) -> None:
    parser = PDFParser()
    payload = parser.parse_invoice(args.path)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved PDF parse result to {args.output}")


def run_analytics(args: argparse.Namespace) -> None:
    orders = json.loads(Path(args.orders).read_text(encoding="utf-8"))
    pipeline = AnalyticsPipeline(Path(args.output_dir))
    df = pipeline.aggregate_orders(orders)
    anomalies = pipeline.detect_anomalies(df["revenue"])
    anomalies.to_csv(Path(args.output_dir) / "anomalies.csv")
    pipeline.cluster_skus(df[["revenue", "quantity"]])
    print(f"Analytics saved to {args.output_dir}")


def run_bot(args: argparse.Namespace) -> None:
    config = AppConfig.load()
    if not config.telegram:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан в .env, бот не может стартовать.")
    application = build_bot_application(config)
    application.run_polling()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Utility CLI for Nalog + Wildberries parsing.")
    subparsers = parser.add_subparsers()

    nalog_parser = subparsers.add_parser("nalog", help="Work with FNS API")
    nalog_parser.add_argument("--mode", choices=["company", "debt", "statements"], default="company")
    nalog_parser.add_argument("--inn", required=True)
    nalog_parser.add_argument("--kpp")
    nalog_parser.add_argument("--output", default="data/nalog.json")
    nalog_parser.set_defaults(func=fetch_nalog)

    wb_parser = subparsers.add_parser("wb", help="Work with Wildberries API")
    wb_parser.add_argument("--mode", choices=["orders", "stocks", "report"], default="orders")
    wb_parser.add_argument("--date-from", dest="date_from", required=True)
    wb_parser.add_argument("--date-to", dest="date_to")
    wb_parser.add_argument("--status", default="all")
    wb_parser.add_argument("--warehouse-id", dest="warehouse_id", type=int)
    wb_parser.add_argument("--output", default="data/wb.json")
    wb_parser.set_defaults(func=fetch_wb)

    img_parser = subparsers.add_parser("image", help="Parse invoice/receipt images")
    img_parser.add_argument("path")
    img_parser.add_argument("--output", default="data/image.json")
    img_parser.set_defaults(func=parse_image)

    pdf_parser = subparsers.add_parser("pdf", help="Parse PDF invoices")
    pdf_parser.add_argument("path")
    pdf_parser.add_argument("--output", default="data/pdf.json")
    pdf_parser.set_defaults(func=parse_pdf)

    analytics_parser = subparsers.add_parser("analytics", help="Run AI analytics on orders JSON")
    analytics_parser.add_argument("--orders", required=True)
    analytics_parser.add_argument("--output-dir", dest="output_dir", default="data/analytics")
    analytics_parser.set_defaults(func=run_analytics)

    bot_parser = subparsers.add_parser("bot", help="Run Telegram bot for remote commands")
    bot_parser.set_defaults(func=run_bot)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
