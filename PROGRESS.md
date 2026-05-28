# 项目工作日志

## 项目概述

为基金投资者构建一个医药板块风险收益比监控系统。从"预测下周涨跌"的 XGBoost 模型开始，经历方法论重构、多轮 Bug 修复和实用化改造，最终定型为基于五规则的极端超跌状态检测器，支持每日自动运行、微信推送和可视化看板。

---

## 第一章：方案设计与初始搭建

### 需求讨论

用户需求：通过因子分析预测股市板块/金价，辅助基金投资决策。

经过讨论确定：
- 预测标的：申万医药生物指数（801150），与黄金驱动逻辑互补
- 预测周期：周频为主，日频聚合（周频噪声可控、与宏观因子频率匹配）
- 输出形式：方向判断 + 幅度预测，含稳健性检验
- 因子不固化，灵活可扩展
- 严格时间序列切分训练/测试集
- 数据源全部免费（AKShare + FRED）
- 技术栈：Python + Jupyter Notebook

### 创建项目骨架

```bash
mkdir -p config data/raw data/processed data/manual \
  src/data_fetcher src/factors src/features src/models src/backtest \
  src/utils notebooks app
```

安装依赖（使用清华镜像解决国内 pip 超时）：

```bash
pip install akshare yfinance pandas-datareader xgboost shap \
  scikit-learn jupyter plotly openpyxl seaborn \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 数据采集模块

**AKShare 数据源** (`src/data_fetcher/akshare_source.py`)：
- 探索 AKShare 实际可用 API：`index_hist_sw`（申万行业指数）、`stock_zh_index_daily`（大盘指数）、`stock_hsgt_hist_em`（北向资金）、`futures_foreign_hist`（COMEX 黄金期货）、`macro_china_pmi`、`macro_china_cpi`、`macro_china_ppi`、`macro_china_money_supply`（M2）、`macro_china_market_margin_sh/sz`（融资融券）、`stock_board_concept_index_ths`（概念板块）、`currency_boc_sina`（USD/CNY 汇率）、`spot_golden_benchmark_sge`（上海金交所）
- 函数签名与文档不完全一致，逐一测试确认参数格式
- 申万医药代码为 `801150`，COMEX 黄金代码为 `GC`

**FRED 数据源** (`src/data_fetcher/fred_source.py`)：
- 通过 `pandas_datareader` 获取美国宏观数据
- 序列包括：DGS10（10Y 利率）、DGS2（2Y 利率）、DFII10（TIPS 实际利率）、FEDFUNDS（联邦基金利率）、CPIAUCSL（CPI）、UNRATE（失业率）、T10Y2Y（利差）

**YFinance 数据源** (`src/data_fetcher/yfinance_source.py`)：
- 用于获取 GLD（黄金 ETF）、GC=F（黄金期货）、DXY（美元指数）、VIX（恐慌指数）
- 在中国网络环境下被限流（YFRateLimitError），实际不可用
- 后续通过 AKShare 的 `futures_foreign_hist(symbol="GC")` 替代

**发现**：
- AKShare API 版本间差异大（`sw_index_daily` 变更为 `index_hist_sw`）
- `index_analysis_daily_sw` 内部编码 bug（中文字段丢失），改用 `index_hist_sw`
- `bond_china_yield` 数据仅到 2021 年，太旧不可用
- `currency_boc_sina` 仅返回最近约 180 行数据

### 因子体系

创建 `Factor` 基类 + 因子注册表模式，共设计约 44 个因子，分四大类：
- 宏观：美债利率/利差、实际利率、美元指数、VIX、联邦基金利率、CPI、失业率、中国 CPI/PPI/PMI/M2、中美利差
- 市场：多周期动量、成交额、北向资金、超额收益、行业轮动强度
- 技术：RSI、MACD、布林带、波动率、量比、均线排列、价格位置
- 情绪：GLD 持仓变化、PE/PB 分位、政策事件（占位）、搜索指数（占位）

因子注册表（`config/factor_registry.py`）声明式注册，增删条目即可切换因子组合。

### 特征工程

`src/features/engineer.py`：滞后（1/2/4 周）、滚动统计（4/13 周均值/标准差）、一阶差分。

---

## 第二章：XGBoost 模型尝试（已废弃）

### V1：36 因子预测下周涨跌

**操作流程**：
1. 从 AKShare + FRED 拉取 2020-01 至今的全部数据
2. 用 `FactorPipeline` 批量计算 36 个因子
3. 用 `align_factors_with_target` 对齐因子与下周收益率
4. 因子筛选：`FactorScreener` 按 IC/IC_IR/VIF 筛选
5. 时间序列切分：前 80% 训练，后 20% 测试
6. 特征工程：对每个因子做滞后+滚动+差分
7. StandardScaler 标准化
8. 训练 XGBoost Classifier（方向）和 Regressor（幅度）
9. TimeSeriesSplit 5 折交叉验证

**初始结果**：声称准确率 56.98%、Hit Ratio 59.30%

**严格统计检验暴露问题**：
- Binomial Test：P-value = 0.87，无法拒绝"模型无效"假设
- Permutation Test（200 次打乱标签重新训练）：真实模型在 69 分位，31% 的假模型表现更好
- 结论：模型没有可证明的预测能力

**排查发现三处致命数据泄露**：
1. 因子筛选在全部 428 周数据上做 IC 分析，测试集参与了因子选择
2. 月频数据（CPI/PPI/M2）前向填充，月末标注的 PPI 实际要到次月中旬才公布
3. 特征工程递归叠加（add_lags → add_rolling → add_diff 依次对所有列操作），5 个原始因子最终产生 200 个特征，样本/特征 = 1.7:1

**修复所有泄露后**：准确率降至 46.51%，跑输"永远做多"基准（52.33%）。

### V2：XGBoost 预测拐点

**操作流程**：
1. 用 `scipy.signal.argrelextrema(order=8)` 标注历史底部（T 是 T±8 区间最低点）
2. 用 TurningPointFeatures 构建拐点专属特征（ERP 分位、成交量占比、底背离、美债二阶导、融资背离）
3. 用 `scale_pos_weight` 处理样本不平衡（正负比 1:23）
4. 训练 XGBoost Classifier

**结果**：模型完全不发信号——学会了"永远说没底"来最小化误差。正样本仅 14 个，模型根本无法学习。

### 关键教训

- 用 Accuracy 评估极度不平衡事件毫无意义（永远输出 0 就有 96% 准确率）
- 预测"每一周涨跌"本质是在预测噪声
- 数据泄露的三个主要来源：特征筛选在全集上做、月频数据未做发布时滞、特征工程叠加爆炸
- 极稀疏事件（4.2%）不适合梯度提升树，需要完全不同的方法论

---

## 第三章：规则探测器 V3

### 方法论转变

不再预测每一周，改为识别极端超跌状态。用五条经济含义明确的简单规则，多数表决产生信号。

### 五规则设计

```
Score = Rule_R + Rule_D + Rule_C + Rule_P + Rule_M
Signal = (Score ≥ 2)
```

| 规则 | 条件 | 阈值来源 |
|:----:|------|----------|
| R（RSI 超卖） | RSI(14) < 30 | 底部 RSI 均值 35.2 vs 正常 51.2，p=0.0002 |
| D（深度回撤） | 13 周最大回撤 < -10% | 底部回撤均值 -14.4% vs 正常 -5.9%，p<0.0001 |
| C（极度便宜） | 5 年价格分位 < 15% | 底部均值 36.3 vs 正常 52.3，p=0.059 |
| P（恐慌指数） | 偏度 < -1 或波动率 > 2.5 年 80 分位 | 捕捉极端左尾事件 |
| M（聪明钱） | ETF 份额逆势增长 | 价跌+份额增 |

### 拐点标注

```python
from scipy.signal import argrelextrema
mins = argrelextrema(values, np.less, order=8)[0]
# T 时刻是 [T-8, T+8] 区间内的最低点 → label=1
```

标注结果：18 个底部、15 个顶部（2018-2026），底部占全部观测的 4.2%。

### 评估结果（测试期 2024-10 ~ 2026-05）

四个测试期底部：
- 2025-01-10：急跌底，D+C 规则触发 → 命中
- 2025-04-18：慢跌底，C+P 规则触发 → 命中
- 2026-01-02：温和调整底，指标均未达极端 → 漏检
- 2026-03-20：温和调整底，DD 逼近但未突破 -10% → 漏检

### V3 结论

Precision（信号级）= 47%，底部级 Recall = 50%。MFE/MAE：Armed 信号后 13 周期望收益 +5.0%，胜率 60%。

---

## 第四章：V3 Bug 修复（多轮）

### 第一轮：tracker 硬编码、灵敏度不对齐

**问题 1**：`app/tracker.py` 中 Rule P 显示逻辑写死了 `vol > 50`，与 `turning_points.py` 中的动态 80 分位不一致。

**操作**：`_compute()` 中不再手工重算规则状态，改为从 `df` 列直接读取 `latest["rule_panic"]` 等。

**问题 2**：Rule M 在 UI 中永远显示 False。

**操作**：同上，改为直接从 `latest["rule_micro"]` 读取。

**问题 3**：`sensitivity_analysis()` 只用 3 条规则（RSI+DD+Cheap），而主模型是 5 条规则。

**操作**：重写 `sensitivity_analysis`，使用 `_compute_five_rules()` 辅助函数，与主模型完全一致。此前 REPORT 中 Precision 80% 的错误数字就是来自 3 规则简化模型。

**问题 4**：`mfe_mae_summary()` 对 MAE 列也计算 `win_rate`，而 MAE 始终 ≤0，`win_rate` 恒为 0 毫无意义。

**操作**：区分列类型——ret/mfe 列用 `win_rate(>0)`，mae 列改用 `pct_exceed_5pct(<-5%)`。

### 第二轮：FN 虚高、min_periods、列名

**问题 5**：`evaluate_signals()` 的 `bottoms` 包含全部 18 个历史底部，而 `sigs` 仅来自测试期。历史底部在测试期必然找不到信号，全部错误计入 FN。

**操作**：添加 `bottoms_in_test` 过滤——先按 `label==1` 和时间区间筛选，再计算 FN。同时新增双层指标：`precision`（信号级）和 `recall_bottom`（底部级）。

**问题 6**：`_compute_five_rules()` 中 Rule C 的 `rolling(260)` 缺少 `min_periods=52`，与主模型不一致。

**操作**：添加 `min_periods=52`。

**问题 7**：`label_turning_points()` docstring 写 `label_desc`，实际返回列名为 `desc`。

**操作**：列名改为 `label_desc`。

### 第三轮：CPI 失真、margin 对齐、RSI 算法

**问题 8**：`fred_source.py` 的 `_cpi_to_yoy()` 使用 `pct_change(periods=12)`——数据已 `resample("D").ffill()` 变为日频，12 期 = 12 天涨幅，而非同比。

**操作**：改用 `df["value"].shift(freq=pd.DateOffset(years=1))` 精确对齐一年前。

**问题 9**：`akshare_source.py` 的 `fetch_margin_data()` 沪深相加使用 DataFrame 整数 Index 对齐，而非 date 对齐。sh 和 sz 各自过滤后保留原始 RangeIndex，不同日期对应不同 Index 位置，加法产生大量 NaN。

**操作**：先用 `merge(on="date")` 对齐，再相加。

**问题 10**：`akshare_source.py` 的 `fetch_cn_ppi()` 使用 `[c for c if "同比" in str(c)][0]` 动态取列名。

**操作**：改为固定列名 `"当月同比增长"`，与其他方法一致。

**问题 11**：RSI 使用 `rolling(period).mean()`（SMA），报告声称 Wilder 平滑。

**操作**：改为 `ewm(alpha=1/period, adjust=False).mean()`，即 Wilder smoothing。SMA RSI = 28.8（触发），Wilder RSI = 33.3（不触发），Wilder 更保守。

**问题 12**：价格分位使用 `(x.iloc[-1] > x).mean() * 100`，非标准 percentile 定义。

**操作**：改为 `scipy.stats.percentileofscore(x, x.iloc[-1], kind='rank')`。

### 第四轮：死代码清理

**操作**：
- 删除 `config/settings.py`、`config/factor_registry.py`、整个 `config/` 目录
- 删除 `src/factors/`（全部 44 个旧因子类）
- 删除 `src/features/screening.py`、`src/utils/`
- 删除 `src/models/evaluate.py`、`src/models/classifier.py`、`src/models/regressor.py`、`src/models/train.py`、`src/models/train_v2.py`、`src/models/validate.py`
- 删除 `src/backtest/simple_backtest.py`
- `fred_source.py` 删除未使用的 `__init__` 和相关 import
- `manual_input.py` 和 `yfinance_source.py` 将 `config.settings` import 改为内联路径定义

清理后保留 22 个文件。

---

## 第五章：方法论深度重构 V4

### 核心批判（外部审查）

1. 标签定义的 look-ahead bias：`argrelextrema(order=8)` 使用未来 8 周信息
2. ±2 周容忍区间叠加后，一个"底部区域"长达 12-16 周，大量自然企稳被计入成功
3. 小样本（18 个底部）下统计不可靠
4. 连续信号重复计数，Precision 虚高
5. 规则可能高度共线（RSI/DD/Cheap 都源于价格下跌）
6. MFE/MAE 前向窗口重叠，非独立样本
7. 人工阈值 = 数据挖掘
8. 用 Precision/Recall 评估 regime detection 不合适

### V4.0：标签改为前向收益

**操作**：
1. 创建 `label_buying_opportunities()`：
   ```python
   # 时刻 T 买入, 持有 13 周
   # 总收益 > 5% AND 前 4 周最大回撤 > -8%
   # → label = 1（好买点）
   ```
2. 126/429（29.4%）为好买点（vs V3 的 18 个局部极值）
3. 仅 12/18（67%）的 V3 底部是 V4 好买点——局部极值 ≠ 可盈利买点

### V4.1：Triple Barrier + 条件期望 + 条件概率

**操作**：
1. 创建 `triple_barrier_labels()`：路径依赖，先触及 +8% = SUCCESS，先触及 -5% = FAIL，到期未触及 = NEUTRAL
2. 创建 `collapse_labels()`：连续同向标签合并为独立机会，134→12
3. 创建 `conditional_return_analysis()`：比较 E[ret|Armed] vs E[ret]
4. 创建 `rule_conditional_prob()`：计算 P(A=1|B=1) 替代 Pearson r
5. 创建 `collapse_signals()`：连续 Armed 信号合并为交易机会
6. 更新 MFE/MAE：13 周 lockout 防止窗口重叠，新增 benchmark 随机买入对照

**关键发现**：
- P(DD=1|RSI=1) = 1.0（RSI 超卖时回撤必超 -10%），但 P(RSI=1|DD=1) = 0.04
- RSI-DD 条件概率 r=0.18，规则之间具有实质性独立性
- E[ret|Armed] = +8.4%，E[ret] 无条件 = +0.7%，uplift = +7.7%
- Benchmark 对照：13 周 Armed +8.4% vs 随机买入 +1.8%，alpha = +6.6%

### V4.2：去前瞻偏差 + Barrier 敏感性

**操作**：
1. `collapse_signals`：保留 cluster **第一条**（最早可操作），而非最高 score（实盘无法判断）
2. 创建 `barrier_sensitivity()`：测试 (+6/+8/+10) × (-3/-5/-7) 共 9 组参数
3. CPI 同比改用 `pd.DateOffset(years=1)` 处理闰年

**关键发现**：uplift 在全部 9 组参数下稳定在 +7.9%，不依赖特定 barrier 参数选择。

---

## 第六章：实用化改造 V4.3

### Distance-to-Trigger（反推目标价）

**操作**：
1. 创建 `distance_to_trigger()`：
   - Rule D：`trigger = 13周最高价 × 0.90`
   - Rule C：`trigger = 5年价格序列第 15 百分位`
   - Rule R：近似值（RSI 递归无法精确反推）
2. 在 `tracker.py` 的 CLI 输出中添加"距离触发"段
3. 每天输出：当前价 → 触发价 → 还需跌多少

### 三级警报系统

**操作**：
1. 创建 `alert_level()`：
   - SILENT：Score=0，距触发 >3%
   - YELLOW：Score=1 或距触发 <3%
   - RED：Score≥2 且之前 <2（状态翻转）
2. 在 `tracker.py` 中读取上一轮 Score（从 `signal_history.csv`）来判断是否状态翻转

### 水位线 Dashboard

**操作**：
1. 创建 `app/dashboard.py`，生成自包含 HTML 文件
2. 使用 Lightweight Charts（CDN 加载，无需安装）
3. 走势图上叠加两条水平虚线：红线（回撤触发价）和绿线（估值触发价）
4. 仓位建议：Score 0-1 → 0%，Score 2 → 15-30%，Score 3 → 50%，Score 4-5 → 70%
5. 规则状态、历史 Armed 信号表、关键指标面板

### 推送通知模块

**操作**：
1. 创建 `app/notify.py`：
   - `push_serverchan()`：Server酱（免费微信推送）
   - `push_pushdeer()`：PushDeer
   - `push_webhook()`：自定义 Webhook
   - `push()`：尝试所有渠道 + GitHub Actions summary
2. SILENT 静默不推送，YELLOW/RED 自动推送
3. `--test` 模式强制发送测试推送验证配置
4. `--dry-run` 模式仅打印不推送

### GitHub Actions CI 配置

**操作**：
1. 安装 Server酱 → 获取 SendKey
2. Windows 设置永久环境变量：
   ```powershell
   [Environment]::SetEnvironmentVariable("PUSH_KEY", "SCT...", "User")
   ```
3. 项目推送到 GitHub：
   ```bash
   git init && git add . && git commit -m "..."
   git remote add origin https://github.com/ytzmzmq/financial_analysis.git
   git push -u origin main
   ```
4. GitHub Settings → Secrets → 添加 `PUSH_KEY`
5. 创建 `.github/workflows/medical_tracker.yml`：每交易日 14:45 运行
6. 调试 CI 问题：
   - `grep -oP` 兼容性 → 改用 Python `ci_parse.py`
   - `matplotlib` ModuleNotFoundError → 删除未使用的 import（CI 不装但文件顶部 import 了）
   - 网络超时 → 加 `timeout-minutes: 20`、`timeout 900` 命令
   - 权限不足 → 添加 `permissions: contents: write, issues: write`
   - `git push` 失败时不影响 CI 状态 → 加 `|| true`

### 本地 vs 云端

- 本地：`python app/notify.py`（CLI）或 `python app/dashboard.py`（生成看板）
- 云端：GitHub Actions 每交易日自动运行，网络波动时需手动重试 push
- Cloudflare 加速：部分 push 失败可通过 `gh auth login` 或设置代理解决

---

## 最终系统

### 文件清单

```
financial_analysis/
├── REPORT.md                              # 方法论报告 V4.3
├── PROGRESS.md                            # 本文件
├── requirements.txt
├── app/
│   ├── tracker.py                         # CLI 跟踪器
│   ├── dashboard.py                       # HTML 看板生成器
│   ├── notify.py                          # 推送通知模块
│   └── ci_parse.py                        # CI 输出解析
├── src/
│   ├── data_fetcher/
│   │   ├── __init__.py
│   │   ├── akshare_source.py              # AKShare 数据采集
│   │   ├── fred_source.py                 # FRED 数据采集
│   │   ├── yfinance_source.py            # Yahoo Finance（备用）
│   │   ├── manual_input.py               # 手动 CSV 导入
│   │   └── ocr_capture.py                # 截图 OCR
│   └── models/
│       ├── __init__.py
│       └── turning_points.py              # 核心：Triple Barrier + 五规则
│                                          # + Bootstrap + 条件期望
│                                          # + 距离触发 + 警报
├── .github/workflows/medical_tracker.yml  # 每交易日 14:45 自动运行
├── .gitignore
└── data/manual/_template.csv
```

## 第八章：实时看板与 ETF 代理（最新）

### 实时看板服务器

创建 `app/server.py`：HTTP 服务器，浏览器打开 `http://127.0.0.1:8888`，F5 刷新即拉取最新数据重新计算。

