"""
postclose_review.py - A股收盘复盘分析引擎
==========================================
聚合 scraper / fund_flow / opportunity / lhb / board_analysis 所有模块，
生成结构化复盘数据（主线分类/四分层锚定/连板风判/情绪阶段），
供 report_html.py 渲染为收盘复盘 HTML 报告。

使用方式:
  from postclose_review import run_postclose_review
  data = run_postclose_review()
  # data 是完整的结构化 dict，可传入 report_html.gen_postclose_html(data)

分析框架:
  1. 盘型/环境 — 指数、广度、涨跌停数量
  2. 资金流证据 — 行业/板块净流入前5、个股净流入/流出前5
  3. 情绪运行阶段 — 发酵扩散偏高潮/冰点/分歧/一致等
  4. 主线/次主线/活口/失败轮动 — 方向归类
  5. 连板高度单元 — 连板股风险判定
  6. 四分层 — 情绪锚/强度锚/次核心/活口/失败锚
"""

import sys
import os
import time
import warnings
from datetime import datetime, date
from typing import Optional

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# 确保当前目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 模块懒加载 ─────────────────────────────────────────────────

_SCRAPER = None
_FF = None
_OPP = None
_LHB = None
_BA = None

def _load(mod_name: str):
    try:
        return __import__(mod_name, fromlist=[''])
    except ImportError:
        return None

def _scraper():
    global _SCRAPER
    if _SCRAPER is None:
        _SCRAPER = _load('scraper')
    return _SCRAPER

def _ff():
    global _FF
    if _FF is None:
        _FF = _load('fund_flow')
    return _FF

def _opp():
    global _OPP
    if _OPP is None:
        _OPP = _load('opportunity')
    return _OPP

def _lhb():
    global _LHB
    if _LHB is None:
        _LHB = _load('lhb')
    return _LHB

def _ba():
    global _BA
    if _BA is None:
        _BA = _load('board_analysis')
    return _BA


# ── 工具函数 ────────────────────────────────────────────────────

def _sf(v, default=0.0):
    try:
        f = float(v)
        return f if not np.isnan(f) else default
    except:
        return default

def _fmt_pct(v):
    try:
        v = float(v)
        if np.isnan(v): return "N/A"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.2f}%"
    except:
        return "N/A"

def _fmt_amt(v):
    try:
        v = float(v)
        if abs(v) >= 1e8:
            return f"{v/1e8:.2f}亿"
        if abs(v) >= 1e6:
            return f"{v/1e6:.2f}万"
        return f"{v:.0f}"
    except:
        return "N/A"

def _safe_col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None

def _today_str():
    return date.today().strftime("%Y%m%d")

def _code_bare(code):
    """去掉前缀返回纯6位代码"""
    s = str(code)
    if s.startswith(("sz", "sh", "bj")) and len(s) == 8:
        return s[2:]
    return s.zfill(6)


# ═══════════════════════════════════════════════════════════════════
#  1. 数据汇聚
# ═══════════════════════════════════════════════════════════════════

def _fetch_index_data():
    """获取主要指数行情（腾讯接口）"""
    indices = {}
    try:
        import requests
        url = "https://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688"
        session = requests.Session()
        session.trust_env = False
        r = session.get(url, timeout=10)
        r.encoding = "gbk"
        idx_map = {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指",
            "sh000688": "科创50",
        }
        for line in r.text.strip().split("\n"):
            if "~" not in line:
                continue
            m = __import__('re').search(r'v_(\w+)="([^"]+)"', line)
            if not m:
                continue
            sym = m.group(1)
            if sym not in idx_map:
                continue
            parts = m.group(2).split("~")
            if len(parts) < 33:
                continue
            cur = _sf(parts[3])
            chg = _sf(parts[31])
            pct = _sf(parts[32])
            if cur <= 0:
                continue
            indices[sym] = {
                "name": idx_map[sym],
                "price": cur,
                "change": chg,
                "pct": pct,
            }
    except Exception as e:
        print(f"  [postclose] 指数数据获取失败: {e}")
    return indices


