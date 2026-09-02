# 农业板块周期监控系统 — 工作日志

> 隶属仓库 `financial_analysis`（与医药板块监控器共享仓库与每日 14:45 推送），独立子目录 `agriculture/`，不改动医药项目任何代码。
> 目标：为农业主题基金投资者提供 ①买卖信号预测 ②指数连续跌 n 天的概率参考 ③板块周期状态估计 ④高稳健因子库；约束：基金持有满 7 天避免惩罚性赎回费（1.5%），半年维度追求足够收益率。

---

## 状态总览

| 阶段 | 状态 | 说明 |
|---|---|---|
| 0. 项目调研与骨架 | ✅ 完成 2026-09-02 | 复用医药项目架构约定，建立日志体系 |
| 1. 外文文献调研 | ✅ 完成 2026-09-02 | 详见 `docs/literature_review.md`，36 条文献（顶刊 6 篇：Econometrica×2、QJE×2、JPE×1、AER×1；JF/JFE/RFS 合计 13 篇），引文经 Crossref/JSTOR 核验 |
| 2. 建模策略提案 | ✅ 完成 2026-09-02 | 详见 `docs/strategy_proposal.md`，**待用户确认后建模** |
| 3. 数据管道 | ⏸ 未开始（等策略确认） | AKShare：申万农林牧渔 801010.SI / 中证农业 000122 |
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
**状态：等待用户确认，未动工建模。**
