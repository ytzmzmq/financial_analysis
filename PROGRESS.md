# 项目工作日志

## 项目概述

为基金投资者构建一个医药板块（申万医药生物 801150）风险收益比监控系统。从最初的"预测下周涨跌"的 XGBoost 模型，经过多轮方法论重构、Bug 修复和实用化改造，最终定型为基于五规则的极端超跌状态检测器，支持每日自动运行、微信推送和可视化看板。

数据源：AKShare（免费）+ FRED（免费）。全部使用 Python。

---

## 第一阶段：方案讨论与初始搭建（2026-05-26 上午）

### 需求对齐
- 预测目标：黄金价格 + 创新药/医疗板块的周频方向与幅度
- 数据源：AKShare + yfinance + FRED，免费为主，手动输入为补充
- 因子体系灵活可扩展，严格时序切分训练/测试集
- 输出形式：Jupyter Notebook 研究 + 后续可复用程序

### 方案设计
- 确定"黄金 + 医药生物"双标的
- 预测周期选择周频（日频聚合），理由是噪声可控、与宏观因子频率匹配
- 稳健性检验体系：滚动窗口 CV、样本外测试、Bootstrap CI、SHAP 因子重要性、基准对比
- 因子分四大类：宏观（14个）、市场（12个）、技术（10个）、情绪/另类（8个）

### 项目骨架搭建
- 创建 `financial_analysis/` 目录结构
- 实现三大数据源采集模块：
  - `akshare_source.py`：申万医药指数、沪深300、创业板、北向资金、PMI/CPI/PPI
  - `yfinance_source.py`：GLD/GC=F/DXY/VIX（网络受限，后续发现 AKShare 替代方案）
  - `fred_source.py`：美债利率、TIPS、CPI、失业率、联邦基金利率
- 实现因子基类 `Factor` + 因子注册表 + 44 个因子
- 实现特征工程管道（滞后、滚动统计、差分）
- 安装依赖（换用清华镜像解决国内 pip 慢的问题）

### 关键发现
- YFinance 在中国网络环境下被限流（Rate Limit），DXY/VIX/GLD 无法获取
- AKShare 的 `sw_index_daily` API 已变更为 `index_hist_sw`，需要适配
- 中证医疗指数（CSI 000933）可作为申万医药生物的补充数据源

---

## 第二阶段：XGBoost 模型尝试（2026-05-26 下午 ~ 05-27）

### V1 — 36 因子 XGBoost 预测下周涨跌
- 训练 XGBoost Classifier（方向）和 Regressor（幅度）
- 报告准确率 56.98%，Hit Ratio 59.30%
- 因子筛选在全部 428 周数据上做 IC 分析 → **测试集信息泄露到因子选择**
- 月频数据（CPI/PPI/M2）未做发布时滞 → **未来函数**
- 特征工程递归叠加（滞后→滚动→差分反复套娃），5 因子爆炸为 200 特征 → **维度灾难**

### 严格统计检验揭示真相
- Binomial Test：P-value = 0.87（无法拒绝"模型无效"的假设）
- Permutation Test：真实模型在69分位（31%的随机模型表现更好）
- 结论：模型没有可证明的预测能力

### V2 — XGBoost 预测拐点
- 尝试用局部极值标注真实拐点（18个底部/428周，占比4.2%）
- 极度不平衡下模型完全不敢发信号
- 结论：极稀疏事件不适合梯度提升树

### 关键教训
- 预测"每一周涨跌"本质是在预测噪声（周收益标准差 3.5%）
- Accuracy 对极度不平衡事件完全无意义（永远说"没底"就有 96% 准确率）
- 数据泄露的三个来源：特征筛选时机、月频数据对齐、特征工程爆炸

---

## 第三阶段：基于规则的探测器 V3（2026-05-28）

### 方法论转变
- 放弃预测"每一周"，专注识别"转折点"
- 用 `scipy.signal.argrelextrema` 标注局部极值（T 时刻是 [T-8, T+8] 区间最低点）
- 五条经济含义明确的规则，多数表决（Score≥2）产生信号

### 五规则探测器
| 规则 | 条件 | 经济逻辑 |
|:----:|------|----------|
| R | RSI(14) < 30 | 短期动能衰竭 |
| D | 13周回撤 < -10% | 跌幅充分 |
| C | 5年价格分位 < 15% | 历史低位 |
| P | 偏度 < -1 或波动 > 80分位 | 极端左尾 |
| M | ETF份额逆势增 | 机构抄底 |

