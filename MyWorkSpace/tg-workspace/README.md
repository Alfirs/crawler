# TG Workspace

🎯 Desktop application for managing Telegram leads with AI-powered CRM and gamification.

## Features

- 📥 Import Telegram chat exports (JSON/HTML)
- 🤖 AI-powered lead classification and scoring
- 💬 Personalized message generation with Gemini
- 📊 CRM workflow with status tracking
- 🎮 Gamification: XP, levels, streaks, badges
- 🛡️ Anti-spam protection and daily limits

## Tech Stack

- **Desktop**: Electron + React + Vite + Tailwind + shadcn/ui
- **Backend**: Python FastAPI + SQLite
- **LLM**: Google Gemini (via OpenAI-compatible API)

## Project Structure

```
tg-workspace/
├── apps/
│   ├── desktop/    # Electron + React frontend
│   └── api/        # Python FastAPI backend
├── shared/         # Shared types/contracts
└── scripts/        # Dev and build scripts
```

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- pnpm (recommended) or npm

### Installation

1. Clone and install dependencies:

```bash
# Install frontend dependencies
cd apps/desktop
pnpm install

# Install backend dependencies
cd ../api
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

3. Run in development:

```bash
# Terminal 1: Start API server
cd apps/api
python -m uvicorn app.main:app --reload --port 8765

# Terminal 2: Start Electron app
cd apps/desktop
pnpm dev
```

### Build for Production

```bash
cd apps/desktop
pnpm build
```

This creates `dist/` with Windows installer.

## Safety Rules

⚠️ **No automatic message sending!**

- All messages are drafts until manually confirmed
- "Copy" + "Open in Telegram" workflow only
- Daily contact limits (default: 15)
- Follow-up cooldown (24-48 hours)
- "Do Not Contact" list for declined leads

## License

MIT