def _fetch_all_data(use_cache=True):
    """汇聚所有数据源"""
    print("[postclose] 汇聚数据...")
    t0 = time.time()

    # 1. 全量实时行情
    scr = _scraper()
    realtime_df, board_df, industry_map = None, pd.DataFrame(), {}
    if scr:
        try:
            realtime_df, board_df, industry_map = scr.fetch_data(use_cache=use_cache, force_cache=True)
            print(f"  [postclose] 实时行情: {len(realtime_df)} 只")
        except Exception as e:
            print(f"  [postclose] 实时行情获取失败: {e}")

    # 2. 指数行情
    indices = _fetch_index_data()

    # 3. 资金流
    ind_flow = pd.DataFrame()
    concept_flow = pd.DataFrame()
    hsgt = pd.DataFrame()
    flow_sentiment = "中性"
    ff = _ff()
    if ff:
        if hasattr(ff, 'get_industry_flow'):
            try:
                ind_flow = ff.get_industry_flow()
                print(f"  [postclose] 行业资金流: {len(ind_flow)} 个行业")
            except Exception as e:
                print(f"  [postclose] 行业资金流失败: {e}")
        if hasattr(ff, 'get_concept_flow'):
            try:
                concept_flow = ff.get_concept_flow()
            except:
                pass
        if hasattr(ff, 'get_hsgt_hold'):
            try:
                hsgt = ff.get_hsgt_hold()
            except:
                pass

    # 综合资金情绪
    if not ind_flow.empty:
        net_col = _safe_col(ind_flow, "净流入(万)", "净额")
        if net_col:
            total_net = pd.to_numeric(ind_flow[net_col], errors="coerce").sum() / 1e8
            if total_net > 500:
                flow_sentiment = "大幅流入"
            elif total_net > 100:
                flow_sentiment = "温和流入"
            elif total_net < -500:
                flow_sentiment = "大幅流出"
            elif total_net < -100:
                flow_sentiment = "温和流出"

    # 4. 涨跌停数据
    opp = _opp()
    opp_data = {}
    if opp:
        try:
            opp_data = opp.find_opportunities()
            print(f"  [postclose] 机会池: {list(opp_data.keys())}")
        except Exception as e:
            print(f"  [postclose] 机会数据失败: {e}")

    zt_df = opp_data.get("涨停股池", pd.DataFrame())
    dt_df = opp_data.get("跌停股池", pd.DataFrame())
    zbgc_df = opp_data.get("炸板股池", pd.DataFrame())
    yesterday_zt_df = opp_data.get("昨日涨停", pd.DataFrame())
    strong_df = opp_data.get("强势股池", pd.DataFrame())

    # 5. 龙虎榜
    lhb_result = {}
    lhb_mod = _lhb()
    if lhb_mod and hasattr(lhb_mod, 'analyze_lhb'):
        try:
            lhb_result = lhb_mod.analyze_lhb(days=10)
        except Exception as e:
            print(f"  [postclose] 龙虎榜数据失败: {e}")

    print(f"  [postclose] 数据汇聚完成，耗时 {time.time()-t0:.1f}s")
    return {
        "realtime_df": realtime_df,
        "board_df": board_df,
        "industry_map": industry_map,
        "indices": indices,
        "ind_flow": ind_flow,
        "concept_flow": concept_flow,
        "hsgt": hsgt,
        "flow_sentiment": flow_sentiment,
        "zt_df": zt_df,
        "dt_df": dt_df,
        "zbgc_df": zbgc_df,
        "yesterday_zt_df": yesterday_zt_df,
        "strong_df": strong_df,
        "lhb_result": lhb_result,
        "opp_data": opp_data,
    }


# ═══════════════════════════════════════════════════════════════════
#  2. 市场环境分析
# ═══════════════════════════════════════════════════════════════════

def _analyze_environment(realtime_df, board_df, zt_df, zbgc_df, dt_df, indices):
    """分析盘型/环境"""
    if realtime_df is None or realtime_df.empty:
        return {"error": "实时行情数据不可用"}

    total = len(realtime_df)
    up = int((realtime_df["涨跌幅(%)"] > 0).sum())
    down = int((realtime_df["涨跌幅(%)"] < 0).sum())
    flat = total - up - down
    avg_pct = float(realtime_df["涨跌幅(%)"].mean())
    med_pct = float(realtime_df["涨跌幅(%)"].median())
    breadth = round(up / total * 100, 2) if total > 0 else 0

    zt_count = len(zt_df) if zt_df is not None and not zt_df.empty else 0
    zbgc_count = len(zbgc_df) if zbgc_df is not None and not zbgc_df.empty else 0
    dt_count = len(dt_df) if dt_df is not None and not dt_df.empty else 0

    # 非ST涨停统计
    nonst_zt = 0
    if zt_df is not None and not zt_df.empty:
        name_col = _safe_col(zt_df, "名称")
        if name_col:
            nonst_zt = int((~zt_df[name_col].astype(str).str.startswith(("ST", "*ST", "S*ST"))).sum())

    # 指数数据
    idx_items = []
    for sym, info in indices.items():
        idx_items.append({
            "name": info["name"],
            "price": f"{info['price']:.2f}",
            "pct": _fmt_pct(info["pct"]),
        })

    # 板强度排名（前10）
    board_strength = []
    if board_df is not None and not board_df.empty:
        pct_col = _safe_col(board_df, "涨跌幅(%)")
        if pct_col:
            top_boards = board_df.nlargest(10, pct_col)
            for _, row in top_boards.iterrows():
                name_col = _safe_col(board_df, "板块名称")
                lead_col = _safe_col(board_df, "领涨股")
                board_strength.append({
                    "name": row.get(name_col, "") if name_col else "",
                    "pct": _fmt_pct(row.get(pct_col, 0)),
                    "lead_stock": row.get(lead_col, "") if lead_col else "",
                })

    return {
        "total": total,
        "up": up,
        "down": down,
        "flat": flat,
        "avg_pct": _fmt_pct(avg_pct),
        "med_pct": _fmt_pct(med_pct),
        "breadth": breadth,
        "zt_count": zt_count,
        "nonst_zt_count": nonst_zt,
        "zbgc_count": zbgc_count,
        "dt_count": dt_count,
        "zt_total_reached": zt_count + zbgc_count,
        "indices": idx_items,
        "board_strength": board_strength,
    }


