@echo off
echo ========================================
echo   TG Workspace - Development Mode
echo ========================================
echo.

:: Start API server
echo Starting API server...
cd /d "%~dp0apps\api"
start "TG Workspace API" cmd /k "python -m uvicorn app.main:app --reload --port 8765"

:: Wait for API to start
echo Waiting for API to initialize...
timeout /t 3 /nobreak > nul

:: Start frontend
echo Starting frontend...
cd /d "%~dp0apps\desktop"
start "TG Workspace Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo   Both servers are starting...
echo   API: http://127.0.0.1:8765
echo   Frontend: http://localhost:5173
echo ========================================
echo.
pause
