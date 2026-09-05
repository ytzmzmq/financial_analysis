@echo off
chcp 65001 >nul 2>&1

REM 农业板块每日信号 - 本机桌面通知（可选；部署以 GitHub Actions 为准）
REM 手动运行或自行注册计划任务（示例）：
REM   schtasks /create /tn "农业板块Tracker" /tr "<项目路径>\run_tracker_agri.bat" /sc daily /st 14:45 /rl highest

set PROJECT_DIR=%~dp0
if not defined PYTHON set PYTHON=python
set PYTHONPATH=%PROJECT_DIR%

set LOGFILE=%PROJECT_DIR%agriculture\data\processed\tracker_log_agri.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === agri tracker start === >> "%LOGFILE%"
"%PYTHON%" agriculture\app\tracker_agri.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === agri tracker done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo.
type "%LOGFILE%" | more +0
pause
