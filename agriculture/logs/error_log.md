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
