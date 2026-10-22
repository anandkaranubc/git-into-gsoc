"""Structured project ideas from an organization's GSoC ideas page.

Ideas pages come in a handful of shapes: one heading per idea with labelled
lines ("Difficulty: Medium"), bullet labels under a heading, HTML with bold
labels, published Google Docs, and umbrella index pages that only link to
sub-project pages. This module turns any of them into a list of
`ProjectIdea` records with a confidence flag, or reports honestly that the
page is an index or unstructured. No field is ever guessed: a missing label
stays empty.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from git_into_gsoc.http_client import CachedHttpClient, HttpError, NotFoundError
from git_into_gsoc.models import IdeasDocument, ProjectIdea
from git_into_gsoc.text import clean_untrusted

MAX_CHARS = 600_000
MIN_IDEAS_FOR_LAYOUT = 2

_GDOC = re.compile(r"^/document/d/([A-Za-z0-9_-]+)")
_URL_RE = re.compile(r"https?://[^\s<>()\"'\]]+")
_MD_LINK_RE = re.compile(r"\[([^\]\n]{1,80})\]\((https?://[^\s)]+)\)")
_HOURS_RE = re.compile(r"\b(90|175|350)\s*(?:h\b|hr|hrs|hours|-hour|hour)?", re.I)
_SIZE_WORD_RE = re.compile(r"\b(small|medium|large)\b", re.I)
# Hours other than 90, 175, or 350 ("300 hours", "80 to 160 hours", "360 hrs"); not a
# weekly load ("40 hours per week").
_ANY_HOURS_RE = re.compile(
    r"\b(\d{2,3})(?:\s*(?:-|\u2013|to)\s*(\d{2,3}))?\s*(?:h\b|hrs?\b|hours?\b)"
    r"(?!\s*(?:per|a|each|every|/)\s*week)",
    re.I,
)

LABELS: dict[str, tuple[str, ...]] = {
    "difficulty": (
        "difficulty",
        "difficulty level",
        "difficulty rating",
        "complexity",
        # omegaUp: "Skill level: High" is how hard the project is, not a skill.
        "skill level",
        "level",
        "experience level",
        "expertise level",
    ),
    "size": (
        "project size",
        "expected size of project",
        "expected project size",
        "size",
        "duration",
        "length",
        "project length",
        "estimate project length",
        "estimated project length",
        "time commitment",
        "hours",
        "expected time",
    ),
    "mentors": (
        "mentor",
        "mentor(s)",
        "mentors",
        "possible mentor",
        "possible mentors",
        "possible mentor(s)",
        "potential mentor",
        "potential mentor(s)",
        "potential mentors",
        "mentors name",
        "primary mentor",
    ),
    "skills": (
        "skills",
        "relevant skills",
        "recommended skills",
        "required skills",
        "required skills / knowledge",
        "required/desirable skills",
        "skills required",
        "skills needed",
        "prerequisites",
        "prerequisite",
        "knowledge prerequisite",
        "knowledge prerequisites",
        "required knowledge",
        "project requirements",
        "requirements",
        "technologies",
        "tech stack",
    ),
    "outcome": (
        "expected outcome",
        "expected outcomes",
        "expected results",
        "expected result",
        "outcome",
        "outcomes",
        "deliverables",
        "goal",
        "goals",
        "impact",
    ),
    "description": (
        "description",
        "summary",
        "brief explanation",
        "detailed description",
        "background",
        "abstract",
    ),
    "links": (
        "related issues/prs",
        "related issues/prs/etc.",
        "related issues",
        "related bug reports",
        "upstream issue (url)",
        "upstream issue",
        "github issue",
        "links",
        "resources",
        "references",
        "further reading",
        "see also",
    ),
}


def _norm_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).rstrip(" .:")


_LABEL_LOOKUP = {
    _norm_label(alias): field for field, aliases in LABELS.items() for alias in aliases
}
_LABEL_LINE_RE = re.compile(
    r"^\s*(?:[-*+•]\s*)?(?:\*\*|__)?\s*(?P<label>[A-Za-z][A-Za-z()/ .-]{1,40}?)\s*(?:\*\*|__)?\s*:\s*(?P<value>.*)$"
)
_NON_IDEA_HEADINGS = (
    "how to apply",
    "how to get started",
    "getting started",
    "introduction",
    "overview",
    "about",
    "contact",
    "timeline",
    "application",
    "applying",
    "proposal",
    "faq",
    "communication",
    "general information",
    "requirements for applicants",
    "mentors",
    "table of contents",
    "contents",
    "ideas list",
    "project ideas",
    "ideas",
    "welcome",
    "template",
    "ai policy",
    "ai usage policy",
    "draft ideas",
    "see also",
    "footnotes",
    "references",
    "notes",
    "project sizes",
    "sizes",
    "what you should know",
    "how do we judge",
    "navigation menu",
    "navigation",
)
_COMMENT_RE = re.compile(r"^\s*(?:\[//\]:\s*#|#(?!#*\s)|<!--)")
_BULLET_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
_AI_RE = re.compile(r"\b(ai|llm|llms|chatgpt|copilot|gemini|claude|language model)s?\b", re.I)
_POLICY_RE = re.compile(
    r"\b(propos\w*|submission\w*|polic\w*|allow\w*|permit\w*|prohibit\w*|forbid\w*|"
    r"ban(?:ned|s)?|reject\w*|disclos\w*|generated|written by|plagiar\w*|cheat\w*|"
    r"offload\w*|rely on|must not|should not|do not|don't|not accept\w*|accept\w*|"
    # MetaBrainz: "We discourage the use of AI tools in communications and contributions."
    r"discourag\w*|encourag\w*|avoid\w*|refrain\w*|not (?:use|rely))\b",
    re.I,
)


# ---------------------------------------------------------------- URL mapping


def ideas_document_url(url: str) -> str | None:
    """Best URL for a *structured* read of an ideas page (headings preserved).

    Returns None for pages that are really issue-tracker searches; callers
    should list the issues instead.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    if host == "docs.google.com":
        if parsed.path.startswith("/document/d/e/") and parts[-1:] == ["pub"]:
            return url.split("#", 1)[0]
        match = _GDOC.match(parsed.path)
        if match:
            return f"https://docs.google.com/document/d/{match.group(1)}/export?format=html"
        return None
    if host == "github.com":
        if len(parts) >= 3 and parts[2] in {"issues", "labels", "projects", "discussions"}:
            return None
        if len(parts) >= 4 and parts[2] == "wiki":
            page = "/".join(parts[3:]).removesuffix(".md")
            return f"https://raw.githubusercontent.com/wiki/{parts[0]}/{parts[1]}/{page}.md"
        if len(parts) >= 5 and parts[2] == "blob":
            return f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/{'/'.join(parts[3:])}"
    return url.split("#", 1)[0]


