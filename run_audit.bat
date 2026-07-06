@echo off
REM 月度因子审计 — 每月1号自动运行稳健性检验 + 新因子发现
REM 报告输出到 data\processed\audit_report.md
REM
REM 首次使用请修改:
REM   1. 如果 python 不在 PATH 中，取消下方 PYTHON 注释行并填入实际路径
REM   2. 确保 data\processed\ 目录存在

REM 自动定位到 bat 文件所在目录（项目根目录）
set PROJECT_DIR=%~dp0
REM 如 python 不在 PATH 中，取消注释并修改为你的 Python 路径:
REM set PYTHON=C:\path\to\python.exe
if not defined PYTHON set PYTHON=python

set LOGFILE=%PROJECT_DIR%data\processed\audit_log.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === monthly audit start === >> "%LOGFILE%"
"%PYTHON%" app/monthly_audit.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === monthly audit done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo. >> "%LOGFILE%"
