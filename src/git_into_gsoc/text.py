"""Make text written by strangers safe to show and short enough to read.

Issue bodies, PR titles, CONTRIBUTING files and ideas pages are untrusted
input. Models and people both read them, so hidden characters, HTML comments
and runaway length are stripped before they reach any output. Nothing here
tries to detect intent; it only removes what no honest text needs.
"""

from __future__ import annotations

import re
import unicodedata

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TAG_RE = re.compile(r"</?(?:script|style|iframe|img|svg|object|embed)[^>]*>", re.I)
_INVISIBLE = {
    "​",  # zero width space
    "‌",
    "‍",
    "⁠",
    "﻿",
    "­",  # soft hyphen
}


def _is_hidden(char: str) -> bool:
    if char in _INVISIBLE:
        return True
    code = ord(char)
    if 0xE0000 <= code <= 0xE007F:  # Unicode tag characters ("ASCII smuggling")
        return True
    category = unicodedata.category(char)
    return category in {"Cf", "Cc"} and char not in "\n\t"


def clean_untrusted(text: str | None, *, limit: int = 400) -> str:
    """Strip hidden characters, comments and risky tags, collapse whitespace, cap length."""
    if not text:
        return ""
    value = _HTML_COMMENT_RE.sub(" ", str(text))
    value = _TAG_RE.sub(" ", value)
    value = "".join(ch for ch in value if not _is_hidden(ch))
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value).strip()
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value
