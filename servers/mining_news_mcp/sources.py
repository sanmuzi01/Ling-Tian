from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from shared.cache import JsonCache, stable_key
from shared.config import FIXTURE_DIR
from shared.http import FetchError, fetch_text, utc_now
from shared.schemas import Article, Citation, NewsHit, to_json

RSS_FEEDS = [
    "https://www.mining.com/feed/",
    "https://www.mining.com/commodity/lithium/feed/",
    "https://www.mining.com/commodity/copper/feed/",
]

HTML_INDEXES = [
    "https://www.azomining.com/news-index.aspx",
    "https://www.mining.com/",
]

FOCUSED_PILBARA_SOURCES = [
    {
        "url": "https://www.pls.com/assets/pilgangoora-operation",
        "source": "live:company-page:pls.com",
        "title_hint": "Pilgangoora Operation asset page",
    },
    {
        "url": "https://financialfilings.com/filings/pls-group-limited/annual-report/2026/57388515/",
        "source": "live:filing:financialfilings.com",
        "title_hint": "PLS Group Limited Annual Report 2026",
    },
]


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
        cache_key = stable_key("search:v7", query.lower(), str(days), str(self.offline))
        cached = self.cache.get(cache_key)
        if cached:
            return [NewsHit(**item) for item in cached]

        hits = [] if self.offline else self._live_search(query, days)
        if hits:
            self.cache.set(cache_key, [hit.__dict__ for hit in hits])
            return hits

        hits = self._fixture_search(query)
        self.cache.set(cache_key, [hit.__dict__ for hit in hits])
        return hits

    def _fixture_search(self, query: str) -> list[NewsHit]:
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
                        fetched_at=utc_now(),
                    )
                )
        hits.sort(key=lambda hit: (hit.published_at, hit.score), reverse=True)
        return hits

    def _live_search(self, query: str, days: int) -> list[NewsHit]:
        candidates: list[dict] = []
        if _is_pilbara_query(query):
            for source in FOCUSED_PILBARA_SOURCES:
                try:
                    candidates.append(self._parse_focused_page(source["url"], source["source"], source["title_hint"]))
                except Exception:
                    continue
            for url in [
                "https://www.mining.com/?s=Pilgangoora",
                "https://www.mining.com/?s=Pilbara%20Minerals",
                "https://www.miningweekly.com/searchadvanced_mw.php?searchString=Pilgangoora",
            ]:
                try:
                    candidates.extend(self._parse_html_index(url))
                except Exception:
                    continue

        for feed_url in RSS_FEEDS:
            try:
                candidates.extend(self._parse_rss(feed_url))
            except Exception:
                continue
        if len(candidates) < 3:
            for url in HTML_INDEXES:
                try:
                    candidates.extend(self._parse_html_index(url))
                except Exception:
                    continue

        terms = _query_terms(query)
        deduped: dict[str, dict] = {}
        for item in candidates:
            url = item.get("url", "")
            if not url.startswith("http"):
                continue
            score = _relevance_score(query, item)
            if score >= 0.34 or len(deduped) < 5:
                existing = deduped.get(url)
                if not existing or score > existing["score"]:
                    item["score"] = round(score, 3)
                    deduped[url] = item

        hits: list[NewsHit] = []
        ranked = sorted(deduped.values(), key=lambda x: (x["score"], x["published_at"]), reverse=True)
        for idx, item in enumerate(ranked, start=1):
            hits.append(
                NewsHit(
                    title=item["title"],
                    url=item["url"],
                    source=item["source"],
                    published_at=item["published_at"],
                    snippet=item["snippet"],
                    score=item["score"],
                    citation_id=f"S{idx}",
                    fetched_at=item.get("fetched_at"),
                )
            )
            if len(hits) >= 10:
                break
        return hits

    def _parse_focused_page(self, page_url: str, source: str, title_hint: str) -> dict:
        fetched_at = utc_now()
        html = fetch_text(page_url, timeout=15)
        title = _extract_title(html) or title_hint
        text = _extract_readable_text(html)
        snippet = _best_snippet(text, ["Pilgangoora", "lithium", "Mineral Resource", "spodumene"])
        return {
            "title": title_hint if len(title) > 140 else title,
            "url": page_url,
            "source": source,
            "published_at": "2026-08-23T00:00:00Z" if "financialfilings" in page_url else "1970-01-01T00:00:00Z",
            "snippet": snippet,
            "fetched_at": fetched_at,
        }

    def _parse_rss(self, feed_url: str) -> list[dict]:
        fetched_at = utc_now()
        xml = fetch_text(feed_url, timeout=12)
        root = ET.fromstring(xml)
        items: list[dict] = []
        for item in root.findall(".//item"):
            title = _clean_html(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            description = _clean_html(item.findtext("description") or "")
            pub_date = _to_iso(item.findtext("pubDate"))
            if title and link:
                items.append(
                    {
                        "title": title,
                        "url": link,
                        "source": f"live:rss:{canonical_domain(feed_url)}",
                        "published_at": pub_date,
                        "snippet": description[:240],
                        "fetched_at": fetched_at,
                    }
                )
        return items

    def _parse_html_index(self, page_url: str) -> list[dict]:
        fetched_at = utc_now()
        html = fetch_text(page_url, timeout=12)
        items: list[dict] = []
        for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
            href, label = match.groups()
            title = _clean_html(label)
            if len(title) < 24:
                continue
            if href.startswith(("mailto:", "javascript:")):
                continue
            if not href.startswith("http"):
                domain = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
                href = domain + (href if href.startswith("/") else f"/{href}")
            lowered = f"{title} {href}".lower()
            if not any(word in lowered for word in ("mining", "minerals", "lithium", "copper", "nickel")):
                continue
            items.append(
                {
                    "title": title[:180],
                    "url": href,
                    "source": f"live:html:{canonical_domain(page_url)}",
                    "published_at": "1970-01-01T00:00:00Z",
                    "snippet": title[:240],
                    "fetched_at": fetched_at,
                }
            )
            if len(items) >= 20:
                break
        return items

    def fetch_article(self, url: str) -> Article:
        cache_key = stable_key("article:v4", url)
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
                    fetched_at=utc_now(),
                )
                article = Article(
                    title=item["title"],
                    url=item["url"],
                    source=item["source"],
                    published_at=item["published_at"],
                    text=item["text"],
                    authors=item.get("authors", []),
                    citations=[citation],
                    fetched_at=citation.fetched_at,
                )
                self.cache.set(cache_key, to_json(article))
                return article
        if self.offline:
            raise ValueError(f"Article not found: {url}")
        fetched_at = utc_now()
        html = fetch_text(url, timeout=15)
        title = _extract_title(html) or url
        text = _extract_readable_text(html)
        published_at = _extract_published_at(html, url)
        citation = Citation(
            id=f"S{stable_key('article-citation', url)[:4]}",
            title=title,
            url=url,
            source=f"live:html:{canonical_domain(url)}",
            published_at=published_at,
            fetched_at=fetched_at,
        )
        article = Article(
            title=title,
            url=url,
            source=citation.source,
            published_at=published_at or "",
            text=text,
            authors=[],
            citations=[citation],
            fetched_at=fetched_at,
        )
        self.cache.set(cache_key, to_json(article))
        return article