### ETF 代理实时价格

`fetch_sw_medical` 通过 `ak.fund_etf_spot_em()` 抓取 512290（生物医药ETF）盘中涨跌幅，等比例映射到申万医药指数。周末自动跳过。

### 极速模式

server.py 仅拉取 `sw_medical` 数据（跳过宏观数据），耗时从 14s 降至 <1s。

### 试算功能

网页右上角输入框，输入任意点位（如 7430），点击按钮即基于该价格重新计算 Score 和触发价。

### 图表去重

lightweight-charts 遇重复时间轴会崩溃，前端加 `uniqueData` 去重+排序。

### 近期 Bug 修复

- `collapse_labels` cluster 逻辑错误：`clusters[1:]` → `cluster[1:]`
- `alert_level` 返回 `"green"` → `"silent"`（notify.py 只识别 silent/yellow/red）
- Rule C 触发价：`rank().idxmin()` → `quantile(0.15)`
- ETF 接口：`stock_zh_a_spot_em()` → `fund_etf_spot_em()` → 最终改用直接 `requests` 调用东方财富 API
- tracker 同一天重复追加 history → 按日期去重
- 日期截断导致本周数据丢失 → 配合实时代理移除截断
- **实时数据（V4.5）**：最终方案——Sina 财经 API 抓取 512170(医疗ETF华宝)实时涨跌幅，等比例映射 801150。国内网络无障碍，映射误差 <0.1%。全量稳健性检验通过：所有指标与原始 EOD 数据源一致（uplift +7.7%, CI [+0.2%,+16.3%]）。图表库首次下载后内联到 HTML，完全离线可用

