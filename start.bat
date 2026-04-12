@echo off
echo ==========================================
echo   Recalbox ROM Manager v1.0
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM Install dependencies only if missing
python -c "import flask, flask_cors" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install flask flask-cors --quiet
)

echo.
echo Starting server...
echo.
echo ============================================
echo   Open in browser: http://localhost:5123
echo ============================================
echo.
echo   Default share path: \\RECALBOX\share
echo   Override with: set RECALBOX_SHARE=\\YOUR_IP\share
echo.
echo   Press Ctrl+C to stop
echo ============================================
echo.

python server.py
pause
