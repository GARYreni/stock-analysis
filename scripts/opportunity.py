"""
opportunity.py - 个股机会发现 v3（合并 star_stocks 评分功能）
基于同花顺技术选股数据 + 东方财富涨跌停数据，发现各类交易机会，
并提供 rank_opportunities() 对候选股进行多维度加权评分排序。

使用示例：
  find_opportunities() -> dict of {category: DataFrame}
  rank_opportunities(top_n=5) -> dict with stars, strong, focus, watch
  get_hot_stocks(limit=20) -> DataFrame
  analyze_limit_up() -> dict
"""

import pandas as pd
import numpy as np
import warnings
import os
import sys
import time
import threading

# WSL 代理（必须在 import akshare 之前清除）
os.environ.pop("http_proxy",  None)
os.environ.pop("https_proxy", None)
os.environ.pop("HTTP_PROXY",  None)
os.environ.pop("HTTPS_PROXY", None)

# ── requests patch: 去掉代理让 akshare 直连 ──────────────────────
for _k in list(os.environ.keys()):
    if 'proxy' in _k.lower():
        os.environ.pop(_k)
try:
    import requests as _req
    _orig_send = _req.Session.send
    def _no_proxy_send(self, request, **kw):
        kw.pop('proxies', None)
        return _orig_send(self, request, **kw)
    _req.Session.send = _no_proxy_send
    _orig_get = _req.api.get
    def _no_proxy_get(url, params=None, **kw):
        kw.pop('proxies', None)
        return _orig_get(url, params=params, **kw)
    _req.api.get = _no_proxy_get
    _orig_post = _req.api.post
    def _no_proxy_post(url, data=None, **kw):
        kw.pop('proxies', None)
        return _orig_post(url, data=data, **kw)
    _req.api.post = _no_proxy_post
except Exception:
    pass

warnings.filterwarnings("ignore")

# ── akshare 懒加载（避免启动时卡顿）──────────────────────────────

_ak = None

def _akshare():
    global _ak
    if _ak is None:
        import akshare as _mod
        _ak = _mod
    return _ak


def _today_str() -> str:
    """返回今日日期字符串（YYYYMMDD 格式，akshare 涨停接口需要此格式）"""
    from datetime import date
    return date.today().strftime("%Y%m%d")


# ── 工具函数 ───────────────────────────────────────────────────

def _fmt_chg(v):
    try:
        v = float(v)
        if np.isnan(v): return "N/A"
        return f"+{v:.2f}%" if v > 0 else f"{v:.2f}%"
    except:
        return "N/A"


def _fmt_turn(v):
    try:
        v = float(v)
        if np.isnan(v): return "N/A"
        return f"{v:.2f}%"
    except:
        return "N/A"


# ── 核心接口 ───────────────────────────────────────────────────

