---
name: a-stock-analysis
category: productivity
description: A股全市场行情爬取 + 板块/个股分析 + 报告生成，支持板块趋势、个股对比、新闻舆情（akshare 东财新闻为主源，SearXNG 为备源）、完整 Markdown 报告输出到桌面。内置8大分析模式：全市场全景、机会发现（--opportunity）、荐股评分（--recommend，合并机会+评分）、科创板、龙虎榜、资金流、涨停板、热门股。
---

# A股分析系统

## 触发条件
- 用户说"分析A股"、"全市场全景"、"板块分析"、"分析某只股票"
- 用户说"生成A股报告"、"帮我看看XX股票"、"蓝色光标能买吗"
- 用户说个股代码或名称如"300058"、"宁德时代"、"紫金矿业"
- 用户说"机会发现"、"技术选股"、"涨停股"、"龙虎榜"、"资金流"、"科创板"、"荐股"、"推荐买什么"
- ⚠️ CLI 用 --stock 只传代码（如 `--stock 601899`），不要传名称
- ⚠️ 多股对比时 `--kline` 参数仍然生效——有则拉K线+深度技术分析，无则只对比实时数据

## 环境要求
- Python 3.12+
- 依赖：`akshare` `pandas` `requests`（**不需要 baostock**）
- 缓存目录：`/tmp/a_stock_cache/`
- 桌面路径：需要根据目标机器的用户名修改 `main.py` 中的 `DESKTOP` 常量
- **⚠️ 致命名称映射 Bug**：在某些环境下，`akshare` 或新浪接口返回的股票代码与名称可能发生严重错位。在使用自动化报告时，必须通过核对名称与代码的一致性来验证数据的真实性。特别注意：天赐材料 (002709)、新宙邦 (300037) 等高频分析股必须在 `scraper.py` 的 `CORRECTION_MAP` 中显式校准。若发现代码对应的名称不符（如 300037 映射为其他公司），应立即修正映射表。

```
scraper.fetch_data() 返回三元组 (df, board_df, board_map)，不要直接当 DataFrame 用 .columns 查询
```
⚠️ `df['涨跌幅(%)']` 列名带百分号，`board_df['涨跌幅(%)']` 也是，注意区分使用场景。筛选时用 `涨跌幅(%)` 字段，板块数据中也有该字段但含义不同。

## 代码文件结构

```
~/.hermes/skills/a-stock-analysis/
├── SKILL.md          ← 本文件
└── scripts/
    ├── main.py       ← CLI 入口（7大分析模式）
    ├── scraper.py    ← fetch_data() / get_kline() / get_kline_ths()
    ├── sector_map.py ← filter_by_board()
    ├── analyzer.py   ← analyze_market / analyze_sector / analyze_stock / analyze_stock_comparison
    ├── report.py     ← gen_report()（11种报告模板，含 --recommend）
    ├── opportunity.py ← find_opportunities() + rank_opportunities() + get_recommend_report()
    │                  （技术选股+涨跌停 + 荐股评分，原 star_stocks.py 已合并）
    ├── board_analysis.py ← 板块内选股推荐
    ├── kcb.py         ← 科创板分析
    ├── lhb.py         ← 龙虎榜分析
    ├── fund_flow.py   ← 资金流分析
    ├── capital_flow.py← 高性能资金流
    ├── strategy.py    ← 轻量回测引擎
    ├── star_stocks.py ← ⚠️ 已废弃，功能已合并至 opportunity.py；保留仅作兼容垫片
    └── news_search.py ← SearXNG 新闻搜索（可选）
```

> **v3 合并说明**：`star_stocks.py` 的多维度评分功能已移入 `opportunity.py`（`rank_opportunities()` / `get_recommend_report()`）。
> 新入口统一用 `--recommend`，`--stars` 保留但显示废弃提示。

