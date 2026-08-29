# Mining Rights Daily Agent

An MCP-based mining rights daily brief Agent. It combines four independent MCP
servers:

- `mining-news-mcp`: mining news search and article fetch.
- `mineral-pdf-mcp`: NI 43-101 / technical-report resource extraction.
- `lme-price-mcp`: commodity price point and trend tools.
- `mining-risk-mcp`: evidence-backed market, resource, operating, and policy risk assessment.

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
  mining-risk-mcp      assess_risks(topic, news, resources, prices)
```

## Vue 3 Frontend Demo

The repository includes a Vue 3 + Vite test console in `frontend/`. It
lets reviewers enter a brief request, run the Agent, and inspect execution
feedback:

- planned execution steps
- MCP tool progress
- delivery check for 4 MCP servers plus the Agent client
- crawl trace with both fetch time and source/article publish time
- total latency
- citation count
- warning count
- Markdown brief preview
- structured run JSON

Run it with:

```bash
python -m frontend.dev_server 8765
cd frontend
npm install
npm run dev
```

Then open `http://127.0.0.1:5173`. The Vue app calls the Python API server at
`http://127.0.0.1:8765/api/run`.

For a built static demo:

```bash
cd frontend
npm run build
cd ..
python -m frontend.dev_server 8765
```

Then open `http://127.0.0.1:8765`.

## Engineering Choices

- Standard-library MCP stdio implementation for deterministic local review.
- Live-first data providers with fixture fallback for stable 5-minute interviews and CI.
- Async orchestration so independent tools run concurrently.
- Typed internal schemas with dataclasses and explicit JSON conversion.
- Citation validation: factual sections must be backed by sources.
- Degraded-mode reporting: failed or low-confidence tools are visible in output.
- PDF extraction separates page discovery, table/text parsing, normalization, and confidence.

## Live Data Strategy

By default, the project attempts real collection before falling back:

- News: tries public MINING.COM RSS feeds, then public mining news index pages.
- Article fetch: downloads the live article page, extracts readable paragraph text,
  and records both crawler fetch time and article publish time when available.
- Prices: calls Yahoo Finance chart endpoints for publicly available commodity or commodity-proxy series.
- PDF: defaults to a live PLS Group annual-report PDF, scans candidate pages with `pdfplumber`, and extracts Indicated/Inferred rows when confidence is sufficient.
- Risk: derives a structured risk score from collected news, resource extraction status, and price trends through a separate MCP server.

Set `MINING_AGENT_OFFLINE=true` or pass `--offline` to force deterministic fixture mode. Override
`MINING_AGENT_PDF_URL` to test another technical report PDF:

```bash
MINING_AGENT_PDF_URL=https://example.com/report.pdf python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

## Why This Design

This is intentionally not a single prompt demo. Each data capability is isolated
behind MCP tool contracts, while the Agent only plans, validates, and composes.
That makes the system easier to test, replace, and connect to Claude Desktop or
Cursor.

## Limitations

Some mining publishers block automated access or require paid subscriptions, and
official exchange feeds may require credentials. The system therefore uses live
public sources where available and reports degraded mode instead of inventing
missing data.
