![Uploading image.png…]()

# Mining Rights Daily Agent

一个基于 MCP (Model Context Protocol) 的“矿权日报”Agent。项目面向面试题要求实现：多个 MCP server 提供独立数据能力，一个 Agent client 负责规划、编排、校验和生成 Markdown 简报，并提供 Vue 3 前端用于演示执行过程。

默认输入示例：

```text
给我生成一份关于 Pilbara 锂矿的今日简报
```

输出内容包括新闻摘要、资源量 / 储量数据、价格走势、风险提示、数据完整性说明和引用来源链接。

## Highlights

- **4 个 MCP server + 1 个 Agent client**：超过题目“至少 3 个 MCP server”的要求。
- **真实数据优先**：默认 live-first，优先爬取公开新闻、PDF 报告和行情接口，失败时才进入 fixture fallback。
- **运行轨迹监测**：每个爬取页面 / 接口调用都记录 `fetched_at`，并尽量解析源内容的 `published_at`。
- **可验证引用**：Markdown 简报中的事实性内容带来源编号，结构化 JSON 保留完整引用链。
- **Vue 3 演示页面**：支持中文页面、执行反馈、MCP 工具耗时、交付核验、运行轨迹、价格趋势折线图、Markdown/JSON 查看。
- **工程化交付**：包含 `RUN.md`、`mcp-config.json`、`docker-compose.yml`、测试、示例输出和 `.gitignore`。

## Deliverables

| 类型 | 路径 | 说明 |
|---|---|---|
| Agent client | `agent/daily_brief_agent.py` | 主流程编排、MCP 调用、引用校验、Markdown 输出 |
| News MCP | `servers/mining_news_mcp/` | `search(query, days)`、`fetch_article(url)` |
| PDF MCP | `servers/mineral_pdf_mcp/` | `extract_resources(pdf_url)` |
| Price MCP | `servers/lme_price_mcp/` | `get_price(commodity, date)`、`get_trend(commodity, days)` |
| Risk MCP | `servers/mining_risk_mcp/` | `assess_risks(topic, news, resources, prices)` |
| MCP 配置 | `mcp-config.json` | 可接入 Claude Desktop / Cursor |
| 运行说明 | `RUN.md` | 5 分钟内跑起来，含 `docker compose up --build` |
| 前端 | `frontend/` | Vue 3 + Vite 演示控制台 |
| 示例输出 | `examples/` | Markdown 和 JSON 样例 |
| 测试 | `tests/` | MCP、Agent、数据解析测试 |

## Architecture

```text
User Query
   |
   v
Agent Client: agent.daily_brief_agent
   |
   |-- mining-news-mcp.search(query, days)
   |-- mining-news-mcp.fetch_article(url)
   |-- mineral-pdf-mcp.extract_resources(pdf_url)
   |-- lme-price-mcp.get_trend(commodity, days)
   |-- mining-risk-mcp.assess_risks(topic, news, resources, prices)
   |
   v
Verifier -> Composer -> Markdown Brief + Structured JSON
```

核心设计思路是把数据能力隔离在 MCP server 后面，Agent client 只做意图解析、并发编排、降级处理、引用校验和报告生成。这样每个数据源都可以单独替换、单独测试，也方便接入 Claude Desktop 或 Cursor。

## MCP Servers

### `mining-news-mcp`

新闻聚合 MCP server。

工具：

- `search(query, days)`：搜索矿业新闻，返回标题、URL、来源、发布时间、抓取时间、摘要、相关性分数。
- `fetch_article(url)`：抓取文章正文，解析可读文本，并从 HTML 中提取 `article:published_time`、`datePublished`、`time datetime` 或 URL 日期。

### `mineral-pdf-mcp`

技术报告 / NI 43-101 类 PDF 解析 MCP server。

工具：

- `extract_resources(pdf_url)`：下载 PDF，扫描候选页面，抽取 Indicated / Inferred 资源量记录，返回页码、置信度、引用和运行轨迹。

### `lme-price-mcp`

价格行情 MCP server。

工具：

- `get_price(commodity, date)`：获取指定日期价格点。
- `get_trend(commodity, days)`：获取价格时间序列、涨跌幅、波动率和趋势方向。

当前 live 数据使用 Yahoo Finance 公开 chart 接口作为公开可访问的商品 / 商品链代理数据源。

### `mining-risk-mcp`

风险分析 MCP server。

工具：

- `assess_risks(topic, news, resources, prices)`：基于新闻、PDF 抽取状态和价格走势生成市场价格、资源量可信度、运营执行、政策许可四类风险评分。

## Quick Start

完整运行说明见 [RUN.md](./RUN.md)。

本地直接运行：

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

保存 Markdown 和 JSON：

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" \
  --output examples/pilbara_lithium_generated.md \
  --json-output examples/pilbara_lithium_generated.json
```

Docker Compose 一条命令：

```bash
docker compose up --build
```

## Vue 3 Frontend

前端位于 `frontend/`，用于面试演示和功能验收。

启动 Python API / 静态服务：

```bash
python -m frontend.dev_server 8765
```

启动 Vue 3 开发服务：

```bash
cd frontend
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