```bash
cd ~/.hermes/skills/a-stock-analysis/scripts

# ── 全市场/板块/个股（原有模式）──────────────────────────────
# 全市场全景（49板块逐一分析，每板块Top3，约10秒）
python3 main.py --no-news

# 板块分析
python3 main.py --sector 有色金属 --no-news

# 个股分析（含320日K线+技术指标，只用代码）
python3 main.py --stock 601899 --kline --no-news

# 个股分析 + 新闻舆情（SearXNG 必须已部署）
python3 main.py --stock 601899 --kline

# 多股对比（多个代码用逗号分隔；加 --kline 获取K线+深度技术分析，生成完整对比报告）
python3 main.py --stock 601899,600519 --kline --no-news

# 列出所有49个板块
python3 main.py --boards

# 强制刷新缓存（网络恢复时）
python3 main.py --refresh

# ── 新增分析模式 ─────────────────────────────────────────────
# 机会发现（技术选股+涨跌停+新股，5个数据源汇总）
python3 main.py --opportunity

# 当日热门股票（涨停+强势+量价各来源汇总）
python3 main.py --hot

# 涨停板专项分析（连板分析+涨停明细）
python3 main.py --limit-up

# 科创板全景（PE分布+强弱榜+成交额+换手率）
python3 main.py --kcb

# 龙虎榜分析（近10日明细+机构溢价+游资高频）
python3 main.py --lhb

# 资金流分析（行业+概念+北向持股）
python3 main.py --fund-flow

# ── 综合评分选股 ───────────────────────────────────────────
# 整合5维度综合评分（动量+资金+技术面+龙虎榜+市值），输出三档候选
python3 main.py --stars

# ── 荐股评分（合并星标功能，一次调用同时输出机会清单和最优排序）───
# 等同于 --opportunity（机会清单）+ --stars（排序决策），合并为一个命令
python3 main.py --recommend
```

## 新增模块详解

### 1. opportunity.py — 个股机会发现

整合6大数据源，发现各类技术面机会，并提供多维度加权评分排序：

| 函数 | 数据源 | 说明 |
|------|--------|------|
| `find_opportunities()` | 汇总所有 | 返回各分类 DataFrame dict（THS 池已禁用，只用东财6池） |
| `get_em_limit_up()` | 东财 | 涨停板（当日） |
| `get_em_limit_down()` | 东财 | 跌停板（当日） |
| `get_em_yesterday_zt()` | 东财 | 昨日涨停（含炸板回封） |
| `get_em_strong_pool()` | 东财 | 强势股池 |
| `get_em_second_new()` | 东财 | 次新股 |
| `get_em_炸板()` | 东财 | 炸板股 |
| `summarize_opportunities()` | — | 各池汇总统计文本 |
| `rank_opportunities(top_n)` | — | 多维度加权评分（动量+市值+资金+技术），返回 Top N DataFrame |
| `get_recommend_report(top_n)` | — | 完整荐股报告 dict（含三档分类 + 综合评分 + 详细数据） |
| ⚠️ THS 池（已禁用） | 同花顺 | `get_ths_*` 系列每池500-2000只，合并后5000+ 候选导致评分超时，注释保留仅作参考 |

### 2. kcb.py — 科创板分析

| 函数 | 说明 |
|------|------|
| `get_kcb_spot()` | 实时行情（akshare.sina） |
| `get_kcb_kline(code, days)` | 历史K线（同花顺） |
| `analyze_kcb()` | 全景分析（涨跌幅分布/PE分布/强弱榜） |
| `analyze_kcb_stock(code)` | 单只科创板股票深度分析 |

### 3. lhb.py — 龙虎榜分析

| 函数 | 数据源 | 说明 |
|------|--------|------|
| `get_lhb_detail(days)` | akshare.stock_lhb_em | 近N日龙虎榜明细 |
| `get_lhb_statistics()` | akshare.stock_lhb_em | 个股统计（上榜次数/净额） |
| `analyze_lhb(days)` | — | 综合分析（机构溢价+游资高频） |
| `get_lhb_stock_detail(code)` | — | 单只股票龙虎榜历史 |

