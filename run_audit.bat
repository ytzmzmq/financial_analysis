@echo off
REM 月度因子审计 — 每月1号自动运行稳健性检验 + 新因子发现
REM 报告输出到 data/processed/audit_report.md

set PROJECT_DIR=D:\financial_analysis
set PYTHON=C:\Users\lenovo\AppData\Local\Programs\Python\Python313\python.exe
set LOGFILE=%PROJECT_DIR%\data\processed\audit_log.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === monthly audit start === >> "%LOGFILE%"
"%PYTHON%" app/monthly_audit.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === monthly audit done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo. >> "%LOGFILE%"
