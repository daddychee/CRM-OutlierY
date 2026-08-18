@echo off
rem Windows launcher - double-click to open the Niche Research START window.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 niche_research_gui.py
    goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python niche_research_gui.py
    goto end
)

echo.
echo Python 3 was not found.
echo Install it from https://www.python.org/downloads/ and tick "Add Python to PATH".
echo.
pause

:end
if %errorlevel% neq 0 pause
