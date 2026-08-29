# Run in 5 Minutes

## Option A: Local Python

From the project root:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

Optional: enable LLM composition before running:

```bash
set OPENAI_API_KEY=your_api_key_here
set MINING_AGENT_LLM_MODEL=gpt-5.6-luna
set MINING_AGENT_LLM_BASE_URL=https://api.openai.com/v1
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

Without `OPENAI_API_KEY`, the Agent automatically falls back to deterministic
template composition and still runs end-to-end.

You can also pass the model configuration directly:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" ^
  --llm-enabled ^
  --llm-model deepseek-chat ^
  --llm-base-url https://api.deepseek.com/v1 ^
  --llm-api-key your_api_key_here
```

Save outputs:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" \
  --output examples/pilbara_lithium_generated.md \
  --json-output examples/pilbara_lithium_generated.json
```

Force deterministic offline fixture mode:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" --offline
```

Use a real technical-report PDF URL:

```bash
set MINING_AGENT_PDF_URL=https://example.com/report.pdf
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

Run smoke tests without third-party dependencies:

```bash
python -m unittest discover -s tests
```

On Windows, if `python` is not in `PATH`, use `py -3` or the absolute path of
your Python executable. The project itself has no required third-party runtime
dependencies.

## Option B: Docker Compose

```bash
docker compose up --build
```

To enable the optional LLM layer with Docker Compose:

```bash
set OPENAI_API_KEY=your_api_key_here
set MINING_AGENT_LLM_MODEL=gpt-5.6-luna
set MINING_AGENT_LLM_BASE_URL=https://api.openai.com/v1
docker compose up --build
```

The generated brief is written to:

```text
examples/pilbara_lithium_generated.md
examples/pilbara_lithium_generated.json
```

## Option C: Vue 3 Frontend Test Console

Start the Python Agent API server:

```bash
python -m frontend.dev_server 8765
```

In another terminal, start the Vue 3 dev server:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Click `生成简报` to execute the Agent through the local `/api/run` endpoint. The
page shows step-by-step execution feedback, the 4 MCP server + 1 Agent client
delivery check, crawl trace rows with fetch time and publish time, latency,
citation count, warning count, LLM model configuration, Markdown output, and
structured JSON.

If you prefer a built static frontend:

```bash
cd frontend
npm run build
cd ..
python -m frontend.dev_server 8765
```

Then open `http://127.0.0.1:8765`.

## Connect to Claude Desktop or Cursor

Use `mcp-config.json`. If your client requires absolute paths, replace `cwd` with
the absolute project directory and keep the commands:

```json
{
  "command": "python",
  "args": ["-m", "servers.mining_news_mcp.server"]
}
```

## MCP Smoke Test

List tools from one server:

```bash
python -m shared.mcp_smoke servers.mining_news_mcp.server
```

Smoke-test the additional risk server:

```bash
python -m shared.mcp_smoke servers.mining_risk_mcp.server
```