### V3 结论
- Precision（信号级）：47%（9/19）— 但未做信号去重，连续信号重复计数
- 底部覆盖率：4个底部中抓到2个（急跌底和慢跌底各1个，2个温和底漏检）
- MFE/MAE：Armed 信号后 13 周期望收益 +5.0%，胜率 60%
- **根本问题**：标签定义使用 `argrelextrema(order=8)`，即 T±8 周的局部最低点，使用了未来 8 周信息

### V3.1~V3.4：多轮 Bug 修复
- **tracker Rule P 硬编码**：UI 显示 `vol > 50` 固定阈值，与模型动态 80 分位不一致 → 改读 df 列
- **tracker Rule M 永远 False**：UI 短路 → 改读 df 列
- **evaluate_signals FN 虚高**：`bottoms` 未过滤测试区间，全部 18 个历史底部计入 FN
- **sensitivity_analysis 用 3 规则**：与主模型 5 规则不一致
- **fred_source CPI 同比**：`pct_change(periods=12)` = 12 天涨幅而非 365 天
- **akshare_source margin 对齐**：沪深 index 对齐而非 date merge
- **label_turning_points 列名**：docstring 写 `label_desc` 实际为 `desc`
- **RSI 算法**：从 SMA 改为 Wilder 平滑 `ewm(alpha=1/14)`
- **价格分位**：从布尔均值改为 `scipy.stats.percentileofscore`

---

## 第四阶段：方法论深度重构 V4（2026-05-29 ~ 05-30）

### 核心批判（来自外部审查）
1. **标签的 look-ahead bias**：局部极值用了未来 8 周信息
2. **小样本统计不可靠**：18 个底部，Bootstrap CI 极宽
3. **信号重复计数**：连续 Armed 信号未去重，Precision 虚高
4. **规则独立性未验证**：RSI/DD/Cheap 可能高度共线
5. **MFE/MAE 幸存者偏差**：连续信号导致前向窗口重叠
6. **Threshold 数据挖掘**：看过全历史后定阈值
7. **评估框架错配**：用 Precision/Recall 评估 regime detection

### V4.0 — 标签改为纯前向收益
- 标签：13 周终值 > +5% 且 4 周 MAE > -8%
- 126/429（29.4%）为"好买点"（vs V3 的 18 个局部极值）
- 仅 67% 的 V3 底部是 V4 好买点——局部极值 ≠ 可盈利买点

### V4.1 — Triple Barrier 标签
- 改为路径依赖标签：先触及 +8% = SUCCESS，先触及 -5% = FAIL
- 134 Success / 243 Fail / 52 Neutral
- Label clustering：连续同向标签合并，134→12 个独立机会
- 评估框架：从 Precision/Recall 改为条件期望 E[ret|Armed] vs E[ret]
- 规则相关性：改用 P(A=1|B=1) 条件概率替代 Pearson
- 关键发现：P(DD=1|RSI=1)=1.0（RSI 超卖时回撤必超-10%），但 P(RSI=1|DD=1)=0.04
- 信号去重：18→2 个交易机会（保留 cluster 第一条）

### V4.2 — 信号去重修正 + Barrier 敏感性
- collapse_signals：保留第一条（最早可操作），去除"最高 score"前瞻偏差
- Barrier 参数敏感性：uplift 在全部参数组合下稳定在 **+7.9%**
- fred_source：CPI 改用 `pd.DateOffset(years=1)` 处理闰年
- 清理死代码（config、factors、backtest 目录）

---

## 第五阶段：实用化改造 V4.3（2026-05-31）

### Distance-to-Trigger（反推目标价）
- Rule D：`trigger = 13周最高价 × 0.90`
- Rule C：`trigger = 5年价格序列第 15 百分位`
- 每天输出：当前价 → 触发价 → 还需跌多少

### 三级警报系统
| 级别 | 条件 | 行为 |
|:----:|------|------|
| SILENT | Score=0, 距触发 >3% | 不推送 |
| YELLOW | Score=1 或距触发 <3% | 微信预警 |
| RED | Score≥2 状态翻转 | 微信报警 + GitHub Issue |

### 水位线 Dashboard
- 自包含 HTML（Lightweight Charts），浏览器直接打开
- 走势图上叠加回撤水位线（红线）和估值水位线（绿线）
- K 线砸穿虚线 = 击球区

### 推送通知模块
- 支持 Server酱（微信）、PushDeer、自定义 Webhook
- GitHub Actions 每交易日 14:45 自动运行
- SILENT 静默，YELLOW/RED 自动推送

