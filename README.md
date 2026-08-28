# Mining Rights Daily Agent

An MCP-based mining rights daily brief Agent. It combines three independent MCP
servers:

- `mining-news-mcp`: mining news search and article fetch.
- `mineral-pdf-mcp`: NI 43-101 / technical-report resource extraction.
- `lme-price-mcp`: commodity price point and trend tools.

The Agent client accepts a request such as:

```text
给我生成一份关于 Pilbara 锂矿的今日简报
```

It returns a Markdown brief with news, resource data, price trend, risk notes,
data-quality notes, and source citations.

## Architecture

```text
Agent Client
  interpret -> plan -> concurrent MCP calls -> verify -> compose -> persist

MCP Servers
  mining-news-mcp      search(query, days), fetch_article(url)
  mineral-pdf-mcp      extract_resources(pdf_url)
  lme-price-mcp        get_price(commodity, date), get_trend(commodity, days)
```

## Engineering Choices

- Standard-library MCP stdio implementation for deterministic local review.
- Offline fixture mode for stable 5-minute interviews and CI.
- Async orchestration so independent tools run concurrently.
- Typed internal schemas with dataclasses and explicit JSON conversion.
- Citation validation: factual sections must be backed by sources.
- Degraded-mode reporting: failed or low-confidence tools are visible in output.
- PDF extraction separates page discovery, table/text parsing, normalization, and confidence.

## Why This Design

This is intentionally not a single prompt demo. Each data capability is isolated
behind MCP tool contracts, while the Agent only plans, validates, and composes.
That makes the system easier to test, replace, and connect to Claude Desktop or
Cursor.

## Limitations

The repository ships with reliable fixture-backed providers. Real provider
adapters are intentionally thin extension points because exchange data, premium
mining databases, and some price feeds often require credentials or have rate
limits. The system reports degraded mode instead of inventing missing data.