def issues_page_target(url: str) -> tuple[str, str] | None:
    """(owner/repo, label) when an ideas link is really a GitHub issue search or label page."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    if host != "github.com" or len(parts) < 3:
        return None
    full_name = f"{parts[0]}/{parts[1]}"
    if parts[2] == "labels" and len(parts) >= 4:
        return full_name, unquote(parts[3])
    if parts[2] == "issues":
        query = unquote(parse_qs(parsed.query).get("q", [""])[0]).replace("+", " ")
        match = re.search(r'label:(?:"([^"]+)"|(\S+))', query)
        label = (match.group(1) or match.group(2)) if match else "gsoc"
        return full_name, label
    return None


# ------------------------------------------------------------- HTML -> lines


class _LineParser(HTMLParser):
    """Flatten HTML into markdown-like lines: headings, bullets, bold labels, links."""

    _BLOCK: ClassVar[frozenset[str]] = frozenset(
        {"p", "div", "li", "br", "tr", "section", "article", "blockquote", "pre", "table"}
        # C2SI writes each field as <dt>Mentors</dt><dd>names</dd>: two lines, not one.
        | {"dl", "dt", "dd"}
    )
    _SKIP: ClassVar[frozenset[str]] = frozenset(
        {"script", "style", "noscript", "svg", "head", "nav", "footer"}
    )
    # Real content starts here even when a page omits </head> (allowed in HTML)
    # or never closes a nav; otherwise the whole page would be skipped.
    _CONTENT: ClassVar[frozenset[str]] = frozenset({"body", "main", "article"})
    # Hand-written sites mark titles with styled divs instead of heading tags.
    _DIV_HEADING: ClassVar[tuple[tuple[str, int], ...]] = (
        ("subsubsection", 3),
        ("subsection", 3),
        ("sectiontitle", 2),
        ("section-title", 2),
        ("section_title", 2),
        ("heading", 2),
        ("title", 2),
    )

    def __init__(self, base_url: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._skip = 0
        self._heading: int | None = None
        self._bold = 0
        self._href: str | None = None
        self._li = False
        self._divs: list[int | None] = []
        # The level of the last real heading, and whether the current heading is a
        # collapsible block's title (<summary>, class "accordion"), which sits below it.
        self._last = 0
        self._soft = False

    def _flush(self) -> None:
        text = re.sub(r"[ \t]+", " ", "".join(self._buf)).strip()
        self._buf = []
        if not text:
            return
        if self._heading:
            self.lines.append("#" * self._heading + " " + text)
        elif self._li:
            self.lines.append("- " + text)
        else:
            self.lines.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._CONTENT:
            self._skip = 0
            self._flush()
            return
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush()
            self._heading = self._last = int(tag[1])
            self._soft = False
        elif tag == "li":
            self._flush()
            self._li = True
        elif tag == "div":
            self._flush()
            if self._soft and self._heading:
                # An accordion's title holds only the title; a block inside it is the
                # body (Bootstrap wraps every item in one <div class="accordion">).
                self._heading, self._soft = None, False
            level = self._div_level(attrs)
            if level:
                self._last = level
            elif self._collapsible(tag, attrs):
                level, self._soft = min(6, self._last + 1), True
            self._divs.append(level)
            if level:
                self._heading = level
        elif tag == "summary" or (tag == "button" and self._collapsible(tag, attrs)):
            # C2SI and the Neuroinformatics Unit put each idea in a collapsible block
            # whose title is not a heading tag; it is one level below the last heading.
            self._flush()
            self._heading, self._soft = min(6, self._last + 1), True
        elif tag in self._BLOCK:
            self._flush()
        elif tag in {"b", "strong"}:
            self._bold += 1
            self._buf.append("**")
        elif tag == "a":
            self._href = dict(attrs).get("href") or None

    @staticmethod
    def _collapsible(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        return tag == "summary" or "accordion" in str(dict(attrs).get("class") or "").split()

    def _div_level(self, attrs: list[tuple[str, str | None]]) -> int | None:
        classes = str(dict(attrs).get("class") or "").lower()
        if not classes or "page" in classes or "container" in classes:
            return None
        for marker, level in self._DIV_HEADING:
            if marker in classes:
                return level
        return None

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush()
            self._heading = None
        elif tag == "li":
            self._flush()
            self._li = False
        elif tag == "div":
            self._flush()
            if self._divs and self._divs.pop():
                self._heading, self._soft = None, False
        elif tag in {"summary", "button"} and self._soft:
            self._flush()
            self._heading, self._soft = None, False
        elif tag in self._BLOCK:
            self._flush()
        elif tag in {"b", "strong"} and self._bold:
            self._bold -= 1
            self._buf.append("**")
        elif tag == "a" and self._href:
            href = self._href
            if self.base_url and not href.startswith(("#", "mailto:", "javascript:")):
                # ML4SCI links each project's ideas as "/gsoc/projects/2026/...": a
                # relative link was dropped, so the umbrella page lost all of them.
                href = urljoin(self.base_url, href)
            if href.startswith(("http://", "https://")):
                self._buf.append(f" ({href})")
            self._href = None

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def html_to_lines(raw: str, base_url: str | None = None) -> list[str]:
    """HTML as markdown-like lines: headings (a collapsible block's title counts as
    one), bullets, bold labels, definition-list terms and values, and links, with
    scripts, menus, and footers left out."""
    parser = _LineParser(base_url)
    parser.feed(raw[:MAX_CHARS])
    parser.close()
    return [html.unescape(line) for line in parser.lines]


_UNDERLINE_RE = re.compile(r"^\s*([=\-~^\"'`+*]{3,})\s*$")
# Markdown setext uses = and -; reStructuredText uses any of these, deeper levels
# usually ~ or ^ or " in that order of appearance.
_UNDERLINE_LEVEL = {"=": 1, "-": 2, "~": 3, "^": 3, '"': 3, "'": 3, "`": 3, "+": 3}
_FRONT_MATTER_RE = re.compile(r"\A\s*---\n.*?\n---\n", re.S)


def _promotable(line: str) -> bool:
    text = line.strip()
    return (
        3 <= len(text) <= 120
        and not _heading(line)
        and not text.startswith("|")
        and not _BULLET_RE.match(text)
        and not _LABEL_LINE_RE.match(text)
    )


def markdown_to_lines(raw: str) -> list[str]:
    """Markdown or reStructuredText as lines: underlined headings become `#` headings;
    front matter, comments, and rules are dropped."""
    lines: list[str] = []
    text = _FRONT_MATTER_RE.sub("", raw[:MAX_CHARS], count=1)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    prev_blank = True
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped.strip():
            prev_blank = True
            continue
        underline = _UNDERLINE_RE.match(stripped)
        if underline:
            # A line of = or - (or an rst adornment) right under a plain text line
            # underlines a heading; after a blank line it is a horizontal rule.
            level = _UNDERLINE_LEVEL.get(underline.group(1)[0])
            if level and not prev_blank and lines and _promotable(lines[-1]):
                lines[-1] = "#" * level + " " + lines[-1].strip()
            prev_blank = True
            continue
        prev_blank = False
        if _COMMENT_RE.match(stripped) or stripped.startswith(".. "):
            continue
        lines.append(stripped)
    return lines


def _looks_like_html(raw: str) -> bool:
    head = raw[:2000].lower()
    return "<html" in head or "<body" in head or "<!doctype html" in head or "<div" in head


def to_lines(raw: str, base_url: str | None = None) -> list[str]:
    """An ideas page as lines, whether it arrived as HTML or as markdown; a line with
    breaks inside it is split where a label starts, or after a label's bare name, so
    each label is read."""
    lines = html_to_lines(raw, base_url) if _looks_like_html(raw) else markdown_to_lines(raw)
    # A paragraph with line breaks (<br>) arrives as one line: MariaDB writes "Skills
    # needed: C++, bison" and "Mentors: ..." in one, and neither label was read. Split
    # only such lines: a link and its text on two lines must stay one ("Topic (url)").
    out: list[str] = []
    for line in lines:
        parts = line.split("\n")
        # A label after a break ("...bison<br>Mentors: ..."), not a label whose value
        # wraps onto the next lines (Submitty's "Expected Outcomes: This project ...").
        # Or a label's bare name before its value ("**Duration**<br>Small (~90 hours)").
        if len(parts) > 1 and (
            any(_label(part.strip()) for part in parts[1:])
            or _norm_label(_clean(parts[0])) in _LABEL_LOOKUP
        ):
            out.extend(parts)
        else:
            out.append(line)
    return out


# ------------------------------------------------------------------ parsing


def _heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
    if not match:
        return None
    text = re.sub(r"[*_`]+", "", match.group(2)).strip()
    return len(match.group(1)), text


# When a label is not in the vocabulary, one of these words inside it decides
# the field ("Skills required/preferred", "Confirmed Mentor", "Description of
# the project"). Order matters: the first match wins.
_LABEL_KEYWORDS = (
    ("difficult", "difficulty"),
    ("mentor", "mentors"),
    ("level", "difficulty"),  # before "skill": "Required skill level" is a difficulty
    ("skill", "skills"),
    ("outcome", "expected_outcome"),
    ("deliverable", "expected_outcome"),
    ("description", "description"),
    ("hours", "size"),
    ("size", "size"),
    ("length", "size"),
    ("duration", "size"),
)


def _field_for_label(label: str) -> str | None:
    field = _LABEL_LOOKUP.get(label)
    if field is not None:
        return field
    for word, candidate in _LABEL_KEYWORDS:
        if word in label and candidate in LABELS:
            return candidate
    return None


def _label(line: str) -> tuple[str, str, str] | None:
    """(field, label, value) when a line is `Label: value` for a known label."""
    match = _LABEL_LINE_RE.match(line)
    if not match:
        return None
    label = _norm_label(match.group("label"))
    field = _field_for_label(label)
    if field is None:
        return None
    # "**Estimated size of project:**" closes the bold after the colon; the value is on
    # the next line, not "**".
    return field, label, re.sub(r"^(?:\*\*|__)\s*", "", match.group("value")).strip()


def _clean(value: str) -> str:
    value = _BULLET_RE.sub("", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\*\*|__|`", "", value)
    return clean_untrusted(re.sub(r"\s+", " ", value), limit=600)


def _split_list(value: str) -> list[str]:
    value = _clean(value)
    parts = re.split(r"\s*(?:,|;|/| and | or |\|)\s*(?![^()]*\))", value)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _split_people(value: str) -> list[str]:
    # One name per line counts as a list too (the Neuroinformatics Unit's
    # "@alessandrofelder\n@igortatarnikov"); _clean would join the lines.
    value = "; ".join(_clean(line) for line in value.split("\n"))
    # A linked name renders as "Name (https://...)"; the link is kept in idea.links.
    value = re.sub(r"\s*\(\s*(?:https?:)?//[^)]*\)", "", value)
    # Cloudflare replaces an email address with "[email protected]" (C2SI).
    value = re.sub(r"\s*\(?\[email\s+protected\]\)?", "", value, flags=re.I)
    parts = re.split(r"\s*(?:,|;| and |&)\s*(?![^()]*\))", value)
    return [p.strip(" .") for p in parts if p.strip(" .")]


# Words in a "Mentors" field that are job titles, links, or instructions, not names.
_ROLE_WORDS = frozenset(
    [
        *("advisor", "advisory", "ambassador", "analyst", "architect", "author", "board"),
        *("ceo", "chief", "consultant", "contact", "contributor", "creator", "cto"),
        *("developer", "director", "discord", "engineer", "enthusiast", "founder", "github"),
        *("head", "ideas", "infrastructure", "intern", "lead", "leader", "linkedin"),
        *("maintainer", "manager", "member", "mentors", "officer", "principal", "professor"),
        *("project", "projects", "researcher", "scientist", "security", "senior", "slack"),
        *("speaker", "staff", "student", "systems", "team", "twitter"),
    ]
)
_NAME_PARTICLES = frozenset(
    [
        *("van", "der", "de", "da", "del", "della", "di", "du", "dos", "das", "von", "ten"),
        *("ter", "la", "le", "bin", "al"),
    ]
)
_LINKING_WORDS = frozenset(
    [
        *("a", "an", "and", "at", "for", "if", "in", "of", "on", "or", "our", "the", "to"),
        *("us", "we", "with", "you"),
    ]
)
_HANDLE_RE = re.compile(r"^@?[a-z0-9][a-z0-9_-]{2,38}$")


def _person(part: str) -> str | None:
    """A person's name or handle from one piece of a mentors field, or None.

    Contact details in parentheses stay ("Alice (@alice)"); a title after " - ",
    "|", or a bullet is dropped.
    """
    if "http" in part or re.search(r"[:!?]\s*$", part):
        return None
    text = re.split(r"\s*[|\u2022]\s*", part, maxsplit=1)[0]
    text = re.split(r"\s+[-\u2013]\s+", text, maxsplit=1)[0].strip(" .,")
    bare = re.sub(r"\s*\([^)]*\)", "", text).strip(" .,")
    words = bare.split()
    # GitHub handles ignore case: "@IgorTatarnikov" is one, "AI" alone is not.
    if len(words) == 1 and _HANDLE_RE.match(bare.lower() if bare.startswith("@") else bare):
        return text
    if not 1 <= len(words) <= 5:
        return None
    # R's mentors are "TD Hocking": initials before one surname are a name.
    initials = len(words) == 2 and len(words[0]) <= 3 and not words[1].isupper()
    for position, word in enumerate(words):
        lower = word.lower().strip(".")
        if lower in _NAME_PARTICLES or (initials and position == 0 and word.isupper()):
            continue  # "A Chetia": an initial, not the article
        if lower in _ROLE_WORDS or lower in _LINKING_WORDS:
            return None
        if not word[0].isalpha() or word[0].islower():
            return None
        if len(word) >= 2 and word.isupper() and not (initials and position == 0):
            return None  # "AI", "CCSP": titles, not names
    return text


def mentor_names(parts: list[str]) -> list[str]:
    """Names and handles from a split mentors field, dropping titles and instructions."""
    names = [_person(part) for part in parts]
    return list(dict.fromkeys(n for n in names if n))


def normalize_size(value: str) -> tuple[str | None, int | None]:
    """(size, hours) from a size value: "175 hours" and "medium" both give ("medium",
    175); (None, None) when neither a GSoC hour count nor a size word is found."""
    hours = _HOURS_RE.search(value or "")
    if hours:
        number = int(hours.group(1))
        return {90: "small", 175: "medium", 350: "large"}[number], number
    # MetaBrainz's "300 hours" was dropped, so the idea had no size at all. Keep the
    # hours the page states (a range's upper end), with the nearest GSoC size.
    other = _ANY_HOURS_RE.search(value or "")
    if other:
        number = int(other.group(2) or other.group(1))
        if 30 <= number <= 600:
            return ("small" if number < 133 else "medium" if number < 263 else "large"), number
    word = _SIZE_WORD_RE.search(value or "")
    if word:
        size = word.group(1).lower()
        return size, {"small": 90, "medium": 175, "large": 350}[size]
    return None, None


def normalize_difficulty(value: str) -> str | None:
    """The page's difficulty word as "easy", "medium", or "hard" ("beginner" is easy,
    "challenging" is hard), or None when it uses no such word."""
    text = (value or "").lower()
    if not text.strip():
        return None
    if re.search(r"\b(easy|beginner|simple|low|novice|trivial)\b", text):
        return "easy"
    if re.search(r"\b(hard|advanced|difficult|high|expert|challenging)\b", text):
        return "hard"
    if re.search(r"\b(medium|intermediate|moderate|mid)\b", text):
        return "medium"
    return None


def _paragraphs(text: str) -> list[str]:
    """Join wrapped lines into paragraphs; a heading or a list item starts a new one."""
    chunks: list[list[str]] = []
    after_heading = False
    for line in text.splitlines():
        if not line.strip():
            continue
        heading = bool(_heading(line))
        # A heading is a paragraph of its own: "About AI" is not the start of the rule.
        if not chunks or heading or after_heading or _BULLET_RE.match(line):
            chunks.append([line])
        else:
            chunks[-1].append(line)
        after_heading = heading
    return [" ".join(chunk) for chunk in chunks]


def ai_policy_sentences(text: str, limit: int = 4) -> list[str]:
    """Sentences that look like a rule about AI/LLM use (not AI as a topic).

    Links are ignored when matching: a list of links to sub-pages is not a rule,
    even when a domain ends in ".ai" or a path says "proposed".
    """
    found: list[str] = []
    for paragraph in _paragraphs(text):
        flat = re.sub(r"\s+", " ", re.sub(r"[#*_`]+", "", paragraph))
        for sentence in re.split(r"(?<=[.!?])\s+", flat):
            sentence = sentence.strip()
            prose = _URL_RE.sub(" ", sentence)
            if not (_AI_RE.search(prose) and _POLICY_RE.search(prose)):
                continue
            if not 20 <= len(sentence) <= 400:
                continue
            clean = clean_untrusted(sentence, limit=400)
            if clean not in found:
                found.append(clean)
            if len(found) >= limit:
                return found
    return found


def _candidate_levels(lines: list[str]) -> list[int]:
    counts: dict[int, int] = {}
    for line in lines:
        head = _heading(line)
        if head and _norm_label(head[1]) not in _LABEL_LOOKUP:
            counts[head[0]] = counts.get(head[0], 0) + 1
    return [level for level, count in counts.items() if count >= MIN_IDEAS_FOR_LAYOUT]


def _split_blocks(
    lines: list[str], level: int
) -> tuple[list[tuple[str, list[str], str | None]], list[str]]:
    """Blocks at `level` plus the lines that sit outside any block (page rules live there)."""
    blocks: list[tuple[str, list[str], str | None]] = []
    outside: list[str] = []
    section: str | None = None
    title: str | None = None
    body: list[str] = []
    for line in lines:
        head = _heading(line)
        if head and head[0] < level:
            if title is not None:
                blocks.append((title, body, section))
                title, body = None, []
            section = head[1]
            outside.append(line)
            continue
        if head and head[0] == level and not _without_urls(_clean(head[1])).strip():
            continue  # Oppia's "### </p>": no title, so the idea above goes on
        if head and head[0] == level:
            if title is not None:
                blocks.append((title, body, section))
            title, body = head[1], []
            continue
        if title is not None:
            body.append(line)
        else:
            outside.append(line)
    if title is not None:
        blocks.append((title, body, section))
    return blocks, outside


def _labelled(idea: ProjectIdea) -> int:
    return sum(
        1
        for value in (idea.difficulty, idea.size, idea.mentors, idea.skills, idea.expected_outcome)
        if value
    )


# A page title such as "GNOME Project ideas for Google Summer of Code 2026".
_PAGE_TITLE_RE = re.compile(
    r"\bideas?\b.*\b(?:gsoc|summer of code)\b|\b(?:gsoc|summer of code)\b.*\bideas?\b"
)


def _is_non_idea(title: str) -> bool:
    low = title.lower().strip(" :#")
    return (
        any(
            low in (word, word + "s") or low.startswith(word + " ") or low.endswith(" " + word)
            for word in _NON_IDEA_HEADINGS
        )
        or bool(_PAGE_TITLE_RE.search(low))
        or len(low) < 3
    )


def _without_urls(text: str) -> str:
    """A heading without the address of the link it is ("ListenBrainz (https://...)"),
    or a wiki's section edit link ("Add support for SPFS[edit]")."""
    bare = re.sub(r"\s*\(https?://[^)\s]+\)", "", text)
    return re.sub(r"\s*\[edit\]\s*$", "", bare).strip() or text


