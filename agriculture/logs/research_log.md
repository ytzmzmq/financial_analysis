# 文献调研日志（research_log）

> 规则：每完成一个小步骤立即追加一条记录。检索工具：WebSearch/WebFetch；限定外文期刊（英文为主），中文资料不作为理论依据。
> 格式：`[步骤号] 时间 | 动作 | 结果摘要`

## [R-00] 2026-09-02 | 调研准备
- 确定六条检索线索（对应需求 1~5）：短期反转/连跌日、行业动量与板块轮动、农业商品周期（蛛网/畜产品周期/猪周期）、宏观与商品因子、区制转换与周期估计、数据窥探与回测过拟合控制。
- 计划每条线索 2~4 次检索，共 12~16 组检索，产出 ≥25 篇可引用的外文期刊文献。

## [R-01] 2026-09-02 | 检索批次 1：短期反转与连续下跌
- 检索词：`Jegadeesh 1990 evidence predictable behavior security returns short horizon reversal`、`short-term reversal stock returns consecutive down days probability`、`De Bondt Thaler overreaction hypothesis stock market`。
- 结果：命中 Jegadeesh (1990, Journal of Finance)、Lehmann (1990, QJE)、De Bondt & Thaler (1985, JF)、Nagel (2012, RFS, evaporating liquidity/short-term reversal returns)。确认：月内尺度反转效应显著，卖方流动性提供者获得反转溢价——连跌后买入有理论依据。详见综述 §1。

## [R-02] 2026-09-02 | 检索批次 2：行业动量与板块轮动
- 检索词：`Moskowitz Grinblatt 1999 industry explain momentum`、`sector rotation business cycle strategy evidence`、`investment clock asset returns`。
- 结果：命中 Moskowitz & Grinblatt (1999, JF)、Conover et al. sector rotation、Ilomäki et al.、以及 Chong & Phillips (2015, Journal of Investing) 行业轮动实证。确认：行业动量很大程度可由行业层面解释，板块层面的趋势与轮动具可交易性。详见综述 §2。

## [R-03] 2026-09-02 | 检索批次 3：农业商品周期
- 检索词：`Ezekiel 1938 cobweb theorem`、`hog cycle livestock cattle cycles Rosen Murphy Scheinkman`、`pig price cycle China agricultural economics`。
- 结果：命中 Ezekiel (1938, QJE)、Rosen, Murphy & Scheinkman (1994, JPE)、Harlow (1960) 综述、以及中国生猪周期外文实证（China Agricultural Economic Review / Agricultural Economics 等）。确认：生猪生产-价格存在约 3~4 年周期，是农业板块基本面的核心周期源。详见综述 §3。

## [R-04] 2026-09-02 | 检索批次 4：区制转换与周期计量
- 检索词：`Hamilton 1989 Markov regime switching business cycle`、`hidden Markov model stock market regime bull bear`、`spectral analysis stock market cycles`。
- 结果：命中 Hamilton (1989, Econometrica)、Harding & Pagan (2002) 断点/周期刻画、Guidolin & Timmermann (2007, JFE) HMM 资产配置。确认：二状态/三状态 HMM 是板块周期区制估计的标准工具。详见综述 §4。

## [R-05] 2026-09-02 | 检索批次 5：宏观与商品因子
- 检索词：`Chen Roll Ross economic forces stock returns`、`Fama French commodity futures risk premium`、`corn soybean wheat price agribusiness stock returns`、`El Nino Southern Oscillation agricultural commodity prices`。
- 结果：命中 Chen, Roll & Ross (1986, Journal of Business)、Gorton & Rouwenhorst (2006, **Financial Analysts Journal**，注意常见误引为 RFS)、Asness, Moskowitz & Pedersen (2013, JF)、Atems 等 ENSO×农业股研究。确认：CPI/PPI、利率、原油、玉米/大豆/猪肉价格、ENSO 天气指数可作为农业板块稳健外部因子。详见综述 §5。

## [R-06] 2026-09-02 | 检索批次 6：中国市场特异性
- 检索词：`Liu Stambaugh Yuan size value China`、`Chinese stock market reversal overnight return momentum China`、`A-share retail investor sentiment turnover anomaly`。
- 结果：命中 Liu, Stambaugh & Yuan (2019, JFE, CH-3/CH-4)、Nartea et al. 中国动量缺失、Jiang, Kelly & Zhang? 等关于中国反转更强的证据（确认 A 股短期反转强于美股、换手率/散户情绪因子有效）。详见综述 §6。

## [R-07] 2026-09-02 | 检索批次 7：技术规则与连跌序列统计
- 检索词：`Brock Lakonishok LeBaron simple technical trading rules`、`runs test daily stock prices serial dependence Markov chain up down`、`consecutive down days stock market streak probability`。
- 结果：命中 Brock, Lakonishok & LeBaron (1992, JF)；runs 检验谱系（Lisbon 市场随机游走检验、*JEDC* 2025 含未观测趋势的 runs test、"Indexing and Stock Market Serial Dependence Around the World"）；实践统计（标普连跌 8 天仍近似硬币频率，P(连跌2天)≈20%）。确认：连跌 n 天的概率可用历史频率表 + 一阶/二阶 Markov 链双口径估计，且文献口径下指数符号序列接近随机游走——该层的价值在条件收益分布与校准，不能神化预测力。详见综述 §7。

