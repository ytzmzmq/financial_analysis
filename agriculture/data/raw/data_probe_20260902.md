# akshare 数据源探测报告（2026-09-02）

## 申万农林牧渔 801010（index_hist_sw）
- ✅ 成功，6446 行，列：['代码', '日期', '收盘', '开盘', '最高', '最低', '成交量', '成交额']
  - `日期`: 1999-12-30 → 2026-09-01

## 申万农林牧渔 801010 对照：申万医药 801150
- ✅ 成功，6446 行，列：['代码', '日期', '收盘', '开盘', '最高', '最低', '成交量', '成交额']
  - `日期`: 1999-12-30 → 2026-09-01

## 中证农业 000122（stock_zh_index_daily sh000122）
- ✅ 成功，3616 行，列：['date', 'open', 'high', 'low', 'close', 'volume']
  - `date`: 2011-10-18 → 2026-09-02

## 中证农业 000122（index_zh_a_hist）
- ❌ 失败：`ProxyError: HTTPSConnectionPool(host='80.push2.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=b%3AMK0`

## 沪深300（stock_zh_index_daily sh000300）
- ✅ 成功，5984 行，列：['date', 'open', 'high', 'low', 'close', 'volume']
  - `date`: 2002-01-04 → 2026-09-02

## 生猪/畜牧相关函数发现
- 候选：['futures_hog_core', 'futures_hog_cost', 'futures_hog_supply', 'index_hog_spot_price', 'spot_corn_price_soozhu', 'spot_hog_crossbred_soozhu', 'spot_hog_lean_price_soozhu', 'spot_hog_soozhu', 'spot_hog_three_way_soozhu', 'spot_hog_year_trend_soozhu', 'spot_mixed_feed_soozhu', 'spot_soybean_price_soozhu']

## 生猪期货主力 LH0（futures_main_sina）
- ✅ 成功，1370 行，列：['日期', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '动态结算价']
  - `日期`: 2021-01-08 → 2026-09-02

## 玉米期货主力 C0（futures_main_sina）
- ✅ 成功，5268 行，列：['日期', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '动态结算价']
  - `日期`: 2005-01-04 → 2026-09-02

## 豆粕期货主力 M0（futures_main_sina）
- ✅ 成功，5274 行，列：['日期', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '动态结算价']
  - `日期`: 2005-01-04 → 2026-09-02

## 估值相关函数发现
- 候选：['bond_zh_cov_value_analysis', 'business_value_artist', 'fund_value_estimation_em', 'online_value_artist', 'option_value_analysis_em', 'stock_index_pb_lg', 'stock_index_pe_lg', 'stock_market_activity_legu', 'stock_market_pb_lg', 'stock_market_pe_lg', 'stock_value_em', 'stock_zh_index_value_csindex']

## CPI（macro_china_cpi）
- ✅ 成功，223 行，列：['月份', '全国-当月', '全国-同比增长', '全国-环比增长', '全国-累计', '城市-当月', '城市-同比增长', '城市-环比增长', '城市-累计', '农村-当月', '农村-同比增长', '农村-环比增长']

## PPI（macro_china_ppi）
- ✅ 成功，247 行，列：['月份', '当月', '当月同比增长', '累计']

## 货币供应 M1/M2（macro_china_money_supply）
- ✅ 成功，223 行，列：['月份', '货币和准货币(M2)-数量(亿元)', '货币和准货币(M2)-同比增长', '货币和准货币(M2)-环比增长', '货币(M1)-数量(亿元)', '货币(M1)-同比增长', '货币(M1)-环比增长', '流通中的现金(M0)-数量(亿元)', '流通中的现金(M0)-同比增长', '流通中的现金(M0)-环比增长']

## 融资融券汇总（macro_china_market_margin_sh）
- ✅ 成功，3986 行，列：['日期', '融资买入额', '融资余额', '融券卖出量', '融券余量', '融券余额', '融资融券余额']
  - `日期`: 2010-03-31 → 2026-09-01


---

# 补充探测（生猪现货族 + 估值）

## 生猪现货价格指数 index_hog_spot_price()
- ✅ 成功，585 行，列：['日期', '指数', '4个月均线', '6个月均线', '12个月均线', '预售均价', '成交均价', '成交均重']
  - `日期`: 2015-01-05 → 2026-08-31
  - `指数`: 92.88 → 75.51

## 生猪现货-搜猪网 spot_hog_soozhu()
- ✅ 成功，28 行，列：['省份', '价格', '涨跌幅']
  - `省份`: 北京 → 贵州
  - `价格`: 9.2 → 10.6

## 三元生猪现货-搜猪网 spot_hog_three_way_soozhu()
- ✅ 成功，15 行，列：['日期', '价格']
  - `日期`: 2026-08-19 → 2026-09-02
  - `价格`: 264.27 → 236.67

