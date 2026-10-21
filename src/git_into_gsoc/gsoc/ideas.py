"""Fetch an org's ideas page as plain text (best effort).

Ideas pages are the single best signal for which repositories a GSoC org
actually mentors in. Public Google Docs are read through their plain-text
export; everything else is fetched as HTML/markdown and stripped.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from git_into_gsoc.http_client import CachedHttpClient, HttpError

MAX_CHARS = 400_000
_GDOC = re.compile(r"^/document/d/([A-Za-z0-9_-]+)")


def ideas_fetch_url(url: str) -> str | None:
    """Map an ideas-page URL to the cheapest plain-text form of the same content."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    if host == "docs.google.com":
        match = _GDOC.match(parsed.path)
        return (
            f"https://docs.google.com/document/d/{match.group(1)}/export?format=txt"
            if match
            else None
        )
    if host == "github.com" and len(parts) >= 4 and parts[2] == "wiki":
        page = "/".join(parts[3:]).removesuffix(".md")
        return f"https://raw.githubusercontent.com/wiki/{parts[0]}/{parts[1]}/{page}.md"
    if host == "github.com" and len(parts) >= 5 and parts[2] == "blob":
        rest = "/".join(parts[3:])
        return f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/{rest}"
    return url.split("#", 1)[0]


def to_text(raw: str) -> str:
    """Keep link targets (they name repos) while dropping markup."""
    with_links = re.sub(r"""<a\s[^>]*href=["']([^"']+)["'][^>]*>""", r" \1 ", raw, flags=re.I)
    no_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", with_links, flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", no_scripts))
    return re.sub(r"\s+", " ", text)[:MAX_CHARS]


def fetch_ideas_text(http: CachedHttpClient, url: str | None, ttl: int) -> str | None:
    target = ideas_fetch_url(url) if url else None
    if not target:
        return None
    try:
        return to_text(http.get_text(target, ttl=ttl))
    except HttpError:
        return None
