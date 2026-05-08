"""
ai_analyst.py - DeepSeek AI 分析模块
=====================================
将 postclose_review 的结构化数据发送给 DeepSeek，
生成报告中需要 AI 推理的文字章节。

使用方式:
  from ai_analyst import analyze_with_deepseek
  ai_sections = analyze_with_deepseek(review_data, api_key="sk-xxx")
  # ai_sections 是 dict，包含所有 AI 生成的文字章节
"""

import json
import os
from datetime import datetime


def _build_prompt(data: dict) -> str:
    """根据结构化数据构建发送给 DeepSeek 的分析 prompt"""
    env = data.get("env", {})
    stage = data.get("stage", {})
    themes = data.get("themes", [])
    lianban = data.get("lianban", [])
    fund_evidence = data.get("fund_evidence", {})
    indices = data.get("indices", {})
    date_str = data.get("date", "")

    # ── 指数 ──
    idx_lines = []
    for sym, info in indices.items():
        idx_lines.append(f"  {info['name']}: {info['pct']}")
    idx_text = "\n".join(idx_lines) if idx_lines else "  暂无"

    # ── 市场数据 ──
    market_text = f"""- 上涨 {env.get('up', 0)} 家，下跌 {env.get('down', 0)} 家，平盘 {env.get('flat', 0)} 家
- 市场广度（上涨占比）: {env.get('breadth', 0):.1f}%
- 平均涨跌幅: {env.get('avg_pct', 'N/A')}，中位数涨跌幅: {env.get('med_pct', 'N/A')}
- 正式封住涨停: {env.get('zt_count', 0)} 只（非ST: {env.get('nonst_zt_count', 0)} 只）
- 触及涨停+炸板合计: {env.get('zt_total_reached', 0)} 只
- 炸板: {env.get('zbgc_count', 0)} 只
- 跌停: {env.get('dt_count', 0)} 只"""

    # ── 资金流 ──
    inflows = fund_evidence.get("sector_inflow_top5", [])
    outflows = fund_evidence.get("sector_outflow_top5", [])
    fund_text = ""
    if inflows:
        fund_text += "行业净流入前5: " + " | ".join(
            [f"{i['name']} {i['net']}" for i in inflows]
        )
    if outflows:
        fund_text += "\n行业净流出前5: " + " | ".join(
            [f"{o['name']} {o['net']}" for o in outflows]
        )
    if not fund_text:
        fund_text = "暂无资金流数据"

    stock_in = fund_evidence.get("stock_inflow_top5", [])
    stock_out = fund_evidence.get("stock_outflow_top5", [])
    stock_fund_text = ""
    if stock_in:
        stock_fund_text += "个股净流入前5: " + " | ".join(
            [f"{s['name']} {s['pct']} {s['amt']}" for s in stock_in]
        )
    if stock_out:
        stock_fund_text += "\n个股净流出前5: " + " | ".join(
            [f"{s['name']} {s['pct']} {s['amt']}" for s in stock_out]
        )

    # ── 方向归类 ──
    theme_text_parts = []
    for t in themes[:8]:
        stocks = t.get("stocks", [])
        stock_str = "、".join([
            f"{s['name']}{s.get('pct', '')}"
            for s in stocks[:12]
        ])
        anchors = t.get("anchors", [])
        anchor_str = ""
        if anchors:
            anchor_str = " | 锚: " + "、".join([
                f"{a['name']}({a.get('role', '')})"
                for a in anchors
            ])
        theme_text_parts.append(
            f"【{t.get('level', '')}】{t['name']}（{t.get('member_count', 0)}只）\n"
            f"  成员: {stock_str}{'...' if len(stocks) > 12 else ''}{anchor_str}\n"
            f"  裁定: {t.get('board_fund', '资金未覆盖')}"
        )
    theme_text = "\n".join(theme_text_parts) if theme_text_parts else "暂无方向数据"

    # ── 连板 ──
    lb_text = ""
    for lb in lianban[:15]:
        lb_text += f"  {lb['name']} {lb.get('lb_count', 0)}连板 {lb.get('pct', '')} | 换手{lb.get('turnover', 'N/A')} | {lb.get('theme', '')} | {lb.get('risk_type', '')}\n"
    if not lb_text:
        lb_text = "暂无连板数据"

    # ── 四分层 ──
    four_layer_parts = []
    for t in themes:
        if t.get("member_count", 0) < 2:
            continue
        scored = t.get("all_scored", [])
        if not scored:
            continue
        parts_for_theme = []
        for role in ["情绪锚", "强度锚", "次核心", "活口", "失败锚"]:
            role_stocks = [s for s in scored if s.get("role") == role]
            if role_stocks:
                stock_descs = [
                    f"{s['name']}({s.get('pct', '')}，换手{s.get('turnover', 'N/A')}，{s.get('volume_judge', '')})"
                    for s in role_stocks
                ]
                parts_for_theme.append(f"  {role}: {'; '.join(stock_descs)}")
        uncl = t.get("unclassified", [])
        if uncl:
            parts_for_theme.append(f"  未进入四分层: {'、'.join([s['name'] for s in uncl])}")
        if parts_for_theme:
            four_layer_parts.append(f"【{t['name']}】\n" + "\n".join(parts_for_theme))
    four_layer_text = "\n\n".join(four_layer_parts) if four_layer_parts else "暂无四分层数据"

    # ── 组装完整 prompt ──
    prompt = f"""你是一位资深A股市场研究员，正在撰写 {date_str} 收盘复盘报告。

请基于以下结构化市场数据，撰写6个分析章节。要求：
- 语言专业、精炼、有洞察力
- 使用中国A股市场惯用术语
- 每章控制在150-300字
- 明确指出风险点和次日验证要点
- 不做模糊预测，只基于数据做合理推演

══════════════ 市场数据 ══════════════

【指数表现】
{idx_text}

【盘型/环境】
{market_text}

【情绪阶段】
判定: {stage.get('stage', '')}
资金情绪: {stage.get('flow_sentiment', '')}
风险提示: {stage.get('risk_note', '')}

【资金流证据】
{fund_text}

【个股资金流】
{stock_fund_text}

【方向归类】
{theme_text}

【连板高度】
{lb_text}

【四分层锚定】
{four_layer_text}

══════════════ 请生成以下6个章节 ══════════════

请按以下JSON格式输出，每个字段是一个完整的HTML段落（可含<span class="pct-up">...</span>等CSS类）：

{{
  "process_stages": "第5节：过程状态分层 — 描述今日早盘/盘中/尾盘三个阶段的资金流向和热点演变过程（根据涨停时间分布和板块轮动逻辑推断）",
  "role_summary": "第7节：角色层总收口 — 总结今日情绪高度由谁维持、方向强度由谁拿走、扩散留存方向的质量评估",
  "fact_basis": "第8节：事实依据 — 列出支撑今日判断的关键事实：指数、涨停数、板块强度、个股表现等",
  "reason_analysis": "第9节：原因拆解 — 分析主线/次主线/活口形成的原因，为什么某些方向能成为主线而不是其他",
  "mid_correction": "第10节：盘中判断修正 + 次日观察与证伪 — 盘中可能的误判和收盘修正，明确次日需要验证的关键点",
  "next_day": "第11节：次日市场观察摘要 — 次日需要重点观察的2-3组验证信号"
}}

只输出JSON，不要输出其他内容。"""

    return prompt