也可以构建后由 Python 服务直接托管：

```bash
cd frontend
npm install
npm run build
cd ..
python -m frontend.dev_server 8765
```

打开：

```text
http://127.0.0.1:8765
```

页面包含：

- 运行轨迹监测，展示抓取时间和发布时间
- Agent 执行链路
- MCP 工具耗时
- 4 MCP server + 1 Agent client 交付核验
- 数据覆盖统计
- 新闻证据流
- PDF 资源量抽取结果
- 价格趋势折线图
- Markdown 简报和结构化 JSON

## Connect to Claude Desktop / Cursor

项目提供 `mcp-config.json`：

```json
{
  "mcpServers": {
    "mining-news-mcp": {
      "command": "python",
      "args": ["-m", "servers.mining_news_mcp.server"],
      "cwd": "."
    },
    "mineral-pdf-mcp": {
      "command": "python",
      "args": ["-m", "servers.mineral_pdf_mcp.server"],
      "cwd": "."
    },
    "lme-price-mcp": {
      "command": "python",
      "args": ["-m", "servers.lme_price_mcp.server"],
      "cwd": "."
    },
    "mining-risk-mcp": {
      "command": "python",
      "args": ["-m", "servers.mining_risk_mcp.server"],
      "cwd": "."
    }
  }
}
```

如果客户端不支持相对 `cwd`，把 `cwd` 改为项目绝对路径即可。

## Configuration

`.env.example` 提供默认配置：

```env
MINING_AGENT_OFFLINE=false
MINING_AGENT_STRICT_CITATIONS=true
MINING_AGENT_TIMEOUT_SECONDS=30
MINING_AGENT_PDF_URL=https://cdn.financialreports.eu/financialreports/media/filings/65576/2026/RNS/65576_rns_2026-08-23_c3d18a66-1f27-477f-92de-45222c0b4f78.pdf
```

常用环境变量：

- `MINING_AGENT_OFFLINE=false`：默认 live-first，优先真实爬取。
- `MINING_AGENT_OFFLINE=true`：强制使用 fixture，适合无网络演示或 CI。
- `MINING_AGENT_PDF_URL=...`：替换技术报告 PDF 地址。

## Data Strategy

默认情况下，系统按 live-first 策略运行：

- 新闻：抓取公开矿业新闻页面、搜索页和 RSS。
- 正文：下载真实文章页并抽取正文、发布时间和抓取时间。
- PDF：下载真实技术报告 PDF，扫描资源量相关页面并解析 Indicated / Inferred。
- 行情：调用公开行情接口获取近 7 日时间序列。
- 风险：用独立 MCP server 基于前面证据生成结构化风险评分。

如果实时源不可访问、超时或被目标站点拦截，系统会使用 fixture fallback，并在运行报告、页面 badge、数据完整性说明中暴露，不会伪装成实时数据。

## Output Shape

Markdown 简报包含：

- 执行摘要
- 资产动态与新闻证据
- 资源量 / 储量信息
- 价格走势
- 风险提示
- 数据完整性说明
- 引用来源

JSON 输出包含：

- `news`
- `resources`
- `prices`
- `risks`
- `citations`
- `warnings`
- `run_report`
- `evidence_summary`

其中 `run_report.crawl_trace` 会记录每个爬取页面或接口调用：

```json
{
  "tool": "mining-news-mcp.fetch_article",
  "source": "live:html:mining.com",
  "url": "https://www.mining.com/...",
  "title": "Pilbara Minerals ...",
  "published_at": "2024-08-25T23:02:12+00:00",
  "fetched_at": "2026-08-29T01:06:04Z",
  "status": "ok"
}
```

## Tests

运行全部测试：

```bash
python -m unittest discover -s tests
```

检查 MCP server 工具列表：

```bash
python -m shared.mcp_smoke servers.mining_news_mcp.server
python -m shared.mcp_smoke servers.mineral_pdf_mcp.server
python -m shared.mcp_smoke servers.lme_price_mcp.server
python -m shared.mcp_smoke servers.mining_risk_mcp.server
```

前端构建：

```bash
cd frontend
npm install
npm run build
```

## Project Structure

```text
.
├── agent/                  # Agent client orchestration
├── servers/                # MCP servers
│   ├── mining_news_mcp/
│   ├── mineral_pdf_mcp/
│   ├── lme_price_mcp/
│   └── mining_risk_mcp/
├── shared/                 # MCP stdio runtime, schemas, cache, HTTP helpers
├── frontend/               # Vue 3 demo console
├── data/                   # fixtures and local cache
├── examples/               # sample Markdown / JSON outputs
├── tests/                  # unit and e2e tests
├── mcp-config.json
├── docker-compose.yml
├── RUN.md
└── README.md
```

## Notes and Limitations

- 部分新闻网站可能会对自动化访问返回 403 或限流；项目会透明降级并给出 warning。
- 公开交易所实时数据通常需要凭证，本项目使用公开可访问行情接口或商品链代理指标进行演示。
- PDF 资源量抽取依赖原报告排版，低置信度记录会在输出中提示人工复核。
- 本项目用于工程能力和 Agent 编排演示，不构成投资建议。
