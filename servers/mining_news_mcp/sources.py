from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from shared.cache import JsonCache, stable_key
from shared.config import FIXTURE_DIR
from shared.schemas import Article, Citation, NewsHit, to_json


def _load_fixture() -> list[dict]:
    path = FIXTURE_DIR / "news" / "pilbara_lithium.json"
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.")


class MiningNewsService:
    def __init__(self, offline: bool = True) -> None:
        self.offline = offline
        self.cache = JsonCache("news")

    def search(self, query: str, days: int = 7) -> list[NewsHit]:
        cache_key = stable_key("search:v2", query.lower(), str(days), str(self.offline))
        cached = self.cache.get(cache_key)
        if cached:
            return [NewsHit(**item) for item in cached]

        terms = {token.lower() for token in query.replace("锂", "lithium").split() if token}
        hits: list[NewsHit] = []
        for idx, item in enumerate(_load_fixture(), start=1):
            haystack = f"{item['title']} {item['snippet']} {item['text']}".lower()
            matches = sum(1 for term in terms if term in haystack)
            score = 0.55 + min(0.4, matches * 0.1)
            if matches or "pilbara" in haystack or not terms:
                hits.append(
                    NewsHit(
                        title=item["title"],
                        url=item["url"],
                        source=item["source"],
                        published_at=item["published_at"],
                        snippet=item["snippet"],
                        score=round(score, 3),
                        citation_id=f"S{idx}",
                    )
                )
        hits.sort(key=lambda hit: (hit.published_at, hit.score), reverse=True)
        self.cache.set(cache_key, [hit.__dict__ for hit in hits])
        return hits

    def fetch_article(self, url: str) -> Article:
        cache_key = stable_key("article", url)
        cached = self.cache.get(cache_key)
        if cached:
            citations = [Citation(**item) for item in cached.pop("citations")]
            return Article(citations=citations, **cached)

        for idx, item in enumerate(_load_fixture(), start=1):
            if item["url"] == url:
                citation = Citation(
                    id=f"S{idx}",
                    title=item["title"],
                    url=item["url"],
                    source=item["source"],
                    published_at=item["published_at"],
                )
                article = Article(
                    title=item["title"],
                    url=item["url"],
                    source=item["source"],
                    published_at=item["published_at"],
                    text=item["text"],
                    authors=item.get("authors", []),
                    citations=[citation],
                )
                self.cache.set(cache_key, to_json(article))
                return article
        raise ValueError(f"Article not found: {url}")