def _leaf_sections(lines: list[str], *, level: int) -> list[tuple[int, str, list[str], str]]:
    """Each heading with only its own text (the lines before the next heading), and the
    last heading at `level` above it."""
    sections: list[tuple[int, str, list[str], str]] = []
    parent = ""
    for line in lines:
        head = _heading(line)
        if head:
            if head[0] <= level:
                parent = head[1] if head[0] == level else ""
            sections.append((head[0], head[1], [], parent))
        elif sections:
            sections[-1][2].append(line)
    return sections


def _is_aside(section: str | None) -> bool:
    """A whole heading that is about something else: "Communications", "FAQ".

    Only the whole heading counts: a page titled "Summer of Code - Getting Started"
    still holds its "Suggested projects".
    """
    low = (section or "").lower().strip(" :#")
    return any(low in (word, word + "s") for word in _NON_IDEA_HEADINGS if "idea" not in word)


def _is_list_heading(section: str) -> bool:
    """A parent heading that only says "the ideas": "Ideas List", "Project Ideas"."""
    low = section.lower().strip(" :#")
    return bool(re.fullmatch(r"(?:list of )?(?:the )?(?:project )?ideas?(?: list)?", low)) or bool(
        _PAGE_TITLE_RE.search(low)
    )


# A line that only states a project's size: "Full-time project 350h", "175 hours".
# A line that is all bold and ends in a colon, such as "**Details:**", is a label.
_BOLD_LABEL_RE = re.compile(r"(\*\*|__)[^*_\n]{1,80}(?::\1|\1:)")
_SIZE_LINE_RE = re.compile(
    r"(?:(?:full|part)[- ]time\s+)?(?:project\s*)?[:(,-]?\s*(?:90|175|350)\s*(?:h|hrs?|hours?)\)?",
    re.I,
)


