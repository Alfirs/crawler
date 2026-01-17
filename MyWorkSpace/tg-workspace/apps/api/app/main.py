"""
TG Workspace API - FastAPI Backend
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db.database import engine, Base
from app.api import workspaces, sources, messages, leads, outreach, templates, settings, gamification, llm, telegram, autopost

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title="TG Workspace API",
    description="Backend API for Telegram Lead Management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Electron app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["Workspaces"])
app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(leads.router, prefix="/api/leads", tags=["Leads"])
app.include_router(outreach.router, prefix="/api/outreach", tags=["Outreach"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(gamification.router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(llm.router, prefix="/api/llm", tags=["LLM"])
app.include_router(telegram.router, prefix="/api/telegram", tags=["Telegram"])
app.include_router(autopost.router, prefix="/api/autopost", tags=["Autopost"])

@app.get("/")
async def root():
    return {"message": "TG Workspace API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}
