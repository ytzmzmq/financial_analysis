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

---

## 第八章：监控基础设施 (2026-07-07)

### 背景

V5.1 模型定型后，原有的信号持久化依赖 `signal_history.csv`，没有错误处理机制，因子稳健性只能手动跑 optimizer 验证。需要将"手动跑脚本"升级为"自动运行 + 自动报警 + 定期自检"的完整监控链路，同时为搬运到新机器做准备。

### 设计决策

存储选型选了 SQLite 而不是继续用 CSV，原因是 CSV 只能存两个字段（date/score），而我们需要记录完整的信号快照（armed 状态、三因子触发情况、触发价位等）来支持后续的因子审计。SQLite 是 Python 内置的，零依赖零成本，且支持结构化查询。

错误处理采用"写库 + 页面展示"方案而非推送通知，因为用户大部分时间在本地看页面，推送只在 YELLOW/RED 时使用。数据源错误（AKShare 网络问题）和计算错误（因子计算异常）分层捕获，写入 system_log 表，前端页面顶部自动拉取并显示横幅。

因子审计选择月度频率 + 只生成报告不自动切换模型。自动切换模型风险太高——因子筛选的结果对小样本敏感，人工审核后再决定是否更新评分卡更稳妥。

### 实现细节

**db.py** 提供三个核心函数：`save_signal`（写入信号，INSERT OR REPLACE 按日期去重）、`get_history`（读取历史，按日期倒序）、`get_latest_score`（获取上一次 score 用于 alert_level 计算）。另加 `log_error` 和 `get_recent_errors` 用于错误日志。首次运行自动检测旧 CSV 并迁移数据。数据库文件路径硬编码为项目根目录下的 `data/processed/signals.db`，不依赖工作目录。

**tracker.py** 的 `_compute` 函数改用 SQLite 持久化，并增加试算模式判断（`custom_price is not None` 时不写库）。`run_cli` 函数加了三层 try/except：数据拉取、数据解析、信号计算分别捕获异常并写入 system_log。数据新鲜度校验（超过 7 天告警）和数据量校验（少于 52 周告警）作为 warning 级别记录。

**server.py** 新增三个路由：`/api/history`（从 SQLite 读历史信号）、`/api/errors`（读最近 24h 错误日志）。前端加了 Tab 切换（实时监控 / 历史信号），历史 Tab 包含信号表格（日期/Score/价格/警报级别/三因子状态/触发价）和 Score 趋势图（带 3.5 分 Armed 虚线）。错误横幅在页面加载时自动检查，有错误显示红色/黄色，无错误自动隐藏。同时清理了原有重复定义的 `_serve_api` 方法。

**monthly_audit.py** 分 Part A 和 Part B。Part A 做三项稳健性检验：滚动窗口稳定性（近 3 年 vs 全历史的条件收益，偏差 >50% 标"漂移"）、触发频率漂移（近半年 vs 全历史）、信号质量回顾（最近 10 次 Armed 的 13 周前瞻收益）。Part B 运行 `run_full_pipeline` 全流程，对比当前 V5 评分卡的三个因子，标注新通过和不再通过的因子，给出候选评分卡建议。报告输出为 markdown。

**定时任务** 通过 Windows 任务计划程序实现：`run_tracker.bat` 每天 14:45 执行（收盘前 15 分钟抓尾盘数据），`run_audit.bat` 每月 1 号 09:00 执行。两个 bat 文件都把日志追加到 `data/processed/` 下对应的 log 文件。

### 新增/修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/db.py` | 新增 | SQLite 存储模块（signals + system_log 表） |
| `app/monthly_audit.py` | 新增 | 月度因子审计脚本 |
| `run_tracker.bat` | 新增 | 每日定时任务批处理 |
| `run_audit.bat` | 新增 | 每月定时任务批处理 |
| `README.md` | 新增 | 使用说明 + 新机搬运指南 |
| `app/tracker.py` | 修改 | CSV→SQLite，三层 try/except，数据校验 |
| `app/server.py` | 修改 | 历史 Tab、错误横幅、/api/history、/api/errors、清理重复方法 |
| `.claude/CLAUDE.md` | 修改 | 更新架构说明 |

