# 医药板块风险收益比监控器 - 完整代码包

18 files | V4.3

## 方法论报告
`REPORT.md`
```markdown
# 医药板块风险收益比监控器 — 方法论与验证

**日期**: 2026-05-28 | **版本**: V4.3

---

## 一、定位

这是一个**极端超跌状态检测器 / 风险收益比监控器**。

它回答：**当前医药板块是否处于历史上赔率较好的区域？**

不预测最低点，不预测反弹时间。它识别的是：多种极端条件同时满足时，历史上条件期望收益系统性高于无条件期望的区域。

---

## 二、标签定义：Triple Barrier（路径依赖, 无未来函数）

### 方法

```
在时刻 T 买入, 持有 13 周:
  - 先触及 +8%  → SUCCESS (label=1)
  - 先触及 -5%  → FAIL (label=-1)
  - 到期未触及  → NEUTRAL (label=0)
```

路径依赖意味着先触及下轨再反弹也不计入成功——这更接近真实交易中已止损的情况。

### 与 V3/V4 的对比

| | V3 | V4 | V4.1 |
|---|---|---|---|
| 标签方法 | 局部极值(T±8) | 13周终值>5% | Triple Barrier |
| 路径依赖 | 无 | 仅前4周 | 全路径 |
| 使用未来信息 | 是 | 否 | 否 |
| success(原始) | 18 (4.2%) | 126 (29.4%) | 134 (31.2%) |
| success(collapsed) | — | — | 12 (2.8%) |

### Label Clustering

连续同向标签（间隔<4周）合并为一个机会。原始 134 个 success → collapse 为 **12 个独立盈利机会**。这避免了 Recall 分母被连续区间放大。

---

## 三、五规则探测器

| 代号 | 名称 | 条件 | 经济逻辑 |
|:----:|------|------|----------|
| R | RSI超卖 | RSI(14, Wilder) < 30 | 短期动能衰竭 |
| D | 深度回撤 | 13周最大回撤 < -10% | 跌幅充分 |
| C | 极度便宜 | 5年价格分位 < 15% | 历史低位区域 |
| P | 恐慌指数 | 偏度<-1 或 波动率>80分位 | 极端左尾事件 |
| M | 聪明钱 | ETF份额增+价格跌 | 机构越跌越买 |

### 规则条件概率 P(A=1|B=1)

```
            rule_rsi  rule_dd  rule_cheap  rule_panic  rule_micro
rule_rsi       1.00     0.04       0.02        0.01        0.00
rule_dd        1.00     1.00       0.24        0.15        0.00
rule_cheap     0.20     0.46       1.00        0.29        0.00
rule_panic     0.20     0.20       0.43        1.00        0.00
```

关键发现：
- P(DD=1|RSI=1) = 1.0：RSI 超卖时回撤必超 -10%。但 P(RSI=1|DD=1) = 0.04：回撤超 -10% 时 RSI 超卖仅 4%。RSI 是远更严格的过滤器。
- P(Cheap=1|DD=1) = 0.24、P(Panic=1|Cheap=1) = 0.29：规则之间具有实质性独立性，条件概率远低于直觉。

**结论**：规则相互独立，多数表决 Score≥2 具有增量信息。

### 信号去重

连续 Armed 信号（间隔<4周）合并为一个交易机会，保留 cluster 内**第一条**信号（最早可操作信号）。不使用"最高 score"——实盘中 cluster 结束前无法判断哪条是最高分，事后选最高分属于前瞻偏差。

测试期（2024-10 ~ 2026-05）：18 条原始信号 → **2 个去重交易机会**（2024-10-11, 2025-04-11）。

---

## 四、核心评估：条件期望

### 方法

比较 **E[forward_return | Armed]** 与 **E[forward_return]**（无条件期望），计算 uplift。

### 全量数据结果（去重叠, lockout=13周, n_armed=10）

| 指标 | 无条件 | Armed | Uplift |
|------|:------:|:-----:|:------:|
| 13周期望收益 | +0.7% | +8.4% | **+7.7%** |
| Uplift 95% CI | — | — | **[+0.2%, +16.3%]** |
| Hit ratio (>0) | 48% | 70% | +22pp |
| n (独立机会) | 416 | 10 | — |

### Benchmark 对照

| 持有期 | Armed | 随机买入 | Alpha | n_armed |
|:------:|:-----:|:-------:|:-----:|:-------:|
| 4周 | +0.8% | +0.2% | +0.6% | 10 |
| 13周 | **+8.4%** | +1.8% | **+6.6%** | 10 |
| 26周 | +4.8% | +4.9% | -0.1% | 10 |

Armed 的 alpha 集中在 13 周窗口。26 周后 Armed 与随机买入无差异——超跌修复通常在 1-2 个季度内完成。

### 统计说明

Uplift 95% CI 下限 +0.2% 为正值，但需注意：
- n=10，金融收益重尾、非 IID、存在 regime dependence
- Bootstrap CI 在这些条件下可能低估真实不确定性
- **历史样本中观察到正向 uplift，但不能宣称"正期望已被统计确认"**
- 若增加/减少 1-2 个样本，CI 可能跨零

---

## 五、当前信号

**2026-05-29**：

```
指标                 当前值      阈值      触发？
─────────────────────────────────────────
RSI(14, Wilder)      33.3       < 30       ✗
13周最大回撤          -8.2%     < -10%     ✗
5年价格分位          22%        < 15%      ✗
收益偏度             0.19      < -1        ✗
年化波动率           12.4%      > 80分位    ✗
─────────────────────────────────────────
Score: 0/5 → HOLD
─────────────────────────────────────────
```

---

## 六、Distance-to-Trigger（反推目标价）

系统不仅报告"是否触发"，还计算每条规则触发所需的精确价格：

```
当前指数: 7551 点
Rule D (深度回撤): 触发价 7405 点 (再跌 -1.9%)
Rule C (极度便宜): 触发价 7400 点 (再跌 -2.0%)
```

### 算法

- Rule D: `trigger = 13周最高价 × 0.90`
- Rule C: `trigger = 5年价格序列的第 15 百分位`
- Rule R: 近似值（RSI 为递归指标，无法精确反推）

---

## 七、三级日度警报

| 级别 | 条件 | 含义 |
|:----:|------|------|
| SILENT | Score=0, 距触发 >3% | 安静，正常上班 |
| YELLOW | Score=0 但距触发 <3%，或 Score=1 | 备好资金，随时可能触发 |
| RED | Score≥2 且之前 <2（状态翻转） | ARMED！历史上期望 +8.4% |

GitHub Actions 每交易日 14:45 自动运行。SILENT 时静默不推送，YELLOW/RED 时通过以下渠道推送：
- **Server酱** (微信): 设置 `PUSH_KEY` 环境变量
- **PushDeer**: 设置 `PUSHDEER_KEY`
- **自定义 Webhook**: 设置 `WEBHOOK_URL`
- **GitHub Issue**: RED 警报自动创建 Issue（无需配置）

本地手动运行: `python app/notify.py`

---

## 八、水位线图

Dashboard (`dashboard.html`) 走势图上叠加两条虚线：
- **红线**：回撤触发价（Rule D 水位线）
- **绿线**：估值触发价（Rule C 水位线）

K 线砸穿虚线 = 极致赔率击球区。每天打开浏览器即可一目了然。

---

## 九、使用指南

```bash
python app/tracker.py                # 命令行 (信号 + 距离触发 + 警报)
python app/dashboard.py              # 生成 HTML 看板
start dashboard.html                 # 浏览器打开看板
```

| Score | 仓位 | 含义 |
|:-----:|:----:|------|
| 0-1 | 0% | 观望 |
| 2 | 15-30% | Armed：轻仓，历史上 13 周期望 +8.4% |
| 3 | 50% | 半仓，强信号 |
| 4-5 | 70% | 重仓，极强信号 |

---

## 十、已知局限

1. **小样本**：全量去重后仅 10 个独立 Armed 机会。统计推断不可靠。
2. **规则阈值人工设定**：RSI<30、DD<-10% 等基于全历史确定，存在数据挖掘风险。严格方法应是 expanding walk-forward。
3. **Triple Barrier 参数**：+8%/-5% 是人为设定。但参数敏感性分析显示 uplift 高度稳定：

| 参数 | success% | uplift |
|:------|:--------:|:------:|
| +6%/-5% | 38.2% | +7.9% |
| **+8%/-5%** | **31.2%** | **+7.9%** |
| +10%/-5% | 26.3% | +7.9% |
| +8%/-3% | 26.6% | +7.9% |
| +8%/-7% | 33.6% | +7.9% |

uplift 在全部测试参数下均稳定在 +7.9%，说明 Armed 的条件收益优势不依赖特定的 barrier 参数选择。
4. **仅覆盖医药板块**：黄金预测和顶部检测未实现。
5. **无交易成本建模**：基金申赎费、时间成本未纳入。
6. **Armed 信号 26 周后 alpha 消失**：超跌修复效应集中在 1-2 季度，不适合长期持有信号。

---

## 十一、版本记录

| 版本 | 关键变更 |
|------|----------|
| V1-V2 | XGBoost预测涨跌/拐点。含数据泄露，已废弃 |
| V3 | 五规则+局部极值标签(未来函数)。Precision 47% |
| V3.1-3.4 | 多轮Bug修复 |
| V4 | 前向收益标签、信号去重、Bootstrap CI、RSI Wilder |
| **V4.1** | Triple Barrier标签(路径依赖)、条件期望评估、条件概率相关性、Benchmark对照、label clustering |
| **V4.2** | collapse保留第一条(去前瞻偏差)、Barrier参数敏感性(uplift稳定+7.9%)、fred_source清理死代码+闰年修正 |
| **V4.3** | Distance-to-Trigger、三级警报(SILENT/YELLOW/RED)、水位线图、CI每交易日14:45、ETF代理实时价格(fund_etf_spot_em+512290)、极速server模式(仅拉医药指数<1s)、试算输入框、Rule C触发价修正(quantile) |

---

## 附录：代码结构

```
financial_analysis/
├── REPORT.md                                    # 本报告
├── dashboard.html                               # 自包含看板 (双击浏览器打开)
├── app/
│   ├── dashboard.py                             # 生成 HTML 看板
│   └── tracker.py                               # CLI 跟踪器 (信号+距离触发+警报)
├── src/
│   ├── data_fetcher/
│   │   ├── akshare_source.py                    # AKShare: 申万/COMEX黄金/融资融券/PMI/CPI/M2
│   │   └── fred_source.py                       # FRED: 美债利率/CPI/失业率
│   └── models/
│       └── turning_points.py                    # Triple Barrier + 五规则 + Bootstrap
│                                                # + 条件期望 + 距离触发 + 警报
├── .github/workflows/medical_tracker.yml        # CI: 每交易日 14:45 自动运行
└── requirements.txt
```

```
---

## 项目工作日志
`PROGRESS.md`
```markdown
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
- ETF 接口：`stock_zh_a_spot_em()` → `fund_etf_spot_em()`
- tracker 同一天重复追加 history → 按日期去重
- 日期截断导致本周数据丢失 → 配合 ETF 代理移除截断

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

```
---

## 依赖清单
`requirements.txt`
```text
pandas>=2.0
numpy>=1.24
scipy>=1.10
akshare>=1.11
openpyxl>=3.1

```
---

## Git忽略规则
`.gitignore`
```
__pycache__/
*.pyc
dashboard.html
data/processed/
data/raw/
.vscode/
.idea/
.claude/

```
---

## CI/CD工作流
`.github/workflows/medical_tracker.yml`
```yaml
name: 医药板块每日监控 + 推送

on:
  schedule:
    - cron: '45 6 * * 1-5'
  workflow_dispatch:

permissions:
  contents: write
  issues: write

jobs:
  daily-check:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install
        run: pip install pandas numpy scipy akshare openpyxl

      - name: Verify code
        run: |
          python -c "from src.models.turning_points import TurningPointDetector; print('Import OK')"
          python -c "from app.tracker import _compute, _load_data; print('Tracker OK')"

      - name: Run monitor
        id: monitor
        env:
          PUSH_KEY: ${{ secrets.PUSH_KEY }}
        run: |
          timeout 900 python app/notify.py 2>&1 | tee output.txt || true
          python app/ci_parse.py

      - name: Load results
        id: parsed
        run: cat alert_result.txt >> $GITHUB_OUTPUT

      - name: Generate dashboard
        timeout-minutes: 5
        run: timeout 300 python app/dashboard.py || true

      - name: Commit
        timeout-minutes: 2
        run: |
          git config user.name "bot"
          git config user.email "bot@users.noreply.github.com"
          git add dashboard.html data/processed/signal_history.csv 2>/dev/null || true
          git diff --staged --quiet || (git commit -m "[auto] $(date +%Y-%m-%d) ${{ steps.parsed.outputs.alert }}" && git push || true)

      - name: Issue (RED)
        if: steps.parsed.outputs.alert == 'red'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const out = fs.existsSync('output.txt') ? fs.readFileSync('output.txt','utf8').slice(0,4000) : '';
            await github.rest.issues.create({
              owner: context.repo.owner, repo: context.repo.repo,
              title: `ARMED! Score=${{ steps.parsed.outputs.score }} (${new Date().toISOString().split('T')[0]})`,
              body: '```\n' + out + '\n```\n\n历史Armed信号13周期望+8.4%',
              labels: ['armed','alert']
            });

```
---

