@echo off
chcp 65001 >nul 2>&1

REM Medical sector tracker - daily scheduled task with desktop notification
REM Auto-detects project dir from bat file location

set PROJECT_DIR=%~dp0
if not defined PYTHON set PYTHON=python
set PYTHONPATH=%PROJECT_DIR%

set LOGFILE=%PROJECT_DIR%data\processed\tracker_log.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === tracker start === >> "%LOGFILE%"
"%PYTHON%" app/notify.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === tracker done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo. >> "%LOGFILE%"