## [R-08] 2026-09-02 | 检索批次 8：数据窥探与回测过拟合
- 检索词：`White 2000 reality check data snooping`、`Sullivan Timmermann White 1999 data snooping technical trading`、`Bailey Lopez de Prado deflated Sharpe ratio`、`Lopez de Prado advances financial machine learning walk-forward purged cross validation`。
- 结果：命中 White (2000, Econometrica)、Sullivan, Timmermann & White (1999, JF)、Bailey & López de Prado (2014, JPM)、Harvey, Liu & Zhu (2016, RFS, t>3)、López de Prado (2018)。确认：全流程反过拟合方案（预先注册阈值、参数网格预算、purged walk-forward、多重检验校正、测试集只碰一次）。详见综述 §8。

## [R-09] 2026-09-02 | 检索批次 9：季节性
- 检索词：`Bouman Jacobsen 2002 Halloween indicator sell in May`、`turn of the month seasonality stock returns`、`Chinese New Year effect stock market`。
- 结果：命中 Bouman & Jacobsen (2002, AER)、Lakonishok & Smidt (1988)、Yuan & Gupta 中国春节效应外文研究。确认：可做季节哑因子（农历新年前后、春秋收储/补栏季节性）。详见综述 §9。

## [R-10] 2026-09-02 | 汇总
- 共整理 36 篇外文文献（顶刊 Econometrica×2、JPE×1、QJE×2、AER×1；JF/JFE/RFS 合计 13 篇），写入 `docs/literature_review.md`，每篇含作者、年份、期刊、核心结论、对本项目的映射（§10 映射总表）。
- 检索覆盖度自评：6 条线索全部有 ≥3 篇直接支撑；缺口：①A 股农业主题基金费率结构的学术文献少（用监管规则 CSRC 2017 流动性新规 7 天 1.5% 惩罚性赎回费替代，属规则事实而非文献）；②生猪周期中国的精确周期长度各研究在 36~48 个月间有分歧（策略上不硬编码，改为数据驱动估计）。

## [R-11] 2026-09-02 | 补充检索批次：游程统计、动量/波动管理、中国特异
- 检索词：`Moskowitz Ooi Pedersen time series momentum JFE 2012`、`Moreira Muir volatility managed portfolios JF 2017`、`China A-share short-term reversal momentum overnight return anomaly`、`China Agricultural Economic Review pig cycle`。
- 结果：新增核验 MOP (2012, JFE 时间序列动量)、Moreira & Muir (2017, JF) 及其反驳 Cederburg et al. (2020, JFE)、Gao et al. (2021, PBFJ)、Cheema et al. (2022, PBFJ)、Wang et al. (2020, CAER 生猪市场动态分析)。写入综述 §2/§3/§5/§6。

## [R-12] 2026-09-02 | 引文精确核验（Crossref API 批量）
- 方法：对不确定出处的引文逐一调用 Crossref API（query.bibliographic + 精确题名），核验题目/期刊/年份/作者/DOI。
- 核验与纠错结果：
  - Lehmann (1990) QJE ✓ (doi:10.2307/2937816)；De Bondt & Thaler (1985) JF ✓ (doi:10.2307/2327804)。
  - Schaller & van Norden (1997)：实际发表在 *Applied Financial Economics* 7(2)（我原记为 Journal of Empirical Finance，已纠正）。
  - Lakonishok & Smidt (1988)：准确题名 *Are Seasonal Anomalies Real? A Ninety-Year Perspective*，RFS 1(4)（纠正题名）。
  - Atems ENSO 论文：期刊为 *Water Resources and Economics*（2020-10，doi:10.1016/j.wre.2020.100157），作者 Atems, Maresca, Ma & McGraw（检索页摘要误标为 IRFA，已纠正）。
  - Cederburg, O'Doherty, Wang & Yan (2020) *On the performance of volatility-managed portfolios*, JFE ✓ (doi:10.1016/j.jfineco.2020.04.015)。
  - Gorton & Rouwenhorst (2006)：*Financial Analysts Journal* 62(2)（纠正为 RFS 的常见误引）。
- 综述最终定稿 36 条，标注 ✅/△ 核验状态。（注：后续追加调研后定稿 42 条，结构调整为 §10 连跌×基本面、§11 映射总表）