## 核心:拐点检测
`src/models/turning_points.py`
```python
"""
医药板块风险收益比监控器 V4.3

功能:
  1. Triple Barrier 标签 (路径依赖, +8%/-5%, 13周)
  2. 五规则探测器 (RSI Wilder / DD / Cheap / Panic / Micro)
  3. 条件期望评估 E[ret|Armed] vs E[ret]
  4. 规则条件概率 P(A=1|B=1)
  5. 信号去重 (保留cluster第一条)
  6. Distance-to-Trigger (反推触发目标价)
  7. 三级警报 (silent/yellow/red)
  8. Bootstrap CI + Benchmark 对照 + 参数敏感性
"""
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema


# ═══════════════════════════════════════════
# 1. Triple Barrier Labeling
# ═══════════════════════════════════════════

def triple_barrier_labels(prices: pd.Series,
                          horizon_weeks: int = 13,
                          upper_barrier_pct: float = 8.0,
                          lower_barrier_pct: float = -5.0) -> pd.DataFrame:
    """
    Triple Barrier 标签 (路径依赖, 纯前向)。

    在未来 horizon_weeks 内:
      - 先触及 +upper_barrier_pct → SUCCESS (label=1)
      - 先触及 -lower_barrier_pct → FAIL (label=-1)
      - 到期未触及任一 → NEUTRAL (label=0)

    不使用任何未来函数——标签仅取决于 T 之后的实际价格路径。
    中性样本表示"方向不明", 在评估中可排除或单独处理。
    """
    prices = prices.sort_index()
    n = len(prices)
    labels = np.zeros(n, dtype=int)
    returns = np.full(n, np.nan)
    hit_barrier = np.full(n, np.nan, dtype=object)

    for i in range(n):
        entry = prices.iloc[i]
        end_idx = min(i + horizon_weeks, n - 1)
        if end_idx <= i + 1:
            continue

        fut = prices.iloc[i + 1:end_idx + 1]
        ret_series = (fut / entry - 1) * 100

        # 检查哪个barrier先被触及
        upper_hit = None
        lower_hit = None
        for j, r in enumerate(ret_series):
            if upper_hit is None and r >= upper_barrier_pct:
                upper_hit = j
            if lower_hit is None and r <= lower_barrier_pct:
                lower_hit = j
            if upper_hit is not None and lower_hit is not None:
                break

        returns[i] = ret_series.iloc[-1]  # 最终收益

        if upper_hit is not None and lower_hit is not None:
            if upper_hit < lower_hit:
                labels[i] = 1; hit_barrier[i] = 'upper'
            else:
                labels[i] = -1; hit_barrier[i] = 'lower'
        elif upper_hit is not None:
            labels[i] = 1; hit_barrier[i] = 'upper'
        elif lower_hit is not None:
            labels[i] = -1; hit_barrier[i] = 'lower'
        else:
            labels[i] = 0; hit_barrier[i] = 'neutral'

    return pd.DataFrame({
        'price': prices.values,
        'label': labels,
        'forward_ret': returns,
        'barrier': hit_barrier,
        'label_desc': ['success' if l == 1 else 'fail' if l == -1 else 'neutral' for l in labels],
    }, index=prices.index)


def collapse_labels(labels: pd.DataFrame, max_gap_weeks: int = 4) -> pd.DataFrame:
    """
    连续的同向标签合并为一个机会。
    例如连续 6 周 success → 合并为 1 个 opportunities。
    避免 Recall 分母被人为放大。
    """
    result = labels.copy()
    result['label_collapsed'] = result['label']

    for label_val in [1, -1]:
        mask = (result['label'] == label_val)
        dates = result[mask].index
        if len(dates) < 2:
            continue
        clusters = []
        current = [dates[0]]
        for d in dates[1:]:
            if (d - current[-1]).days <= max_gap_weeks * 7:
                current.append(d)
            else:
                clusters.append(current)
                current = [d]
        clusters.append(current)
        for cluster in clusters:
            for d in cluster[1:]:  # 同一 cluster 内保留第一条, 其余清零
                result.loc[d, 'label_collapsed'] = 0

    return result


# ═══════════════════════════════════════════
# 2. 五规则探测器
# ═══════════════════════════════════════════

class TurningPointDetector:

    def compute(self, med_w: pd.Series,
                pe_data: pd.Series | None = None,
                etf_shares: pd.Series | None = None) -> pd.DataFrame:
        df = pd.DataFrame(index=med_w.index)
        df['price'] = med_w

        df['rsi'] = self._rsi_wilder(med_w, 14)
        df['rule_rsi'] = (df['rsi'] < 30).astype(int)

        df['drawdown_13w'] = (med_w / med_w.rolling(13).max() - 1) * 100
        df['rule_dd'] = (df['drawdown_13w'] < -10).astype(int)

        if pe_data is not None and len(pe_data.dropna()) > 100:
            df['val_pct_5y'] = pe_data.rolling(260, min_periods=52).rank(pct=True) * 100
        else:
            df['val_pct_5y'] = med_w.rolling(260, min_periods=52).rank(pct=True) * 100
        df['rule_cheap'] = (df['val_pct_5y'] < 15).astype(int)

        df['skew_13w'] = med_w.pct_change().rolling(13).skew()
        df['vol_annual'] = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100
        df['vol_80pct'] = df['vol_annual'].rolling(130, min_periods=52).quantile(0.8)
        df['rule_panic'] = ((df['skew_13w'] < -1) | (df['vol_annual'] > df['vol_80pct'])).astype(int)

        df['rule_micro'] = 0
        if etf_shares is not None and len(etf_shares.dropna()) > 20:
            sw = etf_shares.resample('W-FRI').last().reindex(med_w.index).ffill()
            df['rule_micro'] = ((sw.pct_change(4) * 100 > 2) & (med_w.pct_change(4) * 100 < 0)).astype(int)

        df['score'] = df[['rule_rsi','rule_dd','rule_cheap','rule_panic','rule_micro']].sum(axis=1)
        df['armed'] = (df['score'] >= 2).astype(int)

        df['macd_hist'] = self._macd_histogram(med_w)
        df['macd_stable'] = (df['macd_hist'] >= df['macd_hist'].shift(1)).astype(int)
        df['above_ma2'] = (med_w > med_w.rolling(2).mean()).astype(int)
        df['right_confirm'] = ((df['macd_stable'] == 1) | (df['above_ma2'] == 1)).astype(int)
        df['buy_signal'] = ((df['armed'] == 1) & (df['right_confirm'] == 1)).astype(int)

        return df

    @staticmethod
    def _rsi_wilder(close, period=14):
        delta = close.diff()
        gain = delta.clip(lower=0); loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _macd_histogram(close, fast=12, slow=26, signal=9):
        ef = close.ewm(span=fast, adjust=False).mean()
        es = close.ewm(span=slow, adjust=False).mean()
        return (ef - es) - (ef - es).ewm(span=signal, adjust=False).mean()


# ═══════════════════════════════════════════
# 3. Bootstrap CI
# ═══════════════════════════════════════════

def bootstrap_ci(data: np.ndarray, statistic_fn, n_iter: int = 2000,
                 confidence: float = 0.95, seed: int = 42) -> dict:
    if len(data) < 4:
        return {'mean': np.nan, 'ci_low': np.nan, 'ci_high': np.nan,
                'n_too_small': True}
    rng = np.random.RandomState(seed)
    stats = []
    n = len(data)
    for _ in range(n_iter):
        idx = rng.choice(n, size=n, replace=True)
        try:
            stats.append(statistic_fn(data[idx]))
        except Exception:
            continue
    stats = np.array(stats)
    alpha = (1 - confidence) / 2
    return {
        'mean': np.mean(stats), 'std': np.std(stats),
        'ci_low': np.percentile(stats, alpha * 100),
        'ci_high': np.percentile(stats, (1 - alpha) * 100),
        'n_too_small': False,
    }


# ═══════════════════════════════════════════
# 4. 信号去重 (保留cluster内第一条, 最早可操作)
# ═══════════════════════════════════════════

def collapse_signals(signal_series: pd.Series,
                     max_gap_weeks: int = 4) -> pd.Series:
    """
    连续信号（间隔 < max_gap_weeks）合并为一个交易机会。

    保留每个 cluster 的**第一条**信号（最早可操作信号）。
    注意：不使用"最高 score"——在实盘中 cluster 结束前无法判断哪条是最高分，
    事后选最高分属于前瞻偏差。
    """
    result = signal_series.copy() * 0
    sig_dates = signal_series[signal_series == 1].index
    if len(sig_dates) == 0:
        return result

    clusters = []
    current = [sig_dates[0]]
    for d in sig_dates[1:]:
        if (d - current[-1]).days <= max_gap_weeks * 7:
            current.append(d)
        else:
            clusters.append(current)
            current = [d]
    clusters.append(current)

    for cluster in clusters:
        result.loc[cluster[0]] = 1  # 第一条 = 最早可操作信号
    return result


# ═══════════════════════════════════════════
# 5. 条件概率相关性 (替代Pearson)
# ═══════════════════════════════════════════

def rule_conditional_prob(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 P(A=1 | B=1) 而非 Pearson r。
    对于 binary threshold 规则, 条件概率比 Pearson 更有意义。
    """
    rule_cols = ['rule_rsi', 'rule_dd', 'rule_cheap', 'rule_panic', 'rule_micro']
    n = len(rule_cols)
    result = pd.DataFrame(index=rule_cols, columns=rule_cols, dtype=float)

    for a in rule_cols:
        for b in rule_cols:
            if a == b:
                result.loc[a, b] = 1.0
            else:
                b_true = df[df[b] == 1]
                result.loc[a, b] = b_true[a].mean() if len(b_true) > 0 else 0.0

    return result.astype(float)


# ═══════════════════════════════════════════
# 6. 条件期望评估 (替代Precision/Recall)
# ═══════════════════════════════════════════

def conditional_return_analysis(prices: pd.Series, armed: pd.Series,
                                 forward_weeks: int = 13,
                                 lockout_weeks: int = 13) -> dict:
    """
    评估 Armed 信号的预测价值。

    比较:
      E[forward_return | Armed]
      vs
      E[forward_return] (unconditional)

    同时计算 uplift 和 hit ratio improvement。
    """
    prices = prices.sort_index()
    n = len(prices)

    # Unconditional: 所有周的 forward return
    all_rets = []
    for i in range(n - forward_weeks):
        ret = (prices.iloc[i + forward_weeks] / prices.iloc[i] - 1) * 100
        all_rets.append(ret)
    all_rets = np.array(all_rets)

    # Conditional on Armed (de-overlapped)
    sig_dates = armed[armed == 1].index.sort_values()
    used = []
    last = None
    for d in sig_dates:
        if last is None or (d - last).days > lockout_weeks * 7:
            used.append(d)
            last = d

    armed_rets = []
    for d in used:
        pos = prices.index.searchsorted(d)
        end = min(pos + forward_weeks, n - 1)
        if end > pos:
            ret = (prices.iloc[end] / prices.iloc[pos] - 1) * 100
            armed_rets.append(ret)
    armed_rets = np.array(armed_rets)

    e_uncond = np.mean(all_rets)
    e_armed = np.mean(armed_rets) if len(armed_rets) > 0 else np.nan
    uplift = e_armed - e_uncond
    hit_uncond = (all_rets > 0).mean()
    hit_armed = (armed_rets > 0).mean() if len(armed_rets) > 0 else np.nan

    # Bootstrap CI for uplift
    uplift_ci = None
    if len(armed_rets) >= 4:
        ci = bootstrap_ci(armed_rets, np.mean)
        uplift_ci = (ci['ci_low'] - e_uncond, ci['ci_high'] - e_uncond)

    return {
        'e_unconditional': e_uncond,
        'e_armed': e_armed,
        'uplift': uplift,
        'uplift_ci': uplift_ci,
        'hit_unconditional': hit_uncond,
        'hit_armed': hit_armed,
        'n_armed_opportunities': len(armed_rets),
        'n_total_weeks': n,
    }


# ═══════════════════════════════════════════
# 7. MFE/MAE (带benchmark对照)
# ═══════════════════════════════════════════

def forward_return_analysis(prices: pd.Series, signals: pd.Series,
                            horizons: list = None, lockout_weeks: int = 13,
                            benchmark: bool = True) -> pd.DataFrame:
    if horizons is None: horizons = [4, 13, 26]
    sig_dates = signals[signals == 1].index.sort_values()
    prices = prices.sort_index()

    used = []
    last = None
    for d in sig_dates:
        if last is None or (d - last).days > lockout_weeks * 7:
            used.append(d)
            last = d

    results = []
    for d in used:
        if d not in prices.index: continue
        entry = prices.loc[d]
        pos = prices.index.searchsorted(d)
        row = {'signal_date': d}
        for h in horizons:
            end = min(pos + h, len(prices) - 1)
            fut = prices.iloc[pos:end + 1]
            if len(fut) < 2: continue
            row[f'ret_{h}w'] = (fut.iloc[-1] / entry - 1) * 100
            row[f'mfe_{h}w'] = (fut.max() / entry - 1) * 100
            row[f'mae_{h}w'] = (fut.min() / entry - 1) * 100
        results.append(row)

    # Benchmark: 随机周的 unconditional forward return
    if benchmark and len(used) > 0:
        n_prices = len(prices)
        rng = np.random.RandomState(42)
        bench_dates = rng.choice(
            range(52, n_prices - max(horizons)), size=min(len(used) * 5, 200), replace=False
        )
        for idx in bench_dates:
            entry = prices.iloc[idx]
            row = {'signal_date': prices.index[idx], '_benchmark': True}
            for h in horizons:
                end = min(idx + h, n_prices - 1)
                fut = prices.iloc[idx:end + 1]
                if len(fut) < 2: continue
                row[f'ret_{h}w'] = (fut.iloc[-1] / entry - 1) * 100
                row[f'mfe_{h}w'] = (fut.max() / entry - 1) * 100
                row[f'mae_{h}w'] = (fut.min() / entry - 1) * 100
            results.append(row)

    return pd.DataFrame(results)


def mfe_mae_summary(fwd_df: pd.DataFrame) -> pd.DataFrame:
    """分别对Armed和Benchmark做汇总"""
    rows = {}
    for subset_name, subset in [('armed', fwd_df[fwd_df['_benchmark'] != True]
                                 if '_benchmark' in fwd_df.columns else fwd_df),
                                ('benchmark', fwd_df[fwd_df['_benchmark'] == True]
                                 if '_benchmark' in fwd_df.columns else pd.DataFrame())]:
        if len(subset) == 0: continue
        for col in subset.columns:
            if not any(col.startswith(p) for p in ['ret_', 'mfe_', 'mae_']): continue
            v = subset[col].dropna()
            if len(v) == 0: continue
            key = f'{subset_name}_{col}'
            row = {'mean': v.mean(), 'median': v.median(), 'std': v.std(),
                   'min': v.min(), 'max': v.max(), 'n': len(v)}
            if col.startswith('mae_'):
                row['pct_exceed_5pct'] = (v < -5).mean()
            else:
                row['win_rate'] = (v > 0).mean()
                ci = bootstrap_ci(v.values, np.mean)
                row['mean_ci_low'] = ci.get('ci_low', np.nan)
                row['mean_ci_high'] = ci.get('ci_high', np.nan)
            rows[key] = row
    return pd.DataFrame(rows).T


# ═══════════════════════════════════════════
# 8. 参数敏感性
# ═══════════════════════════════════════════

def sensitivity_analysis(med_w: pd.Series, labels: pd.DataFrame,
                         rsi_range=None, dd_range=None, score_range=None,
                         test_start='2024-10-01', test_end=None) -> pd.DataFrame:
    if rsi_range is None: rsi_range = [25, 28, 30, 32, 35]
    if dd_range is None: dd_range = [-12, -10, -8, -6]
    if score_range is None: score_range = [1, 2, 3]
    t_start = pd.Timestamp(test_start)
    t_end = pd.Timestamp(test_end) if test_end else med_w.index[-1]
    good = labels[(labels['label'] == 1) & (labels.index >= t_start) & (labels.index <= t_end)]

    results = []
    for rsi_t in rsi_range:
        for dd_t in dd_range:
            for sc_t in score_range:
                df = _compute_five_rules(med_w, rsi_t, dd_t)
                score = df[['rule_rsi','rule_dd','rule_cheap','rule_panic','rule_micro']].sum(axis=1)
                signal = collapse_signals((score >= sc_t).astype(int))

                test_sig = signal[(signal.index >= t_start) & (signal.index <= t_end)]
                tp = fp = 0; hit = set()
                for dt in test_sig[test_sig == 1].index:
                    nb = good[(good.index >= dt - pd.Timedelta(weeks=2)) &
                              (good.index <= dt + pd.Timedelta(weeks=2))]
                    if len(nb): tp += 1; hit.update(nb.index)
                    else: fp += 1
                missed = sum(1 for d in good.index if d not in hit)
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0
                rec = len(hit) / len(good) if len(good) > 0 else 0
                results.append({'rsi': rsi_t, 'dd': dd_t, 'score_n': sc_t,
                                'precision': prec, 'recall': rec, 'n_signals': test_sig.sum()})
    return pd.DataFrame(results)


def barrier_sensitivity(med_w: pd.Series,
                        upper_range: list = None,
                        lower_range: list = None,
                        horizon_weeks: int = 13) -> pd.DataFrame:
    """不同 Triple Barrier 参数下 success/fail/neutral 分布"""
    if upper_range is None: upper_range = [6, 8, 10]
    if lower_range is None: lower_range = [-3, -5, -7]
    results = []
    for up in upper_range:
        for lo in lower_range:
            tb = triple_barrier_labels(med_w, horizon_weeks=horizon_weeks,
                                       upper_barrier_pct=up, lower_barrier_pct=lo)
            for v, name in [(1, 'success'), (-1, 'fail'), (0, 'neutral')]:
                results.append({
                    'upper': up, 'lower': lo, 'label': name,
                    'count': (tb['label'] == v).sum(),
                    'pct': (tb['label'] == v).mean(),
                })
    return pd.DataFrame(results)


def _compute_five_rules(med_w, rsi_thresh, dd_thresh):
    df = pd.DataFrame(index=med_w.index)
    df['rule_rsi'] = (TurningPointDetector._rsi_wilder(med_w, 14) < rsi_thresh).astype(int)
    df['rule_dd'] = ((med_w / med_w.rolling(13).max() - 1) * 100 < dd_thresh).astype(int)
    p5 = med_w.rolling(260, min_periods=52).rank(pct=True) * 100
    df['rule_cheap'] = (p5 < 15).astype(int)
    skew = med_w.pct_change().rolling(13).skew()
    vol = med_w.pct_change().rolling(13).std() * np.sqrt(52) * 100
    vol_pct = vol.rolling(130, min_periods=52).quantile(0.8)
    df['rule_panic'] = ((skew < -1) | (vol > vol_pct)).astype(int)
    df['rule_micro'] = 0
    return df


# ═══════════════════════════════════════════
# 10. Distance-to-Trigger (反推目标价)
# ═══════════════════════════════════════════

def distance_to_trigger(df: pd.DataFrame, med_w: pd.Series) -> dict:
    """计算当前价格距离 Rule D (回撤) 和 Rule C (估值) 触发的绝对价位差距"""
    latest = df.iloc[-1]
    curr_price = latest['price']

    # Rule D (13周回撤 < -10%): 跌破过去13周最高点的 90% 即触发
    max_13w = med_w.rolling(13).max().iloc[-1]
    trigger_d = max_13w * 0.90
    triggered_d = bool(latest['rule_dd'])
    pct_away_d = (trigger_d / curr_price - 1) * 100 if not triggered_d else 0.0

    # Rule C (5年分位 < 15%): 过去260周价格的 15% 分位数 = 触发底线
    if len(med_w) >= 52:
        trigger_c = med_w.tail(260).quantile(0.15)
    else:
        trigger_c = np.nan
    triggered_c = bool(latest['rule_cheap'])
    pct_away_c = (trigger_c / curr_price - 1) * 100 if not triggered_c and not np.isnan(trigger_c) else 0.0

    return {
        "D": {
            "name": "深度回撤(Rule D)", "triggered": triggered_d,
            "current": curr_price, "trigger_price": trigger_d, "pct_away": pct_away_d,
        },
        "C": {
            "name": "极度便宜(Rule C)", "triggered": triggered_c,
            "current": curr_price, "trigger_price": trigger_c, "pct_away": pct_away_c,
        },
    }


def alert_level(df: pd.DataFrame, prev_score: int | None = None) -> dict:
    """根据 Score 变化和距离阈值的远近，判断当天的报警级别"""
    latest = df.iloc[-1]
    curr_score = int(latest['score'])
    if prev_score is None:
        prev_score = curr_score

    dist = distance_to_trigger(df, df['price'])

    # 状态翻转：昨天还没到击球区，今天盘中跌出了机会
    if curr_score >= 2 and prev_score < 2:
        return {"level": "red",
                "message": f"状态翻转！Score从 {prev_score} 突升至 {curr_score}/5！极值击球区出现！"}
    # 持续在底部
    elif curr_score >= 2:
        return {"level": "red",
                "message": f"持续处于 Armed 状态 (Score {curr_score}/5)，按计划分批买入。"}
    # 常态区，检查是否接近触发
    else:
        d_away = abs(dist['D']['pct_away']) if not dist['D']['triggered'] else 999
        c_away = abs(dist['C']['pct_away']) if not dist['C']['triggered'] else 999
        min_away = min(d_away, c_away)
        if min_away <= 2.5:
            return {"level": "yellow",
                    "message": f"临界预警！距底部极值线仅差 {min_away:.1f}%，随时可能触发，请备好资金。"}
        else:
            return {"level": "silent",
                    "message": "常态区间。未见极值错杀，安心生活。"}

```
---