def _clean_html(value: str) -> str:
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_published_at(html: str, url: str = "") -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']pubdate["\'][^>]+content=["\']([^"\']+)["\']',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r"<time[^>]+datetime=[\"']([^\"']+)[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.I | re.S)
        if match:
            return match.group(1).strip()
    url_match = re.search(r"/(20\d{2})[-/](\d{2})[-/](\d{2})(?:/|-)", url)
    if url_match:
        year, month, day = url_match.groups()
        return f"{year}-{month}-{day}T00:00:00Z"
    return None


def _query_terms(query: str) -> set[str]:
    normalized = query.lower().replace("锂", "lithium").replace("矿", "mining")
    terms = {token for token in re.split(r"[^a-z0-9]+", normalized) if len(token) > 2}
    if "pilbara" in normalized:
        terms.update({"pilgangoora", "pls", "spodumene"})
    if "lithium" in normalized:
        terms.update({"li2o", "battery"})
    return terms


def _is_pilbara_query(query: str) -> bool:
    normalized = query.lower()
    return "pilbara" in normalized or "pilgangoora" in normalized or "皮尔巴拉" in query


def _relevance_score(query: str, item: dict) -> float:
    text = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('url', '')}".lower()
    terms = _query_terms(query)
    matches = sum(1 for term in terms if term in text)
    score = min(0.8, matches * 0.11)
    if any(term in text for term in ("pilbara", "pilgangoora", "pls.com")):
        score += 0.35
    if any(term in text for term in ("lithium", "spodumene", "li2o")):
        score += 0.2
    if "mining.com" in text:
        score += 0.05
    return min(score, 0.99)


def _best_snippet(text: str, keywords: list[str]) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?。])\s+", text)
    lowered_keywords = [keyword.lower() for keyword in keywords]
    ranked = sorted(
        sentences,
        key=lambda sentence: sum(1 for keyword in lowered_keywords if keyword in sentence.lower()),
        reverse=True,
    )
    snippet = ranked[0] if ranked else text
    return snippet[:260]


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return _clean_html(match.group(1)) if match else None


def _extract_readable_text(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>|<nav.*?</nav>|<footer.*?</footer>", " ", html, flags=re.I | re.S)
    chunks = re.findall(r"<p[^>]*>(.*?)</p>|<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.I | re.S)
    text = " ".join(_clean_html(" ".join(chunk)) for chunk in chunks)
    return text[:6000] if text else _clean_html(html)[:6000]


def _to_iso(value: str | None) -> str:
    if not value:
        return "1970-01-01T00:00:00Z"
    try:
        return parsedate_to_datetime(value).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return "1970-01-01T00:00:00Z"
