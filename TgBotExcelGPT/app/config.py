import os
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Simple settings loader using environment variables."""

    neuroapi_key: Optional[str]
    neuroapi_model: str
    unstructured_api_key: Optional[str]
    google_service_account_json: Optional[str]
    google_drive_folder_id: Optional[str]
    google_sheets_id: Optional[str]
    suppliers_sheet_range: str
    telegram_bot_token: Optional[str]
    webhook_secret: Optional[str]
    smtp_host: Optional[str]
    smtp_port: int
    smtp_user: Optional[str]
    smtp_password: Optional[str]
    imap_host: Optional[str]
    imap_user: Optional[str]
    imap_password: Optional[str]

    def __init__(self) -> None:
        self.neuroapi_key = os.getenv("NEUROAPI_API_KEY")
        self.neuroapi_model = os.getenv("NEUROAPI_MODEL", "gpt-4o")
        self.unstructured_api_key = os.getenv("UNSTRUCTURED_API_KEY")
        self.google_service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        self.google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self.google_sheets_id = os.getenv("GOOGLE_SHEETS_ID")
        self.suppliers_sheet_range = os.getenv("SUPPLIERS_SHEET_RANGE", "Suppliers!A2:E1000")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.webhook_secret = os.getenv("WEBHOOK_SECRET")
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.imap_host = os.getenv("IMAP_HOST")
        self.imap_user = os.getenv("IMAP_USER")
        self.imap_password = os.getenv("IMAP_PASSWORD")


settings = Settings()