---

## 第九章：V5.2 重构 — 四因子两层判定 (2026-07-07)

### 背景

V5.1 使用 3 因子评分卡（M1=4.5/S3=3.0/V1=2.5，阈值 3.5），单因子 M1 权重占 45%。存在三个结构性问题：缺少量价维度因子（RSI 等指标未纳入），Score 阈值一刀切无法区分信号强度，计算逻辑和模型参数耦合在 V5Detector 类中导致维护困难。

### 设计决策

按外部评审意见的 7 阶段顺序执行：指标收口 → 规则引擎 → DB 扩展 → 消费方改造 → 月审升级 → 切配置 → 清理。核心原则是"统一规则入口"——所有信号判定通过 `evaluate_signal()` 一个函数完成，消费方（tracker/server/dashboard/monthly_audit）只做展示，不理解模型。

V5.2 采用两层判定替代单一 Score 阈值。第一层 n_factors >= 2 做准入（防单因子误触发），第二层按因子组成分级（strong/standard/weak/hold）。Score 降为辅助显示变量。

### 实现细节

**indicators.py** 新建共享指标模块，消除 factor_optimizer.py 和 turning_points.py 中重复的 `_rsi_wilder` 和 `_macd_histogram` 实现。

**rule_registry.py** 新建统一规则引擎。`RULE_DEFS` 定义 4 个因子的完整元数据（名称/维度/条件/显示文本/阈值描述），`MODEL_CONFIGS` 按版本存储模型参数（V5.1 和 V5.2 并存），`evaluate_signal()` 返回 `SignalResult` dataclass，`evaluate_signal_history()` 返回全历史 DataFrame。切换模型版本只需改 `ACTIVE_MODEL_VERSION` 一行。

**db.py** 扩展 signals 表 6 列（model_version/signal_tier/n_factors/is_live_signal/factor_snapshot/l1_triggered），使用 `_ensure_column()` 实现幂等迁移，`get_latest_score` 返回 float，新增 `get_live_signals()` 查询 is_live_signal=1 的记录。

**tracker.py** 完全消费 `evaluate_signal()` 返回的 `SignalResult`，不再自己理解模型。CLI 显示改为 `HOLD [hold] (V5.2)` 格式，Score 去掉 /5。

**server.py** HTML 模板改为动态进度条（替代 5 段固定柱），添加 tier 显示标签。JS render 函数动态计算 `score/max_score*100%` 填充率，阈值线条件渲染（V5.1 画线，V5.2 不画）。API 返回新增 max_score/signal_tier/n_factors/model_version/score_threshold 字段。

**dashboard.py** 替换 V5Detector 为 evaluate_signal + evaluate_signal_history，规则展示从硬编码改为动态读取 rules_status。

**monthly_audit.py** A3 拆分为 A3a（从 SQLite 取 live 信号复盘）和 A3b（用 evaluate_signal_history 做 retrospective replay），新增 A5 按 signal_tier 分组的组合表现表（胜率/平均/中位收益）。所有硬编码的 CURRENT_FACTORS/CURRENT_SCORECARD 替换为 MODEL_CONFIGS 动态查找。Part B 审计建议指向 rule_registry.py 而非 V5Detector。

### 新增/修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/models/indicators.py` | 新增 | 共享技术指标单一来源 |
| `src/models/rule_registry.py` | 新增 | 统一规则引擎 (RULE_DEFS + MODEL_CONFIGS + evaluate_signal) |
| `src/models/factor_optimizer.py` | 修改 | 删除重复指标，改用 indicators.py |
| `src/models/turning_points.py` | 修改 | 删除重复指标，distance_to_trigger/alert_level 支持 config 参数 |
| `app/db.py` | 修改 | 扩展 6 列 + 幂等迁移 + get_live_signals |
| `app/tracker.py` | 修改 | 消费 evaluate_signal()，CLI 格式更新 |
| `app/server.py` | 修改 | 动态进度条 + tier 显示 + API 新字段 |
| `app/dashboard.py` | 修改 | 替换 V5Detector，动态规则展示 |
| `app/monthly_audit.py` | 修改 | A3 拆分 + A5 组合表 + MODEL_CONFIGS |
| `README.md` | 修改 | V5.2 版本描述、架构、审计说明 |
| `REPORT.md` | 修改 | 方法论报告同步 V5.2 |
| `.claude/CLAUDE.md` | 修改 | 架构说明和数据流同步 V5.2 |

