"""Make text written by strangers safe to show and short enough to read.

Issue bodies, PR titles, CONTRIBUTING files and ideas pages are untrusted
input. Models and people both read them, so hidden characters, HTML comments
and runaway length are stripped before they reach any output. Nothing here
tries to detect intent; it only removes what no honest text needs.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TAG_RE = re.compile(r"</?(?:script|style|iframe|img|svg|object|embed)[^>]*>", re.I)
# Text GitHub renders as nothing readable: an image shows its picture, not its alt text;
# a link reference definition shows nothing at all. A 2026-11-01 review put instructions
# in both, and they reached the model word for word. The character classes exclude the
# opening bracket so a flood of "![" stays linear.
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\[\]]*\]\([^()]*\)")
_LINK_REFERENCE_RE = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*\S+.*$", re.M)
_HIDDEN_OPEN_RE = re.compile(r"<(\w+)[^<>]*\b(?:hidden\b|display\s*:\s*none)[^<>]*>", re.I)
_INVISIBLE = {
    "\u200b",  # zero width space
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
    "\u00ad",  # soft hyphen
    "\u3164",  # Hangul filler: category Lo, so the Cf check misses it; same for the three below
    "\u115f",
    "\u1160",
    "\uffa0",
}


def _is_hidden(char: str) -> bool:
    if char in _INVISIBLE:
        return True
    code = ord(char)
    if 0xE0000 <= code <= 0xE007F:  # Unicode tag characters ("ASCII smuggling")
        return True
    category = unicodedata.category(char)
    return category in {"Cf", "Cc"} and char not in "\n\t"


# Control characters other than tab and newline, including ESC, which starts the
# terminal escape sequences that can retitle a window or write to the clipboard.
_ASCII_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def strip_hidden(text: str) -> str:
    """Remove characters that are invisible to people or that control the terminal."""
    if text.isascii():
        return _ASCII_CONTROL_RE.sub("", text)
    return "".join(ch for ch in text if not _is_hidden(ch))


def strip_hidden_all(value: Any) -> Any:
    """``strip_hidden`` on every string in JSON-like data; other values pass through."""
    if isinstance(value, str):
        return strip_hidden(value)
    if isinstance(value, dict):
        return {key: strip_hidden_all(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [strip_hidden_all(item) for item in value]
    return value


# Phone keyboards and macOS type a curly apostrophe (U+2019) in "I'm"; patterns are
# written with a straight one. Curly double quotes are folded the same way.
_TYPOGRAPHIC = str.maketrans(
    {"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u201c": '"', "\u201d": '"'}
)


def straight_quotes(text: str) -> str:
    """Text with curly apostrophes and quotes made straight, for pattern matching."""
    return (text or "").translate(_TYPOGRAPHIC)


def _drop_hidden_elements(text: str) -> str:
    """Remove elements with a `hidden` attribute or `display:none`, content included.

    A loop rather than one regex with a backreference: `<p hidden>` repeated 20,000
    times with no closing tag made that regex rescan the text from every opener.
    """
    kept: list[str] = []
    pos = 0
    unclosed: set[str] = set()  # a name with no closing tag ahead is searched once
    for match in _HIDDEN_OPEN_RE.finditer(text):
        if match.start() < pos:
            continue
        name = match.group(1).lower()
        end = match.end()
        if name not in unclosed:
            close = re.compile(rf"</{name}\s*>", re.I).search(text, end)
            if close is None:
                unclosed.add(name)
            else:
                end = close.end()
        kept.append(text[pos : match.start()])
        pos = end
    kept.append(text[pos:])
    return " ".join(kept)


def clean_untrusted(text: str | None, *, limit: int = 400) -> str:
    """Strip hidden characters and text GitHub hides, collapse whitespace, cap length."""
    if not text:
        return ""
    value = _HTML_COMMENT_RE.sub(" ", str(text))
    value = _MARKDOWN_IMAGE_RE.sub(" ", value)
    value = _drop_hidden_elements(value)
    value = _LINK_REFERENCE_RE.sub(" ", value)
    value = _TAG_RE.sub(" ", value)
    value = strip_hidden(value)
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value).strip()
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value