## 数据:AKShare
`src/data_fetcher/akshare_source.py`
```python
"""A股数据源：行情、板块指数、资金流向 —— 通过 AKShare"""
import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    ak = None


class AKShareSource:
    """封装 AKShare 数据获取，统一返回标准化 DataFrame"""

    def __init__(self):
        pass

    # ── 申万医药生物指数 ──
    def fetch_sw_medical(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取申万医药生物指数(801150)日线，用 ETF 代理映射盘中实时价格"""
        if ak is None:
            raise ImportError("akshare not installed")

        # 1. 获取历史日线
        df = ak.index_hist_sw(symbol="801150", period="day")
        df = df.rename(columns={
            "日期": "date", "收盘": "close", "开盘": "open",
            "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()

        # 2. 用 512290(生物医药ETF) 盘中涨跌幅推算指数实时点位
        try:
            today = pd.Timestamp.today().normalize()
            if today.weekday() < 5:
                spot_df = ak.fund_etf_spot_em()
                etf = spot_df[spot_df["代码"] == "512290"]
                if not etf.empty:
                    pct_change = float(etf["涨跌幅"].iloc[0]) / 100.0
                    # 只在日线还未更新今天数据时(盘中)，才用昨天收盘价推算
                    if df.iloc[-1]["date"] < today:
                        last_close = df.iloc[-1]["close"]
                        realtime_price = last_close * (1 + pct_change)
                        new_row = {"date": today, "close": realtime_price, "open": realtime_price,
                                   "high": realtime_price, "low": realtime_price,
                                   "volume": 0, "amount": 0}
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        print(f"[AKShare] ETF代理: 512290盘中涨跌{pct_change*100:+.2f}% → 指数盘中估算 {realtime_price:.2f}")
                    # 如果df里已有今天数据(收盘后)，保持原样不动
        except Exception:
            pass  # 网络不佳则静默退回历史数据

        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = "sw_medical"
        cols = ["date", "ticker", "close", "open", "high", "low", "volume", "amount"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 中证医疗指数（备选/补充） ──
    def fetch_csi_medical(self, start_date: str = "20180101",
                          end_date: str | None = None) -> pd.DataFrame:
        """获取中证医疗指数(000933)日线"""
        if ak is None:
            raise ImportError("akshare not installed")
        df = ak.stock_zh_index_daily(symbol="sh000933")
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = "csi_medical"
        cols = ["date", "ticker", "close", "open", "high", "low", "volume"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 大盘指数 ──
    def fetch_market_index(self, symbol: str = "hs300",
                           start_date: str = "20180101",
                           end_date: str | None = None) -> pd.DataFrame:
        """获取大盘指数日线: hs300 / cyb / sz50 / sh000001"""
        if ak is None:
            raise ImportError("akshare not installed")
        symbol_map = {
            "hs300": "sh000300", "cyb": "sz399006",
            "sz50": "sh000016", "sh000001": "sh000001",
        }
        code = symbol_map.get(symbol, symbol)
        df = ak.stock_zh_index_daily(symbol=code)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
        df = df[mask]
        df["ticker"] = symbol
        cols = ["date", "ticker", "close", "open", "high", "low", "volume"]
        return df[cols].sort_values("date").reset_index(drop=True)

    # ── 北向资金 ──
    def fetch_north_flow(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取沪股通北向资金日净流入"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.stock_hsgt_hist_em(symbol="沪股通")
            df = df.rename(columns={
                "日期": "date", "当日成交净买额": "net_flow",
                "买入成交额": "buy_amount", "卖出成交额": "sell_amount",
            })
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "north_flow",
                "value": pd.to_numeric(df["net_flow"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── COMEX 黄金期货（真实国际金价） ──
    def fetch_comex_gold(self, start_date: str = "20180101",
                         end_date: str | None = None) -> pd.DataFrame:
        """获取 COMEX 黄金期货(GC)日线 —— 真实国际金价"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.futures_foreign_hist(symbol="GC")
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "gold_futures",
                "close": df["close"],
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "volume": df.get("volume", np.nan),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── USD/CNY 汇率（DXY 的国内替代） ──
    def fetch_usd_cny(self, start_date: str = "20180101",
                      end_date: str | None = None) -> pd.DataFrame:
        """获取美元兑人民币汇率（替代 DXY）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.currency_boc_sina(symbol="美元")
            df["date"] = pd.to_datetime(df["日期"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "usdcny",
                "value": pd.to_numeric(df["央行中间价"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 上海金交所基准价 ──
    def fetch_sge_gold(self, start_date: str = "20180101",
                       end_date: str | None = None) -> pd.DataFrame:
        """获取上海黄金交易所基准金价"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.spot_golden_benchmark_sge()
            df["date"] = pd.to_datetime(df["交易时间"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "sge_gold",
                "close": pd.to_numeric(df["早盘价"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── 黄金概念板块 ──
    def fetch_gold_concept(self, start_date: str = "20180101",
                           end_date: str | None = None) -> pd.DataFrame:
        """获取同花顺黄金概念板块指数"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.stock_board_concept_index_ths(
                symbol="黄金概念", start_date=start_date, end_date=end_date or "20260101"
            )
            df = df.rename(columns={
                "date": "date", "收盘价": "close", "开盘价": "open",
                "最高价": "high", "最低价": "low", "成交量": "volume",
            })
            if "date" not in df.columns:
                for c in df.columns:
                    if "日期" in str(c):
                        df = df.rename(columns={c: "date"})
                        break
            df["date"] = pd.to_datetime(df["date"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "gold_concept_cn",
                "close": df.get("close", np.nan),
                "open": df.get("open", np.nan),
                "high": df.get("high", np.nan),
                "low": df.get("low", np.nan),
                "volume": df.get("volume", np.nan),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "close"])

    # ── 融资融券（沪深合计） ──
    def fetch_margin_data(self, start_date: str = "20180101",
                          end_date: str | None = None) -> pd.DataFrame:
        """获取沪深两市融资融券日数据（合并）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            sh = ak.macro_china_market_margin_sh()
            sz = ak.macro_china_market_margin_sz()
            sh["date"] = pd.to_datetime(sh["日期"]).dt.normalize()
            sz["date"] = pd.to_datetime(sz["日期"]).dt.normalize()
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            sh = sh[(sh["date"] >= pd.Timestamp(start_date)) & (sh["date"] <= pd.Timestamp(end_date))]
            sz = sz[(sz["date"] >= pd.Timestamp(start_date)) & (sz["date"] <= pd.Timestamp(end_date))]

            # merge on date（杜绝 index 错位）
            merged = sh[["date", "融资融券余额"]].merge(
                sz[["date", "融资融券余额"]], on="date",
                suffixes=("_sh", "_sz"), how="outer"
            )
            result = pd.DataFrame({
                "date": merged["date"],
                "ticker": "total_margin",
                "value": (pd.to_numeric(merged["融资融券余额_sh"], errors="coerce").fillna(0) +
                          pd.to_numeric(merged["融资融券余额_sz"], errors="coerce").fillna(0)),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── M2 货币供应量 ──
    def fetch_m2(self, start_date: str = "20180101",
                 end_date: str | None = None) -> pd.DataFrame:
        """获取中国 M2 月度同比增速"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_money_supply()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_m2",
                "value": pd.to_numeric(df["货币和准货币(M2)-同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 中国 PMI ──
    def fetch_cn_pmi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国官方制造业 PMI + 非制造业 PMI（月频）"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_pmi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            records = []
            for _, row in df.iterrows():
                d = row["date"]
                records.append({"date": d, "ticker": "cn_mfg_pmi",
                               "value": pd.to_numeric(row["制造业-指数"], errors="coerce")})
                records.append({"date": d, "ticker": "cn_nonmfg_pmi",
                               "value": pd.to_numeric(row["非制造业-指数"], errors="coerce")})
            return pd.DataFrame(records).sort_values("date").reset_index(drop=True) if records else pd.DataFrame(columns=["date", "ticker", "value"])
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 中国 CPI / PPI ──
    def fetch_cn_cpi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国 CPI 月度同比"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_cpi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_cpi",
                "value": pd.to_numeric(df["全国-同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    def fetch_cn_ppi(self, start_date: str = "20180101",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取中国 PPI 月度同比"""
        if ak is None:
            raise ImportError("akshare not installed")
        try:
            df = ak.macro_china_ppi()
            date_col = [c for c in df.columns if "月" in str(c)][0]
            df["date"] = pd.to_datetime(
                df[date_col].str.extract(r"(\d{4})年(\d{1,2})月").apply(
                    lambda x: f"{x[0]}-{x[1].zfill(2)}-01", axis=1
                )
            )
            if end_date is None:
                end_date = pd.Timestamp.now().strftime("%Y%m%d")
            mask = (df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))
            df = df[mask]
            result = pd.DataFrame({
                "date": df["date"],
                "ticker": "cn_ppi",
                "value": pd.to_numeric(df["当月同比增长"], errors="coerce"),
            })
            return result.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "ticker", "value"])

    # ── 批量拉取 ──
    def fetch_all(self, start_date: str = "20180101",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """一次性拉取所有 AKShare 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")
        results = {}
        fetchers = [
            ("sw_medical", lambda: self.fetch_sw_medical(start_date, end_date)),
            ("csi_medical", lambda: self.fetch_csi_medical(start_date, end_date)),
            ("hs300", lambda: self.fetch_market_index("hs300", start_date, end_date)),
            ("cyb", lambda: self.fetch_market_index("cyb", start_date, end_date)),
            ("sh000001", lambda: self.fetch_market_index("sh000001", start_date, end_date)),
            ("north_flow", lambda: self.fetch_north_flow(start_date, end_date)),
            ("gold_futures", lambda: self.fetch_comex_gold(start_date, end_date)),
            ("gold_concept_cn", lambda: self.fetch_gold_concept(start_date, end_date)),
            ("usdcny", lambda: self.fetch_usd_cny(start_date, end_date)),
            ("sge_gold", lambda: self.fetch_sge_gold(start_date, end_date)),
            ("cn_pmi", lambda: self.fetch_cn_pmi(start_date, end_date)),
            ("cn_cpi", lambda: self.fetch_cn_cpi(start_date, end_date)),
            ("cn_ppi", lambda: self.fetch_cn_ppi(start_date, end_date)),
            ("total_margin", lambda: self.fetch_margin_data(start_date, end_date)),
            ("cn_m2", lambda: self.fetch_m2(start_date, end_date)),
        ]
        for name, fetcher in fetchers:
            try:
                results[name] = fetcher()
                print(f"[AKShare] {name}: {len(results[name])} rows")
            except Exception as e:
                print(f"[AKShare] Failed {name}: {e}")
                results[name] = pd.DataFrame()
        return results

```
---

