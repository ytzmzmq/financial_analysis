# 农业板块周期监控系统

为**农业主题基金**投资者构建的周期状态识别系统：监测申万农林牧渔指数（801010），
输出买卖建议、连跌 n 天概率参考、周期相位与猪周期状态。与仓库根目录的医药板块
监控器共享同一次 GitHub Actions 每日运行（北京时间 14:45），**每天一条合并微信推送**，
医药项目代码零改动。

**线上入口（GitHub Pages，实测可达）**
- 🌾 农业看板：<https://ytzmzmq.github.io/financial_analysis/dashboard_agri.html>
- 💊 医药看板：<https://ytzmzmq.github.io/financial_analysis/dashboard.html>
- 🏠 落地页：<https://ytzmzmq.github.io/financial_analysis/>
- 📖 使用手册：[REPORT.md](REPORT.md)

## 每日信号（GitHub Actions 自动）

工作日 14:45 自动运行 `agriculture/app/tracker_agri.py`：
- 计算 CycleScore（HP 月频周期分量 z 值）、猪周期相位、Markov 收缩区制概率、
  恐慌分（偏度+波动分位）、连跌天数与 L-B2 基本面条件化参考卡；
- 警报三级：**RED**=今日有可执行动作（买入/卖出，T+1 基金申赎）、**YELLOW**=接近触发
  或持有中风险提示、**SILENT**=常态；
- 结果写入 `agriculture/data/processed/signals.db`（SQLite），生成自包含看板
  `dashboard_agri.html`，与医药看板同一次 commit/push；
- **微信合并推送**：`notify_combined.py` 把医药+农业拼成**每天一条** Server酱消息
  （标题 `医药:x 农业:y｜农业快照`，正文含两板块信号全文与看板链接）；
- **滚动日报 issue**：RED/YELLOW 日在 `agri-daily` 标签的滚动 issue 追加当日全文，
  RED 另开 `agri-alert` 警报 issue；
- **GitHub Pages**：gh-pages 分支随每日运行自动更新，看板浏览器直达。

本地查看：直接打开仓库根目录 `dashboard_agri.html`（离线自包含），或用上面的 Pages 地址。

## 信号规则（V1.2 周期主导，冻结于 src/models/model_config_agri.json）

- **主信号·周期迟滞门**：CycleScore > 0 持有，< −0.2 清仓（Schmitt 触发器防抖）。
  理论依据：蛛网定理（Ezekiel 1938, QJE）与畜产品周期（Rosen et al. 1994, JPE）——
  农业板块存在文献级内生周期；规则族诊断显示周期门是训练/验证两段都稳健的最优简单族。
- **恐慌加速买入**：恐慌分（13 周偏度 + 波动率分位）≥ 80 且非收缩区制 → 立即持有
  （Nagel 2012 RFS：高波动期反转溢价最大）。
- **卖出**：周期门下穿，或区制+趋势双确认（可选模式，冻结配置当前为 cycle_only）。
- **基金执行约束**：T 日收盘信号 → T+1 未知价执行；**强制 7 自然日最短持有**
  （规避 <7 天 1.5% 惩罚性赎回费）；申购 0.15% / 赎回 0.5% 计入回测。

## 目录结构

```
agriculture/
  app/
    tracker_agri.py        每日信号计算（CLI/CI 共用）
    ci_parse_agri.py       CI 输出解析（alert/score/快照）
    notify_combined.py     医药+农业合并微信推送（每天一条）
    dashboard_agri.py      自包含 HTML 看板 → 仓库根 dashboard_agri.html（含净值对比图）
    db_agri.py             SQLite（signals + system_log，独立于医药库）
    monthly_audit_agri.py  月度因子审计（含 alphalens 式 IC 诊断，只监测不自动改配置）
  src/
    data_fetcher/akshare_source.py  数据源 + CSV 缓存 + 防前视对齐
    models/indicators_agri.py       共享指标
    models/cycle_regime.py          区制模型（Hamilton 1989）+ HP 周期相位
    models/streak_stats.py          连跌频率/马氏链/L-B2 条件表
    models/factor_library.py        因子定义（单一来源）
    models/pipeline.py              特征流水线
    models/model_config_agri.json   冻结配置（阈值/表/回测指标，版本化）
    backtest/backtester.py          T+1 + 费用 + 7 天约束回测器
    backtest/anti_overfit.py        Reality Check / DSR / PBO(CSCV)
  scripts/
    build_cache.py         构建本地数据缓存
    calibrate_signals.py   校准流水线（筛选→网格→检验→冻结）
    selfcheck.py           自检（防前视/执行约束断言）
    backfill_signals.py    历史信号回填（is_live=0，不覆盖实盘行）
    screen_new_factors.py  新增候选因子筛查报告（不动冻结配置）
  docs/literature_review.md   42 条外文文献综述（理论支撑）
  docs/strategy_proposal.md   建模策略 v1.1（含反过拟合协议）
  logs/research_log.md        文献调研日志
  logs/error_log.md           报错日志（13 条已解决记录）
  PROGRESS.md                 工作总日志
```

## 本地运行

```bash
pip install -r agriculture/requirements.txt
python agriculture/scripts/build_cache.py        # 构建缓存
python agriculture/app/tracker_agri.py           # 今日信号
python agriculture/app/dashboard_agri.py         # 生成看板
python agriculture/scripts/selfcheck.py          # 自检
python agriculture/scripts/backfill_signals.py   # 历史信号回填（一次性/数据修复）
python agriculture/app/monthly_audit_agri.py     # 月度审计
python agriculture/scripts/calibrate_signals.py  # 重校准（默认不必跑）
python agriculture/scripts/screen_new_factors.py # 新因子筛查报告（不动配置）
```

本机桌面通知（可选）：根目录 `run_tracker_agri.bat`，或自行注册计划任务（见 bat 内注释）。
微信推送由 CI 的 `notify_combined.py` 自动完成，本地无需配置。

## 诚实披露（必读）

- **测试段被使用 3 次**（V1.0/V1.1/V1.2 各一次终评），其统计量存在乐观偏差；
  真实基准以实盘与月度审计为准。
- **微信推送每天 1 条**（医药+农业合并，Server酱免费额度 5 条/天只占 1 条）；
  推送失败不阻断流水线（看板/issue/数据提交照常）。
- V1.2 冻结结果：验证段（2016-2021）年化 +9.3% vs 买入持有 +0.2%；测试段（2022-）
  年化 +4.7% vs 指数 −7.0%（超额 +12.6%），回撤 −32.9% vs −46.1%，7 天违规 0 次。
- White Reality Check（p≈0.5）与 DSR（0.74<0.9）**未达显著**——本系统定位是
  「周期状态识别 + 赔率改善 + 回撤收缩」，不承诺收益率；半年目标（绝对 ≥4% 或
  超额 ≥3%）达成率约 52%。
- 数据全部来自 AKShare 免费接口；宏观数据按"次月 15 日可得"对齐防前视。