### 4. fund_flow.py — 资金流分析

| 函数 | 数据源 | 说明 |
|------|--------|------|
| `get_industry_flow()` | akshare.stock_fund_flow_industry | 90个行业资金流 |
| `get_concept_flow()` | akshare.stock_fund_flow_concept | 387个概念资金流 |
| `get_stock_flow(code, period)` | akshare.stock_individual_fund_flow | 个股资金流 |
| `get_hsgt_hold()` | akshare.stock_hsgt_hold_stock_em | 北向持股排行（今日持股-股数） |
| `analyze_fund_flow()` | — | 综合分析（情绪判断+Top10汇总） |
| 北向资金历史净买入 | akshare.stock_hsgt_hist_em | `stock_hsgt_north_net_flow_in_em` **不存在**，用 `stock_hsgt_hist_em`；东财实时数据可直抓 JSONP `push2.eastmoney.com/api/qt/kamtop/get?fields=f62,f184`（f62=沪股通净买额，f184=深股通净买额） |

## 新闻舆情模块（akshare 东财新闻为主源，SearXNG 为备源）

**主数据源**：akshare `stock_news_em()` — 东财实时财经快讯，返回 `关键词/新闻标题/新闻内容/发布时间/文章来源`，无需额外配置，即装即用。默认加载50条，按关键词智能过滤+排序。

**备数据源**：SearXNG（需 Docker）。

**SearXNG 安装**（Windows 端执行以重启容器让配置生效）：
```powershell
cd $env:USERPROFILE\searxng
docker compose restart
```

**SearXNG 配置**：`~/searxng/settings.yml` 必须包含 `defaultengines` 才能响应 JSON 搜索（否则返回403）。最小可用配置：
```yaml
use_default_settings: true
server:
  secret_key: "..."  # 保持原值
  port: 8080
search:
  formats:
    - html
    - json
  defaultengines:
    - google
    - bing
    - baidu
```

**搜索策略**：
- `search_stock_news(name, sym, n=10)` → 多角度查询（业绩/研报 + 储能动态 + 公告），去重+过滤广告+智能排序
- `search_sector_news(board, n=8)` → 板块行业新闻
- `search_market_news(n=8)` → A股市场整体新闻
- `check_searxng()` → 健康检查

**已知垃圾词过滤**：
- 绝对过滤：快手、爱奇艺、抖音、小红书、拼多多、腾讯视频、网银、手机银行等
- 降权（排在后面）：走势图、K线图、搜狐证券

## 关键数据源格式（实测经验）\n\n### 代理与连接稳定性 (WSL专用)\n- **环境变量强制覆盖**：在 WSL 环境中，调用 `main.py` 时建议在 shell 层显式执行 `export http_proxy=http://127.0.0.1:7897; export https_proxy=http://127.0.0.1:7897; python3 ...`。这能有效解决 `akshare` 内部部分请求在 `requests` 层面忽略内部设置导致 `RemoteDisconnected` 的问题。\n\n### 历史日K线（ifzq 优先 + 同花顺兜底，含换手率）
```python
import random, requests
rnd = ''.join(str(random.randint(0, 9)) for _ in range(16))
url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,320,qfq&_={rnd}"
# sym 格式: sz300058 或 sh600000
# 返回: {"data":{"sz300058":{"qfqday":[["日期","收盘(qfq)","开盘","高","低","成交量"],...]}}}
# 字段顺序: [0=日期, 1=收盘(qfq前复权), 2=开盘, 3=高, 4=低, 5=成交量]
# 注意：新浪 K线接口对 sz 股票返回空，不要用！
```

**同花顺日K接口（get_kline_ths）**：
- URL: `http://d.10jqka.com.cn/v6/line/hs_{code}/01/last.js`
- 字段: `[日期, 收盘, 开盘, 高, 低, 成交量, 成交额, 换手率(%), ...]`
- 优势: 历史最深（贵州茅台5900+条）、**自带换手率**、sz/sh自动兼容（统一 `hs_` 前缀）
- get_kline() 已内置自动兜底：ifzq 失败或数据不足5条时自动切换同花顺