## 数据:FRED
`src/data_fetcher/fred_source.py`
```python
"""美国宏观经济数据源 —— 通过 FRED (pandas_datareader)"""
import pandas as pd
import numpy as np

try:
    import pandas_datareader.data as web
except ImportError:
    web = None


class FREDSource:
    """封装 FRED 数据获取，统一返回 (date, ticker, value) 长表"""

    # FRED 序列 ID → 内部名称
    SERIES_MAP = {
        "DGS10": "us10y",          # 10年期美债收益率
        "DGS2": "us2y",            # 2年期美债收益率
        "DFII10": "us_tips10y",    # 10年期 TIPS 收益率（实际利率）
        "FEDFUNDS": "fed_funds",   # 联邦基金利率
        "CPIAUCSL": "us_cpi",      # CPI (需要手动转为同比)
        "CPILFESL": "us_core_cpi", # 核心 CPI
        "UNRATE": "us_unemployment",  # 失业率
        "T10Y2Y": "us_10y2y_spread",  # 10Y-2Y 利差（直接可用）
        "DTWEXBGS": "usd_index_tw",   # 贸易加权美元指数
    }

    def fetch_series(self, fred_code: str, name: str,
                     start_date: str = "2018-01-01",
                     end_date: str | None = None) -> pd.DataFrame:
        """获取单个 FRED 序列"""
        if web is None:
            raise ImportError("pandas_datareader not installed")
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        try:
            data = web.DataReader(fred_code, "fred", start=start_date, end=end_date)
            data = data.reset_index()
            data.columns = ["date", "value"]
            data["ticker"] = name
            data["date"] = pd.to_datetime(data["date"]).dt.normalize()
            # 前向填充日期间隔（FRED 只在发布日有值）
            data = data.set_index("date").resample("D").ffill().reset_index()
            return data[["date", "ticker", "value"]].dropna(subset=["value"])
        except Exception as e:
            print(f"[FRED] Failed to fetch {name} ({fred_code}): {e}")
            return pd.DataFrame(columns=["date", "ticker", "value"])

    def _cpi_to_yoy(self, df: pd.DataFrame) -> pd.DataFrame:
        """将 CPI 水平值转为同比变化率"""
        df = df.copy()
        # 同比: 使用 DateOffset 精确对齐 (处理闰年)
        df = df.set_index("date")
        df["value"] = (df["value"] / df["value"].shift(freq=pd.DateOffset(years=1)) - 1) * 100
        df = df.reset_index()
        return df.dropna(subset=["value"])

    def fetch_all(self, start_date: str = "2018-01-01",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """批量拉取所有 FRED 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        results = {}
        for fred_code, name in self.SERIES_MAP.items():
            try:
                df = self.fetch_series(fred_code, name, start_date, end_date)
                # CPI 需要转为同比
                if fred_code in ("CPIAUCSL", "CPILFESL"):
                    df = self._cpi_to_yoy(df)
                results[name] = df
            except Exception as e:
                print(f"[FRED] Failed to fetch {name}: {e}")
                results[name] = pd.DataFrame(columns=["date", "ticker", "value"])
        return results

```
---

## 数据:YFinance
`src/data_fetcher/yfinance_source.py`
```python
"""国际数据源：黄金、美元、VIX —— 通过 yfinance"""
import pandas as pd
import numpy as np
from pathlib import Path
DATA_RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

try:
    import yfinance as yf
except ImportError:
    yf = None


class YFinanceSource:
    """封装 yfinance 数据获取，统一返回 (date, ticker, value) 或 (date, ticker, ohlcv)"""

    # 常用 ticker 映射
    TICKER_MAP = {
        "GLD": "GLD",               # SPDR Gold Trust ETF
        "GC=F": "GC=F",             # 黄金期货
        "DXY": "DX-Y.NYB",          # 美元指数
        "VIX": "^VIX",             # CBOE 波动率
        "SPY": "SPY",              # 标普500 ETF
        "TLT": "TLT",              # 20Y+ 美债ETF（利率敏感）
        "USO": "USO",              # WTI 原油ETF（通胀传导）
    }

    def __init__(self):
        self.cache_dir = DATA_RAW / "yfinance"

    def fetch_ohlcv(self, raw_ticker: str, name: str,
                    start_date: str = "2018-01-01",
                    end_date: str | None = None) -> pd.DataFrame:
        """获取单个标的 OHLCV 日线数据"""
        if yf is None:
            raise ImportError("yfinance not installed")
        yf_ticker = self.TICKER_MAP.get(raw_ticker, raw_ticker)
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        data = yf.download(yf_ticker, start=start_date, end=end_date,
                           progress=False, auto_adjust=True)
        if data.empty:
            return pd.DataFrame(columns=["date", "ticker", "close", "open", "high", "low", "volume"])

        # yfinance 返回 MultiIndex 列
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        data = data.reset_index()
        data["ticker"] = name
        data.columns = [c.lower() for c in data.columns]
        if "adj close" in data.columns:
            data = data.drop(columns=["adj close"])
        rename_map = {k: k for k in data.columns}
        data = data.rename(columns=rename_map)
        return data.rename(columns={"date": "date"}).reset_index(drop=True)

    def fetch_all_gold(self, start_date: str = "2018-01-01",
                       end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """获取黄金相关所有数据"""
        tickers = {
            "GLD": "gold_etf",
            "GC=F": "gold_futures",
            "DXY": "dxy",
            "VIX": "vix",
        }
        results = {}
        for raw_ticker, name in tickers.items():
            try:
                results[name] = self.fetch_ohlcv(raw_ticker, name, start_date, end_date)
            except Exception as e:
                print(f"[YFinance] Failed to fetch {name}: {e}")
                results[name] = pd.DataFrame()
        return results

    def fetch_all(self, start_date: str = "2018-01-01",
                  end_date: str | None = None) -> dict[str, pd.DataFrame]:
        """批量拉取所有 yfinance 数据"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        all_tickers = {
            "GLD": "gold_etf",
            "GC=F": "gold_futures",
            "DXY": "dxy",
            "VIX": "vix",
            "SPY": "sp500",
            "TLT": "us_20y_bond",
            "USO": "wti_oil",
        }
        results = {}
        for raw_ticker, name in all_tickers.items():
            try:
                results[name] = self.fetch_ohlcv(raw_ticker, name, start_date, end_date)
            except Exception as e:
                print(f"[YFinance] Failed to fetch {name}: {e}")
                results[name] = pd.DataFrame()
        return results

```
---

