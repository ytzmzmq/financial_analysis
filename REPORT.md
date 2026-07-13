# 医药板块风险收益比监控器 — V5.2 因子优化框架

**日期**: 2026-07-13 | **版本**: V5.2

---

## 一、定位

这是一个**经过五阶段严格因子筛选的极端超跌检测器**。仅保留统计学上无法被随机性解释的因子，并按历史超额贡献度分配权重。

---

## 二、方法论核心：五阶段因子筛选与赋权

### 阶段 1：候选因子池构建

候选因子池分三层：11 个核心因子（始终可计算）+ 3 个数据依赖因子（V4/L4/S3，需额外数据源）+ 3 个外部环境因子（S4/E1/E2，候选但未纳入 MODEL_CONFIGS）。所有因子二值化(0/1)，仅使用 T 日及以前数据。

| 维度 | 因子 | 逻辑 |
|------|------|------|
| **估值(V)** | V1: 5年价格分位 < 15% | 历史低位区域 |
| | V2: 距52周低点 < 5% | 接近一年低点 |
| | V3: 连续下跌 > 8周 | 长期阴跌后估值修复 |
| | V4: 真实PE < 5年15%分位 | PE估值冰点（需PE数据） |
| **量价(L)** | L1: RSI Wilder < 30 | 动能衰竭 |
| | L2: 13周回撤 < -12% | 深度回撤 |
| | L3: 波动率收缩 < 2年25分位 | 暴风雨前的宁静 |
| | L4: 成交量 < 2年10%分位 | 地量冰点（需成交量数据） |
| **动能(M)** | M1: 收益偏度 < -1.5 | 极端左尾事件 |
| | M2: 4周累计跌幅 > 8% | 加速下跌 |
| | M3: MACD 柱状线创13周新低 | 动能极值 |
| **资金(S)** | S1: 价格低点+RSI不新低 | 底背离 |
| | S2: 下跌放缓 | 动能减弱 |
| | S3: 融资底背离 | 价格13周新低+融资逆势加仓（V5.1引入） |
| **外部(E)** | S4: 北向资金背离 | 候选，未纳入（样本不足） |
| | E1: 大盘熊市 | 候选，未纳入（与V1共触发86%） |
| | E2: M2加速 | 候选，未纳入（与M1共触发89%） |

S1/S2 为原始资金面候选因子，经三漏斗检验后未通过（S1 频率偏高且 Uplift CI 不达标，S2 条件收益不足）。S3 为 V5.1 引入的融资底背离因子，统计显著性更优，已通过筛选并纳入 MODEL_CONFIGS。S4/E1/E2 为 V5.2 新增的外部环境候选因子，代码骨架保留在 RULE_DEFS 但未加入 MODEL_CONFIGS——经五阶段筛选均未通过（详见第六节）。

### 阶段 2：单因子三漏斗检验

每个候选因子必须同时通过三道漏斗，否则直接淘汰。

**漏斗 1 — 稀疏度**：2% <= 触发频率 <= 15%。频率太低是统计孤本，太高则无"极值"意义。

**漏斗 2 — 绝对收益**：因子触发后 13 周期望收益 > +5.0%。

**漏斗 3 — 稳健性置信度**：Uplift = 条件期望 - 无条件期望。Bootstrap 2000 次，95% CI 下限必须 > +1.0%。

**检验结果（V5.2 三漏斗）**：16 个候选因子，**4 个通过三漏斗**：

| 因子 | 频率 | E[ret\|触发] | Uplift | 95% CI |
|------|:---:|:----------:|:------:|:------:|
| **L1: RSI超卖 (<30)** | 2.1% | +9.5% | +8.9% | [+3.9%, +14.1%] |
| **M1: 偏度异常 (<-1.5)** | 4.1% | +8.7% | +8.0% | [+2.8%, +13.1%] |
| **S3: 融资底背离** | 4.6% | +6.2% | +5.6% | [+1.8%, +9.4%] |
| **V1: 估值冰点 (<15%分位)** | 14.9% | +5.6% | +4.9% | [+1.1%, +8.7%] |