## [R-13] 2026-09-02 | 追加调研：连跌概率与基本面的关系（用户新需求）
- 背景：用户确认建模策略后追加需求——找到"连续跌 n 天的概率/后续走势与基本面的关系"，作为买入信号判断依据。
- 检索词：`Campbell Grossman Wang trading volume serial correlation reversal`、`Hameed Mian industries stock return reversals fundamental`、`Da Liu Schaumburg short-term return reversal`、`Baker Wurgler investor sentiment cross-section`、`Campbell Shiller valuation ratios long-run outlook`、`Hameed Kang Viswanathan stock market declines liquidity`、`Avramov Chordia Goyal liquidity autocorrelations`。
- 结果（7 篇全部核验）：CGW (1993, QJE) 高量下跌=流动性冲击→反转、缩量下跌=信息→惯性；Hameed & Mian (2015, JFQA) 行业基本面型下跌短期不反转、流动性型下跌反转；Hameed et al. (2010, JF) 大盘下跌期流动性枯竭、跌势自我强化；Avramov et al. (2006, JF) 反转强度随波动率/非流动性上升；Da et al. (2014, **Management Science**，纠正误记为 RFS) 反转成分分解；Baker & Wurgler (2006, JF) 低情绪→后续高收益；Campbell & Shiller (1998, JPM) 估值预测长期而非短期。
- 综合结论写入综述新 §10：短尺度反弹概率由"量能/波动/大盘/下跌来源（流动性 vs 基本面）"决定；半年尺度期望收益由"估值/情绪/猪周期相位"决定；农业特有整合假设（猪周期相位→利空是否已定价）作为原创检验项。
- 落地：L-B 层升级为 L-B2"基本面条件化连跌概率表"（7 个条件变量，见 strategy_proposal.md §4 L-B）。

## [R-14] 2026-09-02 | 本地数据源可用性探测（M1 前置）
- 前提：本机所有 python 环境（Conda base / Conda pytorch / Python312）均无 akshare → 为农业项目在 Python312 安装 akshare 1.18.83 + pandas 3.0.5 + numpy 2.5.1 + scipy 1.18.1 + statsmodels 0.15.0（清华镜像），依赖版本与根 requirements.txt 对齐，另建 `agriculture/requirements.txt`。
- 探测脚本：`data/raw/probe_akshare.py` + `probe_akshare2.py`，完整报告 `data/raw/data_probe_20260902.md`。
- 关键结果：
  - ✅ 主链路全通：申万农林牧渔 801010（6446 行，约 2000 年起日线）、中证农业 000122（3616 行，约 2011 起）、沪深300（5984 行）、玉米/豆粕期货主力（2004/2000 年起）、CPI/PPI/M1M2、两融。
  - ✅ 猪周期数据族：`index_hog_spot_price()` 2015-01 起周频 585 行（含 4/6/12 月均线）——L-A 猪价区制 + L-B2 猪相位条件的锚；生猪期货 LH0（2021 起，日频）；`futures_hog_core/cost/supply`（产能/成本/供给，但仅 2025-09 起，暂不入模）。
  - ❌ 三个缺口与替代：东财 `index_zh_a_hist` 被代理拦截（改用新浪源 `stock_zh_index_daily`，已验证）；乐咕估值接口不含农林牧渔、中证官网 csindex 估值仅近 20 个交易日（估值维度改用价格 5 年分位 + 相对强弱替代）；2015 年前猪价无免费源（猪价区制样本定为 2015 起，约 2.5 轮周期）。
- 结论：主链路 100% 可用、无需付费数据源，M1 数据管道可按 proposal §2.2 动工；决策点 6 落定为「index_hog_spot_price（周频历史）+ LH0（日频补充）」双源。

## [R-15] 2026-09-05 | 高星研究范式对照（GitHub）
- 用户要求参考 GitHub 高星的经济学/金融研究范式；用 GitHub API 核实星标：
  OpenBB 72.6k、ai-hedge-fund 63.2k、qlib 48.2k、ML4T 20.8k、alphalens 4.4k、QuantEcon.py 2.4k。
- 采纳：alphalens 式 Rank-IC/ICIR/分位单调性进入月度审计 §A2；qlib 的 point-in-time 与
  实验注册对应本项目 selfcheck + 冻结配置版本化；ai-hedge-fund 作为反面参照（LLM 观点不进模型）。
- 落档：`docs/paradigm_benchmark.md`。

## [R-16] 2026-09-05 | 新增候选因子筛查（ENSO/猪粮比）
- 数据：NOAA ONI（psl.noaa.gov oni.data，1950 起）接入并按"季节末月次月 15 日可得"防前视对齐；猪粮比代理=生猪指数/玉米期货。
- 三漏斗结果（训练段 2005-2021，报告 data/processed/factor_screen_update.md）：
  - `enso_nino`：t=+5.47 但前后半方向不一致 → FAIL；
  - `enso_nina`：预注册方向(+1)下 t=−4.67 且前后半一致 → **拉尼娜活跃期农业股未来 20 日显著更差**；
    按纪律不事后翻向，记为 V1.3 版本评审候选（方向 −1 重新预注册，下一轮校准的测试段届时检验）；
  - `hog_corn_ratio`：样本 1695<2500 → SKIP（生猪指数 2015 起），待训练窗延展重评。
- 纪律：本轮只出报告，冻结配置 V1.2 与测试段未动。
