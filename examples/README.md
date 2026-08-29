# Examples

Run:

```bash
python -m agent.daily_brief_agent "给我生成一份关于 Pilbara 锂矿的今日简报" \
  --output examples/pilbara_lithium_brief.md \
  --json-output examples/pilbara_lithium_brief.json
```

Use `--offline` only when you want deterministic fixture output for CI or demos
without network access.
