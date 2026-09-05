# 报错日志（error_log）

> 规则：任何步骤出现报错、异常、数据缺失，必须在此追加记录：时间 | 步骤 | 现象 | 原因分析 | 处置 | 状态。
> 无报错时保持"暂无"。

---

## 报错记录

| # | 时间 | 步骤 | 现象 | 原因分析 | 处置 | 状态 |
|---|---|---|---|---|---|---|
| 1 | 2026-09-02 | 文献检索批次 1 | WebSearch 返回 `user concurrency limit exceeded` 与 2 次 60s 超时 | 检索工具并发受限 | 改为每次并发 2 条、单条重试 | ✅ 已解决 |
| 2 | 2026-09-02 | 核验 Atems ENSO 论文出处 | WebFetch ScienceDirect 返回 403；WebSearch 多次超时；Semantic Scholar API 返回 429 | ScienceDirect 反爬、学术 API 限流 | 改用 **Crossref API**（open、无限流）成功精确核验，并顺带批量核验其余 10+ 条引文出处 | ✅ 已解决 |
| 3 | 2026-09-02 | 本地运行数据探测 | 本机所有 python 环境（Conda base 3.13 / Conda pytorch / Python312）均无 akshare；且发现医药 tracker_log.txt 为空——本机当前环境跑不了医药项目 | 未在上述环境安装依赖（医药项目 CI 在 GitHub Actions 上运行不受影响；本机计划任务可能早已失效） | 为农业项目在 Python312 安装 akshare==1.18.83 及配套依赖（清华镜像）；**提醒：若需本机桌面通知，医药项目的 Windows 计划任务也需要重装依赖** | ✅ 已解决（农业侧） |
| 4 | 2026-09-02 | 数据探测：东财指数接口 | `index_zh_a_hist(000122)` ProxyError（代理拦截 push2.eastmoney.com） | 本机代理/东财接口不稳定 | 改用新浪源 `stock_zh_index_daily("sh000122")`，3616 行验证通过 | ✅ 已解决 |
| 5 | 2026-09-02 | 数据探测：板块估值 | 乐咕 `stock_index_pe_lg/pb_lg` 不含农林牧渔（KeyError）；中证 `stock_zh_index_value_csindex` 仅返回近 20 个交易日；旧版 `index_value_hist_funddb` 在 akshare 1.18.83 已移除 | 免费数据源覆盖范围限制 | 估值维度改用「价格 5 年分位」（医药 V1 同款）+「相对万得全A 60 日强弱」；最新 PE 由中证官网月度人工参考；因子三漏斗中估值因子以价格分位形式重新定义 | ✅ 已解决（设计替代） |
| 6 | 2026-09-02 | 首轮探测脚本 | `ak.index_value_hist_funddb` 属性不存在导致脚本第 7 项 AttributeError 中断 | akshare 1.18.83 已移除该接口 | 脚本改为动态发现（dir(ak) 正则匹配 + getattr 防御），重跑成功 | ✅ 已解决 |
| 7 | 2026-09-02 | M1 数据管道首跑 | `macro_china_cpi` 的"月份"列为中文格式 `2026年07月份`，`pd.to_datetime` 解析失败 | akshare 宏观接口返回中文月份 | `_to_date_index` 增加中文月份分支（正则提取年月 → 月末时间戳），重跑通过 | ✅ 已解决 |
| 8 | 2026-09-02 | M3 周期层首跑 | `cycle_z` 全程 ≈ +13 个标准差，相位判定永久失效 | `hpfilter` 返回 `(cycle, trend)`，解包写反把**趋势**当成了周期分量 | 修正解包顺序 `cyc, _ = hpfilter(...)`，重跑 z 分布正常（±3σ 内） | ✅ 已解决 |
| 9 | 2026-09-02 | M3 区制模型 | statsmodels 0.15 `MarkovRegression` 取 `p[1->1]` 抛 KeyError，静默降级 | 0.15 参数化只给每行 k−1 个自由转移参数：`p[0->0]`、`p[1->0]` | 改为 `p_stay1 = 1 − p[1->0]`；并在报告中保留 fallback_reason 以便发现静默降级 | ✅ 已解决 |
| 10 | 2026-09-02 | M4 因子筛选 | 晚起点因子（宏观/两融/生猪）在子训练段窗口内样本 <2500 被漏斗1静默淘汰 | 筛选窗口误用子训练段 2005-2015，而非协议的完整训练段 2005-2021 | 筛选窗口改为 TRAIN_FULL（2005-2021），与 strategy_proposal §3 一致；生猪动量因子（2015 起）如实未达 10 年门槛，V1.0 不入模（猪信息经 L-B2 相位条件进入） | ✅ 已解决 |
| 11 | 2026-09-02 | M5 DSR 计算 | 零交易配置的日收益全为 0，std=0 → SR=NaN → `nanargmax` 崩溃 | 网格中部分配置在子训练段从不触发买入 | 零方差列按 SR=0 计入试验池；同时暴露出"0 交易"根因即报错 #8/#9，随其修复 | ✅ 已解决 |
| 12 | 2026-09-02 | 自检 #1 宏观对齐 | `reindex(calendar).ffill()` 丢弃落在周末/节假日的源时间戳行（如 2024-09-15 周日的可得日），数据延迟近一个月才进入日频表 | reindex 只保留精确匹配的标签，非交易日源行被静默丢掉；虽不构成前视但造成延迟失真 | 新增 `_ffill_to_calendar`（union→ffill→reindex）统一对齐宏观/周频猪价/期货等全部外源序列，selfcheck 通过 | ✅ 已解决 |
| 13 | 2026-09-02 | 自检 #1 断言设计 | 三次误报：①同比数值跨月重合被当"提前出现"；②asof 落在非交易日取到前值；③自检拿错帧（对齐帧当原始帧） | 断言逻辑写得不严谨，数据本身无误 | 改为"可得日后首个交易日取新值、前一交易日取上期值"的阶梯不变量 | ✅ 已解决 |
| 14 | 2026-09-02 | codex-security 扫描（推送前门禁） | 连续三次环境故障：①工具子进程以 GBK 解码 git 输出，含中文的 commit 标题致 UnicodeDecodeError；②`codex-home` 凭证目录校验失败——排查发现 `codex-security` 状态目录被 4 个孤儿 SID 授予 Modify 权限（疑似同步工具遗留）；③脚本内 `set` 的占位 OPENAI_API_KEY 未传到 node 进程 | 中文 Windows 控制台编码 + 历史 ACL 污染 + 环境透传差异 | ①改扫无 .git 的干净代码副本（同时符合"干净副本"实践）；②`icacls /reset /T /C` 重置 ACL 为标准继承；③从 bash 侧 `export OPENAI_API_KEY=placeholder-not-used`。最终扫描成功：**findings=[]，coverage complete，全部面 no_issue_found，通过 --fail-on-severity high 门禁** | ✅ 已解决 |
| 15 | 2026-09-05 | GitHub Pages 部署步骤 | 连续两轮 failure：①heredoc 结束符带 YAML 缩进永不匹配，吞掉整个脚本；②pages_tmp 子仓库 git commit 报 empty ident name | bash heredoc 规则 + git init 不继承父仓库配置 | ①改 printf 多行构造；②git config 移到 git init 之后；③两轮误提交临时诊断文件（jobs_tmp.json 等）已清理并 ignore | ✅ 已解决 |
| 16 | 2026-09-05 | 微信推送 | Server酱返回失败（连续多轮测试后） | 免费额度 5 条/天，当日医药+农业多次测试耗尽 | 推送改为 fail-soft（失败不阻断流水线）；次日定时运行自动恢复；后与医药合并为每天 1 条（notify_combined.py），额度更充裕 | ✅ 已解决 |
| 17 | 2026-09-05 | 本地提交 | `git add -A` 两次误提交无关文件：`.workbuddy/memory/*.md`（用户工具状态）与诊断临时文件 jobs_tmp.json 等 | 全量 add 未配 ignore | 移出提交并补 .gitignore（.workbuddy/、*_tmp.json、logs_raw.txt、logs_tmp.zip）；教训：本仓库 add 用显式路径 | ✅ 已解决 |
| 18 | 2026-09-05 | 推送 | 多次 `git push` 被 fetch-first 拒绝：CI 每日 [auto] 提交与本地开发提交交替领先；农业 signals.db（二进制）双方都改时 rebase 冲突 | 共享仓库内 CI 机器人与本地开发并行 | 固定解法：`git pull --rebase` → 二进制冲突取本地超集版本（本地=回填+合并实盘行）→ 推送；后续先 fetch 再开工 | ✅ 已解决 |
