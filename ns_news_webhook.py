"""Poll NationStates announcements and post newly seen items to Discord."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.nationstates.net/page=news"
DB_PATH = Path(__file__).resolve().parent / ".state" / "announcements.sqlite3"
LOG = logging.getLogger("ns-news-webhook")


@dataclass(frozen=True)
class Announcement:
    key: str
    title: str
    url: str
    summary: str


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _preview(container: Tag) -> str:
    for paragraph in container.find_all("p"):
        classes = paragraph.get("class", [])
        if any("author" in class_name.lower() for class_name in classes):
            continue
        text = _clean(paragraph.get_text(" ", strip=True))
        if text and not text.lower().startswith("by "):
            return text
    return ""


def parse_announcements(html: str, page_url: str) -> list[Announcement]:
    """Extract announcement entries from common article/list markup.

    Links/headings define entries; adjacent paragraph text is used as a short
    preview. URL-backed IDs remain stable if the page's wording changes.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Tag] = []
    for node in soup.select("article, .announcement, .news-item, .news, .article"):
        if isinstance(node, Tag):
            candidates.append(node)

    entries: list[Announcement] = []
    seen: set[str] = set()
    if candidates:
        for container in candidates:
            heading = container.find(["h2", "h3", "h4"])
            link = heading.find("a", href=True) if heading else container.find("a", href=True)
            title = _clean(heading.get_text(" ", strip=True) if heading else (link.get_text(" ", strip=True) if link else ""))
            if not title or not link:
                continue
            href = urljoin(page_url, str(link.get("href", "")))
            if not _is_site_url(href, page_url):
                continue
            summary = _preview(container)
            item = _announcement(title, href, summary)
            if item.key not in seen:
                seen.add(item.key)
                entries.append(item)
    else:
        # Fallback for pages without semantic article containers: use linked
        # headings and their nearest containing block.
        for heading in soup.find_all(["h2", "h3", "h4"]):
            link = heading.find("a", href=True) or heading.find_parent("a", href=True)
            if not link:
                continue
            title = _clean(heading.get_text(" ", strip=True))
            href = urljoin(page_url, str(link.get("href", "")))
            if not title or not _is_site_url(href, page_url):
                continue
            # The NationStates news page uses one outer #newspage container
            # with repeated heading + .newsstory sibling pairs. Never search
            # that outer container for a paragraph or every post gets its first byline.
            story = heading.find_next_sibling(class_="newsstory")
            container = story if isinstance(story, Tag) else heading.parent
            summary = _preview(container) if isinstance(container, Tag) else ""
            item = _announcement(title, href, summary)
            if item.key not in seen:
                seen.add(item.key)
                entries.append(item)
    return entries


def _is_site_url(url: str, page_url: str) -> bool:
    return urlparse(url).netloc.lower().endswith("nationstates.net") and urlparse(page_url).scheme in {"http", "https"}


def _announcement(title: str, url: str, summary: str) -> Announcement:
    identity = url.split("#", 1)[0].rstrip("/") or url
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return Announcement(key, title, url, summary)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute("""CREATE TABLE IF NOT EXISTS announcements (
        key TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
        summary TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0
    )""")
    return db


def _discord_payload(item: Announcement) -> dict[str, object]:
    embed: dict[str, object] = {
        "title": item.title[:256],
        "url": item.url,
        "color": 0x376FA3,
    }
    if item.summary:
        embed["description"] = item.summary[:4096]
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def _fetch_with_chromium(page_url: str, user_agent: str) -> tuple[str, str]:
    """Fetch the page in standard headless Chromium; direct HTTP gets 403."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=user_agent)
                page = context.new_page()
                response = page.goto(page_url, wait_until="domcontentloaded", timeout=45_000)
                if response is None:
                    raise RuntimeError("Chromium did not receive a page response")
                if response.status >= 400:
                    raise RuntimeError(f"Chromium received HTTP {response.status}")
                return page.content(), page.url
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise RuntimeError(f"Chromium fetch failed: {exc}") from exc


def run() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook or "discord.com/api/webhooks/" not in webhook:
        LOG.error("Set a valid DISCORD_WEBHOOK_URL in .env")
        return 2

    page_url = os.getenv("NATIONSTATES_NEWS_URL", BASE_URL).strip()
    # Match the Chromium version installed by Playwright when no override is set.
    user_agent = os.getenv("NATIONSTATES_USER_AGENT", "").strip() or (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/159.0.0.0 Safari/537.36"
    )
    try:
        # NationStates returns 403 to our plain HTTP client, so use Chromium
        # for the news-page fetch rather than making a doomed preliminary request.
        html, resolved_url = _fetch_with_chromium(page_url, user_agent)
        items = parse_announcements(html, resolved_url)
        if not items:
            LOG.warning("No announcements found; page markup may have changed")
            return 0

        with httpx.Client(timeout=30) as client, _connect() as db:
            db.executemany(
                "INSERT OR IGNORE INTO announcements(key,title,url,summary) VALUES(?,?,?,?)",
                [(i.key, i.title, i.url, i.summary) for i in items],
            )
            pending = db.execute("SELECT key,title,url,summary FROM announcements WHERE sent=0 ORDER BY rowid").fetchall()
            for key, title, url, summary in pending:
                result = client.post(webhook, json=_discord_payload(Announcement(key, title, url, summary)))
                result.raise_for_status()
                db.execute("UPDATE announcements SET sent=1 WHERE key=?", (key,))
                LOG.info("Posted: %s", title)
        return 0
    except (httpx.HTTPError, sqlite3.Error, RuntimeError) as exc:
        LOG.error("Polling failed: %s", exc)
        return 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run())


if __name__ == "__main__":
    main()
