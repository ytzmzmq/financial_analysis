# GitHub 高星研究范式对照（2026-09-02）

> 用户要求：参考 GitHub 高星的经济学/金融研究范式。本文核对各仓库实际星标
>（GitHub API，2026-09-02），给出与本项目的映射与已采纳的改进。
> 属方法论参照，不构成文献引用（非同行评审来源）。

## 一、仓库核对

| 仓库 | Stars | 定位 | 对本项目的相关性 |
|---|---|---|---|
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | 72.6k | 开源金融数据/分析平台 | 数据平台形态参照（我们用 AKShare 同理，重数据可得性与降级链） |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | 63.2k | 多智能体"分析师团队"演示 | **反面参照**：LLM 观点组合无回测纪律，不采用其信号生成方式 |
| [microsoft/qlib](https://github.com/microsoft/qlib) | 48.2k | AI 量化投研平台 | **核心参照**：point-in-time 数据纪律、walk-forward 工作流、实验记录器（R 框架）、模型注册 |
| [stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading) | 20.8k | ML4T 教材代码（第 3 版） | **核心参照**：purged/embargoed CV、组合回测偏差清单（与 López de Prado 协议同源） |
| [quantopian/alphalens](https://github.com/quantopian/alphalens) | 4.4k | 因子表现分析标准件 | **核心参照**：Rank-IC / ICIR / 分位单调性 / 换手率分析（见 §2 已采纳） |
| [QuantEcon/QuantEcon.py](https://github.com/QuantEcon/QuantEcon.py)（及 QuantEcon 讲义） | 2.4k | 计量经济学开源研究范式 | **核心参照**：可复现研究（固定版本依赖 + 脚本化 + 日志留痕）与随机动态规划范式 |

## 二、已采纳的改进（落地到代码）

1. **alphalens 式因子诊断 → `app/monthly_audit_agri.py` §A2**（本次新增）
   - Rank-IC（因子与 20 日前瞻收益的秩相关）、ICIR（IC 均值/波动）、
     Q1/Q2/Q3 前瞻收益单调性检验——分位单调性破坏即"因子衰减"预警，
     纳入月度审计的版本治理证据链。
2. **qlib 式实验注册 → 校准流水线**
   - 本项目的 `model_config_agri.json`（冻结参数+协议+反过拟合检验结果+版本披露）
     + `calibration_report.md`（每次校准的完整留痕）即 qlib "recorder" 的轻量等价物；
     版本号 V1.0→V1.1→V1.2 与 test_peek_count 计数对应 qlib 的模型注册思想。
3. **qlib/ML4T 的 point-in-time 纪律 → `akshare_source.py` + `selfcheck.py`**
   - 宏观按可得日（次月 15 日）阶梯对齐、周频猪价按报告日 asof、
     `selfcheck.py` 以断言固化（宏观阶梯不变量 / T+1 成交 / 7 天约束）。
4. **QuantEcon 式可复现研究 → 全项目**
   - 依赖精确锁定（requirements.txt）、校准脚本一次运行产出全部产物、
     PROGRESS/research/error 三日志留痕——对应其"讲义可一键复算"的范式。

## 三、对照后的差距与路线（不立即实施，记入月度审计路线图）

- **多资产横截面**：alphalens/qlib 的 IC 是横截面概念，本项目为单指数时间序列版
  （Rank-IC 的时间序列近似）；若未来扩展到农业板块内多 ETF/个股，可直接套用
  alphalens 全套横截面诊断。
- **组合优化层**：qlib 有完整 topk-dropout 组合构建；本项目面向单一基金申赎，
  仓位只有 0/1，暂不需要。
- **AI 观点整合**：ai-hedge-fund 式 LLM 分析师可以作为"非交易信号"的信息源
  （如新闻/政策解读），但必须走与量化因子相同的 t≥3 三漏斗检验才允许进模型。
