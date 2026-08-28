from __future__ import annotations

import asyncio
import unittest

from agent.daily_brief_agent import run_daily_brief
from shared.citations import cited_ids


class AgentE2ETests(unittest.TestCase):
    def test_agent_generates_cited_brief(self) -> None:
        result = asyncio.run(run_daily_brief("给我生成一份关于 Pilbara 锂矿的今日简报"))
        self.assertIn("Pilbara lithium", result.topic)
        self.assertIn("## 2. 新闻动态", result.markdown)
        self.assertIn("## 3. 资源量 / 储量信息", result.markdown)
        self.assertIn("## 4. 价格走势", result.markdown)
        self.assertGreaterEqual(len(cited_ids(result.markdown)), 5)
        self.assertEqual(result.run_report["warning_count"], len(result.warnings))


if __name__ == "__main__":
    unittest.main()

