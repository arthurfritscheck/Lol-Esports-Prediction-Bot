@echo off
rem restarts the bot automatically if it crashes or loses connection
cd /d "%~dp0"
:loop
python main.py
echo Bot stopped, restarting in 10 seconds... (close this window to stop it)
timeout /t 10 /nobreak >nul
goto loop
