@echo off
rem ============================================================
rem  本地准点触发：调用 GitHub workflow_dispatch 启动每日流水线
rem  由 Windows 计划任务 FinancialAnalysis_CI_1452 在
rem  周一至周五 14:52 自动调用（与 cron-job.org 的 14:45 错开，
rem  避免两次 dispatch 同时到达导致重复运行）
rem
rem  日志：%LOCALAPPDATA%\financial_analysis_ci\trigger_ci.log
rem  手动验证：双击本文件，或 python scripts\trigger_ci.py --check
rem ============================================================
setlocal
set "PY=D:\Conda\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0trigger_ci.py" %*
exit /b %ERRORLEVEL%
