# Run in 5 Minutes

## Option A: Local Python

From the project root:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" --offline
```

Save outputs:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" \
  --offline \
  --output examples/pilbara_lithium_generated.md \
  --json-output examples/pilbara_lithium_generated.json
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

The generated brief is written to:

```text
examples/pilbara_lithium_generated.md
examples/pilbara_lithium_generated.json
```

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