### 健康监测层：Evidence-based 因子评估

通过三漏斗的因子接受多维 Evidence 综合评估，输出 Grade + Confidence + Action，不直接淘汰因子。

**Evidence 来源**（可扩展）：滚动窗口 uplift 通过率、触发集中度 (CV)、A1 近3年条件收益漂移、近半年触发频率漂移、跨窗口 uplift 衰减趋势。未来可扩展 Seasonality、Regime、Market Beta、Industry Rotation 等维度。

**Grade 分类**：

| Grade | 含义 | Action |
|-------|------|--------|
| Stable | ≥75% 窗口 uplift 为正，无衰减趋势 | 保持当前权重 |
| Regime-dependent | 触发集中在特定市场阶段（如暴跌期），触发时 uplift 仍正向 | 继续观察，不调整权重 |
| Declining | uplift 跨窗口呈下降趋势 | 重点监测，下次审计复查 |
| Unstable | 多数窗口 uplift 为负或无规律 | 进入 V5.3 候选淘汰列表 |

**Confidence 评估**：根据 Evidence 充足程度给出 High / Medium / Low。例如窗口数 ≥3 且触发 ≥15 次 → High；低频因子 → Medium/Low；Declining 仅基于 2 个有效窗口 → Low。

**当前 4 因子的评估结果：**

| 因子 | Grade | Confidence | Evidence 摘要 |
|------|:-----:|:----------:|--------------|
| L1_rsi_30 | Stable | Medium | 低频(9次)，2/2窗口正向，A1漂移89%需关注 |
| M1_skew_neg | Regime-dependent | Medium | CV=1.51，触发集中在暴跌期，是设计意图 |
| S3_margin_diverge | Stable | High | 4/4窗口正向(CV=0.42)，A1漂移仅10%，最稳定 |
| V1_price_5y_low | Declining | High | 衰减比0.13(+25.6%→+2.2%/+4.5%)，方向仍正但幅度大幅缩小 |

**版本决策 (Version Recommendation)**：

| 推荐 | 条件 |
|------|------|
| Keep Current | 无 Unstable，Declining ≤1 |
| Keep Current — 重点观察 | 1 个 Declining，需连续 2 次审计确认 |
| Recommend V5.3 Review | ≥2 个 Declining 或 ≥1 个 Unstable |

当前决策：**Keep Current — 重点观察**。V1 为唯一 Declining 因子，需下次审计复查，若持续 Declining 则启动 V5.3 评估。

### 阶段 3：条件概率去重

计算 P(A=1|B=1)。M1 和 V1 的条件概率 < 0.65，两者独立——偏度异常捕获的是恐慌性急跌，估值冰点捕获的是阴跌磨底，维度不重叠。无需剔除。

### 阶段 4：Uplift 驱动评分卡

按 Uplift 贡献度分配权重，离散化到 0.5 步长（总分 9.5 分）。

| 因子 | Uplift | 权重建模 | 最终得分 |
|------|:------:|:--------:|:-------:|
| L1: RSI超卖 | +7.1% | 25% | **3.0** |
| M1: 偏度异常 | +8.0% | 28% | **2.5** |
| S3: 融资背离 | +5.5% | 20% | **2.0** |
| V1: 估值冰点 | +4.9% | 17% | **2.0** |

V5.2 采用更均匀的权重分布（3.0/2.5/2.0/2.0），避免单因子主导。满分 9.5，实际判定不依赖单一 Score 阈值，而是两层机制：准入 + 分级。

### 阶段 5：两层判定机制

V5.2 不再使用单一 Score 阈值，改为两层判定：

**第一层 — 准入**：n_factors >= 2（至少 2 个因子同时触发方可 Armed）

**第二层 — 分级**：

| Tier | 条件 | 含义 |
|------|------|------|
| hold | n_factors < 2 | 无信号 |
| weak_armed | n_factors = 2，不含 L1/M1 | 弱 Armed |
| standard_armed | n_factors = 2，含 L1 或 M1 | 标准 Armed |
| strong_armed | n_factors >= 3 | 强 Armed |

