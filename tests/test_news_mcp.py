from __future__ import annotations

import unittest

from servers.mining_news_mcp.sources import MiningNewsService


class MiningNewsTests(unittest.TestCase):
    def test_search_returns_ranked_hits(self) -> None:
        service = MiningNewsService(offline=True)
        hits = service.search("Pilbara lithium", days=7)
        self.assertGreaterEqual(len(hits), 3)
        self.assertTrue(all(hit.citation_id.startswith("S") for hit in hits))

    def test_fetch_article_returns_citation(self) -> None:
        service = MiningNewsService(offline=True)
        hit = service.search("Pilbara lithium", days=7)[0]
        article = service.fetch_article(hit.url)
        self.assertEqual(article.url, hit.url)
        self.assertEqual(len(article.citations), 1)


if __name__ == "__main__":
    unittest.main()

