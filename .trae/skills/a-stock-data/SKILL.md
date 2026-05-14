---
name: "a-stock-data"
description: "Summarizes and applies simonlin1212/a-stock-data A-share data toolkit. Invoke when you need A股行情/研报/信号/新闻/公告 data endpoints or integration guidance."
---

# A-Stock-Data (A股全栈数据工具包)

This skill is a local workspace companion for the GitHub project:

- https://github.com/simonlin1212/a-stock-data

Use it to quickly understand what the toolkit provides and how to integrate it into NeoTrade workflows.

## When to Invoke

- You need A-share market data (K线/盘口/估值/涨跌停价).
- You need research reports (研报列表/PDF/一致预期) and want the headers/auth details handled.
- You need “signal layer” data (题材/北向/概念板块/资金流向/龙虎榜/解禁/行业对比).
- You want to add or replace data sources in NeoTrade’s pipelines with a stable, battle-tested wrapper.

## What the Repo Provides (Evidence-Based)

The upstream README documents a “6-layer architecture” and “~21 endpoints” consolidating data across sources including mootdx, Tencent Finance, Eastmoney, akshare, iwencai, THS, Baidu, cninfo.

Key categories:

- Market data: mootdx (multi-period K lines, order book, ticks), Tencent valuation fields.
- Research: Eastmoney report list + PDF download, akshare consensus, iwencai NL search (requires API key).
- Signals: THS hot stocks + northbound flows, Baidu concepts + fund flows, 龙虎榜 + 全市场龙虎榜, 解禁日历, 行业对比.
- News: Eastmoney stock news, CLS flashes, global news.
- Fundamentals/filings: mootdx finance + F10, cninfo announcements.

Source: upstream README and SKILL.md in the repo root.

## Recommended Local Usage (NeoTrade)

### 1) Mirror the upstream Skill (fastest)

If you are using a “Skill-aware” assistant (Claude Code/Codex/OpenClaw), the upstream project provides a ready-to-use SKILL.md:

```bash
mkdir -p ~/.claude/skills/a-stock-data
curl -o ~/.claude/skills/a-stock-data/SKILL.md \
  https://raw.githubusercontent.com/simonlin1212/a-stock-data/main/SKILL.md
pip install mootdx akshare requests pandas stockstats
```

### 2) Integration checkpoints for NeoTrade

When integrating, keep these checkpoints explicit:

- Data contract: normalize stock_code format (6-digit) and date format (YYYY-MM-DD).
- Rate limits / stability: akshare/Eastmoney can be anti-bot; use retry + backoff and cache.
- Sensitive auth: iwencai NL requires API key; do not hardcode keys in repo.

## Practical “Drop-In” Targets

Good candidates to plug into NeoTrade:

- Replace/augment valuation data via Tencent Finance endpoint.
- Add “concept/industry attribution” and “fund flow” features for screeners/monitor pages.
- Add “龙虎榜/全市场龙虎榜” for event-driven watchlists.
- Add “研报 PDF” retrieval for qualitative context in audit cards.

## Notes

- The upstream repo is Apache-2.0 licensed (verify in LICENSE before redistribution).
- Prefer using it as an external dependency or mirrored skill, rather than copy-pasting large embedded code blocks into NeoTrade.