def _parse_block(
    title: str, body: list[str], *, section: str | None, source_url: str
) -> ProjectIdea:
    idea = ProjectIdea(
        title=_without_urls(_clean(title))[:200], section=section, source_url=source_url
    )
    free_text: list[str] = []
    current: str | None = None
    taken = 0  # lines the running field has taken
    cell: str | None = None
    cells = sum(1 for line in body if _norm_label(_clean(line)) in _LABEL_LOOKUP) >= 2
    for line in body:
        head = _heading(line)
        if head:
            # GNOME writes "### Project Length: Long (~350 hours)" as a heading.
            inline = _label(head[1])
            if inline and inline[2]:
                _assign(idea, inline[0], inline[2])
                current = None
                continue
            label = _norm_label(head[1])
            current, taken = _LABEL_LOOKUP.get(label), 0
            if current is None:
                current = None
                free_text.append(head[1])
            continue
        labelled = _label(line)
        if labelled:
            field, _, value = labelled
            if value.startswith("#"):  # inline template note, not a value
                value = ""
            current, taken = (field if not value else None), 0
            if value:
                _assign(idea, field, value)
            continue
        # SageMath lays an idea out as table cells: "Mentor", then "Travis Scrimshaw".
        # A line that is only a label's name labels the one line after it, in a block
        # with several such lines: one "Mentors" in a page's contents is a link. It also
        # ends a field that runs on (C2SI's "Skills Required:" lines, then "Mentor").
        bare = _LABEL_LOOKUP.get(_norm_label(_clean(line))) if cells else None
        if bare:
            current, cell = None, bare
            continue
        if current and taken and _BOLD_LABEL_RE.fullmatch(line.strip()):
            # Kubeflow's "**Mentors:**" names, then "**Contributor:**", a label this reader
            # does not know. Before any value it is a group ("**For modules A-D:**").
            current = None
        if current:
            _assign(idea, current, line)
            taken += 1
        elif cell:
            _assign(idea, cell, line)
            if _BULLET_RE.match(line):
                continue  # a list under the label's name: each item belongs to it
        elif not idea.size and _SIZE_LINE_RE.fullmatch(_clean(line).strip(" .")):
            _assign(idea, "size", line)  # MariaDB: "**Full-time project 350h**"
        else:
            free_text.append(line)
        cell = None
    if not idea.description:
        text = " ".join(_clean(x) for x in free_text if not _URL_RE.fullmatch(x.strip()))
        idea.description = text[:500].strip()
    for line in [*body, title]:
        for url in _URL_RE.findall(line):
            cleaned = url.rstrip(".,;:")
            if cleaned not in idea.links:
                idea.links.append(cleaned)
    idea.links = idea.links[:10]
    labelled_fields = _labelled(idea)
    if labelled_fields >= 2:
        idea.confidence = "high"
    elif labelled_fields == 1 or len(body) >= 3:
        idea.confidence = "medium"
    else:
        idea.confidence = "low"
    return idea