### 全量A股实时行情（腾讯批量接口）
- 来源：腾讯 `https://qt.gtimg.cn/q=`（GBK编码，分批80只，并发8线程）
- 缓存：`/tmp/a_stock_cache/realtime.pkl`
- 代码格式：`sz000001`（含前缀），匹配时用 `.str[2:]` 去前缀
- WSL 环境直连腾讯 HTTPS，无需代理（`session.trust_env = False`）
- **行格式匹配**：沪市行以 `="1~` 开头，深市/创业板以 `="51~` 开头——必须同时匹配两种标记

**腾讯实时行情关键字段索引（已验证，禁止混淆）：**

| 索引 | 字段名 | 说明 |
|------|--------|------|
| [35] | 成交额/量 | 格式 `"价格/成交量(手)/成交额(元)"`，**不是** 简单字符串 |
| [37] | 成交额(万元) | **不是换手率**，是成交额万元单位（已废弃直接使用） |
| [44] | 总市值(亿) | 直接使用 |
| [45] | 流通市值(亿) | 直接使用 |
| [57] | 换手率(permille) | 千分数（如 106.56 = 10.656%），**不是百分比** |

**换手率计算公式（2025-04-28 验证正确）：**
```python
amt_raw = parts[35]                        # "16.03/552466/875047695"
amt = float(amt_raw.split("/")[2])          # index[2]=成交额(元)
nmc = float(parts[45])                      # 流通市值(亿)
turnover = round(amt / (nmc * 1e8) * 100, 3)  # 换手率(%)
```

**验证数据（已知正确值）：**
- 603399 永杉锂业：成交额 875,047,695元，流通市值 82.12亿 → 换手率 10.656% ✅
- 002902 铭普光磁：换手率 13.451% ✅
- 001298 好上好：换手率 7.466% ✅

> ⚠️ 绝对禁止直接取 `parts[35]` 作为成交额（那是 `"价格/成交量(手)/成交额(元)"` 拼接字符串），或直接用 `parts[37]`（那是成交额万元，不是换手率%）。

### 行业板块
- 板块列表：`http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php`（**Pipe分隔，不是JSON！**）
- 板块成分：`http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?node={node}&num=1000`（UTF-8 JSON）
- 新浪节点代码：**必须动态获取**，不要硬编码

## 已知坑（已踩过）

