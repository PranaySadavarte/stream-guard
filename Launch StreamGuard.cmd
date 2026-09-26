@echo off
cd /d "%~dp0"
if exist "dist\StreamGuard\StreamGuard.exe" (
    start "StreamGuard" "dist\StreamGuard\StreamGuard.exe"
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "StreamGuard" ".venv\Scripts\pythonw.exe" -m streamguard.ui.main_window
    exit /b
)
if exist "..\.venv\Scripts\pythonw.exe" (
    start "StreamGuard" "..\.venv\Scripts\pythonw.exe" -m streamguard.ui.main_window
    exit /b
)
echo Install StreamGuard as described in README.md first.
pause
