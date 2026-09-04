@echo off
echo ================================================================
echo   IBVAP - Intelligent Border Video Analytics Platform
echo ================================================================
echo.
echo Launching desktop surveillance system...
.\.venv\Scripts\python.exe main_desktop.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Application closed with exit code %ERRORLEVEL%.
    echo Please make sure all dependencies are installed.
    echo.
    pause
)
