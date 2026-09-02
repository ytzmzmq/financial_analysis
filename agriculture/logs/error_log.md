# 报错日志（error_log）

> 规则：任何步骤出现报错、异常、数据缺失，必须在此追加记录：时间 | 步骤 | 现象 | 原因分析 | 处置 | 状态。
> 无报错时保持"暂无"。

---

## 报错记录

| # | 时间 | 步骤 | 现象 | 原因分析 | 处置 | 状态 |
|---|---|---|---|---|---|---|
| 1 | 2026-09-02 | 文献检索批次 1 | WebSearch 返回 `user concurrency limit exceeded` 与 2 次 60s 超时 | 检索工具并发受限 | 改为每次并发 2 条、单条重试 | ✅ 已解决 |
| 2 | 2026-09-02 | 核验 Atems ENSO 论文出处 | WebFetch ScienceDirect 返回 403；WebSearch 多次超时；Semantic Scholar API 返回 429 | ScienceDirect 反爬、学术 API 限流 | 改用 **Crossref API**（open、无限流）成功精确核验，并顺带批量核验其余 10+ 条引文出处 | ✅ 已解决 |
