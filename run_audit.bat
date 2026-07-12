@echo off
chcp 65001 >nul 2>&1

REM Monthly factor audit - scheduled task
REM Auto-detects project dir from bat file location

set PROJECT_DIR=%~dp0
if not defined PYTHON set PYTHON=python
set PYTHONPATH=%PROJECT_DIR%

set LOGFILE=%PROJECT_DIR%data\processed\audit_log.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === monthly audit start === >> "%LOGFILE%"
"%PYTHON%" app/monthly_audit.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === monthly audit done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo. >> "%LOGFILE%"