| 坑 | 解法 |
|----|------|
| 新浪行业板块返回 Pipe 分隔字符串 | 用 `re.finditer` 解析，不用 json.loads |
| 腾讯市值只有约45%股票有数据 | 用 `pd.to_numeric(..., errors="coerce")` 处理 NaN |
| WSL 直连新浪/腾讯 HTTPS 不稳定 | `scraper.py` 中 `_PROXY = "http://127.0.0.1:7897"`，且在 `import akshare` **之前** `os.environ.setdefault("http_proxy")`，否则 akshare 内部 requests 不走代理 |
| akshare `stock_info_a_code_name()` 直连北交所接口失败（`RemoteDisconnected`） | 同上，代理配置生效后可解决 |
| **同花顺 HTTP 接口(d.10jqka.com.cn)走代理7897失败** | 用 `requests.Session()` 直连，**不要**在 `requests.get()` 显式传 `proxies={}`，否则 `no_proxy` 环境变量完全失效 |
| ifzq K线字段顺序 [日期, 收盘(qfq), 开盘, 高, 低, 成交量]，索引1=前复权收盘 | 用实际数据交叉验证，报告表头和分析引擎取数要对应 |
| 技术指标原为启发式假数据 | 实现真实算法：RSI(14)标准公式，MACD(12,26,9)=EMA差值+DEA+红绿柱，布林带(20,2σ) |
| main.py 多个分支用 `return` 提前退出，清理逻辑不执行 | 每个 return 前显式调 `_clean_reports()`，或 `try/finally` 统一包裹 |
| 板块分析时 top3 永远为空 | 用模块级缓存 `_board_syms_cache` 避免重复请求 |
| 新浪节点代码错误 | 动态获取，不硬编码 |
| 模块内 requests 未 import | analyzer.py 顶层 `import requests` |
| 总市值列 dtype=object 导致 nlargest 报错 | 先 `pd.to_numeric(df["总市值(亿)"], errors="coerce")` 再 nlargest |
| news_search.py 不存在导致 NEWS_ENABLED=False | 创建模块后 import 即可，service check 后自动启用 |
| 搜索结果含广告/行情页 | news_search.py 中 BAD_TITLES 垃圾词过滤 + LOW_PRIORITY 降权 + 智能评分排序 |
| akshare 龙虎榜/资金流/北向等模块路径旧说法"stock_feature" | akshare 最新版本均已改为**顶级函数**，直接 `ak.stock_lhb_detail_em()` / `ak.stock_fund_flow_industry()` / `ak.stock_hsgt_hold_stock_em()` 即可，**不需要** `from akshare.stock_feature import ...` |
| akshare `stock_fund_flow_industry/concept()` 列名 | 返回列名为"净额"不是"净流入"，rename 时用 `c in ("净额", "净流入")` |
| report.py `lines.append("...")` 中 `\n` 被展开为真实换行符导致 `SyntaxError: unterminated string literal` | 文件中不要直接用 Enter 换行拼接字符串内容，改用 `\n` 转义；排查：`python3 -c "import ast; ast.parse(open('report.py').read())"` 快速定位错误行 |
| akshare `stock_hsgt_hold_stock_em()` 列名 | 返回"今日持股-股数"不是"持股数量"，rename 时检测 `"持股-股数" in c` |
| akshare `stock_lhb_detail_em()` 实际字段 | 21列：`['序号','代码','名称','上榜日','解读','收盘价','涨跌幅','龙虎榜净买额','龙虎榜买入额','龙虎榜卖出额','龙虎榜成交额','市场总成交额','净买额占总成交比','成交额占总成交比','换手率','流通市值','上榜原因','上榜后1日','上榜后2日','上榜后5日','上榜后10日']` |
| akshare `stock_lhb_stock_statistic_em()` 字段 | 有"买方机构次数"、"卖方机构次数"、"机构买入净额"，不是笼统的"龙虎榜净额" |
| akshare `stock_individual_fund_flow()` 签名 | 位置参数 `(stock, market)`，market='sh'/'sz'，**不是** `symbol=xxx, period='5日'` |
| akshare `stock_ipo_benefit_ths()` 返回空 | 函数存在但 `r.text` 为 None，会抛出 `AttributeError: 'NoneType' object has no attribute 'text'` |
| akshare `stock_rank_xstp_ths`(向上突破) 3572行 / `stock_rank_xxtp_ths`(创新低) 3719行 | 数据量大，akshare内部有约72/75页分页请求，耗时约18秒，属正常现象 |
| akshare ths系列接口底层URL | 均访问 `http://data.10jqka.com.cn/*`，需要代理7897才能连通 |
|| akshare `stock_board_industry_name_ths()` 只返回板块名和代码 | 返回 `['name', 'code']` 两条字段，不含行情数据，需配合行情接口使用 |
| akshare `stock_zh_kcb_spot()` 替换旧接口 | akshare 1.13+ 不再有 `stock_zh_kcb_sina()`；实时行情改用 `akshare.stock_zh_kcb_spot()`，K线改用 `akshare.stock_zh_kcb_daily()`；列名不含括号后缀：`涨跌幅` 而非 `涨跌幅(%)`，`换手率` 而非 `换手率(%)`，`市盈率` 而非 `市盈率TTM`，`成交额` 单位为元（需自行除 1e8 转为亿）|
| akshare `stock_lhb_em` 不存在 | 正确顶级函数：`akshare.stock_lhb_detail_em(symbol="近一年")`（龙虎榜明细）和 `akshare.stock_lhb_stock_statistic_em()`（营业部统计）；**不是** `ak.stock_lhb_em` |
| akshare rename 多源列→同一目标列产生重复 | 多个源列映射到同一目标列名（如 `'行业-涨跌幅'` 和 `'领涨股-涨跌幅'` 都映射 `'涨跌幅(%)'`），`df[col]` 返回 DataFrame 炸掉后续 `.str./.astype()`；**两步去重**：rename **前**做 `df.loc[:, ~df.columns.duplicated()]`（去除源列完全重复）+ rename **后**再做一次（处理 rename 碰撞产生的目标列重复）；`pd.factorize(df.columns)` 误用为 `.iloc[:, Index]` 会报 `IndexError`，正确用法只取返回值第一个元素（整数数组）作为 iloc 位置索引 |
| akshare `stock_zt_pool_em()` 等涨停接口 | 不传 `date` 参数默认返回空；**修复**：传入 `YYYYMMDD` 格式日期（`_today_str()`）；`_clean_zt()` 东财列名映射（`涨跌幅`→`涨跌幅(%)`、`换手率(%)`、`流通市值(亿)`、`总市值(亿)`、`所属行业` 等），keep 筛选也补上 `所属行业` |
| 东财 `push2.eastmoney.com` HTTPS API 间歇性断连 | 偶发性 `RemoteDisconnected`/`ProxyError`，即使通过代理7897也不稳定；**降级方案**：涨跌停明细改用 akshare `stock_zt_pool_em(date)`（需要 date 参数）；指数行情用腾讯 `qt.gtimg.cn`（最稳定）；北向资金用东财 JSONP 接口 `api/qt/kamtop/get`；板块行情用新浪 `vip.stock.finance.sina.com.cn` |
| akshare ths 板块接口（`stock_board_industry_name_ths`/`stock_board_concept_name_ths`）偶发返回空 | 底层 `data.10jqka.com.cn` 响应慢或空；**降级方案**：同花顺板块为空时自动切换新浪板块接口 `https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class`（概念）和 `?param=industry`（行业），返回 JSON 对象（`{code: "name,count,chg,..."}` 格式），需用 `json.loads` 解析 |
| akshare `stock_zt_pool_em()` 无 `symbol` 参数 | 函数签名中无 `symbol` 关键字参数，不要传；涨停数据只需 `date` 参数；跌停数据用 `akshare.stock_dt_pool_em(date=date_str)` |
| akshare 指数实时行情 `stock_zh_index_spot_em` 参数错误 | 传 `symbol` 需用映射表（如 `symbol="1.000001"` 映射到 `"sh000001"`），**直接传股票代码会 KeyError**；**推荐用腾讯接口**：`https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688,sh000300`（GBK，字段[3]=最新价，字段[31]=涨跌额，字段[32]=涨跌幅），WSL 直连代理可用 |
| akshare `stock_zh_index_spot_sina` 接口签名 | 不接受 `symbol` 参数，需调用无参版本获取全量指数列表，再自行过滤；**推荐直接用腾讯 qt 接口** |
| 腾讯市值接口(`qt.gtimg.cn`)行格式 | 沪市行以 `="1~` 开头，深市/创业板以 `="51~` 开头；`fetch_batch_tx()` 中必须同时匹配 `="1~` 和 `="51~`，否则深市股票市值100%缺失，覆盖率仅 ~44% |
| **深交所/北交所股票列表 WSL 直连超时** | SSE/SZSE/BSE official XLSX/JSON 接口从 WSL 直连均超时（无代理）；**正确方案**：用腾讯批量接口 `qt.gtimg.cn` 枚举生成全量列表。`scraper.py` 的 `get_stock_list()` 已实现：并行 20 线程，每批 60 代码，约 4.4s 抓完 4964 只 A 股；该函数内置 6 小时内存缓存（`_stock_list_cache`），重复调用不重抓 |
| **akshare `stock_zt_pool_strong_em` 日期格式** | 函数期望 `YYYYMMDD` 格式（如 `20260428`），**不是** `YYYY-MM-DD`；`opportunity.py` 的 `_today_str()` 已返回正确格式，调用时直接传 `_today_str()` 即可 |
| **腾讯 `parts[35]` 分割格式导致换手率计算错误** | `parts[35]` 是 `"价格/成交量(手)/成交额(元)"` 拼接字符串，取 `[0]` 会拿到价格（导致换手率为0）；`parts[37]` 是成交额(万元)也不是换手率%；`parts[57]` 是换手率permille。正确做法：用 `parts[35].split("/")[2]` 取成交额(元) 除以 `parts[45]` 流通市值(亿) × 1e8 × 100 |
| **THS 技术选股候选爆炸导致 `rank_opportunities` 超时** | 同花顺 11 个技术选股池（量价齐升/持续放量/连续上涨/创新高等）每池返回 500-2000 只，合并后 5000+ 候选 → 评分循环 5373 只 → 超 300s。**正确方案**：`find_opportunities()` 中 THS 池已禁用（注释状态），只用东财 6 个涨跌停池（约 100-200 只候选），评分 < 5s；`rank_opportunities()` 的 `get_recommend_report` 超时从 120s 改为 300s |
| **main.py 缺少 `import pandas as pd`** | `gen_report("recommend")` 分支最后 `stars_df = pd.DataFrame(...)` 触发 `NameError`；已在 main.py 顶层加 `import pandas as pd` |
| **Pipeline 性能基线（实测）** | 冷启动（无缓存）：约 279s（`find_opportunities` 113s + `rank_opportunities` 含全量 fetch_data）；热启动（有缓存）：约 20s（`find_opportunities` 7s + `rank_opportunities` 5s）；`--recommend --no-news` 端到端约 19s 桌面报告 |
| **候选股评分资金/技术分为 0** | 当前评分依赖候选池标签（涨停/强势=5分动量 + 市值=2.5分）；资金/技术/龙虎/板块维度的数据源对接逻辑在 `_score_momentum`/`_score_fund_flow_fast` 等函数中，需对照 `get_recommend_report` 返回的 dict 字段名做匹配；这是已知的数据层待优化项，不影响 pipeline 正常运行 |

