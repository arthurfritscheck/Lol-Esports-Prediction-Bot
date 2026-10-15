@echo off
rem runs the TEST bot with the settings from .env.test
cd /d "%~dp0"
python main.py --test
pause