# ═══════════════════════════════════════════════════════════════════
#  3. 资金流证据
# ═══════════════════════════════════════════════════════════════════

def _analyze_fund_evidence(ind_flow, realtime_df, zt_df):
    """提取资金流证据（行业Top5 + 个股Top5）"""
    evidence = {
        "sector_inflow_top5": [],
        "sector_outflow_top5": [],
        "stock_inflow_top5": [],
        "stock_outflow_top5": [],
    }

    # 行业净流入/流出 Top5
    if ind_flow is not None and not ind_flow.empty:
        name_col = _safe_col(ind_flow, "行业名称")
        net_col = _safe_col(ind_flow, "净流入(万)")
        pct_col = _safe_col(ind_flow, "涨跌幅(%)")
        if net_col and name_col:
            # 流入Top5
            top_in = ind_flow.nlargest(5, net_col)
            for _, row in top_in.iterrows():
                evidence["sector_inflow_top5"].append({
                    "name": row[name_col],
                    "net": _fmt_amt(row[net_col] * 10000) if "万" in str(net_col) else _fmt_amt(row[net_col]),
                    "pct": _fmt_pct(row[pct_col]) if pct_col else "",
                })
            # 流出Top5
            top_out = ind_flow.nsmallest(5, net_col)
            for _, row in top_out.iterrows():
                evidence["sector_outflow_top5"].append({
                    "name": row[name_col],
                    "net": _fmt_amt(row[net_col] * 10000) if "万" in str(net_col) else _fmt_amt(row[net_col]),
                    "pct": _fmt_pct(row[pct_col]) if pct_col else "",
                })

    # 个股资金流 Top5（从实时行情中取成交额最大的）
    if realtime_df is not None and not realtime_df.empty:
        amt_col = _safe_col(realtime_df, "成交额(元)")
        pct_col2 = _safe_col(realtime_df, "涨跌幅(%)")
        name_col2 = _safe_col(realtime_df, "名称")
        code_col2 = _safe_col(realtime_df, "代码")
        if amt_col and pct_col2:
            # 涨幅靠前 + 成交额大 → 资金流入个股
            inflow_stocks = realtime_df.copy()
            inflow_stocks = inflow_stocks[inflow_stocks[pct_col2] > 0]
            if amt_col in inflow_stocks.columns:
                top_in_stocks = inflow_stocks.nlargest(5, amt_col)
                for _, row in top_in_stocks.iterrows():
                    evidence["stock_inflow_top5"].append({
                        "name": str(row.get(name_col2, "")),
                        "code": _code_bare(row.get(code_col2, "")),
                        "pct": _fmt_pct(row[pct_col2]),
                        "amt": _fmt_amt(row[amt_col]),
                    })

            # 跌幅靠前 + 成交额大 → 资金流出个股
            outflow_stocks = realtime_df.copy()
            outflow_stocks = outflow_stocks[outflow_stocks[pct_col2] < 0]
            if amt_col in outflow_stocks.columns:
                top_out_stocks = outflow_stocks.nlargest(5, amt_col)
                for _, row in top_out_stocks.iterrows():
                    evidence["stock_outflow_top5"].append({
                        "name": str(row.get(name_col2, "")),
                        "code": _code_bare(row.get(code_col2, "")),
                        "pct": _fmt_pct(row[pct_col2]),
                        "amt": _fmt_amt(row[amt_col]),
                    })

    return evidence


# ═══════════════════════════════════════════════════════════════════
#  4. 情绪运行阶段判定
# ═══════════════════════════════════════════════════════════════════

def _determine_market_stage(env, flow_sentiment):
    """根据涨停数/炸板率/市场广度判定市场情绪阶段"""
    zt = env["zt_count"]
    zbgc = env["zbgc_count"]
    dt = env["dt_count"]
    breadth = env["breadth"]
    zt_reached = env["zt_total_reached"]

    # 炸板率
    zbgc_rate = zbgc / zt_reached * 100 if zt_reached > 0 else 0

    # 规则判定
    if zt >= 100 and zbgc_rate <= 20 and breadth >= 60:
        stage = "发酵扩散偏高潮"
        stage_emoji = "🔴"
        risk_note = "涨停数量很大，但炸板和跌停未消失，后排普涨和旧强分化不能被误判成同等主线"
    elif zt >= 80 and zbgc_rate <= 25 and breadth >= 55:
        stage = "强修复扩散"
        stage_emoji = "🟡"
        risk_note = "扩散后有淘汰，更适合验证前排和容量承接，不可无差别外推后排"
    elif zt >= 50 and breadth >= 50:
        stage = "修复确认"
        stage_emoji = "🟡"
        risk_note = "方向开始收敛，关注主线能否继续给正反馈"
    elif zt >= 30 and breadth >= 45:
        stage = "弱修复/轮动"
        stage_emoji = "🔵"
        risk_note = "板块轮动快，追高风险大，只看核心前排"
    elif zt <= 20 and breadth <= 40:
        stage = "冰点/退潮"
        stage_emoji = "🔵"
        risk_note = "资金观望，不宜激进开仓"
    elif dt >= 50:
        stage = "恐慌释放"
        stage_emoji = "⚪"
        risk_note = "跌停数量大，等恐慌释放完毕后再看修复"
    else:
        stage = "震荡分歧"
        stage_emoji = "🔵"
        risk_note = "多空力量均衡，方向不明确"

    return {
        "stage": stage,
        "emoji": stage_emoji,
        "zbgc_rate": round(zbgc_rate, 1),
        "risk_note": risk_note,
        "flow_sentiment": flow_sentiment,
    }


