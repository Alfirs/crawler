from __future__ import annotations

import asyncio

from app.config import Settings
from app.db import init_db


async def _main() -> None:
    settings = Settings()
    print(f"Initializing database at: {settings.db_path}")
    await init_db(settings.db_path)
    print("Database initialized successfully.")


if __name__ == "__main__":
    asyncio.run(_main())
