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
from git_into_gsoc.text import clean_untrusted

MAX_CHARS = 600_000
MIN_IDEAS_FOR_LAYOUT = 2

_GDOC = re.compile(r"^/document/d/([A-Za-z0-9_-]+)")
_URL_RE = re.compile(r"https?://[^\s<>()\"'\]]+")
_MD_LINK_RE = re.compile(r"\[([^\]\n]{1,80})\]\((https?://[^\s)]+)\)")
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
)
_COMMENT_RE = re.compile(r"^\s*(?:\[//\]:\s*#|#(?!#*\s)|<!--)")
_BULLET_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
_AI_RE = re.compile(r"\b(ai|llm|llms|chatgpt|copilot|gemini|claude|language model)s?\b", re.I)
_POLICY_RE = re.compile(
    r"\b(propos\w*|submission\w*|polic\w*|allow\w*|permit\w*|prohibit\w*|forbid\w*|"
    r"ban(?:ned|s)?|reject\w*|disclos\w*|generated|written by|plagiar\w*|cheat\w*|"
    r"offload\w*|rely on|must not|should not|do not|don't|not accept\w*|accept\w*)\b",
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
    text = re.sub(r"<!--.*?-->", " ", raw[:MAX_CHARS], flags=re.S)
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped.strip():
            continue
        if _COMMENT_RE.match(stripped):
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
    label = _norm_label(match.group("label"))
    field = _LABEL_LOOKUP.get(label)
    if field is None:
        return None
    return field, label, match.group("value").strip()


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


def _paragraphs(text: str) -> list[str]:
    """Join wrapped lines into paragraphs; a heading or a list item starts a new one."""
    chunks: list[list[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not chunks or _heading(line) or _BULLET_RE.match(line):
            chunks.append([line])
        else:
            chunks[-1].append(line)
    return [" ".join(chunk) for chunk in chunks]


def ai_policy_sentences(text: str, limit: int = 3) -> list[str]:
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
    idea = ProjectIdea(
        title=clean_untrusted(title, limit=200), section=section, source_url=source_url
    )
    free_text: list[str] = []
    current: str | None = None
    for line in body:
        head = _heading(line)
        if head:
            label = _norm_label(head[1])
            current = _LABEL_LOOKUP.get(label)
            if current is None:
                current = None
                free_text.append(head[1])
            continue
        labelled = _label(line)
        if labelled:
            field, _, value = labelled
            if value.startswith("#"):  # inline template note, not a value
                value = ""
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


# Headings whose links lead away from ideas (navigation, people, process). A
# heading about ideas, such as "Ideas Pages" on an umbrella index, keeps its links.
_NAV_HEADINGS = tuple(h for h in _NON_IDEA_HEADINGS if "idea" not in h and h != "template")


def _is_nav_heading(title: str) -> bool:
    low = title.lower().strip(" :")
    return any(
        low == word or low.startswith(word + " ") or low.endswith(" " + word)
        for word in _NAV_HEADINGS
    )


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
        if _is_nav_heading(current):
            continue
        titles = {url.rstrip(".,;:)"): text for text, url in _MD_LINK_RE.findall(line)}
        for url in _URL_RE.findall(line):
            cleaned = url.rstrip(".,;:)")
            if cleaned in seen:
                continue
            seen.add(cleaned)
            title = _clean(titles.get(cleaned) or "") or current or cleaned
            pages.append({"title": title, "url": cleaned})
    return pages[:40]


def extract_ideas(lines: list[str], *, source_url: str) -> IdeasDocument:
    doc = IdeasDocument(source_url=source_url, fetched_url=source_url)
    doc.headings = [h[1] for line in lines if (h := _heading(line))][:60]
    levels = _candidate_levels(lines)
    if not levels:
        doc.sub_pages = _sub_pages(lines)
        # A page that is mostly links to other pages, such as an umbrella
        # organization's list of its projects, is an index even without headings.
        mostly_links = len(doc.sub_pages) >= 3 and len(doc.sub_pages) * 3 >= len(lines)
        doc.layout = "index" if mostly_links else "unstructured"
        doc.ai_policy = ai_policy_sentences("\n".join(lines))
        return doc

    # Try every candidate level; keep the one whose blocks carry the most labelled fields.
    best: tuple[int, int, int, list[ProjectIdea], list[str]] | None = None
    for level in levels:
        blocks, outside = _split_blocks(lines, level)
        ideas = [
            _parse_block(t, b, section=s, source_url=source_url)
            for t, b, s in blocks
            if not _is_non_idea(t)
        ]
        yield_ = sum(_labelled(i) for i in ideas)
        key = (yield_, len(ideas), level)
        if best is None or key > best[:3]:
            best = (*key, ideas, outside)
    assert best is not None
    _, _, _, ideas, outside = best
    doc.ai_policy = ai_policy_sentences("\n".join(outside))

    labelled_blocks = sum(1 for i in ideas if _labelled(i))
    if ideas and labelled_blocks * 2 >= len(ideas):
        # On a mostly labelled page, a block with no recognised field at all is a
        # section heading (intro, collaborations, how to apply), not an idea.
        ideas = [i for i in ideas if i.labelled_fields or i.links]
    with_links = sum(1 for i in ideas if i.links)
    if ideas and labelled_blocks == 0 and with_links >= max(1, len(ideas) // 2):
        doc.layout = "index"
        doc.sub_pages = _sub_pages(lines)
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
