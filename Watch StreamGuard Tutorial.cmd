@echo off
if exist "%~dp0artifacts\tutorial\StreamGuard-Tutorial.mp4" (
    start "" "%~dp0artifacts\tutorial\StreamGuard-Tutorial.mp4"
    exit /b
)
if exist "%~dp0release\StreamGuard\docs\StreamGuard-Tutorial.mp4" (
    start "" "%~dp0release\StreamGuard\docs\StreamGuard-Tutorial.mp4"
    exit /b
)
echo Tutorial not found. See docs\QUICK_START.md for instructions.
pause