def find_opportunities(max_staleness_minutes: int = 60) -> dict:
    """
    综合扫描所有类型的机会，发现当前可关注个股。
    返回 dict: {分类名: DataFrame}

    优先级排序（从强到弱）：
      🔴 涨停股池（当日最强）
      🟡 强势股池（近期持续强势）
      🟡 昨日涨停（人气延续）
      🟢 创新高（趋势启动）
      🟢 连续上涨（动量延续）
      🟢 持续放量（资金介入）
      🟢 量价齐升（量价配合）
      🟢 向上突破（技术突破）
      🔵 次新股池（新股溢价）
      ⚪ 炸板股池（炸板关注）
      🔵 跌停股池（恐慌情绪）
    """
    results = {}

    # 1. 涨停股池（东方财富）
    try:
        df = _akshare().stock_zt_pool_em(date=_today_str())
        if df is not None and not df.empty:
            df = _clean_zt(df)
            results["涨停股池"] = df
    except Exception as e:
        results["涨停股池"] = pd.DataFrame()

    # 2. 强势股池（东方财富）
    try:
        df = _akshare().stock_zt_pool_strong_em(date=_today_str())
        if df is not None and not df.empty:
            results["强势股池"] = _clean_strong(df)
    except:
        results["强势股池"] = pd.DataFrame()

    # 3. 昨日涨停（东方财富）
    try:
        df = _akshare().stock_zt_pool_previous_em(date=_today_str())
        if df is not None and not df.empty:
            results["昨日涨停"] = _clean_zt(df)
    except:
        results["昨日涨停"] = pd.DataFrame()

    # 4. 次新股池（东方财富）
    try:
        df = _akshare().stock_zt_pool_sub_new_em(date=_today_str())
        if df is not None and not df.empty:
            results["次新股池"] = _clean_zt(df)
    except:
        results["次新股池"] = pd.DataFrame()

    # 5. 炸板股池（东方财富）
    try:
        df = _akshare().stock_zt_pool_zbgc_em(date=_today_str())
        if df is not None and not df.empty:
            results["炸板股池"] = _clean_strong(df)
    except:
        results["炸板股池"] = pd.DataFrame()

    # 6. 跌停股池（东方财富）
    try:
        df = _akshare().stock_zt_pool_dtgc_em(date=_today_str())
        if df is not None and not df.empty:
            results["跌停股池"] = _clean_dt(df)
    except:
        results["跌停股池"] = pd.DataFrame()

    # ── 同花顺技术选股（已禁用：候选过多导致 rank_opportunities 超时）
    # 改用东财涨跌停池作为精选候选（约 100-200 只），由 rank_opportunities
    # 里的多维度评分（动量/资金/技术/财务/舆情）从全市场补充优质标的
    # 启用时建议只选 1-2 个最实用的池，候选上限 500 只
    # if THS_ENABLED:
    #     for name, fn in [
    #         ("量价齐升", lambda: _akshare().stock_rank_ljqs_ths()),
    #         ("持续放量", lambda: _akshare().stock_rank_cxfl_ths()),
    #         ("连续上涨", lambda: _akshare().stock_rank_lxsz_ths()),
    #         ("创新高",   lambda: _akshare().stock_rank_cxg_ths()),
    #         ("向上突破", lambda: _akshare().stock_rank_xstp_ths()),
    #         ("资金流入", lambda: _akshare().stock_rank_zjlj_ths()),
    #         ("连续下跌", lambda: _akshare().stock_rank_lxxd_ths()),
    #         ("创新低",   lambda: _akshare().stock_rank_cxd_ths()),
    #         ("持续缩量", lambda: _akshare().stock_rank_cxsl_ths()),
    #         ("量价齐跌", lambda: _akshare().stock_rank_ljqd_ths()),
    #         ("向下突破", lambda: _akshare().stock_rank_xxtp_ths()),
    #     ]:
    #         try:
    #             df = fn()
    #             if df is not None and not df.empty:
    #                 results[name] = _clean_tech(df)
    #         except:
    #             pass

    # 清理空结果
    return {k: v for k, v in results.items() if v is not None and not v.empty}


# ── 数据清洗 ───────────────────────────────────────────────────

def _clean_zt(df: pd.DataFrame) -> pd.DataFrame:
    """清洗涨停/跌停股池数据（适配东方财富列名）"""
    # 东财返回列名：名称、代码、涨跌幅、连板数、流通市值、总市值、换手率、成交额、所属行业
    # 注意：东财列名是"名称"不是"简称"，"流通市值"/"总市值"不带括号
    keep = []
    for col in df.columns:
        if any(k in col for k in ["代码", "名称", "简称", "涨跌幅", "换手率", "流通", "市值", "连板", "成交额", "所属行业"]):
            keep.append(col)
    if keep:
        df = df[keep].copy()

    # 统一列名（东财用"名称"，同花顺用"简称"；东财"流通市值"不带括号）
    rename = {}
    for col in df.columns:
        if "涨跌幅" in col and "涨跌幅(%)" not in rename:
            rename[col] = "涨跌幅(%)"
        elif "换手率" in col and "换手率(%)" not in rename:
            rename[col] = "换手率(%)"
        elif "流通市值" in col and "流通市值(亿)" not in rename:
            rename[col] = "流通市值(亿)"
        elif "总市值" in col and "总市值(亿)" not in rename:
            rename[col] = "总市值(亿)"
        elif "成交额" in col and "成交额(元)" not in rename:
            rename[col] = "成交额(元)"
        elif "所属行业" in col:
            rename[col] = "所属行业"

    if rename:
        seen = set()
        final_rename = {}
        for col in df.columns:
            target = rename.get(col, col)
            if target not in seen:
                seen.add(target)
                if target != col:
                    final_rename[col] = target
        df = df.rename(columns=final_rename)

    # 统一代码列
    for col in ["代码", "股票代码"]:
        if col in df.columns:
            df = df.rename(columns={col: "代码"})
            break

    # 统一名称列
    for col in ["名称", "简称", "股票简称"]:
        if col in df.columns:
            df = df.rename(columns={col: "名称"})
            break

    # 清理代码格式
    if "代码" in df.columns:
        df["代码"] = df["代码"].astype(str).str.zfill(6)

    return df.reset_index(drop=True)


def _clean_strong(df: pd.DataFrame) -> pd.DataFrame:
    """清洗强势股/炸板数据"""
    return _clean_zt(df)


def _clean_dt(df: pd.DataFrame) -> pd.DataFrame:
    """清洗跌停数据"""
    return _clean_zt(df)


