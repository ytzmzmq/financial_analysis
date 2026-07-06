@echo off
REM 医药板块底部探测器 - 定时执行脚本
REM 用于 Windows 任务计划程序，每天自动运行 tracker.py 并将信号写入 SQLite

set PROJECT_DIR=D:\financial_analysis
set PYTHON=C:\Users\lenovo\AppData\Local\Programs\Python\Python313\python.exe
set LOGFILE=%PROJECT_DIR%\data\processed\tracker_log.txt

cd /d "%PROJECT_DIR%"

echo [%date% %time%] === tracker start === >> "%LOGFILE%"
"%PYTHON%" app/tracker.py >> "%LOGFILE%" 2>&1
echo [%date% %time%] === tracker done (exitcode=%errorlevel%) === >> "%LOGFILE%"
echo. >> "%LOGFILE%"
