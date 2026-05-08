# 股票分析自用

A股全市场行情分析系统，支持收盘复盘、板块分析、个股分析、资金流、龙虎榜、机会发现等。

## 快速开始

```bash
pip install akshare pandas openai
python scripts/main.py --postclose
```

## 功能模式

| 命令 | 功能 |
|------|------|
| `--postclose` | 收盘复盘 HTML 报告（含 DeepSeek AI 分析） |
| `--stock 601899 --kline` | 个股深度分析 |
| `--sector 有色金属` | 板块分析 |
| `--opportunity` | 机会发现 |
| `--fund-flow` | 资金流分析 |
| `--lhb` | 龙虎榜分析 |
| `--recommend` | 荐股评分 |

## AI 分析

设置环境变量 `DEEPSEEK_API_KEY` 后，`--postclose` 会自动调用 DeepSeek 生成 6 个 AI 分析章节。

## 数据源

腾讯/新浪/同花顺/东方财富 — 通过 akshare 和直连接口获取。
