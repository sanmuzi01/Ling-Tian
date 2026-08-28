from __future__ import annotations

import json
import math
from statistics import pstdev

from shared.cache import JsonCache, stable_key
from shared.config import FIXTURE_DIR


class CommodityPriceProvider:
    def __init__(self, offline: bool = True) -> None:
        self.offline = offline
        self.cache = JsonCache("prices")

    def _series(self, commodity: str) -> dict:
        data = json.loads(
            (FIXTURE_DIR / "prices" / "commodity_prices.json").read_text(encoding="utf-8")
        )
        key = commodity.lower().replace("锂", "lithium")
        if key not in data:
            raise ValueError(f"Unsupported commodity: {commodity}")
        return data[key]

    def get_price(self, commodity: str, date: str) -> dict:
        series = self._series(commodity)
        for point in series["points"]:
            if point["date"] == date:
                return {
                    "commodity": commodity.lower().replace("锂", "lithium"),
                    "date": point["date"],
                    "price": point["price"],
                    "currency": series["currency"],
                    "unit": series["unit"],
                    "citation_id": series["source"]["id"],
                }
        raise ValueError(f"No price for {commodity} on {date}")

    def get_trend(self, commodity: str, days: int = 7) -> dict:
        cache_key = stable_key("trend", commodity.lower(), str(days), str(self.offline))
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        series = self._series(commodity)
        points = series["points"][-days:]
        first = points[0]["price"]
        last = points[-1]["price"]
        change_pct = ((last - first) / first) * 100 if first else 0.0
        returns = [
            math.log(points[idx]["price"] / points[idx - 1]["price"])
            for idx in range(1, len(points))
            if points[idx - 1]["price"]
        ]
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        trend = "up" if change_pct > 1 else "down" if change_pct < -1 else "flat"
        commodity_key = commodity.lower().replace("锂", "lithium")
        result = {
            "commodity": commodity_key,
            "currency": series["currency"],
            "unit": series["unit"],
            "points": [
                {
                    "commodity": commodity_key,
                    "date": point["date"],
                    "price": point["price"],
                    "currency": series["currency"],
                    "unit": series["unit"],
                    "citation_id": series["source"]["id"],
                }
                for point in points
            ],
            "change_pct": round(change_pct, 2),
            "volatility": round(volatility, 4),
            "trend": trend,
            "citations": [series["source"]],
        }
        self.cache.set(cache_key, result)
        return result