回算结果（435 周）：8 次 Armed，其中 4 次 strong_armed、2 次 standard_armed、2 次 weak_armed。

Score 降为辅助显示变量，不再作为 Armed 主判定依据。

---

## 三、V5.2 探测器

### 与 V4/V5.1 的对比

| | V4 (五规则等权) | V5.1 (评分卡加权) | V5.2 (两层判定) |
|---|---|---|---|
| 因子数 | 5（等权各1分）| 3（加权） | 4（加权） |
| 筛选方法 | 人工阈值 | 三漏斗统计检验 | 三漏斗 + 监测层 |
| 权重 | 等权投票 | Uplift 驱动 | Uplift 驱动 |
| 阈值 | Score≥2/5 | Score≥3.5 | n_factors≥2 + tier |
| 入选标准 | 常识判断 | CI 下限 > 1% | CI 下限 > 1% |
| 架构 | V5Detector | V5Detector | rule_registry 统一入口 |

V5.2 相对 V5.1 的关键改进：新增 L1(RSI超卖) 覆盖量价维度，采用两层判定避免单因子误触发，Score 降为辅助变量。

### 当前架构

```
rule_registry.py — 统一规则引擎
  ├── RULE_DEFS: 4 个因子定义（名称/维度/条件/显示文本）
  ├── MODEL_CONFIGS: 版本化模型参数（V5.1/V5.2 并存）
  ├── evaluate_signal(): 实时信号判定 → SignalResult
  └── evaluate_signal_history(): 全历史回算 → DataFrame
```

### 当前信号

```
模型: V5.2 | 满分: 9.5 | Armed规则: n_factors_tier
Score: 7.0  [strong_armed]  (3 factors)
L1 RSI超卖(3.0分): ★ 已触发（RSI 28.3, 需 < 30）
M1 偏度异常(2.5分): ★ 已触发（偏度 -1.82, 需 < -1.5）
S3 融资背离(2.0分): ★ 已触发（价创13周新低 + 融资逆势加仓）
V1 估值冰点(2.0分): 未触发（分位 22%, 需 < 15%）
→ RED（Strong Armed, 3 因子同时触发）
```

---

## 四、使用指南

```bash
python app/tracker.py                    # CLI 信号
python app/dashboard.py && start dashboard.html  # 看板
python app/server.py                      # 实时服务器
```

| Tier | 条件 | 仓位 |
|------|------|:----:|
| hold | n_factors < 2 | 0% |
| weak_armed | n_factors = 2，不含 L1/M1 | 15% |
| standard_armed | n_factors = 2，含 L1 或 M1 | 40% |
| strong_armed | n_factors >= 3 | 60% |

---

## 五、已知局限

1. L1 仅 9 次触发，边际增益的统计样本偏小（Confidence: Medium，Evidence-based 监测标记为 Stable）
2. 估值因子用价格分位替代真实 PE，可能在盈利大幅变动时失真
3. n=8 独立机会，统计仍然偏小
4. 4 个因子覆盖 4 个维度（量价/动能/资金/估值），已测试宏观外溢（北向/大盘/M2）、跨市场（XBI/IBB）、产业链（化工/食品/房地产）三类外部因子均未通过筛选——缺少宏观流动性和政策事件维度的独立信息源
5. tier 分级规则（standard vs weak）基于经验判断；A6 组合统计提供了初步实证数据（含V1组合收益17-19%、S3+V1为13.4%），但样本量尚不足以据此调整
6. V1 的 Evidence-based Grade 为 Declining (High Confidence, 衰减比0.13)，需下次审计验证是否持续衰减。若连续 2 次 Declining 则启动 V5.3
7. 未引入非线性组合：L1×M1 同时触发时的交互效应未被单独测量

---

## 六、外部因子探索（已验证排除）

2026-07-13 对三条外部因子扩展路径做了系统测试，结论一致：外部因子不提供独立于现有 4 因子的预测信息。