# ═══════════════════════════════════════════════════════════════════
#  5. 方向归类（主线/次主线/活口/失败轮动）
# ═══════════════════════════════════════════════════════════════════

# 板块→方向映射（父子标签体系）
THEME_CLASSIFICATION = {
    # AI算力/硬件/通信链
    "通信设备": ("AI算力/硬件/通信链", "主线"),
    "通信服务": ("AI算力/硬件/通信链", "主线"),
    "光通信": ("AI算力/硬件/通信链", "主线"),
    "光纤光缆": ("AI算力/硬件/通信链", "主线"),
    "CPO概念": ("AI算力/硬件/通信链", "主线"),
    "元器件": ("AI算力/硬件/通信链", "主线"),
    "半导体": ("AI算力/硬件/通信链", "主线"),
    "芯片": ("AI算力/硬件/通信链", "主线"),
    "PCB概念": ("AI算力/硬件/通信链", "主线"),
    "消费电子": ("AI算力/硬件/通信链", "主线"),
    "先进封装": ("AI算力/硬件/通信链", "主线"),
    "电子元件": ("AI算力/硬件/通信链", "主线"),
    "算力租赁": ("AI算力/硬件/通信链", "主线"),
    "数据中心": ("AI算力/硬件/通信链", "主线"),
    "东数西算": ("AI算力/硬件/通信链", "主线"),
    "云计算": ("AI算力/硬件/通信链", "主线"),
    "人工智能": ("AI算力/硬件/通信链", "主线"),
    "智能穿戴": ("AI算力/硬件/通信链", "主线"),
    "5G概念": ("AI算力/硬件/通信链", "次主线"),
    "电子器件": ("AI算力/硬件/通信链", "次主线"),
    # 机器人/工业母机/高端制造
    "机器人": ("机器人/工业母机/高端制造", "次主线"),
    "工业母机": ("机器人/工业母机/高端制造", "次主线"),
    "自动化设备": ("机器人/工业母机/高端制造", "次主线"),
    "智能制造": ("机器人/工业母机/高端制造", "次主线"),
    "机械行业": ("机器人/工业母机/高端制造", "次主线"),
    "通用设备": ("机器人/工业母机/高端制造", "次主线"),
    "专用设备": ("机器人/工业母机/高端制造", "次主线"),
    "高端装备": ("机器人/工业母机/高端制造", "次主线"),
    # 电力/电网/新能源
    "电力行业": ("电力/电网/新能源", "次主线"),
    "电网设备": ("电力/电网/新能源", "次主线"),
    "电力物联网": ("电力/电网/新能源", "次主线"),
    "光伏": ("电力/电网/新能源", "次主线"),
    "风电": ("电力/电网/新能源", "次主线"),
    "核电": ("电力/电网/新能源", "次主线"),
    "储能": ("电力/电网/新能源", "次主线"),
    "充电桩": ("电力/电网/新能源", "次主线"),
    "电气设备": ("电力/电网/新能源", "次主线"),
    # 消费/传媒/AI应用
    "传媒娱乐": ("消费/传媒/AI应用", "活口"),
    "文化传媒": ("消费/传媒/AI应用", "活口"),
    "游戏": ("消费/传媒/AI应用", "活口"),
    "抖音概念": ("消费/传媒/AI应用", "活口"),
    "网红经济": ("消费/传媒/AI应用", "活口"),
    "AI应用": ("消费/传媒/AI应用", "活口"),
    "食品饮料": ("消费/传媒/AI应用", "活口"),
    # 商业航天/军工/低空
    "商业航天": ("商业航天/军工/低空", "活口"),
    "航天航空": ("商业航天/军工/低空", "活口"),
    "军工": ("商业航天/军工/低空", "活口"),
    "大飞机": ("商业航天/军工/低空", "活口"),
    "低空经济": ("商业航天/军工/低空", "活口"),
    "无人机": ("商业航天/军工/低空", "活口"),
    # ST情绪/风险链
    "ST": ("ST情绪/风险链", "情绪"),
}


