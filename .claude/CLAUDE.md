# CLAUDE.md — 医药板块风险收益比监控器

## 项目概述
基于五阶段因子优化的医药板块极端超跌检测系统。不是"底部预测器"，是"赔率改善状态识别器"。
运行环境: Python 3.13, Windows 11, VS Code

## 核心架构
```
app/tracker.py          → CLI 信号输出 + 距离触发 + 警报 (三层 try/except 防护)
app/server.py           → 实时看板服务器 (http://127.0.0.1:8888, Tab 切换: 实时/历史)
app/db.py               → SQLite 存储: signals 表 + system_log 表 (自动建表+CSV迁移)
app/dashboard.py        → 生成自包含 HTML 看板
app/notify.py           → 微信推送 (Server酱/PushDeer/Webhook)
app/monthly_audit.py    → 月度因子审计 (稳健性检验 + 新因子发现, 输出 audit_report.md)
src/models/rule_registry.py  → 统一规则引擎 (RULE_DEFS + MODEL_CONFIGS + evaluate_signal)
src/models/indicators.py     → 共享技术指标 (rsi_wilder + macd_histogram 单一来源)
src/models/turning_points.py → distance_to_trigger + alert_level + Triple Barrier
src/models/factor_optimizer.py → 五阶段因子筛选框架
src/data_fetcher/akshare_source.py → AKShare + Sina ETF 实时
src/data_fetcher/fred_source.py    → FRED 美国宏观
run_tracker.bat         → Windows 任务计划: 每天 14:45 执行 tracker.py
run_audit.bat           → Windows 任务计划: 每月 1 号 09:00 执行审计
run_v5_optimizer.py     → 一键重跑五阶段优化
```

## 数据存储
- 信号历史: `data/processed/signals.db` (SQLite, signals 表, INSERT OR REPLACE 去重)
- 错误日志: 同库 system_log 表 (timestamp/source/level/message)
- 旧 CSV (`signal_history.csv`) 首次运行自动导入, 之后不再使用
- 审计报告: `data/processed/audit_report.md`
- 执行日志: `data/processed/tracker_log.txt` + `audit_log.txt`

## API 路由 (server.py)
- `GET /` → SPA 看板 (JS 动态渲染, Tab 切换实时/历史)
- `GET /api/signal?price=` → 实时信号 JSON (含 chart 数据 + armed_history)
- `GET /api/history` → SQLite 历史信号记录
- `GET /api/errors` → 最近 24h 系统错误/警告日志

## 关键约定
- 回复全部用中文
- 所有 md 文件 (REPORT/PROGRESS/CODE_REVIEW) 每次代码改动后必须同步更新
- 数据源: AKShare + Sina ETF + FRED, 全部免费
- 实时价格: Sina 抓 512170 ETF 涨跌幅映射 801150
- 浏览器看板图表库首次下载缓存到 data/lightweight-charts.min.js
- GitHub Actions 每交易日 14:45 自动运行 (与本地 schtasks 并行)
- 试算模式 (custom_price) 不写入 SQLite, 防止假信号污染历史
- 错误处理: 数据拉取/解析/计算三层 try/except, 失败写 system_log + 页面横幅

## 常用命令
```bash
python app/tracker.py                     # CLI 信号
python app/server.py                      # 实时服务器 (自动开浏览器)
python app/server.py --port 9000          # 指定端口
python app/server.py --no-browser         # 不自动开浏览器
python app/monthly_audit.py              # 月度因子审计
python app/dashboard.py                  # 生成静态看板
python app/notify.py --test              # 测试推送
python run_v5_optimizer.py               # 重跑因子优化
```

## 数据流
AKShare(指数/融资) + Sina(ETF实时) → resample(W-FRI) → FactorPool(14因子) → 三漏斗筛选 → MODEL_CONFIGS(V5.2: 4因子 L1=3.0/M1=2.5/S3=2.0/V1=2.0) → evaluate_signal() → Score + n_factors_tier Armed → signal_tier(hold/weak/standard/strong) → SQLite