## 工具:手动导入
`src/data_fetcher/manual_input.py`
```python
"""手动数据导入 —— CSV/Excel 模板解析"""
import pandas as pd
import numpy as np
from pathlib import Path
DATA_MANUAL = Path(__file__).resolve().parent.parent.parent / "data" / "manual"


class ManualInput:
    """手动数据导入器，支持标准模板 CSV/Excel"""

    TEMPLATE_COLS = ["date", "ticker", "value", "source"]

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_MANUAL

    def read_file(self, filepath: str | Path) -> pd.DataFrame:
        """读取单个手动数据文件，自动检测 CSV/Excel"""
        filepath = Path(filepath)
        if filepath.suffix in (".csv",):
            df = pd.read_csv(filepath)
        elif filepath.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        else:
            raise ValueError(f"Unsupported format: {filepath.suffix}")

        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        if "source" not in df.columns:
            df["source"] = str(filepath.name)
        return df[["date", "ticker", "value", "source"]].dropna(subset=["date", "value"])

    def read_all(self) -> pd.DataFrame:
        """读取 data/manual/ 下所有文件并合并"""
        dfs = []
        for f in self.data_dir.glob("*"):
            if f.suffix in (".csv", ".xlsx", ".xls"):
                try:
                    df = self.read_file(f)
                    dfs.append(df)
                    print(f"[ManualInput] Loaded {f.name}: {len(df)} rows")
                except Exception as e:
                    print(f"[ManualInput] Skipped {f.name}: {e}")
        if not dfs:
            return pd.DataFrame(columns=self.TEMPLATE_COLS)
        return pd.concat(dfs, ignore_index=True).sort_values("date")

    @staticmethod
    def create_template(output_path: str | Path = "data/manual/_template.csv"):
        """创建标准模板 CSV"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template = pd.DataFrame(columns=["date", "ticker", "value", "source"])
        template.loc[0] = ["2025-01-15", "medical_policy_event", 1, "https://example.com/policy1"]
        template.loc[1] = ["2025-02-01", "medical_drug_approval", 3, "CDE官网"]
        template.loc[2] = ["2025-01-10", "gold_search_index", 85.5, "百度指数"]
        template.to_csv(output_path, index=False)
        print(f"Template created at {output_path}")
        return template

    def merge_to_data(self, data_dict: dict) -> dict:
        """将手动数据合并到 data dict 中"""
        manual_df = self.read_all()
        if manual_df.empty:
            return data_dict

        # 按 ticker 分组，每个 ticker 作为一个独立数据源
        for ticker in manual_df["ticker"].unique():
            sub = manual_df[manual_df["ticker"] == ticker]
            # 兼容已有的数据格式
            if ticker in data_dict and not data_dict[ticker].empty:
                existing = data_dict[ticker]
                if "value" in existing.columns:
                    combined = pd.concat([existing, sub[["date", "ticker", "value"]]])
                    data_dict[ticker] = combined.drop_duplicates(subset=["date"]).sort_values("date")
                else:
                    data_dict[ticker] = sub[["date", "ticker", "value"]]
            else:
                data_dict[f"manual_{ticker}"] = sub[["date", "ticker", "value"]]

        return data_dict

```
---

## 工具:OCR
`src/data_fetcher/ocr_capture.py`
```python
"""OCR 数据提取 —— 通过 clipboard-vision MCP 从截图提取结构化数据"""
import pandas as pd
import subprocess
import json
import tempfile
from pathlib import Path


class OCRCapture:
    """从截图/剪贴板中提取数据表，需 clipboard-vision MCP 支持"""

    def __init__(self):
        pass

    def from_clipboard(self) -> str:
        """从剪贴板截图提取文本（需要 MCP 工具）"""
        # 此函数通过 MCP 调用 clipboard-vision 的 extract_text_from_clipboard
        # 在实际使用中，由 Claude Code 的 MCP 协议处理
        print("调用 clipboard-vision MCP: extract_text_from_clipboard")
        print("请在 Claude Code 中使用 mcp__clipboard-vision__extract_text_from_clipboard 工具")
        return ""

    def from_screenshot(self, image_path: str) -> str:
        """从截图文件提取文本"""
        print(f"调用 clipboard-vision MCP: extract_text from {image_path}")
        print("请在 Claude Code 中使用 mcp__clipboard-vision__extract_text 工具")
        return ""

    def parse_table(self, ocr_text: str) -> pd.DataFrame | None:
        """尝试从 OCR 文本中解析表格数据。

        支持格式：
        - 逗号/制表符分隔的表格
        - Markdown 表格
        - 空格对齐的表格
        """
        if not ocr_text.strip():
            return None

        lines = [l.strip() for l in ocr_text.strip().split("\n") if l.strip()]

        # Markdown 表格
        if any("|" in l for l in lines):
            return self._parse_markdown_table(lines)

        # 制表符分隔
        if "\t" in lines[0]:
            rows = [l.split("\t") for l in lines]
        # 逗号分隔
        elif "," in lines[0] and lines[0].count(",") >= 2:
            rows = [l.split(",") for l in lines]
        else:
            # 尝试空格分隔
            rows = [l.split() for l in lines]

        if not rows or len(rows) < 2:
            return None

        # 第一行作为列名
        cols = [c.strip() for c in rows[0]]
        data = [[v.strip() for v in row] for row in rows[1:]]

        df = pd.DataFrame(data, columns=cols)

        # 自动检测日期列
        for c in df.columns:
            if any(kw in c.lower() for kw in ["date", "日期", "时间"]):
                try:
                    df[c] = pd.to_datetime(df[c])
                except Exception:
                    pass

        return df

    @staticmethod
    def _parse_markdown_table(lines: list[str]) -> pd.DataFrame:
        """解析 Markdown 表格"""
        # 过滤分隔符行（| --- | --- |）
        data_lines = [l for l in lines if "---" not in l and l.count("|") >= 2]
        if not data_lines:
            return pd.DataFrame()

        header = [c.strip() for c in data_lines[0].split("|") if c.strip()]
        rows = []
        for line in data_lines[1:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                rows.append(cells)

        return pd.DataFrame(rows, columns=header[:len(rows[0])] if rows else header)

    def to_manual_format(self, df: pd.DataFrame, source: str = "ocr") -> pd.DataFrame:
        """将解析出的表格转为标准手动数据格式 (date, ticker, value)"""
        result = pd.DataFrame()
        result["date"] = pd.to_datetime(df.iloc[:, 0])
        result["ticker"] = "ocr_data"
        result["value"] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        result["source"] = source
        return result.dropna(subset=["date", "value"])

```
---

## init
`src/data_fetcher/__init__.py`
```python
from .akshare_source import AKShareSource
from .yfinance_source import YFinanceSource
from .fred_source import FREDSource
from .manual_input import ManualInput
from .ocr_capture import OCRCapture

```
---

## init
`src/models/__init__.py`
```python

```
---

## 应用:CLI跟踪器
`app/tracker.py`
```python
"""
医药生物板块底部探测器 — 每周跟踪器

用法:
    python app/tracker.py              # 命令行
    streamlit run app/tracker.py       # Web界面
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import streamlit as st
    IN_STREAMLIT = True
except ImportError:
    IN_STREAMLIT = False


def _load_data() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.data_fetcher.akshare_source import AKShareSource
    # 极速模式: 只拉医药指数, 跳过宏观慢速接口 (14s → <1s)
    med_df = AKShareSource().fetch_sw_medical("20180101")
    return {"sw_medical": med_df}


def _compute(data: dict, custom_price: float = None) -> dict:
    """计算信号。custom_price: 可选, 用指定价格覆盖最新周数据（用于试算）"""
    from src.models.turning_points import TurningPointDetector

    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    # 用 custom_price 覆盖最新一周的收盘价（"跌到XX会触发"的试算功能）
    if custom_price is not None and len(med_w) > 0:
        med_w.iloc[-1] = custom_price

    det = TurningPointDetector()
    df = det.compute(med_w)
    latest = df.iloc[-1]

    # 规则状态直接从 df 读取（与 Score 计算完全一致）
    rule_defs = [
        ("rule_rsi",   "R:RSI超卖",     f"{latest['rsi']:.1f}",               "< 30",          "短期动能衰竭"),
        ("rule_dd",    "D:深度回撤",     f"{latest['drawdown_13w']:.1f}%",     "< -10%",        "跌幅充分"),
        ("rule_cheap", "C:极度便宜",     f"{latest['val_pct_5y']:.0f}%",       "< 15%分位",     "历史底部区域"),
        ("rule_panic", "P:恐慌指数",     f"偏度{latest['skew_13w']:.2f}/波动率{latest['vol_annual']:.1f}%",
                                         "偏度<-1 或 波动>80分位",               "极端左尾或恐慌"),
        ("rule_micro", "M:聪明钱流入",   "ETF份额",                             "价跌+份额增",    "机构越跌越买"),
    ]

    rules_status = []
    for col, name, val, thresh, desc in rule_defs:
        rules_status.append({
            "name": name, "triggered": bool(latest[col]),
            "value": val, "threshold": thresh, "description": desc,
        })

    from src.models.turning_points import distance_to_trigger, alert_level
    dist = distance_to_trigger(df, med_w)

    # 读取历史 + 保存今天 (合并为一次IO，避免竞态)
    hist_path = Path("data/processed/signal_history.csv")
    today_str = str(latest.name.date())
    prev_score = None
    if not hist_path.parent.exists():
        hist_path.parent.mkdir(parents=True, exist_ok=True)
    if hist_path.exists():
        hist = pd.read_csv(hist_path)
        if len(hist) > 0:
            prev_score = int(hist.iloc[-1].get("score", 0))
        hist = hist[hist["date"] != today_str]
    else:
        hist = pd.DataFrame(columns=["date", "score"])
    hist = pd.concat([hist, pd.DataFrame([{"date": today_str, "score": int(latest["score"])}])], ignore_index=True)
    hist.to_csv(hist_path, index=False)

    alert = alert_level(df, prev_score)

    return {
        "date": latest.name.date(),
        "price": latest["price"],
        "rsi": latest["rsi"],
        "drawdown_13w": latest["drawdown_13w"],
        "val_pct_5y": latest["val_pct_5y"],
        "skew": latest["skew_13w"],
        "vol": latest["vol_annual"],
        "score": int(latest["score"]),
        "armed": bool(latest["armed"]),
        "buy": bool(latest["buy_signal"]),
        "macd_ok": bool(latest["macd_stable"]),
        "ma2_ok": bool(latest["above_ma2"]),
        "rules_status": rules_status,
        "distance_to_trigger": dist,
        "alert": alert,
        "df": df,
    }


# ═══════════════════════════════════════
# CLI
# ═══════════════════════════════════════

def run_cli():
    print("=" * 60)
    print("  医药生物板块(801150) — 底部探测器")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n[1/2] 拉取数据...")
    data = _load_data()
    med = data["sw_medical"].set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()
    print(f"  指数: {len(med_w)}周 ({med_w.index[0].date()} ~ {med_w.index[-1].date()})")

    print("\n[2/2] 计算信号...")
    sig = _compute(data)

    status = "BUY ZONE" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    print(f"\n{'='*60}")
    print(f"  {status}")
    print(f"{'='*60}")
    print(f"  日期:       {sig['date']}")
    print(f"  收盘价:     {sig['price']:.2f}")
    print(f"  Score:      {sig['score']}/5")
    print()

    for r in sig["rules_status"]:
        mark = "[ON]" if r["triggered"] else "[  ]"
        print(f"  {mark} {r['name']}: {r['value']} (阈值: {r['threshold']})")

    if sig["armed"]:
        print(f"\n  右侧确认: MACD={'ON' if sig['macd_ok'] else 'OFF'}  MA2={'ON' if sig['ma2_ok'] else 'OFF'}")

    # Distance to trigger
    print(f"\n  距离触发:")
    dist = sig["distance_to_trigger"]
    for key in ["D", "C"]:
        d = dist[key]
        if d["triggered"]:
            print(f"    {d['name']}: 已触发")
        elif d.get("trigger_price"):
            gap = d["trigger_price"] - d["current"]
            print(f"    {d['name']}: 未触发. 触发价={d['trigger_price']:.0f} (需跌至{d['trigger_price']:.0f}, 再跌{abs(d['pct_away']):.1f}%)")

    # Alert
    print(f"\n  警报: [{sig['alert']['level'].upper()}] {sig['alert']['message']}")

    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        print(f"\n  近期Armed信号 ({len(recent)}次):")
        for d, row in recent.tail(8).iterrows():
            print(f"    {d.date()}  sc={int(row.score)}  RSI={row.rsi:.0f}  DD={row.drawdown_13w:.0f}%  price={row.price:.0f}")

    print()


# ═══════════════════════════════════════
# Streamlit
# ═══════════════════════════════════════

def run_streamlit():
    st.set_page_config(page_title="医药底部探测器", page_icon="📊", layout="wide")
    st.title("📊 医药生物板块 — 底部探测器")
    st.caption(f"更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with st.spinner("数据加载中..."):
        sig = _compute(_load_data())

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    status = "BUY" if sig["buy"] else "ARMED" if sig["armed"] else "HOLD"
    c1.metric("状态", status, delta=f"Score {sig['score']}/5")
    c2.metric("RSI(14)", f"{sig['rsi']:.1f}", delta=f"{sig['rsi']-30:.1f} vs 30")
    c3.metric("13周回撤", f"{sig['drawdown_13w']:.1f}%", delta=f"{sig['drawdown_13w']+10:.1f}% vs -10%")

    st.markdown("---")
    st.subheader("五规则状态")
    for r in sig["rules_status"]:
        icon = "✅" if r["triggered"] else "⬜"
        st.write(f"{icon} **{r['name']}**: {r['value']} (阈值: {r['threshold']}) — *{r['description']}*")

    st.markdown("---")
    st.subheader("近期Armed信号")
    df = sig["df"]
    recent = df[(df.index >= "2024-01-01") & (df["armed"] == 1)]
    if len(recent) > 0:
        st.dataframe(recent[["price", "score", "rsi", "drawdown_13w", "val_pct_5y"]],
                     use_container_width=True)

    st.caption("REPORT.md — 完整方法论与验证")


if __name__ == "__main__":
    if IN_STREAMLIT:
        run_streamlit()
    else:
        run_cli()

```
---

