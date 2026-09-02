# 农业板块周期监控系统 — 工作日志

> 隶属仓库 `financial_analysis`（与医药板块监控器共享仓库与每日 14:45 推送），独立子目录 `agriculture/`，不改动医药项目任何代码。
> 目标：为农业主题基金投资者提供 ①买卖信号预测 ②指数连续跌 n 天的概率参考 ③板块周期状态估计 ④高稳健因子库；约束：基金持有满 7 天避免惩罚性赎回费（1.5%），半年维度追求足够收益率。

---

## 状态总览

| 阶段 | 状态 | 说明 |
|---|---|---|
| 0. 项目调研与骨架 | ✅ 完成 2026-09-02 | 复用医药项目架构约定，建立日志体系 |
| 1. 外文文献调研 | ✅ 完成 2026-09-02 | 详见 `docs/literature_review.md`，42 条文献（含追加的连跌×基本面专项 7 篇），引文经 Crossref/JSTOR 核验 |
| 1.5 追加调研：连跌×基本面 | ✅ 完成 2026-09-02 | 综述 §10 + L-B2 条件化连跌概率表设计 |
| 2. 建模策略提案 | ✅ **用户已确认 2026-09-02（全部按推荐）** | 详见 `docs/strategy_proposal.md` v1.1 |
| 3. 数据管道 | 🔄 进行中 | akshare 数据源可用性探测 |
| 4. 因子库与周期估计 | ⏸ 未开始 | |
| 5. 模型与回测（严格训练/测试分离） | ⏸ 未开始 | |
| 6. 接入每日 14:45 共享推送 | ⏸ 未开始 | |
| 7. 文档与看板 | ⏸ 未开始 | |

---

## 第 0 章：项目调研与骨架搭建（2026-09-02）

### 步骤 0.1 现有医药项目架构调研 ✅

- 仓库根：`D:\Program\claudecode_data\financial_analysis`，git 干净，分支 main。
- 医药项目结构：`app/`（tracker/server/dashboard/notify/monthly_audit）+ `src/models/`（rule_registry 统一规则引擎、indicators、turning_points、factor_optimizer）+ `src/data_fetcher/`（akshare/fred）+ `data/processed/signals.db`（SQLite，含 system_log 错误表）。
- 推送机制：`.github/workflows/medical_tracker.yml`，cron `45 6 * * 1-5`（UTC，= 北京时间周一至五 14:45），单 job 内：安装依赖 → notify.py 计算 → ci_parse 解析 → dashboard 生成 → **一次 git commit & push**（dashboard.html + signals.db）→ 红色警报时开 issue。本机另有 Windows 计划任务 14:45 跑 `run_tracker.bat` 做桌面通知。
- 因子治理：RULE_DEFS 单一来源 + MODEL_CONFIGS 版本化 + 月度审计（三漏斗筛选、健康分级、漂移监测），阈值不固化、Evidence 驱动。
- **对农业项目的复用决定**：目录结构、SQLite 日志约定、"信号=状态识别而非点位预测"的方法论、月度审计思路全部可复用；医药代码本身零改动。工作流文件新增农业步骤（用户已授权共享推送）。

### 步骤 0.2 创建农业子项目骨架 ✅

```
agriculture/
  PROGRESS.md            本文件（工作总日志）
  logs/research_log.md   文献调研日志（每步更新）
  logs/error_log.md      报错日志（有错必记）
  docs/literature_review.md   外文文献综述（理论支撑）
  docs/strategy_proposal.md   建模策略提案（待确认）
  src/  app/  data/raw/  data/processed/
```

---

## 第 1 章：外文文献调研（2026-09-02）

过程与每条检索结果记录于 `logs/research_log.md`；最终综述沉淀于 `docs/literature_review.md`。
覆盖六条理论线：①短期反转与连续下跌日 ②行业动量与板块轮动 ③农业/生猪周期（蛛网模型、畜产品周期）④宏观与商品因子 ⑤制度转换（Markov 区制）⑥数据窥探与回测过拟合控制。

**结论：文献支撑充分，建模策略已成稿，进入用户确认环节。**

---

## 第 2 章：建模策略提案（2026-09-02）

`docs/strategy_proposal.md` 已完成：五层信号架构（周期状态层 → 连跌概率层 → 因子打分层 → 融合买卖信号层 → 基金执行约束层）、训练 2014-06~2022-12 / 测试 2023-01~2026-08 严格分离、 walk-forward 滚动验证、White Reality Check + Deflated Sharpe 控制数据窥探。
**状态：2026-09-02 用户批复"全部按推荐"，策略 v1.1 定稿，进入建模阶段。**

> 注：表中训练/测试切分以 strategy_proposal.md §3 为准（训练 2005-01~2021-12，测试 2022-01 起）；本行早期草稿数字作废。

---

## 第 3 章：用户确认与追加调研（2026-09-02）

### 步骤 3.1 用户确认 ✅

- 用户批复：**全部按推荐**（主标的 801010+000122、混合信号风格、低换手、半年绝对≥4%或超额≥3%、共享推送+桌面通知、猪价源带降级链）。
- 决策已回写 `docs/strategy_proposal.md` §6。

### 步骤 3.2 追加需求：连跌 n 天概率与基本面的关系 ✅