---

## 第十章：外部因子探索与模型边界确认 (2026-07-13)

### 背景

V5.2 四因子模型（L1/M1/S3/V1）在月度审计中表现稳健（全 Tier 胜率 100%），但四个因子全部来源于医药板块自身的量价和资金数据。一个自然的扩展方向是：外部因子——跨市场传导、宏观外溢、产业链联动——是否能提供独立的预测信息？

### 第一轮：宏观外溢因子（S4/E1/E2）

在 `factor_optimizer.py` 的 `build_factor_pool()` 中新增 3 个候选因子，数据源全部来自 `akshare_source.py` 已有接口：

- **S4_north_diverge**：价格创13周新低 + 北向资金4周净流入逆势增加（资金面维度，"北向聪明钱左侧抄底"）
- **E1_market_bear**：沪深300处于熊市状态（低于200日均线）+ 医药处于低位（跨市场共振维度）
- **E2_m2_accel**：M2同比增速6个月加速（宏观流动性维度，"放水预期"）

数据管线改造：`tracker.py`、`monthly_audit.py`、`rule_registry.py`、`evaluate_signal()`/`evaluate_signal_history()` 全部增加 `north_w`/`hs300_w`/`m2_w` 三个参数的透传。`rule_registry.py` 的 `RULE_DEFS` 新增三个因子定义，但**未加入 `MODEL_CONFIGS`**——代码骨架保留，待后续审计重新评估。

通过完整的月度审计五阶段筛选。结果：3 个因子均未通过。

| 因子 | 失败原因 |
|------|----------|
| S4_north_diverge | 触发率过低（<2%），统计样本不足 |
| E1_market_bear | 与 V1_price_5y_low 条件概率 86.2%，高度共触发——两者都捕获"全面下跌"状态 |
| E2_m2_accel | 与 M1_skew_neg 条件概率 88.9%，实质冗余——M2加速期恰好是市场暴跌期 |

### 第二轮：跨市场生物医药指数（XBI/IBB）

测试美股/欧洲生物医药指数是否对国内医药板块有领先预测力。构建分析脚本测试 XBI（SPDR S&P Biotech ETF）和 IBB（iShares Biotechnology ETF）与 801150 的关系。

数据通过 yfinance 获取 XBI/IBB 历史日线，与 801150 对齐周频后分析。

结果：

- 同期相关性：801150-XBI = 0.224，801150-IBB = 0.271——弱相关
- 领先1周相关性：XBI → 801150 = 0.067——无预测力
- 因子筛选：仅 F3_xbi_rsi30（XBI RSI超卖）通过三漏斗，但与 L1_rsi_30 高度重叠（条件概率 >65%），去重后被淘汰

结论：全球生物医药指数不纳入因子池。中美医药板块受各自的监管周期、集采政策、医保制度驱动，联动性不足以构成交易信号。

### 第三轮：产业链因子（化工/食品饮料/房地产/消费者信心）

因果链假设：上游成本改善→制药利润提升（化工）、平行消费周期见底（食品饮料）、地产下行→防御配置切换（房地产）、消费信心→医疗支出（需求端）。

数据源确认：SW一级行业指数（801030化工、801120食品饮料、801180房地产）通过 `ak.index_hist_sw` 获取，化工期货（MA0甲醇、V0 PVC）通过 `ak.futures_zh_daily_sina` 获取，消费者信心指数通过 `ak.macro_china_xfzxx` 获取。

构建 10 个候选因子，覆盖 4 条因果链：