def _classify_themes(realtime_df, board_df, industry_map, zt_df, ind_flow):
    """将当日涨停/强势股按方向归类为主/次主线/活口"""
    themes = {}

    # 从 zt_df 中获取涨停股所属行业
    if zt_df is not None and not zt_df.empty and not realtime_df.empty:
        name_col = _safe_col(zt_df, "名称")
        code_col_z = _safe_col(zt_df, "代码")
        chg_col = _safe_col(zt_df, "涨跌幅(%)")

        for _, row in zt_df.iterrows():
            code = _code_bare(row.get(code_col_z, ""))
            name = str(row.get(name_col, ""))
            chg = _sf(row.get(chg_col, 0)) if chg_col else 0

            # 匹配行业
            industry = _find_stock_industry(code, industry_map, realtime_df)
            if not industry:
                industry = _find_stock_board(code, name, realtime_df)

            # 映射到方向
            theme_name, theme_level = _map_to_theme(industry, name)
            if theme_name is None:
                theme_name = "独立/待归因"
                theme_level = "待定"

            if theme_name not in themes:
                themes[theme_name] = {
                    "name": theme_name,
                    "level": theme_level,
                    "stocks": [],
                    "member_count": 0,
                    "board_pct": "",
                    "board_fund": "",
                    "reasoning": "",
                }
            stock_info = {
                "code": code,
                "name": name,
                "pct": _fmt_pct(chg),
                "pct_raw": chg,
                "industry": industry or "未归类",
            }
            themes[theme_name]["stocks"].append(stock_info)
            themes[theme_name]["member_count"] += 1

    # 补充强势股池中的票（如果不在涨停池中）
    opp = _opp()
    if opp:
        try:
            opp_data = opp.find_opportunities()
            strong = opp_data.get("强势股池", pd.DataFrame())
            yesterday_zt = opp_data.get("昨日涨停", pd.DataFrame())

            for df_src, src_label in [(strong, "强势"), (yesterday_zt, "昨日涨停")]:
                if df_src is None or df_src.empty:
                    continue
                code_col = _safe_col(df_src, "代码")
                name_col = _safe_col(df_src, "名称")
                chg_col = _safe_col(df_src, "涨跌幅(%)")
                if not code_col:
                    continue
                for _, row in df_src.iterrows():
                    code = _code_bare(row.get(code_col, ""))
                    name = str(row.get(name_col, ""))
                    chg = _sf(row.get(chg_col, 0)) if chg_col else 0
                    # 检查是否已在主题池中
                    already_in = False
                    for t in themes.values():
                        for s in t["stocks"]:
                            if s["code"] == code:
                                already_in = True
                                break
                        if already_in:
                            break
                    if already_in:
                        continue
                    # 强势股才加入非涨停主题
                    industry = _find_stock_industry(code, industry_map, realtime_df)
                    if not industry:
                        industry = _find_stock_board(code, name, realtime_df)
                    theme_name, theme_level = _map_to_theme(industry, name)
                    if theme_name is None:
                        continue
                    if theme_name not in themes:
                        themes[theme_name] = {
                            "name": theme_name,
                            "level": theme_level,
                            "stocks": [],
                            "member_count": 0,
                            "board_pct": "",
                            "board_fund": "",
                            "reasoning": "",
                        }
                    stock_info = {
                        "code": code,
                        "name": name,
                        "pct": _fmt_pct(chg),
                        "pct_raw": chg,
                        "industry": industry or "未归类",
                    }
                    themes[theme_name]["stocks"].append(stock_info)
                    themes[theme_name]["member_count"] += 1
        except Exception as e:
            print(f"  [postclose] 补充强势股失败: {e}")

    # 补充板块量价数据
    if board_df is not None and not board_df.empty:
        for theme in themes.values():
            # 查找匹配的板块
            pct_col = _safe_col(board_df, "涨跌幅(%)")
            name_col_b = _safe_col(board_df, "板块名称")
            if pct_col and name_col_b:
                matched = board_df[board_df[name_col_b].astype(str).str.contains(
                    theme["name"][:6], na=False
                )]
                if not matched.empty:
                    row = matched.iloc[0]
                    theme["board_pct"] = _fmt_pct(row[pct_col])

    # 补资金流数据
    if ind_flow is not None and not ind_flow.empty:
        name_col_f = _safe_col(ind_flow, "行业名称")
        net_col = _safe_col(ind_flow, "净流入(万)")
        if name_col_f and net_col:
            for theme in themes.values():
                matched = ind_flow[ind_flow[name_col_f].astype(str).str.contains(
                    theme["name"][:6], na=False
                )]
                if not matched.empty:
                    row = matched.iloc[0]
                    net_val = _sf(row[net_col], 0)
                    theme["board_fund"] = _fmt_amt(net_val * 10000 if "万" in str(net_col) else net_val)

    # 排序：主线 > 次主线 > 活口，同级别按成员数
    level_order = {"主线": 0, "次主线": 1, "活口": 2, "情绪": 3, "待定": 4}
    sorted_themes = sorted(
        themes.values(),
        key=lambda t: (level_order.get(t["level"], 9), -t["member_count"])
    )

    return sorted_themes


