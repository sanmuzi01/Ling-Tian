from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from statistics import pstdev

from shared.cache import JsonCache, stable_key
from shared.config import FIXTURE_DIR
from shared.http import FetchError, fetch_text, utc_now


YAHOO_SYMBOLS = {
    "copper": ("HG=F", "COMEX copper futures continuous contract"),
    "lithium": ("LIT", "Global X Lithium & Battery Tech ETF proxy for lithium chain"),
    "nickel": ("NIKL.L", "London-listed nickel ETF proxy"),
    "zinc": ("ZNC=F", "Zinc futures proxy"),
}


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

    def _live_series(self, commodity: str, days: int) -> dict:
        key = commodity.lower().replace("锂", "lithium")
        if key not in YAHOO_SYMBOLS:
            raise ValueError(f"Unsupported commodity: {commodity}")
        symbol, title = YAHOO_SYMBOLS[key]
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={max(days, 7)}d&interval=1d"
        fetched_at = utc_now()
        published_at = datetime.now(timezone.utc).isoformat()
        payload = json.loads(fetch_text(url, timeout=12))
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise FetchError(f"Yahoo chart returned no result for {symbol}")
        timestamps = result.get("timestamp") or []
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quote.get("close") or []
        meta = result.get("meta", {})
        points = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            points.append(
                {
                    "date": datetime.fromtimestamp(ts, timezone.utc).date().isoformat(),
                    "price": round(float(close), 4),
                }
            )
        if len(points) < 2:
            raise FetchError(f"Not enough live price points for {symbol}")
        return {
            "currency": meta.get("currency") or "USD",
            "unit": "contract/share",
            "source": {
                "id": {"lithium": "S31", "copper": "S32", "nickel": "S33"}.get(key, "S34"),
                "title": title,
                "url": url,
                "source": "live:yahoo-chart",
                "published_at": published_at,
                "fetched_at": fetched_at,
            },
            "points": points[-days:],
            "trace": [
                {
                    "tool": "lme-price-mcp.get_trend",
                    "source": "live:yahoo-chart",
                    "url": url,
                    "published_at": published_at,
                    "fetched_at": fetched_at,
                    "status": "ok",
                }
            ],
        }

    def get_price(self, commodity: str, date: str) -> dict:
        try:
            series = self._series(commodity) if self.offline else self._live_series(commodity, days=30)
        except Exception:
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
        cache_key = stable_key("trend:v6", commodity.lower(), str(days), str(self.offline))
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        try:
            series = self._series(commodity) if self.offline else self._live_series(commodity, days)
        except Exception:
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
            "trace": series.get(
                "trace",
                [
                    {
                        "tool": "lme-price-mcp.get_trend",
                        "source": series["source"]["source"],
                        "url": series["source"]["url"],
                        "published_at": series["source"].get("published_at"),
                        "fetched_at": series["source"].get("fetched_at") or utc_now(),
                        "status": "fallback"
                        if str(series["source"]["source"]).startswith("fixture:")
                        else "ok",
                    }
                ],
            ),
        }
        self.cache.set(cache_key, result)
        return result