| 因果链 | 候选因子 | 结果 |
|--------|----------|------|
| 上游成本 | U1_chem_52w_low, U2_chem_crash, U3_chem_fut_low | 全部 F1（频率不达标）|
| 平行消费 | P1_food_52w_low, P2_food_rsi30, P3_food_leads | P1 F1频率，P2/P3 F2收益不达标 |
| 跨周期配置 | C1_realestate_defense, C2_realestate_crash | 全部 F1（频率不达标）|
| 需求端 | D1_cci_low, D2_cci_crash | D1 F1频率，D2 F2收益不达标 |

关键发现：板块间同期周收益率相关性不低（化工0.67、食品饮料0.62、房地产0.44），但领先-滞后相关性全部接近零（化工领先1周=-0.047，食品饮料+0.002，房地产+0.011）。化工期货与医药的相关性仅0.057。这意味着板块间是"被同一个宏观因子同时驱动"的同期共振，而非"A先跌然后传导到B"的因果链。

### 三轮探索的统一结论

三条扩展路径一致指向同一个结论：

1. 跨市场因子（XBI/IBB）→ 同期弱相关0.22，无领先性
2. 宏观外溢因子（北向/大盘/M2）→ 与现有因子高度共触发（>65%条件概率）
3. 产业链因子（化工/食品/房地产/消费者信心）→ 无领先性，同期共振不构成交易信号

V5.2 四因子模型保持原样是最优解。这四个因子之所以有效，恰恰因为它们都直接刻画了医药板块自身的量价结构和资金行为。未来因子挖掘应聚焦于医药行业内部指标——集采政策节奏、IND审批数据、医药ETF申赎、医保基金结余等。

### 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/models/factor_optimizer.py` | 修改 | 新增 S4/E1/E2 候选因子 + 外部数据透传 |
| `src/models/rule_registry.py` | 修改 | RULE_DEFS 新增 3 因子定义（未加入 MODEL_CONFIGS） |
| `app/tracker.py` | 修改 | _load_data + _compute 新增北向/沪深300/M2 数据 |
| `app/monthly_audit.py` | 修改 | 全部 6 处调用点透传外部数据，A3a NoneType 修复 |
| `src/data_fetcher/akshare_source.py` | 无修改 | 已有 north_flow/market_index/m2 接口 |

---

## 第十一章：审计方法论升级 — 稳定性监测层 + 组合统计 (2026-07-14)

### 背景

外部审核提出两项 P0 改进建议：(1) 评估因子时间稳定性，防止因子收益集中在某几年导致 Bootstrap 虚假通过；(2) 新增因子组合统计（Combo Statistics），让 tier 分级从经验判断走向数据驱动。

初始实现将时间稳定性作为第四道筛选漏斗，但发现对暴跌检测器类因子（M1/V1）过于激进——M1 触发集中在暴跌期是设计意图而非缺陷。最终方案将时间稳定性从"筛选漏斗"调整为"健康监测层（Monitoring Layer）"，不淘汰因子，仅输出 Stability Grade 供研究参考。

### 时间稳定性分析实现

在 `factor_optimizer.py` 中新增 `temporal_stability()` 函数，作为独立的健康监测层运行（不参与 `screen_factors()` 的筛选流程）。

实现细节：
- 将全历史切成 4 个重叠窗口（50% overlap，每窗口约 137 周）
- 每个窗口独立计算因子的 uplift（条件收益 - 无条件收益）
- 要求窗口内至少 3 次触发才计算 uplift，否则标记为 NaN
- 输出 Stability Grade（Stable / Regime-dependent / Declining / Unstable）而非 Pass/Fail
- **低频豁免**：总触发次数 ≤15 的因子若非 Stable 则标注"(低频)"，因为样本太少时窗口分析的统计效力不足
- 触发集中度通过 CV（变异系数）量化，CV > 0.8 且 uplift 正向 → Regime-dependent

### 组合统计 A6 实现

在 `monthly_audit.py` 中新增 `_combo_factor_statistics()` 函数，作为审计 A6 部分。

实现细节：
- 枚举当前 4 个活跃因子的所有非空组合（C(4,2)=6 + C(4,3)=4 + C(4,4)=1 = 11 种）
- 对每种组合统计：触发周数、已验证数、13周前瞻平均收益、胜率、Bootstrap CI
- 输出写入审计报告 A6 部分