- 用户要求："找到连续跌 n 天的概率与基本面的关系，便于我判断买入信号，请你也做个调研"。
- 执行：7 篇外文文献专项调研（全部核验，1 处期刊出处纠正：Da et al. 2014 为 Management Science 而非 RFS），详见 `logs/research_log.md` [R-13] 与综述 §10。
- 核心结论：连跌分两类——流动性/非信息冲击型（放量、跟跌、高波动、大盘强）倾向反弹可抄；基本面现金流利空型（独跌、缩量、猪价利空中途）倾向惯性观望。短尺度看流动性条件，半年尺度看估值/情绪/猪周期相位。
- 落地：L-B 层升级为 **L-B2 基本面条件化连跌概率表**（7 条件变量，见 strategy_proposal.md §4），其中"猪周期相位 → 利空是否已定价"为文献整合的原创检验项，仅训练段估计、测试段验证。

---

## 第 4 章：建模与部署（2026-09-02，用户授权"继续往下做 + 部署到 GitHub"）

### 步骤 4.1 M1 数据管道 ✅

- `src/data_fetcher/akshare_source.py`：9 类数据源 + CSV 缓存 + `_ffill_to_calendar` 防前视对齐（宏观按次月 15 日可得）。
- 期间修复：中文月份解析（#7）、周末可得日被 reindex 丢弃的延迟失真（#12）。

### 步骤 4.2 M2+M3 游程概率层与周期状态层 ✅

- `streak_stats.py`：频率表/一阶马氏链/条件收益 + L-B2 七条件分层表（样本 <30 自动合并）。
- `cycle_regime.py`：2 状态 Markov 区制（statsmodels，`p[1->0]` 参数化修复 #9）+ HP 月频周期相位（Ravn-Uhlig λ，解包 bug 修复 #8）+ 猪价独立相位。
- 关键产出（训练段冻结）：连跌≥5 天年均 3.6 次、P(明日涨|连跌7天)=0.407；区制 p00/p11≈0.89。

### 步骤 4.3 M4+M5 校准与反过拟合 ✅（V1.0 → V1.1 → V1.2 三轮迭代）

- 因子三漏斗（t≥3）：21 个候选中 5 个入选——halloween(t=6.2)、skew_13w(t=5.0)、vol_pctile_20d(t=5.0)、meal_mom_60d(t=3.6)、mom_120d(t=3.3)；vol_ratio 与 vol_pctile 相关 0.73 被去冗。
- **规则族诊断**（仅子训练/验证段）：周期相位门（cycle_score>0）为两段最稳健的简单族（子训练超额 +4.2%、验证段 +11.7%），远优于 MA 系/动量系/复合分数系。
- **V1.2 周期主导架构**：周期迟滞门（θ_in=0/θ_out=−0.2，a priori 固定）为主信号；恐慌分≥80 为加速买入；退出模式 6 配置网格。
- 反过拟合结果：PBO 0.275（通过）；RC p≈0.5 与 DSR 0.74 未达显著（如实报告，策略定位=状态识别与赔率改善，非收益承诺）。
- **验证段**（2016-2021）：年化 +9.3% vs 买入持有 +0.2%，相对门槛全过。**测试段**（2022-，第 3 次也是最后一次使用，披露于配置）：年化 +4.7% vs 指数 −7.0%，**超额 +12.6%**，回撤 −32.9% vs −46.1%，3 笔交易全盈，**7 天约束违规 0 次**。
- 冻结 `src/models/model_config_agri.json`（V1.2）。

### 步骤 4.4 M6 每日链路与共享推送 ✅

- `tracker_agri.py`（实测输出：YELLOW / 持仓中 62 天 / 周期扩张(-0.06) / 猪周期扩张 / 收缩概率 86%）+ `ci_parse_agri.py` + `db_agri.py`（独立 SQLite）+ `dashboard_agri.html` 自包含看板。
- `medical_tracker.yml` 增量修改（授权范围内）：Commit 前插入农业三步（Run/Parse/Dashboard），同一次运行同一次 push；农业 RED 开 `agri-alert` issue。医药代码零改动。

### 步骤 4.5 M7 自检与审计 ✅

- `scripts/selfcheck.py`：**SELF-CHECK PASSED**——宏观防前视阶梯不变量、前瞻收益仅作标签、T+1 成交、26 笔交易 0 违规、冻结表值域、全历史复算一致。
- `app/monthly_audit_agri.py`：因子漂移/触发频率/SQLite 复盘/数据健康四块，只监测不自动改配置。

### 当前状态

代码全部就绪，待安全审查（codex-security）后推送 GitHub；首个 CI 运行于推送后当日 14:45（北京时间）触发。

---

### 步骤 3.3 本地数据源可用性探测 ✅（发生于第 4 章之前，存档于 research_log [R-14]）

- 目的：验证 akshare 本地环境下 801010 指数、生猪价格、玉米/豆粕等关键数据的可用性（L-B2 与 L-A 依赖猪价数据）。
- 结果：主链路 100% 可用（801010 全历史日线、000122 对照、沪深300、玉米/豆粕期货、宏观、两融）；**猪周期数据族可用**——`index_hog_spot_price` 2015 年起周频 + 生猪期货 LH0 2021 年起日频（决策点 6 落定为双源）。
- 缺口与替代：东财指数接口被代理拦截（改新浪源）；农林牧渔 PE/PB 历史不可得（估值维度改用价格 5 年分位）。
- 详见 `data/raw/data_probe_20260902.md` 与 `logs/research_log.md` [R-14]；报错处理见 `logs/error_log.md` #3–#6。
- 下一步（M1）：编写 `src/data_fetcher/akshare_source.py`，落地防前视对齐与本地缓存。