def _find_stock_industry(code, industry_map, realtime_df):
    """从 multiple sources 查找股票所属行业"""
    bare = _code_bare(code)

    # 1. industry_map
    if industry_map:
        for key in [bare, f"sz{bare}", f"sh{bare}"]:
            if key in industry_map:
                return str(industry_map[key])

    # 2. zt_df 所属行业列
    if realtime_df is not None and not realtime_df.empty:
        code_col = _safe_col(realtime_df, "代码")
        if code_col:
            rt_df = realtime_df.copy()
            rt_df["_code_bare"] = rt_df[code_col].astype(str).str[-6:]
            match = rt_df[rt_df["_code_bare"] == bare]
            if not match.empty:
                for col in ["所属行业", "行业", "industry"]:
                    if col in rt_df.columns:
                        val = match.iloc[0].get(col)
                        if val and str(val) not in ("nan", ""):
                            return str(val)

    return None


def _find_stock_board(code, name, realtime_df):
    """通过代码前缀和名称推断板块"""
    bare = _code_bare(code)
    # 前缀推断
    if bare.startswith("68"):
        return "半导体"  # 科创板多数归半导体/科技
    if bare.startswith("300"):
        return "创业板"
    # 名称推断
    keywords = {
        "通信": "通信设备", "光纤": "光纤光缆", "光电": "光通信",
        "微电": "半导体", "芯片": "芯片", "软件": "软件服务",
        "机器": "机器人", "数控": "工业母机", "智能": "智能制造",
        "电力": "电力行业", "电气": "电气设备", "能源": "新能源",
        "传媒": "传媒娱乐", "影视": "文化传媒", "游戏": "游戏",
        "医药": "医药", "医疗": "医疗器械", "生物": "生物制药",
        "航空": "航天航空", "航天": "商业航天", "军工": "军工",
    }
    for kw, board in keywords.items():
        if kw in str(name):
            return board
    return None


def _map_to_theme(industry, name):
    """将行业名映射到方向"""
    if not industry:
        return None, None
    for keyword, (theme, level) in THEME_CLASSIFICATION.items():
        if keyword in str(industry) or keyword in str(name):
            return theme, level
    # 模糊匹配
    for keyword, (theme, level) in THEME_CLASSIFICATION.items():
        if any(w in str(industry) for w in keyword):
            return theme, level
    return None, None


# ═══════════════════════════════════════════════════════════════════
#  6. 连板高度分析
# ═══════════════════════════════════════════════════════════════════

def _analyze_connection_board(zt_df, realtime_df, industry_map, themes):
    """分析连板股：高度、换手变化、风险判定"""
    if zt_df is None or zt_df.empty:
        return []

    # 找连板股
    lianban_stocks = []
    lb_cols = [c for c in zt_df.columns if "连板" in str(c) or "连续" in str(c)]

    for _, row in zt_df.iterrows():
        lb_count = 0
        for col in lb_cols:
            try:
                val = int(float(row[col]))
                lb_count = max(lb_count, val)
            except:
                pass
        if lb_count < 2:
            continue

        code = _code_bare(row.get("代码", ""))
        name = str(row.get("名称", ""))
        chg = _sf(row.get("涨跌幅(%)", row.get("涨跌幅", 0)))

        # 从实时行情获取换手率
        turnover = None
        prev_turnover = None
        if realtime_df is not None and not realtime_df.empty:
            code_col = _safe_col(realtime_df, "代码")
            if code_col:
                rt_df = realtime_df.copy()
                rt_df["_code_bare"] = rt_df[code_col].astype(str).str[-6:]
                match = rt_df[rt_df["_code_bare"] == _code_bare(code)]
                if not match.empty:
                    tr_col = _safe_col(realtime_df, "换手率(%)")
                    if tr_col:
                        turnover = _sf(match.iloc[0].get(tr_col, 0))

        # 风险判定
        risk_type = "分歧接力"
        if turnover is not None:
            if turnover < 3:
                risk_type = "一字连板风险"
            elif turnover > 20:
                risk_type = "高潮接力风险"
            elif 3 <= turnover <= 10:
                risk_type = "分歧接力"

        # 判断状态
        if abs(chg) >= 19.8:
            state = "封住涨停"
        elif chg >= 9.9:
            state = "回封涨停"
        else:
            state = "非涨跌停"

        # 确定所属主题
        theme = "独立/待归因"
        for t in themes:
            for s in t.get("stocks", []):
                if s.get("code") == code:
                    theme = t["name"]
                    break

        # ST标记
        is_st = name.startswith(("ST", "*ST", "S*ST", "SST"))
        if is_st:
            risk_type = "ST情绪高度，风险单列"

        lianban_stocks.append({
            "code": code,
            "name": name,
            "lb_count": lb_count,
            "state": state,
            "pct": _fmt_pct(chg),
            "pct_raw": chg,
            "turnover": f"{turnover:.2f}%" if turnover else "N/A",
            "prev_turnover": "N/A",
            "theme": theme,
            "risk_type": risk_type,
            "is_st": is_st,
        })

    # 按连板数降序
    lianban_stocks.sort(key=lambda x: (-x["lb_count"], -x["pct_raw"]))
    return lianban_stocks


# ═══════════════════════════════════════════════════════════════════
#  7. 四分层（情绪锚/强度锚/次核心/活口/失败锚）
# ═══════════════════════════════════════════════════════════════════

