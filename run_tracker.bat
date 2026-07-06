@echo off
REM 医药板块底部探测器 - 定时执行脚本
REM 用于 Windows 任务计划程序，每天自动运行 tracker.py 并将信号写入 SQLite
REM
REM 首次使用请修改:
REM   1. 如果 python 不在 PATH 中，取消下方 PYTHON 注释行并填入实际路径
REM   2. 确保 data\processed\ 目录存在

REM 自动定位到 bat 文件所在目录（项目根目录）
set PROJECT_DIR=%~dp0
REM 如 python 不在 PATH 中，取消注释并修改为你的 Python 路径:
REM set PYTHON=C:\path\to\python.exe
if not defined PYTHON set PYTHON=python

set LOGFILE=%PROJECT_DIR%data\processed\tracker_log.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === tracker start === >> "%LOGFILE%"
"%PYTHON%" app/tracker.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === tracker done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo. >> "%LOGFILE%"