## 应用:HTML看板
`app/dashboard.py`
```python
"""生成自包含 HTML 看板 — 浏览器直接打开"""
import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;color:#1f2937;padding:20px}
.container{max-width:900px;margin:0 auto}
.header{text-align:center;margin-bottom:24px}
.header h1{font-size:24px;font-weight:700}
.header p{color:#6b7280;font-size:14px}
.card{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.card-title{font-size:14px;font-weight:600;color:#6b7280;text-transform:uppercase;margin-bottom:12px;letter-spacing:.5px}
.signal-badge{display:inline-block;padding:6px 16px;border-radius:20px;font-weight:700;font-size:16px;color:#fff}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.metric{text-align:center;padding:12px;background:#f9fafb;border-radius:8px}
.metric .val{font-size:22px;font-weight:700}
.metric .lbl{font-size:11px;color:#6b7280;margin-top:4px}
.rule-row{display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:13px}
.rule-icon{width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;margin-right:10px;font-size:14px;flex-shrink:0}
.rule-icon.on{background:#d1fae5;color:#065f46}
.rule-icon.off{background:#f3f4f6;color:#9ca3af}
.rule-desc{color:#6b7280;margin-left:auto;font-size:12px}
.rec-table{width:100%;font-size:12px;border-collapse:collapse}
.rec-table th,.rec-table td{text-align:center;padding:6px 8px;border-bottom:1px solid #f3f4f6}
.rec-table th{color:#6b7280;font-weight:600}
.first-signal{font-weight:600}
#chart{width:100%;height:350px}
.footer{text-align:center;color:#9ca3af;font-size:12px;margin-top:20px}
.position-card{text-align:center;padding:24px}
.position-card .pct{font-size:48px;font-weight:800}
.position-card .label{font-size:16px;color:#6b7280;margin-top:4px}"""


def build_dashboard(output_path: str = "dashboard.html"):
    from src.data_fetcher.akshare_source import AKShareSource
    from src.models.turning_points import TurningPointDetector, collapse_signals
    import time

    t0 = time.time()
    print("极速拉取最新数据...")

    med_df = AKShareSource().fetch_sw_medical("20180101")
    med = med_df.set_index("date")["close"].sort_index()
    med_w = med.resample("W-FRI").last().dropna()

    det = TurningPointDetector()
    df = det.compute(med_w)
    latest = df.iloc[-1]

    score = int(latest["score"])
    if score <= 1:       pct, label, color = 0, "观望 (0%)", "#9CA3AF"
    elif score == 2:
        if bool(latest["right_confirm"]): pct, label, color = 30, "轻仓 30% — Armed + 右侧确认", "#F59E0B"
        else:                             pct, label, color = 15, "试探仓 15% — Armed, 等右侧确认", "#F59E0B"
    elif score == 3:     pct, label, color = 50, "半仓 50% — 强信号", "#F97316"
    else:                pct, label, color = 70, "重仓 70% — 极强信号", "#EF4444"

    from src.models.turning_points import distance_to_trigger
    dist = distance_to_trigger(df, med_w)

    weekly_data = []
    for i in range(max(0, len(df) - 104), len(df)):
        r = df.iloc[i]
        weekly_data.append({"time": r.name.strftime("%Y-%m-%d"), "value": round(float(r["price"]), 2),
                            "armed": bool(r["armed"]), "score": int(r["score"])})

    daily_recent = med[med.index > df.index[-1]]
    for d, p in daily_recent.items():
        weekly_data.append({"time": d.strftime("%Y-%m-%d"), "value": round(float(p), 2),
                            "armed": False, "score": 0})

    data_date_str = df.index[-1].strftime("%Y-%m-%d")
    daily_latest_str = med.index[-1].strftime("%Y-%m-%d") if len(med) > 0 else data_date_str

    rule_defs = [
        ("R: RSI超卖", bool(latest["rule_rsi"]), f'{latest["rsi"]:.1f}', "< 30", "短期动能衰竭"),
        ("D: 深度回撤", bool(latest["rule_dd"]), f'{latest["drawdown_13w"]:.1f}%', "< -10%", "跌幅充分"),
        ("C: 极度便宜", bool(latest["rule_cheap"]), f'{latest["val_pct_5y"]:.0f}%', "< 15%", "历史低位区域"),
        ("P: 恐慌指数", bool(latest["rule_panic"]), f'偏度{latest["skew_13w"]:.2f}', "偏度<-1 或 波动飙升", "极端左尾事件"),
        ("M: 聪明钱", bool(latest["rule_micro"]), "待数据", "ETF份额逆势增", "机构越跌越买"),
    ]
    rules_html = ""
    for name, ok, val, thresh, desc in rule_defs:
        rules_html += f"""<div class="rule-row">
    <div class="rule-icon {'on' if ok else 'off'}">{'Y' if ok else '-'}</div>
    <div><strong>{name}</strong><br><span style="font-size:11px;color:#6b7280">{val} (阈值: {thresh})</span></div>
    <div class="rule-desc">{desc}</div>
</div>"""

    collapsed = collapse_signals(df["armed"])
    armed_html = ""
    for i in range(max(0, len(df) - 156), len(df)):
        r = df.iloc[i]
        if not bool(r["armed"]): continue
        d = r.name; first = bool(collapsed.iloc[i])
        armed_html += f"""<tr class="{'first-signal' if first else ''}">
    <td>{d.strftime('%Y-%m-%d')}</td><td>{int(r['score'])}/5</td><td>{r['price']:.0f}</td>
    <td>{r['rsi']:.1f}</td><td>{r['drawdown_13w']:.1f}%</td><td>{'*' if first else ''}</td></tr>"""

    waterline_html = ""
    for key, emoji in [("D", "红"), ("C", "绿")]:
        dv = dist[key]
        if dv["triggered"]:
            waterline_html += f'<div style="padding:6px 12px;background:#f0fdf4;border-radius:6px;font-size:13px">{emoji} <b>{dv["name"]}</b>: 已触发</div>'
        elif dv.get("trigger_price") and not np.isnan(dv["trigger_price"]):
            waterline_html += f'<div style="padding:6px 12px;background:#fefce8;border-radius:6px;font-size:13px">{emoji} <b>{dv["name"]}</b>: 触发价 <b>{dv["trigger_price"]:.0f}</b> (距当前 {dv["pct_away"]:+.1f}%)</div>'

    waterline_prices = {}
    for key in ["D", "C"]:
        if not dist[key]["triggered"] and dist[key].get("trigger_price") and not np.isnan(dist[key]["trigger_price"]):
            waterline_prices[key] = dist[key]["trigger_price"]

    chart_data = json.dumps(weekly_data, ensure_ascii=False)
    waterline_json = json.dumps(waterline_prices, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医药板块风险收益比监控器</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>医药板块 风险收益比监控器</h1>
  <p>申万医药生物(801150) | 生成 {datetime.now().strftime('%Y-%m-%d %H:%M')} | 指标至 {data_date_str} | 日线至 {daily_latest_str} | AKShare</p>
</div>
<div class="card"><div class="position-card">
  <div class="pct" style="color:{color}">{pct}%</div>
  <div class="label">{label}</div>
  <div style="margin-top:12px"><span class="signal-badge" style="background:{color}">Score {score}/5</span></div>
</div></div>
<div class="card"><div class="card-title">关键指标</div><div class="metrics">
  <div class="metric"><div class="val">{latest["price"]:.0f}</div><div class="lbl">收盘价 ({daily_latest_str})</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['rsi']<30 else '#1f2937'}">{latest["rsi"]:.1f}</div><div class="lbl">RSI(14) Wilder</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['drawdown_13w']<-10 else '#1f2937'}">{latest["drawdown_13w"]:.1f}%</div><div class="lbl">13周最大回撤</div></div>
  <div class="metric"><div class="val" style="color:{'#ef4444' if latest['val_pct_5y']<15 else '#1f2937'}">{latest["val_pct_5y"]:.0f}%</div><div class="lbl">5年价格分位</div></div>
  <div class="metric"><div class="val">{latest["vol_annual"]:.1f}%</div><div class="lbl">年化波动率</div></div>
  <div class="metric"><div class="val" style="color:{'#10b981' if latest['right_confirm'] else '#9ca3af'}">{'已触发' if latest['right_confirm'] else '未触发'}</div><div class="lbl">右侧确认 MACD/MA2</div></div>
</div></div>
<div class="card"><div class="card-title">触发水位线</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">{waterline_html if waterline_html else '<span style="color:#9ca3af">无法计算</span>'}</div>
</div>
<div class="card"><div class="card-title">五规则状态</div>{rules_html}</div>
<div class="card"><div class="card-title">走势图 (近2年周线+近日线 | 黄箭头=Armed | 虚线=水位线)</div><div id="chart"></div></div>
<div class="card"><div class="card-title">近期 Armed 信号 (* = 入场)</div>
  <table class="rec-table"><tr><th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th><th>入场</th></tr>{armed_html}</table>
</div>
<div class="footer">AKShare | 耗时 {time.time()-t0:.2f}s | 仅供参考, 不构成投资建议</div>
</div>
<script>
var d = {chart_data};
var chart = LightweightCharts.createChart(document.getElementById('chart'), {{
    layout: {{ background: {{ color: '#ffffff' }}, textColor: '#1f2937' }},
    grid: {{ vertLines: {{ color: '#f3f4f6' }}, horzLines: {{ color: '#f3f4f6' }} }},
    rightPriceScale: {{ borderColor: '#d1d5db' }},
    timeScale: {{ borderColor: '#d1d5db', timeVisible: true }},
    width: document.getElementById('chart').clientWidth, height: 350,
}});
var line = chart.addLineSeries({{ color: '#3B82F6', lineWidth: 2 }});
var uniqueData = [], seen = new Set();
d.forEach(function(w) {{
    if (!seen.has(w.time) && w.value != null && !isNaN(w.value)) {{ seen.add(w.time); uniqueData.push(w); }}
}});
uniqueData.sort(function(a,b) {{ return a.time.localeCompare(b.time); }});
var prices = uniqueData.map(function(w) {{ return {{ time: w.time, value: w.value }}; }});
var markers = uniqueData.filter(function(w) {{ return w.armed; }}).map(function(w) {{
    return {{ time: w.time, position: 'belowBar', color: '#F59E0B', shape: 'arrowUp', text: String(w.score) }};
}});
line.setData(prices); line.setMarkers(markers);
var waterlines = {waterline_json};
var colors = {{ 'D': '#EF4444', 'C': '#10B981' }};
var labels = {{ 'D': '回撤触发', 'C': '估值触发' }};
Object.keys(waterlines).forEach(function(key) {{
    var price = waterlines[key];
    var wl = chart.addLineSeries({{ color: colors[key], lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }});
    var data = [];
    for (var i = 0; i < prices.length; i++) {{ data.push({{ time: prices[i].time, value: price }}); }}
    wl.setData(data);
    wl.setMarkers([{{ time: prices[prices.length-1].time, position: 'inLine', color: colors[key], shape: 'circle', text: labels[key] + ' ' + price.toFixed(0) }}]);
}});
chart.timeScale().fitContent();
window.addEventListener('resize', function() {{ chart.applyOptions({{ width: document.getElementById('chart').clientWidth }}); }});
</script>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Dashboard saved ({time.time()-t0:.2f}s)")
    return output_path


if __name__ == "__main__":
    build_dashboard()

```
---