def _assign(idea: ProjectIdea, field: str, value: str) -> None:
    value = value.strip()
    if not value or value.startswith("#"):  # "#" starts an inline template instruction
        return
    idea.labelled_fields += 1
    if field == "difficulty":
        idea.difficulty_raw = (idea.difficulty_raw + " " + _clean(value)).strip()
        idea.difficulty = normalize_difficulty(idea.difficulty_raw) or idea.difficulty
    elif field == "size":
        idea.size_raw = (idea.size_raw + " " + _clean(value)).strip()
        size, hours = normalize_size(idea.size_raw)
        idea.size, idea.hours = size or idea.size, hours or idea.hours
    elif field == "mentors":
        idea.mentors.extend(p for p in mentor_names(_split_people(value)) if p not in idea.mentors)
    elif field == "skills":
        idea.skills.extend(p for p in _split_list(value) if p not in idea.skills)
    elif field == "outcome":
        idea.expected_outcome = (idea.expected_outcome + " " + _clean(value)).strip()[:500]
    elif field == "description":
        idea.description = (idea.description + " " + _clean(value)).strip()[:500]
    elif field == "links":
        for url in _URL_RE.findall(value):
            cleaned = url.rstrip(".,;:")
            if cleaned not in idea.links:
                idea.links.append(cleaned)


# Headings whose links lead away from ideas (navigation, people, process). A
# heading about ideas, such as "Ideas Pages" on an umbrella index, keeps its links.
_NAV_HEADINGS = tuple(h for h in _NON_IDEA_HEADINGS if "idea" not in h and h != "template")


def _is_nav_heading(title: str) -> bool:
    low = title.lower().strip(" :")
    return any(
        low == word or low.startswith(word + " ") or low.endswith(" " + word)
        for word in _NAV_HEADINGS
    )


# Link texts that say nothing about where they lead ("List of proposals" beside each
# of ML4SCI's 18 projects): such a link is named after the line just before it.
_GENERIC_LINK_TEXT = re.compile(
    r"^(?:list of (?:proposals|projects|ideas)|proposals|projects|(?:project )?ideas?"
    r"(?: page| list)?|here|more|read more|details|link|click here|see more|list|"
    r"(?:google summer of code|gsoc)(?: 20\d\d)?(?: (?:project )?ideas?(?: page| list)?)?)$",
    re.I,
)
_ONLY_LINK_RE = re.compile(r"[-*\s]*([^()\n]{2,160}?)\s*\((https?://[^)\s]+)\)\s*")
# Pages about the program itself, never one organization's ideas.
_PROGRAM_SITES = ("summerofcode.withgoogle.com", "developers.google.com/open-source/gsoc")


def _lead_name(line: str) -> str:
    """'CMS (http://cms.cern/) is a high-energy physics experiment...' -> 'CMS'."""
    text = re.sub(r"\s*\(https?://[^)]*\)", "", line).strip(" -*")
    match = re.match(r"(?:The\s+)?(.{2,60}?)(?:\s+(?:is|are|was|focuses|aims)\b|[.:;,]|$)", text)
    return _clean(match.group(1)) if match else ""


def _slug_name(url: str) -> str:
    """'.../project_EXXA.html' -> 'EXXA'."""
    stem = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    stem = re.sub(r"^(?:project|proposals?|ideas?)[_-]", "", stem, flags=re.I)
    return stem.replace("_", " ").replace("-", " ").strip()


def _sub_pages(lines: list[str]) -> list[dict[str, str]]:
    """Outbound links grouped under headings: the shape of an umbrella index page."""
    pages: list[dict[str, str]] = []
    current = ""
    previous = ""
    seen: set[str] = set()
    generic_links: Counter[str] = Counter()  # per heading
    for line in lines:
        head = _heading(line)
        if head:
            current = _without_urls(head[1])
            previous = ""
            continue
        if _is_nav_heading(current):
            continue
        titles = {url.rstrip(".,;:)"): text for text, url in _MD_LINK_RE.findall(line)}
        # A line that is nothing but one HTML link renders as "text (url)".
        only_link = _ONLY_LINK_RE.fullmatch(line)
        if only_link:
            titles.setdefault(only_link.group(2).rstrip(".,;:)"), only_link.group(1))
        for url in _URL_RE.findall(line):
            cleaned = url.rstrip(".,;:)")
            if cleaned in seen or any(site in cleaned for site in _PROGRAM_SITES):
                continue
            if re.search(r"github\.com/[^/]+/[^/]+/edit/", cleaned):
                continue  # "Improve this page" links to the page's own source
            seen.add(cleaned)
            text = _clean(titles.get(cleaned) or "")
            generic = ""
            if text and _GENERIC_LINK_TEXT.match(text):
                # The sentence before names the project ("CMS is a ... experiment"), but
                # only if it mentions the page's own name; "This project" does not.
                lead, slug = _lead_name(previous), _slug_name(cleaned)
                squash = re.compile(r"[^a-z0-9]")
                fits = (
                    lead[:1].isupper()  # not "purpose of EXXA"
                    and slug
                    and squash.sub("", slug.lower()) in squash.sub("", lead.lower())
                )
                text, generic = (lead, "") if fits else ("", slug or lead)
                generic_links[current] += 1
            title = text or current or cleaned
            pages.append({"title": title, "url": cleaned, "section": current, "generic": generic})
        previous = line
    # A generic link ("ideas", "GSoC 2026") is named after its heading when the heading
    # covers one sub-project (Python's "pocketpy": chat, homepage, ideas). A heading with
    # several generic links lists many projects ("List of proposals" beside each of
    # ML4SCI's), so each is named after the page it leads to.
    for page in pages:
        fallback = page.pop("generic")
        if fallback and (not page["section"] or generic_links[page["section"]] > 1):
            page["title"] = fallback
    if any(page["section"] for page in pages):
        # Links above the first heading are the site's menu ("Getting Started",
        # "Mentors", other years' pages), not its projects. A page with no headings
        # at all keeps them: there the links are the content.
        pages = [page for page in pages if page["section"]]
    # "page.html#contact" is a part of a page, not another page.
    kept: list[dict[str, str]] = []
    bases: set[str] = set()
    for page in pages:
        base = page["url"].split("#", 1)[0]
        if base in bases:
            continue
        bases.add(base)
        kept.append(page)
    return kept[:40]