### 核心模块 `turning_points.py` 功能清单

| 函数/类 | 用途 |
|---------|------|
| `triple_barrier_labels()` | 路径依赖标签（+8%/-5%，13周） |
| `collapse_labels()` | 连续同向标签合并 |
| `TurningPointDetector` | 五规则探测器（RSI Wilder/DD/Cheap/Panic/Micro） |
| `collapse_signals()` | 连续 Armed 信号合并（保留第一条） |
| `rule_conditional_prob()` | 条件概率 P(A=1\|B=1) |
| `conditional_return_analysis()` | E[ret\|Armed] vs E[ret] |
| `forward_return_analysis()` | 去重叠 + benchmark 对照 |
| `mfe_mae_summary()` | 区分 armed/benchmark 汇总 |
| `bootstrap_ci()` | Bootstrap 置信区间 |
| `sensitivity_analysis()` | 五规则参数网格搜索 |
| `barrier_sensitivity()` | Triple Barrier 参数敏感性 |
| `distance_to_trigger()` | 反推目标价（Rule D/C/R） |
| `alert_level()` | 三级警报（SILENT/YELLOW/RED） |
| `evaluate_signals()` | 双层评估（信号级 Precision / 底部级 Recall） |

### 使用方式

```bash
# 本地命令行
python app/tracker.py                     # 信号 + 距离触发 + 警报

# 推送通知
python app/notify.py                      # 正常模式（SILENT 自动静默）
python app/notify.py --test               # 测试推送通道
python app/notify.py --dry-run            # 仅打印不推送

# 可视化看板
python app/dashboard.py                   # 生成 dashboard.html
start dashboard.html                      # 浏览器打开

# 云端（配置 GitHub Secrets 后）
# 每交易日 14:45 自动运行，YELLOW/RED 自动推送
```

### 核心结论

- E[ret|Armed] 13周 = +8.4%（unconditional = +0.7%，uplift = +7.7%）
- Uplift 对 Triple Barrier 参数不敏感（9 组参数组合均稳定在 +7.9%）
- 条件 Hit ratio = 70%（无条件 = 48%）
- 定位：极端超跌状态检测 / 风险收益比监控器（非底部预测器）