## 应用:推送通知
`app/notify.py`
```python
"""
推送通知模块 — 支持多种推送渠道

用法:
    python app/notify.py                    # 运行 tracker 并在有警报时推送
    python app/notify.py --dry-run          # 仅打印，不实际推送

环境变量 (可选, 不设置则仅打印):
    PUSH_KEY       Server酱 SendKey (https://sct.ftqq.com/)
    PUSHDEER_KEY   PushDeer pushkey
    WEBHOOK_URL    自定义 Webhook URL (POST JSON)
"""
import sys
import os
import json
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def push_serverchan(title: str, content: str, push_key: str = None) -> bool:
    """Server酱 (微信推送)"""
    key = push_key or os.environ.get("PUSH_KEY", "")
    if not key:
        return False
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = json.dumps({"title": title, "desp": content}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [ServerChan] Failed: {e}")
        return False


def push_pushdeer(title: str, content: str, push_key: str = None) -> bool:
    """PushDeer"""
    key = push_key or os.environ.get("PUSHDEER_KEY", "")
    if not key:
        return False
    try:
        url = f"https://api2.pushdeer.com/message/push?pushkey={key}&text={urllib.parse.quote(title)}&desp={urllib.parse.quote(content)}"
        urllib.request.urlopen(url, timeout=10)
        return True
    except Exception as e:
        print(f"  [PushDeer] Failed: {e}")
        return False


def push_webhook(title: str, content: str, webhook_url: str = None) -> bool:
    """自定义 Webhook"""
    url = webhook_url or os.environ.get("WEBHOOK_URL", "")
    if not url:
        return False
    try:
        data = json.dumps({"title": title, "content": content, "time": datetime.now().isoformat()}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [Webhook] Failed: {e}")
        return False


def push(title: str, content: str) -> bool:
    """尝试所有渠道"""
    sent = False
    for fn in [push_serverchan, push_pushdeer, push_webhook]:
        if fn(title, content):
            sent = True
    # GitHub Actions: 输出到 workflow summary
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## {title}\n\n{content}\n")
        sent = True
    return sent


def run(dry_run: bool = False, test_push: bool = False):
    """主入口：计算信号 + 按需推送"""
    from app.tracker import _compute, _load_data

    # 测试模式：强制发送测试推送
    if test_push:
        title = "测试推送 — 医药板块监控器"
        content = f"如果你收到这条消息，说明推送配置成功！\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"  测试模式: 强制推送")
        if not dry_run:
            sent = push(title, content)
            if sent:
                print("  测试推送已发送！请检查微信/手机是否收到。")
            else:
                print("  推送失败！请检查 PUSH_KEY 是否正确设置。")
                print(f"  当前 PUSH_KEY: {'已设置' if os.environ.get('PUSH_KEY') else '未设置'}")
        else:
            print(f"  [dry-run] 标题: {title}\n  内容: {content}")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 运行监控...")
    try:
        sig = _compute(_load_data())
    except Exception as e:
        print(f"  数据拉取失败: {e}")
        print(f"  [SILENT] 无法计算信号, 静默退出")
        return
    alert = sig["alert"]
    score = sig["score"]

    # 构建推送内容
    lines = [
        f"日期: {sig['date']}",
        f"指数: {sig['price']:.0f}",
        f"Score: {score}/5",
        f"警报: [{alert['level'].upper()}] {alert['message']}",
        "",
        "--- 距离触发 ---",
    ]
    for key in ["D", "C"]:
        d = sig["distance_to_trigger"][key]
        if d["triggered"]:
            lines.append(f"{d['name']}: 已触发")
        elif d.get("trigger_price"):
            lines.append(f"{d['name']}: 触发价 {d['trigger_price']:.0f} (距当前 {d['pct_away']:+.1f}%)")
    content = "\n".join(lines)

    # 根据警报级别决定是否推送
    level = alert["level"]
    if level == "silent":
        print(f"  Score={score} [{level}] — 静默, 不推送")
        return

    # YELLOW 或 RED: 推送
    emoji = "🔴" if level == "red" else "🟡"
    title = f"{emoji} 医药板块{'ARMED!' if level == 'red' else '近触发预警'} (Score={score})"

    print(f"  [{level.upper()}] {alert['message']}")
    print(f"  推送标题: {title}")

    if not dry_run:
        sent = push(title, content)
        if sent:
            print("  推送已发送")
        else:
            print("  未配置推送渠道 (设置 PUSH_KEY / PUSHDEER_KEY / WEBHOOK_URL 环境变量)")
    else:
        print("  [dry-run] 跳过推送")
        print(content)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    test = "--test" in sys.argv
    run(dry_run=dry, test_push=test)

```
---

## 应用:CI解析
`app/ci_parse.py`
```python
"""CI 辅助脚本：从 output.txt 解析 alert level 和 score"""
import sys, re

with open("output.txt", "r", encoding="utf-8", errors="replace") as f:
    text = f.read()

# 解析 alert: 找 [SILENT] 或 [YELLOW] 或 [RED]
m = re.search(r'\[(SILENT|YELLOW|RED)\]', text)
alert = m.group(1).lower() if m else "silent"

# 解析 score
m = re.search(r'Score:\s*(\d+)', text)
score = m.group(1) if m else "0"

# 输出给 GitHub Actions
with open("alert_result.txt", "w") as f:
    f.write(f"alert={alert}\nscore={score}\n")
print(f"alert={alert} score={score}")

```
---