def _four_layer_anchor(theme, realtime_df):
    """在每个方向内对个股做四分层角色判定"""
    stocks = theme.get("stocks", [])
    if not stocks or realtime_df is None or realtime_df.empty:
        return theme

    # 计算每个股票的评分
    scored = []
    code_col = _safe_col(realtime_df, "代码")
    tr_col = _safe_col(realtime_df, "换手率(%)")
    amt_col = _safe_col(realtime_df, "成交额(元)")
    cap_col = _safe_col(realtime_df, "流通市值(亿)")

    for s in stocks:
        code = s["code"]
        rt_match = None
        if code_col:
            rt_df = realtime_df.copy()
            rt_df["_code_bare"] = rt_df[code_col].astype(str).str[-6:]
            match = rt_df[rt_df["_code_bare"] == _code_bare(code)]
            if not match.empty:
                rt_match = match.iloc[0]

        pct = _sf(s.get("pct_raw", 0))
        turnover = _sf(rt_match.get(tr_col, 0), 0) if rt_match is not None and tr_col else 0
        amt = _sf(rt_match.get(amt_col, 0), 0) if rt_match is not None and amt_col else 0
        cap = _sf(rt_match.get(cap_col, 0), 0) if rt_match is not None and cap_col else 0

        # 评分 = 涨幅权重40% + 成交额权重30% + 流通市值权重20% + 换手率权重10%
        pct_score = min(pct / 20 * 40, 40) if pct > 0 else 0
        amt_score = min(amt / 5e9 * 30, 30) if amt > 0 else 0
        cap_score = min(cap / 500 * 20, 20) if cap > 0 else 0
        tr_score = min(turnover / 20 * 10, 10) if turnover > 0 else 0
        total_score = pct_score + amt_score + cap_score + tr_score

        s["score"] = round(total_score, 1)
        s["turnover"] = f"{turnover:.2f}%" if turnover else "N/A"
        s["amt"] = _fmt_amt(amt)

        # 量价裁定
        if turnover > 10:
            s["volume_judge"] = "放量封板" if pct >= 9.9 else "放量承接"
        elif 3 <= turnover <= 10:
            s["volume_judge"] = "缩量锁筹" if pct >= 9.9 else "缩量承接"
        else:
            s["volume_judge"] = "缩量封板" if pct >= 9.9 else "缩量"

        scored.append(s)

    # 降序排列
    scored.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 分配角色
    # 前1-2名: 情绪锚 + 强度锚
    # 3-5名: 次核心
    # 6-8名: 活口
    # 其余: 未进入四分层
    anchors = []

    if len(scored) >= 1:
        scored[0]["role"] = "情绪锚"
        anchors.append(scored[0])

    if len(scored) >= 2:
        scored[1]["role"] = "强度锚"
        anchors.append(scored[1])

    for i in range(2, min(len(scored), 5)):
        scored[i]["role"] = "次核心"

    for i in range(5, min(len(scored), 8)):
        scored[i]["role"] = "活口"

    for i in range(8, len(scored)):
        scored[i]["role"] = "未进入四分层"

    theme["anchors"] = anchors
    theme["all_scored"] = scored
    theme["unclassified"] = [s for s in scored if s.get("role") == "未进入四分层"]

    # 失败锚
    theme["failed_anchor"] = None
    if theme.get("level") in ("主线", "次主线"):
        failed = [s for s in scored if s.get("pct_raw", 0) < 3 and s.get("role") in ("次核心", "活口")]
        if failed:
            theme["failed_anchor"] = failed[0]["name"]

    return theme


# ═══════════════════════════════════════════════════════════════════
#  8. 轮动支线追踪（跨日对比）
# ═══════════════════════════════════════════════════════════════════

def _track_rotation(yesterday_zt_df, zt_df, realtime_df, themes):
    """追踪上一交易日支线在今日的演变"""
    # 从昨日涨停提取当时的支线
    yesterday_tracks = []
    if yesterday_zt_df is not None and not yesterday_zt_df.empty:
        code_col = _safe_col(yesterday_zt_df, "代码")
        name_col = _safe_col(yesterday_zt_df, "名称")
        if code_col:
            # 只取前5个代表性股票
            for _, row in yesterday_zt_df.head(5).iterrows():
                code = _code_bare(row.get(code_col, ""))
                name = str(row.get(name_col, ""))
                chg = _sf(row.get("涨跌幅(%)", row.get("涨跌幅", 0)))
                yesterday_tracks.append({"code": code, "name": name, "yesterday_pct": _fmt_pct(chg)})

    # 构建当前日期的追踪结果
    tracks = []
    for yt in yesterday_tracks:
        # 查找今日表现
        today_pct = "N/A"
        status = "未延续"
        if realtime_df is not None and not realtime_df.empty:
            code_col = _safe_col(realtime_df, "代码")
            if code_col:
                rt_df = realtime_df.copy()
                rt_df["_code_bare"] = rt_df[code_col].astype(str).str[-6:]
                match = rt_df[rt_df["_code_bare"] == _code_bare(yt["code"])]
                if not match.empty:
                    pct_col = _safe_col(realtime_df, "涨跌幅(%)")
                    if pct_col:
                        today_pct = _fmt_pct(match.iloc[0].get(pct_col, 0))
                        pct_raw = _sf(match.iloc[0].get(pct_col, 0))
                        if pct_raw >= 9.9:
                            status = "留存并升主线"
                        elif pct_raw >= 3:
                            status = "留存但分化"
                        elif pct_raw >= 0:
                            status = "留存为次级方向"
                        else:
                            status = "活口/应用扩散"

        # 确定归位
        for t in themes:
            for s in t.get("stocks", []):
                if s.get("code") == yt["code"]:
                    status = f"留存 → {t['name'][:20]}"
                    break

        tracks.append({
            "code": yt["code"],
            "name": yt["name"],
            "yesterday_pct": yt["yesterday_pct"],
            "today_pct": today_pct,
            "status": status,
        })

    return tracks


