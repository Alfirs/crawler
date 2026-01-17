@echo off
title TG Workspace
echo ========================================
echo   TG Workspace - Launching...
echo ========================================
echo.

:: Start API server in background
start "TG Workspace API" /min cmd /c "cd /d %~dp0apps\api && python -m uvicorn app.main:app --port 8765"

:: Wait for API
echo Waiting for API server...
timeout /t 3 /nobreak > nul

:: Start Frontend in background
start "TG Workspace Frontend" /min cmd /c "cd /d %~dp0apps\desktop && npm run dev"

:: Wait for frontend
echo Waiting for frontend...
timeout /t 5 /nobreak > nul

:: Open browser
echo Opening TG Workspace...
start http://localhost:5173

echo.
echo ========================================
echo   TG Workspace is running!
echo   Close this window to stop the app.
echo ========================================
pause