def ideas_from_link_list(doc: IdeasDocument, *, page_url: str, section: str) -> list[ProjectIdea]:
    """A page that only lists its ideas as links, one per idea, on the same site.

    ML4SCI's project pages list each proposal as a link under "Project Proposals". The
    titles are the ideas; every proposal page holds the details.
    """
    host = urlparse(page_url).netloc
    ideas: list[ProjectIdea] = []
    for page in doc.sub_pages:
        where = urlparse(page["url"])
        if where.netloc != host:
            continue
        # The link's own address must name a proposal or idea: ML4SCI links its project
        # pages as project_*.html (each holds several ideas) and each idea as
        # proposal_*.html, as CERN-HSF does.
        if not re.search(r"proposal|idea", where.path, re.I):
            continue
        if not re.search(r"proposal|idea|project", page.get("section", ""), re.I):
            continue
        title = page["title"]
        if not title or title == page.get("section") or _GENERIC_LINK_TEXT.match(title):
            title = _slug_name(page["url"])  # the page's own name, such as "BOA"
        if not title:
            continue
        ideas.append(
            ProjectIdea(title=title, section=section, links=[page["url"]], source_url=page_url)
        )
    return ideas


_TEMPLATE_TITLES = {"title", "project title", "idea title", "your title", "name of the project"}


# Headings that tell applicants what to send, not what to build.
_GUIDANCE_RE = re.compile(
    r"\bhow to apply\b|\bwhat to include\b|\byour (?:proposal|application)\b|"
    r"\b(?:proposal|application) (?:template|guidelines?|format|pdf)\b",
    re.I,
)


def _is_template(idea: ProjectIdea) -> bool:
    """A blank template for new ideas, or advice on what to put in a proposal."""
    title = re.sub(r"[<>\[\]{}]", "", idea.title).strip().lower()
    section = (idea.section or "").strip().lower()
    return (
        title in _TEMPLATE_TITLES
        or "template" in section
        or title.startswith("template")
        or bool(_GUIDANCE_RE.search(f"{section} / {title}"))
    )