# ═══════════════════════════════════════════════════════════════════
#  9. 主入口
# ═══════════════════════════════════════════════════════════════════

def run_postclose_review(use_cache=True):
    """
    主入口：运行完整收盘复盘分析，返回结构化 dict。
    包含所有 13 个章节所需的数据，供 report_html.py 渲染。
    """
    t_start = time.time()
    print("=" * 62)
    print("  A股收盘复盘分析引擎")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    # 1. 汇聚数据
    data = _fetch_all_data(use_cache=use_cache)

    realtime_df = data["realtime_df"]
    board_df = data["board_df"]
    industry_map = data["industry_map"]
    indices = data["indices"]
    ind_flow = data["ind_flow"]
    flow_sentiment = data["flow_sentiment"]
    zt_df = data["zt_df"]
    dt_df = data["dt_df"]
    zbgc_df = data["zbgc_df"]
    yesterday_zt_df = data["yesterday_zt_df"]

    if realtime_df is None or realtime_df.empty:
        return {"error": "无法获取实时行情数据，请检查网络连接", "elapsed": time.time() - t_start}

    # 2. 环境分析
    print("[postclose] 分析市场环境...")
    env = _analyze_environment(realtime_df, board_df, zt_df, zbgc_df, dt_df, indices)

    # 3. 资金流证据
    print("[postclose] 提取资金流证据...")
    fund_evidence = _analyze_fund_evidence(ind_flow, realtime_df, zt_df)

    # 4. 情绪阶段
    print("[postclose] 判定情绪阶段...")
    stage = _determine_market_stage(env, flow_sentiment)

    # 5. 方向归类
    print("[postclose] 归类市场方向...")
    themes = _classify_themes(realtime_df, board_df, industry_map, zt_df, ind_flow)

    # 6. 连板分析
    print("[postclose] 分析连板高度...")
    lianban = _analyze_connection_board(zt_df, realtime_df, industry_map, themes)

    # 7. 四分层
    print("[postclose] 执行四分层锚定...")
    for theme in themes:
        if theme["member_count"] >= 2:
            _four_layer_anchor(theme, realtime_df)

    # 8. 轮动追踪
    print("[postclose] 追踪轮动支线...")
    rotation = _track_rotation(yesterday_zt_df, zt_df, realtime_df, themes)

    # 9. 股票池更新
    stock_pool = {
        "upgrade_keep": [],
        "new_add": [],
        "risk_downgrade": [],
    }
    # 主线的情绪锚+强度锚 → 上修/保留
    for theme in themes:
        if theme.get("level") == "主线":
            for a in theme.get("anchors", [])[:4]:
                stock_pool["upgrade_keep"].append({
                    "code": a["code"],
                    "name": a["name"],
                    "reason": f"{theme['name']} {a.get('role', '')}",
                })
        elif theme.get("level") == "次主线":
            for a in theme.get("anchors", [])[:2]:
                stock_pool["new_add"].append({
                    "code": a["code"],
                    "name": a["name"],
                    "reason": f"{theme['name']} {a.get('role', '')}",
                })

    elapsed = time.time() - t_start
    print(f"\n  [postclose] 分析完成，总耗时 {elapsed:.1f}s")

    return {
        "date": date.today().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "env": env,
        "indices": indices,
        "fund_evidence": fund_evidence,
        "flow_sentiment": flow_sentiment,
        "stage": stage,
        "themes": themes,
        "lianban": lianban,
        "rotation": rotation,
        "stock_pool": stock_pool,
        "board_df": board_df,
        "elapsed": round(elapsed, 1),
    }


# ── CLI 独立运行 ───────────────────────────────────────────────

if __name__ == "__main__":
    import json
    result = run_postclose_review()
    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
    else:
        # 简要输出
        print(f"\n📊 市场环境: 涨停{result['env']['zt_count']} 炸板{result['env']['zbgc_count']} 跌停{result['env']['dt_count']}")
        print(f"📈 情绪阶段: {result['stage']['stage']}")
        print(f"🎯 方向归类:")
        for t in result["themes"][:8]:
            print(f"  {t['level']:4s} | {t['name']:<30s} | {t['member_count']}只")
        if result["lianban"]:
            print(f"🔗 连板高度:")
            for lb in result["lianban"][:10]:
                print(f"  {lb['name']:<8s} {lb['lb_count']}连板 {lb['pct']} | {lb['risk_type']}")