### GitHub Actions CI 调试
- 问题 1：`grep -oP` 在 Ubuntu runner 上解析失败 → 改用 Python 脚本 `ci_parse.py`
- 问题 2：`matplotlib` 未安装但被 import → 彻底删除（从未实际使用）
- 问题 3：网络不稳定导致 push 失败 → 加 timeout 和重试
- 问题 4：AKShare 从 GitHub 美国服务器拉数据慢 → 加 20 分钟 timeout
- 最终将 CI 跑通，实现完全自动化

---

## 最终系统架构

```
financial_analysis/
├── REPORT.md                              # 方法论报告 V4.3
├── PROGRESS.md                            # 项目工作日志（本文件）
├── app/
│   ├── tracker.py                         # CLI 跟踪器（信号 + 距离触发 + 警报）
│   ├── dashboard.py                       # HTML 看板生成器
│   └── notify.py                          # 推送通知模块（Server酱/PushDeer/Webhook）
├── src/
│   ├── data_fetcher/
│   │   ├── akshare_source.py              # AKShare 数据采集
│   │   └── fred_source.py                 # FRED 数据采集
│   └── models/
│       └── turning_points.py              # Triple Barrier 标签 + 五规则探测器
│                                          # + Bootstrap + 条件期望 + 距离触发 + 警报
├── .github/workflows/medical_tracker.yml  # CI：每交易日 14:45 自动运行
└── dashboard.html                         # 自包含看板
```

---

## 核心指标总结

| 指标 | 值 |
|------|-----|
| 标签方法 | Triple Barrier (+8%/-5%, 13周, 路径依赖) |
| 规则数量 | 5（RSI/DD/Cheap/Panic/Micro） |
| 信号条件 | Score ≥ 2（多数表决） |
| E[ret\|Armed] 13周 | +8.4%（全量，n=10，de-overlapped） |
| Uplift vs unconditional | +7.7%（CI: +0.2% ~ +16.3%） |
| 条件 Hit ratio | 70%（vs 无条件 48%） |
| Barrier 参数稳健性 | uplift 稳定在 +7.9%（6 组参数组合） |
| 信号去重 | Cluster 第一条，间隔 <4 周合并 |
| RSI 算法 | Wilder smoothing（ewm alpha=1/14） |
| 评估框架 | 条件期望（非 Precision/Recall） |

---

## 关键教训

1. **Accuracy 在金融预测中几乎无用**：永远输出"不买"就有 96% 准确率
2. **数据泄露无处不在**：因子筛选时机、月频数据对齐、特征工程叠加、甚至 label 定义本身
3. **局部极值 ≠ 可盈利买点**：33% 的 V3 底部在 V4 定义下不是好买点
4. **Precision/Recall 不适合 regime detection**：更适合用条件期望 E[ret|state]
5. **规则数量比规则复杂度更重要**：5 条简单规则的多数表决比 XGBoost 更稳健
6. **小样本下 Bootstrap CI 不可解释**：n=2 时 CI [0%,100%]，统计推断失效
7. **信号去重至关重要**：连续信号 collapse 后 18→2 个交易机会
8. **Triple Barrier 的 uplift 对参数不敏感**：+7.9% 在全部参数组合下稳定
9. **Wilder RSI 比 SMA RSI 更保守**：33.3 vs 28.8，减少假触发
10. **自动化推送需要静默机制**：每天都推会信息疲劳，状态翻转才推才有价值

---

## 版本时间线

| 日期 | 版本 | 里程碑 |
|------|:----:|--------|
| 05-26 上午 | — | 方案讨论、需求对齐、项目骨架搭建 |
| 05-26 下午 | V1 | XGBoost 36 因子预测涨跌。含 3 处数据泄露 |
| 05-27 | V2 | XGBoost 预测拐点。样本不足，废弃 |
| 05-28 | V3 | 五规则探测器 + 局部极值标签。Precision 47% |
| 05-29 | V3.1~3.4 | 多轮 Bug 修复（硬编码、FN 虚高、CPI 失真等） |
| 05-30 上午 | V4.0 | 标签改为前向收益（去除未来函数） |
| 05-30 下午 | V4.1 | Triple Barrier + 条件期望 + 条件概率 + Benchmark |
| 05-30 晚上 | V4.2 | collapse 去前瞻偏差 + Barrier 敏感性 + 闰年修正 |
| 05-31 | V4.3 | Distance-to-Trigger + 三级警报 + 水位线 + CI 推送 |