## 报告输出

| 模式 | 文件名 |
|------|--------|
| 全市场全景 | `A股市场全景分析报告_YYYYMMDD_HHMMSS.md` |
| 板块分析 | `板块深度分析_板块名_YYYYMMDD_HHMMSS.md` |
| 个股分析 | `个股分析_名称_YYYYMMDD_HHMMSS.md` |
| 机会发现 | `个股机会发现_YYYYMMDD_HHMMSS.md` |
| 热门股票 | `当日热门股票_YYYYMMDD_HHMMSS.md` |
| 涨停板 | `涨停板分析_YYYYMMDD_HHMMSS.md` |
| 科创板 | `科创板全景分析_YYYYMMDD_HHMMSS.md` |
| 龙虎榜 | `龙虎榜分析_YYYYMMDD_HHMMSS.md` |
| 资金流 | `资金流分析_YYYYMMDD_HHMMSS.md` |
| 荐股综合评级 | `荐股综合评级_YYYYMMDD_HHMMSS.md` |

所有报告自动保存到 `DESKTOP` 路径（默认 `main.py` 中配置，WSL 下为 `/mnt/c/Users/negan/Desktop/`）。

## 快速验证命令
```bash
cd ~/.hermes/skills/a-stock-analysis/scripts
python3 main.py --no-news      # 全市场，约8秒
python3 main.py --boards        # 列出49板块
python3 main.py --stock 300037 --kline --no-news  # 单股，约2秒
python3 main.py --stock 300037 --kline             # 单股+新闻，需SearXNG
python3 main.py --opportunity   # 机会发现（多个akshare接口）
python3 main.py --kcb           # 科创板
python3 main.py --lhb           # 龙虎榜
python3 main.py --fund-flow     # 资金流
python3 main.py --recommend     # 荐股评分（机会清单 + 多维度排序，一次完成）
python3 main.py --stars         # ⚠️ 已废弃，改用 --recommend
ls -lt ~/Desktop/*.md | head -5  # 查看最新报告
```