def extract_ideas(lines: list[str], *, source_url: str) -> IdeasDocument:
    """Read the ideas on a page that is already split into lines.

    The result's `layout` says what was found: "headings", with the ideas in
    `ideas`; "index", a page that mostly links to other pages, with those pages in
    `sub_pages` and the page's own blocks in `fallback_ideas` when they may still
    be the ideas; or "unstructured", when nothing read as an idea. `ai_policy`
    holds the page's sentences about AI use that sit outside any idea block.
    """
    doc = IdeasDocument(source_url=source_url, fetched_url=source_url)
    doc.headings = [h[1] for line in lines if (h := _heading(line))][:60]
    levels = _candidate_levels(lines)
    if not levels:
        doc.sub_pages = _sub_pages(lines)
        # A page that is mostly links to other pages, such as an umbrella
        # organization's list of its projects, is an index even without headings.
        # Label lines ("Mentors: ...") split out of a paragraph are not more prose.
        prose = sum(1 for line in lines if not _label(line))
        mostly_links = len(doc.sub_pages) >= 3 and len(doc.sub_pages) * 3 >= prose
        doc.layout = "index" if mostly_links else "unstructured"
        doc.ai_policy = ai_policy_sentences("\n".join(lines))
        return doc

    # Try every candidate level; keep the one whose blocks carry the most labelled fields.
    best: tuple[tuple[int, ...], int, list[ProjectIdea], list[str]] | None = None
    for level in levels:
        blocks, outside = _split_blocks(lines, level)
        ideas = [
            _parse_block(t, b, section=s, source_url=source_url)
            for t, b, s in blocks
            if not _is_non_idea(t)
        ]
        yield_ = sum(_labelled(i) for i in ideas)
        # When as many blocks carry as many fields, the deeper level wins: LibreOffice's
        # "## Filters" holds one "### Add JPEG XL import support", and its empty groups
        # ("## Draw") are not ideas. With no fields anywhere, more blocks still win.
        labelled = sum(1 for i in ideas if _labelled(i))
        key = (yield_, labelled, level if labelled else len(ideas), len(ideas), level)
        if best is None or key > best[0]:
            best = (key, level, ideas, outside)
    assert best is not None
    _, level, ideas, outside = best
    # Some pages put ideas at two heading levels: ListenBrainz's 2026 page has three
    # under "## Ideas" as ### and its two Android ideas as ##. A heading above the
    # ideas' level whose own text, before the next heading, holds two idea fields is an
    # idea too. Headings below it ("Prerequisites", "Expected Outcome:") are parts of one.
    known = {i.title.lower() for i in ideas}
    parents = {_without_urls(_clean(i.title)).lower() for i in ideas}
    for depth, title, body, parent in _leaf_sections(lines, level=level):
        if depth == level or _is_non_idea(title) or title.rstrip().endswith(":"):
            continue
        if depth > level and _without_urls(_clean(parent)).lower() in parents:
            continue  # a part of an idea: its "Prerequisites" or "Expected Outcome"
        if _label(title) or _without_urls(_clean(title)).lower() in known:
            continue
        extra = _parse_block(title, body, section=None, source_url=source_url)
        if _labelled(extra) >= 2:
            ideas.append(extra)
            known.add(extra.title.lower())
    for idea in ideas:
        if idea.section and _is_list_heading(idea.section):
            idea.section = None  # "Ideas List / Cronjob Optimization" says nothing more
    # omegaUp's "# Communications" holds "## If you have questions about ...": a block
    # under a section that is not about ideas, with no idea fields, is not an idea.
    ideas = [i for i in ideas if not (_is_aside(i.section) and not _labelled(i))]
    doc.ai_policy = ai_policy_sentences("\n".join(outside))

    # Pages show a blank template for new ideas ("Template / Title", mentors "Mentor,
    # Info"); it has every label and none of the content.
    ideas = [i for i in ideas if not _is_template(i)]
    labelled_blocks = sum(1 for i in ideas if _labelled(i))
    if ideas and labelled_blocks * 2 >= len(ideas):
        # On a mostly labelled page, a block with no recognised field at all is a
        # section heading (intro, collaborations, how to apply), not an idea.
        ideas = [i for i in ideas if i.labelled_fields or i.links]
    with_links = sum(1 for i in ideas if i.links)
    high_blocks = sum(1 for i in ideas if i.confidence == "high")
    if ideas and high_blocks == 0 and with_links >= max(1, len(ideas) // 2):
        # No block is clearly an idea and most link elsewhere: an index of other
        # pages. A stray label in prose does not change that.
        doc.layout = "index"
        doc.sub_pages = _sub_pages(lines)
        # Blocks with some labels or paragraphs of prose may still be the ideas
        # themselves; keep them for when the links lead nowhere.
        prose = sum(len(i.description) for i in ideas) / len(ideas) >= 240
        if labelled_blocks or prose:
            doc.fallback_ideas = ideas
        return doc
    if not ideas:
        doc.layout = "unstructured"
        doc.sub_pages = _sub_pages(lines)
        return doc
    doc.layout = "headings"
    doc.ideas = ideas
    return doc


# ---------------------------------------------------------------- ranking


def rank_ideas(
    ideas: list[ProjectIdea],
    *,
    skills: list[str] | None = None,
    size: str | None = None,
    difficulty: str | None = None,
    interests: list[str] | None = None,
    experience: str | None = None,
    hours_per_week: int | None = None,
) -> list[ProjectIdea]:
    """Order ideas by fit; never drops any, so the user sees the whole page.

    Skills are matched as concepts ("reactjs" is React, "C/C++" counts once), and
    each idea says which skills it would teach.
    """
    from git_into_gsoc.matching.concepts import label
    from git_into_gsoc.matching.ideas import fit_idea, idea_concepts, known_skills, required_skills
    from git_into_gsoc.matching.profile import build_profile

    person = build_profile(
        technologies=skills,
        interests=interests,
        experience=experience,
        hours_per_week=hours_per_week,
    )
    ranked = []
    for idea in ideas:
        score = 0.0
        reasons: list[str] = []
        learn: list[str] = []
        if not person.empty:
            skill_keys, domain_keys = idea_concepts(
                skills=idea.skills, text=f"{idea.title} {idea.description}"
            )
            fit = fit_idea(person, skill_keys=skill_keys, domain_keys=domain_keys)
            if fit.have:
                score += 10 * len(fit.have)
                reasons.append("Skills match: " + ", ".join(fit.have))
            if fit.topics:
                score += 6
                reasons.append("About " + ", ".join(fit.topics))
            learn = fit.to_learn
            # Each skill to learn makes the idea a little harder to start.
            score -= 2 * len(learn)
            # A skill the page says is required counts for more than one it mentions.
            required = required_skills(" ".join([idea.description, *idea.skills]))
            missing = [c for c in required if c not in known_skills(person)]
            if missing:
                score -= 8 * min(2, len(missing))
                reasons.append(
                    "Requires " + ", ".join(label(c) for c in missing) + ", which you did not list"
                )
            elif required:
                score += 4
                reasons.append("You have the skills it says are required")
        if size and idea.size == size:
            score += 6
            reasons.append(f"{idea.hours or ''}h size fits".replace(" h ", " "))
        if difficulty and idea.difficulty == difficulty:
            score += 5
            reasons.append(f"Difficulty {difficulty}")
        if idea.confidence == "high":
            score += 2
        if idea.mentors:
            score += 1
        ranked.append(
            idea.model_copy(
                update={"match_score": score, "match_reasons": reasons, "skills_to_learn": learn}
            )
        )
    ranked.sort(key=lambda i: (-i.match_score, i.title))
    return ranked


# ------------------------------------------------------------------ fetch


def fetch_ideas_document(http: CachedHttpClient, url: str | None, ttl: int) -> IdeasDocument | None:
    """Fetch and parse an ideas page; None when it cannot be read as a document."""
    target = ideas_document_url(url) if url else None
    if not url or not target:
        return None
    try:
        raw = http.get_text(target, ttl=ttl)
    except NotFoundError:
        # The raw file name is a guess. A GitHub wiki page can live in a folder
        # (CGAL's GSoC/Project-Ideas.md), differ in case (AboutCode), or be Org mode
        # (R): the page itself, as GitHub renders it, is then the way in. Any other
        # failure (blocked, rate-limited) would fail there too. Only wiki pages: a
        # missing file's page is GitHub's app around nothing.
        if target == url.split("#", 1)[0] or not _GITHUB_WIKI_RE.match(url):
            return None
        try:
            target = url.split("#", 1)[0]
            raw = http.get_text(target, ttl=ttl)
        except HttpError:
            return None
        body = _github_wiki_body(raw, target)
        if body is None:
            return None
        raw = body
    except HttpError:
        return None
    doc = extract_ideas(to_lines(raw, base_url=target), source_url=url)
    doc.fetched_url = target
    if _looks_like_html(raw):
        # R lists its projects in a table: Proposal, Hours, Status, Mentors, Languages.
        # Flattened into lines, every cell reads as text and nothing as an idea.
        rows = table_ideas(raw, source_url=url)
        if len(rows) >= MIN_IDEAS_FOR_LAYOUT and len(rows) > len(doc.ideas):
            doc.ideas, doc.fallback_ideas, doc.sub_pages = rows, [], []
            doc.layout = "table"
    if _MEDIAWIKI_RE.search(raw[:20_000]):
        # OpenStreetMap writes each idea as a {{GSoC idea |title=... |skills=...}}
        # template. The rendered page shows them as boxes this cannot tell apart from
        # the wiki's own; the wikitext names every field.
        wikitext_url = target + ("&" if "?" in target else "?") + "action=raw"
        try:
            ideas = wiki_template_ideas(http.get_text(wikitext_url, ttl=ttl), source_url=url)
        except HttpError:
            ideas = []
        if len(ideas) >= MIN_IDEAS_FOR_LAYOUT:
            doc.ideas, doc.fallback_ideas, doc.sub_pages = ideas, [], []
            doc.layout = "templates"
            doc.fetched_url = wikitext_url
    return doc


_GITHUB_WIKI_RE = re.compile(r"https?://(?:www\.)?github\.com/[^/]+/[^/]+/wiki/", re.I)


def _github_wiki_body(html: str, url: str) -> str | None:
    """The page's own text from a rendered GitHub wiki page, or None when it is gone.

    GitHub sends a missing wiki page to the wiki's Home (Libreswan's 2026 ideas link),
    and its menus ("Navigation Menu", "Clone this wiki locally") are headings that
    hide R's table of projects.
    """
    parsed = urlparse(url)
    if parsed.netloc.lower().removeprefix("www.") != "github.com" or "/wiki/" not in parsed.path:
        return html
    page = parsed.path.rstrip("/").rsplit("/", 1)[-1].lower()
    if page != "home" and re.search(r"<title>\s*Home\s*·", html):
        return None
    start = html.find('id="wiki-body"')
    if start == -1:
        return html
    end = html.find('id="wiki-footer"', start)
    return "<div " + html[start : end if end != -1 else len(html)]


class _TableParser(HTMLParser):
    """Rows of every table: each cell's text and its first link."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.tables: list[list[list[tuple[str, str | None]]]] = []
        self._cell: list[str] | None = None
        self._link: str | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self.tables.append([])
        elif self._depth == 1 and tag == "tr":
            self.tables[-1].append([])
        elif self._depth == 1 and tag in ("td", "th") and self.tables and self.tables[-1]:
            self._cell, self._link = [], None
        elif tag == "a" and self._cell is not None and self._link is None:
            href = dict(attrs).get("href")
            if href and not href.startswith("#"):
                self._link = urljoin(self.base_url, href)
        elif tag == "br" and self._cell is not None:
            self._cell.append(", ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self.tables and self.tables[-1]:
            text = " ".join("".join(self._cell).split())
            self.tables[-1][-1].append((text, self._link))
            self._cell = None
        elif tag == "table" and self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


# Table headers, by the field their column fills. "Project", "Proposal", or "Idea"
# needs one more idea field beside it; "Topic", "Title", or "Name" needs two, since an
# event's agenda (Topic, Speaker, Duration) is a table too.
_TABLE_COLUMNS = (
    ("title", re.compile(r"proposal|project|idea|title|topic|^name$", re.I)),
    ("mentors", re.compile(r"mentor", re.I)),
    ("size", re.compile(r"hours|size|length|duration", re.I)),
    ("difficulty", re.compile(r"difficult|level|complexity", re.I)),
    ("skills", re.compile(r"skill|language|technolog|stack|tools|tech\b", re.I)),
)
_STRONG_TITLE = re.compile(r"proposal|project|idea", re.I)
# GCC's wiki lists past years' accepted projects as Project, Student, Mentors.
_PAST_COLUMN = re.compile(r"student|contributor|participant|accepted|\byear\b", re.I)


def table_ideas(html_text: str, *, source_url: str) -> list[ProjectIdea]:
    """Ideas from every table with a title column and enough idea fields.

    CCExtractor keeps one table per area, so all of them count, in page order.
    """
    parser = _TableParser(source_url)
    try:
        parser.feed(html_text[:MAX_CHARS])
    except Exception:
        return []
    ideas: list[ProjectIdea] = []
    seen: set[str] = set()
    for rows in parser.tables:
        if len(rows) < 2:
            continue
        header = [text.lower() for text, _ in rows[0]]
        if any(_PAST_COLUMN.search(name) for name in header):
            continue
        columns: dict[str, int] = {}
        for index, name in enumerate(header):
            for field, pattern in _TABLE_COLUMNS:
                if field not in columns and pattern.search(name):
                    columns[field] = index
                    break
        if "title" not in columns:
            continue
        needed = 1 if _STRONG_TITLE.search(header[columns["title"]]) else 2
        if len(columns) - 1 < needed:
            continue
        for row in rows[1:]:
            if len(row) <= columns["title"]:
                continue
            title, link = row[columns["title"]]
            # R's first row is "MENTORS-COPY-THIS-TEMPLATE".
            low = title.lower()
            if not title or "template" in low or low in _TEMPLATE_TITLES or low in seen:
                continue
            seen.add(low)
            idea = ProjectIdea(title=_clean(title)[:200], source_url=source_url)
            if link:
                idea.links.append(link)
            for field, index in columns.items():
                if field != "title" and index < len(row) and row[index][0]:
                    _assign(idea, field, row[index][0])
            idea.confidence = "high" if _labelled(idea) >= 2 else "medium"
            ideas.append(idea)
    return ideas


_MEDIAWIKI_RE = re.compile(r'<meta name="generator" content="MediaWiki', re.I)
# Template parameters, by the field they fill (OpenStreetMap's {{GSoC idea}} uses
# title, summary, skills, useful_skills, length, difficulty, mentors).
_WIKI_PARAMS = {
    "title": "title",
    "name": "title",
    "project": "title",
    "summary": "description",
    "description": "description",
    "skills": "skills",
    "required_skills": "skills",
    "useful_skills": "skills",
    "preferred_skills": "skills",
    "length": "size",
    "size": "size",
    "duration": "size",
    "hours": "size",
    "difficulty": "difficulty",
    "level": "difficulty",
    "mentors": "mentors",
    "mentor": "mentors",
    "possible_mentors": "mentors",
    "outcome": "outcome",
    "expected_outcome": "outcome",
    "expected_results": "outcome",
    "deliverables": "outcome",
}


def _wiki_blocks(text: str) -> list[tuple[int, str]]:
    """(start, body) of each top-level {{...}} template, braces balanced."""
    blocks: list[tuple[int, str]] = []
    depth, start, i = 0, 0, 0
    while i < len(text) - 1:
        pair = text[i : i + 2]
        if pair == "{{":
            if depth == 0:
                start = i
            depth += 1
            i += 2
        elif pair == "}}" and depth:
            depth -= 1
            if depth == 0:
                blocks.append((start, text[start + 2 : i]))
            i += 2
        else:
            i += 1
    return blocks


def _wiki_params(body: str) -> dict[str, str]:
    """`key=value` parameters of one template, split on top-level pipes only."""
    parts: list[str] = []
    depth, current = 0, list[str]()
    for i, char in enumerate(body):
        pair = body[i : i + 2]
        if pair in ("{{", "[["):
            depth += 1
        elif pair in ("}}", "]]") and depth:
            depth -= 1
        if char == "|" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    params: dict[str, str] = {}
    for part in parts[1:]:
        key, sep, value = part.partition("=")
        if sep:
            params[key.strip().lower()] = value.strip()
    return params


def _wiki_text(value: str) -> str:
    """Wiki markup to plain text: [[User:A|A]] is A, [https://x text] is text."""
    value = re.sub(r"\{\{[^{}]*\}\}", " ", value)
    value = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", value)
    value = re.sub(r"\[(?:https?|mailto):[^\s\]]+\s+([^\]]+)\]", r"\1", value)
    value = re.sub(r"\[(https?://[^\s\]]+)\]", r"\1", value)
    value = re.sub(r"'{2,}|<[^>]+>", " ", value)
    return " ".join(value.split())


def wiki_template_ideas(wikitext: str, *, source_url: str) -> list[ProjectIdea]:
    """Ideas written as MediaWiki templates with a title parameter, one per template."""
    headings = [
        (m.start(), m.group(1).strip())
        for m in re.finditer(r"^==+\s*(.+?)\s*==+\s*$", wikitext, re.M)
    ]
    ideas: list[ProjectIdea] = []
    for start, body in _wiki_blocks(wikitext[:MAX_CHARS]):
        params = _wiki_params(body)
        title = _wiki_text(params.get("title") or params.get("name") or params.get("project") or "")
        if not title:
            continue
        heading = next((h for pos, h in reversed(headings) if pos < start), "")
        # Every value here is text strangers wrote: it goes through _clean, as the
        # parameters do in _assign.
        section = _clean(_wiki_text(heading))[:120] or None
        idea = ProjectIdea(title=_clean(title)[:200], section=section, source_url=source_url)
        for key, value in params.items():
            field = _WIKI_PARAMS.get(key)
            if field and field != "title" and (text := _wiki_text(value)):
                _assign(idea, field, text)
        for url in _URL_RE.findall(body):
            cleaned = url.rstrip(".,;:]")
            if cleaned not in idea.links:
                idea.links.append(cleaned)
        idea.links = idea.links[:10]
        idea.confidence = "high" if _labelled(idea) >= 2 else "medium"
        ideas.append(idea)
    return ideas
