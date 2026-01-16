from fastapi import FastAPI

from app.api.routers import drafts
from app.db import init_db
from app.workers.scheduler import get_scheduler

app = FastAPI(title="Content Factory")

app.include_router(drafts.router)


@app.on_event("startup")
async def startup_event() -> None:
    init_db()
    scheduler = get_scheduler()
    await scheduler.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    scheduler = get_scheduler()
    await scheduler.stop()