## 已知坑点

### `pd.concat` 列名不同导致列数叠加
`get_hot_boards()` 中行业流 rename 为"行业名称"、概念流 rename 为"概念名称"，concat 后
会得到 6 列而非 4 列（两者共同列 3 个 + 各自独有的 1 个）。**必须在 concat 前用
`df.rename(columns={...: "板块名称"})` 统一列名**，再 concat。

### akshare 行业/概念资金流 API 列名相同
`stock_fund_flow_industry` 和 `stock_fund_flow_concept` 返回的列名完全一致
（`行业`/`行业-涨跌幅`/`净额`），不是概念流返回"概念名称"。rename 逻辑要分别处理。

### 荐股评分阈值需同步维护
`opportunity.py`（`rank_opportunities` 中的 strong/focus/watch 分层）、
`report.py`（`gen_star_stocks_report` 报告表格标题）和 `main.py`（console 输出）
是三处独立的阈值硬编码，改评分满分时需同步更新这 3 处。
`star_stocks.py` 保留为兼容垫片（已不参与核心流程）。

### PDF 报告生成（TODO）
reportlab/weasyprint 未安装，PDF 输出暂不可用。安装后可启用：
```bash
pip install reportlab  # 中文字体需要 wqy-zenhei 或 source-han-serif
```
**目标**：个股分析 + K线图（matplotlib SVG内嵌）+ 技术指标表格 + 数据来源 + 免责声明，全部整合为单次 PDF。

