from __future__ import annotations

import unittest

from servers.mineral_pdf_mcp.extractor import MineralPdfExtractor


class MineralPdfTests(unittest.TestCase):
    def test_extract_resources_returns_indicated_and_inferred(self) -> None:
        extractor = MineralPdfExtractor(offline=True)
        result = extractor.extract_resources("fixture://pilbara-ni-43101")
        categories = {item["category"] for item in result["resources"]}
        self.assertIn("Indicated", categories)
        self.assertIn("Inferred", categories)
        self.assertGreaterEqual(min(item["confidence"] for item in result["resources"]), 0.8)


if __name__ == "__main__":
    unittest.main()

