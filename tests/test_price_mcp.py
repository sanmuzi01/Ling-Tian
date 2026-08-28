from __future__ import annotations

import unittest

from servers.lme_price_mcp.providers import CommodityPriceProvider


class PriceProviderTests(unittest.TestCase):
    def test_lithium_trend_has_metrics(self) -> None:
        provider = CommodityPriceProvider(offline=True)
        trend = provider.get_trend("lithium", days=7)
        self.assertEqual(trend["commodity"], "lithium")
        self.assertEqual(len(trend["points"]), 7)
        self.assertIn(trend["trend"], {"up", "down", "flat"})
        self.assertTrue(trend["citations"][0]["id"].startswith("S"))


if __name__ == "__main__":
    unittest.main()

