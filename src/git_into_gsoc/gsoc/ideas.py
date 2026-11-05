"""Fetch an org's ideas page as plain text (best effort).

Ideas pages are the single best signal for which repositories a GSoC org
actually mentors in. Public Google Docs are read through their plain-text
export; everything else is fetched as HTML/markdown and stripped.
"""

from __future__ import annotations

import html
import json
import re
from urllib.parse import urljoin, urlparse

from git_into_gsoc.http_client import CachedHttpClient, HttpError

MAX_CHARS = 400_000
_GDOC = re.compile(r"^/document/d/([A-Za-z0-9_-]+)")
_CONFLUENCE_PAGE = re.compile(r"^/wiki/spaces/[^/]+/pages/(\d+)")
_CONFLUENCE_API = "/wiki/rest/api/content/"
# A page that only sends the reader on: preCICE's old ideas address holds nothing else.
_META_REFRESH = re.compile(
    r"""<meta\s[^>]*http-equiv=["']?refresh["']?[^>]*content=["']?\s*0\s*;\s*url=['"]?([^"'>\s]+)""",
    re.I,
)
# A refresh inside <noscript> only sends readers without scripts to a notice page.
_NOSCRIPT = re.compile(r"<noscript\b.*?</noscript>", re.I | re.S)


def confluence_api_url(url: str) -> str | None:
    """The REST address of a Confluence Cloud page, or None for any other page.

    Confluence Cloud builds each page in the browser, so OpenMRS, JBoss, Mifos and
    OpenELIS read as pages with no ideas. The REST API returns the same page as HTML.
    """
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()  # never a user name or password before the host
    match = _CONFLUENCE_PAGE.match(parsed.path)
    if parsed.scheme not in {"http", "https"} or not match:
        return None
    if not host.endswith((".atlassian.net", ".jira.com")):
        return None
    return f"https://{host}{_CONFLUENCE_API}{match.group(1)}?expand=body.view"


def get_page(http: CachedHttpClient, target: str, ttl: int) -> tuple[str, str]:
    """(page text, the address it came from), unwrapping what the address hides.

    A Confluence REST reply is unwrapped to its HTML, and a page that only redirects
    with a meta refresh is followed once. Raises HttpError like `get_text`.
    """
    raw = http.get_text(target, ttl=ttl)
    if _CONFLUENCE_API in target:
        try:
            body = json.loads(raw)["body"]["view"]["value"]
        except (ValueError, KeyError, TypeError, RecursionError):
            return "", target
        return f"<html><body>{body}</body></html>", target
    moved = _META_REFRESH.search(_NOSCRIPT.sub(" ", raw[:4096]))
    if moved:
        follow = urljoin(target, html.unescape(moved.group(1)))
        try:
            return http.get_text(follow, ttl=ttl), follow
        except HttpError:
            return raw, target  # the page as it came is still better than nothing
    return raw, target


def ideas_fetch_url(url: str) -> str | None:
    """Map an ideas-page URL to the cheapest plain-text form of the same content."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    confluence = confluence_api_url(url)
    if confluence:
        return confluence
    if host == "docs.google.com":
        # A published document (/document/d/e/<id>/pub) has no export link; its
        # public page is the readable form. Its "e" is not a document id.
        if parsed.path.startswith("/document/d/e/") and parts[-1:] == ["pub"]:
            return url.split("#", 1)[0]
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


# A tag is read up to the next angle bracket, so one pass over a page is linear however
# the tags are left open. The regexes this replaced backtracked for minutes on a page
# of unterminated `<a href="` tags, and html.parser before 3.13.4 does the same
# (health audit, 2026-11-05); `ideas` and `repos` read any page an organization links to.
_TAG_RE = re.compile(r"<(/?)([a-z!?][a-z0-9-]*)([^<>]*)>", re.I)
_HREF_RE = re.compile(r"""\bhref\s*=\s*["']([^"'<>]+)""", re.I)


def to_text(raw: str) -> str:
    """Keep link targets (they name repos) while dropping markup."""
    raw = raw[:MAX_CHARS]
    parts: list[str] = []
    skipping: str | None = None  # inside <script> or <style>
    at = 0
    for tag in _TAG_RE.finditer(raw):
        closing, name, attrs = tag.group(1), tag.group(2).lower(), tag.group(3)
        if skipping is None:
            parts.append(raw[at : tag.start()])
            href = _HREF_RE.search(attrs) if name == "a" else None
            if href:
                parts.append(href.group(1))
            if name in {"script", "style"} and not closing:
                skipping = name
        elif closing and name == skipping:
            skipping = None
        at = tag.end()
    if skipping is None:
        parts.append(raw[at:])
    return re.sub(r"\s+", " ", html.unescape(" ".join(parts)))[:MAX_CHARS]


def fetch_ideas_text(http: CachedHttpClient, url: str | None, ttl: int) -> str | None:
    target = ideas_fetch_url(url) if url else None
    if not target:
        return None
    try:
        return to_text(get_page(http, target, ttl)[0])
    except HttpError:
        return None