### 首次审计运行的关键发现

**Part B 三漏斗筛选结果**：16 个候选因子中 4 个通过三漏斗：

| 因子 | 触发数 | 三漏斗 | Stability Grade | 说明 |
|------|--------|--------|----------------|------|
| L1_rsi_30 | 9 | 通过 | Stable (低频) | 触发极少但集中有效 |
| M1_skew_neg | 18 | 通过 | Regime-dependent | 触发集中在暴跌期，设计意图 |
| S3_margin_diverge | 20 | 通过 | Stable | 最稳定的因子 |
| V1_price_5y_low | 65 | 通过 | Declining | 近期 uplift 衰减，需监测 |

**A6 组合统计结果**（首次有数据的组合表现表）：

| 组合 | 触发数 | 已验证 | 平均收益 | 胜率 |
|------|--------|--------|----------|------|
| L1+V1 | 5 | 1 | 17.9% | 100% |
| M1+V1 | 2 | 2 | 18.9% | 100% |
| S3+V1 | 5 | 2 | 13.4% | 100% |
| L1+M1 | 1 | 1 | 17.9% | 100% |
| L1+S3 | 3 | 0 | 待验证 | N/A |

初步模式：含 V1 的组合收益最高（17-19%），S3+V1 相对最低（13.4%）。但样本量太小，尚不能据此调整 tier。

### 核心问题：时间稳定性对"暴跌检测器"因子的适用性

M1（偏度异常）在四漏斗模式下被淘汰的原因值得深入分析。M1 的 18 次触发高度集中在几次市场暴跌期（2018贸易战、2020疫情、2022杀估值），在正常市场窗口中几乎没有触发，因此窗口 uplift 不稳定。

但这里存在一个方法论悖论：**M1 的设计目的就是在暴跌期触发**，而暴跌本身就不是每个时间窗口都会发生的事件。一个"暴跌检测器"如果每个窗口都均匀触发，反而说明它不是好的暴跌检测器。

同理，V1（估值冰点）的近期 uplift 从 5.6% 下降到 3.4%，但这可能反映的是市场结构变化（医药板块估值中枢下移），而非因子本身失效——V1 在低估值时触发的信号仍然有正向收益，只是幅度变小。

A1 滚动窗口检验显示 M1 和 V1 都是"稳定"的（近3年条件收益偏差未超过 50%），说明它们在 A1 的粗粒度检验下没有问题，但在细粒度窗口分析中暴露了不稳定性。

### 最终方案：从"第四漏斗"转为"健康监测层"

经外部审核讨论后确定最终方案：时间稳定性分析从"第四道筛选漏斗"调整为"模型健康监测层（Monitoring Layer）"。

实现要点：
- `screen_factors()` 恢复为三漏斗筛选（稀疏度 → 收益 → Bootstrap CI），不淘汰任何通过三漏斗的因子
- `temporal_stability()` 函数输出 Stability Grade 而非 Pass/Fail 二值判定
- `run_full_pipeline()` 在三漏斗筛选之后单独运行监测层，报告所有通过因子的 Grade
- `monthly_audit.py` 在 Part A 和 Part B 之间新增"健康监测层"章节，展示活跃因子的 Grade

Stability Grade 分类体系：
| Grade | 判定条件 | 行为含义 |
|-------|----------|----------|
| Stable | ≥75% 窗口 uplift > 0，无衰减 | 因子在各市场阶段均有效 |
| Regime-dependent | 触发 CV > 0.8，触发时 uplift 正向 | 因子依赖特定市场状态（如暴跌），是设计意图 |
| Declining | 后半段 uplift < 前半段的 50% | alpha 衰减，需持续监测 |
| Unstable | 多数窗口 uplift ≤ 0 | 因子可能已失效 |

