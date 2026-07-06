# 医药板块风险收益比监控器

基于 V5.2 四因子分级判定的极端超跌状态检测系统，监控申万医药生物指数(801150)。不是底部预测器，是赔率改善状态识别器。

## 快速开始

```bash
pip install pandas numpy scipy akshare openpyxl

python app/tracker.py          # CLI 查看当前信号
python app/server.py           # 启动实时看板 http://127.0.0.1:8888
python app/monthly_audit.py    # 生成月度因子审计报告
```

看板打开后顶部有两个 Tab：「实时监控」显示当前 Score、因子状态、Tier 分级、距离触发水位线、近两年周线图；「历史信号」显示 SQLite 中积累的所有历史记录和 Score 趋势图。页面会自动拉取 AKShare 数据，每次刷新都是最新的。试算框可以输入假设点位看"跌到多少会触发"。

如果数据源出问题（AKShare 拉不到、数据过旧、数据量不足），页面顶部会出现红色或黄色横幅，同时错误记录在 SQLite 的 system_log 表里。

## 架构说明

```
app/
  tracker.py          信号计算引擎，CLI/Web 共用
  server.py           HTTP 看板服务器 (stdlib http.server, 无框架依赖)
  db.py               SQLite 存储：signals 表(信号历史) + system_log 表(错误日志)
  dashboard.py        生成自包含 HTML 看板(离线可用)
  notify.py           微信推送(Server酱/PushDeer/Webhook)
  monthly_audit.py    月度因子审计：稳健性检验 + 新因子发现
  ci_parse.py         GitHub Actions 输出解析

run_tracker.bat       Windows 任务计划用，每天 14:45 执行 tracker.py
run_audit.bat         Windows 任务计划用，每月 1 号 09:00 执行审计

src/
  models/rule_registry.py     统一规则引擎：RULE_DEFS + MODEL_CONFIGS + evaluate_signal
  models/indicators.py        共享技术指标（rsi_wilder, macd_histogram 单一来源）
  models/turning_points.py    distance_to_trigger + alert_level + Triple Barrier
  models/factor_optimizer.py  五阶段因子筛选框架
  data_fetcher/akshare_source.py  AKShare 数据源(含 Sina ETF 实时代理)
  data_fetcher/fred_source.py     FRED 美国宏观数据

data/processed/
  signals.db          SQLite 数据库(自动创建，旧 CSV 数据自动迁移)
  audit_report.md     最近一次月度审计报告
  tracker_log.txt     定时任务执行日志
  audit_log.txt       审计执行日志
```

数据存储全部本地化：信号历史写入 SQLite（`data/processed/signals.db`），错误日志也写同一张库的 system_log 表。旧的 `signal_history.csv` 在首次运行时自动导入 SQLite，之后不再使用。

## 定时任务

两个 Windows 任务计划程序条目，全免费，不需要服务器：

```bash
# 每天 14:45 自动跑 tracker，信号写入 SQLite
schtasks /create /tn "医药板块Tracker" /tr "D:\financial_analysis\run_tracker.bat" /sc daily /st 14:45 /rl highest

# 每月 1 号 09:00 跑因子审计，报告输出到 data/processed/audit_report.md
schtasks /create /tn "月度因子审计" /tr "D:\financial_analysis\run_audit.bat" /sc monthly /d 1 /st 09:00 /rl highest
```

14:45 选在收盘前 15 分钟，能抓到当天尾盘数据。审计选月初是为了在月初评估上月因子表现，有足够时间决定是否调整模型。

bat 文件里的 `PROJECT_DIR` 和 `PYTHON` 路径需要根据实际环境修改。

## 月度审计说明

`monthly_audit.py` 分两部分：

Part A 检验当前四因子(L1/M1/S3/V1)的稳健性。滚动窗口稳定性对比近 3 年和全历史的条件收益，偏差超过 50% 标记为"漂移"。触发频率漂移检查近半年 vs 全历史的触发率。信号复盘分两部分：A3a 从 SQLite 取真实 live 信号复盘，A3b 用当前模型对全历史做 retrospective replay。A5 按 signal_tier 分组统计组合表现（胜率、平均/中位收益）。

Part B 运行完整的五阶段因子优化流水线，与当前 MODEL_CONFIGS 配置对比。如果有新因子通过筛选或旧因子不再通过，会在报告末尾建议更新 `rule_registry.py` 中的模型配置。报告只生成不自动执行——是否采纳由你决定。

---

## 搬运到新机器

以下步骤基于 Windows 11 环境。

### 1. 装 Python

去 python.org 下载 Python 3.13 安装包，安装时勾选 "Add to PATH"。安装完后打开 CMD 确认：

```bash
python --version
```

### 2. 拷贝项目

把整个 `financial_analysis` 文件夹拷到新机器的目标位置（比如 `D:\financial_analysis`）。项目里没有任何编译产物或环境绑定，纯 Python + SQLite，直接拷即可。

`data/processed/signals.db` 也一起拷，里面是历史信号记录。`data/lightweight-charts.min.js` 拷不拷都行，首次启动 server.py 会自动从 CDN 下载。

### 3. 装依赖

```bash
cd D:\financial_analysis
pip install pandas numpy scipy akshare openpyxl
```

就这五个包，没有 Flask/FastAPI/Streamlit 之类的重型依赖。`sqlite3` 是 Python 自带的。

### 4. 验证能跑

```bash
python app/tracker.py
```

正常情况下会拉取 AKShare 数据并输出信号。如果报网络错误，检查是否需要代理（AKShare 走的是东方财富和新浪的接口）。

```bash
python app/server.py
```

浏览器会自动打开 `127.0.0.1:8888`，看到看板就说明一切正常。

### 5. 注册定时任务

修改 `run_tracker.bat` 和 `run_audit.bat` 里的 `PROJECT_DIR` 路径，然后以管理员身份执行：

```bash
schtasks /create /tn "医药板块Tracker" /tr "D:\financial_analysis\run_tracker.bat" /sc daily /st 14:45 /rl highest
schtasks /create /tn "月度因子审计" /tr "D:\financial_analysis\run_audit.bat" /sc monthly /d 1 /st 09:00 /rl highest
```

验证任务是否注册成功：

```bash
schtasks /query /tn "医药板块Tracker"
schtasks /query /tn "月度因子审计"
```

### 6. 可选：微信推送

如果需要 YELLOW/RED 警报推送到微信，配置 Server酱：

```bash
# 设置环境变量（系统级）
setx PUSH_KEY "你的Server酱SendKey"

# 测试
python app/notify.py --test
```

不配置也完全不影响使用，错误和信号都会写本地 SQLite，页面上能看到。

### 搬运检查清单

- [ ] Python 3.13 已安装，`python --version` 正常
- [ ] `pip install pandas numpy scipy akshare openpyxl` 完成
- [ ] `python app/tracker.py` 能输出信号
- [ ] `python app/server.py` 能打开看板
- [ ] `run_tracker.bat` 和 `run_audit.bat` 路径已修改
- [ ] 两条 schtasks 已注册并验证
- [ ] (可选) Server酱 PUSH_KEY 已配置
