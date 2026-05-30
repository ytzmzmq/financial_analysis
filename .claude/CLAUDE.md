# CLAUDE.md — 医药板块风险收益比监控器

## 项目概述
基于五阶段因子优化的医药板块极端超跌检测系统。不是"底部预测器"，是"赔率改善状态识别器"。
运行环境: Python 3.13, Windows 11, VS Code

## 核心架构
```
app/tracker.py          → CLI 信号输出 + 距离触发 + 警报
app/dashboard.py        → 生成自包含 HTML 看板
app/server.py           → 实时看板服务器 (http://127.0.0.1:8888)
app/notify.py           → 微信推送 (Server酱)
src/models/turning_points.py  → V5Detector + Triple Barrier + 距离触发
src/models/factor_optimizer.py → 五阶段因子筛选框架
src/data_fetcher/akshare_source.py → AKShare + Sina ETF 实时
src/data_fetcher/fred_source.py    → FRED 美国宏观
run_v5_optimizer.py     → 一键重跑五阶段优化
```

## 关键约定
- 回复全部用中文
- 所有 md 文件 (REPORT/PROGRESS/CODE_REVIEW) 每次代码改动后必须同步更新
- 数据源: AKShare + Sina ETF + FRED, 全部免费
- 实时价格: Sina 抓 512170 ETF 涨跌幅映射 801150
- 浏览器看板图表库首次下载缓存到 data/lightweight-charts.min.js
- GitHub Actions 每交易日 14:45 自动运行, SSH 推送

## 常用命令
```bash
python app/tracker.py                     # CLI 信号
python app/dashboard.py                   # 生成看板
python app/server.py                      # 实时服务器
python app/notify.py --test              # 测试推送
python run_v5_optimizer.py               # 重跑因子优化
```

## 数据流
AKShare(指数/融资) + Sina(ETF实时) → resample(W-FRI) → FactorPool(14因子) → 三漏斗筛选 → 评分卡(3因子) → V5Detector → Score → Armed/Alert