### `fetch_data()` 返回三元组而非 DataFrame
`scraper.fetch_data()` 返回 `(df, board_df, board_map)`，其中 `board_df` 是板块
数据（用于领涨股→行业映射），`df` 才是行情 DataFrame。不要直接对三元组调用
`.columns` 等 DataFrame 方法。

### K线数据校验（实时价格交叉验证）
`get_kline()` 有两层防护机制（已内置，不需要手动处理）：

1. **日期校验**：最新K线日期必须在最近3个交易日内，否则自动 fallback 到同花顺。
2. **实时价格交叉验证**：调用 `get_realtime_price()`（腾讯 qt.gtimg.cn 单只接口，字段3=现价），与K线收盘对比：
   - 差异 < 5%：正常
   - 差异 5%~15%：标注 `_昨收可疑`
   - 差异 > 15%：强制用实时价格替换最后一条K线收盘，标记 `_实时校验`

⚠️ **仍需清缓存的场景**：若接口缓存层（文件缓存，非本模块）保存了旧数据，
或周一分析时只有上周五数据，可手动清缓存：
```python
import os
for f in os.listdir('/tmp/a_stock_cache/'):
    if 'kline' in f or 'ths' in f:
        os.remove(os.path.join('/tmp/a_stock_cache/', f))
```

`get_kline()` 返回 `list[dict]`，key 是 `'前复权收盘'`（不是 `'收盘'`），`df = pd.DataFrame(data)` 后用 `df['前复权收盘']`。

### 多股对比 `--stock A,B --kline` 报告内容单薄
内置多股对比报告只含基础行情表格，不含技术指标。**深度技术对比需用自定义脚本**：
参考 `analyzer.py` 的 `analyze_stock()` 中的技术指标实现（RSI/MACD/KDJ/布林带/均线），
读取 K线后自行计算后逐行输出对比表格。也可以在 `analyzer.py` 中增加
`analyze_stock_comparison()` 函数作为专用对比入口。
