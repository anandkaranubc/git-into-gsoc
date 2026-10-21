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
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import parse_qs, unquote, urlparse

from git_into_gsoc.http_client import CachedHttpClient, HttpError
from git_into_gsoc.models import IdeasDocument, ProjectIdea

MAX_CHARS = 600_000
MIN_IDEAS_FOR_LAYOUT = 2

_GDOC = re.compile(r"^/document/d/([A-Za-z0-9_-]+)")
_URL_RE = re.compile(r"https?://[^\s<>()\"'\]]+")
_HOURS_RE = re.compile(r"\b(90|175|350)\s*(?:h\b|hr|hrs|hours|-hour|hour)?", re.I)
_SIZE_WORD_RE = re.compile(r"\b(small|medium|large)\b", re.I)

LABELS: dict[str, tuple[str, ...]] = {
    "difficulty": ("difficulty", "difficulty level", "difficulty rating", "complexity"),
    "size": (
        "project size",
        "expected size of project",
        "expected project size",
        "size",
        "duration",
        "length",
        "project length",
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
_LABEL_LOOKUP = {alias: field for field, aliases in LABELS.items() for alias in aliases}
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
)
_AI_RE = re.compile(r"\b(ai|llm|llms|chatgpt|copilot|gemini|claude|language model)s?\b", re.I)
_POLICY_RE = re.compile(
    r"\b(propos|submission|polic|allow|permit|prohibit|forbid|ban|reject|disclos|generated|"
    r"disclose|plagiar|cheat|assist|offload|rely)\w*",
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
    )
    _SKIP: ClassVar[frozenset[str]] = frozenset(
        {"script", "style", "noscript", "svg", "head", "nav", "footer"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._skip = 0
        self._heading: int | None = None
        self._bold = 0
        self._href: str | None = None
        self._li = False

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
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush()
            self._heading = int(tag[1])
        elif tag == "li":
            self._flush()
            self._li = True
        elif tag in self._BLOCK:
            self._flush()
        elif tag in {"b", "strong"}:
            self._bold += 1
            self._buf.append("**")
        elif tag == "a":
            self._href = dict(attrs).get("href") or None

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
        elif tag in self._BLOCK:
            self._flush()
        elif tag in {"b", "strong"} and self._bold:
            self._bold -= 1
            self._buf.append("**")
        elif tag == "a" and self._href:
            if self._href.startswith(("http://", "https://")):
                self._buf.append(f" ({self._href})")
            self._href = None

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def html_to_lines(raw: str) -> list[str]:
    parser = _LineParser()
    parser.feed(raw[:MAX_CHARS])
    parser.close()
    return [html.unescape(line) for line in parser.lines]


def markdown_to_lines(raw: str) -> list[str]:
    lines = []
    for line in raw[:MAX_CHARS].splitlines():
        stripped = line.rstrip()
        if not stripped.strip():
            continue
        if re.match(r"^\s*(?:---+|===+|\*\*\*+)\s*$", stripped):
            continue
        setext = re.match(r"^(={3,}|-{3,})\s*$", stripped)
        if setext:
            continue
        lines.append(stripped)
    return lines


def _looks_like_html(raw: str) -> bool:
    head = raw[:2000].lower()
    return "<html" in head or "<body" in head or "<!doctype html" in head or "<div" in head


def to_lines(raw: str) -> list[str]:
    return html_to_lines(raw) if _looks_like_html(raw) else markdown_to_lines(raw)


# ------------------------------------------------------------------ parsing


def _heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
    if not match:
        return None
    text = re.sub(r"[*_`]+", "", match.group(2)).strip()
    return len(match.group(1)), text


def _label(line: str) -> tuple[str, str, str] | None:
    """(field, label, value) when a line is `Label: value` for a known label."""
    match = _LABEL_LINE_RE.match(line)
    if not match:
        return None
    label = re.sub(r"\s+", " ", match.group("label")).strip().lower().rstrip(".")
    field = _LABEL_LOOKUP.get(label)
    if field is None:
        return None
    return field, label, match.group("value").strip()


def _clean(value: str) -> str:
    value = re.sub(r"\*\*|__|`", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _split_list(value: str) -> list[str]:
    value = _clean(value)
    parts = re.split(r"\s*(?:,|;|/| and | or |\|)\s*(?![^()]*\))", value)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _split_people(value: str) -> list[str]:
    value = _clean(value)
    parts = re.split(r"\s*(?:,|;| and |&)\s*(?![^()]*\))", value)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def normalize_size(value: str) -> tuple[str | None, int | None]:
    hours = _HOURS_RE.search(value or "")
    if hours:
        number = int(hours.group(1))
        return {90: "small", 175: "medium", 350: "large"}[number], number
    word = _SIZE_WORD_RE.search(value or "")
    if word:
        size = word.group(1).lower()
        return size, {"small": 90, "medium": 175, "large": 350}[size]
    return None, None


def normalize_difficulty(value: str) -> str | None:
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


def ai_policy_sentences(text: str, limit: int = 3) -> list[str]:
    """Sentences that look like a rule about AI/LLM use (not AI as a topic)."""
    found: list[str] = []
    flat = re.sub(r"\s+", " ", re.sub(r"[#*_`]+", "", text))
    for sentence in re.split(r"(?<=[.!?])\s+", flat):
        if _AI_RE.search(sentence) and _POLICY_RE.search(sentence):
            clean = sentence.strip()
            if 20 <= len(clean) <= 400 and clean not in found:
                found.append(clean)
            if len(found) >= limit:
                break
    return found


def _choose_level(lines: list[str]) -> int | None:
    counts: dict[int, int] = {}
    for line in lines:
        head = _heading(line)
        if head and head[1].strip().lower().rstrip(".:") not in _LABEL_LOOKUP:
            counts[head[0]] = counts.get(head[0], 0) + 1
    candidates = [
        (count, -level) for level, count in counts.items() if count >= MIN_IDEAS_FOR_LAYOUT
    ]
    if not candidates:
        return None
    # Most frequent level wins; on a tie prefer the deeper one (idea headings sit under sections).
    best = max(candidates)
    return -best[1]


def _is_non_idea(title: str) -> bool:
    low = title.lower().strip(" :")
    return (
        any(
            low == word or low.startswith(word + " ") or low.endswith(" " + word)
            for word in _NON_IDEA_HEADINGS
        )
        or len(low) < 3
    )


def _parse_block(
    title: str, body: list[str], *, section: str | None, source_url: str
) -> ProjectIdea:
    idea = ProjectIdea(title=title, section=section, source_url=source_url)
    free_text: list[str] = []
    current: str | None = None
    for line in body:
        head = _heading(line)
        if head:
            label = head[1].strip().lower().rstrip(".:")
            current = _LABEL_LOOKUP.get(label)
            if current is None:
                current = None
                free_text.append(head[1])
            continue
        labelled = _label(line)
        if labelled:
            field, _, value = labelled
            current = field if not value else None
            if value:
                _assign(idea, field, value)
            continue
        if current:
            _assign(idea, current, line)
        else:
            free_text.append(line)
    if not idea.description:
        text = " ".join(_clean(x) for x in free_text if not _URL_RE.fullmatch(x.strip()))
        idea.description = text[:500].strip()
    for line in [*body, title]:
        for url in _URL_RE.findall(line):
            cleaned = url.rstrip(".,;:")
            if cleaned not in idea.links:
                idea.links.append(cleaned)
    idea.links = idea.links[:10]
    labelled_fields = sum(
        1
        for value in (idea.difficulty, idea.size, idea.mentors, idea.skills, idea.expected_outcome)
        if value
    )
    if labelled_fields >= 2:
        idea.confidence = "high"
    elif labelled_fields == 1 or len(body) >= 3:
        idea.confidence = "medium"
    else:
        idea.confidence = "low"
    return idea


def _assign(idea: ProjectIdea, field: str, value: str) -> None:
    value = value.strip()
    if not value:
        return
    if field == "difficulty":
        idea.difficulty_raw = (idea.difficulty_raw + " " + _clean(value)).strip()
        idea.difficulty = normalize_difficulty(idea.difficulty_raw) or idea.difficulty
    elif field == "size":
        idea.size_raw = (idea.size_raw + " " + _clean(value)).strip()
        size, hours = normalize_size(idea.size_raw)
        idea.size, idea.hours = size or idea.size, hours or idea.hours
    elif field == "mentors":
        idea.mentors.extend(p for p in _split_people(value) if p not in idea.mentors)
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


def _sub_pages(lines: list[str]) -> list[dict[str, str]]:
    """Outbound links grouped under headings: the shape of an umbrella index page."""
    pages: list[dict[str, str]] = []
    current = ""
    seen: set[str] = set()
    for line in lines:
        head = _heading(line)
        if head:
            current = head[1]
            continue
        for url in _URL_RE.findall(line):
            cleaned = url.rstrip(".,;:)")
            if cleaned in seen or _is_non_idea(current):
                continue
            seen.add(cleaned)
            pages.append({"title": current or cleaned, "url": cleaned})
    return pages[:40]


def extract_ideas(lines: list[str], *, source_url: str) -> IdeasDocument:
    level = _choose_level(lines)
    doc = IdeasDocument(source_url=source_url, fetched_url=source_url)
    doc.headings = [h[1] for line in lines if (h := _heading(line))][:60]
    doc.ai_policy = ai_policy_sentences("\n".join(lines))
    if level is None:
        doc.layout = "unstructured"
        doc.sub_pages = _sub_pages(lines)
        return doc

    blocks: list[tuple[str, list[str], str | None]] = []
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
            continue
        if head and head[0] == level:
            if title is not None:
                blocks.append((title, body, section))
            title, body = head[1], []
            continue
        if title is not None:
            body.append(line)
    if title is not None:
        blocks.append((title, body, section))

    ideas = [
        _parse_block(t, b, section=s, source_url=source_url)
        for t, b, s in blocks
        if not _is_non_idea(t)
    ]
    good = [i for i in ideas if i.confidence in {"high", "medium"}]
    link_only = all(
        not any(i.description or i.mentors or i.skills or i.size for i in ideas) and i.links
        for i in ideas
    )
    if ideas and (link_only or not good):
        doc.layout = "index" if any(i.links for i in ideas) else "unstructured"
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
) -> list[ProjectIdea]:
    """Order ideas by fit; never drops any, so the user sees the whole page."""
    wanted = {s.strip().lower() for s in skills or [] if s.strip()}
    ranked = []
    for idea in ideas:
        score = 0.0
        reasons: list[str] = []
        have = {s.lower() for s in idea.skills}
        hits = sorted(w for w in wanted if any(w == h or w in h or h in w for h in have))
        if hits:
            score += 10 * len(hits)
            reasons.append("Skills match: " + ", ".join(hits))
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
        ranked.append(idea.model_copy(update={"match_score": score, "match_reasons": reasons}))
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
    except HttpError:
        return None
    doc = extract_ideas(to_lines(raw), source_url=url)
    doc.fetched_url = target
    return doc