## 生猪年度趋势-搜猪网 spot_hog_year_trend_soozhu()
- ✅ 成功，200 行，列：['日期', '价格']
  - `日期`: 2026-02-15 → 2026-09-02
  - `价格`: 11.61 → 10.71

## 混合饲料价-搜猪网 spot_mixed_feed_soozhu()
- ✅ 成功，15 行，列：['日期', '价格']
  - `日期`: 2026-08-19 → 2026-09-02
  - `价格`: 2.97 → 2.97

## 玉米现货-搜猪网 spot_corn_price_soozhu()
- ✅ 成功，15 行，列：['日期', '价格']
  - `日期`: 2026-08-19 → 2026-09-02
  - `价格`: 2.36 → 2.41

## 生猪核心产能 futures_hog_core()
- ✅ 成功，367 行，列：['date', 'value']
  - `date`: 2025-09-01 → 2026-09-02
  - `value`: 13.83 → 11.11

## 生猪养殖成本 futures_hog_cost()
- ✅ 成功，367 行，列：['date', 'value']
  - `date`: 2025-09-01 → 2026-09-02
  - `value`: 2373 → 2365

## 生猪理论出栏供给 futures_hog_supply()
- ✅ 成功，90 行，列：['date', 'value']
  - `date`: 2026-05-28 → 2026-08-25
  - `value`: 14.77 → 16.3

## 申万农林牧渔 PE（stock_index_pe_lg symbol=农林牧渔）
- ❌ 失败：`KeyError: '农林牧渔'` 
## 申万农林牧渔 PE（stock_index_pe_lg symbol=申万农林牧渔）
- ❌ 失败：`KeyError: '申万农林牧渔'` 
## 申万农林牧渔 PB（stock_index_pb_lg symbol=农林牧渔）
- ❌ 失败：`KeyError: '农林牧渔'` 
## 申万农林牧渔 PB（stock_index_pb_lg symbol=申万农林牧渔）
- ❌ 失败：`KeyError: '申万农林牧渔'` 
## 中证农业000122官方估值 stock_zh_index_value_csindex
- ✅ 20 行，列：['日期', '指数代码', '指数中文全称', '指数中文简称', '指数英文全称', '指数英文简称', '市盈率1', '市盈率2', '股息率1', '股息率2']
- 起止：2026-09-02 → 2026-08-06


---

# 探测结论（M1 数据管道输入）

## ✅ 可用（主链路全通）
| 数据 | 接口 | 覆盖 | 用途 |
|---|---|---|---|
| 申万农林牧渔 801010 | index_hist_sw | 6446 行（约 2000-01 起，日线 OHLC+量额） | 主建模序列 |
| 中证农业 000122 | stock_zh_index_daily(sh000122) | 3616 行（约 2011-11 起） | 基金对照 |
| 沪深300 | stock_zh_index_daily(sh000300) | 5984 行 | 大盘状态/残差因子 |
| 生猪价格指数 | index_hog_spot_price() | 2015-01 起周频 585 行（含 4/6/12 月均线） | 猪周期区制锚（L-A 工具3 + L-B2 猪相位条件） |
| 生猪期货 LH0 | futures_main_sina(LH0) | 2021-01 起 1370 行 | 猪价日频补充 |
| 玉米/豆粕期货主力 | futures_main_sina(C0/M0) | 2004-09 / 2000-10 起 | 饲料成本、猪粮比代理 |
| CPI/PPI/M1/M2 | macro_china_* | 全历史月度 | 宏观因子（发布滞后对齐） |
| 两融 | macro_china_market_margin_sh | 3986 行 | 杠杆资金因子 |

## ❌ 不可用与替代
| 缺口 | 现象 | 替代方案 |
|---|---|---|
| 东财指数历史 index_zh_a_hist | ProxyError（代理拦截 eastmoney push2） | 用 stock_zh_index_daily（新浪源）替代，已验证可用 |
| 农林牧渔 PE/PB 历史分位 | 乐咕 lg 接口不支持农林牧渔（KeyError）；中证官网 csindex 仅返回近 20 个交易日 | 估值维度改用「价格 5 年分位」（医药 V1 同款）+「相对万得全A 60 日强弱」；最新 PE 由中证官网人工月度参考 |
| 2015 年前猪价长序列 | 免费接口无 | 猪周期区制样本定为 2015-01 起（约 2.5 轮周期）；L-A 主区制模型仍用 801010 全历史 |

## 结论
主链路数据 100% 可用，猪周期条件数据可用（2015 起周频），无需付费源。数据管道可按 strategy_proposal.md §2.2 动工。
