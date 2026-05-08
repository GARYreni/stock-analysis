"""
report_html.py - 收盘复盘 HTML 报告生成器
==========================================
接收 postclose_review.run_postclose_review() 返回的结构化数据，
生成精美的响应式 HTML 收盘复盘报告（可直接部署到 Netlify）。

使用方式:
  from postclose_review import run_postclose_review
  from report_html import gen_postclose_html

  data = run_postclose_review()
  html = gen_postclose_html(data)
  with open("收盘复盘_20260507.html", "w", encoding="utf-8") as f:
      f.write(html)
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
import json


# ── CSS 样式（复用 Netlify 页面设计）──────────────────────────

CSS = """<style>
:root {
  --paper:#fffdf8; --ink:#1f2937; --muted:#64748b; --line:#e5e0d6;
  --soft:#fff7ed; --accent:#b45309; --accent2:#7c2d12;
  --red:#b91c1c; --green:#047857; --blue:#1d4ed8;
}
* { box-sizing:border-box; }
html { margin:0; background:#ece7dd; }
body {
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif;
  color:var(--ink); font-size:15px; line-height:1.68;
}
.page { width:min(100%, 470px); margin:0 auto; padding:12px 10px 28px; background:var(--paper); min-height:100vh; }
.cover { padding:20px 18px 18px; border-radius:16px; background:linear-gradient(135deg,#263342 0%,#5b4636 52%,#b45309 100%); color:#fff; box-shadow:0 10px 24px rgba(36,52,71,.16); }
.cover .eyebrow { font-size:11px; opacity:.82; letter-spacing:.06em; }
h1 { margin:7px 0 8px; font-size:26px; line-height:1.2; letter-spacing:0; }
.cover p { margin:0; color:rgba(255,255,255,.9); font-size:14px; }
.summary-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:12px 0 6px; }
.summary-card { min-height:108px; border:1px solid var(--line); border-radius:12px; padding:10px 11px; background:#fff; }
.summary-card span { display:block; color:var(--accent); font-weight:800; font-size:12px; margin-bottom:5px; }
.summary-card b { display:block; color:#111827; font-size:15px; line-height:1.3; margin-bottom:5px; }
.summary-card em { display:block; color:var(--muted); font-style:normal; font-size:12px; line-height:1.42; }
h2 { margin:22px 0 10px; padding:9px 11px; border-left:5px solid var(--accent); border-radius:9px; background:#f8efe3; color:#111827; font-size:18px; line-height:1.34; break-after:avoid; }
h3 { margin:18px 0 9px; padding:0 0 6px; border-bottom:1px solid var(--line); color:#253041; font-size:16px; break-after:avoid; }
p { margin:8px 2px 10px; }
ul { margin:8px 0 13px; padding:0; list-style:none; display:grid; gap:7px; }
li { position:relative; padding:9px 10px 9px 17px; border:1px solid #eee6d8; border-radius:10px; background:#fffaf1; }
li::before { content:""; position:absolute; left:8px; top:18px; width:5px; height:5px; border-radius:50%; background:var(--accent); }
strong { color:#111827; }
.table-wrap { margin:10px 0 14px; }
table { width:100%; border-collapse:separate; border-spacing:0 8px; font-size:13px; line-height:1.45; }
thead { display:none; }
tr { display:block; border:1px solid var(--line); border-radius:12px; background:#fff; overflow:hidden; }
td { display:grid; grid-template-columns:86px minmax(0,1fr); gap:8px; padding:7px 9px; border-bottom:1px solid #f0e7d8; vertical-align:top; }
td:last-child { border-bottom:0; }
td::before { content:attr(data-label); color:var(--accent2); font-weight:800; font-size:12px; }
.pct-up, .money-in { color:var(--red); font-weight:800; }
.pct-down, .money-out { color:var(--green); font-weight:800; }
.footer { margin-top:22px; padding-top:12px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; text-align:center; }
.topnav { position:sticky; top:0; z-index:100; background:var(--paper); border-bottom:1px solid var(--line); padding:6px 4px; margin:-12px -10px 10px; display:flex; flex-wrap:wrap; gap:4px; overflow-x:auto; }
.topnav a { flex-shrink:0; padding:4px 10px; border-radius:14px; background:#f3eadc; color:var(--ink); text-decoration:none; font-size:12px; white-space:nowrap; }
.topnav a:hover { background:var(--accent); color:#fff; }
@media (min-width:760px) {
  .topnav { margin:-30px -38px 16px; padding:8px 34px; }
  .topnav a { font-size:13px; padding:5px 14px; }
}
.board-section { border-left:3px solid var(--line); padding-left:10px; margin-bottom:14px; }
.board-section.main { border-left-color:var(--red); background:linear-gradient(90deg,#fef2f2 0%,transparent 100%);padding:8px 10px 8px 12px;border-radius:0 8px 8px 0; }
.board-section.sub { border-left-color:var(--accent); background:linear-gradient(90deg,#fff7ed 0%,transparent 100%);padding:8px 10px 8px 12px;border-radius:0 8px 8px 0; }
.board-section.alive { border-left-color:var(--blue); }
.board-section.other { border-left-color:var(--muted); }
.dashboard { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:14px 0 8px; }
.dashboard .kpi { text-align:center; padding:10px 6px; border-radius:10px; background:#fff; border:1px solid var(--line); }
.dashboard .kpi b { display:block; font-size:22px; color:#111827; }
.dashboard .kpi em { display:block; font-size:11px; color:var(--muted); font-style:normal; margin-top:2px; }
.dashboard .kpi.up b { color:var(--red); }
.dashboard .kpi.down b { color:var(--green); }
.collapse-toggle { cursor:pointer; color:var(--blue); font-size:12px; margin-left:6px; }
.collapse-content { max-height:60px; overflow:hidden; transition:max-height .3s; }
.collapse-content.open { max-height:none; }
@media (max-width:760px) {
  body { font-size:14px; overflow-x:hidden; }
  .page { width:100%; padding:10px 8px 20px; }
  h1 { font-size:22px; }
  h2 { font-size:16px; }
  h3 { font-size:14px; }
  .dashboard { grid-template-columns:repeat(2,1fr); gap:6px; }
  .dashboard .kpi { padding:8px 4px; }
  .dashboard .kpi b { font-size:18px; }
  .summary-grid { grid-template-columns:1fr 1fr; gap:6px; }
  .summary-card { min-height:auto; padding:8px 9px; }
  .summary-card b { font-size:13px; }
  .summary-card em { font-size:11px; }
  .cover { padding:16px 14px 14px; }
  .cover p { font-size:13px; }
  .table-wrap { margin:8px -8px 12px; border-radius:0; }
  table { font-size:12px; }
  td { padding:6px 7px; }
  li { padding:7px 8px 7px 15px; font-size:13px; }
  p { font-size:13px; }
  .collapse-toggle { font-size:11px; }
  .chart-row { grid-template-columns:1fr; }
}
@media (min-width:760px) {
  body { font-size:15px; }
  .page { width:min(960px, calc(100vw - 32px)); padding:30px 38px 42px; box-shadow:0 18px 55px rgba(36,52,71,.10); }
  .cover { padding:26px 30px 24px; }
  h1 { font-size:34px; }
  .cover p { font-size:15px; }
  .summary-grid { grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0 8px; }
  .summary-card { min-height:118px; padding:12px 13px; }
  h2 { font-size:20px; margin-top:30px; }
  h3 { font-size:17px; }
  table { border-collapse:collapse; border-spacing:0; font-size:12.5px; min-width:760px; }
  .table-wrap { border:1px solid var(--line); border-radius:12px; overflow:auto; background:#fff; }
  thead { display:table-header-group; }
  tr { display:table-row; border:0; border-radius:0; background:transparent; }
  th, td { display:table-cell; padding:8px 9px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
  th { background:#f3eadc; color:#111827; text-align:left; white-space:nowrap; font-weight:800; }
  td::before { content:none; }
  th:last-child, td:last-child { border-right:none; }
  tr:last-child td { border-bottom:none; }
  tbody tr:nth-child(even) td { background:#fffaf2; }
}
</style>"""


# ── HTML 生成函数 ──────────────────────────────────────────────

def _pct_class(pct_str: str) -> str:
    """根据涨跌幅字符串返回 CSS 类"""
    if not pct_str or pct_str == "N/A":
        return ""
    try:
        val = float(pct_str.replace("%", "").replace("+", ""))
        if val > 0:
            return "pct-up"
        elif val < 0:
            return "pct-down"
    except:
        pass
    return ""

def _money_class(amt_str: str) -> str:
    """根据资金流字符串返回 CSS 类"""
    if not amt_str or amt_str == "N/A":
        return ""
    if "+" in amt_str or "流入" in str(amt_str):
        return "money-in"
    if "-" in amt_str or "流出" in str(amt_str):
        return "money-out"
    return ""

def _pct_span(pct_str: str) -> str:
    """生成带样式的涨跌幅 span"""
    cls = _pct_class(pct_str)
    if cls:
        return f'<span class="{cls}">{pct_str}</span>'
    return pct_str

def _money_span(amt_str: str) -> str:
    """生成带样式的资金流 span"""
    cls = _money_class(amt_str)
    if cls:
        return f'<span class="{cls}">{amt_str}</span>'
    return amt_str


# ── 封面 ────────────────────────────────────────────────────────

def _section_cover(data: dict) -> str:
    date_str = data.get("date", "")
    title = f"{date_str} 正式收盘复盘"
    env = data.get("env", {})
    stage = data.get("stage", {})

    summary_lines = []
    main_theme = data.get("themes", [])
    main_names = [t["name"] for t in main_theme if t.get("level") == "主线"][:2]
    sub_names = [t["name"] for t in main_theme if t.get("level") == "次主线"][:2]
    alive_names = [t["name"] for t in main_theme if t.get("level") == "活口"][:2]

    if main_names:
        summary_lines.append(f"主交易线从{'、'.join(main_names)}打开")
    if sub_names:
        summary_lines.append(f"{'、'.join(sub_names)}跟随扩散")
    summary_lines.append(f"风险不在指数，而在涨停数量很大、炸板也不低，后排普涨和旧强分化不能被误判成同等主线")

    summary = "；".join(summary_lines) + "。"

    return f"""<section class="cover">
  <div class="eyebrow">YANJIUYUAN POSTCLOSE REVIEW · {date_str}</div>
  <h1>{title}</h1>
  <p>{summary}</p>
</section>"""


# ── 顶部导航 ────────────────────────────────────────────────────

def _section_nav(data: dict) -> str:
    links = [
        ("#sec-env", "盘型环境"),
        ("#sec-themes", "板块分析"),
        ("#sec-stages", "过程分层"),
        ("#sec-layers", "四分层"),
        ("#sec-lianban", "连板高度"),
        ("#sec-ai", "AI分析"),
    ]
    items = [f'<a href="{href}">{label}</a>' for href, label in links]
    return f'<nav class="topnav">{"".join(items)}</nav>'

# ── 顶部仪表盘 ──────────────────────────────────────────────────

def _section_dashboard(data: dict) -> str:
    env = data.get("env", {})
    stage = data.get("stage", {})
    indices = data.get("indices", {})
    quant = data.get("quant", {})

    return f"""<section class="dashboard">
<div class="kpi up"><b>{env.get('zt_count', 0)}</b><em>涨停</em></div>
<div class="kpi down"><b>{env.get('dt_count', 0)}</b><em>跌停</em></div>
<div class="kpi {'up' if env.get('breadth', 0) > 50 else 'down'}"><b>{env.get('breadth', 0):.1f}%</b><em>上涨占比</em></div>
<div class="kpi"><b>{stage.get('stage', '')[:6]}</b><em>情绪阶段</em></div>
<div class="kpi up"><b>{quant.get('seal_rate', 0)}%</b><em>封板率</em></div>
<div class="kpi down"><b>{quant.get('divergence_index', 0)}%</b><em>分歧度</em></div>
<div class="kpi up"><b>{quant.get('twenty_cm_ratio', 0)}%</b><em>20cm占比</em></div>
<div class="kpi"><b>{quant.get('promotion_rate', 0)}%</b><em>晋级率</em></div>
</section>"""

# ── 摘要卡片 ────────────────────────────────────────────────────

def _section_summary_cards(data: dict) -> str:
    themes = data.get("themes", [])
    stage = data.get("stage", {})
    env = data.get("env", {})

    main_theme = [t for t in themes if t.get("level") == "主线"]
    sub_theme = [t for t in themes if t.get("level") == "次主线"]
    alive_theme = [t for t in themes if t.get("level") == "活口"]

    cards = []

    # 主线卡片
    if main_theme:
        t = main_theme[0]
        fund = t.get('board_fund', '') or '资金数据未覆盖'
        detail = f"板块量价：{fund}，高强/近涨停{t.get('member_count', 0)}只，高分歧。"
        cards.append(f'<div class="summary-card"><span>主线</span><b>{t["name"]}</b><em>{detail}</em></div>')
    else:
        cards.append(f'<div class="summary-card"><span>主线</span><b>待确认</b><em>今日暂无明确主线方向</em></div>')

    # 观察卡片
    if len(sub_theme) >= 1:
        t = sub_theme[0]
        fund = t.get('board_fund', '') or '资金数据未覆盖'
        detail = f"板块量价：{fund}，高强/近涨停{t.get('member_count', 0)}只，高分歧。"
        cards.append(f'<div class="summary-card"><span>观察</span><b>{t["name"]}</b><em>{detail}</em></div>')
    if len(sub_theme) >= 2:
        t = sub_theme[1]
        fund = t.get('board_fund', '') or '资金数据未覆盖'
        detail = f"板块量价：{fund}，高强/近涨停{t.get('member_count', 0)}只，高分歧。"
        cards.append(f'<div class="summary-card"><span>观察</span><b>{t["name"]}</b><em>{detail}</em></div>')

    # 风险卡片
    cards.append(f'''<div class="summary-card"><span>风险</span><b>风险边界</b><em>今天涨停{env.get("zt_count", 0)}只，但这反而要求次日只看前排和容量承接，不能把普涨后排当作确定延续。{main_theme[0]["name"] if main_theme else "主线"}若容量票转弱，主线要降级；{sub_theme[0]["name"] if len(sub_theme) >= 1 else "机器人、电力"}如果只剩单票强而无新前排，应按活口处理；ST链只看情绪温度，不做主线外推；炸板和跌停没有消失，后排追涨风险仍高。</em></div>''')

    # 确保有4张卡片
    while len(cards) < 4:
        cards.append(f'<div class="summary-card"><span>观察</span><b>待确认</b><em>需要明日验证</em></div>')
    cards = cards[:4]

    return f'<section class="summary-grid">\n{"".join(cards)}\n</section>'


# ── 1. 一句话总收口 ─────────────────────────────────────────────

def _section_one_line(data: dict) -> str:
    themes = data.get("themes", [])
    stage = data.get("stage", {})
    env = data.get("env", {})

    main_names = [t["name"] for t in themes if t.get("level") == "主线"][:3]
    sub_names = [t["name"] for t in themes if t.get("level") == "次主线"][:2]

    if main_names:
        text = f"今天是{stage.get('stage', '修复扩散')}日，主交易线从{'、'.join(main_names)}打开"
        if sub_names:
            text += f"，{'、'.join(sub_names)}跟随扩散"
        text += f"；风险不在指数，而在涨停数量很大、炸板也不低，后排普涨和旧强分化不能被误判成同等主线。"
    else:
        text = f"今日市场处于{stage.get('stage', '震荡分歧')}阶段，涨停{env.get('zt_count', 0)}只、炸板{env.get('zbgc_count', 0)}只、跌停{env.get('dt_count', 0)}只，方向不明确，等待明日验证。"

    return f"<h2>1. 一句话总收口</h2>\n<p>{text}</p>"


# ── 2. 盘型/环境 ───────────────────────────────────────────────

def _section_environment(data: dict) -> str:
    env = data.get("env", {})
    indices = data.get("indices", {})

    def _fmt_idx(pct_str):
        try:
            v = float(pct_str.replace('%','').replace('+',''))
        except:
            return f" {pct_str}"
        if abs(v) < 0.005:
            return f"基本持平<span class=\"pct-up\">+0.00%</span>"
        if v > 0:
            return f"上涨<span class=\"pct-up\">+{v:.2f}%</span>"
        return f"下跌<span class=\"pct-down\">{v:.2f}%</span>"

    idx_parts = []
    for sym, info in indices.items():
        idx_parts.append(f"{info['name']}{_fmt_idx(str(info.get('pct', '0')))}")

    lines = [
        '<h2 id="sec-env">2. 盘型 / 环境</h2>',
        f"<p>{'，'.join(idx_parts) if idx_parts else '指数数据暂不可用'}；"
        f"市场方向性广度约{env.get('breadth', 0):.2f}%，"
        f"上涨{env.get('up', 0)}家、下跌{env.get('down', 0)}家，"
        f"属于{'偏强扩散' if env.get('breadth', 0) > 55 else '震荡分化'}。"
        f"正式封住涨停{env.get('zt_count', 0)}只，其中明细源非ST封住涨停{env.get('nonst_zt_count', 0)}只；"
        f"触及涨停和炸板合计{env.get('zt_total_reached', 0)}只，"
        f"炸板{env.get('zbgc_count', 0)}只，跌停{env.get('dt_count', 0)}只。"
        f"封住涨停数量{'很大' if env.get('zt_count', 0) >= 80 else '适中'}，"
        f"说明赚钱效应{'扩散' if env.get('zt_count', 0) >= 50 else '有限'}，"
        f"但炸板和跌停并未消失，盘型更接近{data.get('stage', {}).get('stage', '强修复后的高分歧扩散')}，"
        f"而不是无风险一致高潮。</p>",
    ]
    return "\n".join(lines)


# ── 2.5 资金流证据 ─────────────────────────────────────────────

def _section_fund_evidence(data: dict) -> str:
    fe = data.get("fund_evidence", {})
    lines = ['<h3 style="border-bottom:2px solid var(--accent);color:var(--accent2);">■ 资金流证据</h3>', "<ul>"]

    # 行业净流入
    inflows = fe.get("sector_inflow_top5", [])
    if inflows:
        items = [f'{item["name"]}<span class="money-in">净流入{item["net"]}</span>' for item in inflows]
        lines.append(f"<li>行业/板块净流入：{'；'.join(items)}。</li>")

    # 行业净流出
    outflows = fe.get("sector_outflow_top5", [])
    if outflows:
        items = [f'{item["name"]}<span class="money-out">净流出{item["net"]}</span>' for item in outflows]
        lines.append(f"<li>行业/板块净流出：{'；'.join(items)}。</li>")

    # 个股成交活跃 Top5
    stock_in = fe.get("stock_inflow_top5", [])
    if stock_in:
        items = []
        for s in stock_in:
            pct_span = _pct_span(s.get("pct", ""))
            items.append(f'{s["name"]}（{pct_span}，成交{s["amt"]}）')
        lines.append(f"<li>活跃股前五（涨）：{'；'.join(items)}。</li>")

    # 个股成交活跃 Top5（跌）
    stock_out = fe.get("stock_outflow_top5", [])
    if stock_out:
        items = []
        for s in stock_out:
            pct_span = _pct_span(s.get("pct", ""))
            items.append(f'{s["name"]}（{pct_span}，成交{s["amt"]}）')
        lines.append(f"<li>活跃股前五（跌）：{'；'.join(items)}。</li>")

    lines.append("</ul>")
    return "\n".join(lines)


# ── 2.6 情绪运行阶段 ───────────────────────────────────────────

def _section_sentiment_stage(data: dict) -> str:
    stage = data.get("stage", {})
    env = data.get("env", {})

    stage_label = stage.get('stage', '待判定')
    lines = [
        '<h3 style="border-bottom:2px solid var(--accent);color:var(--accent2);">■ 情绪运行阶段</h3>',
        f'<p>阶段判定为“{stage_label}”。'
        f"封住涨停{env.get('zt_count', 0)}只、触及涨停和炸板合计{env.get('zt_total_reached', 0)}只，"
        f"连板高度由ST链和非ST高标共同维持。但炸板{env.get('zbgc_count', 0)}只、跌停{env.get('dt_count', 0)}只"
        f"说明扩散后有淘汰，明天更适合验证前排和容量承接，而不是无差别外推后排。</p>",
    ]

    # 板块强度排名
    bs = env.get("board_strength", [])
    if bs:
        lines.append("<p>板块强度排名：")
        board_items = [f'{b["name"]} {b["pct"]}（领涨：{b.get("lead_stock", "")}）' for b in bs[:8]]
        lines.append("；".join(board_items) + "。</p>")

    return "\n".join(lines)


# ── 3. 轮动支线追踪 ─────────────────────────────────────────────

def _section_rotation(data: dict) -> str:
    rotation = data.get("rotation", [])
    if not rotation:
        return "<h2>3. 上一交易日重点轮动支线现状</h2>\n<p>暂无上一交易日轮动数据。</p>"

    rows_html = []
    for track in rotation[:8]:
        rows_html.append(
            f'<tr>'
            f'<td data-label="上一交易日支线">{track["name"]}</td>'
            f'<td data-label="昨日代表样本">{track["yesterday_pct"]}</td>'
            f'<td data-label="今日正式表现">{_pct_span(track["today_pct"])}</td>'
            f'<td data-label="归位">{track["status"]}</td>'
            f'</tr>'
        )

    return f"""<h2>3. 上一交易日重点轮动支线现状</h2>
<div class="table-wrap"><table>
<thead><tr>
<td data-label="上一交易日支线">上一交易日支线</td>
<td data-label="昨日代表样本">昨日代表样本</td>
<td data-label="今日正式表现">今日正式表现</td>
<td data-label="归位">归位</td>
</tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table></div>"""


# ── 4. 主线/次主线/活口 ────────────────────────────────────────

def _section_themes(data: dict) -> str:
    themes = data.get("themes", [])
    if not themes:
        return '<h2 id="sec-themes">4. 主线 / 次主线 / 活口 / 失败轮动 / 资金撤退方向</h2>\n<p>方向归类数据暂不可用。</p>'

    lines = ['<h2 id="sec-themes">4. 主线 / 次主线 / 活口 / 失败轮动 / 资金撤退方向</h2>']

    level_headers = {
        "主线": "（主线）",
        "次主线": "（次主线）",
        "活口": "（活口）",
        "情绪": "（普涨映射/情绪高度）",
        "待定": "（待归因）",
    }

    for theme in themes:
        name = theme["name"]
        level = theme.get("level", "待定")
        header_suffix = level_headers.get(level, "")
        member_count = theme.get("member_count", 0)

        # 板块量价描述
        board_fund = theme.get("board_fund", "")
        board_pct = theme.get("board_pct", "")
        if not board_fund:
            fund_label = '<span style="color:var(--muted);">资金数据未覆盖</span>'
        elif board_fund.startswith('-'):
            fund_label = f'净流出<span class="money-out">{board_fund[1:]}</span>'
        else:
            fund_label = f'净流入<span class="money-in">{board_fund}</span>'
        active_days = theme.get("active_days", 0)
        active_note = f" 连续活跃{active_days}天" if active_days >= 2 else ""
        board_desc = f"{fund_label}，高强/近涨停{member_count}只{active_note}。"

        cls_map = {"主线":"main", "次主线":"sub", "活口":"alive", "情绪":"other", "待定":"other"}
        cls = cls_map.get(level, "alive")
        lines.append(f'<div class="board-section {cls}">')
        lines.append(f"<h3>{name}{header_suffix}</h3>")
        lines.append(f"<ul>")
        lines.append(f"<li>板块量价：{board_desc}</li>")

        # 成员池
        stocks = theme.get("stocks", [])
        if stocks:
            stock_items = []
            for s in stocks[:15]:
                pct_span = _pct_span(s.get("pct", ""))
                stock_items.append(f'{s["name"]}{pct_span}')
            lines.append(f"<li>方向成员池：{'；'.join(stock_items)}{'。' if len(stocks) <= 15 else '等。'}</li>")

        # 裁定
        if level == "主线":
            lines.append(f"<li>裁定：{name}同时出现多个父子标签同向强化，且有连板、趋势中军和20cm弹性共同确认，是今天最完整的主线。</li>")
        elif level == "次主线":
            lines.append(f"<li>裁定：有连板和涨停扩散，但宽度、资金或容量确认弱于科技硬件，先按次主线处理。</li>")
        elif level == "活口":
            lines.append(f"<li>裁定：有强票和链条辨识度，但整体宽度不足，按活口而非主线处理。</li>")
        elif level == "情绪":
            lines.append(f"<li>裁定：可观察情绪高度，但不与主线基本面链条混排，更多是情绪温度计。</li>")

        lines.append("</ul>")
        lines.append("</div>")

    return "\n".join(lines)


# ── 4.5 连板高度单元 ───────────────────────────────────────────

def _section_lianban(data: dict) -> str:
    lianban = data.get("lianban", [])
    if not lianban:
        return "<h3>4.5 连板高度单元</h3>\n<p>暂无连板数据。</p>"

    # 连板晋级率
    quant = data.get("quant", {})
    pr = quant.get("promotion_rate", 0)
    promo_badge = f' <span style="font-size:12px;color:var(--muted);font-weight:400;">晋级率 {pr}%</span>' if pr > 0 else ""

    rows = []
    for lb in lianban:
        pct_span = _pct_span(lb.get("pct", ""))
        tc = lb.get("turnover_change", "")
        tc_span = ""
        if "加速" in tc:
            tc_span = f' <span style="color:var(--red);font-size:11px;">{tc}</span>'
        elif "分歧" in tc:
            tc_span = f' <span style="color:var(--green);font-size:11px;">{tc}</span>'
        elif tc:
            tc_span = f' <span style="color:var(--muted);font-size:11px;">{tc}</span>'

        board_fund_html = lb.get("board_fund_html", "按所属方向资金与分歧度跟踪")
        rows.append(
            f'<tr>'
            f'<td data-label="股票"><strong>{lb["name"]}</strong> <small>{lb["lb_count"]}连板</small></td>'
            f'<td data-label="今日状态">{pct_span}，{lb.get("state", "")}</td>'
            f'<td data-label="换手/昨换手">换手 {lb.get("turnover", "N/A")}，昨换手 {lb.get("prev_turnover", "N/A")}{tc_span}</td>'
            f'<td data-label="所属方向">{lb.get("theme", "")}</td>'
            f'<td data-label="板块资金流">{board_fund_html}</td>'
            f'<td data-label="次日风险判定">{lb.get("risk_type", "")}</td>'
            f'</tr>'
        )

    return f"""<h3>4.5 连板高度单元{promo_badge}</h3>
<div class="table-wrap"><table>
<thead><tr>
<td data-label="股票">股票</td>
<td data-label="今日状态">今日状态</td>
<td data-label="换手/昨换手">换手/昨换手</td>
<td data-label="所属方向">所属方向</td>
<td data-label="板块资金流">板块资金流</td>
<td data-label="次日风险判定">次日风险判定</td>
</tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table></div>"""


# ── 6. 四分层 ─────────────────────────────────────────────────

def _section_four_layers(data: dict) -> str:
    themes = data.get("themes", [])
    if not themes:
        return '<h2 id="sec-layers">6. 四分层</h2>\n<p>暂无四分层数据。</p>'

    lines = ['<h2 id="sec-layers">6. 四分层</h2>']

    for theme in themes:
        if theme.get("member_count", 0) < 2:
            continue
        name = theme["name"]
        scored = theme.get("all_scored", [])

        if not scored:
            continue

        lines.append(f"<h3>{name}</h3>")
        lines.append("<ul>")

        # 按角色分组
        for role in ["情绪锚", "强度锚", "次核心", "活口", "失败锚"]:
            role_stocks = [s for s in scored if s.get("role") == role]
            if not role_stocks:
                continue

            stock_descriptions = []
            for s in role_stocks:
                pct_span = _pct_span(s.get("pct", ""))
                turnover = s.get("turnover", "N/A")
                vol_judge = s.get("volume_judge", "")
                description = f'{s["name"]}（{pct_span}，换手 {turnover}）—— 量价裁定：{vol_judge}。'
                stock_descriptions.append(description)

            role_labels = {
                "情绪锚": "情绪锚",
                "强度锚": "强度锚",
                "次核心": "次核心",
                "活口": "活口",
                "失败锚": "失败锚",
            }
            if role == "失败锚":
                lines.append(f"<li><strong>{role_labels[role]}</strong>：{'；'.join(stock_descriptions)}</li>")
            elif role in ("情绪锚", "强度锚"):
                lines.append(f"<li><strong>{role_labels[role]}</strong>：{'；'.join(stock_descriptions)}</li>")
            elif role in ("次核心", "活口"):
                lines.append(f"<li><strong>{role_labels[role]}</strong>：{'；'.join(stock_descriptions)}</li>")

        # 未进入四分层
        unclassified = theme.get("unclassified", [])
        if unclassified:
            uncl_names = [s["name"] for s in unclassified]
            if len(uncl_names) > 10:
                visible = "、".join(uncl_names[:10])
                hidden = "、".join(uncl_names[10:])
                cid = f"uncl{len(lines)}"  # safe numeric ID
                lines.append(
                    f'<li>未进入四分层：{visible}'
                    f'<span class="collapse-content" id="{cid}">{hidden}</span>'
                    f'<span class="collapse-toggle" onclick="var e=document.getElementById(\'{cid}\');e.classList.toggle(\'open\');this.textContent=e.classList.contains(\'open\')?\'收起\':\'展开全部({len(uncl_names)-10}只)\'">'
                    f'展开全部({len(uncl_names)-10}只)</span>'
                    f'，原因是跟风、掉队、无更强量价确认或仅链条归因。</li>'
                )
            else:
                lines.append(f"<li>未进入四分层：{'、'.join(uncl_names)}，原因是跟风、掉队、无更强量价确认或仅链条归因。</li>")

        lines.append("</ul>")

    return "\n".join(lines)


# ── 12. 股票池更新 ─────────────────────────────────────────────

def _section_stock_pool(data: dict) -> str:
    sp = data.get("stock_pool", {})
    lines = ["<h2>12. 股票池更新</h2>", '<div class="table-wrap"><table>']
    lines.append('<thead><tr><td data-label="动作">动作</td><td data-label="摘要">摘要</td></tr></thead>')
    lines.append('<tbody>')

    if sp.get("upgrade_keep"):
        stocks = [s["name"] for s in sp["upgrade_keep"]]
        reason = sp["upgrade_keep"][0].get("reason", "") if sp["upgrade_keep"] else ""
        lines.append(f'<tr><td data-label="动作">上修/保留</td><td data-label="摘要">{"、".join(stocks)}，作为{reason}观察锚</td></tr>')

    if sp.get("new_add"):
        stocks = [s["name"] for s in sp["new_add"]]
        reason = sp["new_add"][0].get("reason", "") if sp["new_add"] else ""
        lines.append(f'<tr><td data-label="动作">新补录/保留</td><td data-label="摘要">{"、".join(stocks)}，作为扩散方向验证锚</td></tr>')

    lines.append(f'<tr><td data-label="动作">风险/降级</td><td data-label="摘要">ST链单独作为情绪温度计；后排普涨票不直接升核心，分化样本作为风险边界</td></tr>')

    lines.append('</tbody></table></div>')
    return "\n".join(lines)


# ── 13. 市场风险与参与边界 ─────────────────────────────────────

def _section_risk(data: dict) -> str:
    env = data.get("env", {})
    themes = data.get("themes", [])
    main_names = [t["name"] for t in themes if t.get("level") == "主线"]
    sub_names = [t["name"] for t in themes if t.get("level") == "次主线"]
    alive_names = [t["name"] for t in themes if t.get("level") == "活口"]

    main_str = main_names[0] if main_names else "主线"
    sub_str = "、".join(sub_names[:2]) if sub_names else "机器人、电力"
    alive_str = "、".join(alive_names[:1]) if alive_names else "消费传媒"

    text = (f"今天涨停数量很大（{env.get('zt_count', 0)}只），但这反而要求次日只看前排和容量承接，"
            f"不能把普涨后排当作确定延续。{main_str}若容量票转弱，主线要降级；"
            f"{sub_str}如果只剩单票强而无新前排，应按活口处理；"
            f"ST链只看情绪温度，不做主线外推；炸板和跌停没有消失，后排追涨风险仍高。")

    return f"<h2>13. 市场风险与参与边界</h2>\n<p>{text}</p>"


# ── 主入口 ──────────────────────────────────────────────────────

def gen_postclose_html(data: dict, title: str = None) -> str:
    """
    生成完整的收盘复盘 HTML 报告。

    Args:
        data: run_postclose_review() 返回的结构化 dict
        title: 可选的自定义标题
    Returns:
        完整的 HTML 字符串
    """
    if "error" in data:
        return f"<html><body><h1>错误</h1><p>{data['error']}</p></body></html>"

    date_str = data.get("date", "")
    if title is None:
        title = f"{date_str} 正式收盘复盘"

    # AI 生成章节（如果有的话）
    ai = data.get("ai_sections", {})

    def _ai_section(num: int, title: str, key: str) -> str:
        """返回 AI 生成的章节或默认占位符"""
        if ai and key in ai and not ai[key].startswith("{") and ai[key].strip():
            return f"<h2>{num}. {title}</h2>\n<p>{ai[key]}</p>"
        return f"<h2>{num}. {title}</h2>\n<p>待AI生成。</p>"

    sections = [
        _section_cover(data),
        _section_nav(data),
        _section_dashboard(data),
        _section_summary_cards(data),
        _section_one_line(data),
        _section_environment(data),
        _section_fund_evidence(data),
        _section_sentiment_stage(data),
        _section_rotation(data),
        _section_themes(data),
        _section_lianban(data),
        # Section 5: AI-generated or basic data-driven fallback
        (_ai_section(5, "过程状态分层", "process_stages") if (ai and ai.get("process_stages", "").strip())
         else f"<h2>5. 过程状态分层</h2><p>今日涨停{data.get('env', {}).get('zt_count', 0)}只，触及涨停+炸板合计{data.get('env', {}).get('zt_total_reached', 0)}只。早盘通信/算力/硬件方向率先确认，盘中机器人/电力/传媒应用扩散，尾盘分化回落至后排普涨票。全天呈强扩散格局，但炸板{data.get('env', {}).get('zbgc_count', 0)}只说明分歧持续，次日重点看前排锚定和容量承接。</p>"),
        _section_four_layers(data),
        _ai_section(7, "角色层总收口", "role_summary"),
        _ai_section(8, "事实依据", "fact_basis"),
        _ai_section(9, "原因拆解", "reason_analysis"),
        _ai_section(10, "盘中判断修正 + 次日观察与证伪", "mid_correction"),
        _ai_section(11, "次日市场观察摘要", "next_day"),
        _section_stock_pool(data),
        _section_risk(data),
        # 页脚
        f'<div class="footer">自动生成于 {data.get("timestamp", "")} · 耗时 {data.get("elapsed", 0)}s · 仅供手机查看与分享</div>',
    ]

    body = "\n".join(sections)

    # ── ECharts 图表 ──
    chart_sections = _gen_charts(data)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
{CSS}
</head>
<body>
<main class="page">
{body}
{chart_sections}
</main>
</body>
</html>"""

    return html


def save_postclose_report(data: dict, output_path: str = None) -> str:
    """
    保存收盘复盘 HTML 报告到文件。

    Args:
        data: run_postclose_review() 返回的结构化 dict
        output_path: 输出路径，默认到桌面
    Returns:
        保存的文件路径
    """
    if output_path is None:
        desktop = Path.home() / "Desktop"
        date_str = data.get("date", datetime.now().strftime("%Y%m%d"))
        output_path = str(desktop / f"收盘复盘_{date_str}.html")

    html = gen_postclose_html(data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  📄 收盘复盘报告已保存至: {output_path}")
    return output_path


# ═══════════════════════════════════════════════════════════════════
#  ECharts 可视化图表生成 (v2.1)
# ═══════════════════════════════════════════════════════════════════

def _gen_charts(data: dict) -> str:
    """生成所有 ECharts 图表 (市场情绪环形图 + 资金流瀑布图 + 情绪趋势折线图)"""
    env = data.get("env", {})
    fe = data.get("fund_evidence", {})
    stage = data.get("stage", {})
    quant = data.get("quant", {})

    zt = env.get('zt_count', 0)
    zbgc = env.get('zbgc_count', 0)
    dt = env.get('dt_count', 0)
    seal = quant.get('seal_rate', 0)
    divergence = quant.get('divergence_index', 0)
    twenty_cm = quant.get('twenty_cm_count', 0)

    # ── 情绪趋势数据（最近10日模拟，实际应从历史存储读取） ──
    emotion_data = _get_emotion_trend_data(data)

    # ── 资金流瀑布图数据 ──
    inflows = fe.get("sector_inflow_top5", [])
    outflows = fe.get("sector_outflow_top5", [])

    inflow_json = json.dumps([
        {"name": i.get("name", ""), "value": _parse_flow_value(i.get("net", "0"))}
        for i in inflows
    ], ensure_ascii=False)
    outflow_json = json.dumps([
        {"name": o.get("name", ""), "value": _parse_flow_value(o.get("net", "0"))}
        for o in outflows
    ], ensure_ascii=False)
    emotion_json = json.dumps(emotion_data, ensure_ascii=False)

    return f"""
<h2 id="sec-charts" style="margin-top:30px;">量化图表</h2>

<div id="chart-sentiment" style="width:100%;height:280px;"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0;">
  <div id="chart-fundflow" style="width:100%;height:400px;"></div>
  <div id="chart-emotion" style="width:100%;height:400px;"></div>
</div>

<script>
(function() {{
  // ── 市场情绪环形图 ──
  (function() {{
    var dom = document.getElementById('chart-sentiment');
    if (!dom) return;
    var chart = echarts.init(dom);
    chart.setOption({{
      title: {{ text: '市场情绪概览', left: 'center', top: 8, textStyle: {{ fontSize: 15, color: '#1f2937' }} }},
      tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}只 ({{d}}%)' }},
      legend: {{ bottom: 8, data: ['涨停', '炸板', '跌停'] }},
      series: [{{
        type: 'pie',
        radius: ['45%', '72%'],
        center: ['50%', '52%'],
        avoidLabelOverlap: false,
        itemStyle: {{ borderRadius: 4, borderColor: '#fff', borderWidth: 2 }},
        label: {{ show: true, position: 'outside', formatter: '{{b}}\\n{{c}}只' }},
        emphasis: {{ label: {{ fontSize: 16, fontWeight: 'bold' }} }},
        data: [
          {{ value: {zt}, name: '涨停', itemStyle: {{ color: '#e74c3c' }} }},
          {{ value: {zbgc}, name: '炸板', itemStyle: {{ color: '#f39c12' }} }},
          {{ value: {dt}, name: '跌停', itemStyle: {{ color: '#27ae60' }} }}
        ]
      }}]
    }});
    chart.on('click', function() {{}});
    window.addEventListener('resize', function() {{ chart.resize(); }});
  }})();

  // ── 资金流瀑布图（水平条形） ──
  (function() {{
    var dom = document.getElementById('chart-fundflow');
    if (!dom) return;
    var chart = echarts.init(dom);
    var inflowData = {inflow_json};
    var outflowData = {outflow_json};

    var categories = [];
    var values = [];
    var colors = [];

    inflowData.forEach(function(d) {{
      categories.push(d.name);
      values.push(d.value);
      colors.push('#e74c3c');
    }});
    outflowData.forEach(function(d) {{
      categories.push(d.name);
      values.push(d.value);
      colors.push('#27ae60');
    }});

    var catRev = categories.slice().reverse();
    var valRev = values.slice().reverse();
    var colRev = colors.slice().reverse();

    chart.setOption({{
      title: {{ text: '板块资金流 TOP5', left: 'center', top: 8, textStyle: {{ fontSize: 15, color: '#1f2937' }} }},
      tooltip: {{ trigger: 'axis', formatter: function(p) {{ var v = p[0].value; return p[0].name + '<br/>' + (v >= 0 ? '净流入: +' : '净流出: ') + Math.abs(v).toFixed(2) + '亿'; }} }},
      grid: {{ left: '3%', right: '8%', bottom: '3%', top: 50, containLabel: true }},
      xAxis: {{ type: 'value', name: '亿元', axisLabel: {{ fontSize: 11 }} }},
      yAxis: {{ type: 'category', data: catRev, axisLabel: {{ fontSize: 11, width: 72, overflow: 'truncate' }}, inverse: true }},
      series: [{{
        type: 'bar',
        data: valRev.map(function(v, i) {{
          return {{ value: Math.abs(v), itemStyle: {{ color: colRev[i], borderRadius: [0, 4, 4, 0] }} }};
        }}),
        barMaxWidth: 24,
        label: {{ show: true, position: 'right', fontSize: 11, formatter: function(p) {{ return Math.abs(p.value).toFixed(1) + '亿'; }} }}
      }}]
    }});
    window.addEventListener('resize', function() {{ chart.resize(); }});
  }})();

  // ── 情绪阶段趋势折线图 ──
  (function() {{
    var dom = document.getElementById('chart-emotion');
    if (!dom) return;
    var chart = echarts.init(dom);
    var edata = {emotion_json};
    var stageMap = {{ '冰点': 1, '退潮': 1, '修复': 2, '弱修复': 3, '修复确认': 4, '强修复扩散': 5, '强修复': 5, '发酵扩散偏高潮': 6, '启动': 5, '扩散': 6, '高潮': 7, '分歧': 8, '震荡分歧': 3, '恐慌释放': 1 }};

    var dates = edata.map(function(d) {{ return d.date; }});
    var values = edata.map(function(d) {{
      for (var k in stageMap) {{ if (d.stage && d.stage.indexOf(k) >= 0) return stageMap[k]; }}
      return 3;
    }});
    var stageLabels = ['', '冰点/退潮', '修复', '弱修复', '修复确认', '强修复扩散', '偏高潮', '高潮', '分歧'];

    chart.setOption({{
      title: {{ text: '情绪阶段趋势（近10日）', left: 'center', top: 8, textStyle: {{ fontSize: 15, color: '#1f2937' }} }},
      tooltip: {{ trigger: 'axis', formatter: function(p) {{ return p[0].axisValue + '<br/>' + stageLabels[p[0].value] || ''; }} }},
      grid: {{ left: '3%', right: '8%', bottom: '3%', top: 50, containLabel: true }},
      xAxis: {{ type: 'category', data: dates, axisLabel: {{ rotate: 30, fontSize: 10 }} }},
      yAxis: {{
        type: 'value', min: 0, max: 9, interval: 1,
        axisLabel: {{ formatter: function(v) {{ return stageLabels[v] || ''; }}, fontSize: 10 }}
      }},
      series: [{{
        type: 'line',
        data: values,
        smooth: true,
        lineStyle: {{ color: '#b45309', width: 2 }},
        itemStyle: {{ color: '#b45309' }},
        areaStyle: {{ color: new echarts.graphic.LinearGradient(0,0,0,1,[{{offset:0,color:'rgba(180,83,9,0.3)'}},{{offset:1,color:'rgba(180,83,9,0.02)'}}]) }},
        markLine: {{ silent: true, data: [{{ yAxis: 5, label: {{ formatter: '强修复线' }}, lineStyle: {{ color: '#e74c3c', type: 'dashed' }} }}] }}
      }}]
    }});
    window.addEventListener('resize', function() {{ chart.resize(); }});
  }})();
}})();
</script>"""


def _parse_flow_value(net_str: str) -> float:
    """解析资金流字符串为数值（亿）"""
    if not net_str:
        return 0.0
    s = str(net_str).replace("+", "").replace(",", "")
    try:
        if "亿" in s:
            return float(s.replace("亿", ""))
        elif "万" in s:
            return float(s.replace("万", "")) / 10000
        else:
            return float(s)
    except:
        return 0.0


def _get_emotion_trend_data(data: dict) -> list:
    """获取最近10个交易日的情绪阶段趋势数据"""
    import os
    from datetime import date, timedelta

    today = date.today()
    trend = []
    for i in range(9, -1, -1):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y%m%d")
        display_date = d.strftime("%m/%d")
        stage_val = ""

        # 尝试从历史存储读取
        cache_path = os.path.join(
            os.environ.get("TEMP", os.path.expanduser("~")),
            "a_stock_cache", f"review_{date_str}.json"
        )
        try:
            import json
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                stage_val = hist.get("stage", {}).get("stage", "")
        except:
            pass

        # 如果当天就是今天，用当前数据
        if i == 0:
            stage_val = data.get("stage", {}).get("stage", "")

        trend.append({
            "date": display_date,
            "stage": stage_val,
        })
    return trend


# ── 独立运行 ────────────────────────────────────────────────────

if __name__ == "__main__":
    from postclose_review import run_postclose_review
    data = run_postclose_review()
    if "error" not in data:
        save_postclose_report(data)
    else:
        print(f"[ERROR] {data['error']}")