def analyze_with_deepseek(data: dict, api_key: str = None,
                          model: str = "deepseek-v4-pro",
                          base_url: str = "https://api.deepseek.com") -> dict:
    """
    调用 DeepSeek API 进行 AI 分析，返回各文字章节的 dict。

    Args:
        data: run_postclose_review() 返回的结构化数据
        api_key: DeepSeek API Key（默认从环境变量 DEEPSEEK_API_KEY 读取）
        model: 模型名（默认 deepseek-chat 即 V3）
        base_url: API 地址（默认 https://api.deepseek.com）

    Returns:
        dict with keys: process_stages, role_summary, fact_basis,
                        reason_analysis, mid_correction, next_day
    """
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"error": "未设置 DeepSeek API Key，请传入 api_key 参数或设置环境变量 DEEPSEEK_API_KEY"}

    prompt = _build_prompt(data)

    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "请先安装 openai: pip install openai"}

    client = OpenAI(api_key=api_key, base_url=base_url)

    print("  [AI] 调用 DeepSeek 进行市场分析...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位资深A股市场研究员。只输出被要求的JSON格式，不要额外文字。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        content = response.choices[0].message.content

        # 清理可能的 markdown 代码块包裹
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            elif content.endswith("```\n"):
                content = content[:-4]

        result = json.loads(content)
        print(f"  [AI] 分析完成，生成 {len(result)} 个章节")
        return result

    except json.JSONDecodeError as e:
        print(f"  [AI] JSON解析失败: {e}")
        print(f"  原始输出: {content[:500]}...")
        return {"error": f"AI 返回格式异常: {e}", "raw": content}
    except Exception as e:
        print(f"  [AI] 调用失败: {e}")
        return {"error": str(e)}


def enrich_review_data(data: dict, api_key: str = None,
                       model: str = "deepseek-v4-pro") -> dict:
    """
    用 DeepSeek 分析结果丰富收盘复盘数据，返回增强后的 data dict。
    直接可传给 report_html.gen_postclose_html()。

    Args:
        data: run_postclose_review() 的输出
        api_key: DeepSeek API Key

    Returns:
        增强后的 data dict（新增 ai_sections 字段）
    """
    ai = analyze_with_deepseek(data, api_key=api_key, model=model)
    if "error" in ai:
        print(f"  [AI] 警告: {ai['error']}")
    data["ai_sections"] = ai
    return data
