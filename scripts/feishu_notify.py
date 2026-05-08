"""
feishu_notify.py - 飞书通知 + GitHub Pages 部署
==============================================
通过飞书机器人 Webhook 发送收盘复盘摘要到手机，
同时自动将 HTML 报告部署到 GitHub Pages，附带可点击链接。

使用方式:
  from feishu_notify import send_postclose_to_feishu
  send_postclose_to_feishu(html_path, review_data, webhook_url)

前置条件:
  1. GitHub Pages 已启用（Settings → Pages → Source: master /docs）
  2. 飞书机器人 Webhook 已配置，关键词设为 "zgy"
"""

import json
import os
import shutil
import subprocess
import requests
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────
GITHUB_PAGES_URL = "https://garyreni.github.io/stock-analysis"
REPO_DIR = "D:/AI/a-stock-analysis"
DOCS_DIR = "D:/AI/a-stock-analysis/docs"


def _deploy_to_github_pages(html_path: str) -> str:
    """将 HTML 报告复制到 docs/ 并推送到 GitHub Pages，返回可访问的 URL。"""
    try:
        html_name = os.path.basename(html_path)

        # 1. 确保 docs 目录存在
        os.makedirs(DOCS_DIR, exist_ok=True)

        # 2. 复制 HTML 到 docs/
        dest = os.path.join(DOCS_DIR, html_name)
        shutil.copy2(html_path, dest)

        # 3. 创建 index.html（指向最新报告）
        index_path = os.path.join(DOCS_DIR, "index.html")
        shutil.copy2(html_path, index_path)

        # 4. git add + commit + push（有变更才 commit）
        subprocess.run(
            ["git", "add", "docs/"],
            cwd=REPO_DIR, check=True, capture_output=True,
        )
        # 检查是否有变更
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_DIR, capture_output=True,
        )
        if diff_result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"update: {html_name}"],
                cwd=REPO_DIR, check=True, capture_output=True,
            )
        subprocess.run(
            ["git", "push"],
            cwd=REPO_DIR, check=True, capture_output=True, timeout=30,
        )

        # GitHub Pages 有短暂延迟，URL 约 30 秒后生效
        url = f"{GITHUB_PAGES_URL}/{html_name}"
        print(f"  [部署] ✅ 已推送到 GitHub Pages: {url}")
        return url

    except Exception as e:
        # 部署失败不阻塞主流程
        print(f"  [部署] 推送失败: {e}")
        return ""


def _send_text(webhook_url: str, text: str) -> bool:
    """发送纯文本消息到飞书（带关键词 zgy）"""
    try:
        # 飞书关键词过滤：消息必须包含关键词
        text_with_keyword = f"zgy {text}"
        resp = requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": text_with_keyword}},
            timeout=10,
        )
        result = resp.json()
        if result.get("code") != 0:
            print(f"  [飞书] 发送失败: {result.get('msg', '')}")
            return False
        return True
    except Exception as e:
        print(f"  [飞书] 发送文本失败: {e}")
        return False


def _send_card(webhook_url: str, title: str, content: list) -> bool:
    """发送富文本卡片到飞书（标题含关键词 zgy）"""
    try:
        body = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": f"zgy · {title}"},
                    "template": "orange",
                },
                "elements": content,
            },
        }
        resp = requests.post(webhook_url, json=body, timeout=10)
        result = resp.json()
        if result.get("code") != 0:
            print(f"  [飞书] 发送卡片失败: {result.get('msg', '')}")
            return False
        return True
    except Exception as e:
        print(f"  [飞书] 发送卡片失败: {e}")
        return False


def _build_summary_card(data: dict, report_url: str = "") -> list:
    """根据复盘数据构建飞书消息卡片内容"""
    env = data.get("env", {})
    stage = data.get("stage", {})
    themes = data.get("themes", [])
    indices = data.get("indices", {})
    lianban = data.get("lianban", [])

    elements = []

    # 指数
    idx_text = " | ".join([
        f"{info['name']} {info.get('pct', '')}"
        for info in indices.values()
    ])
    if idx_text:
        elements.append({
            "tag": "markdown",
            "content": f"**📊 指数**\n{idx_text}",
        })

    # 盘型
    elements.append({
        "tag": "markdown",
        "content": (
            f"**📈 盘型**\n"
            f"涨停 **{env.get('zt_count', 0)}** 只 | "
            f"炸板 {env.get('zbgc_count', 0)} 只 | "
            f"跌停 {env.get('dt_count', 0)} 只\n"
            f"上涨 {env.get('up', 0)} 家 / 下跌 {env.get('down', 0)} 家 | "
            f"广度 {env.get('breadth', 0):.1f}%"
        ),
    })

    # 情绪
    elements.append({
        "tag": "markdown",
        "content": (
            f"**🎯 情绪**: {stage.get('stage', 'N/A')} | "
            f"资金: {stage.get('flow_sentiment', 'N/A')}"
        ),
    })

    # 方向
    theme_lines = []
    for t in themes[:5]:
        theme_lines.append(
            f"• **{t.get('level', '')}** {t['name']}（{t.get('member_count', 0)}只）"
        )
    if theme_lines:
        elements.append({
            "tag": "markdown",
            "content": "**🔥 方向**\n" + "\n".join(theme_lines),
        })

    # 连板
    if lianban:
        lb_lines = []
        for lb in lianban[:6]:
            lb_lines.append(
                f"• {lb['name']} {lb.get('lb_count', 0)}连板 "
                f"{lb.get('pct', '')} | {lb.get('risk_type', '')}"
            )
        elements.append({
            "tag": "markdown",
            "content": "**🔗 连板**\n" + "\n".join(lb_lines),
        })

    # 风险
    elements.append({
        "tag": "markdown",
        "content": f"⚠️ {stage.get('risk_note', '次日只看前排和容量承接')}",
    })

    elements.append({"tag": "hr"})

    # 报告链接
    if report_url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📄 查看完整报告"},
                "type": "primary",
                "url": report_url,
            }],
        })
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"zgy | {data.get('timestamp', '')} | 点击上方按钮查看完整 HTML 报告"}],
        })
    else:
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"zgy | {data.get('timestamp', '')} | 电脑端打开 HTML 查看完整报告"}],
        })

    return elements


def send_postclose_to_feishu(html_path: str, data: dict,
                              webhook_url: str = None,
                              deploy: bool = True) -> str:
    """
    发送收盘复盘报告到飞书手机，同时部署到 GitHub Pages。

    Args:
        html_path: HTML 报告文件路径
        data: run_postclose_review() 返回的结构化数据
        webhook_url: 飞书机器人 Webhook URL
        deploy: 是否同步部署到 GitHub Pages

    Returns:
        GitHub Pages URL（如果部署成功），否则空字符串
    """
    webhook_url = webhook_url or os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        print("  [飞书] 未设置 Webhook URL，跳过发送")
        return ""

    print("  [飞书] 发送收盘复盘...")

    # 1. 部署到 GitHub Pages
    report_url = ""
    if deploy:
        print("  [部署] 推送到 GitHub Pages...")
        report_url = _deploy_to_github_pages(html_path)

    # 2. 发送卡片消息（含链接）
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    card_content = _build_summary_card(data, report_url)
    ok1 = _send_card(webhook_url, f"📊 {date_str} 收盘复盘", card_content)

    if ok1:
        print(f"  [飞书] ✅ 复盘已发送到手机")
        if report_url:
            print(f"  [飞书] 📎 完整报告: {report_url}")

    return report_url
