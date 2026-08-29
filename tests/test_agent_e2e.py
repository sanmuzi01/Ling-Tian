from __future__ import annotations

import asyncio
import os
import unittest

from agent.daily_brief_agent import run_daily_brief
from shared.citations import cited_ids


class AgentE2ETests(unittest.TestCase):
    def test_agent_generates_cited_brief(self) -> None:
        os.environ["MINING_AGENT_OFFLINE"] = "true"
        result = asyncio.run(run_daily_brief("给我生成一份关于 Pilbara 锂矿的今日简报"))
        self.assertIn("Pilbara lithium", result.topic)
        self.assertIn("## 2. 资产动态与新闻证据", result.markdown)
        self.assertIn("## 3. 资源量 / 储量信息", result.markdown)
        self.assertIn("## 4. 价格走势", result.markdown)
        self.assertGreaterEqual(len(cited_ids(result.markdown)), 5)
        self.assertEqual(result.run_report["warning_count"], len(result.warnings))
        self.assertGreaterEqual(len(result.run_report["crawl_trace"]), 4)
        for item in result.run_report["crawl_trace"]:
            self.assertTrue(item.get("tool"))
            self.assertTrue(item.get("url"))
            self.assertTrue(item.get("fetched_at"))
            self.assertIn("published_at", item)
        self.assertGreaterEqual(len(result.run_report["mcp_contract"]["servers"]), 4)
        self.assertEqual(
            result.run_report["mcp_contract"]["agent_client"],
            "agent.daily_brief_agent",
        )
        self.assertIn("risk_score", result.risks)


if __name__ == "__main__":
    unittest.main()
