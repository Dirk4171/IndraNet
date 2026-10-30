@echo off
REM IndraNet 2 aus dem Quelltext starten. Öffnet den Browser.
REM Einmalig vorher:  python -m pip install -r requirements.txt
cd /d "%~dp0"
python -X utf8 indranet.py %*
if errorlevel 1 pause
