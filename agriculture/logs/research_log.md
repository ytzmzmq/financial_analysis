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
- 综述最终定稿 36 条，标注 ✅/△ 核验状态。