def _clean_tech(df: pd.DataFrame) -> pd.DataFrame:
    """清洗同花顺技术选股数据"""
    # 同花顺技术选股字段：序号、股票代码、股票简称、涨跌幅、换手率、最新价、前期高点...
    rename = {}
    for col in df.columns:
        cn = col.lower()
        if "代码" in col and col not in rename:
            rename[col] = "代码"
        elif "简称" in col and col not in rename:
            rename[col] = "名称"
        elif "涨跌幅" in col:
            rename[col] = "涨跌幅(%)"
        elif "换手率" in col:
            rename[col] = "换手率(%)"
        elif "最新价" in col or "收盘" in col or "最新" in col:
            rename[col] = "最新价"
        elif "成交量" in col:
            rename[col] = "成交量"
        elif "成交额" in col:
            rename[col] = "成交额"
        elif "连涨" in col:
            rename[col] = "连涨天数"
        elif "阶段" in col:
            rename[col] = "阶段涨幅"
        elif "量价" in col:
            rename[col] = "量价齐升天数"
        elif "前期" in col and "高点" in col:
            rename[col] = "前期高点"
        elif "前期" in col and "低" in col:
            rename[col] = "前期低点"

    df = df.rename(columns=rename)

    # 统一代码格式
    if "代码" in df.columns:
        df["代码"] = df["代码"].astype(str).str.zfill(6)

    # 去掉序号列
    for col in ["序号"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    return df.reset_index(drop=True)


# ── 便捷接口 ───────────────────────────────────────────────────

def get_hot_stocks(limit: int = 20) -> pd.DataFrame:
    """
    返回当前最热的股票（涨停股 + 强势股 + 量价齐升优先合并）
    """
    all_hot = []
    opp = find_opportunities()

    priority_order = ["涨停股池", "强势股池", "昨日涨停", "次新股池",
                      "量价齐升", "持续放量", "连续上涨", "创新高"]

    seen = set()
    for cat in priority_order:
        if cat in opp and not opp[cat].empty:
            df = opp[cat].copy()
            if "代码" in df.columns and "名称" in df.columns:
                for _, row in df.iterrows():
                    code = str(row.get("代码", ""))
                    if code not in seen:
                        seen.add(code)
                        row_data = row.to_dict()
                        row_data["_来源分类"] = cat
                        all_hot.append(row_data)
                        if len(all_hot) >= limit:
                            break
        if len(all_hot) >= limit:
            break

    if not all_hot:
        return pd.DataFrame()

    result = pd.DataFrame(all_hot)
    if "涨跌幅(%)" in result.columns:
        result = result.sort_values("涨跌幅(%)", ascending=False)
    return result.reset_index(drop=True)


def analyze_limit_up() -> dict:
    """
    专门分析当日涨停情况：涨停数量、连板情况、热门涨停板块分布
    """
    opp = find_opportunities()
    zt_df = opp.get("涨停股池", pd.DataFrame())

    if zt_df.empty:
        return {
            "zt_count": 0,
            "lianban_stocks": [],
            "hot_boards": [],
            "zbgc_count": 0,
            "dt_count": 0,
            "summary": "今日涨停数据暂不可用",
        }

    # 找连板股（字段含"连板"或"连续"）
    lianban_cols = [c for c in zt_df.columns if "连板" in c or "连续" in c]
    lianban_stocks = []
    if lianban_cols:
        for _, row in zt_df.iterrows():
            for col in lianban_cols:
                val = row.get(col)
                try:
                    if float(val) >= 2:
                        lianban_stocks.append({
                            "代码": row.get("代码", ""),
                            "名称": row.get("名称", ""),
                            "连板数": val,
                            "涨跌幅": row.get("涨跌幅(%)", row.get("涨跌幅", "N/A")),
                        })
                except:
                    pass

    # 炸板统计
    zbgc_count = 0
    dt_count = 0
    if "炸板股池" in opp and not opp["炸板股池"].empty:
        zbgc_count = len(opp["炸板股池"])
    if "跌停股池" in opp and not opp["跌停股池"].empty:
        dt_count = len(opp["跌停股池"])

    return {
        "zt_count": len(zt_df),
        "lianban_stocks": lianban_stocks,
        "zbgc_count": zbgc_count,
        "dt_count": dt_count,
        "zt_df": zt_df,
        "summary": f"涨停 {len(zt_df)} 只 | 炸板 {zbgc_count} | 跌停 {dt_count} | 连板 {len(lianban_stocks)}"
    }


def summarize_opportunities(opp: dict = None) -> str:
    """
    生成机会摘要文本（用于报告）
    """
    if opp is None:
        opp = find_opportunities()

    lines = []
    priority_order = [
        ("🔴 涨停股池", "涨停股池"),
        ("🟡 强势股池", "强势股池"),
        ("🟡 昨日涨停", "昨日涨停"),
        ("🟢 量价齐升", "量价齐升"),
        ("🟢 持续放量", "持续放量"),
        ("🟢 连续上涨", "连续上涨"),
        ("🟢 创新高", "创新高"),
        ("🟢 向上突破", "向上突破"),
        ("🔵 次新股池", "次新股池"),
        ("⚪ 炸板股池", "炸板股池"),
        ("🔵 跌停股池", "跌停股池"),
    ]

    for emoji, key in priority_order:
        if key in opp and not opp[key].empty:
            n = len(opp[key])
            # 取前3只代表性股票
            top3 = []
            df_slice = opp[key]

            # 安全地获取涨跌幅列（可能存在重复列名）
            chg_col = None
            for cn in ["涨跌幅(%)", "涨跌幅", "涨跌幅\n(%)"]:
                if cn in df_slice.columns:
                    chg_col = cn
                    break

            if chg_col is not None:
                try:
                    numeric_col = pd.to_numeric(df_slice[chg_col], errors="coerce")
                    top3_idx = numeric_col.nlargest(3).dropna().index
                    top3_rows = df_slice.loc[top3_idx]
                except Exception:
                    top3_rows = df_slice.head(3)
            else:
                top3_rows = df_slice.head(3)

            for _, r in top3_rows.iterrows():
                name = r.get("名称") or r.get("股票简称") or "?"
                code = r.get("代码") or "?"
                chg_val = r[chg_col] if chg_col else None
                # 处理：chg_val可能是Series/标量/NaN
                try:
                    if chg_val is not None and not (isinstance(chg_val, float) and pd.isna(chg_val)):
                        chg_fmt = _fmt_chg(chg_val)
                        top3.append(f"{name}({code}){chg_fmt}")
                    else:
                        top3.append(f"{name}({code})")
                except Exception:
                    top3.append(f"{name}({code})")

            lines.append(f"{emoji} **{key}** ({n}只): {', '.join(top3)}")

    if not lines:
        return "⚠️ 暂未发现明显交易机会"

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# 以下为合并自 star_stocks.py 的荐股评分功能
# ═══════════════════════════════════════════════════════════════════════

def _sf(v, default=np.nan):
    try:
        f = float(v)
        return f if not np.isnan(f) else default
    except:
        return default

def _fmt_cap(v):
    try:
        v = float(v)
        if np.isnan(v): return "N/A"
        if v >= 1e8: return f"{v/1e8:.1f}亿"
        if v >= 1e6: return f"{v/1e6:.1f}万"
        return f"{v:.0f}"
    except:
        return "N/A"

def _safe_col(df: pd.DataFrame, *names) -> str:
    for n in names:
        if n in df.columns: return n
    return None

# ── 模块懒加载（避免循环依赖）─────────────────────────────

def _import_m(mod_name: str):
    try:
        return __import__(mod_name, fromlist=[''])
    except ImportError:
        return None

_FF = None
def _load_ff():
    global _FF
    if _FF is None:
        _FF = _import_m('fund_flow') or _import_m('scripts.fund_flow')
    return _FF

_SC = None
def _load_scraper():
    global _SC
    if _SC is None:
        _SC = _import_m('scraper') or _import_m('scripts.scraper')
    return _SC

_LHB = None
def _load_lhb():
    global _LHB
    if _LHB is None:
        _LHB = _import_m('lhb') or _import_m('scripts.lhb')
    return _LHB

_NEWS = None
def _load_news():
    global _NEWS
    if _NEWS is None:
        _NEWS = _import_m('news_search') or _import_m('scripts.news_search')
    return _NEWS

# ── 财务数据缓存（8秒超时）──────────────────────────────

_financial_cache: dict = {}

def _load_financial_batch(candidate_codes: set) -> dict:
    global _financial_cache
    _financial_cache = {}
    try:
        import akshare as ak
        result_holder = [None]
        exc_holder = [None]
        def _fetch():
            try:
                result_holder[0] = ak.stock_financial_analysis_indicator_em(symbol="", start_year="2023")
            except Exception as e:
                exc_holder[0] = e
        t = threading.Thread(target=_fetch, daemon=True)
        t.start()
        t.join(timeout=8)
        if t.is_alive() or exc_holder[0]:
            return _financial_cache
        df = result_holder[0]
        if df is None or df.empty:
            return _financial_cache
        code_col = next((c for c in df.columns if "代码" in str(c)), None)
        if not code_col:
            return _financial_cache
        df[code_col] = df[code_col].astype(str).str.zfill(6)
        df = df[df[code_col].isin(candidate_codes)]
        date_col = next((c for c in df.columns if "日期" in str(c) or "报告期" in str(c)), None)
        if date_col:
            df = df.sort_values(date_col, ascending=False).drop_duplicates(subset=[code_col], keep="first")
        _financial_cache = {row[code_col]: row.to_dict() for _, row in df.iterrows()}
    except:
        pass
    return _financial_cache

# ── 各维度评分函数 ───────────────────────────────────────

def _score_momentum(code: str, opp: dict) -> tuple:
    score = 0.0; tags = []
    positive = {
        "涨停股池": 3.0, "强势股池": 2.5, "昨日涨停": 2.0, "次新股池": 1.5,
        "量价齐升": 2.0, "持续放量": 1.5, "连续上涨": 1.5, "创新高": 2.0,
        "向上突破": 1.5, "炸板股池": 1.0,
    }
    count = 0
    for cat, weight in positive.items():
        if cat in opp:
            df = opp[cat]
            if not df.empty and "代码" in df.columns:
                codes = df["代码"].astype(str).str.zfill(6)
                if code.zfill(6) in codes.values:
                    score += weight; count += 1; tags.append(cat)
    if count >= 3:
        score += 1.0; tags.append("多重确认")
    return min(score, 5.0), tags

def _score_fund_flow_fast(code: str, ff_mod, ind_flow: pd.DataFrame, hsgt: pd.DataFrame) -> tuple:
    score = 0.0; tags = []
    if hsgt is not None and not hsgt.empty:
        hsgt_codes = hsgt.get("代码", pd.Series(dtype=str)).astype(str).str.zfill(6)
        if code.zfill(6) in hsgt_codes.values:
            row = hsgt[hsgt_codes == code.zfill(6)].iloc[0]
            pct_col = _safe_col(hsgt, "持股比例", "持股比例(%)", "持股_占流通股比")
            if pct_col:
                pct = _sf(row.get(pct_col, 0))
                if pct > 3: score += 2.0; tags.append(f"北向{pct:.1f}%")
                elif pct > 1: score += 1.0; tags.append(f"北向{pct:.1f}%")
    if ind_flow is not None and not ind_flow.empty:
        top5_inds = ind_flow.head(5)["行业名称"].tolist() if "行业名称" in ind_flow.columns else []
        stock_ind = globals().get("_ind_stock_map", {}).get(code, "")
        if stock_ind in top5_inds:
            score += 1.0; tags.append("资金热捧")
    return min(score, 3.0), tags

def _score_technical(code: str, opp: dict) -> tuple:
    score = 0.0; tags = []
    tech = {"创新高": 2.0, "量价齐升": 1.5, "持续放量": 1.5, "连续上涨": 1.0, "向上突破": 1.0}
    for cat, weight in tech.items():
        if cat in opp:
            df = opp[cat]
            if not df.empty and "代码" in df.columns:
                codes = df["代码"].astype(str).str.zfill(6)
                if code.zfill(6) in codes.values:
                    score += weight; tags.append(cat)
    return min(score, 3.0), tags

def _score_market(realtime_df: pd.DataFrame, code: str) -> tuple:
    score = 0.0; tags = []
    if realtime_df is None or realtime_df.empty:
        return 0.0, []
    code_col = _safe_col(realtime_df, "代码", "code")
    if not code_col:
        return 0.0, []
    df = realtime_df.copy()
    df["_code_bare"] = df[code_col].astype(str).str[-6:]
    df = df[df["_code_bare"] == code.zfill(6)]
    if df.empty:
        return 0.0, []
    row = df.iloc[0]
    cap_col = _safe_col(realtime_df, "流通市值(亿)", "流通市值", "流通市值(万元)", "流通市值(元)")
    if cap_col:
        cap_raw = _sf(row.get(cap_col, np.nan))
        if "万元" in str(cap_col): cap = cap_raw / 10000 if cap_raw > 0 else np.nan
        elif "元" in str(cap_col): cap = cap_raw / 1e8 if cap_raw > 0 else np.nan
        else: cap = cap_raw
        if not np.isnan(cap) and 50 <= cap <= 500: score += 1.5; tags.append(f"{cap:.0f}亿")
        elif not np.isnan(cap) and cap > 0: score += 0.5; tags.append(f"{cap:.0f}亿")
    turn_col = _safe_col(realtime_df, "换手率(%)", "换手率")
    if turn_col:
        turn = _sf(row.get(turn_col, 0))
        if turn > 3: score += 0.5; tags.append(f"换手{turn:.1f}%")
        elif turn > 0: score += 0.25; tags.append(f"换手{turn:.1f}%")
    name_col = _safe_col(realtime_df, "名称", "股票名称")
    if name_col:
        name = str(row.get(name_col, ""))
        if not name.startswith(("ST", "*ST", "S*ST", "SST")):
            score += 0.5; tags.append("非ST")
        else:
            tags.append("ST风险")
    return min(score, 3.0), tags

def _score_lhb(code: str, lhb_result: dict) -> tuple:
    score = 0.0; tags = []
    if not lhb_result:
        return 0.0, []
    hot = lhb_result.get("hot_stocks", [])
    for item in hot:
        if str(item.get("代码", "")).zfill(6) == code.zfill(6):
            score += 1.5; tags.append(f"上榜{item.get('上榜次数',1)}次"); break
    recent = lhb_result.get("recent_list", [])
    for record in recent:
        if str(record.get("代码", "")).zfill(6) == code.zfill(6):
            buy = record.get("买方席位", record.get("机构买入", ""))
            if buy and ("机构" in str(buy) or "专用" in str(buy)):
                score += 1.0; tags.append("机构买入"); break
    return min(score, 2.0), tags

def _score_financial(code: str) -> tuple:
    score = 0.0; tags = []
    if code not in _financial_cache:
        return 0.0, []
    row = _financial_cache[code]
    for col in ["净资产收益率(%)", "ROE(%)", "净资产收益率", "ROE"]:
        if col in row and row[col] is not None:
            roe = _sf(row.get(col, 0))
            if not np.isnan(roe) and roe != 0:
                if roe > 15: score += 1.5; tags.append(f"ROE{roe:.1f}%"); break
                elif roe > 10: score += 1.0; tags.append(f"ROE{roe:.1f}%"); break
                elif roe > 5: score += 0.5; tags.append(f"ROE{roe:.1f}%"); break
    for col in ["营收增长率(%)", "营业收入增长率", "营收增长率"]:
        if col in row and row[col] is not None:
            rev = _sf(row.get(col, 0))
            if not np.isnan(rev) and rev != 0:
                if rev > 20: score += 1.0; tags.append(f"营收+{rev:.0f}%"); break
                elif rev > 10: score += 0.5; tags.append(f"营收+{rev:.0f}%"); break
    for col in ["销售毛利率(%)", "毛利率", "销售毛利率"]:
        if col in row and row[col] is not None:
            gp = _sf(row.get(col, 0))
            if not np.isnan(gp) and gp > 0: tags.append(f"毛利率{gp:.1f}%"); break
    return min(score, 3.0), tags

def _score_sentiment(code: str, news_mod, name: str) -> tuple:
    score = 0.0; tags = []
    if news_mod is None:
        return 0.0, []
    try:
        search_fn = getattr(news_mod, 'search_stock_news', None)
        if search_fn is None:
            return 0.0, []
        results = search_fn(code=code, name=name, limit=10)
        if not results:
            return 0.5, ["无负面舆情"]
        pos = sum(1 for r in results if r.get("sentiment") == "positive")
        neg = sum(1 for r in results if r.get("sentiment") == "negative")
        if pos >= 3: score = 2.0; tags.append(f"正面+{pos}篇")
        elif pos == 2: score = 1.5; tags.append(f"正面+{pos}篇")
        elif pos == 1: score = 1.0; tags.append("正面+1")
        if neg == 0: score += 0.5; tags.append("无负面舆情")
        elif neg >= 3: score = max(0, score - 1.0); tags.append(f"负面-{neg}篇")
    except:
        pass
    return min(score, 2.0), tags

def _score_board(code: str, hot_boards: dict) -> tuple:
    score = 0.0; tags = []
    if not hot_boards or hot_boards.get("混合", pd.DataFrame()).empty:
        return 0.0, []
    mixed = hot_boards["混合"]
    bname_col = None
    for cn in ["板块名称", "名称", "行业名称", "概念名称"]:
        if cn in mixed.columns:
            bname_col = cn; break
    if not bname_col:
        return 0.0, []
    top10 = set(mixed.head(10)[bname_col].astype(str).tolist())
    top20 = set(mixed.head(20)[bname_col].astype(str).tolist())
    top30 = set(mixed.head(30)[bname_col].astype(str).tolist())
    stock_board = globals().get("_ind_stock_map", {}).get(code, "")
    if not stock_board:
        return 0.0, []
    for bn in top10:
        if bn in str(stock_board) or str(stock_board) in bn:
            return 2.0, [f"热门TOP10:{bn[:6]}"]
    for bn in top20:
        if bn in str(stock_board) or str(stock_board) in bn:
            return 1.0, [f"热门TOP20:{bn[:6]}"]
    for bn in top30:
        if bn in str(stock_board) or str(stock_board) in bn:
            return 0.5, [f"跟随板块:{bn[:6]}"]
    return 0.0, []


# ── 核心荐股函数 ────────────────────────────────────────

def rank_opportunities(top_n: int = 5) -> pd.DataFrame:
    """
    对 find_opportunities() 所有候选股进行多维度加权评分，返回 Top N。
    评分维度：动量 / 资金 / 技术 / 市值 / 龙虎榜 / 板块 / 财务 / 舆情
    """
    import time as _time
    _t0 = _time.time()
    all_codes: dict = {}
    print(f"  [rank_opportunities] 1/5 find_opportunities...", flush=True)
    # 从 opportunity 候选股池收集
    opp = find_opportunities()
    for cat, df in opp.items():
        if df is not None and not df.empty and "代码" in df.columns:
            for _, row in df.iterrows():
                c = str(row.get("代码", "")).zfill(6)
                if c and c != "000000":
                    all_codes[c] = {"name": row.get("名称", ""), "code": c}

    # 从北向持股补充
    print(f"  [rank_opportunities] 2/5 北向+资金流...", flush=True)
    ff_mod = _load_ff()
    hsgt = pd.DataFrame()
    if ff_mod and hasattr(ff_mod, 'get_hsgt_hold'):
        try: hsgt = ff_mod.get_hsgt_hold()
        except: pass
    if not hsgt.empty and "代码" in hsgt.columns:
        for _, row in hsgt.iterrows():
            c = str(row.get("代码", "")).zfill(6)
            if c and c not in all_codes:
                all_codes[c] = {"name": row.get("名称", ""), "code": c}

    # 加载辅助数据
    print(f"  [rank_opportunities] 3/5 fetch_data+龙虎榜+新闻...", flush=True)
    ind_flow = pd.DataFrame()
    hot_boards: dict = {}
    if ff_mod:
        if hasattr(ff_mod, 'get_industry_flow'):
            try: ind_flow = ff_mod.get_industry_flow()
            except: pass
        if hasattr(ff_mod, 'get_hot_boards'):
            try: hot_boards = ff_mod.get_hot_boards(n=30)
            except: pass

    realtime_df = pd.DataFrame(); industry_map = {}
    scraper_mod = _load_scraper()
    if scraper_mod and hasattr(scraper_mod, 'fetch_data'):
        try:
            res = scraper_mod.fetch_data(use_cache=True)
            if res: realtime_df, _, industry_map = res
        except: pass

    # 构建股票→行业映射（无前缀）
    _ind_stock_map_raw = {}
    for code, bname in industry_map.items():
        if not bname or str(bname) in ("nan", "None", ""):
            continue
        bare = code[2:] if code.startswith(("sz", "sh")) and len(code) == 8 else code
        if bare not in _ind_stock_map_raw:
            _ind_stock_map_raw[bare] = bname
    global _ind_stock_map
    _ind_stock_map = _ind_stock_map_raw

    lhb_result = {}
    lhb_mod = _load_lhb()
    if lhb_mod and hasattr(lhb_mod, 'analyze_lhb'):
        try: lhb_result = lhb_mod.analyze_lhb(days=10)
        except: pass

    news_mod = _load_news()
    news_available = news_mod is not None and hasattr(news_mod, 'search_stock_news')
    _load_financial_batch(set(all_codes.keys()))

    print(f"  [rank_opportunities] 4/5 评分循环 ({len(all_codes)} 只候选)...", flush=True)
    scores = []
    for code, info in all_codes.items():
        name = info["name"]
        m_s, m_t = _score_momentum(code, opp)
        f_s, f_t = _score_fund_flow_fast(code, ff_mod, ind_flow, hsgt)
        t_s, t_t = _score_technical(code, opp)
        mk_s, mk_t = _score_market(realtime_df, code)
        l_s, l_t = _score_lhb(code, lhb_result)
        b_s, b_t = _score_board(code, hot_boards)
        fi_s, fi_t = _score_financial(code)
        s_s, s_t = _score_sentiment(code, news_mod, name) if news_available else (0.0, [])
        # 加权总评分
        weighted = (m_s*1.5 + f_s*1.2 + t_s*1.2 + fi_s*1.0 + s_s*1.0 + b_s*1.0 + l_s*0.8 + mk_s*0.5)
        high = [m_s >= 2.0, f_s >= 1.5, t_s >= 1.5, fi_s >= 1.5]
        resonance = 2.0 if sum(high) >= 3 else (1.0 if sum(high) >= 2 else 0.0)
        total = weighted + resonance
        # 实时行情补充
        price, chg, tr, cap = "", "", "", ""
        if not realtime_df.empty:
            c_col = _safe_col(realtime_df, "代码", "code")
            if c_col:
                rt2 = realtime_df.copy()
                rt2["_code_bare"] = rt2[c_col].astype(str).str[-6:]
                sub = rt2[rt2["_code_bare"] == code.zfill(6)]
                if not sub.empty:
                    r = sub.iloc[0]
                    p_col = _safe_col(realtime_df, "最新价", "现价", "收盘")
                    chg_col2 = _safe_col(realtime_df, "涨跌幅(%)", "涨跌幅", "涨跌额")
                    tr_col2 = _safe_col(realtime_df, "换手率(%)", "换手率")
                    cp_col2 = _safe_col(realtime_df, "流通市值(亿)", "流通市值", "流通市值(万元)")
                    price = f"{_sf(r.get(p_col, np.nan)):.2f}" if not np.isnan(_sf(r.get(p_col, np.nan))) else ""
                    try:
                        chg_v = float(r.get(chg_col2, np.nan))
                        chg = f"+{chg_v:.2f}%" if chg_v > 0 else f"{chg_v:.2f}%"
                    except:
                        chg = ""
                    tr = f"{_sf(r.get(tr_col2, 0)):.2f}%"
                    cap = _fmt_cap(_sf(r.get(cp_col2, 0)))
        scores.append({
            "代码": code, "名称": name, "综合评分": round(total, 2),
            "动量分": round(m_s, 1), "资金分": round(f_s, 1), "技术分": round(t_s, 1),
            "市值分": round(mk_s, 1), "龙虎分": round(l_s, 1), "板块分": round(b_s, 1),
            "财务分": round(fi_s, 1), "舆情分": round(s_s, 1),
            "最新价": price, "涨跌幅": chg, "换手率": tr, "流通市值": cap,
            "机会标签": " | ".join(m_t),
            "资金标签": " | ".join(f_t), "技术标签": " | ".join(t_t),
            "板块标签": " | ".join(b_t), "财务标签": " | ".join(fi_t), "舆情标签": " | ".join(s_t),
            "推荐理由": "顶级精选" if total >= 14.0 else "高质量关注" if total >= 9.0 else "潜在机会",
        })
    if not scores:
        return pd.DataFrame()
    print(f"  [rank_opportunities] 5/5 排序输出... ({_time.time()-_t0:.1f}s)", flush=True)
    return pd.DataFrame(scores).sort_values("综合评分", ascending=False).reset_index(drop=True).head(top_n)


def get_recommend_report(top_n: int = 5) -> dict:
    """
    完整荐股报告（包含所有数据），供 gen_report() 生成 Markdown。
    返回 dict: stars, strong, focus, watch, board_dist, summary, elapsed
    """
    # 评分核心：K线数据全部并发获取（避免串行超时）
    MAX_SCORING_WORKERS = 20
    t0 = time.time()
    _result = [None]
    def _scan():
        try:
            _result[0] = rank_opportunities(top_n=top_n)
        except Exception as e:
            _result[0] = e
    t = threading.Thread(target=_scan, daemon=True)
    t.start()
    t.join(timeout=300)   # 评分需要 fetch_data(4964只)+K线，抓取较慢，300s足够
    elapsed = time.time() - t0

    if t.is_alive():
        return {
            "stars": [], "count": 0, "elapsed": round(elapsed, 1),
            "summary": f"评分超时（>{300}s），请检查网络后重试",
            "board_recommendations": {}, "strong": [], "focus": [], "watch": [],
        }
    result = _result[0]
    if isinstance(result, Exception):
        return {
            "stars": [], "count": 0, "elapsed": round(elapsed, 1),
            "summary": f"扫描出错: {result}",
            "board_recommendations": {}, "strong": [], "focus": [], "watch": [],
        }

    stars = result
    if stars.empty:
        return {
            "stars": [], "count": 0, "elapsed": round(elapsed, 1),
            "summary": "今日暂未发现星标股票", "board_recommendations": {},
            "strong": [], "focus": [], "watch": [],
        }

    strong = stars[stars["综合评分"] >= 14.0]
    focus  = stars[(stars["综合评分"] >= 9.0) & (stars["综合评分"] < 14.0)]
    watch  = stars[(stars["综合评分"] >= 4.0) & (stars["综合评分"] < 9.0)]

    board_dist = {}
    for _, row in stars.iterrows():
        ot = row.get("机会标签", "")
        if ot:
            for t2 in ot.split("|"):
                t2 = t2.strip()
                if t2:
                    board_dist[t2] = board_dist.get(t2, 0) + 1

    parts = [f"今日共发现 **{len(stars)} 只** 候选股票"]
    if not strong.empty:
        parts.append(f"顶级精选 {len(strong)} 只：{', '.join(strong['名称'].head(5).tolist())}")
    if not focus.empty:
        parts.append(f"高质量关注 {len(focus)} 只：{', '.join(focus['名称'].head(5).tolist())}")

    # 板块推荐（15秒超时，从 board_analysis 加载）
    board_recs = {}
    try:
        ba = _import_m('board_analysis')
        if ba and hasattr(ba, 'get_board_recommendations'):
            _br = [{}]
            def _fetch_boards():
                try: _br[0] = ba.get_board_recommendations(n_per_board=3, top_boards=15)
                except: pass
            tb = threading.Thread(target=_fetch_boards, daemon=True)
            tb.start()
            tb.join(timeout=15)
            if not tb.is_alive():
                board_recs = _br[0]
    except:
        pass

    return {
        "stars": stars.to_dict("records"),
        "count": len(stars),
        "strong": strong.to_dict("records"),
        "focus": focus.to_dict("records"),
        "watch": watch.to_dict("records"),
        "board_dist": sorted(board_dist.items(), key=lambda x: -x[1])[:10],
        "board_recommendations": board_recs,
        "summary": " | ".join(parts),
        "elapsed": round(elapsed, 1),
    }