**宏观外溢因子（S4/E1/E2）**：3 个候选因子加入 factor_optimizer 的五阶段筛选管线。S4_north_diverge 触发率过低（<2%）；E1_market_bear 与 V1_price_5y_low 条件概率 86.2%（都捕获"全面下跌"）；E2_m2_accel 与 M1_skew_neg 条件概率 88.9%（M2 加速期恰好是市场暴跌期）。代码骨架保留在 RULE_DEFS 但未加入 MODEL_CONFIGS。

**跨市场生物医药指数（XBI/IBB）**：801150 与 XBI 同期相关性仅 0.224，领先 1 周仅 0.067。中美医药板块受各自监管周期、集采政策、医保制度驱动，联动性不足。

**产业链因子（化工/食品/房地产/消费者信心）**：10 个候选因子全部未通过三漏斗。核心发现：板块间同期周收益率相关性 0.44-0.67，但领先-滞后相关性全部接近零。化工期货与医药相关性仅 0.057。板块间是同期共振而非因果传导。

**结论**：V5.2 四因子模型保持原样最优。未来因子挖掘应聚焦医药行业内部指标（集采节奏、IND审批、ETF申赎、医保结余）。

---

## 七、未来优化方向

1. **医药行业内部指标**：集采政策节奏、IND 审批数据、医药 ETF 申赎变化、医保基金结余——这些是尚未测试的、可能提供独立信息的方向
2. **动态再平衡**：每季度重新运行五阶段框架，MODEL_CONFIGS 权重随市场结构变化自动调整
3. **宏观状态分层**：在牛市/熊市/震荡市分别检验因子有效性，建立 regime-dependent 评分卡
4. **tier 分级回测验证**：用历史数据验证 weak/standard/strong 三档的实际收益差异
5. **引入非线性组合**：L1×M1 同时触发时的交互效应

---

## 八、版本记录

| 版本 | 关键变更 |
|------|----------|
| V1-V2 | XGBoost 尝试（已废弃） |
| V3 | 五规则等权投票 + 局部极值标签 |
| V4 | Triple Barrier 标签 + 条件期望评估 + ETF 实时数据 |
| V5.0 | 五阶段因子筛选 + Uplift 驱动评分卡 + 阈值滑动寻优。仅 2 个因子通过统计检验 |
| V5.1 | 新增 S3(融资底背离)，3 因子评分卡 M1=4.5/S3=3.0/V1=2.5，阈值 3.5 |
| **V5.2** | **新增 L1(RSI超卖)，4 因子两层判定(n_factors≥2+tier)，rule_registry 统一入口，Score 降为辅助变量。双口径月审(A3a live + A3b replay + A5 组合表)。注："7阶段"指工程重构步骤（指标收口→规则引擎→DB扩展→消费方改造→月审升级→切配置→清理），方法论仍为五阶段筛选** |

---

## 附录：代码结构

```
financial_analysis/
├── REPORT.md
├── app/
│   ├── tracker.py                         # CLI 跟踪器 (消费 evaluate_signal)
│   ├── server.py                          # 实时看板服务器 (V5.2 动态适配)
│   ├── dashboard.py                       # 自包含 HTML 看板
│   ├── db.py                              # SQLite: signals 表(19列) + system_log
│   ├── notify.py                          # 微信推送
│   └── monthly_audit.py                   # 月度审计 (A1-A6 + 稳定性监测 + Part B)
├── src/
│   ├── data_fetcher/
│   │   ├── akshare_source.py              # AKShare + Sina ETF 实时
│   │   └── fred_source.py                 # FRED
│   └── models/
│       ├── rule_registry.py               # 统一规则引擎 (RULE_DEFS + MODEL_CONFIGS)
│       ├── indicators.py                  # 共享技术指标 (rsi_wilder + macd_histogram)
│       ├── turning_points.py              # distance_to_trigger + alert_level + Triple Barrier
│       └── factor_optimizer.py            # 三漏斗筛选 + Evidence-based 健康监测 + 版本决策
└── .github/workflows/medical_tracker.yml  # CI 每交易日
```
