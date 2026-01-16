@echo off
echo Starting Auto-Sync for D:\VsCode...
python "D:\VsCode\auto_sync.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Script execution failed with error code %ERRORLEVEL%.
    pause
)