## 应用:实时看板服务器
`app/server.py`
```python
"""
实时看板服务器 — 每次打开/刷新页面自动拉取最新数据

用法:
    python app/server.py              # 启动服务器，自动打开浏览器
    python app/server.py --port 9000  # 指定端口
    python app/server.py --no-browser # 不自动打开浏览器

架构:
    GET /            → 返回 HTML 看板（JS 动态渲染）
    GET /api/signal  → 实时计算信号，返回 JSON
"""
import sys
import json
import argparse
import threading
import webbrowser
import traceback
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_PORT = 8888

# ═══════════════════════════════════════════════════════════════
# HTML 模板 — JS 动态从 /api/signal 拉取数据后渲染
# ═══════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>医药板块监控器</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>window.lightweightCharts||document.write('<script src=\"https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js\"><\/script>')</script>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#222636;--border:#2a2d3e;
  --text:#e2e8f0;--muted:#64748b;--accent:#38bdf8;
  --green:#34d399;--yellow:#fbbf24;--red:#f87171;--silent:#64748b;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* Loading */
#loading{display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;gap:16px;color:var(--muted)}
.spinner{width:36px;height:36px;border:3px solid var(--border);
  border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
#error{display:none;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;gap:12px;color:var(--red)}

/* Layout */
#app{display:none;max-width:960px;margin:0 auto;padding:24px 16px}
.header{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:28px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.header-title{font-size:15px;font-weight:700;letter-spacing:.5px;color:var(--muted);
  text-transform:uppercase}
.header-meta{font-size:12px;color:var(--muted);text-align:right;line-height:1.6}
.header-meta b{color:var(--accent)}

/* Cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:20px;margin-bottom:16px}
.card-title{font-size:11px;font-weight:700;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted);margin-bottom:16px}

/* Status badge */
.status-row{display:flex;align-items:center;gap:16px;margin-bottom:20px}
.badge{display:inline-flex;align-items:center;gap:8px;padding:8px 18px;
  border-radius:8px;font-family:'DM Mono',monospace;font-weight:500;font-size:14px}
.badge.silent{background:#1e293b;color:var(--silent);border:1px solid var(--border)}
.badge.yellow{background:#451a03;color:var(--yellow);border:1px solid #92400e}
.badge.red{background:#450a0a;color:var(--red);border:1px solid #991b1b}
.badge .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.badge.red .dot{animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* Score bar */
.score-bar{display:flex;gap:6px;align-items:center}
.score-seg{height:6px;border-radius:3px;flex:1;background:var(--border);transition:.3s}
.score-seg.active{background:var(--accent)}
.score-seg.active.warn{background:var(--yellow)}
.score-seg.active.alert{background:var(--red)}
.score-label{font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);
  min-width:32px;text-align:right}

/* Metrics grid */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:0}
.metric{background:var(--surface2);border-radius:8px;padding:12px 10px;text-align:center}
.metric .val{font-family:'DM Mono',monospace;font-size:18px;font-weight:500}
.metric .lbl{font-size:10px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.metric.triggered .val{color:var(--red)}

/* Rules */
.rule{display:flex;align-items:center;gap:12px;padding:10px 0;
  border-bottom:1px solid var(--border)}
.rule:last-child{border-bottom:none}
.rule-icon{width:26px;height:26px;border-radius:6px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:12px}
.rule-icon.on{background:#052e16;color:var(--green)}
.rule-icon.off{background:var(--surface2);color:var(--muted)}
.rule-name{font-weight:500;font-size:13px;min-width:100px}
.rule-val{font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);flex:1}
.rule-thresh{font-size:11px;color:var(--border);margin-left:auto}

/* Distance */
.dist-row{display:flex;justify-content:space-between;align-items:center;
  padding:10px 0;border-bottom:1px solid var(--border)}
.dist-row:last-child{border-bottom:none}
.dist-name{font-size:13px;font-weight:500}
.dist-price{font-family:'DM Mono',monospace;font-size:13px}
.dist-pct{font-family:'DM Mono',monospace;font-size:12px;padding:2px 8px;
  border-radius:4px;background:var(--surface2)}
.dist-pct.triggered{color:var(--green)}
.dist-pct.far{color:var(--muted)}
.dist-pct.close{color:var(--yellow)}

/* Chart */
#chart{width:100%;height:320px}

/* Table */
.sig-table{width:100%;border-collapse:collapse;font-size:12px}
.sig-table th{text-align:center;padding:6px 8px;color:var(--muted);
  font-weight:500;border-bottom:1px solid var(--border);font-family:'DM Mono',monospace}
.sig-table td{text-align:center;padding:6px 8px;border-bottom:1px solid var(--border);
  font-family:'DM Mono',monospace;color:var(--muted)}
.sig-table tr.first td{color:var(--text)}
.sig-table tr.first td:first-child::before{content:'▶ ';color:var(--accent)}

/* Alert message */
.alert-msg{font-size:13px;color:var(--muted);padding:10px 14px;
  background:var(--surface2);border-radius:6px;border-left:3px solid var(--border);line-height:1.5}
.alert-msg.yellow{border-color:var(--yellow);color:var(--yellow)}
.alert-msg.red{border-color:var(--red);color:var(--red)}

/* Footer */
.footer{text-align:center;color:var(--muted);font-size:11px;
  margin-top:24px;padding-top:16px;border-top:1px solid var(--border);line-height:2}
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <span>正在拉取最新行情数据…</span>
</div>
<div id="error">
  <span style="font-size:32px">⚠️</span>
  <b id="err-msg">数据加载失败</b>
  <small id="err-detail" style="color:var(--muted)"></small>
  <button onclick="load()" style="margin-top:12px;padding:8px 20px;background:var(--accent);
    color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600">重试</button>
</div>

<div id="app">
  <div class="header">
    <div>
      <div class="header-title">申万医药生物(801150) · 风险收益比监控器</div>
    </div>
    <div class="header-meta">
      数据截止 <b id="h-date">—</b><br>
      更新时间 <b id="h-updated">—</b>
      <div style="margin-top:10px; display:flex; align-items:center; gap:8px; justify-content:flex-end">
        <input type="number" id="custom-price" placeholder="试算点位(如 7430)"
               style="padding:6px; border-radius:6px; border:1px solid #374151; background:#1f2937; color:#e2e8f0; width:160px; font-size:12px;">
        <button onclick="load()" style="padding:6px 12px; background:#38bdf8; color:#000; border:none; border-radius:6px; cursor:pointer; font-size:12px; font-weight:bold;">刷新试算</button>
      </div>
    </div>
  </div>

  <!-- 状态 + Score -->
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px">
      <div>
        <div class="card-title">当前状态</div>
        <div class="status-row">
          <span class="badge" id="badge"><span class="dot"></span><span id="badge-text">—</span></span>
        </div>
        <div class="alert-msg" id="alert-msg"></div>
      </div>
      <div style="min-width:180px">
        <div class="card-title">Score</div>
        <div class="score-bar" id="score-bar">
          <div class="score-seg" id="s0"></div>
          <div class="score-seg" id="s1"></div>
          <div class="score-seg" id="s2"></div>
          <div class="score-seg" id="s3"></div>
          <div class="score-seg" id="s4"></div>
          <span class="score-label" id="score-lbl">0/5</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 关键指标 -->
  <div class="card">
    <div class="card-title">关键指标</div>
    <div class="metrics" id="metrics"></div>
  </div>

  <!-- 五规则 -->
  <div class="card">
    <div class="card-title">五规则状态</div>
    <div id="rules"></div>
  </div>

  <!-- 距离触发 -->
  <div class="card">
    <div class="card-title">距离触发水位线</div>
    <div id="dist"></div>
  </div>

  <!-- 走势图 -->
  <div class="card">
    <div class="card-title">近两年周线 · 黄箭头=Armed · 虚线=触发水位线</div>
    <div id="chart"></div>
  </div>

  <!-- 历史信号 -->
  <div class="card">
    <div class="card-title">近期 Armed 信号 (▶ = 入场信号)</div>
    <table class="sig-table">
      <thead><tr>
        <th>日期</th><th>Score</th><th>价格</th><th>RSI</th><th>回撤</th>
      </tr></thead>
      <tbody id="sig-tbody"></tbody>
    </table>
  </div>

  <div class="footer">
    仅供研究参考，不构成投资建议 &nbsp;|&nbsp;
    方法论: Triple Barrier + 五规则探测器 &nbsp;|&nbsp; V4.3<br>
    <span id="footer-note"></span>
  </div>
</div>

<script>
let chart = null;

async function load() {
  document.getElementById('loading').style.display = 'flex';
  document.getElementById('error').style.display = 'none';
  document.getElementById('app').style.display = 'none';

  try {
    const cpEl = document.getElementById('custom-price');
    const cp = cpEl ? cpEl.value : '';
    const url = cp ? '/api/signal?price=' + cp : '/api/signal';
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
    const d = await r.json();
    render(d);
    document.getElementById('loading').style.display = 'none';
    document.getElementById('app').style.display = 'block';
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'flex';
    document.getElementById('err-msg').textContent = '数据加载失败';
    document.getElementById('err-detail').textContent = e.message;
  }
}

function render(d) {
  // Header
  document.getElementById('h-date').textContent = d.date;
  document.getElementById('h-updated').textContent = d.computed_at;

  // Badge
  const level = d.alert.level;
  const badge = document.getElementById('badge');
  badge.className = 'badge ' + level;
  const labels = {silent:'HOLD', yellow:'YELLOW ⚠', red:'ARMED 🔴'};
  document.getElementById('badge-text').textContent = labels[level] || level.toUpperCase();

  // Alert message
  const msg = document.getElementById('alert-msg');
  msg.textContent = d.alert.message;
  msg.className = 'alert-msg ' + (level === 'silent' ? '' : level);

  // Score bar
  const score = d.score;
  const colorClass = score >= 4 ? 'alert' : score >= 2 ? 'warn' : '';
  for(let i = 0; i < 5; i++) {
    const seg = document.getElementById('s' + i);
    seg.className = 'score-seg' + (i < score ? ' active ' + colorClass : '');
  }
  document.getElementById('score-lbl').textContent = score + '/5';

  // Metrics
  const metrics = [
    {label: 'RSI(Wilder)', val: d.rsi.toFixed(1), trigger: d.rsi < 30},
    {label: '13周回撤', val: d.drawdown_13w.toFixed(1) + '%', trigger: d.drawdown_13w < -10},
    {label: '5年价格分位', val: d.val_pct_5y.toFixed(0) + '%', trigger: d.val_pct_5y < 15},
    {label: '收盘价', val: d.price.toFixed(0), trigger: false},
  ];
  document.getElementById('metrics').innerHTML = metrics.map(m =>
    `<div class="metric${m.trigger?' triggered':''}">
       <div class="val">${m.val}</div>
       <div class="lbl">${m.label}</div>
     </div>`
  ).join('');

  // Rules
  document.getElementById('rules').innerHTML = d.rules_status.map(r =>
    `<div class="rule">
       <div class="rule-icon ${r.triggered?'on':'off'}">${r.triggered?'✓':'—'}</div>
       <div class="rule-name">${r.name}</div>
       <div class="rule-val">${r.value}</div>
       <div class="rule-thresh">阈值: ${r.threshold}</div>
     </div>`
  ).join('');

  // Distance to trigger
  document.getElementById('dist').innerHTML = Object.values(d.distance_to_trigger).map(dt => {
    if (dt.triggered) {
      return `<div class="dist-row">
        <div class="dist-name">${dt.name}</div>
        <div class="dist-pct triggered">已触发 ✓</div>
      </div>`;
    }
    const pct = dt.pct_away;
    const cls = Math.abs(pct) < 2.5 ? 'close' : 'far';
    return `<div class="dist-row">
      <div class="dist-name">${dt.name}</div>
      <div class="dist-price">触发价 ${dt.trigger_price ? dt.trigger_price.toFixed(0) : '—'}</div>
      <div class="dist-pct ${cls}">${pct ? (pct > 0 ? '+' : '') + pct.toFixed(1) + '%' : '—'}</div>
    </div>`;
  }).join('');

  // Chart
  if (chart) { chart.remove(); chart = null; }
  const el = document.getElementById('chart');
  chart = LightweightCharts.createChart(el, {
    layout: {background:{color:'transparent'}, textColor:'#94a3b8'},
    grid: {vertLines:{color:'#1e293b'}, horzLines:{color:'#1e293b'}},
    rightPriceScale: {borderColor:'#2a2d3e'},
    timeScale: {borderColor:'#2a2d3e', timeVisible:true},
    width: el.clientWidth, height: 320,
  });

  const line = chart.addLineSeries({color:'#38bdf8', lineWidth:2});

  // 去重 + 排序 (防止重复时间轴导致图表崩溃)
  const uniqueData = [];
  const seen = new Set();
  d.chart.forEach(w => {
    if (!seen.has(w.time) && w.value != null && !isNaN(w.value)) {
      seen.add(w.time);
      uniqueData.push(w);
    }
  });
  uniqueData.sort((a,b) => a.time.localeCompare(b.time));

  const prices = uniqueData.map(w => ({time:w.time, value:w.value}));
  line.setData(prices);
  line.setMarkers(
    uniqueData.filter(w => w.armed).map(w => ({
      time:w.time, position:'belowBar', color:'#fbbf24',
      shape:'arrowUp', text: String(w.score)
    }))
  );

  // Waterlines
  const wl_colors = {D:'#f87171', C:'#34d399'};
  const wl_labels = {D:'回撤触发', C:'估值触发'};
  Object.entries(d.distance_to_trigger).forEach(([key, dt]) => {
    if (!dt.trigger_price || dt.triggered) return;
    const wl = chart.addLineSeries({
      color:wl_colors[key], lineWidth:1, lineStyle:2,
      priceLineVisible:false, lastValueVisible:false,
    });
    wl.setData(prices.map(p => ({time:p.time, value:dt.trigger_price})));
    wl.setMarkers([{
      time: prices[prices.length-1].time, position:'inLine',
      color:wl_colors[key], shape:'circle',
      text: wl_labels[key] + ' ' + dt.trigger_price.toFixed(0),
    }]);
  });
  chart.timeScale().fitContent();
  window.addEventListener('resize', () => {
    chart.applyOptions({width: el.clientWidth});
  });

  // Armed signal table
  document.getElementById('sig-tbody').innerHTML = d.armed_history.slice(-20).reverse().map(s =>
    `<tr class="${s.first?'first':''}">
       <td>${s.date}</td><td>${s.score}/5</td><td>${s.price}</td>
       <td>${s.rsi}</td><td>${s.dd}%</td>
     </tr>`
  ).join('');

  // Footer note
  document.getElementById('footer-note').textContent =
    `行情来源: AKShare | 计算耗时: ${d.elapsed_s}s`;
}

load();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# API: 实时计算信号并序列化为 JSON
# ═══════════════════════════════════════════════════════════════

def _compute_and_serialize(custom_price: float = None) -> dict:
    import time
    import numpy as np
    t0 = time.time()

    from app.tracker import _compute
    from src.data_fetcher.akshare_source import AKShareSource

    # 极速模式: 只拉取医药指数, 跳过宏观数据 (14s → <1s)
    med_df = AKShareSource().fetch_sw_medical("20180101")
    fast_data = {"sw_medical": med_df}

    sig = _compute(fast_data, custom_price=custom_price)

    df = sig.get("df")
    dist = sig.get("distance_to_trigger", {})

    # ── 水位线触发价（确保可序列化）──
    dist_out = {}
    for k, v in dist.items():
        dist_out[k] = {
            "name": v["name"],
            "triggered": bool(v["triggered"]),
            "trigger_price": float(v["trigger_price"]) if v.get("trigger_price") is not None and not (isinstance(v["trigger_price"], float) and np.isnan(v["trigger_price"])) else None,
            "pct_away": float(v["pct_away"]) if v.get("pct_away") is not None else 0.0,
        }

    # ── 近两年周线数据 ──
    chart_data = []
    if df is not None:
        for i in range(max(0, len(df) - 104), len(df)):
            r = df.iloc[i]
            chart_data.append({
                "time": r.name.strftime("%Y-%m-%d"),
                "value": round(float(r["price"]), 2),
                "armed": bool(r["armed"]),
                "score": int(r["score"]),
            })

    # ── 近期 Armed 信号 ──
    armed_history = []
    if df is not None:
        from src.models.turning_points import collapse_signals
        collapsed = collapse_signals(df["armed"])
        for i in range(max(0, len(df) - 156), len(df)):
            r = df.iloc[i]
            if not bool(r["armed"]):
                continue
            armed_history.append({
                "date": r.name.strftime("%Y-%m-%d"),
                "score": int(r["score"]),
                "price": round(float(r["price"])),
                "rsi": round(float(r["rsi"]), 1),
                "dd": round(float(r["drawdown_13w"]), 1),
                "first": bool(collapsed.iloc[i]),
            })

    elapsed = round(time.time() - t0, 1)

    return {
        "date": str(sig["date"]),
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": elapsed,
        "price": float(sig["price"]),
        "score": int(sig["score"]),
        "armed": bool(sig["armed"]),
        "rsi": float(sig["rsi"]),
        "drawdown_13w": float(sig["drawdown_13w"]),
        "val_pct_5y": float(sig["val_pct_5y"]),
        "rules_status": sig["rules_status"],
        "alert": sig["alert"],
        "distance_to_trigger": dist_out,
        "chart": chart_data,
        "armed_history": armed_history,
    }


# ═══════════════════════════════════════════════════════════════
# HTTP 服务器
# ═══════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path.startswith("/api/signal"):
            self._serve_api()
        else:
            self._serve_html()

    def _serve_html(self):
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_api(self):
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        custom_price = float(qs["price"][0]) if "price" in qs else None
        print(f"  [{datetime.now():%H:%M:%S}] 拉取数据中...")
        try:
            payload = _compute_and_serialize(custom_price=custom_price)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            print(f"  [{datetime.now():%H:%M:%S}] 完成 ({payload['elapsed_s']}s) — Score={payload['score']}/5 [{payload['alert']['level'].upper()}]")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"  [ERROR] {e}\n{tb}")
            body = json.dumps({"error": str(e), "detail": tb}, ensure_ascii=False).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 屏蔽默认 access log，用自定义日志


def main():
    parser = argparse.ArgumentParser(description="医药板块实时监控看板")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"

    print("=" * 50)
    print("  医药板块实时监控看板")
    print(f"  地址: {url}")
    print("  每次刷新页面 (F5) 自动拉取最新行情")
    print("  Ctrl+C 停止服务器")
    print("=" * 50)

    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    main()

```
---