当前 4 因子评估结果：
| 因子 | Grade | 解读 |
|------|-------|------|
| L1_rsi_30 | Stable (低频) | 触发 ≤15 次，低频豁免，窗口统计效力不足 |
| M1_skew_neg | Regime-dependent | 触发集中在暴跌期，是设计意图而非缺陷 |
| S3_margin_diverge | Stable | 最稳定的因子，3/4 窗口 uplift 正向 |
| V1_price_5y_low | Declining | 近期 uplift 衰减（5.6%→3.4%），需下次审计验证是否持续 |

V5.2 MODEL_CONFIGS 维持四因子不变。监测层作为审计报告的参考信息，未来需要多次审计积累证据后才考虑触发 V5.3 版本更新。

### Evidence-based 架构升级

外部审核进一步建议将 Grade 从硬编码规则改为 Evidence-based 合成，增加 Confidence 和 Action，并建立版本决策闭环。

实现要点：
- `temporal_stability()` 重构为纯计算函数（窗口切片 + 原始指标），不含 Grade 判定
- 新增 `factor_health_analysis()` 收集多维 Evidence 后综合输出 Grade + Confidence + Action
- 新增 `version_recommendation()` 聚合所有因子健康状态给出版本决策
- 新增 `HEALTH_ACTIONS` 映射表定义 Grade → 行动建议

Evidence 维度（可扩展）：
| Evidence | 来源 | 用途 |
|----------|------|------|
| rolling_window | temporal_stability 4窗口 | uplift 跨窗口一致性 |
| trigger_cv | 触发计数变异系数 | 触发集中度/Regime 检测 |
| a1_drift | A1 近3年 vs 全历史 | 条件收益漂移交叉验证 |
| freq_drift | 近半年 vs 全历史触发率 | 频率漂移检测 |
| uplift_decay | 窗口间 uplift 前后半段比 | alpha 衰减趋势 |

Confidence 评估逻辑：
| Grade | High 条件 | Medium 条件 | Low 条件 |
|-------|-----------|-------------|----------|
| Stable | ≥3窗口 + ≥15触发 | 其他 | 低频因子 |
| Declining | ≥3窗口 + 衰减比<0.2 | — | 其他 |
| Regime-dependent | — | ≥10触发 | 其他 |
| Unstable | ≥3窗口 + pass=0 | 其他 | — |

版本升级准入机制：
| Version Recommendation | 触发条件 | 行动 |
|------------------------|----------|------|
| Keep Current | 无 Unstable/Declining | 按计划季度审计 |
| Keep Current — 重点观察 | 1 个 Declining | 下次审计复查该因子 |
| Recommend V5.3 Review | ≥2 Declining 或 ≥1 Unstable | 启动 V5.3 评估 |

首次审计实测（2026-07-14）：
| 因子 | Grade | Confidence | Evidence |
|------|-------|------------|----------|
| L1_rsi_30 | Stable | Medium | 低频(9次)，A1漂移89% |
| M1_skew_neg | Regime-dependent | Medium | CV=1.51，仅1个有效窗口 |
| S3_margin_diverge | Stable | High | 4/4窗口正向，A1漂移仅10% |
| V1_price_5y_low | Declining | High | 衰减比0.13，uplift+25.6%→+2.2% |

版本决策：**Keep Current — 重点观察**。V1 为唯一 Declining 因子（High Confidence），若下次审计持续 Declining 则启动 V5.3。

### 其他修复

- **A3a 空值显示修复**：SQLite 中旧信号记录的 signal_tier 和 model_version 字段带有字面引号（如 `'V5.1'`），添加 `strip("'\"")` 清理
- **低频豁免阈值**：设为 15 次触发，覆盖 L1（9次）但不覆盖 M1（18次）和 V1（65次）

### 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/models/factor_optimizer.py` | 修改 | temporal_stability() 重构为纯计算; 新增 factor_health_analysis()(Evidence-based Grade/Confidence/Action); 新增 version_recommendation()(版本决策); 新增 HEALTH_ACTIONS 映射; screen_factors() 恢复三漏斗; run_full_pipeline() 集成监测层+版本决策 |
| `app/monthly_audit.py` | 修改 | 新增 _combo_factor_statistics() A6; 健康监测层改用 factor_health_analysis() 带 A1/freq evidence; 新增版本决策章节; A3a 空值清理修复 |
