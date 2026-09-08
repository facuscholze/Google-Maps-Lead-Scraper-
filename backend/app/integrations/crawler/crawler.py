"""Responsible, limited website crawler (spec §16).

- httpx + BeautifulSoup + trafilatura (no browser automation by default)
- honors robots.txt (real hosts)
- per-domain page cap (MAX_PAGES_PER_DOMAIN), size cap, redirect cap, delays
- virtual host `mockbusiness.local` is served from deterministic fixtures so
  tests and the offline demo never touch the network
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import urllib.parse
from collections import deque
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.integrations import mock_fixtures
from app.services.analysis.types import PageData

logger = logging.getLogger("avascho.crawler")

PRIORITY_PREFIXES = [
    "/", "/contacto", "/contact", "/about", "/about-us", "/nosotros",
    "/servicios", "/services", "/booking", "/reservas", "/pricing", "/precios",
]


def normalize_url(value: str) -> str:
    value = value.strip()
    if not re.match(r"^https?://", value, re.I):
        value = "http://" + value
    return value


def host_of(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def _is_virtual(url: str) -> bool:
    return host_of(url) in ("mockbusiness.local", "mockbusiness.local:80")


def sha256_of(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", "replace"))
    return h.hexdigest()


def content_hash_of(pages: list[PageData]) -> str:
    joined = "".join(f"{p.url}\n{p.http_status}\n{p.html}" for p in sorted(pages, key=lambda x: x.url))
    return sha256_of(joined)


class VirtualSiteResolver:
    """Serves the deterministic mock sites (offline)."""

    def fetch(self, url: str) -> tuple[str, int, str]:
        parsed = urllib.parse.urlparse(url)
        slug = parsed.path.strip("/").split("/")[0] or None
        if not slug or mock_fixtures.get_profile_for_slug(slug) is None:
            return "<html><body><h1>404 Not Found</h1></body></html>", 404, url
        path = parsed.path or "/"
        html, status = mock_fixtures.render_site(slug, path)
        return html, status, url


class HttpFetcher:
    """Fetches real pages with httpx, obeying robots.txt and size caps."""

    def __init__(self) -> None:
        self._robots: dict[str, RobotFileParser] = {}
        timeout = httpx.Timeout(settings.http_timeout_seconds)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=settings.max_redirects,
            headers={
                "User-Agent": "AvaSchoLeadIntelligenceBot/0.1 (+responsible internal research; contact avascho)"
            },
            http2=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _allowed(self, url: str) -> bool:
        host = host_of(url)
        robots = self._robots.get(host)
        if robots is None:
            robots = RobotFileParser()
            robots.set_url(f"https://{host}/robots.txt")
            try:
                robots.read()
            except Exception:  # noqa: BLE001
                robots = RobotFileParser()  # allow when robots cannot be read
                robots.parse([])
            self._robots[host] = robots
        return robots.can_fetch("*", url)

    async def fetch(self, url: str) -> tuple[str, int, str, list[str]]:
        if not self._allowed(url):
            raise CrawlBlockedError(url)
        response = await self._client.get(url)
        html_content = response.text
        if len(html_content.encode("utf-8", "replace")) > settings.max_page_size_bytes:
            html_content = html_content[: settings.max_page_size_bytes]
        links = extract_links(html_content, url)
        return html_content, response.status_code, str(response.url), links


class CrawlBlockedError(Exception):
    def __init__(self, url: str) -> None:
        super().__init__(f"Blocked by robots.txt: {url}")
        self.url = url


def extract_links(html_content: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html_content, "lxml")
    out: list[str] = []
    base_parsed = urllib.parse.urlparse(base_url)
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        resolved = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(resolved)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.lower() != base_parsed.netloc.lower():
            continue  # same-domain only
        # drop fragments & dedupe
        clean = urllib.parse.urlunparse(parsed._replace(fragment=""))
        if clean not in out:
            out.append(clean)
    return out


def sort_pages(urls: list[str]) -> list[str]:
    """Prioritize valuable pages (spec §16)."""

    def rank(url: str) -> int:
        path = urllib.parse.urlparse(url).path.lower()
        for i, prefix in enumerate(PRIORITY_PREFIXES):
            if path == prefix or path.startswith(prefix + "/"):
                return i
        return len(PRIORITY_PREFIXES)

    return sorted(urls, key=rank)


def classify_path(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    if path in ("/", "") or path.endswith(("index.html", "index.htm")):
        return "home"
    for frag, kind in (
        (("/contact", "/contacto"), "contact"),
        (("/about", "/nosotros", "/quienes"), "about"),
        (("/servicios", "/services", "/tratamientos"), "services"),
        (("/booking", "/reserv", "/turno", "/agenda", "/cita", "/schedule"), "booking"),
        (("/pricing", "/precios", "/tarifas"), "pricing"),
    ):
        if path.startswith(frag):
            return kind
    return "other"


class WebsiteCrawler:
    """Crawls a domain responsibly and returns parsed PageData items."""

    async def crawl_async(self, website_url: str, max_pages: int | None = None) -> list[PageData]:
        url = normalize_url(website_url)
        max_pages = min(max_pages or settings.max_pages_per_domain, settings.max_pages_per_domain)
        if _is_virtual(url):
            return self._crawl_virtual(url, max_pages)

        fetcher = HttpFetcher()
        try:
            return await self._crawl_http(fetcher, url, max_pages)
        finally:
            await fetcher.close()

    def _crawl_virtual(self, url: str, max_pages: int) -> list[PageData]:
        resolver = VirtualSiteResolver()
        slug = urllib.parse.urlparse(url).path.strip("/").split("/")[0]
        pages: list[PageData] = []
        for path in mock_fixtures.site_pages(slug):
            page_url = f"http://mockbusiness.local/{slug}{path}"
            html, status, final = resolver.fetch(page_url)
            if status == 404 and path != "/":
                continue
            pages.append(
                self._to_pagedata(page_url, final, status, html, extract_links(html, page_url))
            )
            if len(pages) >= max_pages:
                break
        return pages

    async def _crawl_http(self, fetcher: HttpFetcher, url: str, max_pages: int) -> list[PageData]:
        pages: list[PageData] = []
        seen: set[str] = set()
        queue: deque[str] = deque([url])
        origin = host_of(url)
        while queue and len(pages) < max_pages:
            current = queue.popleft()
            if current in seen or host_of(current) != origin:
                continue
            seen.add(current)
            try:
                html, status, final_url, links = await fetcher.fetch(current)
                time.sleep(settings.crawl_delay_seconds)  # polite throttle
                page = self._to_pagedata(current, final_url, status, html, links)
                pages.append(page)
                for link in sort_pages(links):
                    if len(seen) >= max_pages * 4:
                        break
                    if link not in seen and host_of(link) == origin:
                        queue.append(link)
            except CrawlBlockedError:
                continue
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.info("crawl error %s -> %s", current, exc)
                continue
            if len(pages) >= max_pages:
                break
        return pages

    def crawl(self, website_url: str, max_pages: int | None = None) -> list[PageData]:
        return asyncio.run(self.crawl_async(website_url, max_pages))

    @staticmethod
    def _to_pagedata(
        url: str, final_url: str, status: int, html_content: str, links: list[str]
    ) -> PageData:
        text = extract_main_text(html_content)
        title = extract_title(html_content)
        return PageData(
            url=url,
            http_status=status,
            title=title,
            html=html_content,
            text=text,
            links=links,
            kind=classify_path(final_url or url),
        )


def extract_main_text(html_content: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(html_content, include_comments=False, include_tables=False)
        if extracted:
            return re.sub(r"\s+", " ", extracted).strip()
    except Exception:  # noqa: BLE001
        pass
    soup = BeautifulSoup(html_content, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def extract_title(html_content: str) -> str | None:
    soup = BeautifulSoup(html_content, "lxml")
    if soup.title and soup.title.string:
        return re.sub(r"\s+", " ", soup.title.string).strip()
    return None
