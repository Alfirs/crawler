#!/bin/bash
echo "========================================"
echo "  TG Workspace - Development Mode"
echo "========================================"
echo ""

# Start API server in background
echo "Starting API server..."
cd "$(dirname "$0")/../apps/api"
python -m uvicorn app.main:app --reload --port 8765 &
API_PID=$!

# Wait for API to start
sleep 3

# Start frontend
echo "Starting frontend..."
cd "$(dirname "$0")/../apps/desktop"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  Both servers are running..."
echo "  API: http://127.0.0.1:8765"
echo "  Frontend: http://localhost:5173"
echo "  Press Ctrl+C to stop"
echo "========================================"

# Trap SIGINT to clean up
trap "kill $API_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT

# Wait for both processes
wait
